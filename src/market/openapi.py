"""OpenAPI contract extraction and export for market data plane."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, routing
from fastapi.openapi.utils import get_openapi
from rich import print as rprint

from src.main import app as main_app

DATA_PLANE_PREFIX = "/api/v1/market/data"
CONTRACT_PATH = (
    Path(__file__).resolve().parents[2]
    / "tests"
    / "market"
    / "contracts"
    / "data_plane_openapi.json"
)


def get_data_plane_openapi(app: FastAPI | None = None) -> dict[str, Any]:
    """Extract and slice FastAPI OpenAPI contract for data-plane routes."""
    target_app = app if app is not None else main_app

    routes = [
        rc
        for rc in routing.iter_route_contexts(target_app.routes)
        if getattr(rc, "path_format", getattr(rc, "path", "")).startswith(
            DATA_PLANE_PREFIX
        )
    ]
    return get_openapi(
        title="Market Data Plane Contract",
        version="1.0.0",
        routes=routes,
    )


def dump_data_plane_openapi(
    app: FastAPI | None = None,
    output_path: Path | str = CONTRACT_PATH,
) -> Path:
    """Generate and write the data-plane OpenAPI contract to disk."""
    schema = get_data_plane_openapi(app)
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(schema, indent=2, sort_keys=True) + "\n"
    path.write_text(serialized, encoding="utf-8")
    return path


if __name__ == "__main__":
    out = dump_data_plane_openapi()
    rprint(f"Wrote data-plane OpenAPI contract to {out}")
