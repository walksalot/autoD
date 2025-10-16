"""Validation tests for test infrastructure.

This module validates that all test infrastructure components work correctly:
- Test utilities (PDF generation, metadata loading)
- Mock APIs (Responses, Files, Vector Stores)
- Error simulators
- Pytest fixtures

Run these tests first to ensure infrastructure is working before using it
in actual business logic tests.

Usage:
    pytest tests/test_infrastructure.py -v
"""

import pytest
import json
import hashlib
from pathlib import Path


# ==============================================================================
# Test Utilities Validation
# ==============================================================================

def test_create_test_pdf(sample_pdf):
    """Test PDF creation utility."""
    assert sample_pdf.exists()
    assert sample_pdf.suffix == ".pdf"
    assert sample_pdf.stat().st_size > 0

    # Verify it's a valid PDF structure
    content = sample_pdf.read_bytes()
    assert content.startswith(b"%PDF")
    assert b"%%EOF" in content


def test_create_test_pdf_deterministic(tmp_path):
    """Test that same content produces same hash."""
    from tests.utils import create_test_pdf

    pdf1 = create_test_pdf(content="test123", filename="test1.pdf", tmp_path=tmp_path)
    pdf2 = create_test_pdf(content="test123", filename="test2.pdf", tmp_path=tmp_path)

    hash1 = hashlib.sha256(pdf1.read_bytes()).hexdigest()
    hash2 = hashlib.sha256(pdf2.read_bytes()).hexdigest()

    assert hash1 == hash2, "Same content should produce same hash"


def test_load_metadata_fixture(invoice_metadata):
    """Test metadata fixture loading."""
    assert invoice_metadata["doc_type"] == "Invoice"
    assert invoice_metadata["issuer"] == "Acme Corporation"
    assert invoice_metadata["file_name"] == "acme-invoice-2024-01.pdf"
    assert invoice_metadata["primary_date"] == "2024-01-15"
    assert invoice_metadata["total_amount"] == 1250.00
    assert "summary" in invoice_metadata


def test_all_metadata_fixtures(
    invoice_metadata,
    receipt_metadata,
    utility_bill_metadata,
    bank_statement_metadata,
    unknown_metadata
):
    """Test that all metadata fixtures load correctly."""
    assert invoice_metadata["doc_type"] == "Invoice"
    assert receipt_metadata["doc_type"] == "Receipt"
    assert utility_bill_metadata["doc_type"] == "UtilityBill"
    assert bank_statement_metadata["doc_type"] == "BankStatement"
    assert unknown_metadata["doc_type"] == "Unknown"

    # Verify null handling in unknown doc_type
    assert unknown_metadata["issuer"] is None
    assert unknown_metadata["primary_date"] is None
    assert unknown_metadata["total_amount"] is None


def test_known_hashes(known_hashes, tmp_path):
    """Test known hash values for test content."""
    from tests.utils import create_test_pdf

    # Create PDF with "test" content
    test_pdf = create_test_pdf(content="test", tmp_path=tmp_path)
    test_hash = hashlib.sha256(test_pdf.read_bytes()).hexdigest()

    assert test_hash == known_hashes["test"]


# ==============================================================================
# Mock OpenAI Responses API Validation
# ==============================================================================

def test_mock_openai_basic(mock_openai_client):
    """Test basic mock OpenAI Responses API functionality."""
    response = mock_openai_client.responses.create(
        model="gpt-5",
        input=[{
            "role": "user",
            "content": [{"type": "input_text", "text": "Extract metadata"}]
        }]
    )

    # Validate response structure
    assert response.model == "gpt-5"
    assert response.usage.prompt_tokens > 0
    assert response.usage.output_tokens > 0
    assert response.usage.total_tokens == (
        response.usage.prompt_tokens + response.usage.output_tokens
    )

    # Validate output structure
    assert len(response.output) == 1
    assert response.output[0].role == "assistant"
    assert len(response.output[0].content) == 1
    assert response.output[0].content[0]["type"] == "output_text"

    # Validate metadata JSON
    metadata_text = response.output[0].content[0]["text"]
    metadata = json.loads(metadata_text)
    assert "doc_type" in metadata
    assert "file_name" in metadata


def test_mock_openai_doc_types(
    mock_openai_invoice,
    mock_openai_receipt,
    mock_openai_utility_bill,
    mock_openai_bank_statement,
    mock_openai_unknown
):
    """Test mock clients for different document types."""
    clients = [
        (mock_openai_invoice, "Invoice"),
        (mock_openai_receipt, "Receipt"),
        (mock_openai_utility_bill, "UtilityBill"),
        (mock_openai_bank_statement, "BankStatement"),
        (mock_openai_unknown, "Unknown")
    ]

    for client, expected_doc_type in clients:
        response = client.responses.create(model="gpt-5", input=[])
        metadata_text = response.output[0].content[0]["text"]
        metadata = json.loads(metadata_text)
        assert metadata["doc_type"] == expected_doc_type


