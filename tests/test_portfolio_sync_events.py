"""``portfolio.sync.completed`` / ``portfolio.sync.failed`` wide events.

Uses the account-sync mocking conventions of ``tests/tasks/test_integration.py``
plus an in-memory span exporter, so the assertions cover the emitted fields, the
failure marking and the trace continuity with the originating request.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from opentelemetry import propagate
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import StatusCode, format_trace_id
from stockholm import Currency

from src.account.api.account import AccountApi
from src.account.api.position import PositionApi
from src.account.api_types import Account
from src.auth.api import UserApi
from src.config.settings import Settings
from src.core.email import EmailService
from src.core.enum import AccountTypeEnum, InstitutionEnum
from src.integration.brokers import BrokerApiGateway
from src.integration.brokers.api_types import BrokerAccount, BrokerPosition
from src.integration.brokers.exception import SessionExpiredError
from src.integration.repository import IntegrationUserRepository
from src.integration.schema import IntegrationUserSchema
from src.integration.task import (
    _sync_account_positions_task,
    sync_account_positions_task,
)
from src.market.api import SecurityApi
from src.market.api_types import Security
from src.observability import (
    HUEY_TASK_EVENT,
    bootstrap_observability,
    reset_observability,
    restore_task_context,
)
from src.observability.bootstrap import get_tracer
from src.observability.redaction import is_sensitive_key
from src.worker import huey

SYNC_COMPLETED_EVENT = "portfolio.sync.completed"
SYNC_FAILED_EVENT = "portfolio.sync.failed"

BROKER_ACCOUNT_ID = "broker-account-id"
USER_EMAIL = "user@example.com"

# A fixed, valid W3C traceparent: trace id 4bf92f...4736 / span id 00f067aa0ba902b7
TRACEPARENT = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
PARENT_TRACE_ID = "4bf92f3577b34da6a3ce929d0e0e4736"

_FORBIDDEN_VALUE_SUBSTRINGS = ("@", "token", "secret", "password", "bearer", "ws_sess_")


@pytest.fixture()
def exporter() -> Iterator[InMemorySpanExporter]:
    """Bootstrap a worker tracer that exports to memory, and reset afterwards."""
    span_exporter = InMemorySpanExporter()
    bootstrap_observability(
        service_name="worker",
        settings=Settings(environment="test"),
        span_processor=SimpleSpanProcessor(span_exporter),
    )
    try:
        yield span_exporter
    finally:
        reset_observability()


@pytest.fixture(autouse=True)
def _immediate_mode() -> Iterator[None]:
    """Run Huey tasks synchronously and restore the previous mode afterwards."""
    original_immediate = huey.immediate
    huey.immediate = True
    try:
        yield
    finally:
        huey.immediate = original_immediate


@pytest.fixture
def account() -> Account:
    return Account(
        id=uuid4(),
        external_id="external-account-id",
        name="Test Account",
        user_id=uuid4(),
        integration_user_id=uuid4(),
        account_type_id=AccountTypeEnum.TFSA,
        institution_id=InstitutionEnum.WEALTHSIMPLE.value,
        currency=Currency.CAD,
    )


@pytest.fixture
def integration_user(account: Account) -> IntegrationUserSchema:
    integration_user_id = account.integration_user_id
    assert integration_user_id is not None
    return IntegrationUserSchema(
        id=integration_user_id,
        user_id=account.user_id,
        institution_id=InstitutionEnum.WEALTHSIMPLE,
        external_user_id="external-id",
    )


def _event_spans(span_exporter: InMemorySpanExporter, name: str) -> list[Any]:
    return [span for span in span_exporter.get_finished_spans() if span.name == name]


def _event_span(span_exporter: InMemorySpanExporter, name: str) -> Any:
    spans = _event_spans(span_exporter, name)
    assert len(spans) == 1, f"expected one {name!r} span, got {len(spans)}"
    return spans[0]


def _event_attributes(
    span_exporter: InMemorySpanExporter, name: str
) -> dict[str, Any]:
    return dict(_event_span(span_exporter, name).attributes or {})


def _container(services: dict[Any, Any]) -> AsyncMock:
    container = AsyncMock()

    async def aget(service_type: Any) -> Any:
        return services.get(service_type)

    container.aget.side_effect = aget
    container.__aenter__.return_value = container
    return container


def _security() -> Security:
    return Security(
        id=uuid4(),
        symbol="AAPL",
        exchange="NASDAQ",
        name="Apple Inc.",
        currency=Currency.USD,
        isin=None,
        is_active=True,
        updated_at=datetime.now(UTC),
    )


def _broker_with_one_position() -> AsyncMock:
    broker = AsyncMock()
    broker.get_positions_by_account.return_value = [
        BrokerPosition(
            broker_account_id=BROKER_ACCOUNT_ID,
            name="Apple Inc.",
            symbol="AAPL",
            exchange="NASDAQ",
            quantity=Decimal(10),
            average_cost=Decimal(150),
            currency="USD",
        )
    ]
    broker.get_accounts.return_value = [
        BrokerAccount(
            id=BROKER_ACCOUNT_ID,
            type=AccountTypeEnum.TFSA,
            institution=InstitutionEnum.WEALTHSIMPLE,
            currency=Currency.CAD,
            display_name="Test Account",
            broker_display_name="Test",
            value=Decimal(10000),
            net_deposits=Decimal(5000),
            created_at=datetime.now(UTC),
        )
    ]
    return broker


def _failing_broker() -> AsyncMock:
    broker = AsyncMock()
    broker.get_positions_by_account.side_effect = SessionExpiredError("Session expired")
    return broker


def _services(
    integration_user: IntegrationUserSchema,
    broker_class: Any,
    broker: AsyncMock,
) -> AsyncMock:
    """Build a service container covering the sync success and failure paths."""
    security_api = AsyncMock(spec=SecurityApi)
    security_api.get_or_create_from_broker.return_value = _security()

    integration_user_repository = AsyncMock(spec=IntegrationUserRepository)
    integration_user_repository.get.return_value = integration_user

    position_api = AsyncMock(spec=PositionApi)
    position_api.create.return_value = [MagicMock()]

    user_api = AsyncMock(spec=UserApi)
    user_api.get_email_for_user.return_value = USER_EMAIL

    return _container(
        {
            SecurityApi: security_api,
            IntegrationUserRepository: integration_user_repository,
            PositionApi: position_api,
            AccountApi: AsyncMock(spec=AccountApi),
            UserApi: user_api,
            EmailService: AsyncMock(spec=EmailService),
            broker_class: broker,
        }
    )


@contextmanager
def _patched_sync(container: AsyncMock) -> Iterator[None]:
    with (
        patch("src.integration.task.huey.svcs_registry", MagicMock()),
        patch("src.integration.task.Container", return_value=container),
        patch("src.integration.task.ws_manager", AsyncMock()),
        patch("src.integration.task.mark_sync_started", AsyncMock()),
        patch("src.integration.task.mark_sync_finished", AsyncMock()),
    ):
        yield


# --------------------------------------------------------------------------- #
# Incremental events emitted by the sync stages
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_completed_event_reports_counts_and_provider_calls(
    exporter, account, integration_user
):
    broker_class = cast("type[BrokerApiGateway]", MagicMock())
    container = _services(integration_user, broker_class, _broker_with_one_position())

    with _patched_sync(container):
        await _sync_account_positions_task(
            account.user_id, account, BROKER_ACCOUNT_ID, broker_class
        )

    attributes = _event_attributes(exporter, SYNC_COMPLETED_EVENT)
    assert attributes["account_id"] == str(account.id)
    assert attributes["user_id"] == str(account.user_id)
    assert attributes["broker"] == "wealthsimple"
    assert attributes["trigger"] == "manual"
    assert attributes["positions_seen"] == 1
    assert attributes["positions_changed"] == 1
    assert attributes["outcome"] == "success"
    assert float(attributes["duration_ms"]) >= 0
    assert json.loads(attributes["provider_calls"]) == {
        "positions_fetch": "success",
        "positions_persist": "success",
        "accounts_reconcile": "success",
        "securities_resolved": 1,
    }

    span = _event_span(exporter, SYNC_COMPLETED_EVENT)
    assert span.status.status_code is not StatusCode.ERROR


@pytest.mark.asyncio
async def test_failed_event_reports_error_slug_and_shares_request_trace(
    exporter, account, integration_user
):
    broker_class = cast("type[BrokerApiGateway]", MagicMock())
    container = _services(integration_user, broker_class, _failing_broker())

    tracer = get_tracer("tests.portfolio_sync_events")
    with tracer.start_as_current_span("http.request") as request_span:
        carrier: dict[str, str] = {}
        propagate.inject(carrier)
        request_trace_id = format_trace_id(request_span.get_span_context().trace_id)

        with restore_task_context(
            "sync_account_positions_task", traceparent=carrier["traceparent"]
        ):
            with _patched_sync(container), pytest.raises(SessionExpiredError):
                await _sync_account_positions_task(
                    account.user_id, account, BROKER_ACCOUNT_ID, broker_class
                )

    attributes = _event_attributes(exporter, SYNC_FAILED_EVENT)
    assert attributes["account_id"] == str(account.id)
    assert attributes["user_id"] == str(account.user_id)
    assert attributes["broker"] == "wealthsimple"
    assert attributes["trigger"] == "manual"
    assert attributes["outcome"] == "failure"
    assert attributes["error_slug"] == "session_expired_error"
    assert float(attributes["duration_ms"]) >= 0
    # Only the completion event carries the position counts.
    assert "positions_seen" not in attributes
    assert "positions_changed" not in attributes
    # The failure event carries the fields tail sampling treats as an error.
    assert attributes["outcome"] in {"failed", "failure", "error"}

    span = _event_span(exporter, SYNC_FAILED_EVENT)
    assert span.status.status_code is StatusCode.ERROR
    assert format_trace_id(span.context.trace_id) == request_trace_id


@pytest.mark.asyncio
async def test_sync_events_carry_no_pii(exporter, account, integration_user):
    broker_class = cast("type[BrokerApiGateway]", MagicMock())

    success_container = _services(
        integration_user, broker_class, _broker_with_one_position()
    )
    with _patched_sync(success_container):
        await _sync_account_positions_task(
            account.user_id, account, BROKER_ACCOUNT_ID, broker_class
        )

    failure_container = _services(integration_user, broker_class, _failing_broker())
    with _patched_sync(failure_container), pytest.raises(SessionExpiredError):
        await _sync_account_positions_task(
            account.user_id, account, BROKER_ACCOUNT_ID, broker_class
        )

    for event_name in (SYNC_COMPLETED_EVENT, SYNC_FAILED_EVENT):
        attributes = _event_attributes(exporter, event_name)
        for key, value in attributes.items():
            assert is_sensitive_key(key) is False, f"{event_name} carries {key!r}"
            rendered = str(value).lower()
            for needle in _FORBIDDEN_VALUE_SUBSTRINGS:
                assert needle not in rendered, (
                    f"{needle!r} leaked into {event_name}.{key}"
                )
        # broker is an internal telemetry dimension and must survive redaction.
        assert attributes["broker"] == "wealthsimple"


# --------------------------------------------------------------------------- #
# The huey.task signal path around a real sync task
# --------------------------------------------------------------------------- #


def test_sync_task_emits_huey_task_event(exporter, account, integration_user):
    broker_class = cast("type[BrokerApiGateway]", MagicMock())
    container = _services(integration_user, broker_class, _broker_with_one_position())

    with _patched_sync(container):
        sync_account_positions_task(
            account.user_id,
            account,
            BROKER_ACCOUNT_ID,
            broker_class,
            traceparent=TRACEPARENT,
            trigger="scheduled",
        )

    attributes = _event_attributes(exporter, HUEY_TASK_EVENT)
    assert attributes["task_name"] == "sync_account_positions_task"
    assert attributes["task_id"]
    assert attributes["queue"] == "retail-portfolio"
    assert attributes["status"] == "success"
    assert attributes["retries"] == 0
    assert float(attributes["duration_ms"]) >= 0
    assert "error_slug" not in attributes

    huey_task_span = _event_span(exporter, HUEY_TASK_EVENT)
    assert format_trace_id(huey_task_span.context.trace_id) == PARENT_TRACE_ID

    # The sync event mirrors the trigger it was enqueued with.
    sync_attributes = _event_attributes(exporter, SYNC_COMPLETED_EVENT)
    assert sync_attributes["trigger"] == "scheduled"
    assert sync_attributes["outcome"] == "success"


def test_sync_task_failure_emits_huey_task_error_slug(
    exporter, account, integration_user
):
    broker_class = cast("type[BrokerApiGateway]", MagicMock())
    container = _services(integration_user, broker_class, _failing_broker())

    with _patched_sync(container):
        sync_account_positions_task(
            account.user_id,
            account,
            BROKER_ACCOUNT_ID,
            broker_class,
            traceparent=TRACEPARENT,
        )

    attributes = _event_attributes(exporter, HUEY_TASK_EVENT)
    assert attributes["task_name"] == "sync_account_positions_task"
    assert attributes["status"] == "failed"
    assert attributes["error_slug"] == "session_expired_error"

    span = _event_span(exporter, HUEY_TASK_EVENT)
    assert span.status.status_code is StatusCode.ERROR
    # The failure event re-attaches the enqueue-time context, so the failed
    # execution stays in the originating request's trace.
    assert format_trace_id(span.context.trace_id) == PARENT_TRACE_ID

    sync_attributes = _event_attributes(exporter, SYNC_FAILED_EVENT)
    assert sync_attributes["error_slug"] == "session_expired_error"
    assert sync_attributes["outcome"] == "failure"
