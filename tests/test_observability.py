from __future__ import annotations

import pytest
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from src.config.settings import Settings
from src.observability import (
    bootstrap_observability,
    create_resource,
    get_tracer,
    is_telemetry_enabled,
    parse_otlp_headers,
    reset_observability,
    shutdown_observability,
)


@pytest.fixture(autouse=True)
def _cleanup_observability():
    yield
    reset_observability()


def test_parse_otlp_headers_empty():
    assert parse_otlp_headers(None) == {}
    assert parse_otlp_headers("") == {}
    assert parse_otlp_headers("   ") == {}


def test_parse_otlp_headers_single_pair():
    assert parse_otlp_headers("authorization=secret") == {
        "authorization": "secret"
    }


def test_parse_otlp_headers_multiple_pairs_and_whitespace():
    raw = " authorization = secret , x-api-key=abc-123 , malformed, "
    expected = {
        "authorization": "secret",
        "x-api-key": "abc-123",
    }
    assert parse_otlp_headers(raw) == expected


def test_parse_otlp_headers_values_with_equals():
    raw = "key1=val1=extra,key2=simple"
    assert parse_otlp_headers(raw) == {
        "key1": "val1=extra",
        "key2": "simple",
    }


def test_is_telemetry_enabled_kill_switch_test_env(monkeypatch):
    monkeypatch.delenv("OTEL_SDK_DISABLED", raising=False)
    s = Settings(
        environment="test",
        otel_exporter_otlp_endpoint="http://clickstack:4318",
    )
    assert is_telemetry_enabled(s) is False


def test_is_telemetry_enabled_kill_switch_setting(monkeypatch):
    monkeypatch.delenv("OTEL_SDK_DISABLED", raising=False)
    s = Settings(
        environment="dev",
        otel_sdk_disabled=True,
        otel_exporter_otlp_endpoint="http://clickstack:4318",
    )
    assert is_telemetry_enabled(s) is False


def test_is_telemetry_enabled_kill_switch_env_var(monkeypatch):
    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")
    s = Settings(
        environment="dev",
        otel_sdk_disabled=False,
        otel_exporter_otlp_endpoint="http://clickstack:4318",
    )
    assert is_telemetry_enabled(s) is False

    monkeypatch.setenv("OTEL_SDK_DISABLED", "1")
    assert is_telemetry_enabled(s) is False


def test_is_telemetry_enabled_missing_or_empty_endpoint(monkeypatch):
    monkeypatch.delenv("OTEL_SDK_DISABLED", raising=False)
    s1 = Settings(
        environment="dev",
        otel_exporter_otlp_endpoint=None,
    )
    assert is_telemetry_enabled(s1) is False

    s2 = Settings(
        environment="dev",
        otel_exporter_otlp_endpoint="   ",
    )
    assert is_telemetry_enabled(s2) is False


def test_is_telemetry_enabled_when_configured(monkeypatch):
    monkeypatch.delenv("OTEL_SDK_DISABLED", raising=False)
    s = Settings(
        environment="dev",
        otel_sdk_disabled=False,
        otel_exporter_otlp_endpoint="http://clickstack:4318",
    )
    assert is_telemetry_enabled(s) is True


def test_create_resource_stamps_attributes():
    s = Settings(
        environment="dev",
        deploy_id="deploy-abc",
        service_version="1.2.3",
    )
    resource = create_resource(service_name="backend", settings=s)
    attrs = resource.attributes
    assert attrs["service.name"] == "backend"
    assert attrs["service.version"] == "1.2.3"
    assert attrs["deployment.environment"] == "dev"
    assert attrs["deploy_id"] == "deploy-abc"


def test_create_resource_distinct_service_names():
    backend_res = create_resource(service_name="backend")
    worker_res = create_resource(service_name="worker")
    assert backend_res.attributes["service.name"] == "backend"
    assert worker_res.attributes["service.name"] == "worker"
    assert (
        backend_res.attributes["service.name"]
        != worker_res.attributes["service.name"]
    )


def test_bootstrap_kill_switch_no_processors_in_test_env():
    s = Settings(
        environment="test",
        otel_exporter_otlp_endpoint="http://clickstack:4318",
    )
    provider = bootstrap_observability(service_name="backend", settings=s)
    # When disabled, no span processors should be attached to the provider
    assert len(provider._active_span_processor._span_processors) == 0  # noqa: SLF001

    tracer = get_tracer("test.tracer")
    with tracer.start_as_current_span("test.noop.span") as span:
        span.set_attribute("status", "ok")


def test_in_memory_span_export_with_resource_attributes():
    exporter = InMemorySpanExporter()
    processor = SimpleSpanProcessor(exporter)
    s = Settings(
        environment="test",
        deploy_id="git-commit-hash-123",
        service_version="2.0.0",
    )
    bootstrap_observability(
        service_name="backend",
        settings=s,
        span_processor=processor,
    )

    tracer = get_tracer("test.explicit")
    with tracer.start_as_current_span("sample.operation") as span:
        span.set_attribute("test.key", "test.value")

    finished = exporter.get_finished_spans()
    assert len(finished) == 1
    recorded = finished[0]
    assert recorded.name == "sample.operation"
    assert recorded.attributes is not None
    assert recorded.attributes["test.key"] == "test.value"
    assert recorded.resource is not None
    assert recorded.resource.attributes["service.name"] == "backend"
    assert recorded.resource.attributes["service.version"] == "2.0.0"
    assert (
        recorded.resource.attributes["deployment.environment"] == "test"
    )
    assert recorded.resource.attributes["deploy_id"] == "git-commit-hash-123"


def test_shutdown_observability_graceful():
    s = Settings(environment="test")
    bootstrap_observability(service_name="backend", settings=s)
    shutdown_observability()
    # Repeating shutdown is idempotent and should not raise
    shutdown_observability()
