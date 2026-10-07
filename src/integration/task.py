import asyncio
import logging
from decimal import Decimal

from huey import signals
from svcs import Container

from src.account.api.account import AccountApi
from src.account.api.position import PositionApi
from src.account.api_types import Account
from src.auth.api import UserApi
from src.auth.api_types import UserId
from src.config.settings import settings
from src.core.context import get_request_id, request_id_ctx_var, set_request_id
from src.core.email import EmailService, ExternalAccountErrorEmailData
from src.core.enum import InstitutionEnum
from src.integration.brokers import BrokerApiGateway
from src.integration.brokers.api_types import BrokerAccountId
from src.integration.brokers.exception import (
    ExternalAPIError,
    LoginFailedError,
    OTPRequiredError,
    SessionDoesNotExistError,
    SessionExpiredError,
)
from src.integration.exception import (
    AccountPositionsSyncError,
    IntegrationUserNotFoundError,
)
from src.integration.repository import IntegrationUserRepository
from src.integration.sync_status import mark_sync_finished, mark_sync_started
from src.market.api import SecurityApi
from src.market.fx import FxRateProvider
from src.worker import huey
from src.ws.api_types import AccountSyncMessage, WsEventType
from src.ws.manager import ws_manager

logger = logging.getLogger(__name__)


@huey.task()
def sync_account_positions_task(
    user_id: UserId,
    account: Account,
    broker_account_id: BrokerAccountId,
    broker_class: type[BrokerApiGateway],
    request_id: str | None = None,
) -> None:
    """
    Huey task to sync positions for newly imported accounts
    and notify the frontend via WebSockets.
    Runs in the huey-worker process, isolated from the FastAPI lifecycle.
    """
    if request_id is None:
        request_id = get_request_id()

    asyncio.run(
        _sync_account_positions_task(
            user_id, account, broker_account_id, broker_class, request_id=request_id
        )
    )


async def _do_sync_positions(
    account: Account,
    broker_account_id: BrokerAccountId,
    broker_class: type[BrokerApiGateway],
    svcs_container: Container,
) -> None:
    security_api = await svcs_container.aget(SecurityApi)
    integration_user_repository = await svcs_container.aget(IntegrationUserRepository)

    if account.integration_user_id is None:
        msg = "Account does not have an integration user"
        raise AccountPositionsSyncError(msg)

    integration_user = await integration_user_repository.get(
        account.integration_user_id,
    )

    if integration_user is None:
        raise IntegrationUserNotFoundError(account.integration_user_id)

    broker = await svcs_container.aget(broker_class)
    broker_positions = await broker.get_positions_by_account(
        integration_user=integration_user,
        broker_account_id=broker_account_id,
    )

    position_api = await svcs_container.aget(PositionApi)

    positions_api_types = []
    for broker_position in broker_positions:
        security = await security_api.get_or_create_from_broker(
            institution_id=integration_user.institution_id,
            broker_symbol=broker_position.symbol,
            broker_exchange=broker_position.exchange,
            broker_name=broker_position.name,
        )

        positions_api_types.append(
            broker_position.to_position(account_id=account.id, security_id=security.id)
        )

    await position_api.create(positions_api_types)

    account_api = await svcs_container.aget(AccountApi)

    # Cash is an account attribute (`free_cash`), not a position, so it is
    # fetched separately and converted into the account currency. Gateways that
    # cannot report cash inherit the base no-op, so their free_cash is left
    # untouched (it may come from a CSV import).
    if _broker_reports_cash_balances(broker):
        cash_balances = await broker.get_cash_balances(
            integration_user=integration_user,
            broker_account_id=broker_account_id,
        )
        await account_api.update_free_cash(
            account.id,
            await _sum_cash_in_account_currency(
                cash_balances, str(account.currency), svcs_container
            ),
        )

    # Sync account details (net_deposits)
    broker_accounts = await broker.get_accounts(integration_user)
    broker_account = next(
        (a for a in broker_accounts if a.id == broker_account_id), None
    )
    if broker_account:
        await account_api.update_net_deposits(
            account.id,
            (
                float(broker_account.net_deposits)
                if broker_account.net_deposits is not None
                else None
            ),
        )
        broker_value = float(broker_account.value)
        await account_api.update_broker_value(account.id, broker_value)
        await _reconcile_broker_value(account, broker_value, svcs_container)
        await account_api.update_last_sync_at(account.id)


