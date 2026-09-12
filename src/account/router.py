import json
import uuid
from typing import Annotated
from uuid import UUID

import redis
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)
from stockholm import Currency
from svcs.fastapi import DepContainer

from src.account.api.position import PositionApi
from src.account.api_types import (
    AccountId,
    AccountRenameRequest,
    AccountTotals,
    PortfolioId,
    Position,
    UserPreferences,
)
from src.account.csv import (
    CsvDiscoveredAccount,
    CsvParserError,
    CsvPositionRecord,
    GenericCsvParser,
)
from src.account.exception import AccountNotFoundError, ApiSyncDisabledError
from src.account.repository import (
    AccountRepository,
    InstitutionRepository,
    PositionRepository,
)
from src.account.schema import (
    AccountHoldingRead,
    AccountHoldingsRead,
    AccountSchema,
    InstitutionSchema,
    PortfolioAccountUpdateRequest,
    PortfolioCreate,
    PortfolioRead,
)
from src.account.service.account import AccountService
from src.account.service.portfolio import PortfolioService
from src.account.service.position import PositionService
from src.auth.api import AuthorizationApi, UserApi, current_user
from src.auth.api_types import User
from src.config.limiter import limiter
from src.core.enum import InstitutionEnum
from src.core.pagination import PaginatedResponse, PaginationParams
from src.integration.sync_status import get_active_syncs
from src.market.api import SecurityApi

account_router = APIRouter(prefix="/accounts")
portfolio_router = APIRouter(prefix="/portfolios")


@portfolio_router.get("/")
async def portfolios(
    user: Annotated[User, Depends(current_user)],
    services: DepContainer,
) -> list[PortfolioRead]:
    """
    Get all portfolios for the current user.
    """
    portfolio_service = await services.aget(PortfolioService)
    return await portfolio_service.get_portfolios_by_user(user.id)


@portfolio_router.post("/")
async def portfolio_create(
    portfolio_create_request: PortfolioCreate,
    user: Annotated[User, Depends(current_user)],
    services: DepContainer,
) -> PortfolioRead:
    """
    Create a new portfolio for the current user.
    """
    portfolio_service = await services.aget(PortfolioService)
    return await portfolio_service.create_portfolio(user.id, portfolio_create_request)


@portfolio_router.put("/{portfolio_id}/accounts")
async def portfolio_accounts_sync(
    portfolio_id: PortfolioId,
    portfolio_account_update_request: PortfolioAccountUpdateRequest,
    user: Annotated[User, Depends(current_user)],
    services: DepContainer,
) -> PortfolioRead:
    """
    Sync the list of accounts associated with a portfolio.
    """
    authorization_api = await services.aget(AuthorizationApi)
    portfolio_service = await services.aget(PortfolioService)
    account_service = await services.aget(AccountService)

    portfolio = await portfolio_service.get_portfolio(portfolio_id)
    authorization_api.check_entity_owned_by_user(user, portfolio)

    await account_service.check_accounts_belong_to_user(
        account_ids=portfolio_account_update_request.accounts,
        user_id=user.id,
    )

    return await portfolio_service.sync_portfolio_accounts(
        user_id=user.id,
        portfolio_id=portfolio_id,
        portfolio_account_update=portfolio_account_update_request,
    )


@portfolio_router.delete("/{portfolio_id}")
async def portfolio_delete(
    portfolio_id: PortfolioId,
    user: Annotated[User, Depends(current_user)],
    services: DepContainer,
) -> Response:
    """
    Delete a portfolio.
    """
    authorization_api = await services.aget(AuthorizationApi)
    portfolio_service = await services.aget(PortfolioService)

    portfolio = await portfolio_service.get_portfolio(portfolio_id)
    authorization_api.check_entity_owned_by_user(user, portfolio)

    await portfolio_service.delete_portfolio(portfolio_id)

    return Response(status_code=204)


