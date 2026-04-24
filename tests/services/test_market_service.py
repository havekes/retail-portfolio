from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import override
from uuid import uuid4

import pytest

from src.market.api_types import HistoricalPrice, SecurityId
from src.market.gateway import MarketGateway
from src.market.schema import PriceSchema, SecuritySchema
from src.market.service import MarketService
from src.market.repository import PriceRepository, SecurityRepository


class MockSecurityRepository(SecurityRepository):
    def __init__(self, securities: list[SecuritySchema]):
        self.securities = securities

    @override
    async def get_by_id_or_fail(self, security_id: SecurityId) -> SecuritySchema:
        for security in self.securities:
            if security.id == security_id:
                return security
        raise ValueError("Not found")

    @override
    async def get_or_create(self, security: SecuritySchema) -> SecuritySchema:
        return security

    @override
    async def get_all_active_securities(self) -> list[SecuritySchema]:
        return [s for s in self.securities if s.is_active]

    @override
    async def get_by_code_and_exchange(
        self, code: str, exchange: str
    ) -> SecuritySchema | None:
        for security in self.securities:
            if security.symbol == code and security.exchange == exchange:
                return security
        return None


class MockPriceRepository(PriceRepository):
    def __init__(self):
        self.saved_prices = []

    @override
    async def get_by_security(self, security_id):
        return []

    @override
    async def get_prices(self, security, from_date, to_date):
        return []

    @override
    async def get_latest_price(self, security):
        return None

    @override
    async def get_price_on_date(self, security, date):
        return None

    @override
    async def save_price(self, price: PriceSchema):
        self.saved_prices.append(price)
        return price

    @override
    async def save_prices(self, prices: list[PriceSchema]):
        self.saved_prices.extend(prices)
        return prices


class MockEodhdGateway(MarketGateway):
    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail

    @override
    def search(self, query):
        return []

    @override
    def get_price_on_date(self, security_id, symbol, exchange, date):
        return None

    @override
    def get_prices(self, security_id, symbol, exchange, from_date, to_date):
        if self.should_fail:
            raise RuntimeError("API Error")

        return [
            HistoricalPrice(
                security_id=security_id,
                date=to_date,
                open=Decimal("100.0"),
                high=Decimal("105.0"),
                low=Decimal("95.0"),
                close=Decimal("102.0"),
                adjusted_close=Decimal("102.0"),
                volume=1000,
            )
        ]


@pytest.mark.anyio
async def test_update_daily_prices_for_all_securities():
    securities = [
        SecuritySchema(
            id=uuid4(),
            symbol="AAPL",
            exchange="US",
            currency="USD",
            name="Apple",
            isin="US0378331005",
            is_active=True,
            updated_at=datetime.now(UTC),
        )
    ]
    security_repo = MockSecurityRepository(securities)
    price_repo = MockPriceRepository()
    eodhd_gateway = MockEodhdGateway()

    service = MarketService(
        gateway=eodhd_gateway,
        price_repository=price_repo,
        security_repository=security_repo,
    )

    result = await service.update_daily_prices_for_all_securities()

    assert result == {"success": 1, "failure": 0}
    assert len(price_repo.saved_prices) == 1
    assert price_repo.saved_prices[0].security_id == securities[0].id


@pytest.mark.anyio
async def test_update_daily_prices_failure_continues():
    securities = [
        SecuritySchema(
            id=uuid4(),
            symbol="BAD",
            exchange="US",
            currency="USD",
            name="Bad",
            isin="US000",
            is_active=True,
            updated_at=datetime.now(UTC),
        ),
        SecuritySchema(
            id=uuid4(),
            symbol="GOOD",
            exchange="US",
            currency="USD",
            name="Good",
            isin="US111",
            is_active=True,
            updated_at=datetime.now(UTC),
        ),
    ]
    security_repo = MockSecurityRepository(securities)
    price_repo = MockPriceRepository()

    class FlakyGateway(MockEodhdGateway):
        @override
        def search(self, query):
            return []

        @override
        def get_price_on_date(self, security_id, symbol, exchange, date):
            return None

        @override
        def get_prices(self, security_id, symbol, exchange, from_date, to_date):
            if symbol == "BAD":
                raise RuntimeError("API Error")

            return [
                HistoricalPrice(
                    security_id=security_id,
                    date=to_date,
                    open=Decimal("10.0"),
                    high=Decimal("15.0"),
                    low=Decimal("5.0"),
                    close=Decimal("12.0"),
                    adjusted_close=Decimal("12.0"),
                    volume=100,
                )
            ]

    eodhd_gateway = FlakyGateway()

    service = MarketService(
        gateway=eodhd_gateway,
        price_repository=price_repo,
        security_repository=security_repo,
    )

    result = await service.update_daily_prices_for_all_securities()

    # Expect 1 success and 1 failure
    assert result == {"success": 1, "failure": 1}
    assert len(price_repo.saved_prices) == 1
    assert price_repo.saved_prices[0].security_id == securities[1].id
