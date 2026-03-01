import argparse
from pathlib import Path

from crontab import CronTab
from rich import print as rprint


def setup_cron() -> None:
    # We want to run the update_daily_prices command using uv inside the project root
    project_root = Path(__file__).resolve().parent.parent.parent
    command = (
        f"cd {project_root} && "
        f"/usr/local/bin/uv run python -m src.market.commands.update_daily_prices"
    )

    # Access current user's crontab
    cron = CronTab(user=True)

    # Remove existing jobs with our specific comment to avoid duplicates
    cron.remove_all(comment="retail-portfolio-daily-prices")

    # Create new job
    job = cron.new(command=command, comment="retail-portfolio-daily-prices")

    # Set to run daily at midnight
    job.setall("0 0 * * *")

    # Save the crontab
    cron.write()
    rprint("[green]Successfully installed cron job for daily price updates.[/green]")


def remove_cron() -> None:
    cron = CronTab(user=True)
    cron.remove_all(comment="retail-portfolio-daily-prices")
    cron.write()
    rprint("[green]Successfully removed cron job for daily price updates.[/green]")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Manage the cron job for retail-portfolio daily price updates."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--install",
        action="store_true",
        help="Install the cron job to run daily.",
    )
    group.add_argument(
        "--remove",
        action="store_true",
        help="Remove the existing cron job.",
    )

    args = parser.parse_args()

    if args.install:
        setup_cron()
    elif args.remove:
        remove_cron()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
