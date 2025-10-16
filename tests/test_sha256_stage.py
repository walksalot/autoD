"""
Tests for ComputeSHA256Stage.

Validates:
- SHA-256 hash computation (hex and base64 formats)
- PDF file reading
- Metrics collection (file size)
- Idempotency (rerunning doesn't change hash)
- Error handling (missing files, empty files)
"""

import pytest
from pathlib import Path
from src.stages.sha256_stage import ComputeSHA256Stage
from src.pipeline import ProcessingContext


def test_compute_sha256_from_file(
    empty_context, sample_pdf_bytes, sample_sha256_hex, sample_sha256_base64
):
    """
    Test SHA-256 computation from PDF file on disk.

    Validates that stage reads file and computes correct hex and base64 hashes.
    """
    stage = ComputeSHA256Stage()

    result = stage.execute(empty_context)

    # Verify hashes match expected values
    assert result.sha256_hex == sample_sha256_hex
    assert result.sha256_base64 == sample_sha256_base64

    # Verify pdf_bytes was populated
    assert result.pdf_bytes == sample_pdf_bytes

    # Verify metrics
    assert result.metrics["file_size_bytes"] == len(sample_pdf_bytes)


def test_compute_sha256_with_existing_bytes(
    context_with_hash, sample_sha256_hex, sample_sha256_base64
):
    """
    Test SHA-256 computation when pdf_bytes already set.

    Stage should NOT re-read file if bytes are already in context.
    """
    stage = ComputeSHA256Stage()

    # Context already has pdf_bytes set
    result = stage.execute(context_with_hash)

    # Should compute same hashes
    assert result.sha256_hex == sample_sha256_hex
    assert result.sha256_base64 == sample_sha256_base64


def test_sha256_hex_format(empty_context):
    """
    Test SHA-256 hex format is valid.

    Hex should be 64 characters (256 bits / 4 bits per hex char).
    """
    stage = ComputeSHA256Stage()
    result = stage.execute(empty_context)

    assert len(result.sha256_hex) == 64
    assert all(c in "0123456789abcdef" for c in result.sha256_hex)


def test_sha256_base64_format(empty_context):
    """
    Test SHA-256 base64 format is valid.

    Base64 should be 44 characters (256 bits / 6 bits per char + padding).
    """
    stage = ComputeSHA256Stage()
    result = stage.execute(empty_context)

    assert len(result.sha256_base64) == 44
    # Base64 alphabet: A-Z, a-z, 0-9, +, /, =
    import string

    valid_chars = string.ascii_letters + string.digits + "+/="
    assert all(c in valid_chars for c in result.sha256_base64)


def test_sha256_idempotency(empty_context):
    """
    Test running stage twice produces same hash.

    Verifies SHA-256 computation is deterministic.
    """
    stage = ComputeSHA256Stage()

    result1 = stage.execute(empty_context)
    result2 = stage.execute(result1)  # Run again on same context

    assert result1.sha256_hex == result2.sha256_hex
    assert result1.sha256_base64 == result2.sha256_base64


def test_different_files_produce_different_hashes(tmp_path):
    """
    Test different PDF files produce different SHA-256 hashes.

    Validates hash collision resistance (different inputs → different outputs).
    """
    stage = ComputeSHA256Stage()

    # Create two different PDFs
    pdf1_path = tmp_path / "file1.pdf"
    pdf1_path.write_bytes(b"%PDF-1.0\nContent A")

    pdf2_path = tmp_path / "file2.pdf"
    pdf2_path.write_bytes(b"%PDF-1.0\nContent B")

    context1 = ProcessingContext(pdf_path=pdf1_path)
    context2 = ProcessingContext(pdf_path=pdf2_path)

    result1 = stage.execute(context1)
    result2 = stage.execute(context2)

    assert result1.sha256_hex != result2.sha256_hex
    assert result1.sha256_base64 != result2.sha256_base64


def test_empty_file_produces_valid_hash(tmp_path):
    """
    Test empty file produces valid SHA-256 hash.

    Empty PDF (0 bytes) should still compute a hash (hash of empty string).
    """
    stage = ComputeSHA256Stage()

    empty_pdf = tmp_path / "empty.pdf"
    empty_pdf.write_bytes(b"")

    context = ProcessingContext(pdf_path=empty_pdf)
    result = stage.execute(context)

    # SHA-256 of empty string is e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
    assert (
        result.sha256_hex
        == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )
    assert result.metrics["file_size_bytes"] == 0


def test_missing_file_raises_error(tmp_path):
    """
    Test missing file raises FileNotFoundError.

    Stage should fail fast if PDF doesn't exist.
    """
    stage = ComputeSHA256Stage()

    missing_path = tmp_path / "nonexistent.pdf"
    context = ProcessingContext(pdf_path=missing_path)

    with pytest.raises(FileNotFoundError):
        stage.execute(context)


def test_large_file_hash(tmp_path):
    """
    Test SHA-256 computation for larger files.

    Validates stage can handle files beyond minimal test fixtures.
    """
    stage = ComputeSHA256Stage()

    # Create 1MB file with repeated pattern
    large_pdf = tmp_path / "large.pdf"
    content = b"%PDF-1.0\n" + b"X" * (1024 * 1024)  # ~1MB
    large_pdf.write_bytes(content)

    context = ProcessingContext(pdf_path=large_pdf)
    result = stage.execute(context)

    # Verify hash is computed
    assert len(result.sha256_hex) == 64
    assert len(result.sha256_base64) == 44
    assert result.metrics["file_size_bytes"] == len(content)


def test_metrics_populated(empty_context):
    """
    Test metrics dictionary is populated with file size.

    Validates stage adds file_size_bytes to context.metrics.
    """
    stage = ComputeSHA256Stage()
    result = stage.execute(empty_context)

    assert "file_size_bytes" in result.metrics
    assert isinstance(result.metrics["file_size_bytes"], int)
    assert result.metrics["file_size_bytes"] > 0


def test_hash_matches_known_value():
    """
    Test SHA-256 hash matches known value for specific input.

    Validates correctness against reference implementation.
    """
    import hashlib
    import base64

    stage = ComputeSHA256Stage()

    # Create context with known bytes
    known_bytes = b"test content"
    expected_hex = hashlib.sha256(known_bytes).hexdigest()
    expected_base64 = base64.b64encode(hashlib.sha256(known_bytes).digest()).decode(
        "ascii"
    )

    context = ProcessingContext(
        pdf_path=Path("test.pdf"),  # Path doesn't matter since bytes are set
        pdf_bytes=known_bytes,
    )

    result = stage.execute(context)

    assert result.sha256_hex == expected_hex
    assert result.sha256_base64 == expected_base64
