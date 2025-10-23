"""
Structured logging configuration with JSON formatting for production.
Supports both JSON and text output formats, rotation, and correlation IDs.
"""

import logging
import logging.handlers
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Any, Dict
import uuid


class JSONFormatter(logging.Formatter):
    """
    Custom JSON formatter for structured logging.
    Outputs log records as JSON objects for easy parsing by log aggregators.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add correlation ID if present
        if hasattr(record, "correlation_id"):
            log_data["correlation_id"] = record.correlation_id

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Extract token/cost metrics from record attributes
        # These fields are added via logger.info(..., extra={...})
        token_cost_fields = [
            # Token counts
            "prompt_tokens",
            "output_tokens",
            "cached_tokens",
            "billable_input_tokens",
            "total_tokens",
            # Cost metrics (USD)
            "cost_usd",  # Backward compatibility (WS2)
            "input_cost_usd",
            "output_cost_usd",
            "cache_cost_usd",
            "cache_savings_usd",
            "total_cost_usd",
            # Performance metrics
            "duration_ms",
            "throughput_pdfs_per_hour",
            # Processing context
            "pdf_path",
            "doc_id",
            "sha256_hex",
            "file_size_bytes",
            "stage",
            "status",
            "is_duplicate",
            "model",
            "encoding",
        ]

        for field in token_cost_fields:
            if hasattr(record, field):
                log_data[field] = getattr(record, field)

        # Add any extra fields (for extensibility)
        if hasattr(record, "extra"):
            log_data["extra"] = record.extra

        return json.dumps(log_data)


def setup_logging(
    log_level: str = "INFO",
    log_format: str = "json",
    log_file: str = "logs/paper_autopilot.log",
    max_bytes: int = 10485760,  # 10MB
    backup_count: int = 5,
) -> logging.Logger:
    """
    Configure logging for the application.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_format: Output format ('json' or 'text')
        log_file: Path to log file
        max_bytes: Maximum size of each log file before rotation
        backup_count: Number of backup files to keep

    Returns:
        Configured logger instance
    """
    # Create logs directory if it doesn't exist
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Create logger
    logger = logging.getLogger("paper_autopilot")
    logger.setLevel(getattr(logging, log_level.upper()))

    # Remove existing handlers
    logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)

    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(getattr(logging, log_level.upper()))

    # Choose formatter
    formatter: logging.Formatter
    if log_format == "json":
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


def get_correlation_id() -> str:
    """
    Generate a unique correlation ID for request tracking.
    Used to trace operations across multiple log entries.

    Returns:
        UUID string for correlation
    """
    return str(uuid.uuid4())


# Example usage
if __name__ == "__main__":
    logger = setup_logging(log_level="DEBUG", log_format="json")
    correlation_id = get_correlation_id()

    logger.info("Test log message", extra={"correlation_id": correlation_id})
    logger.debug(
        "Debug message",
        extra={"correlation_id": correlation_id, "extra": {"test": "data"}},
    )
    logger.warning("Warning message")

    try:
        raise ValueError("Test exception")
    except Exception:
        logger.error(
            "Error occurred", exc_info=True, extra={"correlation_id": correlation_id}
        )