async def _reconcile_broker_value(
    account: Account, broker_value: float, svcs_container: Container
) -> None:
    """Log when our computed present value disagrees with the broker value.

    A mismatch larger than 1% of the broker value usually means a valuation gap
    (missing cash, a stale price or a bad FX rate).

    ``PositionService`` is imported locally because this module is imported by
    ``src.integration.api``, which the position service imports in turn; a
    module-level import would create an import cycle.
    """
    from src.account.service.position import PositionService  # noqa: PLC0415

    position_service = await svcs_container.aget(PositionService)
    totals = await position_service.get_total_for_account(account.id, account.currency)
    computed_value = float(totals.value.amount)

    if abs(computed_value - broker_value) > 0.01 * abs(broker_value):
        logger.warning(
            "Broker value mismatch for account %s: broker_value=%s computed_value=%s",
            account.id,
            broker_value,
            computed_value,
        )


def _broker_reports_cash_balances(broker: BrokerApiGateway) -> bool:
    """Return True when ``broker`` overrides the cash-balance no-op.

    The base ``BrokerApiGateway.get_cash_balances`` returns ``{}`` to signal
    "cash not reported". A gateway that does not override it must leave
    ``free_cash`` untouched rather than clearing it to zero.
    """
    return (
        getattr(type(broker), "get_cash_balances", None)
        is not BrokerApiGateway.get_cash_balances
    )


async def _sum_cash_in_account_currency(
    cash_balances: dict[str, Decimal],
    account_currency: str,
    svcs_container: Container,
) -> float:
    """Convert every cash balance to ``account_currency`` and sum them."""
    if not cash_balances:
        return 0.0

    fx_provider = await svcs_container.aget(FxRateProvider)
    converter = await fx_provider.converter()

    # ``CurrencyConverter.convert`` returns a float (our converters are not
    # built with ``decimal=True``), so accumulate in float.
    total = 0.0
    for currency, amount in cash_balances.items():
        if currency == account_currency:
            total += float(amount)
        else:
            total += converter.convert(
                amount=float(amount),
                currency=currency,
                new_currency=account_currency,
            )

    return round(total, 2)


_SYNC_ERROR_MESSAGE_MAPPING: tuple[tuple[type[Exception], str], ...] = (
    (
        SessionExpiredError,
        (
            "Your session with the institution has expired. Please log in to"
            " your account settings to reconnect and re-authenticate your"
            " external account."
        ),
    ),
    (
        SessionDoesNotExistError,
        (
            "No active session was found for your external account. Please log"
            " in to your account settings to link and authenticate your"
            " external account."
        ),
    ),
    (
        OTPRequiredError,
        (
            "A one-time verification code (OTP) or two-factor authentication"
            " is required. Please log in to your account settings to complete"
            " authentication."
        ),
    ),
    (
        LoginFailedError,
        (
            "Authentication with the external institution failed. Please check"
            " your credentials and reconnect your external account."
        ),
    ),
    (
        IntegrationUserNotFoundError,
        (
            "Integration details for this external account could not be found."
            " Please reconnect your external account."
        ),
    ),
    (
        ExternalAPIError,
        (
            "An error occurred while communicating with the external"
            " institution. Please try again later."
        ),
    ),
)


