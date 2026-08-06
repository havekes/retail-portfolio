from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import override
from uuid import uuid4

import pytest

from src.market.api_types import HistoricalPrice, IntradayHistoricalPrice, SecurityId
from src.market.gateway import MarketGateway
from src.market.repository import (
    IntradayPriceRepository,
    PriceRepository,
    SecurityRepository,
)
from src.market.schema import IntradayPriceSchema, PriceSchema, SecuritySchema
from src.market.service import MarketService


class MockSecurityRepository(SecurityRepository):
    def __init__(self, securities: list[SecuritySchema]):
        self.securities = securities

    @override
    async def get_by_id_or_fail(self, security_id: SecurityId) -> SecuritySchema:
        for security in self.securities:
            if security.id == security_id:
                return security
        msg = "Not found"
        raise ValueError(msg)

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
    async def get_prices(
        self, security, from_date, to_date, offset: int = 0, limit: int = 50
    ):
        return [], 0

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


class MockIntradayPriceRepository(IntradayPriceRepository):
    def __init__(self):
        self.saved_prices: list[IntradayPriceSchema] = []

    @override
    async def get_intraday_prices(
        self,
        security_id: SecurityId,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[IntradayPriceSchema]:
        return [p for p in self.saved_prices if p.security_id == security_id]

    @override
    async def save_intraday_price(
        self, price: IntradayPriceSchema
    ) -> IntradayPriceSchema:
        self.saved_prices.append(price)
        return price

    @override
    async def save_intraday_prices(
        self, prices: list[IntradayPriceSchema]
    ) -> list[IntradayPriceSchema]:
        self.saved_prices.extend(prices)
        return prices

    @override
    async def get_latest_intraday_close_by_security(
        self,
    ) -> dict[SecurityId, Decimal]:
        intermediate: dict[SecurityId, tuple[datetime, Decimal]] = {}
        for p in self.saved_prices:
            existing = intermediate.get(p.security_id)
            if existing is None or p.timestamp > existing[0]:
                intermediate[p.security_id] = (p.timestamp, p.close)
        return {sid: close for sid, (_, close) in intermediate.items()}


class MockEodhdGateway(MarketGateway):
    def __init__(self, should_fail: bool = False):  # noqa: FBT001, FBT002
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
            msg = "API Error"
            raise RuntimeError(msg)

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

    @override
    def get_intraday_prices(
        self,
        security_id,
        symbol,
        exchange,
        from_datetime,
        to_datetime,
        interval="1h",
    ):
        if self.should_fail:
            msg = "API Error"
            raise RuntimeError(msg)

        dt = (
            from_datetime
            if from_datetime.tzinfo
            else from_datetime.replace(
                tzinfo=from_datetime.tzinfo or datetime.now().astimezone().tzinfo
            )
        )
        return [
            IntradayHistoricalPrice(
                security_id=security_id,
                timestamp=dt,
                open=Decimal("100.0"),
                high=Decimal("105.0"),
                low=Decimal("95.0"),
                close=Decimal("102.0"),
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
    intraday_price_repo = MockIntradayPriceRepository()
    eodhd_gateway = MockEodhdGateway()

    service = MarketService(
        gateway=eodhd_gateway,
        price_repository=price_repo,
        security_repository=security_repo,
        intraday_price_repository=intraday_price_repo,
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
    intraday_price_repo = MockIntradayPriceRepository()

    class FlakyGateway(MockEodhdGateway):
        @override
        def get_prices(self, security_id, symbol, exchange, from_date, to_date):
            if symbol == "BAD":
                msg = "API Error"
                raise RuntimeError(msg)
            return super().get_prices(
                security_id, symbol, exchange, from_date, to_date
            )

    service = MarketService(
        gateway=FlakyGateway(),
        price_repository=price_repo,
        security_repository=security_repo,
        intraday_price_repository=intraday_price_repo,
    )

    result = await service.update_daily_prices_for_all_securities()

    assert result == {"success": 1, "failure": 1}
    assert len(price_repo.saved_prices) == 1
    assert price_repo.saved_prices[0].security_id == securities[1].id


@pytest.mark.anyio
async def test_update_intraday_prices_for_all_securities():
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
    intraday_price_repo = MockIntradayPriceRepository()
    eodhd_gateway = MockEodhdGateway()

    service = MarketService(
        gateway=eodhd_gateway,
        price_repository=price_repo,
        security_repository=security_repo,
        intraday_price_repository=intraday_price_repo,
    )

    result = await service.update_intraday_prices_for_all_securities()

    assert result == {"success": 1, "failure": 0}
    assert len(intraday_price_repo.saved_prices) == 1
    assert intraday_price_repo.saved_prices[0].security_id == securities[0].id

    # Verify populated-then-retrieved path: the repository returns rows
    # when queried for the security (end-to-end coverage for issue #140)
    retrieved = await intraday_price_repo.get_intraday_prices(securities[0].id)
    assert len(retrieved) == 1
    assert retrieved[0].security_id == securities[0].id


@pytest.mark.anyio
async def test_update_intraday_prices_failure_continues():
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
    intraday_price_repo = MockIntradayPriceRepository()

    class FlakyIntradayGateway(MockEodhdGateway):
        @override
        def get_intraday_prices(
            self,
            security_id,
            symbol,
            exchange,
            from_datetime,
            to_datetime,
            interval="1h",
        ):
            if symbol == "BAD":
                msg = "API Error"
                raise RuntimeError(msg)
            return super().get_intraday_prices(
                security_id, symbol, exchange, from_datetime, to_datetime, interval
            )

    service = MarketService(
        gateway=FlakyIntradayGateway(),
        price_repository=price_repo,
        security_repository=security_repo,
        intraday_price_repository=intraday_price_repo,
    )

    result = await service.update_intraday_prices_for_all_securities()

    assert result == {"success": 1, "failure": 1}
    assert len(intraday_price_repo.saved_prices) == 1
    assert intraday_price_repo.saved_prices[0].security_id == securities[1].id


@pytest.mark.anyio
async def test_fetch_and_save_intraday_prices_success():
    security = SecuritySchema(
        id=uuid4(),
        symbol="AAPL",
        exchange="US",
        currency="USD",
        name="Apple",
        isin="US0378331005",
        is_active=True,
        updated_at=datetime.now(UTC),
    )
    security_repo = MockSecurityRepository([security])
    price_repo = MockPriceRepository()
    intraday_price_repo = MockIntradayPriceRepository()
    gateway = MockEodhdGateway()

    service = MarketService(
        gateway=gateway,
        price_repository=price_repo,
        security_repository=security_repo,
        intraday_price_repository=intraday_price_repo,
    )

    result = await service.fetch_and_save_intraday_prices(security)

    assert result is True
    assert len(intraday_price_repo.saved_prices) == 1
    assert intraday_price_repo.saved_prices[0].security_id == security.id


@pytest.mark.anyio
async def test_fetch_and_save_intraday_prices_custom_range():
    security = SecuritySchema(
        id=uuid4(),
        symbol="AAPL",
        exchange="US",
        currency="USD",
        name="Apple",
        isin="US0378331005",
        is_active=True,
        updated_at=datetime.now(UTC),
    )
    security_repo = MockSecurityRepository([security])
    price_repo = MockPriceRepository()
    intraday_price_repo = MockIntradayPriceRepository()

    class CustomGateway(MockEodhdGateway):
        def __init__(self):
            super().__init__()
            self.captured_from_datetime = None
            self.captured_to_datetime = None

        @override
        def get_intraday_prices(
            self,
            security_id,
            symbol,
            exchange,
            from_datetime,
            to_datetime,
            interval="1h",
        ):
            self.captured_from_datetime = from_datetime
            self.captured_to_datetime = to_datetime
            return super().get_intraday_prices(
                security_id, symbol, exchange, from_datetime, to_datetime, interval
            )

    gateway = CustomGateway()
    service = MarketService(
        gateway=gateway,
        price_repository=price_repo,
        security_repository=security_repo,
        intraday_price_repository=intraday_price_repo,
    )

    from_dt = datetime(2026, 1, 1, 0, 0, tzinfo=UTC)
    to_dt = datetime(2026, 1, 10, 0, 0, tzinfo=UTC)

    result = await service.fetch_and_save_intraday_prices(
        security, from_datetime=from_dt, to_datetime=to_dt
    )

    assert result is True
    assert gateway.captured_from_datetime == from_dt
    assert gateway.captured_to_datetime == to_dt


@pytest.mark.anyio
async def test_fetch_and_save_intraday_prices_empty():
    security = SecuritySchema(
        id=uuid4(),
        symbol="AAPL",
        exchange="US",
        currency="USD",
        name="Apple",
        isin="US0378331005",
        is_active=True,
        updated_at=datetime.now(UTC),
    )
    security_repo = MockSecurityRepository([security])
    price_repo = MockPriceRepository()
    intraday_price_repo = MockIntradayPriceRepository()

    class EmptyIntradayGateway(MockEodhdGateway):
        @override
        def get_intraday_prices(
            self,
            security_id,
            symbol,
            exchange,
            from_datetime,
            to_datetime,
            interval="1h",
        ):
            return []

    service = MarketService(
        gateway=EmptyIntradayGateway(),
        price_repository=price_repo,
        security_repository=security_repo,
        intraday_price_repository=intraday_price_repo,
    )

    result = await service.fetch_and_save_intraday_prices(security)

    assert result is True
    assert len(intraday_price_repo.saved_prices) == 0


@pytest.mark.anyio
async def test_fetch_and_save_intraday_prices_gateway_error():
    security = SecuritySchema(
        id=uuid4(),
        symbol="BAD",
        exchange="US",
        currency="USD",
        name="Bad",
        isin="US000",
        is_active=True,
        updated_at=datetime.now(UTC),
    )
    security_repo = MockSecurityRepository([security])
    price_repo = MockPriceRepository()
    intraday_price_repo = MockIntradayPriceRepository()

    gateway = MockEodhdGateway(should_fail=True)

    service = MarketService(
        gateway=gateway,
        price_repository=price_repo,
        security_repository=security_repo,
        intraday_price_repository=intraday_price_repo,
    )

    result = await service.fetch_and_save_intraday_prices(security)

    assert result is False
    assert len(intraday_price_repo.saved_prices) == 0


def test_aggregate_weekly_prices_unit():
    """Test unit logic of aggregate_weekly_prices in service."""
    from dateutil.parser import parse
    from datetime import date
    from decimal import Decimal
    from uuid import uuid4
    from src.market.schema import PriceSchema
    from src.market.service import aggregate_weekly_prices, PriceAggregationService

    sec_id = uuid4()
    prices = [
        PriceSchema(
            security_id=sec_id,
            date=date(2026, 1, 12),
            open=Decimal("100.00"),
            high=Decimal("105.00"),
            low=Decimal("99.00"),
            close=Decimal("102.00"),
            adjusted_close=Decimal("102.00"),
            volume=1000,
        ),
        PriceSchema(
            security_id=sec_id,
            date=date(2026, 1, 13),
            open=Decimal("102.00"),
            high=Decimal("108.00"),
            low=Decimal("101.00"),
            close=Decimal("107.00"),
            adjusted_close=Decimal("107.00"),
            volume=1500,
        ),
        PriceSchema(
            security_id=sec_id,
            date=date(2026, 1, 19),
            open=Decimal("107.00"),
            high=Decimal("110.00"),
            low=Decimal("105.00"),
            close=Decimal("109.00"),
            adjusted_close=Decimal("109.00"),
            volume=2000,
        ),
    ]
    weekly = aggregate_weekly_prices(prices)
    assert len(weekly) == 2
    assert weekly[0].date == date(2026, 1, 12)
    assert weekly[0].open == Decimal("100.00")
    assert weekly[0].high == Decimal("108.00")
    assert weekly[0].low == Decimal("99.00")
    assert weekly[0].close == Decimal("107.00")
    assert weekly[0].volume == 2500

    assert weekly[1].date == date(2026, 1, 19)
    assert weekly[1].volume == 2000

    # Also test via PriceAggregationService static method
    weekly_svc = PriceAggregationService.aggregate_weekly_prices(prices)
    assert len(weekly_svc) == 2


def test_aggregate_monthly_prices_unit():
    """Test unit logic of aggregate_monthly_prices in service."""
    from datetime import date
    from decimal import Decimal
    from uuid import uuid4
    from src.market.schema import PriceSchema
    from src.market.service import aggregate_monthly_prices, PriceAggregationService

    sec_id = uuid4()
    prices = [
        PriceSchema(
            security_id=sec_id,
            date=date(2026, 1, 15),
            open=Decimal("100.00"),
            high=Decimal("120.00"),
            low=Decimal("95.00"),
            close=Decimal("115.00"),
            adjusted_close=Decimal("115.00"),
            volume=5000,
        ),
        PriceSchema(
            security_id=sec_id,
            date=date(2026, 2, 10),
            open=Decimal("115.00"),
            high=Decimal("130.00"),
            low=Decimal("110.00"),
            close=Decimal("125.00"),
            adjusted_close=Decimal("125.00"),
            volume=6000,
        ),
    ]
    monthly = aggregate_monthly_prices(prices)
    assert len(monthly) == 2
    assert monthly[0].date == date(2026, 1, 15)
    assert monthly[0].close == Decimal("115.00")
    assert monthly[1].date == date(2026, 2, 10)
    assert monthly[1].close == Decimal("125.00")

    # Also test via PriceAggregationService static method
    monthly_svc = PriceAggregationService.aggregate_monthly_prices(prices)
    assert len(monthly_svc) == 2


def test_aggregate_4h_candles_unit():
    """Test unit logic of aggregate_4h_candles in service."""
    from datetime import UTC, datetime
    from decimal import Decimal
    from uuid import uuid4
    from src.market.schema import IntradayPriceSchema
    from src.market.service import aggregate_4h_candles, PriceAggregationService

    sec_id = uuid4()
    candles = [
        IntradayPriceSchema(
            security_id=sec_id,
            timestamp=datetime(2026, 1, 15, 9, 30, tzinfo=UTC),
            open=Decimal("100.00"),
            high=Decimal("102.00"),
            low=Decimal("99.00"),
            close=Decimal("101.00"),
            volume=100,
        ),
        IntradayPriceSchema(
            security_id=sec_id,
            timestamp=datetime(2026, 1, 15, 10, 30, tzinfo=UTC),
            open=Decimal("101.00"),
            high=Decimal("105.00"),
            low=Decimal("100.00"),
            close=Decimal("104.00"),
            volume=200,
        ),
        IntradayPriceSchema(
            security_id=sec_id,
            timestamp=datetime(2026, 1, 15, 13, 0, tzinfo=UTC),
            open=Decimal("104.00"),
            high=Decimal("106.00"),
            low=Decimal("103.00"),
            close=Decimal("105.00"),
            volume=150,
        ),
    ]
    aggregated = aggregate_4h_candles(candles)
    assert len(aggregated) == 2
    assert aggregated[0].timestamp == datetime(2026, 1, 15, 8, 0, tzinfo=UTC)
    assert aggregated[0].open == Decimal("100.00")
    assert aggregated[0].high == Decimal("105.00")
    assert aggregated[0].low == Decimal("99.00")
    assert aggregated[0].close == Decimal("104.00")
    assert aggregated[0].volume == 300

    assert aggregated[1].timestamp == datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
    assert aggregated[1].volume == 150

    # Also test via PriceAggregationService static method
    agg_svc = PriceAggregationService.aggregate_4h_candles(candles)
    assert len(agg_svc) == 2
