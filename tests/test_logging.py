import json
import logging
from src.config.logging import JsonFormatter


def test_json_formatter_basic():
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Test message",
        args=(),
        exc_info=None,
    )
    record.created = 1600000000.0

    formatted = formatter.format(record)
    data = json.loads(formatted)

    assert data["level"] == "INFO"
    assert data["logger"] == "test_logger"
    assert data["message"] == "Test message"
    assert data["request_id"] == "-"


def test_json_formatter_optional_fields():
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Test message",
        args=(),
        exc_info=None,
    )
    record.user_id = 123
    record.domain = "auth"
    record.duration_ms = 45

    formatted = formatter.format(record)
    data = json.loads(formatted)

    assert data["user_id"] == 123
    assert data["domain"] == "auth"
    assert data["duration_ms"] == 45


def test_json_formatter_exc_info():
    formatter = JsonFormatter()
    try:
        1 / 0
    except ZeroDivisionError:
        import sys

        exc_info = sys.exc_info()

    record = logging.LogRecord(
        name="test_logger",
        level=logging.ERROR,
        pathname="test.py",
        lineno=10,
        msg="Error occurred",
        args=(),
        exc_info=exc_info,
    )

    formatted = formatter.format(record)
    data = json.loads(formatted)

    assert "exc_info" in data
    assert "ZeroDivisionError" in data["exc_info"]


def test_json_formatter_exc_text():
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.ERROR,
        pathname="test.py",
        lineno=10,
        msg="Error occurred",
        args=(),
        exc_info=None,
    )
    record.exc_text = "Cached traceback string"

    formatted = formatter.format(record)
    data = json.loads(formatted)

    assert data["exc_info"] == "Cached traceback string"


def test_json_formatter_stack_info():
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.ERROR,
        pathname="test.py",
        lineno=10,
        msg="Error occurred",
        args=(),
        exc_info=None,
    )
    record.stack_info = "Stack frame data"

    formatted = formatter.format(record)
    data = json.loads(formatted)

    assert "stack_info" in data


def test_json_formatter_unserializable_extra():
    class Unserializable:
        def __str__(self):
            return "<unserializable>"

    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Test message",
        args=(),
        exc_info=None,
    )
    record.user_id = Unserializable()

    formatted = formatter.format(record)
    data = json.loads(formatted)

    assert data["user_id"] == "<unserializable>"


from unittest.mock import MagicMock, patch
from src.config.logging import FallbackRichHandler, init_logging


def test_fallback_rich_handler_success():
    handler = FallbackRichHandler()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Success message",
        args=(),
        exc_info=None,
    )
    with patch("rich.logging.RichHandler.emit") as mock_super_emit:
        handler.emit(record)
        mock_super_emit.assert_called_once_with(record)


def test_fallback_rich_handler_failure(capsys):
    handler = FallbackRichHandler()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Failure test message",
        args=(),
        exc_info=None,
    )
    with patch("rich.logging.RichHandler.emit", side_effect=RuntimeError("Rich error")):
        handler.emit(record)

    captured = capsys.readouterr()
    assert "[FALLBACK] INFO: Failure test message" in captured.err


def test_fallback_rich_handler_double_failure():
    handler = FallbackRichHandler()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Double failure test message",
        args=(),
        exc_info=None,
    )
    with (
        patch("rich.logging.RichHandler.emit", side_effect=RuntimeError("Rich error")),
        patch("logging.StreamHandler.emit", side_effect=RuntimeError("Fallback error")),
    ):
        # Should catch all exceptions and not raise
        handler.emit(record)


def test_init_logging_dev_mode():
    with (
        patch("src.config.logging.settings.environment", "dev"),
        patch("logging.basicConfig") as mock_basic_config,
    ):
        init_logging()
        assert mock_basic_config.called
        kwargs = mock_basic_config.call_args.kwargs
        assert "handlers" in kwargs
        assert len(kwargs["handlers"]) == 1
        assert isinstance(kwargs["handlers"][0], FallbackRichHandler)
