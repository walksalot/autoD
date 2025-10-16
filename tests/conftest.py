"""Pytest configuration and fixtures for autoD test suite.

This module provides pytest fixtures for:
- Database sessions (in-memory SQLite for fast, isolated tests)
- Mock OpenAI clients (Responses API, Files API, Vector Stores)
- Test PDF generation
- Metadata fixtures
- Error simulation

All fixtures support parallel test execution (pytest -n auto).

Example usage in tests:
    def test_document_creation(db_session, sample_pdf):
        # db_session: SQLAlchemy session with fresh in-memory database
        # sample_pdf: Path to generated test PDF file
        doc = Document(sha256_hex="abc123", original_filename=sample_pdf.name)
        db_session.add(doc)
        db_session.commit()
        assert doc.id is not None
"""

import pytest
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from typing import Generator

# Import test utilities
from tests.utils import create_test_pdf, load_metadata_fixture

# Import mocks
from tests.mocks.mock_openai import MockResponsesClient, create_mock_client_with_doc_type
from tests.mocks.mock_files_api import MockFilesClient
from tests.mocks.mock_vector_store import MockVectorStoreClient


# ==============================================================================
# Database Fixtures
# ==============================================================================

@pytest.fixture
def db_session() -> Generator:
    """Create in-memory SQLite session for testing.

    Each test gets a fresh database with no state carryover.
    This fixture supports parallel test execution.

    Yields:
        SQLAlchemy session with all tables created

    Example:
        def test_document_query(db_session):
            from src.models import Document
            doc = Document(sha256_hex="abc123", original_filename="test.pdf")
            db_session.add(doc)
            db_session.commit()

            # Query back
            found = db_session.query(Document).filter_by(sha256_hex="abc123").first()
            assert found is not None
    """
    # Import models here to avoid circular dependencies
    from src.models import Base

    # Create in-memory SQLite database
    engine = create_engine("sqlite:///:memory:", future=True, echo=False)

    # Create all tables
    Base.metadata.create_all(engine)

    # Create session
    Session = sessionmaker(bind=engine)
    session = Session()

    yield session

    # Cleanup
    session.close()
    engine.dispose()


# ==============================================================================
# PDF Generation Fixtures
# ==============================================================================

@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    """Create a minimal valid PDF file for testing.

    Args:
        tmp_path: Pytest's temporary directory fixture

    Returns:
        Path to generated PDF file

    Example:
        def test_pdf_processing(sample_pdf):
            assert sample_pdf.exists()
            assert sample_pdf.suffix == ".pdf"
            assert sample_pdf.stat().st_size > 0
    """
    return create_test_pdf(content="test", filename="sample.pdf", tmp_path=tmp_path)


@pytest.fixture
def invoice_pdf(tmp_path: Path) -> Path:
    """Create a test PDF with 'invoice' content for deterministic hashing.

    Returns:
        Path to invoice PDF file

    Example:
        def test_invoice_processing(invoice_pdf):
            # This PDF will always have the same hash
            from tests.utils import KNOWN_HASHES
            import hashlib
            with open(invoice_pdf, "rb") as f:
                actual_hash = hashlib.sha256(f.read()).hexdigest()
            assert actual_hash == KNOWN_HASHES["invoice"]
    """
    return create_test_pdf(content="invoice", filename="invoice.pdf", tmp_path=tmp_path)


@pytest.fixture
def receipt_pdf(tmp_path: Path) -> Path:
    """Create a test PDF with 'receipt' content for deterministic hashing.

    Returns:
        Path to receipt PDF file
    """
    return create_test_pdf(content="receipt", filename="receipt.pdf", tmp_path=tmp_path)


@pytest.fixture
def temp_inbox(tmp_path: Path) -> Path:
    """Create a temporary inbox directory for testing.

    Returns:
        Path to temporary inbox directory

    Example:
        def test_inbox_processing(temp_inbox, sample_pdf):
            # Copy PDF to inbox
            import shutil
            shutil.copy(sample_pdf, temp_inbox / "doc.pdf")

            # Process inbox
            pdfs = list(temp_inbox.glob("*.pdf"))
            assert len(pdfs) == 1
    """
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    return inbox


# ==============================================================================
# Mock OpenAI Client Fixtures
# ==============================================================================

@pytest.fixture
def mock_openai_client() -> MockResponsesClient:
    """Create a mock OpenAI client with Responses API.

    Returns realistic responses for invoice documents by default.

    Returns:
        MockResponsesClient instance

    Example:
        def test_api_call(mock_openai_client):
            response = mock_openai_client.responses.create(
                model="gpt-5",
                input=[{"role": "user", "content": [{"type": "input_text", "text": "Extract"}]}]
            )
            assert response.usage.prompt_tokens > 0
            assert response.output[0].role == "assistant"
    """
    return MockResponsesClient(default_doc_type="invoice")


@pytest.fixture
def mock_openai_invoice() -> MockResponsesClient:
    """Mock OpenAI client that returns Invoice metadata."""
    return create_mock_client_with_doc_type("invoice")


