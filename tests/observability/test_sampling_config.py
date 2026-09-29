"""Config-parse tests for the F-OBS-T16 tail-sampling and retention policy.

Hermetic: these tests only parse source-controlled configuration
(``docker/observability/otelcol-sampling.yaml``,
``docker/observability/clickhouse-ttl.sql``, the observability Compose overlay and
``.env.example``). They never contact ClickStack, HyperDX, ClickHouse, or any
other service, and they never run Docker -- live pipeline verification is a
documented manual runbook step (see ``docker/observability/README.md``
§ "Tail Sampling Policy").
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
COLLECTOR_CONFIG_PATH = (
    REPO_ROOT / "docker" / "observability" / "otelcol-sampling.yaml"
)
TTL_SQL_PATH = REPO_ROOT / "docker" / "observability" / "clickhouse-ttl.sql"
README_PATH = REPO_ROOT / "docker" / "observability" / "README.md"
BURST_SCRIPT_PATH = (
    REPO_ROOT / "docker" / "observability" / "send-sampling-burst.py"
)
OVERLAY_COMPOSE_PATH = REPO_ROOT / "docker-compose.observability.yml"
ENV_EXAMPLE_PATH = REPO_ROOT / ".env.example"

#: The configured band for the retained success bulk (inclusive).
SAMPLING_BAND_MIN = 5
SAMPLING_BAND_MAX = 10
#: Default applied by the compose overlay when the knob is unset.
DEFAULT_SUCCESS_PERCENT = 7
SUCCESS_PERCENT_ENV = "OTEL_SAMPLER_SUCCESS_PERCENT"

#: Services whose telemetry the overlay must route through the sampler.
SAMPLED_SERVICES = ("backend", "worker", "frontend", "indicator-service")


def _load_yaml(path: Path) -> dict[str, Any]:
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict), f"{path} did not parse to a mapping"
    return loaded


def _collector_config() -> dict[str, Any]:
    return _load_yaml(COLLECTOR_CONFIG_PATH)


def _statements(config: dict[str, Any], processor_name: str) -> list[str]:
    """Flatten one transform processor's OTTL statements, in order."""
    blocks = config["processors"][processor_name]["trace_statements"]
    return [statement for block in blocks for statement in block["statements"]]


def _compose_success_percent_default() -> int:
    """Read the overlay's default for OTEL_SAMPLER_SUCCESS_PERCENT."""
    match = re.search(
        rf"{SUCCESS_PERCENT_ENV}:-(\d+)",
        OVERLAY_COMPOSE_PATH.read_text(encoding="utf-8"),
    )
    assert match, f"the overlay must default {SUCCESS_PERCENT_ENV}"
    return int(match.group(1))


def _resolved_success_percent(config: dict[str, Any]) -> float:
    """Resolve the probabilistic policy percentage, following the env knob."""
    policies = config["processors"]["tail_sampling"]["policies"]
    probabilistic = [p for p in policies if p["type"] == "probabilistic"]
    assert len(probabilistic) == 1, "expected exactly one probabilistic policy"
    raw = probabilistic[0]["probabilistic"]["sampling_percentage"]
    if isinstance(raw, int | float):
        return float(raw)
    match = re.fullmatch(
        rf"\$\{{env:{SUCCESS_PERCENT_ENV}(?::-(\d+))?\}}",
        str(raw),
    )
    assert match, f"unexpected sampling_percentage: {raw!r}"
    return float(match.group(1) or _compose_success_percent_default())


def test_traces_pipeline_is_self_consistent_and_orderly() -> None:
    config = _collector_config()
    pipelines = config["service"]["pipelines"]
    assert set(pipelines) == {"traces"}, "only the traces pipeline belongs here"

    traces = pipelines["traces"]
    assert set(traces["receivers"]) <= set(config["receivers"])
    assert set(traces["processors"]) <= set(config["processors"])
    assert set(traces["exporters"]) <= set(config["exporters"])
    assert "otlp" in traces["receivers"]

    processors = traces["processors"]
    # Error marking must precede the sampling decision; the decision must be
    # stamped before batching.
    assert processors.index("transform/error_marking") < processors.index(
        "tail_sampling"
    )
    assert processors.index("tail_sampling") < processors.index(
        "transform/sampling_stamp"
    )
    assert processors.index("transform/sampling_stamp") < processors.index("batch")