@account_router.get("/")
async def accounts(
    user: Annotated[User, Depends(current_user)],
    services: DepContainer,
) -> list[AccountSchema]:
    """
    Get all accounts for the current user.
    """
    account_repository = await services.aget(AccountRepository)
    return await account_repository.get_by_user(user.id)


@account_router.get("/sync-status")
async def account_sync_status(
    user: Annotated[User, Depends(current_user)],
) -> dict[str, list[str]]:
    """Return the IDs of accounts that currently have an active sync job."""
    try:
        active_ids = await get_active_syncs(user.id)
        return {"account_ids": [str(aid) for aid in active_ids]}
    except redis.RedisError as e:
        raise HTTPException(
            status_code=503,
            detail="Sync status service unavailable",
        ) from e


@account_router.get("/me/preferences")
async def get_preferences(
    user: Annotated[User, Depends(current_user)],
    services: DepContainer,
) -> dict:
    """Return the current user's chart preferences."""
    user_api = await services.aget(UserApi)
    prefs = await user_api.get_preferences(user.id)
    return prefs if prefs is not None else {}


@account_router.put("/me/preferences")
async def put_preferences(
    payload: UserPreferences,
    user: Annotated[User, Depends(current_user)],
    services: DepContainer,
) -> dict:
    """Store the current user's chart preferences."""
    user_api = await services.aget(UserApi)
    # exclude_none=True: explicit null fields are dropped; server does not store them
    await user_api.save_preferences(user.id, payload.model_dump(exclude_none=True))
    return await user_api.get_preferences(user.id) or {}


@account_router.patch("/me/preferences")
async def patch_preferences(
    payload: UserPreferences,
    user: Annotated[User, Depends(current_user)],
    services: DepContainer,
) -> dict:
    """Partially update the current user's preferences."""
    user_api = await services.aget(UserApi)
    # exclude_none=True: explicit null fields are dropped;
    # server only updates provided fields
    return await user_api.patch_preferences(
        user.id, payload.model_dump(exclude_none=True)
    )


@account_router.post("/csv/inspect")
async def account_csv_inspect(
    user: Annotated[User, Depends(current_user)],  # noqa: ARG001
    file: Annotated[UploadFile, File(...)],
    services: DepContainer,
    institution_id: Annotated[int | None, Form()] = None,
    institution_id_query: Annotated[int | None, Query(alias="institution_id")] = None,
) -> list[CsvDiscoveredAccount]:
    """
    Inspect an uploaded CSV file and return discovered accounts with preview positions.
    """
    actual_institution_id = (
        institution_id if institution_id is not None else institution_id_query
    )
    if actual_institution_id is None:
        raise HTTPException(status_code=422, detail="institution_id is required")

    institution_repository = await services.aget(InstitutionRepository)
    institution = await institution_repository.get(actual_institution_id)
    if institution is None:
        raise HTTPException(
            status_code=404,
            detail=f"Institution {actual_institution_id} not found",
        )

    if not institution.csv_import_enabled or not institution.csv_format:
        raise HTTPException(
            status_code=400,
            detail=(
                f"CSV import is not enabled or configured for institution "
                f"'{institution.name}'"
            ),
        )

    try:
        content_bytes = await file.read()
        content_str = content_bytes.decode("utf-8-sig")
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to read or decode CSV file: {e}",
        ) from e

    if not content_str or not content_str.strip():
        raise HTTPException(status_code=400, detail="CSV file is empty")

    parser = await services.aget(GenericCsvParser)
    try:
        discovered_accounts = parser.parse(content_str, institution.csv_format)
    except CsvParserError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return discovered_accounts


