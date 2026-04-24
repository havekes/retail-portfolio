import logging
import uuid
from datetime import UTC, date, datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.exceptions import HTTPException
from svcs.fastapi import DepContainer

from src.auth.api import current_user
from src.auth.api_types import User
from src.config.settings import settings
from src.market.ai_service import AIService
from src.market.api import SecurityApi
from src.market.api_types import SecurityId, SecuritySearchResult
from src.market.cache import IndicatorCache
from src.market.gateway import MarketGateway
from src.market.indicators import (
    calculate_50_day_ma,
    calculate_50_week_ma,
    calculate_200_day_ma,
    calculate_200_week_ma,
    calculate_macd,
    calculate_rsi,
)
from src.market.repository import (
    IndicatorPreferencesRepository,
    PriceAlertRepository,
    PriceRepository,
    SecurityDocumentRepository,
    SecurityNoteRepository,
    SecurityRepository,
    WatchlistRepository,
)
from src.market.schema import (
    AIAnalysisRequest,
    AIAnalysisResponse,
    IndicatorPreferencesRead,
    IndicatorPreferencesWrite,
    MACDPoint,
    MAPoint,
    PriceAlertRead,
    PriceAlertWrite,
    PriceHistoryRead,
    PriceSchema,
    RSIPoint,
    SecurityCreateRequest,
    SecurityCreateResponse,
    SecurityDocumentRead,
    SecurityDocumentWrite,
    SecurityNoteRead,
    SecurityNoteWrite,
    SecuritySchema,
    TechnicalIndicatorsRead,
    WatchlistRead,
)
from src.market.task import generate_note_title_task
from src.worker import huey

logger = logging.getLogger(__name__)

market_router = APIRouter(prefix="/api/market")


@market_router.get("/prices/{security_id}/last-close")
async def market_last_close_price(
    _: Annotated[User, Depends(current_user)],
    security_id: SecurityId,
    services: DepContainer,
) -> PriceSchema:
    """
    Get last close OHLC price for a security
    """
    price_repository = await services.aget(PriceRepository)
    security_repository = await services.aget(SecurityRepository)
    security = await security_repository.get_by_id_or_fail(security_id)
    price = await price_repository.get_latest_price(security)

    logger.info("Retrieved last close price for security %s", security_id)

    return PriceSchema.model_validate(price)


@market_router.get("/search")
async def market_search(
    _: Annotated[User, Depends(current_user)],
    q: Annotated[str, Query(description="Search query", min_length=1, max_length=100)],
    services: DepContainer,
) -> list[SecuritySearchResult]:
    """
    Search for securities by query string
    """
    gateway = services.get(MarketGateway)
    results = gateway.search(q)
    logger.info(
        "Searched for securities with query: %s, found %d results", q, len(results)
    )
    return results


@market_router.get("/prices/{security_id}")
async def market_get_prices(
    _: Annotated[User, Depends(current_user)],
    security_id: SecurityId,
    from_date: Annotated[date, Query(description="Start date (ISO 8601)")],
    to_date: Annotated[date, Query(description="End date (ISO 8601)")],
    services: DepContainer,
) -> PriceHistoryRead:
    """
    Get historical prices for a security within a date range
    """
    if from_date > to_date:
        raise HTTPException(
            status_code=422,
            detail="from_date must be less than or equal to to_date",
        )

    price_repository = await services.aget(PriceRepository)
    security_repository = await services.aget(SecurityRepository)
    security = await security_repository.get_by_id_or_fail(security_id)
    prices = await price_repository.get_prices(security, from_date, to_date)

    logger.info(
        "Retrieved %d prices for security %s from %s to %s",
        len(prices),
        security_id,
        from_date,
        to_date,
    )

    return PriceHistoryRead(
        security_id=security_id,
        from_date=from_date,
        to_date=to_date,
        prices=[PriceSchema.model_validate(price) for price in prices],
    )


@market_router.get("/securities/{security_id}")
async def market_get_security(
    _: Annotated[User, Depends(current_user)],
    security_id: SecurityId,
    services: DepContainer,
) -> SecuritySchema:
    """
    Get security details by ID
    """
    security_repository = await services.aget(SecurityRepository)
    security = await security_repository.get_by_id_or_fail(security_id)
    return SecuritySchema.model_validate(security)


