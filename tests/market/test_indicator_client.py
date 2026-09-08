# ruff: noqa: PLR2004, TRY003, EM101
import httpx
import pytest
from fastapi import HTTPException

from src.market.schema import IndicatorCandleSchema, IndicatorSpecSchema
from src.market.service import (
    IndicatorServiceClient,
    indicator_service_client_factory,
)


@pytest.mark.anyio
async def test_compute_success():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/compute"
        assert request.method == "POST"
        return httpx.Response(
            200,
            json={
                "indicators": {
                    "SMA_20": [{"time": "2026-01-01", "value": 150.5}],
                    "BB": [
                        {
                            "time": "2026-01-01",
                            "middle": 150.0,
                            "upper": 160.0,
                            "lower": 140.0,
                        }
                    ],
                }
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = IndicatorServiceClient(
            base_url="http://indicator-test:8080",
            client=http_client,
        )
        candles = [
            IndicatorCandleSchema(
                time="2026-01-01",
                open=100.0,
                high=110.0,
                low=90.0,
                close=105.0,
                volume=1000.0,
            )
        ]
        specs = [
            IndicatorSpecSchema(id="SMA_20", type="SMA", period=20),
            IndicatorSpecSchema(id="BB", type="BB", period=20, std_dev=2.0),
        ]

        result = await client.compute(interval="1d", candles=candles, indicators=specs)

        assert "SMA_20" in result
        assert result["SMA_20"] == [{"time": "2026-01-01", "value": 150.5}]
        assert "BB" in result


@pytest.mark.anyio
async def test_compute_timeout_raises_504():
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Request timed out")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = IndicatorServiceClient(
            base_url="http://indicator-test:8080",
            client=http_client,
        )
        with pytest.raises(HTTPException) as exc_info:
            await client.compute(
                interval="1d",
                candles=[],
                indicators=[IndicatorSpecSchema(type="SMA", period=20)],
            )
        assert exc_info.value.status_code == 504
        assert exc_info.value.detail == "Indicator service timed out"


@pytest.mark.anyio
async def test_compute_connection_error_raises_503():
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = IndicatorServiceClient(
            base_url="http://indicator-test:8080",
            client=http_client,
        )
        with pytest.raises(HTTPException) as exc_info:
            await client.compute(
                interval="1d",
                candles=[],
                indicators=[IndicatorSpecSchema(type="SMA", period=20)],
            )
        assert exc_info.value.status_code == 503
        assert exc_info.value.detail == "Indicator service unavailable"


@pytest.mark.anyio
async def test_compute_server_500_raises_503():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="Internal Server Error")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = IndicatorServiceClient(
            base_url="http://indicator-test:8080",
            client=http_client,
        )
        with pytest.raises(HTTPException) as exc_info:
            await client.compute(
                interval="1d",
                candles=[],
                indicators=[IndicatorSpecSchema(type="SMA", period=20)],
            )
        assert exc_info.value.status_code == 503
        assert exc_info.value.detail == "Indicator service unavailable"


@pytest.mark.anyio
async def test_compute_bad_request_raises_400():
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={"error": "unsupported indicator type: UNKNOWN"},
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = IndicatorServiceClient(
            base_url="http://indicator-test:8080",
            client=http_client,
        )
        with pytest.raises(HTTPException) as exc_info:
            await client.compute(
                interval="1d",
                candles=[],
                indicators=[IndicatorSpecSchema(type="UNKNOWN", period=20)],
            )
        assert exc_info.value.status_code == 400
        assert exc_info.value.detail == "unsupported indicator type: UNKNOWN"


@pytest.mark.anyio
async def test_indicator_service_client_factory():
    client = await indicator_service_client_factory()
    assert isinstance(client, IndicatorServiceClient)
    assert client.base_url.startswith("http")