def test_receiver_listens_on_both_otlp_protocols() -> None:
    protocols = _collector_config()["receivers"]["otlp"]["protocols"]
    assert protocols["http"]["endpoint"].endswith(":4318")
    assert protocols["grpc"]["endpoint"].endswith(":4317")


def test_exporter_forwards_to_clickstack_with_the_api_key() -> None:
    exporter = _collector_config()["exporters"]["otlp_http/clickstack"]
    assert exporter["endpoint"] == "http://clickstack:4318"
    assert exporter["headers"]["authorization"] == "${env:HYPERDX_API_KEY}"
    assert exporter["retry_on_failure"]["enabled"] is True


def test_tail_sampling_retains_errors_unconditionally() -> None:
    policies = _collector_config()["processors"]["tail_sampling"]["policies"]

    status_policy = next(p for p in policies if p["name"] == "errors-all")
    assert status_policy["type"] == "status_code"
    assert status_policy["status_code"]["status_codes"] == ["ERROR"]

    slug_policy = next(p for p in policies if p["name"] == "error-slug-present")
    assert slug_policy["type"] == "string_attribute"
    assert slug_policy["string_attribute"]["key"] == "error_slug"
    values = slug_policy["string_attribute"]["values"]
    # `.+` is the presence test: an absent attribute is never evaluated and an
    # empty `error_slug` is never emitted.
    assert values == [".+"]
    assert slug_policy["string_attribute"]["enabled_regex_matching"] is True

    # Tail sampling stops at the first matching policy: the probabilistic bulk
    # must come last so it never shadows an error-retention rule.
    types = [p["type"] for p in policies]
    assert types[-1] == "probabilistic"
    assert "probabilistic" not in types[:-1]


def test_success_bulk_percentage_stays_within_the_configured_band() -> None:
    config = _collector_config()
    percentage = _resolved_success_percent(config)
    assert SAMPLING_BAND_MIN <= percentage <= SAMPLING_BAND_MAX, percentage

    # The overlay default for the same knob must stay inside the band too, so an
    # unset environment still samples within policy.
    default = _compose_success_percent_default()
    assert SAMPLING_BAND_MIN <= default <= SAMPLING_BAND_MAX, default
    assert percentage == default, "config and overlay defaults drifted apart"


def test_error_marking_promotes_failure_signals_before_sampling() -> None:
    statements = _statements(_collector_config(), "transform/error_marking")
    assert statements, "error marking needs at least one OTTL statement"
    assert all(
        "set(span.status.code, STATUS_CODE_ERROR)" in statement
        for statement in statements
    )

    joined = " ".join(statements)
    # Mirrors `_error_reason()` in src/observability/events.py.
    assert 'span.attributes["error_slug"] != nil' in joined
    for failure in ("failed", "failure", "error"):
        assert f'span.attributes["outcome"] == "{failure}"' in joined
    # The F-OBS-T12 http.request contract carries an int status, which
    # `_error_reason()` cannot see: the gateway marks it instead.
    assert 'span.attributes["event.name"] == "http.request"' in joined
    assert 'span.attributes["status"] == 500' in joined


def test_sampling_stamp_exposes_the_applied_decision() -> None:
    statements = _statements(_collector_config(), "transform/sampling_stamp")
    joined = " ".join(statements)

    assert 'set(span.attributes["event.sampled"], true)' in joined
    assert (
        f'set(span.attributes["event.sample_rate"], ${{env:{SUCCESS_PERCENT_ENV}}})'
        in joined
    )
    assert re.search(
        r'set\(span\.attributes\["event\.sample_rate"\],\s*1\.0\)', joined
    ), "error cohorts must be stamped with a 100% sample rate"
    assert re.search(
        r'set\(span\.attributes\["event\.sample_rate"\],\s*1\.0\)\s+where\b',
        joined,
    ), "the 100% rate must be conditional on the error cohort"


