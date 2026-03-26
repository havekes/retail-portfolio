import contextlib
import logging
import os
import shutil

from rich.console import Console
from rich.logging import RichHandler
from rich.traceback import install


def init_logging() -> None:
    # Attempt to get terminal width, defaulting to 100 if detection fails
    width = shutil.get_terminal_size(fallback=(100, 24)).columns
    # If running in Docker/CI, COLUMNS might be set
    if "COLUMNS" in os.environ:
        with contextlib.suppress(ValueError):
            width = int(os.environ["COLUMNS"])

    # Use a custom console to ensure width is detected correctly (e.g., in Docker)
    console = Console(force_terminal=True, width=width)

    # Install rich traceback handler
    install(console=console, show_locals=True)

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[
            RichHandler(
                console=console,
                rich_tracebacks=True,
                show_path=True,
                enable_link_path=True,
            )
        ],
        force=True,
    )

    # Suppress verbose third-party loggers
    for logger_name in ["urllib3", "httpx", "aiosqlite", "watchfiles", "faker"]:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.INFO)
