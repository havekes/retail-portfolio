import argparse

from rich import print as rprint

from src.market.eodhd import eodhd_gateway_factory


def main():
    parser = argparse.ArgumentParser(
        description="Search for symbols using EODHD gateway"
    )
    _ = parser.add_argument("query", type=str, help="Search query (e.g., 'Apple Inc')")

    eodhd = eodhd_gateway_factory()
    args = parser.parse_args()

    search_results = eodhd.search(args.query)
    rprint(search_results)


if __name__ == "__main__":
    main()