@market_router.get("/watchlists")
async def market_watchlists(
    user: Annotated[User, Depends(current_user)],
    services: DepContainer,
) -> list[WatchlistRead]:
    """
    Get all watchlists for the logged in user
    """
    watchlist_repository = await services.aget(WatchlistRepository)
    return await watchlist_repository.get_by_user(user.id)


@market_router.post("/security")
async def market_create_or_get_security(
    _: Annotated[User, Depends(current_user)],
    request: SecurityCreateRequest,
    services: DepContainer,
) -> SecurityCreateResponse:
    """
    Create a new security or return existing one based on code + exchange.
    Fetches price history if security was newly created.
    """
    security_api = await services.aget(SecurityApi)
    result = await security_api.create_or_get_from_search(request)

    logger.info(
        "Created or retrieved security %s (%s.%s), has_price_data=%s",
        result.security_id,
        result.symbol,
        result.exchange,
        result.has_price_data,
    )

    return result


# Price Alerts endpoints
@market_router.get("/securities/{security_id}/alerts")
async def market_get_alerts(
    user: Annotated[User, Depends(current_user)],
    security_id: SecurityId,
    services: DepContainer,
) -> list[PriceAlertRead]:
    """
    Get all price alerts for a security
    """
    alert_repository = await services.aget(PriceAlertRepository)
    alerts = await alert_repository.get_by_security_and_user(security_id, user.id)
    logger.info("Retrieved %d alerts for security %s", len(alerts), security_id)
    return alerts


@market_router.post("/securities/{security_id}/alerts")
async def market_create_alert(
    user: Annotated[User, Depends(current_user)],
    security_id: SecurityId,
    alert: PriceAlertWrite,
    services: DepContainer,
) -> PriceAlertRead:
    """
    Create a new price alert for a security
    """
    alert_repository = await services.aget(PriceAlertRepository)
    created_alert = await alert_repository.create(alert, security_id, user.id)
    logger.info("Created alert %d for security %s", created_alert.id, security_id)
    return created_alert


@market_router.delete("/securities/{security_id}/alerts/{alert_id}")
async def market_delete_alert(
    user: Annotated[User, Depends(current_user)],
    security_id: SecurityId,
    alert_id: int,
    services: DepContainer,
) -> None:
    """
    Delete a price alert
    """
    alert_repository = await services.aget(PriceAlertRepository)
    await alert_repository.delete(alert_id, user.id)
    logger.info("Deleted alert %d for security %s", alert_id, security_id)


# Security Notes endpoints
@market_router.get("/securities/{security_id}/notes")
async def market_get_notes(
    user: Annotated[User, Depends(current_user)],
    security_id: SecurityId,
    services: DepContainer,
) -> list[SecurityNoteRead]:
    """
    Get all notes for a security
    """
    note_repository = await services.aget(SecurityNoteRepository)
    notes = await note_repository.get_by_security_and_user(security_id, user.id)
    logger.info("Retrieved %d notes for security %s", len(notes), security_id)
    return notes


@market_router.post("/securities/{security_id}/notes")
async def market_create_note(
    user: Annotated[User, Depends(current_user)],
    security_id: SecurityId,
    note: SecurityNoteWrite,
    services: DepContainer,
) -> SecurityNoteRead:
    """
    Create a new note for a security
    """
    note_repository = await services.aget(SecurityNoteRepository)
    created_note = await note_repository.create(note, security_id, user.id)
    logger.info("Created note %d for security %s", created_note.id, security_id)

    # Trigger title generation in background
    generate_note_title_task(created_note.id)

    return created_note


@market_router.put("/securities/{security_id}/notes/{note_id}")
async def market_update_note(
    user: Annotated[User, Depends(current_user)],
    security_id: SecurityId,
    note_id: int,
    note: SecurityNoteWrite,
    services: DepContainer,
) -> SecurityNoteRead:
    """
    Update a note for a security
    """
    note_repository = await services.aget(SecurityNoteRepository)
    updated_note = await note_repository.update(note_id, note, user.id)
    logger.info("Updated note %d for security %s", note_id, security_id)

    # Trigger title update in background
    generate_note_title_task(note_id)

    return updated_note


