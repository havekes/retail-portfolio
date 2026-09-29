"""Docs-consistency tests for the wide-event field dictionary and HyperDX workflow (F-OBS-T20).

Hermetic: these tests only read source-controlled documentation (``docs/field-dictionary.md``,
``docker/observability/README.md``), the version-controlled query exports under
``docker/observability/hyperdx/`` and the canonical catalog in ``src/observability/events.py``.
They never contact HyperDX, ClickStack or any other service, and they never run Docker -- live
verification is documented in the runbook (``docker/observability/README.md`` section 8).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from src.observability.events import CATALOG_EVENTS

REPO_ROOT = Path(__file__).resolve().parents[2]
DICTIONARY_PATH = REPO_ROOT / "docs" / "field-dictionary.md"
RUNBOOK_PATH = REPO_ROOT / "docker" / "observability" / "README.md"
EVENTS_SOURCE_PATH = REPO_ROOT / "src" / "observability" / "events.py"
SAMPLING_CONFIG_PATH = (
    REPO_ROOT / "docker" / "observability" / "otelcol-sampling.yaml"
)
HYPERDX_DIR = REPO_ROOT / "docker" / "observability" / "hyperdx"
SAVED_QUERIES_DIR = HYPERDX_DIR / "saved-queries"
DASHBOARD_PATH = HYPERDX_DIR / "dashboard.json"

#: One version-controlled saved query per analysis scenario, pinned by name.
SCENARIO_FILES = (
    "01-deploy-verification.json",
    "02-anomaly-cohorts.json",
    "03-cross-process-failure-tracing.json",
    "04-frontend-error-correlation.json",
)
#: Scenario files whose primary search runs over a catalog wide event.
WIDE_EVENT_SCENARIO_FILES = SCENARIO_FILES[:3]

#: Keys every saved-query file must carry.
REQUIRED_QUERY_KEYS = (
    "scenario",
    "name",
    "purpose",
    "hyperdx",
    "operator_notes",
    "clickhouse_sql",
    "expected_result",
    "sampling_and_retention",
)
#: Keys every saved-query file's ``hyperdx`` block must carry.
REQUIRED_HYPERDX_KEYS = ("where", "whereLanguage", "select", "orderBy", "tags")

#: Attribute literals of the shared exception-record shape (README section 8.4).
EXCEPTION_INBOX_ATTRIBUTES = frozenset(
    {
        "service.name",
        "exception.type",
        "exception.message",
        "exception.stacktrace",
        "error_name",
        "preview",
        "correlation_id",
        "route",
        "deploy_id",
        "release",
        "task_name",
    }
)

_ATTRIBUTE_CONSTANT_PATTERN = re.compile(
    r'^(ATTRIBUTE_[A-Z0-9_]+) = "([^"]+)"$', re.MULTILINE
)
_CATALOG_ROW_PATTERN = re.compile(
    r"^\| \[`(?P<event>[a-z0-9.]+)`\]\(#(?P<anchor>[a-z0-9-]+)\)", re.MULTILINE
)
_CATALOG_HEADING_PATTERN = re.compile(r"^## `([a-z0-9.]+)`$", re.MULTILINE)
_LUCENE_FIELD_PATTERN = re.compile(r"([A-Za-z_][A-Za-z0-9_.]*)\s*:")
_SPAN_ATTRIBUTE_PATTERN = re.compile(r"SpanAttributes\['([^']+)'\]")
_BACKTICKED_TOKEN_PATTERN = re.compile(r"`([A-Za-z_][A-Za-z0-9_.]*)`")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _runbook_section(number: str) -> str:
    """Return one numbered runbook section, heading excluded."""
    pattern = rf"^## {number}\.[^\n]*\n(?P<body>.*?)(?=^## |\Z)"
    match = re.search(pattern, _read(RUNBOOK_PATH), re.MULTILINE | re.DOTALL)
    assert match, f"docker/observability/README.md must have a section {number}"
    return match.group("body")


def _sampling_section() -> str:
    """Return the dictionary's ``Sampling decision fields`` subsection."""
    text = _read(DICTIONARY_PATH)
    heading = "### Sampling decision fields"
    assert heading in text, "the dictionary must document the sampling decision fields"
    start = text.index(heading)
    end = text.find("\n## ", start)
    return text[start : end if end != -1 else len(text)]


