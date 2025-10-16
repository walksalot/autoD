# Test Infrastructure Documentation

**Version**: 1.0
**Status**: ✅ Complete (All 27 validation tests passing)
**Workstream**: Testing Infrastructure (Workstream 4)

---

## Overview

This test infrastructure provides a complete, production-ready testing framework for the autoD Paper Autopilot system. It includes:

- **Mock OpenAI APIs** - Realistic simulations of Responses API, Files API, and Vector Stores API
- **Test Utilities** - PDF generation, metadata loading, assertion helpers
- **Error Simulators** - Comprehensive error injection for testing retry logic
- **Pytest Fixtures** - All infrastructure available as pytest fixtures
- **Metadata Fixtures** - JSON templates for all document types

## Quick Start

### Running Tests

```bash
# Run all infrastructure validation tests
pytest tests/test_infrastructure.py -v

# Run tests with coverage
pytest tests/ --cov=src --cov-report=html

# Run tests in parallel (after installing pytest-xdist)
pytest tests/ -n auto

# Run only unit tests
pytest tests/ -m unit

# Run excluding slow tests
pytest tests/ -m "not slow"
```

### Using Fixtures in Tests

```python
def test_document_processing(db_session, sample_pdf, mock_openai_client):
    """Example test using multiple fixtures."""
    from src.models import Document
    import hashlib

    # Read PDF and compute hash
    pdf_bytes = sample_pdf.read_bytes()
    sha_hex = hashlib.sha256(pdf_bytes).hexdigest()

    # Create database record
    doc = Document(sha256_hex=sha_hex, original_filename=sample_pdf.name)
    db_session.add(doc)
    db_session.commit()

    # Call mock OpenAI API
    response = mock_openai_client.responses.create(
        model="gpt-5",
        input=[{
            "role": "user",
            "content": [{"type": "input_text", "text": "Extract metadata"}]
        }]
    )

    # Verify response structure
    assert response.usage.prompt_tokens > 0
    assert doc.id is not None
```

---

## Component Reference

### 1. Test Utilities (`tests/utils.py`)

#### PDF Generation

```python
from tests.utils import create_test_pdf, KNOWN_HASHES

# Create a test PDF
pdf_path = create_test_pdf(content="test", filename="doc.pdf", tmp_path=tmp_path)

# Get known hash for test content
hash_value = KNOWN_HASHES["test"]
```

#### Metadata Loading

```python
from tests.utils import load_metadata_fixture

# Load expected metadata for a document type
invoice_metadata = load_metadata_fixture("invoice")
assert invoice_metadata["doc_type"] == "Invoice"
assert invoice_metadata["issuer"] == "Acme Corporation"
```

#### Assertions

```python
from tests.utils import assert_document_equal

# Compare Document against expected values
assert_document_equal(doc, {
    "sha256_hex": "abc123...",
    "original_filename": "test.pdf",
    "status": "completed"
})
```

#### Log Capture

```python
from tests.utils import capture_logs

with capture_logs() as log_output:
    logger.info("Processing PDF", extra={"pdf_path": "/tmp/test.pdf"})
    logs = log_output.getvalue()
    assert "Processing PDF" in logs
    assert "/tmp/test.pdf" in logs
```

---

### 2. Mock OpenAI Responses API (`tests/mocks/mock_openai.py`)

#### Basic Usage

```python
from tests.mocks.mock_openai import MockResponsesClient

client = MockResponsesClient(default_doc_type="invoice")
response = client.responses.create(model="gpt-5", input=[...])

# Response structure matches real API
assert response.usage.prompt_tokens > 0
assert response.output[0].role == "assistant"
```

#### Document Types

```python
from tests.mocks.mock_openai import create_mock_client_with_doc_type

# Create client for specific document type
receipt_client = create_mock_client_with_doc_type("receipt")
response = receipt_client.responses.create(model="gpt-5", input=[...])

# Parse metadata
import json
metadata_text = response.output[0].content[0]["text"]
metadata = json.loads(metadata_text)
assert metadata["doc_type"] == "Receipt"
```

#### Custom Token Counts (for cost testing)

```python
from tests.mocks.mock_openai import create_mock_client_with_custom_tokens

# Test high-cost scenario
client = create_mock_client_with_custom_tokens(
    prompt_tokens=50000,
    output_tokens=10000,
    cached_tokens=5000
)

response = client.responses.create(model="gpt-5", input=[...])
assert response.usage.prompt_tokens == 50000
assert response.usage.cached_tokens == 5000
```

---

### 3. Mock Files API (`tests/mocks/mock_files_api.py`)

```python
from tests.mocks.mock_files_api import MockFilesClient

client = MockFilesClient()

# Upload file
file_obj = client.files.create(file=pdf_path, purpose="assistants")
assert file_obj.id.startswith("file-")

# Retrieve file metadata
retrieved = client.files.retrieve(file_obj.id)
assert retrieved.filename == "test.pdf"

# Delete file
result = client.files.delete(file_obj.id)
assert result["deleted"] == True

# List all files
files = client.files.list()
assert len(files["data"]) > 0
```

