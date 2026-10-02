import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

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
from src.observability import emit_event, error_slug_for_error, restore_task_context
from src.worker import huey
from src.ws.api_types import AccountSyncMessage, WsEventType
from src.ws.manager import ws_manager

logger = logging.getLogger(__name__)

#: Catalog events emitted for the account sync flow.
SYNC_COMPLETED_EVENT = "portfolio.sync.completed"
SYNC_FAILED_EVENT = "portfolio.sync.failed"

#: Task name Huey reports for the account-sync task. Huey names the task class
#: after the bare function name when no explicit name is passed, but older
#: Huey releases (and any future change that passes an explicit name) can
#: report a fully-qualified ``<module>.<func>`` name instead — the interrupted
#: handler therefore compares only the final dotted segment.
SYNC_ACCOUNT_POSITIONS_TASK_NAME = "sync_account_positions_task"

#: Bounded set of provider-call outcomes recorded on a sync event.
PROVIDER_CALL_KEYS: frozenset[str] = frozenset(
    {
        "positions_fetch",
        "positions_persist",
        "accounts_reconcile",
        "securities_resolved",
    }
)


@dataclass
class _SyncEventBuilder:
    """Incrementally collected fields for one account sync wide event."""

    account_id: str
    user_id: str
    broker: str
    trigger: str = "manual"
    started_at: float = field(default_factory=time.monotonic)
    positions_seen: int = 0
    positions_changed: int = 0
    provider_calls: dict[str, str | int] = field(default_factory=dict)

    def note_provider_call(self, key: str, value: str | int) -> None:
        """Record a bounded provider-call outcome; unknown keys are ignored."""
        if key in PROVIDER_CALL_KEYS:
            self.provider_calls[key] = value

    def base_fields(self) -> dict[str, Any]:
        """Return the identity fields shared by the completed/failed events."""
        return {
            "account_id": self.account_id,
            "user_id": self.user_id,
            "broker": self.broker,
            "trigger": self.trigger,
        }

    def duration_ms(self) -> float:
        """Return the elapsed sync time in milliseconds."""
        return round((time.monotonic() - self.started_at) * 1000, 3)


def _broker_dimension(institution_id: Any) -> str:
    """Return the internal broker dimension for an account's institution."""
    try:
        return InstitutionEnum(institution_id).name.lower()
    except TypeError, ValueError:
        return str(institution_id)


def _build_sync_event_builder(
    user_id: UserId,
    account: Account,
    trigger: str,
) -> _SyncEventBuilder:
    """Seed the incremental sync event with the account identity."""
    return _SyncEventBuilder(
        account_id=str(account.id),
        user_id=str(user_id),
        broker=_broker_dimension(account.institution_id),
        trigger=trigger,
    )


def _emit_sync_event(name: str, fields: dict[str, Any]) -> None:
    """Emit a sync wide event without ever affecting the sync itself."""
    try:
        emit_event(name, **fields)
    except Exception as error:  # noqa: BLE001
        logger.debug("Failed to emit %s event: %s", name, error)


def _persisted_position_count(persisted: Any, fallback: int) -> int:
    """Return how many positions the persistence layer reports as changed."""
    try:
        return len(persisted)
    except TypeError:
        return fallback


@huey.task()
def sync_account_positions_task(  # noqa: PLR0913, PLR0917
    user_id: UserId,
    account: Account,
    broker_account_id: BrokerAccountId,
    broker_class: type[BrokerApiGateway],
    request_id: str | None = None,
    traceparent: str | None = None,
    trigger: str = "manual",
) -> None:
    """
    Huey task to sync positions for newly imported accounts
    and notify the frontend via WebSockets.
    Runs in the huey-worker process, isolated from the FastAPI lifecycle.

    ``trigger`` records why the sync ran (``manual`` for a user-initiated import
    or retry, ``scheduled`` for a background run); it stays last and defaulted so
    in-flight messages serialized before this field was introduced still work.
    """
    if request_id is None:
        request_id = get_request_id()

    with restore_task_context(
        "sync_account_positions_task",
        request_id=request_id,
        traceparent=traceparent,
    ):
        asyncio.run(
            _sync_account_positions_task(
                user_id,
                account,
                broker_account_id,
                broker_class,
                request_id=request_id,
                trigger=trigger,
            )
        )