def _documented_attributes() -> set[str]:
    """Every ``attribute``-shaped token the dictionary or runbook pins."""
    return set(
        _BACKTICKED_TOKEN_PATTERN.findall(_read(DICTIONARY_PATH) + _runbook_section("8"))
    )


def _load_saved_query(name: str) -> dict[str, Any]:
    return json.loads(_read(SAVED_QUERIES_DIR / name))


def _sql_fragments(payload: dict[str, Any]) -> list[str]:
    """Every SQL string a document carries (saved query or dashboard)."""
    fragments = [payload.get("clickhouse_sql", "")]
    fragments.extend(
        tile.get("config", {}).get("sqlTemplate", "")
        for tile in payload.get("tiles", [])
    )
    return [fragment for fragment in fragments if fragment]


def _query_attributes(payload: dict[str, Any]) -> set[str]:
    """Attribute literals referenced by a document's searches, both languages."""
    attributes = set(
        _LUCENE_FIELD_PATTERN.findall(payload.get("hyperdx", {}).get("where", ""))
    )
    for fragment in _sql_fragments(payload):
        attributes.update(_SPAN_ATTRIBUTE_PATTERN.findall(fragment))
    return attributes


def test_dictionary_catalog_matches_the_emitted_catalog() -> None:
    text = _read(DICTIONARY_PATH)

    table_events = {match[0] for match in _CATALOG_ROW_PATTERN.findall(text)}
    assert table_events == set(CATALOG_EVENTS), (
        "docs/field-dictionary.md must list exactly the CATALOG_EVENTS "
        "in src/observability/events.py"
    )

    section_headings = set(_CATALOG_HEADING_PATTERN.findall(text))
    assert section_headings == set(CATALOG_EVENTS), (
        "every catalog event needs its own `## `<event>`` field table"
    )


def test_envelope_table_lists_every_attribute_constant() -> None:
    source = _read(EVENTS_SOURCE_PATH)
    constants = dict(_ATTRIBUTE_CONSTANT_PATTERN.findall(source))
    assert constants, "no ATTRIBUTE_* constants found in src/observability/events.py"

    text = _read(DICTIONARY_PATH)
    envelope = text[text.index("## Envelope") : text.index("### Sampling decision fields")]
    for constant, attribute in constants.items():
        assert f"`{attribute}`" in envelope, (
            f"{constant} ({attribute}) is missing from the envelope table"
        )


def test_dictionary_documents_the_sampling_decision_fields() -> None:
    sampling_config = _read(SAMPLING_CONFIG_PATH)
    assert 'span.attributes["event.sampled"]' in sampling_config
    assert 'span.attributes["event.sample_rate"]' in sampling_config

    section = _sampling_section()
    assert "event.sampled" in section
    assert "event.sample_rate" in section
    # The dictionary must say the gateway stamps these, not emit_event.
    assert "transform/sampling_stamp" in section
    assert "emit_event" in section
    assert "otel-sampler" in section
    assert "OTEL_SAMPLER_SUCCESS_PERCENT" in section
    # The trace-bound caveat is what makes the huey.task story correct.
    assert "huey.task" in section
    assert "trace-bound" in section