@market_router.delete("/securities/{security_id}/notes/{note_id}")
async def market_delete_note(
    user: Annotated[User, Depends(current_user)],
    security_id: SecurityId,
    note_id: int,
    services: DepContainer,
) -> None:
    """
    Delete a note for a security
    """
    note_repository = await services.aget(SecurityNoteRepository)
    await note_repository.delete(note_id, user.id)
    logger.info("Deleted note %d for security %s", note_id, security_id)


# Security Documents endpoints
@market_router.get("/securities/{security_id}/documents")
async def market_get_documents(
    user: Annotated[User, Depends(current_user)],
    security_id: SecurityId,
    services: DepContainer,
) -> list[SecurityDocumentRead]:
    """
    Get all documents for a security
    """
    doc_repository = await services.aget(SecurityDocumentRepository)
    documents = await doc_repository.get_by_security_and_user(security_id, user.id)
    logger.info("Retrieved %d documents for security %s", len(documents), security_id)
    return documents


@market_router.post("/securities/{security_id}/documents")
async def market_create_document(
    user: Annotated[User, Depends(current_user)],
    security_id: SecurityId,
    file: Annotated[UploadFile, File(...)],
    services: DepContainer,
) -> SecurityDocumentRead:
    """
    Upload a new document for a security
    """
    upload_dir = Path(settings.upload_path)
    upload_dir.mkdir(parents=True, exist_ok=True)

    file_ext = Path(file.filename).suffix if file.filename else ""
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = upload_dir / unique_filename

    with file_path.open("wb") as buffer:
        content = await file.read()
        buffer.write(content)

    file_size = len(content)

    document = SecurityDocumentWrite(
        filename=file.filename or "unknown",
        file_path=str(file_path),
        file_size=file_size,
        file_type=file.content_type or "application/octet-stream",
    )

    doc_repository = await services.aget(SecurityDocumentRepository)
    created_doc = await doc_repository.create(document, security_id, user.id)
    logger.info("Created document %d for security %s", created_doc.id, security_id)
    return created_doc


@market_router.delete("/securities/{security_id}/documents/{doc_id}")
async def market_delete_document(
    user: Annotated[User, Depends(current_user)],
    security_id: SecurityId,
    doc_id: int,
    services: DepContainer,
) -> None:
    """
    Delete a document for a security
    """
    doc_repository = await services.aget(SecurityDocumentRepository)
    await doc_repository.delete(doc_id, user.id)
    logger.info("Deleted document %d for security %s", doc_id, security_id)


# Indicator Preferences endpoints
@market_router.get("/securities/{security_id}/indicator-preferences")
async def market_get_indicator_preferences(
    user: Annotated[User, Depends(current_user)],
    security_id: SecurityId,
    services: DepContainer,
) -> IndicatorPreferencesRead | None:
    """
    Get indicator preferences for a security
    """
    prefs_repository = await services.aget(IndicatorPreferencesRepository)
    prefs = await prefs_repository.get_for_security_and_user(security_id, user.id)
    logger.info("Retrieved indicator preferences for security %s", security_id)
    return prefs


@market_router.put("/securities/{security_id}/indicator-preferences")
async def market_save_indicator_preferences(
    user: Annotated[User, Depends(current_user)],
    security_id: SecurityId,
    preferences: IndicatorPreferencesWrite,
    services: DepContainer,
) -> IndicatorPreferencesRead:
    """
    Save indicator preferences for a security
    """
    prefs_repository = await services.aget(IndicatorPreferencesRepository)
    saved_prefs = await prefs_repository.save(preferences, security_id, user.id)
    logger.info("Saved indicator preferences for security %s", security_id)
    return saved_prefs