async def _do_sync_positions(
    account: Account,
    broker_account_id: BrokerAccountId,
    broker_class: type[BrokerApiGateway],
    svcs_container: Container,
    builder: _SyncEventBuilder,
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
    try:
        broker_positions = await broker.get_positions_by_account(
            integration_user=integration_user,
            broker_account_id=broker_account_id,
        )
    except Exception:
        builder.note_provider_call("positions_fetch", "failed")
        raise
    builder.note_provider_call("positions_fetch", "success")
    builder.positions_seen = len(broker_positions)

    position_api = await svcs_container.aget(PositionApi)

    positions_api_types = []
    securities_resolved = 0
    for broker_position in broker_positions:
        security = await security_api.get_or_create_from_broker(
            institution_id=integration_user.institution_id,
            broker_symbol=broker_position.symbol,
            broker_exchange=broker_position.exchange,
            broker_name=broker_position.name,
        )
        securities_resolved += 1

        positions_api_types.append(
            broker_position.to_position(account_id=account.id, security_id=security.id)
        )
    builder.note_provider_call("securities_resolved", securities_resolved)

    try:
        persisted_positions = await position_api.create(positions_api_types)
    except Exception:
        builder.note_provider_call("positions_persist", "failed")
        raise
    builder.note_provider_call("positions_persist", "success")
    builder.positions_changed = _persisted_position_count(
        persisted_positions, len(positions_api_types)
    )

    # Sync account details (net_deposits)
    try:
        broker_accounts = await broker.get_accounts(integration_user)
        broker_account = next(
            (a for a in broker_accounts if a.id == broker_account_id), None
        )
        account_api = await svcs_container.aget(AccountApi)
        if broker_account:
            await account_api.update_net_deposits(
                account.id,
                float(broker_account.net_deposits)
                if broker_account.net_deposits
                else None,
            )
            await account_api.update_last_sync_at(account.id)
        builder.note_provider_call(
            "accounts_reconcile", "success" if broker_account else "skipped"
        )
    except Exception:
        builder.note_provider_call("accounts_reconcile", "failed")
        raise


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


async def _sync_account_positions_task(  # noqa: PLR0913, PLR0917
    user_id: UserId,
    account: Account,
    broker_account_id: BrokerAccountId,
    broker_class: type[BrokerApiGateway],
    request_id: str | None = None,
    trigger: str = "manual",
) -> None:
    """
    Async implementation of sync_positions_task.
    """
    if huey.svcs_registry is None:
        msg = "Worker registry not initialized"
        raise RuntimeError(msg)

    req_token = set_request_id(request_id) if request_id else None
    sync_event = _build_sync_event_builder(user_id, account, trigger)

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
                    account,
                    broker_account_id,
                    broker_class,
                    svcs_container,
                    sync_event,
                )

                # Send sync_finished websocket message
                await ws_manager.send_personal_message(
                    AccountSyncMessage(
                        type=WsEventType.ACCOUNT_SYNC_FINISHED, account_id=account.id
                    ).model_dump(mode="json"),
                    user_id,
                )

                _emit_sync_event(
                    SYNC_COMPLETED_EVENT,
                    {
                        **sync_event.base_fields(),
                        "positions_seen": sync_event.positions_seen,
                        "positions_changed": sync_event.positions_changed,
                        "provider_calls": dict(sync_event.provider_calls),
                        "outcome": "success",
                        "duration_ms": sync_event.duration_ms(),
                    },
                )
            except Exception as exc:
                logger.exception("Failed to sync positions for account %s", account.id)
                # Emitted before the mail/websocket side effects so the failure
                # record survives even when those fail in turn.
                _emit_sync_event(
                    SYNC_FAILED_EVENT,
                    {
                        **sync_event.base_fields(),
                        "outcome": "failure",
                        "error_slug": error_slug_for_error(exc),
                        "duration_ms": sync_event.duration_ms(),
                    },
                )
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
    logger.debug("Interrupted task %s reported exc: %r", task.id, exc)
    # Huey 3.4.0 reports the bare function name at SIGNAL_INTERRUPTED time
    # (observed: ``task.name == "sync_account_positions_task"``); other Huey
    # versions report ``<module>.<func>``. Comparing only the final dotted
    # segment keeps this branch correct either way.
    if task.name.rsplit(".", 1)[-1] == SYNC_ACCOUNT_POSITIONS_TASK_NAME:
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
