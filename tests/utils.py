"""Test utilities for autoD Paper Autopilot test suite.

This module provides helper functions for:
- Generating test PDF files
- Comparing database records
- Loading test fixtures
- Capturing logs for assertions

Example usage:
    from tests.utils import create_test_pdf, load_metadata_fixture

    # Create a test PDF with custom content
    pdf_path = create_test_pdf(content="test data", filename="test.pdf")

    # Load expected metadata
    expected = load_metadata_fixture("invoice")
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from contextlib import contextmanager
from io import StringIO


def create_test_pdf(
    content: str = "test", filename: str = "test.pdf", tmp_path: Optional[Path] = None
) -> Path:
    """Generate a minimal valid PDF file for testing.

    Creates a basic PDF structure that can be read by PDF processors.
    The PDF is deterministic for a given content string, so the same
    content always produces the same SHA-256 hash.

    Args:
        content: Text content to include in the PDF (used in hash calculation)
        filename: Name of the PDF file to create
        tmp_path: Optional temporary directory path. If None, creates in current dir.

    Returns:
        Path object pointing to the created PDF file

    Example:
        >>> pdf_path = create_test_pdf(content="invoice data", filename="invoice.pdf")
        >>> assert pdf_path.exists()
        >>> assert pdf_path.name == "invoice.pdf"
    """
    if tmp_path is None:
        tmp_path = Path(".")

    pdf_path = tmp_path / filename

    # Minimal valid PDF structure with embedded content for unique hashing
    # This structure is recognized by most PDF parsers
    pdf_content = f"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /Resources << >> /MediaBox [0 0 612 792] >>
endobj
%% Embedded test content: {content}
%%EOF
""".encode(
        "utf-8"
    )

    pdf_path.write_bytes(pdf_content)
    return pdf_path


def load_metadata_fixture(doc_type: str) -> Dict[str, Any]:
    """Load expected metadata JSON fixture for a document type.

    Fixtures are stored in tests/fixtures/metadata/ directory.

    Args:
        doc_type: Document type (invoice, receipt, utility_bill, bank_statement, unknown)

    Returns:
        Dictionary containing expected metadata structure

    Raises:
        FileNotFoundError: If fixture file doesn't exist
        json.JSONDecodeError: If fixture file contains invalid JSON

    Example:
        >>> metadata = load_metadata_fixture("invoice")
        >>> assert metadata["doc_type"] == "Invoice"
        >>> assert "total_amount" in metadata
    """
    fixture_path = Path(__file__).parent / "fixtures" / "metadata" / f"{doc_type}.json"

    if not fixture_path.exists():
        raise FileNotFoundError(
            f"Metadata fixture not found: {fixture_path}\n"
            f"Available fixtures: invoice, receipt, utility_bill, bank_statement, unknown"
        )

    with open(fixture_path, "r") as f:
        return json.load(f)


def assert_document_equal(actual: Any, expected: Dict[str, Any]) -> None:
    """Assert that a Document database record matches expected values.

    Compares selected fields from a SQLAlchemy Document object against
    expected values. Provides clear assertion messages on mismatch.

    Args:
        actual: Document database object (SQLAlchemy model)
        expected: Dictionary of expected field values

    Raises:
        AssertionError: If any field doesn't match expected value

    Example:
        >>> from src.models import Document
        >>> doc = Document(sha256_hex="abc123", original_filename="test.pdf")
        >>> assert_document_equal(doc, {
        ...     "sha256_hex": "abc123",
        ...     "original_filename": "test.pdf",
        ...     "status": "pending"
        ... })
    """
    for field, expected_value in expected.items():
        actual_value = getattr(actual, field, None)

        assert actual_value == expected_value, (
            f"Field '{field}' mismatch:\n"
            f"  Expected: {expected_value!r}\n"
            f"  Actual:   {actual_value!r}"
        )


@contextmanager
def capture_logs(logger_name: str = "autod", level: int = logging.INFO):
    """Context manager to capture log output for assertions.

    Temporarily adds a StringIO handler to the specified logger,
    allowing tests to assert on log messages.

    Args:
        logger_name: Name of logger to capture (default: "autod")
        level: Minimum log level to capture (default: INFO)

    Yields:
        StringIO object containing captured log output

    Example:
        >>> with capture_logs() as log_output:
        ...     logger.info("Processing PDF", extra={"pdf_path": "/tmp/test.pdf"})
        ...     logs = log_output.getvalue()
        ...     assert "Processing PDF" in logs
        ...     assert "/tmp/test.pdf" in logs
    """
    logger = logging.getLogger(logger_name)
    original_level = logger.level
    log_capture = StringIO()
    handler = logging.StreamHandler(log_capture)
    handler.setLevel(level)

    # Add handler and set level
    logger.addHandler(handler)
    logger.setLevel(level)

    try:
        yield log_capture
    finally:
        # Clean up
        logger.removeHandler(handler)
        logger.setLevel(original_level)


def get_known_hash(content: str) -> str:
    """Get the SHA-256 hash for a known test content string.

    This is useful for tests that need to assert on specific hash values
    without computing them dynamically.

    Args:
        content: Test content string

    Returns:
        SHA-256 hash in hexadecimal format (64 characters)

    Example:
        >>> hash_value = get_known_hash("test")
        >>> assert len(hash_value) == 64
        >>> # Same content always produces same hash
        >>> assert get_known_hash("test") == get_known_hash("test")
    """
    import hashlib

    # Create test PDF content
    pdf_content = f"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /Resources << >> /MediaBox [0 0 612 792] >>
endobj
%% Embedded test content: {content}
%%EOF
""".encode(
        "utf-8"
    )

    return hashlib.sha256(pdf_content).hexdigest()


# Pre-computed known hashes for common test content
KNOWN_HASHES = {
    "test": get_known_hash("test"),
    "invoice": get_known_hash("invoice"),
    "receipt": get_known_hash("receipt"),
    "duplicate": get_known_hash("duplicate"),
}
