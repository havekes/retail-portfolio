import argparse
import uuid
from datetime import UTC, datetime, timedelta

from rich import print as rprint

from src.market.eodhd import eodhd_gateway_factory
from src.market.schema import SecuritySchema


def main():
    parser = argparse.ArgumentParser(
        description="Get a price for a symbol from EODHD demo"
    )
    _ = parser.add_argument("symbol", type=str, help="Symbol")
    _ = parser.add_argument(
        "--date",
        type=str,
        help="On specific date (default: yestarday UTC)",
        default=None,
        required=False,
    )

    eodhd = eodhd_gateway_factory()
    args = parser.parse_args()

    if args.date is None:
        date = (datetime.now(UTC) - timedelta(days=1)).date()
    else:
        date = datetime.strptime(args.date, "%Y-%m-%d").date()  # noqa: DTZ007

    security = SecuritySchema(
        id=uuid.uuid4(),
        symbol=args.symbol,
        exchange="US",
        currency="USD",
        name="",
        isin="",
        updated_at=datetime.now(UTC),
    )

    price = eodhd.get_price_on_date(security, date)
    rprint(price)


if __name__ == "__main__":
    main()