def test_mock_openai_token_tracking():
    """Test custom token counts in mock responses."""
    from tests.mocks.mock_openai import create_mock_client_with_custom_tokens

    client = create_mock_client_with_custom_tokens(
        prompt_tokens=5000,
        output_tokens=1000,
        cached_tokens=500
    )

    response = client.responses.create(model="gpt-5", input=[])

    assert response.usage.prompt_tokens == 5000
    assert response.usage.output_tokens == 1000
    assert response.usage.prompt_tokens_details["cached_tokens"] == 500


# ==============================================================================
# Mock Files API Validation
# ==============================================================================

def test_mock_files_upload(mock_files_client, sample_pdf):
    """Test mock file upload functionality."""
    file_obj = mock_files_client.files.create(file=sample_pdf, purpose="assistants")

    assert file_obj.id.startswith("file-")
    assert file_obj.filename == "sample.pdf"
    assert file_obj.purpose == "assistants"
    assert file_obj.status == "processed"
    assert file_obj.bytes > 0


def test_mock_files_retrieve(mock_files_client, sample_pdf):
    """Test file retrieval by ID."""
    # Upload file
    uploaded = mock_files_client.files.create(file=sample_pdf)

    # Retrieve file
    retrieved = mock_files_client.files.retrieve(uploaded.id)

    assert retrieved.id == uploaded.id
    assert retrieved.filename == uploaded.filename
    assert retrieved.bytes == uploaded.bytes


def test_mock_files_delete(mock_files_client, sample_pdf):
    """Test file deletion."""
    # Upload file
    uploaded = mock_files_client.files.create(file=sample_pdf)

    # Delete file
    result = mock_files_client.files.delete(uploaded.id)

    assert result["deleted"] == True
    assert result["id"] == uploaded.id

    # Verify file is gone
    with pytest.raises(KeyError):
        mock_files_client.files.retrieve(uploaded.id)


def test_mock_files_list(mock_files_client, sample_pdf, tmp_path):
    """Test listing uploaded files."""
    from tests.utils import create_test_pdf

    # Upload multiple files
    pdf1 = create_test_pdf(content="file1", filename="file1.pdf", tmp_path=tmp_path)
    pdf2 = create_test_pdf(content="file2", filename="file2.pdf", tmp_path=tmp_path)

    mock_files_client.files.create(file=pdf1)
    mock_files_client.files.create(file=pdf2)

    # List files
    result = mock_files_client.files.list()

    assert result["object"] == "list"
    assert len(result["data"]) == 2


# ==============================================================================
# Mock Vector Store API Validation
# ==============================================================================

def test_mock_vector_store_create(mock_vector_store_client):
    """Test vector store creation."""
    vs = mock_vector_store_client.vector_stores.create(name="test-store")

    assert vs.id.startswith("vs-")
    assert vs.name == "test-store"
    assert vs.status == "completed"


def test_mock_vector_store_file_attach(mock_vector_store_client):
    """Test attaching files to vector store."""
    # Create vector store
    vs = mock_vector_store_client.vector_stores.create(name="test-store")

    # Attach file
    vs_file = mock_vector_store_client.vector_stores.files.create(
        vector_store_id=vs.id,
        file_id="file-123"
    )

    assert vs_file.id.startswith("vsfile-")
    assert vs_file.vector_store_id == vs.id
    assert vs_file.file_id == "file-123"
    assert vs_file.status == "completed"


def test_mock_vector_store_file_update(mock_vector_store_client):
    """Test updating file attributes in vector store."""
    # Create vector store and attach file
    vs = mock_vector_store_client.vector_stores.create(name="test-store")
    vs_file = mock_vector_store_client.vector_stores.files.create(
        vector_store_id=vs.id,
        file_id="file-123"
    )

    # Update attributes
    updated = mock_vector_store_client.vector_stores.files.update(
        vector_store_id=vs.id,
        file_id=vs_file.id,
        attributes={
            "sha256": "abc123",
            "doc_type": "Invoice",
            "filename": "test.pdf"
        }
    )

    assert updated.attributes is not None
    assert updated.attributes["sha256"] == "abc123"
    assert updated.attributes["doc_type"] == "Invoice"
    assert updated.attributes["filename"] == "test.pdf"


