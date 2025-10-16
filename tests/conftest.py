"""
Pytest configuration and shared fixtures for testing.

Provides:
- Database fixtures (in-memory SQLite)
- OpenAI client mocks
- Sample PDF fixtures
- ProcessingContext fixtures
"""

import pytest
import tempfile
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from unittest.mock import Mock, MagicMock
from datetime import datetime, timezone

from src.models import Base, Document
from src.pipeline import ProcessingContext


@pytest.fixture
def test_db_engine():
    """
    Create in-memory SQLite engine for testing.

    Returns:
        SQLAlchemy engine with tables created
    """
    engine = create_engine("sqlite:///:memory:", future=True, echo=False)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def test_db_session(test_db_engine):
    """
    Create database session for testing.

    Each test gets a fresh session that's rolled back after the test.

    Yields:
        SQLAlchemy session
    """
    SessionLocal = sessionmaker(bind=test_db_engine, future=True)
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def sample_pdf_bytes():
    """
    Minimal valid PDF file as bytes.

    Returns:
        bytes: Smallest possible valid PDF (40 bytes)
    """
    # Minimal PDF that passes PDF validation
    # Header + body + xref + trailer + startxref + EOF
    return b"%PDF-1.0\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj 3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj\nxref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000117 00000 n\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n220\n%%EOF"


@pytest.fixture
def sample_pdf_path(tmp_path, sample_pdf_bytes):
    """
    Create temporary PDF file for testing.

    Args:
        tmp_path: Pytest tmp_path fixture
        sample_pdf_bytes: PDF content fixture

    Returns:
        Path: Path to temporary PDF file
    """
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(sample_pdf_bytes)
    return pdf_path


@pytest.fixture
def sample_sha256_hex(sample_pdf_bytes):
    """
    Compute SHA-256 hex for sample PDF.

    Returns:
        str: 64-character hex string
    """
    import hashlib
    return hashlib.sha256(sample_pdf_bytes).hexdigest()


@pytest.fixture
def sample_sha256_base64(sample_pdf_bytes):
    """
    Compute SHA-256 base64 for sample PDF.

    Returns:
        str: 44-character base64 string
    """
    import hashlib
    import base64
    digest = hashlib.sha256(sample_pdf_bytes).digest()
    return base64.b64encode(digest).decode("ascii")


@pytest.fixture
def empty_context(sample_pdf_path):
    """
    Create empty ProcessingContext for testing.

    Returns:
        ProcessingContext: Context with only pdf_path set
    """
    return ProcessingContext(pdf_path=sample_pdf_path)


@pytest.fixture
def context_with_hash(sample_pdf_path, sample_pdf_bytes, sample_sha256_hex, sample_sha256_base64):
    """
    Create ProcessingContext with SHA-256 hash computed.

    Returns:
        ProcessingContext: Context with pdf_bytes and hashes set
    """
    return ProcessingContext(
        pdf_path=sample_pdf_path,
        pdf_bytes=sample_pdf_bytes,
        sha256_hex=sample_sha256_hex,
        sha256_base64=sample_sha256_base64,
        metrics={"file_size_bytes": len(sample_pdf_bytes)},
    )


@pytest.fixture
def mock_openai_client():
    """
    Create mock OpenAI client for testing API interactions.

    Returns:
        Mock: OpenAI client with mocked files.create() and responses.create()
    """
    client = Mock()

    # Mock Files API response
    file_response = Mock()
    file_response.id = "file-test123abc"
    client.files.create.return_value = file_response

    # Mock Responses API response
    response_mock = Mock()
    response_mock.output = [
        Mock(
            content=[
                Mock(
                    text='{"file_name": "sample.pdf", "doc_type": "Invoice", "issuer": "ACME Corp", "primary_date": "2024-01-15", "total_amount": 1250.00, "summary": "Test invoice for validation"}'
                )
            ]
        )
    ]
    response_mock.model_dump.return_value = {
        "id": "resp_test456def",
        "model": "gpt-5-mini",
        "output": [
            {
                "content": [
                    {
                        "type": "text",
                        "text": '{"file_name": "sample.pdf", "doc_type": "Invoice", "issuer": "ACME Corp", "primary_date": "2024-01-15", "total_amount": 1250.00, "summary": "Test invoice for validation"}',
                    }
                ]
            }
        ],
    }
    client.responses.create.return_value = response_mock

    return client


@pytest.fixture
def existing_document(test_db_session, sample_sha256_hex):
    """
    Create existing document in database for deduplication testing.

    Returns:
        Document: Pre-existing document with same SHA-256 hash
    """
    doc = Document(
        sha256_hex=sample_sha256_hex,
        original_filename="existing.pdf",
        created_at=datetime.now(timezone.utc),
        processed_at=datetime.now(timezone.utc),
        source_file_id="file-existing123",
        metadata_json={"doc_type": "Invoice"},
        status="completed",
    )
    test_db_session.add(doc)
    test_db_session.commit()
    return doc


@pytest.fixture
def sample_metadata_json():
    """
    Sample metadata JSON response from API.

    Returns:
        dict: Structured metadata matching extraction schema
    """
    return {
        "file_name": "sample.pdf",
        "doc_type": "Invoice",
        "issuer": "ACME Corp",
        "primary_date": "2024-01-15",
        "total_amount": 1250.00,
        "summary": "Test invoice for validation",
    }
