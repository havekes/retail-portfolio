"""Tests verifying parity between FastAPI data-plane routes and committed OpenAPI contract."""

from __future__ import annotations

import difflib
import json
import os
from typing import Any

from src.main import app
from src.commands.export_data_plane_contract import (
    CONTRACT_PATH,
    dump_data_plane_openapi,
    get_data_plane_openapi,
)

EXPECTED_ROUTES = {
    "/api/v1/market/data/prices/{symbol}",
    "/api/v1/market/data/quote/{symbol}",
    "/api/v1/market/data/indicators/{symbol}",
    "/api/v1/market/data/symbols/search",
    "/api/v1/market/data/options/{symbol}",
    "/api/v1/market/data/options/{symbol}/expirations",
    "/api/v1/market/data/fundamentals/{symbol}",
    "/api/v1/market/data/fundamentals/{symbol}/statements",
}


def test_data_plane_openapi_artifact_matches_live_fastapi() -> None:
    """Live FastAPI data-plane schema must match the committed artifact byte-for-byte."""
    if os.environ.get("UPDATE_CONTRACTS") == "1":
        dump_data_plane_openapi(app, CONTRACT_PATH)

    assert CONTRACT_PATH.exists(), f"Committed contract not found at {CONTRACT_PATH}"
    committed_text = CONTRACT_PATH.read_text(encoding="utf-8")

    live_schema = get_data_plane_openapi(app)
    live_text = json.dumps(live_schema, indent=2, sort_keys=True) + "\n"

    if committed_text != live_text:
        diff = "".join(
            difflib.unified_diff(
                committed_text.splitlines(keepends=True),
                live_text.splitlines(keepends=True),
                fromfile="committed:tests/market/contracts/data_plane_openapi.json",
                tofile="live:FastAPI",
            )
        )
        raise AssertionError(
            "Live FastAPI data-plane contract has drifted from committed artifact.\n"
            "Run with UPDATE_CONTRACTS=1 (or uv run python -m src.commands.export_data_plane_contract) to regenerate if intentional.\n"
            f"Diff:\n{diff}"
        )


def test_data_plane_contract_covers_all_routes() -> None:
    """Contract covers exactly the expected data-plane routes and no extra endpoints leaked in."""
    schema = get_data_plane_openapi(app)
    paths = schema.get("paths", {})

    assert set(paths.keys()) == EXPECTED_ROUTES
    for route, operations in paths.items():
        assert "get" in operations, f"Expected GET operation for route {route}"