def test_mock_vector_store_attribute_limit(mock_vector_store_client):
    """Test that only 16 attributes are stored (OpenAI limit)."""
    vs = mock_vector_store_client.vector_stores.create(name="test-store")
    vs_file = mock_vector_store_client.vector_stores.files.create(
        vector_store_id=vs.id,
        file_id="file-123"
    )

    # Try to update with 20 attributes
    attrs = {f"attr_{i}": f"value_{i}" for i in range(20)}

    updated = mock_vector_store_client.vector_stores.files.update(
        vector_store_id=vs.id,
        file_id=vs_file.id,
        attributes=attrs
    )

    # Should only have 16 attributes
    assert len(updated.attributes) == 16


# ==============================================================================
# Error Simulator Validation
# ==============================================================================

def test_error_simulator_rate_limit():
    """Test rate limit error simulation."""
    from tests.mocks.error_simulator import simulate_rate_limit, RateLimitError

    with pytest.raises(RateLimitError) as exc_info:
        simulate_rate_limit()

    assert exc_info.value.status_code == 429


def test_error_simulator_timeout():
    """Test timeout error simulation."""
    from tests.mocks.error_simulator import simulate_timeout, Timeout

    with pytest.raises(Timeout):
        simulate_timeout()


def test_error_simulator_api_error():
    """Test API error with custom status code."""
    from tests.mocks.error_simulator import simulate_api_error, APIError

    with pytest.raises(APIError) as exc_info:
        simulate_api_error(503)

    assert exc_info.value.status_code == 503


def test_error_after_n_calls():
    """Test ErrorAfterNCalls helper."""
    from tests.mocks.error_simulator import ErrorAfterNCalls, simulate_rate_limit, RateLimitError

    counter = ErrorAfterNCalls(2, lambda: simulate_rate_limit())

    # First two calls should raise
    with pytest.raises(RateLimitError):
        counter()

    with pytest.raises(RateLimitError):
        counter()

    # Third call should succeed
    counter()  # No exception
    counter()  # Still no exception


def test_mock_client_with_errors():
    """Test mock client configured to raise errors."""
    from tests.mocks.mock_openai import create_mock_client_with_errors
    from tests.mocks.error_simulator import simulate_rate_limit, RateLimitError

    client = create_mock_client_with_errors(simulate_rate_limit)

    with pytest.raises(RateLimitError):
        client.responses.create(model="gpt-5", input=[])


# ==============================================================================
# Database Fixtures Validation
# ==============================================================================

def test_db_session_fixture(db_session):
    """Test in-memory database session."""
    # Import model - note: this will fail until src/models.py exists
    # For now, just verify session exists
    assert db_session is not None


def test_db_session_isolation(db_session):
    """Test that database sessions are isolated between tests."""
    # This test should have a fresh, empty database
    # If models were defined, we'd verify no existing records
    assert db_session is not None


# ==============================================================================
# Combined API Fixtures Validation
# ==============================================================================

def test_mock_all_apis_fixture(mock_all_apis, sample_pdf):
    """Test combined API fixture with all services."""
    # Test Responses API
    response = mock_all_apis["responses"].responses.create(model="gpt-5", input=[])
    assert response.model == "gpt-5"

    # Test Files API
    file_obj = mock_all_apis["files"].files.create(file=sample_pdf)
    assert file_obj.id.startswith("file-")

    # Test Vector Stores API
    vs = mock_all_apis["vector_stores"].vector_stores.create(name="test")
    assert vs.id.startswith("vs-")


# ==============================================================================
# Fixture Isolation Tests
# ==============================================================================

def test_fixture_isolation_sample_pdf_1(sample_pdf):
    """First test using sample_pdf fixture."""
    assert sample_pdf.name == "sample.pdf"


def test_fixture_isolation_sample_pdf_2(sample_pdf):
    """Second test using sample_pdf - should get fresh PDF."""
    # If fixtures are properly isolated, this should be a new file
    assert sample_pdf.name == "sample.pdf"
    assert sample_pdf.exists()


# ==============================================================================
# Test Infrastructure Summary
# ==============================================================================

def test_infrastructure_summary():
    """Summary test to verify all components are importable."""
    # Test utilities
    from tests.utils import create_test_pdf, load_metadata_fixture, assert_document_equal

    # Mocks
    from tests.mocks.mock_openai import MockResponsesClient
    from tests.mocks.mock_files_api import MockFilesClient
    from tests.mocks.mock_vector_store import MockVectorStoreClient
    from tests.mocks.error_simulator import simulate_rate_limit

    # All imports successful
    assert True, "All test infrastructure components are importable"
