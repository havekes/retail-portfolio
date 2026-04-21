import argparse
import asyncio
import logging
import uuid

from rich import print as rprint

from src.account.enum import InstitutionEnum
from src.integration.brokers.wealthsimple import wealthsimple_api_wrapper_factory
from src.integration.schema import IntegrationUserSchema

logging.basicConfig(level=logging.INFO)


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Get wealthsimple positions for an account"
    )
    _ = parser.add_argument("username", type=str, help="Wealthsimple username (email)")
    _ = parser.add_argument("account_id", type=str, help="Wealthsimple account ID")
    _ = parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug API responses logging",
    )
    _ = parser.add_argument(
        "--dump",
        type=str,
        help="Path to dump the raw API response JSON",
        default=None,
    )

    args = parser.parse_args()

    if args.debug:
        logging.getLogger("src.integration.brokers.wealthsimple").setLevel(
            logging.DEBUG
        )

    gateway = await wealthsimple_api_wrapper_factory(
        debug_api_responses=args.debug,
        debug_dump_path=args.dump,
    )

    user = IntegrationUserSchema(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        institution_id=InstitutionEnum.WEALTHSIMPLE,
        external_user_id=args.username,
        display_name=args.username,
    )

    positions = await gateway.get_positions_by_account(user, args.account_id)
    rprint(positions)


if __name__ == "__main__":
    asyncio.run(main())
