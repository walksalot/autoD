# Testing Guide — autoD

**Comprehensive guide for writing tests, achieving coverage targets, and maintaining test quality.**

**Audience**: Developers contributing to autoD
**Last Updated**: 2025-10-16

---

## Table of Contents

1. [Testing Philosophy](#testing-philosophy)
2. [Test Structure](#test-structure)
3. [Running Tests](#running-tests)
4. [Writing Unit Tests](#writing-unit-tests)
5. [Integration Tests](#integration-tests)
6. [Test Fixtures](#test-fixtures)
7. [Mocking External Dependencies](#mocking-external-dependencies)
8. [Coverage Requirements](#coverage-requirements)
9. [Common Testing Patterns](#common-testing-patterns)
10. [Performance Testing](#performance-testing)
11. [CI/CD Integration](#cicd-integration)
12. [Debugging Failed Tests](#debugging-failed-tests)

---

## Testing Philosophy

### Core Principles

1. **Tests as Documentation**: Tests should clearly demonstrate how code is intended to be used
2. **Fast Feedback**: Unit tests should run in milliseconds, integration tests in seconds
3. **Isolation**: Each test should be independent and not rely on other tests
4. **Clarity Over Cleverness**: Prefer readable tests over clever abstractions
5. **Coverage with Purpose**: Target 80%+ coverage, but focus on critical paths

### Testing Pyramid

```
        /\
       /  \        E2E Tests (Few)
      /____\       - Full pipeline tests
     /      \      - Real API calls (CI only)
    /        \
   /__________\    Integration Tests (Some)
  /            \   - Multi-module interactions
 /              \  - Database + API client
/________________\ Unit Tests (Many)
                   - Individual functions
                   - Pure logic
                   - Fast, isolated
```

### Coverage Goals

| Component | Target Coverage | Current | Priority |
|-----------|----------------|---------|----------|
| `src/config.py` | 90% | TBD | High |
| `src/models.py` | 85% | TBD | High |
| `src/processor.py` | 90% | TBD | Critical |
| `src/api_client.py` | 80% | TBD | High |
| `src/vector_store.py` | 75% | TBD | Medium |
| `src/dedupe.py` | 95% | TBD | Critical |
| `src/schema.py` | 90% | TBD | High |
| `src/token_counter.py` | 85% | TBD | Medium |
| `src/prompts.py` | 70% | TBD | Low |
| `src/logging_config.py` | 70% | TBD | Low |
| **Overall** | **80%+** | TBD | Critical |

---

## Test Structure

### Directory Layout

```
tests/
├── __init__.py
├── conftest.py              # Global fixtures
├── fixtures/
│   ├── sample_invoice.pdf
│   ├── sample_receipt.pdf
│   └── sample_metadata.json
├── mocks/
│   ├── mock_openai.py       # Mock OpenAI API client
│   ├── mock_responses.py    # Sample API responses
│   └── mock_files.py        # Mock Files API
├── unit/
│   ├── test_config.py
│   ├── test_models.py
│   ├── test_processor.py
│   ├── test_api_client.py
│   ├── test_vector_store.py
│   ├── test_dedupe.py
│   ├── test_schema.py
│   ├── test_token_counter.py
│   └── test_prompts.py
├── integration/
│   ├── test_pipeline.py     # Full pipeline tests
│   ├── test_db_api.py       # Database + API integration
│   └── test_vector_store_integration.py
└── e2e/
    └── test_end_to_end.py   # Complete workflows
```

### File Naming Conventions

- **Test files**: `test_<module_name>.py`
- **Test functions**: `test_<behavior>`
- **Test classes**: `Test<Component>`

**Examples**:
- `test_config.py` → Tests for `src/config.py`
- `test_sha256_computation()` → Tests SHA-256 hashing
- `TestDatabaseManager` → Tests for `DatabaseManager` class

---

## Running Tests

### Basic Commands

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/unit/test_config.py

# Run specific test function
pytest tests/unit/test_config.py::test_config_loading

# Run tests matching pattern
pytest -k "dedupe"

# Stop on first failure
pytest -x

# Run last failed tests
pytest --lf

# Run tests in parallel (requires pytest-xdist)
pytest -n auto
```

### Coverage Commands

```bash
# Run tests with coverage
pytest --cov=src

# Generate HTML coverage report
pytest --cov=src --cov-report=html

# View coverage report
open htmlcov/index.html

# Coverage with missing lines
pytest --cov=src --cov-report=term-missing

# Fail if coverage below threshold
pytest --cov=src --cov-fail-under=80
```

### Watching for Changes

```bash
# Install pytest-watch
pip install pytest-watch

# Run tests on file changes
ptw
```

---

## Writing Unit Tests

### Test Function Structure (Arrange-Act-Assert)

```python
def test_function_name():
    """Test description in imperative mood."""
    # Arrange - Set up test data and conditions
    input_data = {"key": "value"}
    expected_result = "expected"

    # Act - Execute the code under test
    actual_result = function_under_test(input_data)

    # Assert - Verify the result
    assert actual_result == expected_result
```

### Example: Testing Configuration

**File**: `tests/unit/test_config.py`

```python
import pytest
from pathlib import Path
from src.config import Config, get_config

def test_config_requires_api_key():
    """Config initialization fails if OPENAI_API_KEY is missing."""
    # Arrange
    import os
    original_key = os.environ.get("OPENAI_API_KEY")
    if "OPENAI_API_KEY" in os.environ:
        del os.environ["OPENAI_API_KEY"]

    # Act & Assert
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        Config()

    # Cleanup
    if original_key:
        os.environ["OPENAI_API_KEY"] = original_key

def test_config_validates_model():
    """Config rejects invalid model names."""
    # Arrange
    import os
    os.environ["OPENAI_API_KEY"] = "sk-test-key"
    os.environ["OPENAI_MODEL"] = "invalid-model"

    # Act & Assert
    with pytest.raises(ValueError, match="Model 'invalid-model' not allowed"):
        Config()

def test_config_immutability():
    """Config cannot be modified after creation."""
    # Arrange
    config = get_config()

    # Act & Assert
    with pytest.raises(Exception):  # Pydantic frozen model raises error
        config.openai_model = "gpt-5-pro"

def test_config_defaults():
    """Config uses correct default values."""
    # Arrange
    import os
    os.environ["OPENAI_API_KEY"] = "sk-test-key"
    if "OPENAI_MODEL" in os.environ:
        del os.environ["OPENAI_MODEL"]

    # Act
    config = Config()

    # Assert
    assert config.openai_model == "gpt-5-mini"
    assert config.paper_autopilot_db_url == "sqlite:///paper_autopilot.db"
    assert config.log_level == "INFO"
```

### Example: Testing Database Models

**File**: `tests/unit/test_models.py`

```python
import pytest
from datetime import datetime, timezone
from src.models import Document, Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

@pytest.fixture
def db_session():
    """Create in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_document_creation(db_session):
    """Document can be created with required fields."""
    # Arrange
    doc = Document(
        sha256_hex="a" * 64,
        original_filename="test.pdf"
    )

    # Act
    db_session.add(doc)
    db_session.commit()

    # Assert
    assert doc.id is not None
    assert doc.created_at is not None

def test_document_unique_sha256(db_session):
    """Database enforces unique SHA-256 constraint."""
    # Arrange
    sha_hex = "b" * 64
    doc1 = Document(sha256_hex=sha_hex, original_filename="file1.pdf")
    doc2 = Document(sha256_hex=sha_hex, original_filename="file2.pdf")

    # Act
    db_session.add(doc1)
    db_session.commit()

    db_session.add(doc2)

    # Assert
    with pytest.raises(Exception):  # IntegrityError from unique constraint
        db_session.commit()

def test_document_metadata_json_field(db_session):
    """Document can store JSON metadata."""
    # Arrange
    metadata = {
        "doc_type": "Invoice",
        "issuer": "Acme Corp",
        "total_amount": 123.45
    }
    doc = Document(
        sha256_hex="c" * 64,
        original_filename="invoice.pdf",
        metadata_json=metadata
    )

    # Act
    db_session.add(doc)
    db_session.commit()

    # Assert
    retrieved = db_session.query(Document).filter_by(sha256_hex="c" * 64).first()
    assert retrieved.metadata_json == metadata
    assert retrieved.metadata_json["issuer"] == "Acme Corp"
```

### Example: Testing Deduplication

**File**: `tests/unit/test_dedupe.py`

```python
import pytest
import hashlib
from pathlib import Path
from src.dedupe import deduplicate_and_hash, build_vector_store_attributes
from src.models import Document

def test_sha256_computation(tmp_path):
    """SHA-256 hash is computed correctly."""
    # Arrange
    pdf_path = tmp_path / "test.pdf"
    pdf_content = b"%PDF-1.4\n%%EOF"
    pdf_path.write_bytes(pdf_content)

    expected_sha = hashlib.sha256(pdf_content).hexdigest()

    # Act
    hex_hash, b64_hash, duplicate = deduplicate_and_hash(pdf_path, None)

    # Assert
    assert hex_hash == expected_sha
    assert len(hex_hash) == 64
    assert b64_hash is not None

def test_dedupe_detects_existing(db_session, tmp_path):
    """Deduplication detects existing documents."""
    # Arrange
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%%EOF")

    # First upload - no duplicate
    hex_hash1, _, duplicate1 = deduplicate_and_hash(pdf_path, db_session)
    assert duplicate1 is None

    # Save to database
    doc = Document(sha256_hex=hex_hash1, original_filename="test.pdf")
    db_session.add(doc)
    db_session.commit()

    # Act - Second upload - should detect duplicate
    hex_hash2, _, duplicate2 = deduplicate_and_hash(pdf_path, db_session)

    # Assert
    assert duplicate2 is not None
    assert duplicate2.id == doc.id
    assert hex_hash1 == hex_hash2

def test_vector_store_attributes_generation():
    """Vector store attributes are built correctly."""
    # Arrange
    doc = Document(
        id=123,
        sha256_hex="d" * 64,
        original_filename="invoice.pdf",
        doc_type="Invoice",
        issuer="Acme Corp",
        primary_date="2025-10-16"
    )

    # Act
    attrs = build_vector_store_attributes(doc)

    # Assert
    assert attrs["sha256_hex"] == "d" * 64
    assert attrs["original_file_name"] == "invoice.pdf"
    assert attrs["doc_type"] == "Invoice"
    assert attrs["issuer"] == "Acme Corp"
    assert attrs["document_id"] == "123"
```

### Example: Testing Token Counting

**File**: `tests/unit/test_token_counter.py`

```python
import pytest
from src.token_counter import calculate_cost, format_cost_report, check_cost_alerts

def test_calculate_cost_basic():
    """Cost calculation for basic usage."""
    # Arrange
    prompt_tokens = 1000
    completion_tokens = 500
    cached_tokens = 0
    model = "gpt-5-mini"

    # Act
    result = calculate_cost(prompt_tokens, completion_tokens, cached_tokens, model)

    # Assert
    assert result["prompt_tokens"] == 1000
    assert result["completion_tokens"] == 500
    assert result["cached_tokens"] == 0
    assert result["total_cost"] > 0
    assert isinstance(result["total_cost"], float)

def test_calculate_cost_with_caching():
    """Cost calculation includes cached token discount."""
    # Arrange
    prompt_tokens = 1000
    completion_tokens = 500
    cached_tokens = 900  # 90% cache hit
    model = "gpt-5-mini"

    # Act
    result = calculate_cost(prompt_tokens, completion_tokens, cached_tokens, model)

    # Assert
    assert result["cached_tokens"] == 900
    # Cost should be lower due to cache discount
    result_no_cache = calculate_cost(prompt_tokens, completion_tokens, 0, model)
    assert result["total_cost"] < result_no_cache["total_cost"]

def test_cost_alert_triggers():
    """Cost alerts trigger at appropriate thresholds."""
    # Arrange & Act
    alert_low = check_cost_alerts(0.05)
    alert_medium = check_cost_alerts(0.15)
    alert_high = check_cost_alerts(0.35)
    alert_critical = check_cost_alerts(1.5)

    # Assert
    assert alert_low is None
    assert alert_medium is not None and "WARNING" in alert_medium
    assert alert_high is not None and "HIGH" in alert_high
    assert alert_critical is not None and "CRITICAL" in alert_critical
```

---

## Integration Tests

### Database + API Integration

**File**: `tests/integration/test_db_api.py`

```python
import pytest
from pathlib import Path
from src.database import DatabaseManager
from src.api_client import ResponsesAPIClient
from src.processor import process_document
from src.vector_store import VectorStoreManager

@pytest.fixture
def integration_setup():
    """Set up real database and mock API client for integration tests."""
    db = DatabaseManager("sqlite:///:memory:")
    db.create_tables()
    api_client = ResponsesAPIClient()  # Can mock if needed
    vector_manager = VectorStoreManager()
    return db, api_client, vector_manager

def test_full_pipeline_integration(integration_setup, tmp_path):
    """Full pipeline processes PDF and saves to database."""
    # Arrange
    db, api_client, vector_manager = integration_setup
    pdf_path = tmp_path / "invoice.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF")

    # Act
    result = process_document(pdf_path, db, api_client, vector_manager)

    # Assert
    assert result.success is True
    assert result.document_id is not None

    # Verify database record
    with db.get_session() as session:
        from src.models import Document
        doc = session.query(Document).filter_by(id=result.document_id).first()
        assert doc is not None
        assert doc.original_filename == "invoice.pdf"
```

### Pipeline Stage Integration

**File**: `tests/integration/test_pipeline.py`

```python
import pytest
from pathlib import Path
from src.pipeline import Pipeline, ProcessingContext
from src.stages.sha256_stage import ComputeSHA256Stage
from src.stages.dedupe_stage import DedupeCheckStage

def test_pipeline_multi_stage(db_session, tmp_path):
    """Pipeline executes multiple stages in sequence."""
    # Arrange
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%%EOF")

    pipeline = Pipeline([
        ComputeSHA256Stage(),
        DedupeCheckStage(db_session)
    ])

    context = ProcessingContext(pdf_path=pdf_path)

    # Act
    result = pipeline.process(context)

    # Assert
    assert result.sha256_hex is not None
    assert result.is_duplicate is False
    assert result.error is None
```

---

## Test Fixtures

### Global Fixtures (conftest.py)

**File**: `tests/conftest.py`

```python
import pytest
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models import Base

@pytest.fixture(scope="session")
def test_data_dir():
    """Path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"

@pytest.fixture
def db_session():
    """Create in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

@pytest.fixture
def sample_pdf(tmp_path):
    """Create minimal valid PDF file."""
    pdf_path = tmp_path / "sample.pdf"
    pdf_content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n%%EOF"
    pdf_path.write_bytes(pdf_content)
    return pdf_path

@pytest.fixture
def sample_metadata():
    """Sample metadata JSON from API response."""
    return {
        "doc_type": "Invoice",
        "issuer": "Acme Corp",
        "primary_date": "2025-10-16",
        "total_amount": 123.45,
        "currency": "USD",
        "summary": "Invoice for services rendered"
    }

@pytest.fixture
def mock_openai_response():
    """Mock OpenAI API response."""
    class MockResponse:
        def __init__(self):
            self.usage = type('obj', (object,), {
                'prompt_tokens': 100,
                'output_tokens': 50,
                'prompt_tokens_details': {'cached_tokens': 90}
            })
            self.output_text = '{"doc_type": "Invoice"}'

    return MockResponse()
```

### Fixture Scopes

```python
# Function scope (default) - recreated for each test
@pytest.fixture
def temp_data():
    return {"key": "value"}

# Class scope - shared across test class
@pytest.fixture(scope="class")
def shared_resource():
    return expensive_setup()

# Module scope - shared across test module
@pytest.fixture(scope="module")
def database_connection():
    conn = create_connection()
    yield conn
    conn.close()

# Session scope - shared across entire test session
@pytest.fixture(scope="session")
def config():
    return load_config()
```

---

## Mocking External Dependencies

### Mocking OpenAI API

**File**: `tests/mocks/mock_openai.py`

```python
class MockResponsesAPI:
    """Mock OpenAI Responses API client."""

    def __init__(self, response_data=None):
        self.response_data = response_data or {
            "doc_type": "Invoice",
            "issuer": "Acme Corp",
            "total_amount": 123.45
        }

    def create(self, **kwargs):
        """Mock create_response method."""
        class MockResponse:
            def __init__(self, data):
                self.output_text = str(data)
                self.usage = type('obj', (object,), {
                    'prompt_tokens': 100,
                    'output_tokens': 50,
                    'prompt_tokens_details': {'cached_tokens': 90}
                })()

        return MockResponse(self.response_data)

# Usage in tests
def test_with_mock_api(monkeypatch):
    """Test using mocked OpenAI API."""
    mock_api = MockResponsesAPI({"doc_type": "Receipt"})
    monkeypatch.setattr("src.api_client.client.responses", mock_api)

    # Test code that uses API client
    ...
```

### Mocking Environment Variables

```python
def test_with_env_vars(monkeypatch):
    """Test with custom environment variables."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-5-mini")

    # Test code that uses environment variables
    ...
```

### Mocking File System

```python
def test_with_temp_files(tmp_path):
    """Test with temporary files (pytest built-in fixture)."""
    # tmp_path is a pathlib.Path to a temporary directory
    test_file = tmp_path / "test.pdf"
    test_file.write_bytes(b"%PDF-1.4\n%%EOF")

    # Test code that uses files
    ...
```

---

## Coverage Requirements

### Measuring Coverage

```bash
# Run tests with coverage
pytest --cov=src --cov-report=term-missing

# Generate HTML report
pytest --cov=src --cov-report=html
open htmlcov/index.html

# Fail if coverage below 80%
pytest --cov=src --cov-fail-under=80
```

### Coverage Report Example

```
---------- coverage: platform darwin, python 3.11.5 -----------
Name                       Stmts   Miss  Cover   Missing
--------------------------------------------------------
src/__init__.py                0      0   100%
src/api_client.py            120     12    90%   45-50, 78-82
src/config.py                 85      5    94%   92-95
src/database.py              110      8    93%   156-160
src/dedupe.py                 65      3    95%   48-50
src/logging_config.py         45     15    67%   22-35
src/models.py                 95      8    92%   78-82
src/processor.py             180     15    92%   145-150, 220-225
src/prompts.py                50     12    76%   35-42
src/schema.py                 75      5    93%   65-68
src/token_counter.py          60      8    87%   45-50
src/vector_store.py          100     20    80%   78-92, 120-125
--------------------------------------------------------
TOTAL                        985     111   89%
```

### Prioritizing Coverage

**High Priority** (>90% coverage):
- Core business logic (`processor.py`, `dedupe.py`)
- Data integrity (`models.py`, `schema.py`)
- Configuration (`config.py`)

**Medium Priority** (>80% coverage):
- External integrations (`api_client.py`, `vector_store.py`)
- Cost tracking (`token_counter.py`)

**Low Priority** (>70% coverage):
- Logging (`logging_config.py`)
- Prompts (`prompts.py`)

---

## Common Testing Patterns

### Parametrized Tests

```python
@pytest.mark.parametrize("input,expected", [
    ("Invoice", "Invoice"),
    ("receipt", "Receipt"),
    ("UTILITY_BILL", "UtilityBill"),
])
def test_normalize_doc_type(input, expected):
    """Document type normalization handles various inputs."""
    assert normalize_doc_type(input) == expected
```

### Testing Exceptions

```python
def test_invalid_api_key_raises_error():
    """Invalid API key raises AuthenticationError."""
    with pytest.raises(AuthenticationError, match="Invalid API key"):
        client = ResponsesAPIClient(api_key="invalid-key")
        client.create_response(...)
```

### Testing Retries

```python
def test_retry_logic_on_rate_limit(mocker):
    """API client retries on rate limit errors."""
    # Mock API to fail 3 times, then succeed
    mock_create = mocker.patch("src.api_client.client.responses.create")
    mock_create.side_effect = [
        RateLimitError("Rate limit exceeded"),
        RateLimitError("Rate limit exceeded"),
        RateLimitError("Rate limit exceeded"),
        MockSuccessResponse()
    ]

    # Act
    result = call_with_retry()

    # Assert
    assert mock_create.call_count == 4
    assert result is not None
```

### Testing Logging

```python
def test_structured_logging(caplog):
    """Logs are structured with expected fields."""
    import logging
    from src.logging_config import setup_logging

    logger = setup_logging(log_level="INFO")

    with caplog.at_level(logging.INFO):
        logger.info("Processing started", extra={"doc_id": 123})

    assert "Processing started" in caplog.text
    assert "doc_id" in caplog.records[0].__dict__
    assert caplog.records[0].doc_id == 123
```

---

## Performance Testing

### Load Testing

```python
import time
import pytest

def test_processing_throughput(db_session, tmp_path):
    """Pipeline processes 100 PDFs within time budget."""
    # Arrange
    pdfs = []
    for i in range(100):
        pdf_path = tmp_path / f"doc_{i}.pdf"
        pdf_path.write_bytes(b"%PDF-1.4\n%%EOF")
        pdfs.append(pdf_path)

    # Act
    start_time = time.time()
    for pdf in pdfs:
        result = process_document(pdf, ...)
    duration = time.time() - start_time

    # Assert
    assert duration < 300  # 5 minutes for 100 PDFs
    throughput = 100 / duration
    assert throughput > 0.33  # At least 20 PDFs/minute
```

### Memory Testing

```python
import psutil
import os

def test_memory_usage_bounded():
    """Processing large PDFs doesn't exceed memory budget."""
    process = psutil.Process(os.getpid())
    initial_memory = process.memory_info().rss / 1024 / 1024  # MB

    # Process large PDF
    result = process_document(large_pdf_path, ...)

    final_memory = process.memory_info().rss / 1024 / 1024  # MB
    memory_increase = final_memory - initial_memory

    assert memory_increase < 500  # Less than 500MB increase
```

---

## CI/CD Integration

### GitHub Actions Workflow

**File**: `.github/workflows/test.yml`

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install pytest pytest-cov

      - name: Run tests with coverage
        run: |
          pytest --cov=src --cov-report=xml --cov-fail-under=80

      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage.xml
```

### Pre-commit Hooks

**File**: `.pre-commit-config.yaml`

```yaml
repos:
  - repo: local
    hooks:
      - id: pytest
        name: pytest
        entry: pytest
        language: system
        pass_filenames: false
        always_run: true
```

---

## Debugging Failed Tests

### Common Debugging Techniques

**1. Use `-v` for verbose output**:
```bash
pytest -v tests/unit/test_processor.py
```

**2. Use `-s` to see print statements**:
```bash
pytest -s tests/unit/test_processor.py
```

**3. Use `--pdb` to drop into debugger on failure**:
```bash
pytest --pdb tests/unit/test_processor.py
```

**4. Use `--lf` to run only last failed tests**:
```bash
pytest --lf
```

**5. Use `-k` to run specific test**:
```bash
pytest -k "test_sha256_computation"
```

### Debugging with pdb

```python
def test_complex_logic():
    """Test with debugging."""
    # Set breakpoint
    import pdb; pdb.set_trace()

    result = complex_function()
    assert result == expected
```

**pdb commands**:
- `n` - next line
- `s` - step into function
- `c` - continue execution
- `p variable` - print variable
- `l` - list current code context
- `q` - quit debugger

---

## Best Practices

### DO

✅ Write tests before fixing bugs (reproduce first)
✅ Keep tests focused and independent
✅ Use descriptive test names
✅ Test edge cases and error conditions
✅ Use fixtures for common setup
✅ Mock external dependencies (APIs, databases in unit tests)
✅ Maintain 80%+ code coverage
✅ Run tests locally before pushing
✅ Document complex test setups

### DON'T

❌ Write tests that depend on other tests
❌ Use real API calls in unit tests
❌ Hard-code file paths or credentials
❌ Ignore failing tests
❌ Skip writing tests for "simple" code
❌ Test implementation details (test behavior, not internals)
❌ Leave debugging code (print statements, breakpoints) in tests

---

## References

- **Pytest Documentation**: https://docs.pytest.org/
- **Coverage.py Documentation**: https://coverage.readthedocs.io/
- **Testing Best Practices**: Martin Fowler's testing articles
- **Code Examples**: `tests/` directory in this repository
- **CI/CD Examples**: `.github/workflows/` directory

---

**Last Updated**: 2025-10-16
**Maintained By**: Platform Engineering Team
**Next Review**: After each major feature addition
