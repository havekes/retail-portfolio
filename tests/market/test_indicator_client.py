# ruff: noqa: PLR2004, TRY003, EM101, SLF001
from unittest.mock import AsyncMock, patch

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
    generator = indicator_service_client_factory()
    client = await anext(generator)
    assert isinstance(client, IndicatorServiceClient)
    assert client.base_url.startswith("http")
    await generator.aclose()


@pytest.mark.anyio
async def test_compute_reuses_single_owned_client():
    client = IndicatorServiceClient(base_url="http://indicator-test:8080")
    response = httpx.Response(
        200,
        json={"indicators": {"SMA": [{"time": "2026-01-01", "value": 1.0}]}},
        request=httpx.Request("POST", "http://indicator-test:8080/compute"),
    )
    mock_post = AsyncMock(return_value=response)

    with patch.object(httpx.AsyncClient, "post", mock_post):
        await client.compute(
            interval="1d",
            candles=[],
            indicators=[IndicatorSpecSchema(type="SMA", period=20)],
        )
        first_client = client._client
        await client.compute(
            interval="1d",
            candles=[],
            indicators=[IndicatorSpecSchema(type="SMA", period=20)],
        )

        assert mock_post.await_count == 2
        # The same underlying HTTP client is reused across calls (pooling).
        assert client._client is first_client

    await client.aclose()


@pytest.mark.anyio
async def test_aclose_closes_owned_client():
    client = IndicatorServiceClient(base_url="http://indicator-test:8080")
    response = httpx.Response(
        200,
        json={"indicators": {}},
        request=httpx.Request("POST", "http://indicator-test:8080/compute"),
    )

    with patch.object(httpx.AsyncClient, "post", AsyncMock(return_value=response)):
        await client.compute(
            interval="1d",
            candles=[],
            indicators=[IndicatorSpecSchema(type="SMA", period=20)],
        )

    http_client = client._client
    assert http_client is not None

    await client.aclose()

    assert http_client.is_closed
    assert client._client is None


@pytest.mark.anyio
async def test_aclose_does_not_close_injected_client():
    transport = httpx.MockTransport(lambda _request: httpx.Response(200, json={}))
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = IndicatorServiceClient(
            base_url="http://indicator-test:8080", client=http_client
        )
        await client.aclose()
        assert not http_client.is_closed