async def _sync_account_csv_positions(
    account_id: AccountId,
    institution_id: InstitutionEnum,
    csv_positions: list[CsvPositionRecord],
    services: DepContainer,
) -> None:
    """Resolve securities and persist positions for a CSV account."""
    security_api = await services.aget(SecurityApi)
    position_api = await services.aget(PositionApi)
    position_repository = await services.aget(PositionRepository)
    account_repository = await services.aget(AccountRepository)

    positions: list[Position] = []
    for pos in csv_positions:
        try:
            security = await security_api.get_or_create_from_broker(
                institution_id=institution_id,
                broker_symbol=pos.symbol,
                broker_exchange=pos.exchange or "",
                broker_name=pos.name or "",
            )
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to resolve security for symbol '{pos.symbol}': {e}",
            ) from e

        positions.append(
            Position(
                account_id=account_id,
                security_id=security.id,
                quantity=pos.quantity,
                average_cost=pos.average_cost,
                currency=pos.currency,
            )
        )

    if positions:
        await position_api.create(positions)
    else:
        await position_repository.sync_by_account(account_id, [])

    await account_repository.update_last_sync_at(account_id)


def _parse_account_number_item(item: str) -> list[str]:
    cleaned = item.strip()
    if not cleaned:
        return []
    if cleaned.startswith("[") and cleaned.endswith("]"):
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, list):
                return [s.strip() for s in parsed if isinstance(s, str) and s.strip()]
        except json.JSONDecodeError:
            pass
    if "," in cleaned:
        return [s.strip() for s in cleaned.split(",") if s.strip()]
    return [cleaned]


def _normalize_account_numbers(raw: list[str] | None) -> list[str]:
    """Parse and normalize account numbers from form or query strings."""
    if not raw:
        return []
    result: list[str] = []
    for item in raw:
        result.extend(_parse_account_number_item(item))
    return list(dict.fromkeys(result))


def _validate_csv_institution(
    institution: InstitutionSchema | None, institution_id: int
) -> None:
    if institution is None:
        raise HTTPException(
            status_code=404,
            detail=f"Institution {institution_id} not found",
        )
    if not institution.csv_import_enabled or not institution.csv_format:
        inst_name = institution.name if institution else str(institution_id)
        raise HTTPException(
            status_code=400,
            detail=(
                f"CSV import is not enabled or configured for institution '{inst_name}'"
            ),
        )


def _check_duplicate_accounts(
    user_accounts: list[AccountSchema],
    matching_discovered: list[CsvDiscoveredAccount],
    institution_id: int,
) -> None:
    existing_external_ids = {
        acc.external_id for acc in user_accounts if acc.institution_id == institution_id
    }
    duplicates = [
        acc.account_number
        for acc in matching_discovered
        if acc.account_number in existing_external_ids
    ]
    if duplicates:
        detail_msg = (
            f"Account(s) already exist for this institution: {', '.join(duplicates)}"
        )
        raise HTTPException(
            status_code=400,
            detail=detail_msg,
        )