@pytest.fixture
def mock_openai_receipt() -> MockResponsesClient:
    """Mock OpenAI client that returns Receipt metadata."""
    return create_mock_client_with_doc_type("receipt")


@pytest.fixture
def mock_openai_utility_bill() -> MockResponsesClient:
    """Mock OpenAI client that returns UtilityBill metadata."""
    return create_mock_client_with_doc_type("utility_bill")


@pytest.fixture
def mock_openai_bank_statement() -> MockResponsesClient:
    """Mock OpenAI client that returns BankStatement metadata."""
    return create_mock_client_with_doc_type("bank_statement")


@pytest.fixture
def mock_openai_unknown() -> MockResponsesClient:
    """Mock OpenAI client that returns Unknown doc_type."""
    return create_mock_client_with_doc_type("unknown")


@pytest.fixture
def mock_files_client() -> MockFilesClient:
    """Create a mock OpenAI Files API client.

    Returns:
        MockFilesClient instance

    Example:
        def test_file_upload(mock_files_client, sample_pdf):
            file_obj = mock_files_client.files.create(file=sample_pdf, purpose="assistants")
            assert file_obj.id.startswith("file-")
            assert file_obj.filename == "sample.pdf"

            # Retrieve file
            retrieved = mock_files_client.files.retrieve(file_obj.id)
            assert retrieved.id == file_obj.id
    """
    return MockFilesClient()


@pytest.fixture
def mock_vector_store_client() -> MockVectorStoreClient:
    """Create a mock OpenAI Vector Stores API client.

    Returns:
        MockVectorStoreClient instance

    Example:
        def test_vector_store(mock_vector_store_client):
            # Create vector store
            vs = mock_vector_store_client.vector_stores.create(name="test-store")
            assert vs.id.startswith("vs-")

            # Attach file
            vs_file = mock_vector_store_client.vector_stores.files.create(
                vector_store_id=vs.id,
                file_id="file-123"
            )
            assert vs_file.file_id == "file-123"
    """
    return MockVectorStoreClient()


# ==============================================================================
# Metadata Fixture Loaders
# ==============================================================================

@pytest.fixture
def invoice_metadata() -> dict:
    """Load expected invoice metadata from fixture.

    Returns:
        Dictionary with invoice metadata structure

    Example:
        def test_invoice_metadata(invoice_metadata):
            assert invoice_metadata["doc_type"] == "Invoice"
            assert invoice_metadata["issuer"] == "Acme Corporation"
            assert invoice_metadata["total_amount"] == 1250.00
    """
    return load_metadata_fixture("invoice")


@pytest.fixture
def receipt_metadata() -> dict:
    """Load expected receipt metadata from fixture."""
    return load_metadata_fixture("receipt")


@pytest.fixture
def utility_bill_metadata() -> dict:
    """Load expected utility bill metadata from fixture."""
    return load_metadata_fixture("utility_bill")


@pytest.fixture
def bank_statement_metadata() -> dict:
    """Load expected bank statement metadata from fixture."""
    return load_metadata_fixture("bank_statement")


@pytest.fixture
def unknown_metadata() -> dict:
    """Load expected unknown doc_type metadata from fixture."""
    return load_metadata_fixture("unknown")


# ==============================================================================
# Known Hash Fixtures
# ==============================================================================

@pytest.fixture
def known_hashes() -> dict:
    """Get dictionary of known SHA-256 hashes for test content.

    Returns:
        Dictionary mapping content strings to their SHA-256 hashes

    Example:
        def test_hash_consistency(known_hashes, sample_pdf):
            import hashlib
            with open(sample_pdf, "rb") as f:
                actual = hashlib.sha256(f.read()).hexdigest()
            # sample_pdf uses "test" content
            assert actual == known_hashes["test"]
    """
    from tests.utils import KNOWN_HASHES
    return KNOWN_HASHES


# ==============================================================================
# Combined Mock Client Fixture
# ==============================================================================

@pytest.fixture
def mock_all_apis():
    """Combined fixture with all mock API clients.

    Returns:
        Dictionary with all mock clients

    Example:
        def test_full_pipeline(mock_all_apis, sample_pdf):
            # Upload file
            file_obj = mock_all_apis["files"].files.create(file=sample_pdf)

            # Call Responses API
            response = mock_all_apis["responses"].responses.create(
                model="gpt-5",
                input=[...]
            )

            # Create vector store
            vs = mock_all_apis["vector_stores"].vector_stores.create(name="test")
    """
    return {
        "responses": MockResponsesClient(default_doc_type="invoice"),
        "files": MockFilesClient(),
        "vector_stores": MockVectorStoreClient()
    }


# ==============================================================================
# Pytest Configuration
# ==============================================================================

def pytest_configure(config):
    """Configure pytest with custom markers.

    Markers:
        - slow: Mark test as slow-running
        - integration: Mark test as integration test
        - unit: Mark test as unit test
    """
    config.addinivalue_line("markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "unit: marks tests as unit tests")