@market_router.get("/securities/{security_id}/indicators")
async def market_get_technical_indicators(  # noqa: C901
    _user: Annotated[User, Depends(current_user)],
    security_id: SecurityId,
    services: DepContainer,
    indicators: Annotated[list[str] | None, Query()] = None,
) -> TechnicalIndicatorsRead:
    """
    Get technical indicators for a security based on requested indicator types.

    Args:
        _user: Current authenticated user
        security_id: ID of the security
        services: Service container for dependency injection
        indicators: List of indicator types to calculate

    Returns:
        TechnicalIndicatorsRead with calculated indicators
    """
    price_repository = await services.aget(PriceRepository)
    indicator_cache = await services.aget(IndicatorCache)

    prices = await price_repository.get_by_security(security_id)

    if not prices:
        return TechnicalIndicatorsRead(security_id=security_id)

    prices_sorted = sorted(prices, key=lambda p: p.date)
    requested = indicators or []

    cached_result = None
    if requested:
        cached_result = await indicator_cache.get(
            str(security_id), requested, len(prices)
        )

    if cached_result:
        logger.info("Returned cached indicators for security %s", security_id)
        return TechnicalIndicatorsRead(**cached_result)

    result = TechnicalIndicatorsRead(security_id=security_id)

    if "ma_50_day" in requested:
        ma_data = calculate_50_day_ma(prices_sorted)
        result.ma_50_day = [
            MAPoint(date=date.fromisoformat(p["date"]), value=p["value"])
            for p in ma_data
        ]

    if "ma_200_day" in requested:
        ma_data = calculate_200_day_ma(prices_sorted)
        result.ma_200_day = [
            MAPoint(date=date.fromisoformat(p["date"]), value=p["value"])
            for p in ma_data
        ]

    if "ma_50_week" in requested:
        ma_data = calculate_50_week_ma(prices_sorted)
        result.ma_50_week = [
            MAPoint(date=date.fromisoformat(p["date"]), value=p["value"])
            for p in ma_data
        ]

    if "ma_200_week" in requested:
        ma_data = calculate_200_week_ma(prices_sorted)
        result.ma_200_week = [
            MAPoint(date=date.fromisoformat(p["date"]), value=p["value"])
            for p in ma_data
        ]

    if "macd" in requested:
        macd_data = calculate_macd(prices_sorted)
        result.macd = [
            MACDPoint(
                date=date.fromisoformat(p["date"]),
                macd=p["macd"],
                signal=p["signal"],
                histogram=p["histogram"],
            )
            for p in macd_data
        ]

    if "rsi" in requested:
        rsi_data = calculate_rsi(prices_sorted)
        result.rsi = [
            RSIPoint(date=date.fromisoformat(p["date"]), rsi=p["rsi"]) for p in rsi_data
        ]

    if requested:
        await indicator_cache.set(
            str(security_id), requested, len(prices), result.model_dump()
        )

    logger.info("Calculated indicators %s for security %s", requested, security_id)
    return result


# AI Analysis endpoints
@market_router.post("/securities/{security_id}/ai/fundamentals")
async def market_ai_fundamentals(
    user: Annotated[User, Depends(current_user)],
    security_id: SecurityId,
    services: DepContainer,
) -> AIAnalysisResponse:
    """
    Get AI-powered fundamentals analysis for a security.
    """
    ai_service = await services.aget(AIService)
    try:
        content = await ai_service.analyze_fundamentals(security_id, user.id)
        return AIAnalysisResponse(
            content=content, generated_at=datetime.now(UTC).isoformat()
        )
    except TimeoutError:
        raise HTTPException(status_code=504, detail="AI analysis timed out") from None
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from None


@market_router.post("/securities/{security_id}/ai/summarize-notes")
async def market_ai_summarize_notes(
    user: Annotated[User, Depends(current_user)],
    security_id: SecurityId,
    services: DepContainer,
) -> AIAnalysisResponse:
    """
    Get AI-powered summary of user's notes for a security.
    """
    ai_service = await services.aget(AIService)
    try:
        content = await ai_service.summarize_notes(security_id, user.id)
        return AIAnalysisResponse(
            content=content, generated_at=datetime.now(UTC).isoformat()
        )
    except TimeoutError:
        raise HTTPException(status_code=504, detail="AI analysis timed out") from None
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from None


@market_router.post("/securities/{security_id}/ai/portfolio-debate")
async def market_ai_portfolio_debate(
    user: Annotated[User, Depends(current_user)],
    security_id: SecurityId,
    request: AIAnalysisRequest,
    services: DepContainer,
) -> AIAnalysisResponse:
    """
    Get AI-powered analysis of how a security fits in the user's portfolio.
    """
    ai_service = await services.aget(AIService)
    try:
        portfolio_context = (
            request.portfolio_context or "No portfolio context provided."
        )
        content = await ai_service.analyze_portfolio_fit(
            security_id, user.id, portfolio_context
        )
        return AIAnalysisResponse(
            content=content, generated_at=datetime.now(UTC).isoformat()
        )
    except TimeoutError:
        raise HTTPException(status_code=504, detail="AI analysis timed out") from None
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from None