@account_router.post("/csv/import")
async def account_csv_import(  # noqa: PLR0913, PLR0917
    user: Annotated[User, Depends(current_user)],
    file: Annotated[UploadFile, File(...)],
    services: DepContainer,
    institution_id: Annotated[int | None, Form()] = None,
    institution_id_query: Annotated[int | None, Query(alias="institution_id")] = None,
    account_numbers: Annotated[list[str] | None, Form()] = None,
    account_numbers_query: Annotated[
        list[str] | None, Query(alias="account_numbers")
    ] = None,
) -> list[AccountSchema]:
    """Import selected accounts and positions from an uploaded CSV file."""
    actual_institution_id = (
        institution_id if institution_id is not None else institution_id_query
    )
    if actual_institution_id is None:
        raise HTTPException(status_code=422, detail="institution_id is required")

    raw_account_numbers = (
        account_numbers if account_numbers is not None else account_numbers_query
    )
    normalized_account_numbers = _normalize_account_numbers(raw_account_numbers)
    if not normalized_account_numbers:
        raise HTTPException(status_code=422, detail="account_numbers is required")

    institution_repository = await services.aget(InstitutionRepository)
    institution = await institution_repository.get(actual_institution_id)
    _validate_csv_institution(institution, actual_institution_id)
    assert institution is not None
    assert institution.csv_format is not None

    try:
        content_bytes = await file.read()
        content_str = content_bytes.decode("utf-8-sig")
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to read or decode CSV file: {e}",
        ) from e

    if not content_str or not content_str.strip():
        raise HTTPException(status_code=400, detail="CSV file is empty")

    parser = await services.aget(GenericCsvParser)
    try:
        discovered_accounts = parser.parse(content_str, institution.csv_format)
    except CsvParserError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    requested_set = set(normalized_account_numbers)
    matching_discovered = [
        acc for acc in discovered_accounts if acc.account_number in requested_set
    ]
    if not matching_discovered:
        raise HTTPException(
            status_code=400,
            detail="No matching accounts found in CSV for requested account numbers",
        )

    account_repository = await services.aget(AccountRepository)
    user_accounts = await account_repository.get_by_user(user.id)
    _check_duplicate_accounts(user_accounts, matching_discovered, actual_institution_id)

    created_accounts: list[AccountSchema] = []
    for disc_acc in matching_discovered:
        account_schema = AccountSchema(
            id=uuid.uuid4(),
            external_id=disc_acc.account_number,
            name=disc_acc.account_name,
            user_id=user.id,
            integration_user_id=None,
            account_type_id=disc_acc.account_type_id,
            institution_id=InstitutionEnum(actual_institution_id),
            currency=Currency(disc_acc.currency),
            broker_display_name=disc_acc.account_name,
            is_active=True,
            api_sync_enabled=False,
        )
        created = await account_repository.create(account_schema)
        await _sync_account_csv_positions(
            account_id=created.id,
            institution_id=InstitutionEnum(actual_institution_id),
            csv_positions=disc_acc.positions,
            services=services,
        )
        refreshed = await account_repository.get(created.id)
        created_accounts.append(refreshed if refreshed is not None else created)

    return created_accounts


@account_router.post("/{account_id}/csv-sync")
async def account_csv_sync(
    account_id: AccountId,
    user: Annotated[User, Depends(current_user)],
    file: Annotated[UploadFile, File(...)],
    services: DepContainer,
) -> AccountSchema:
    """Update positions of an existing account from an uploaded CSV file."""
    authorization_api = await services.aget(AuthorizationApi)
    account_repository = await services.aget(AccountRepository)

    account = await account_repository.get(account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")

    authorization_api.check_entity_owned_by_user(user, account)

    institution_repository = await services.aget(InstitutionRepository)
    institution = await institution_repository.get(account.institution_id)
    _validate_csv_institution(institution, account.institution_id)
    assert institution is not None
    assert institution.csv_format is not None

    try:
        content_bytes = await file.read()
        content_str = content_bytes.decode("utf-8-sig")
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to read or decode CSV file: {e}",
        ) from e

    if not content_str or not content_str.strip():
        raise HTTPException(status_code=400, detail="CSV file is empty")

    parser = await services.aget(GenericCsvParser)
    try:
        discovered_accounts = parser.parse(content_str, institution.csv_format)
    except CsvParserError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    matching_account = next(
        (
            acc
            for acc in discovered_accounts
            if acc.account_number == account.external_id
        ),
        None,
    )
    if matching_account is None:
        raise HTTPException(
            status_code=400,
            detail=f"No account matching '{account.external_id}' found in CSV",
        )

    await _sync_account_csv_positions(
        account_id=account.id,
        institution_id=InstitutionEnum(account.institution_id),
        csv_positions=matching_account.positions,
        services=services,
    )

    refreshed = await account_repository.get(account.id)
    if refreshed is None:
        raise HTTPException(status_code=404, detail="Account not found")

    return refreshed