def test_runbook_documents_the_analysis_workflow() -> None:
    section = _runbook_section("8")

    # The four scenarios, by event/record name.
    for event in (
        "portfolio.sync.completed",
        "market.data.fetched",
        "huey.task",
        "exception.type",
    ):
        assert event in section, f"section 8 must cover {event}"

    # The definition-of-done query and the minimal dashboard.
    assert "quantile(0.95)" in section or "p95" in section
    assert "positions_seen" in section
    assert "broker" in section
    assert "dashboard.json" in section
    assert "queue_depth" in section
    assert "/worker/api" in section

    # Triage, event authoring and the redaction boundary pointers.
    assert "Error-inbox triage" in section
    assert "How to add a new event" in section
    assert "CATALOG_EVENTS" in section
    assert "clickhouse-ttl.sql" in section
    assert "PROTECTED_KEYS" in section
    assert "src/observability/redaction.py" in section

    for name in SCENARIO_FILES:
        assert name in section, f"section 8 must point at hyperdx/saved-queries/{name}"


def test_saved_queries_are_exactly_the_four_scenarios() -> None:
    files = sorted(path.name for path in SAVED_QUERIES_DIR.glob("*.json"))
    assert files == list(SCENARIO_FILES)


def test_saved_queries_are_self_describing_and_use_documented_attributes() -> None:
    documented = _documented_attributes()
    scenarios: set[str] = set()

    for name in SCENARIO_FILES:
        payload = _load_saved_query(name)

        for key in REQUIRED_QUERY_KEYS:
            assert payload.get(key), f"{name}: missing {key}"
        for key in REQUIRED_HYPERDX_KEYS:
            assert payload["hyperdx"].get(key), f"{name}: missing hyperdx.{key}"
        assert payload["hyperdx"]["whereLanguage"] == "lucene", name
        assert payload["scenario"] == name.removesuffix(".json").split("-", 1)[1], name
        assert "default.otel_traces" in payload["clickhouse_sql"], name
        assert payload["scenario"] not in scenarios, f"duplicate scenario in {name}"
        scenarios.add(payload["scenario"])

        attributes = _query_attributes(payload)
        assert attributes, f"{name}: the search must reference an attribute"
        assert attributes <= documented, (
            f"{name}: undocumented attributes {sorted(attributes - documented)}"
        )
        if name in WIDE_EVENT_SCENARIO_FILES:
            assert "event.name" in payload["hyperdx"]["where"], name


def test_dashboard_is_minimal_and_uses_documented_attributes() -> None:
    dashboard = json.loads(_read(DASHBOARD_PATH))
    documented = _documented_attributes()

    assert dashboard["name"]
    assert dashboard["version"]
    tiles = dashboard["tiles"]
    assert len(tiles) == 3, "the dashboard is deliberately minimal: three panels"

    for tile in tiles:
        config = tile["config"]
        assert config["configType"] == "sql", tile["id"]
        assert config["connection"], tile["id"]
        assert config["sqlTemplate"].strip(), tile["id"]

    sql = " ".join(_sql_fragments(dashboard))
    # The definition-of-done query, the error rate, and the queue-depth signpost.
    assert "quantile(0.95)" in sql
    assert "positions_seen" in sql
    assert "broker" in sql
    assert "portfolio.sync.failed" in sql
    assert "queue_depth" in sql and "/worker/api" in sql

    attributes = _query_attributes(dashboard)
    assert attributes <= documented, (
        f"dashboard.json: undocumented attributes {sorted(attributes - documented)}"
    )
    assert "event.name" in sql


def test_hyperdx_exports_reference_documented_attributes() -> None:
    """Loose shape check: every export names at least one documented attribute."""
    documented = _documented_attributes() | EXCEPTION_INBOX_ATTRIBUTES
    json_files = sorted(
        path for path in HYPERDX_DIR.rglob("*.json") if path.is_file()
    )
    assert len(json_files) >= 5, "expected the four saved queries plus the dashboard"

    for path in json_files:
        payload = json.loads(_read(path))
        attributes = _query_attributes(payload)
        assert attributes & documented, (
            f"{path.relative_to(REPO_ROOT)}: no documented attribute referenced"
        )