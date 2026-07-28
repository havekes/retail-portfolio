import contextlib
import json
import logging
import os
import shutil
import sys

from rich.console import Console
from rich.logging import RichHandler
from rich.traceback import install

from src.config.settings import settings
from src.core.context import get_request_id


class FallbackRichHandler(RichHandler):
    """RichHandler wrapper that falls back to standard StreamHandler.

    Used when formatting or rendering errors occur.
    """

    def emit(self, record: logging.LogRecord) -> None:
        try:
            super().emit(record)
        except Exception:  # noqa: BLE001
            try:
                fallback_handler = logging.StreamHandler(sys.stderr)
                fallback_handler.setFormatter(
                    logging.Formatter("[FALLBACK] %(levelname)s: %(message)s")
                )
                fallback_handler.emit(record)
            except Exception:  # noqa: BLE001, S110
                pass



class RequestIdFilter(logging.Filter):
    """Filter that injects request_id from contextvars into log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id() or "-"
        return True


class JsonFormatter(logging.Formatter):
    """Formats log records as JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        log_dict = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", "-"),
        }

        for field in ("user_id", "domain", "duration_ms"):
            if hasattr(record, field):
                log_dict[field] = getattr(record, field)

        if record.exc_info:
            log_dict["exc_info"] = self.formatException(record.exc_info)
        elif record.exc_text:
            log_dict["exc_info"] = record.exc_text

        if record.stack_info:
            log_dict["stack_info"] = self.formatStack(record.stack_info)

        return json.dumps(log_dict, default=str)


def init_logging() -> None:
    if settings.environment == "prod":
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        handler.addFilter(RequestIdFilter())

        logging.basicConfig(
            level=logging.DEBUG,
            handlers=[handler],
            force=True,
        )
    else:
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

        handler = FallbackRichHandler(
            console=console,
            rich_tracebacks=True,
            show_path=True,
            enable_link_path=True,
        )
        handler.addFilter(RequestIdFilter())

        logging.basicConfig(
            level=logging.DEBUG,
            format="[%(request_id)s] %(message)s",
            datefmt="[%X]",
            handlers=[handler],
            force=True,
        )

    # Suppress verbose third-party loggers
    for logger_name in ["urllib3", "httpx", "watchfiles", "faker", "svcs"]:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.INFO)
