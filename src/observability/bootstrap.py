from __future__ import annotations

import os
from typing import TYPE_CHECKING

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider

from src.config.settings import Settings
from src.config.settings import settings as app_settings
from src.observability.redaction import RedactingSpanProcessor

if TYPE_CHECKING:
    from opentelemetry.sdk.trace import SpanProcessor
    from opentelemetry.trace import Tracer


class _ObservabilityState:
    active_provider: TracerProvider | None = None


_state = _ObservabilityState()


def create_resource(service_name: str, settings: Settings | None = None) -> Resource:
    """Create an OpenTelemetry Resource with service and environment attributes."""
    effective_settings = settings or app_settings
    return Resource.create(
        {
            "service.name": service_name,
            "service.version": effective_settings.service_version,
            "deployment.environment": effective_settings.environment,
            "deploy_id": effective_settings.deploy_id,
        }
    )


def parse_otlp_headers(headers_str: str | None) -> dict[str, str]:
    """Parse comma-delimited key=value strings into a dictionary for OTLP exporters."""
    if not headers_str:
        return {}

    headers: dict[str, str] = {}
    for raw_part in headers_str.split(","):
        part = raw_part.strip()
        if not part:
            continue
        if "=" in part:
            k, v = part.split("=", 1)
            k = k.strip()
            v = v.strip()
            if k:
                headers[k] = v
    return headers


def is_telemetry_enabled(settings: Settings | None = None) -> bool:
    """
    Check whether OpenTelemetry telemetry export is active.

    Returns False if running in test environment, if disabled via settings/env,
    or if the OTLP exporter endpoint is unset.
    """
    effective_settings = settings or app_settings

    if effective_settings.environment.lower() == "test":
        return False

    if effective_settings.otel_sdk_disabled:
        return False

    env_disabled = os.getenv("OTEL_SDK_DISABLED", "").strip().lower()
    if env_disabled in ("1", "true", "yes", "on"):
        return False

    return bool(
        effective_settings.otel_exporter_otlp_endpoint
        and effective_settings.otel_exporter_otlp_endpoint.strip()
    )


def shutdown_observability() -> None:
    """Flush and shut down the active TracerProvider."""
    if _state.active_provider is not None:
        try:
            _state.active_provider.shutdown()
        finally:
            _state.active_provider = None
    else:
        current = trace.get_tracer_provider()
        if isinstance(current, TracerProvider):
            current.shutdown()


def reset_observability() -> None:
    """Reset global tracer provider state for hermetic test isolation."""
    shutdown_observability()
    try:
        trace._TRACER_PROVIDER = None  # noqa: SLF001
        if hasattr(trace, "_TRACER_PROVIDER_SET_ONCE"):
            trace._TRACER_PROVIDER_SET_ONCE._done = False  # noqa: SLF001
        if hasattr(trace, "_PROXY_TRACER_PROVIDER") and hasattr(
            trace, "ProxyTracerProvider"
        ):
            trace._PROXY_TRACER_PROVIDER = trace.ProxyTracerProvider()  # noqa: SLF001
    except AttributeError, TypeError:
        pass


def bootstrap_observability(
    service_name: str = "backend",
    settings: Settings | None = None,
    span_processor: SpanProcessor | None = None,
) -> TracerProvider:
    """
    Bootstrap the OpenTelemetry SDK for a process (e.g. backend or worker).

    If a span_processor is explicitly provided (such as in tests), it is added.
    Otherwise, if telemetry is enabled, sets up OTLPSpanExporter with
    BatchSpanProcessor. If disabled or in test mode, no processor is attached
    (non-exporting/no-op).
    """
    effective_settings = settings or app_settings

    reset_observability()

    resource = create_resource(service_name=service_name, settings=effective_settings)
    provider = TracerProvider(resource=resource)

    if span_processor is not None:
        if not isinstance(span_processor, RedactingSpanProcessor):
            provider.add_span_processor(RedactingSpanProcessor())
        provider.add_span_processor(span_processor)
    elif is_telemetry_enabled(effective_settings):
        # Exporter packages are imported lazily to avoid side effects on import.
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (  # noqa: PLC0415
            OTLPSpanExporter,
        )
        from opentelemetry.sdk.trace.export import (  # noqa: PLC0415
            BatchSpanProcessor,
        )

        endpoint = (
            (effective_settings.otel_exporter_otlp_endpoint or "").strip().rstrip("/")
        )
        if not endpoint.endswith("/v1/traces"):
            endpoint = f"{endpoint}/v1/traces"

        headers = parse_otlp_headers(effective_settings.otel_exporter_otlp_headers)
        exporter = OTLPSpanExporter(endpoint=endpoint, headers=headers)
        provider.add_span_processor(RedactingSpanProcessor())
        provider.add_span_processor(BatchSpanProcessor(exporter))

    trace.set_tracer_provider(provider)
    _state.active_provider = provider
    return provider


def get_tracer(name: str) -> Tracer:
    """Return an OpenTelemetry Tracer instance."""
    return trace.get_tracer(name)