def _format_sync_error_message(exc: Exception) -> str:
    if isinstance(exc, AccountPositionsSyncError):
        return str(exc) or (
            "Failed to sync account positions. Please try again or reconnect"
            " your external account."
        )

    for exc_cls, msg in _SYNC_ERROR_MESSAGE_MAPPING:
        if isinstance(exc, exc_cls):
            return msg

    return (
        "An unexpected error occurred while syncing your account positions."
        " Please try again later."
    )


async def _send_sync_error_email(
    user_id: UserId,
    account: Account,
    exc: Exception,
    svcs_container: Container,
) -> None:
    user_api = await svcs_container.aget(UserApi)
    email = await user_api.get_email_for_user(user_id)
    if not email:
        logger.warning(
            "User %s has no email or not found; skipping sync error email",
            user_id,
        )
        return

    try:
        institution_name = (
            InstitutionEnum(account.institution_id).name.replace("_", " ").title()
        )
    except ValueError:
        institution_name = str(account.institution_id)

    email_data = ExternalAccountErrorEmailData(
        account_name=account.name,
        institution_name=institution_name,
        error_message=_format_sync_error_message(exc),
        deeplink=f"{settings.frontend_url}/accounts",
    )

    email_service = await svcs_container.aget(EmailService)
    await email_service.send_external_account_error_email(
        recipient=email,
        data=email_data,
    )


async def _sync_account_positions_task(
    user_id: UserId,
    account: Account,
    broker_account_id: BrokerAccountId,
    broker_class: type[BrokerApiGateway],
    request_id: str | None = None,
) -> None:
    """
    Async implementation of sync_positions_task.
    """
    if huey.svcs_registry is None:
        msg = "Worker registry not initialized"
        raise RuntimeError(msg)

    req_token = set_request_id(request_id) if request_id else None

    try:
        async with Container(huey.svcs_registry) as svcs_container:
            try:
                await mark_sync_started(user_id, account.id)
            except Exception:
                logger.exception(
                    "Failed to mark sync started for account %s", account.id
                )

            try:
                # Send sync_started websocket message
                await ws_manager.send_personal_message(
                    AccountSyncMessage(
                        type=WsEventType.ACCOUNT_SYNC_STARTED, account_id=account.id
                    ).model_dump(mode="json"),
                    user_id,
                )

                await _do_sync_positions(
                    account, broker_account_id, broker_class, svcs_container
                )

                # Send sync_finished websocket message
                await ws_manager.send_personal_message(
                    AccountSyncMessage(
                        type=WsEventType.ACCOUNT_SYNC_FINISHED, account_id=account.id
                    ).model_dump(mode="json"),
                    user_id,
                )
            except Exception as exc:
                logger.exception("Failed to sync positions for account %s", account.id)
                try:
                    await _send_sync_error_email(user_id, account, exc, svcs_container)
                except Exception:
                    logger.exception(
                        "Failed to send sync error email for account %s (user %s)",
                        account.id,
                        user_id,
                    )
                # Send sync_failed websocket message
                await ws_manager.send_personal_message(
                    AccountSyncMessage(
                        type=WsEventType.ACCOUNT_SYNC_FAILED, account_id=account.id
                    ).model_dump(mode="json"),
                    user_id,
                )
                raise
            finally:
                await mark_sync_finished(user_id, account.id)
    finally:
        if req_token is not None:
            request_id_ctx_var.reset(req_token)


@huey.signal(signals.SIGNAL_INTERRUPTED)
def handle_interrupted_task(signal, task, exc=None):
    _ = signal
    _ = exc
    if task.name == "sync_account_positions_task":
        try:
            user_id = task.args[0]
            account = task.args[1]
            asyncio.run(mark_sync_finished(user_id, account.id))
            logger.info(
                "Cleaned up sync status for interrupted task %s (user=%s, account=%s)",
                task.id,
                user_id,
                account.id,
            )
        except Exception:
            logger.exception("Failed to clean up interrupted task %s", task.id)