def test_clickhouse_ttl_is_configured_per_event_class() -> None:
    sql = TTL_SQL_PATH.read_text(encoding="utf-8")

    traces = re.search(
        r"ALTER TABLE default\.otel_traces MODIFY TTL(.*?);", sql, re.DOTALL
    )
    assert traces, "otel_traces must keep an explicit TTL statement"
    expression = traces.group(1)

    # A per-row branch on the wide-event name, not a single flat tier.
    assert "multiIf" in expression
    assert "SpanAttributes['event.name']" in expression
    assert "'market.cache.accessed', 7" in expression
    for event in ("http.request", "market.data.fetched", "ws.delivery"):
        assert event in expression
    assert re.search(r"\b14\b", expression), "14-day tier must be present"
    assert re.search(r"\b30\b", expression), "30-day fallback tier must be present"
    assert "INTERVAL 30 DAY" not in expression, "flat tier must be replaced"

    # Logs and metrics keep their tiers.
    assert re.search(
        r"ALTER TABLE default\.otel_logs MODIFY TTL .*?INTERVAL 30 DAY", sql
    )
    for table in (
        "otel_metrics_gauge",
        "otel_metrics_histogram",
        "otel_metrics_sum",
        "otel_metrics_summary",
        "otel_metrics_exponential_histogram",
    ):
        assert re.search(
            rf"ALTER TABLE default\.{table} MODIFY TTL .*?INTERVAL 14 DAY", sql
        ), table


def test_overlay_routes_application_telemetry_through_the_sampler() -> None:
    overlay = _load_yaml(OVERLAY_COMPOSE_PATH)
    services = overlay["services"]

    sampler = services["otel-sampler"]
    assert sampler["image"].startswith("otel/opentelemetry-collector-contrib:")
    assert sampler["image"].split(":")[-1] != "latest", "pin the collector image"
    assert "observability" in sampler["profiles"]
    assert "clickstack" in sampler["depends_on"]
    environment = sampler["environment"]
    assert environment[SUCCESS_PERCENT_ENV] == (
        f"${{{SUCCESS_PERCENT_ENV}:-{DEFAULT_SUCCESS_PERCENT}}}"
    )
    assert "HYPERDX_API_KEY" in environment
    assert any(
        "otelcol-sampling.yaml:/etc/otelcol/otelcol-sampling.yaml" in str(mount)
        or (
            isinstance(mount, dict)
            and str(mount.get("source", "")).endswith("otelcol-sampling.yaml")
            and str(mount.get("target", "")).endswith("otelcol-sampling.yaml")
        )
        for mount in sampler["volumes"]
    )

    for name in SAMPLED_SERVICES:
        endpoint = services[name]["environment"]["OTEL_EXPORTER_OTLP_ENDPOINT"]
        assert "otel-sampler" in endpoint, name


def test_env_example_documents_the_sampler_knobs() -> None:
    env_example = ENV_EXAMPLE_PATH.read_text(encoding="utf-8")
    assert SUCCESS_PERCENT_ENV in env_example
    assert "HYPERDX_API_KEY" in env_example


def test_runbook_documents_the_verification_procedure() -> None:
    readme = README_PATH.read_text(encoding="utf-8")
    assert "Tail Sampling Policy" in readme
    assert SUCCESS_PERCENT_ENV in readme
    assert "HYPERDX_API_KEY" in readme
    assert "SHOW CREATE TABLE default.otel_traces" in readme
    assert BURST_SCRIPT_PATH.name in readme

    # The documented burst helper must target the gateway, not ClickStack.
    burst = BURST_SCRIPT_PATH.read_text(encoding="utf-8")
    assert "http://otel-sampler:4318/v1/traces" in burst
