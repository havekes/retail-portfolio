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
        exc_info=None
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
        exc_info=None
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
        exc_info=exc_info
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
        exc_info=None
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
        exc_info=None
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
        exc_info=None
    )
    record.user_id = Unserializable()
    
    formatted = formatter.format(record)
    data = json.loads(formatted)
    
    assert data["user_id"] == "<unserializable>"