---

### 4. Mock Vector Store API (`tests/mocks/mock_vector_store.py`)

```python
from tests.mocks.mock_vector_store import MockVectorStoreClient

client = MockVectorStoreClient()

# Create vector store
vs = client.vector_stores.create(name="paper-autopilot-docs")
assert vs.id.startswith("vs-")

# Attach file to vector store
vs_file = client.vector_stores.files.create(
    vector_store_id=vs.id,
    file_id="file-123"
)

# Update file attributes (max 16 key-value pairs)
updated = client.vector_stores.files.update(
    vector_store_id=vs.id,
    file_id=vs_file.id,
    attributes={
        "sha256": "abc123",
        "doc_type": "Invoice",
        "filename": "invoice.pdf"
    }
)
assert updated.attributes["doc_type"] == "Invoice"
```

---

### 5. Error Simulators (`tests/mocks/error_simulator.py`)

#### Basic Error Simulation

```python
from tests.mocks.error_simulator import (
    simulate_rate_limit,
    simulate_timeout,
    simulate_api_error,
    RateLimitError,
    Timeout,
    APIError
)

# Test rate limit handling
with pytest.raises(RateLimitError):
    simulate_rate_limit()

# Test timeout handling
with pytest.raises(Timeout):
    simulate_timeout()

# Test 503 Service Unavailable
with pytest.raises(APIError) as exc_info:
    simulate_api_error(503)
assert exc_info.value.status_code == 503
```

#### Fail N Times, Then Succeed

```python
from tests.mocks.error_simulator import ErrorAfterNCalls, simulate_rate_limit

# Fail first 2 calls, then succeed
counter = ErrorAfterNCalls(2, lambda: simulate_rate_limit())

counter()  # Raises RateLimitError (call 1)
counter()  # Raises RateLimitError (call 2)
counter()  # Succeeds (call 3)
counter()  # Succeeds (call 4)
```

#### Mock Client with Errors

```python
from tests.mocks.mock_openai import create_mock_client_with_errors
from tests.mocks.error_simulator import simulate_rate_limit

# Create client that always raises RateLimitError
client = create_mock_client_with_errors(simulate_rate_limit)

with pytest.raises(RateLimitError):
    client.responses.create(model="gpt-5", input=[...])
```

---

### 6. Pytest Fixtures (`tests/conftest.py`)

All infrastructure is available as pytest fixtures. Simply add them as function parameters:

#### Database Fixtures

```python
def test_with_database(db_session):
    """Fresh in-memory SQLite database for each test."""
    from src.models import Document
    doc = Document(sha256_hex="abc123", original_filename="test.pdf")
    db_session.add(doc)
    db_session.commit()
    assert doc.id is not None
```

#### PDF Fixtures

```python
def test_with_pdf(sample_pdf, invoice_pdf, receipt_pdf):
    """Pre-generated test PDFs with deterministic hashes."""
    assert sample_pdf.exists()
    assert invoice_pdf.name == "invoice.pdf"
    assert receipt_pdf.name == "receipt.pdf"
```

#### Mock Client Fixtures

```python
def test_with_mocks(
    mock_openai_client,
    mock_files_client,
    mock_vector_store_client
):
    """All mock API clients available as fixtures."""
    # Use them directly in your tests
    response = mock_openai_client.responses.create(...)
    file_obj = mock_files_client.files.create(...)
    vs = mock_vector_store_client.vector_stores.create(...)
```

#### Document-Type-Specific Fixtures

```python
def test_document_types(
    mock_openai_invoice,
    mock_openai_receipt,
    mock_openai_utility_bill,
    mock_openai_bank_statement,
    mock_openai_unknown
):
    """Fixtures for each document type."""
    # Each returns the corresponding metadata
    pass
```

#### Metadata Fixtures

```python
def test_expected_metadata(
    invoice_metadata,
    receipt_metadata,
    utility_bill_metadata,
    bank_statement_metadata
):
    """Pre-loaded JSON metadata for each document type."""
    assert invoice_metadata["doc_type"] == "Invoice"
    assert receipt_metadata["doc_type"] == "Receipt"
```

#### Combined Fixtures

```python
def test_full_workflow(mock_all_apis, sample_pdf):
    """All APIs in one fixture."""
    # Upload file
    file_obj = mock_all_apis["files"].files.create(file=sample_pdf)

    # Call Responses API
    response = mock_all_apis["responses"].responses.create(...)

    # Create vector store
    vs = mock_all_apis["vector_stores"].vector_stores.create(...)
```

---

## Metadata Fixtures

Pre-defined JSON fixtures for all document types are in `tests/fixtures/metadata/`:

