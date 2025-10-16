"""
Unit tests for structured logging configuration.

Tests JSON formatting, extra field extraction, and logging setup.
"""

import pytest
import logging
import json
import tempfile
import uuid
from pathlib import Path
from unittest.mock import Mock, patch
from src.logging_config import JSONFormatter, setup_logging, get_correlation_id


class TestJSONFormatter:
    """Test suite for JSONFormatter class."""

    def test_formats_basic_log_message(self):
        """Basic log message is formatted as JSON."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None
        )

        result = formatter.format(record)
        log_obj = json.loads(result)

        assert log_obj["message"] == "Test message"
        assert log_obj["level"] == "INFO"
        assert log_obj["logger"] == "test"
        assert log_obj["line"] == 42
        assert "timestamp" in log_obj
        assert log_obj["timestamp"].endswith("Z")  # UTC

    def test_extracts_extra_fields(self):
        """Extra fields are extracted and included in JSON output."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Processing document",
            args=(),
            exc_info=None
        )

        # Add extra fields as attributes (how Python logging works)
        record.pdf_path = "/path/to/doc.pdf"
        record.doc_id = 123
        record.sha256_hex = "abc123..."
        record.stage = "API Stage"

        result = formatter.format(record)
        log_obj = json.loads(result)

        assert log_obj["pdf_path"] == "/path/to/doc.pdf"
        assert log_obj["doc_id"] == 123
        assert log_obj["sha256_hex"] == "abc123..."
        assert log_obj["stage"] == "API Stage"

    def test_extracts_performance_metrics(self):
        """Performance and cost metrics are extracted."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=20,
            msg="API call completed",
            args=(),
            exc_info=None
        )

        record.duration_ms = 1234
        record.cost_usd = 0.05
        record.prompt_tokens = 500
        record.output_tokens = 200

        result = formatter.format(record)
        log_obj = json.loads(result)

        assert log_obj["duration_ms"] == 1234
        assert log_obj["cost_usd"] == 0.05
        assert log_obj["prompt_tokens"] == 500
        assert log_obj["output_tokens"] == 200

    def test_includes_correlation_id(self):
        """Correlation ID is included when present."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=15,
            msg="Test",
            args=(),
            exc_info=None
        )

        correlation_id = "test-correlation-id-123"
        record.correlation_id = correlation_id

        result = formatter.format(record)
        log_obj = json.loads(result)

        assert log_obj["correlation_id"] == correlation_id

    def test_includes_exception_info(self):
        """Exception info is formatted and included."""
        formatter = JSONFormatter()

        try:
            raise ValueError("Test error")
        except ValueError:
            import sys
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=30,
            msg="Error occurred",
            args=(),
            exc_info=exc_info
        )

        result = formatter.format(record)
        log_obj = json.loads(result)

        assert "exception" in log_obj
        assert "ValueError: Test error" in log_obj["exception"]
        assert "Traceback" in log_obj["exception"]

    def test_handles_missing_extra_fields_gracefully(self):
        """Missing extra fields are not included (no errors)."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=25,
            msg="Test",
            args=(),
            exc_info=None
        )

        # Don't add any extra fields
        result = formatter.format(record)
        log_obj = json.loads(result)

        # Should have basic fields but not extra fields
        assert "message" in log_obj
        assert "pdf_path" not in log_obj
        assert "doc_id" not in log_obj

    def test_extracts_status_and_duplicate_flags(self):
        """Status and duplicate flags are extracted."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=35,
            msg="Document processed",
            args=(),
            exc_info=None
        )

        record.status = "completed"
        record.is_duplicate = True
        record.file_size_bytes = 12345

        result = formatter.format(record)
        log_obj = json.loads(result)

        assert log_obj["status"] == "completed"
        assert log_obj["is_duplicate"] is True
        assert log_obj["file_size_bytes"] == 12345


class TestSetupLogging:
    """Test suite for setup_logging function."""

    def test_creates_logger_with_correct_level(self):
        """Logger is created with specified log level."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            logger = setup_logging(log_level="DEBUG", log_file=str(log_file))

            assert logger.level == logging.DEBUG

    def test_creates_log_directory_if_not_exists(self):
        """Log directory is created if it doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "nested" / "dir" / "test.log"
            logger = setup_logging(log_file=str(log_file))

            assert log_file.parent.exists()

    def test_creates_both_console_and_file_handlers(self):
        """Both console and file handlers are created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            logger = setup_logging(log_file=str(log_file))

            assert len(logger.handlers) == 2
            handler_types = [type(h).__name__ for h in logger.handlers]
            assert "StreamHandler" in handler_types
            assert "RotatingFileHandler" in handler_types

    def test_json_formatter_used_for_json_format(self):
        """JSONFormatter is used when format='json'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            logger = setup_logging(log_format="json", log_file=str(log_file))

            # Check file handler has JSONFormatter
            file_handler = [h for h in logger.handlers
                           if type(h).__name__ == "RotatingFileHandler"][0]
            assert isinstance(file_handler.formatter, JSONFormatter)

    def test_text_formatter_used_for_text_format(self):
        """Standard formatter is used when format='text'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = Path(tmpdir) / "test.log"
            logger = setup_logging(log_format="text", log_file=str(log_file))

            # Check file handler has standard Formatter
            file_handler = [h for h in logger.handlers
                           if type(h).__name__ == "RotatingFileHandler"][0]
            assert isinstance(file_handler.formatter, logging.Formatter)
            assert not isinstance(file_handler.formatter, JSONFormatter)


class TestGetCorrelationId:
    """Test suite for get_correlation_id function."""

    def test_returns_valid_uuid_string(self):
        """Correlation ID is a valid UUID string."""
        correlation_id = get_correlation_id()

        # Should be valid UUID format
        uuid_obj = uuid.UUID(correlation_id)
        assert str(uuid_obj) == correlation_id

    def test_generates_unique_ids(self):
        """Each call generates a unique ID."""
        id1 = get_correlation_id()
        id2 = get_correlation_id()
        id3 = get_correlation_id()

        assert id1 != id2
        assert id2 != id3
        assert id1 != id3

    def test_returns_string_type(self):
        """Correlation ID is returned as string."""
        correlation_id = get_correlation_id()
        assert isinstance(correlation_id, str)
