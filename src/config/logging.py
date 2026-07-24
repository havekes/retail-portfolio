import contextlib
import logging
import os
import shutil
import sys

import structlog
from rich.console import Console
from rich.logging import RichHandler
from rich.traceback import install

from src.config.settings import settings


def init_logging() -> None:
    # Attempt to get terminal width, defaulting to 120 if detection fails
    width = shutil.get_terminal_size(fallback=(120, 24)).columns
    # If running in Docker/CI, COLUMNS might be set
    if "COLUMNS" in os.environ:
        with contextlib.suppress(ValueError):
            width = int(os.environ["COLUMNS"])

    # Use a custom console to ensure width is detected correctly (e.g., in Docker)
    console = Console(force_terminal=True, width=width)

    # Install rich traceback handler
    install(console=console, show_locals=True)

    if settings.environment == "prod":
        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer(),
            ],
            wrapper_class=structlog.stdlib.BoundLogger,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )

        handler = logging.StreamHandler(sys.stdout)
        # Using structlog formatter for standard library logs
        formatter = structlog.stdlib.ProcessorFormatter(
            processor=structlog.processors.JSONRenderer(),
        )
        handler.setFormatter(formatter)

        logging.basicConfig(
            level=logging.INFO,
            handlers=[handler],
            force=True,
        )
    else:
        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
            ],
            wrapper_class=structlog.stdlib.BoundLogger,
            logger_factory=structlog.stdlib.LoggerFactory(),
            cache_logger_on_first_use=True,
        )
        handler = RichHandler(
            console=console,
            rich_tracebacks=True,
            show_path=True,
            enable_link_path=True,
        )
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(message)s",
            datefmt="[%X]",
            handlers=[handler],
            force=True,
        )

    # Suppress verbose third-party loggers
    for logger_name in ["urllib3", "httpx", "watchfiles", "faker", "svcs"]:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.INFO)
