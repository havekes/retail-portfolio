"""OpenAPI contract extraction and export for market data plane."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI, routing
from fastapi.openapi.utils import get_openapi
from rich import print as rprint

DATA_PLANE_PREFIX = "/api/v1/market/data"
CONTRACT_PATH = (
    Path(__file__).resolve().parents[2]
    / "tests"
    / "market"
    / "contracts"
    / "data_plane_openapi.json"
)


def get_data_plane_openapi(app: FastAPI) -> dict[str, Any]:
    """Extract and slice FastAPI OpenAPI contract for data-plane routes."""
    routes = [
        rc
        for rc in routing.iter_route_contexts(app.routes)
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
    app: FastAPI,
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
    import os

    os.environ["ENVIRONMENT"] = "test"
    from src.main import app

    out = dump_data_plane_openapi(app)
    rprint(f"Wrote data-plane OpenAPI contract to {out}")
