import argparse
import uuid
from datetime import UTC, datetime, timedelta

from rich import print as rprint

from src.market.eodhd import eodhd_gateway_factory
from src.market.schema import SecuritySchema


def main():
    parser = argparse.ArgumentParser(
        description="Get prices for a symbol from EODHD demo"
    )
    _ = parser.add_argument("symbol", type=str, help="Symbol")
    _ = parser.add_argument(
        "--from-date",
        type=str,
        help="From date (default: today - 1 week)",
        default=datetime.now(UTC).date() - timedelta(days=7),
        required=False,
    )
    _ = parser.add_argument(
        "--to-date",
        type=str,
        help="From date (default: yesterday)",
        default=datetime.now(UTC).date() - timedelta(days=1),
        required=False,
    )

    eodhd = eodhd_gateway_factory()
    args = parser.parse_args()
    security = SecuritySchema(
        id=uuid.uuid4(),
        symbol=args.symbol,
        exchange="US",
        currency="USD",
        name="",
        isin="",
        updated_at=datetime.now(UTC),
    )

    price = eodhd.get_prices(security, from_date=args.from_date, to_date=args.to_date)
    rprint(price)


if __name__ == "__main__":
    main()
