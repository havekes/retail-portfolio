import argparse
import asyncio
import uuid

from rich import print as rprint
from sqlalchemy import delete, func, select

from src.config.database import sessionmanager
from src.market.cache import indicator_cache_factory
from src.market.model import IntradayPriceModel, PriceModel, SecurityModel


def _confirm(prompt: str) -> bool:
    answer = input(f"{prompt} [y/N]: ").strip().lower()
    return answer in ("y", "yes")


async def flush_all() -> None:
    cache = await indicator_cache_factory()
    async with sessionmanager.session() as session:
        price_count = (
            await session.scalar(select(func.count()).select_from(PriceModel)) or 0
        )
        intraday_count = (
            await session.scalar(select(func.count()).select_from(IntradayPriceModel))
            or 0
        )
        total = price_count + intraday_count

        if total == 0:
            rprint("No market data to flush.")
            return

        rprint(
            f"Found {price_count} daily price rows and "
            f"{intraday_count} intraday price rows."
        )
        if not _confirm("Flush ALL market data?"):
            rprint("Aborted.")
            return

        await session.execute(delete(PriceModel))
        await session.execute(delete(IntradayPriceModel))
        await session.commit()
        await cache.flush_all()
        rprint(f"Flushed {total} market data rows and indicator cache.")


async def flush_security(security_id_str: str) -> None:
    cache = await indicator_cache_factory()
    async with sessionmanager.session() as session:
        try:
            security_id = uuid.UUID(security_id_str)
        except ValueError:
            rprint(f"[red]Invalid security id: {security_id_str}[/red]")
            return

        security = await session.get(SecurityModel, security_id)
        if security is None:
            rprint(f"[red]Security {security_id} not found.[/red]")
            return

        price_count = (
            await session.scalar(
                select(func.count())
                .select_from(PriceModel)
                .where(PriceModel.security_id == security_id)
            )
            or 0
        )
        intraday_count = (
            await session.scalar(
                select(func.count())
                .select_from(IntradayPriceModel)
                .where(IntradayPriceModel.security_id == security_id)
            )
            or 0
        )
        total = price_count + intraday_count

        if total == 0:
            rprint(
                f"No market data to flush for {security.symbol} ({security.exchange})."
            )
            return

        rprint(
            f"Found {price_count} daily price rows and "
            f"{intraday_count} intraday price rows for "
            f"{security.symbol} ({security.exchange})."
        )
        if not _confirm("Flush market data for this security?"):
            rprint("Aborted.")
            return

        await session.execute(
            delete(PriceModel).where(PriceModel.security_id == security_id)
        )
        await session.execute(
            delete(IntradayPriceModel).where(
                IntradayPriceModel.security_id == security_id
            )
        )
        await session.commit()
        await cache.invalidate_security(str(security_id))
        rprint(
            f"Flushed {total} market data rows for "
            f"{security.symbol} ({security.exchange})."
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Flush market data for a security or all securities (admin)"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--security-id",
        type=str,
        help="Flush market data for a single security (by id)",
    )
    group.add_argument(
        "--all",
        action="store_true",
        help="Flush market data for all securities",
    )
    args = parser.parse_args()

    if args.all:
        asyncio.run(flush_all())
    else:
        asyncio.run(flush_security(args.security_id))


if __name__ == "__main__":
    main()