@account_router.patch("/{account_id}/rename")
async def account_rename(
    account_id: AccountId,
    account_rename_request: AccountRenameRequest,
    user: Annotated[User, Depends(current_user)],
    services: DepContainer,
) -> AccountSchema:
    """
    Rename an existing account of the current user.
    """
    authorization_api = await services.aget(AuthorizationApi)
    account_repository = await services.aget(AccountRepository)

    account = await account_repository.get(account_id)
    authorization_api.check_entity_owned_by_user(user, account)

    return await account_repository.rename(account_id, account_rename_request.name)


@account_router.delete("/{account_id}")
async def account_delete(
    account_id: AccountId,
    user: Annotated[User, Depends(current_user)],
    services: DepContainer,
) -> Response:
    """
    Delete an account.
    """
    authorization_api = await services.aget(AuthorizationApi)
    account_repository = await services.aget(AccountRepository)
    account_service = await services.aget(AccountService)

    account = await account_repository.get(account_id)
    authorization_api.check_entity_owned_by_user(user, account)

    await account_service.delete_account(account_id)

    return Response(status_code=204)


@account_router.get("/{account_id}/totals")
async def account_totals(
    account_id: AccountId,
    user: Annotated[User, Depends(current_user)],
    services: DepContainer,
) -> AccountTotals:
    """
    Get accounts totals such as cost and price.
    """
    authorization_api = await services.aget(AuthorizationApi)
    account_repository = await services.aget(AccountRepository)
    position_service = await services.aget(PositionService)

    account = await account_repository.get(account_id)
    authorization_api.check_entity_owned_by_user(user, account)

    if account is None:
        raise HTTPException(404)

    return await position_service.get_total_for_account(account_id, account.currency)


@account_router.get("/holdings/{security_id}")
async def security_holdings(
    security_id: UUID,
    user: Annotated[User, Depends(current_user)],
    pagination: Annotated[PaginationParams, Depends()],
    services: DepContainer,
) -> PaginatedResponse[AccountHoldingRead]:
    """Get all holdings for a specific security across user accounts."""
    position_service = await services.aget(PositionService)
    holdings, total = await position_service.get_holdings_by_security(
        security_id, user.id, offset=pagination.offset, limit=pagination.limit
    )
    return PaginatedResponse(
        items=holdings, total=total, offset=pagination.offset, limit=pagination.limit
    )


@account_router.get("/{account_id}/holdings")
async def account_holdings(
    account_id: AccountId,
    user: Annotated[User, Depends(current_user)],
    pagination: Annotated[PaginationParams, Depends()],
    services: DepContainer,
) -> AccountHoldingsRead:
    """Get detailed holdings for a specific account."""
    authorization_api = await services.aget(AuthorizationApi)
    account_repository = await services.aget(AccountRepository)
    position_service = await services.aget(PositionService)

    account = await account_repository.get(account_id)
    authorization_api.check_entity_owned_by_user(user, account)

    return await position_service.get_account_holdings(
        account_id, offset=pagination.offset, limit=pagination.limit
    )


@account_router.post("/{account_id}/sync")
@limiter.limit("3/minute")
async def account_sync_positions(
    request: Request,  # noqa: ARG001
    response: Response,  # noqa: ARG001
    account_id: AccountId,
    user: Annotated[User, Depends(current_user)],
    services: DepContainer,
) -> dict:
    """
    Enqueue a background task to sync positions for the given account.
    """
    authorization_api = await services.aget(AuthorizationApi)
    account_repository = await services.aget(AccountRepository)
    position_service = await services.aget(PositionService)

    account = await account_repository.get(account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")

    authorization_api.check_entity_owned_by_user(user, account)

    if not account.api_sync_enabled:
        raise HTTPException(
            status_code=400,
            detail=f"API sync is not enabled for account {account_id}",
        )

    try:
        await position_service.sync_account_positions(user.id, account_id)
    except AccountNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ApiSyncDisabledError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    return {"accepted": True}