- `invoice.json` - Invoice from Acme Corporation ($1,250.00)
- `receipt.json` - Grocery receipt from Whole Foods ($87.43)
- `utility_bill.json` - Electric bill from PG&E ($156.78)
- `bank_statement.json` - Quarterly bank statement (no amount)
- `unknown.json` - Unknown document type (all nulls)

Each fixture includes:
- `file_name` (string)
- `doc_type` (enum: Invoice, Receipt, UtilityBill, BankStatement, Unknown)
- `issuer` (string or null)
- `primary_date` (ISO YYYY-MM-DD or null)
- `total_amount` (number or null)
- `summary` (string, ≤40 words)

---

## Testing Best Practices

### 1. Use Fixtures Over Manual Setup

❌ **Don't:**
```python
def test_bad():
    # Manual setup
    client = OpenAI(api_key="fake-key")
    pdf = Path("test.pdf")
    pdf.write_bytes(b"%PDF...")
```

✅ **Do:**
```python
def test_good(mock_openai_client, sample_pdf):
    # Fixtures provide everything
    response = mock_openai_client.responses.create(...)
```

### 2. Use Deterministic Test Data

❌ **Don't:**
```python
def test_bad():
    # Random data makes tests flaky
    sha = hashlib.sha256(os.urandom(32)).hexdigest()
```

✅ **Do:**
```python
def test_good(known_hashes):
    # Deterministic hashes
    sha = known_hashes["test"]
```

### 3. Test Error Scenarios

```python
def test_retry_logic():
    from tests.mocks.error_simulator import ErrorAfterNCalls, simulate_rate_limit

    # Fail 3 times, then succeed
    counter = ErrorAfterNCalls(3, simulate_rate_limit)

    # Your retry logic should handle this
    for attempt in range(5):
        try:
            counter()
            break  # Success
        except RateLimitError:
            if attempt == 4:
                raise  # Final attempt failed
```

### 4. Isolate Tests

Each test should be independent and not rely on state from other tests. All fixtures support parallel execution (pytest -n auto).

---

## Success Criteria (All Met ✅)

- ✅ pytest runs with all fixtures working (pytest tests/ -v)
- ✅ Mock OpenAI client returns realistic structured output
- ✅ Test PDFs generate correct SHA-256 hashes
- ✅ Database fixtures support parallel test execution (pytest -n auto)
- ✅ Test utilities simplify test authoring
- ✅ All fixtures documented with examples
- ✅ All 27 validation tests passing

---

## Integration with Other Workstreams

### Workstream 1: Database + Pipeline

Use this infrastructure immediately for testing:
- Database models (db_session fixture)
- SHA-256 deduplication logic (sample_pdf, known_hashes)
- Pipeline stages (mock_openai_client)

### Workstream 2: Retry Logic

Test comprehensive error handling:
- Rate limit errors (simulate_rate_limit)
- Timeout errors (simulate_timeout)
- Server errors (simulate_api_error)
- Multi-retry scenarios (ErrorAfterNCalls)

### Workstream 3: Cost Tracking

Validate token counting and cost calculations:
- Custom token counts (create_mock_client_with_custom_tokens)
- Usage statistics (response.usage)
- Cached token handling

---

## File Structure

```
tests/
├── __init__.py
├── README.md                         # This file
├── conftest.py                       # Pytest configuration & fixtures
├── test_infrastructure.py            # Validation tests (27 passing)
├── utils.py                          # Test utilities
├── mocks/
│   ├── __init__.py
│   ├── mock_openai.py               # Mock Responses API
│   ├── mock_files_api.py            # Mock Files API
│   ├── mock_vector_store.py         # Mock Vector Store API
│   └── error_simulator.py           # Error injection
└── fixtures/
    ├── __init__.py
    └── metadata/
        ├── invoice.json
        ├── receipt.json
        ├── utility_bill.json
        ├── bank_statement.json
        └── unknown.json
```

---

## Troubleshooting

### Import Errors

If you see `ModuleNotFoundError`, ensure you're running pytest from the project root:

```bash
cd /Users/krisstudio/Developer/Projects/autoD-testing
python3 -m pytest tests/
```

### Fixture Not Found

Make sure your test file is in the `tests/` directory. Pytest automatically discovers `conftest.py` fixtures.

### Type Annotation Errors

If you see "TypeError: 'type' object is not subscriptable", you may be using Python < 3.9. The code uses `from typing import List` for Python 3.8 compatibility.

---

## Next Steps

1. **Workstream 1 Integration** (Day 3): Use these fixtures to test database models and pipeline stages
2. **Add Business Logic Tests**: Write tests for actual application features using this infrastructure
3. **Extend Mocks**: Add custom response scenarios as needed for specific test cases

---

**Questions?** Review the docstrings in each module for detailed API documentation and examples.