def test_data_plane_contract_parameters() -> None:
    """Assert expected path and query parameters exist for each route."""
    schema = get_data_plane_openapi(app)
    paths: dict[str, Any] = schema.get("paths", {})

    def get_params(path: str) -> dict[str, dict[str, Any]]:
        params = paths[path]["get"].get("parameters", [])
        return {p["name"]: p for p in params}

    # /prices/{symbol}
    prices_params = get_params("/api/v1/market/data/prices/{symbol}")
    assert prices_params["symbol"]["in"] == "path"
    assert prices_params["symbol"]["required"] is True
    assert prices_params["from"]["in"] == "query"
    assert prices_params["from"]["required"] is False
    assert prices_params["to"]["in"] == "query"
    assert prices_params["to"]["required"] is False
    assert prices_params["interval"]["in"] == "query"
    assert prices_params["interval"]["required"] is False
    assert prices_params["exchange"]["in"] == "query"
    assert prices_params["exchange"]["required"] is False

    # /quote/{symbol}
    quote_params = get_params("/api/v1/market/data/quote/{symbol}")
    assert quote_params["symbol"]["in"] == "path"
    assert quote_params["symbol"]["required"] is True
    assert quote_params["exchange"]["in"] == "query"
    assert quote_params["exchange"]["required"] is False

    # /indicators/{symbol}
    ind_params = get_params("/api/v1/market/data/indicators/{symbol}")
    assert ind_params["symbol"]["in"] == "path"
    assert ind_params["symbol"]["required"] is True
    assert ind_params["indicator"]["in"] == "query"
    assert ind_params["indicator"]["required"] is True
    assert ind_params["period"]["in"] == "query"
    assert ind_params["period"]["required"] is False
    assert ind_params["fast"]["in"] == "query"
    assert ind_params["fast"]["required"] is False
    assert ind_params["slow"]["in"] == "query"
    assert ind_params["slow"]["required"] is False
    assert ind_params["signal"]["in"] == "query"
    assert ind_params["signal"]["required"] is False
    assert ind_params["std_dev"]["in"] == "query"
    assert ind_params["std_dev"]["required"] is False
    assert ind_params["from"]["in"] == "query"
    assert ind_params["from"]["required"] is False
    assert ind_params["to"]["in"] == "query"
    assert ind_params["to"]["required"] is False
    assert ind_params["exchange"]["in"] == "query"
    assert ind_params["exchange"]["required"] is False

    # /symbols/search
    search_params = get_params("/api/v1/market/data/symbols/search")
    assert search_params["q"]["in"] == "query"
    assert search_params["q"]["required"] is True

    # /options/{symbol}
    options_params = get_params("/api/v1/market/data/options/{symbol}")
    assert options_params["symbol"]["in"] == "path"
    assert options_params["expiry"]["in"] == "query"
    assert options_params["expiry"]["required"] is True
    assert options_params["option_type"]["in"] == "query"
    assert options_params["strike_min"]["in"] == "query"
    assert options_params["strike_max"]["in"] == "query"

    # /options/{symbol}/expirations
    expirations_params = get_params("/api/v1/market/data/options/{symbol}/expirations")
    assert expirations_params["symbol"]["in"] == "path"
    assert expirations_params["symbol"]["required"] is True

    # /fundamentals/{symbol}
    fund_params = get_params("/api/v1/market/data/fundamentals/{symbol}")
    assert fund_params["symbol"]["in"] == "path"
    assert fund_params["exchange"]["in"] == "query"
    assert fund_params["exchange"]["required"] is False

    # /fundamentals/{symbol}/statements
    stmt_params = get_params("/api/v1/market/data/fundamentals/{symbol}/statements")
    assert stmt_params["symbol"]["in"] == "path"
    assert stmt_params["statement"]["in"] == "query"
    assert stmt_params["statement"]["required"] is True
    assert stmt_params["period"]["in"] == "query"
    assert stmt_params["period"]["required"] is False
    assert stmt_params["limit"]["in"] == "query"
    assert stmt_params["limit"]["required"] is False
    assert stmt_params["exchange"]["in"] == "query"
    assert stmt_params["exchange"]["required"] is False


def test_data_plane_contract_has_no_provider_names() -> None:
    """The public data-plane contract must not contain vendor or provider names."""
    schema = get_data_plane_openapi(app)
    serialized = json.dumps(schema).lower()
    for provider in ("fmp", "financialmodelingprep", "polygon", "eodhd"):
        assert provider not in serialized, (
            f"Provider name {provider!r} found in live data-plane OpenAPI schema"
        )

    if CONTRACT_PATH.exists():
        committed = CONTRACT_PATH.read_text(encoding="utf-8").lower()
        for provider in ("fmp", "financialmodelingprep", "polygon", "eodhd"):
            assert provider not in committed, (
                f"Provider name {provider!r} found in committed data-plane OpenAPI snapshot"
            )


def test_data_plane_contract_requires_currency_on_price_responses() -> None:
    """Every price-bearing response schema must mark currency required."""
    schema = get_data_plane_openapi(app)
    schemas = schema.get("components", {}).get("schemas", {})

    prices_schema = schemas.get("PriceHistoryResponse", {})
    assert "currency" in prices_schema.get("required", [])
    assert prices_schema["properties"]["currency"]["type"] == "string"

    indicator_schema = schemas.get("IndicatorSeriesResponse", {})
    assert "currency" in indicator_schema.get("required", [])
    assert indicator_schema["properties"]["currency"]["type"] == "string"

    options_schema = schemas.get("OptionsChain", {})
    assert "currency" in options_schema.get("required", [])
    assert options_schema["properties"]["currency"]["type"] == "string"

    quote_schema = schemas.get("Quote", {})
    assert "currency" in quote_schema.get("required", [])
    assert quote_schema["properties"]["currency"]["type"] == "string"


def test_data_plane_contract_options_chain_has_truncated_field() -> None:
    """OptionsChain schema exposes the truncated boolean flag."""
    schema = get_data_plane_openapi(app)
    components = schema.get("components", {}).get("schemas", {})
    options_chain = components.get("OptionsChain", {})
    props = options_chain.get("properties", {})
    assert "truncated" in props
    assert props["truncated"]["type"] == "boolean"
