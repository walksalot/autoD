# Implementation Roadmap: autoD → Paper Autopilot

**Status**: Revised based on architectural review (2025-10-16)
**Timeline**: 4 weeks iterative development
**Strategy**: Ship working software every week, iterate based on real problems

---

## Executive Summary

This roadmap transforms the current 138-line PDF processing sandbox into a production-ready system through **iterative phasing**. Unlike the original 8-phase parallel approach, this strategy builds incrementally with working software at each milestone.

**Key Change**: We're solving **actual problems** one at a time, not hypothetical future problems.

**📋 See Also**: [`CHANGES_FROM_ORIGINAL_PLAN.md`](./CHANGES_FROM_ORIGINAL_PLAN.md) - Comprehensive comparison between the original 8-phase plan and this 4-week iterative approach, including architectural improvements and rationale for all changes.

---

## Critical Architectural Fixes Required

Based on architectural review, the following issues **must** be addressed:

### 1. Database Type Incompatibility ❌
**Problem**: Original plan uses PostgreSQL-specific `JSONB` type
**Impact**: Code won't run on SQLite (dev environment breaks)
**Fix**: Use SQLAlchemy's generic `JSON` type (works on both SQLite and PostgreSQL)

### 2. Monolithic Processing Function ❌
**Problem**: Planned `process_pdf()` function does everything (~200 lines)
**Impact**: Untestable, unclear transaction boundaries, partial failures
**Fix**: Pipeline pattern with discrete stages (see CODE_ARCHITECTURE.md)

### 3. Transaction Boundary Issues ❌
**Problem**: DB commits before vector store uploads → orphaned records on failure
**Impact**: Data corruption, no way to recover
**Fix**: Compensating transactions or best-effort pattern

### 4. Incomplete Retry Logic ❌
**Problem**: Only retries `RateLimitError` and `APIConnectionError`
**Impact**: Fails on timeout errors, 500s, 502s, 503s
**Fix**: Comprehensive retry predicate with tenacity

### 5. Premature Scaling ⚠️
**Problem**: Building for 1M PDFs when processing 10/day
**Impact**: Wasted effort, increased complexity
**Fix**: Start simple, scale when needed

---

## 4-Week Implementation Plan

### Philosophy: Incremental Value Delivery

Each week delivers **working, shippable software** that solves a real problem:

- **Week 1**: Database persistence (query historical PDFs)
- **Week 2**: Resilience (survive API failures gracefully)
- **Week 3**: Observability (understand costs and performance)
- **Week 4**: Production hardening (vector stores, migrations)

---

## Week 1: Foundation & Database Persistence

**Goal**: Process 100 PDFs, store in database, no duplicates

### Day 1-2: Infrastructure Setup

**Tasks**:
1. Initialize git repository
2. Create `.gitignore`, `.env.example`
3. Set up `src/` directory structure
4. Add dependencies (minimal set)

**Deliverables**:
```bash
# Directory structure
src/
├── __init__.py
├── config.py          # Environment configuration
├── models.py          # SQLAlchemy models
├── logging_config.py  # Structured JSON logging
└── processor.py       # Main processing logic

# Dependencies (requirements.txt)
openai>=1.58.1
sqlalchemy>=2.0.36
python-dotenv>=1.0.1
PyPDF2>=3.0.1

# Configuration (.env.example)
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-5
DATABASE_URL=sqlite:///paper_autopilot.db
```

**Code Example** (`src/config.py`):
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Application configuration loaded from environment."""

    # OpenAI
    openai_api_key: str
    openai_model: str = "gpt-5"

    # Database
    database_url: str = "sqlite:///paper_autopilot.db"

    # Processing
    max_output_tokens: int = 60000
    timeout_seconds: int = 300

    class Config:
        env_file = ".env"

settings = Settings()
```

---

### Day 3-4: Database Models & Persistence

**Tasks**:
1. Create SQLAlchemy `Document` model (10 core fields)
2. Add database initialization
3. Implement basic persistence after API call
4. Test with 10 sample PDFs

**Critical Fix**: Use generic `JSON` type, not `JSONB`

**Code Example** (`src/models.py`):
```python
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime, timezone

Base = declarative_base()

class Document(Base):
    __tablename__ = "documents"

    # Primary key
    id = Column(Integer, primary_key=True)

    # File identity (deduplication)
    sha256_hex = Column(String(64), unique=True, index=True, nullable=False)
    original_filename = Column(String(512), nullable=False)

    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    processed_at = Column(DateTime, nullable=True)

    # OpenAI references
    source_file_id = Column(String(64), index=True)
    vector_store_file_id = Column(String(64), index=True, nullable=True)

    # Extracted metadata (full JSON response)
    metadata_json = Column(JSON, nullable=True)  # ← Generic JSON type

    # Status tracking
    status = Column(String(32), default="pending", index=True)
    error_message = Column(Text, nullable=True)

def init_db(db_url: str):
    """Initialize database and return session."""
    engine = create_engine(db_url, future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()
```

**Why 10 fields vs. 40+?**
- Simpler to reason about and test
- JSON blob stores full API response (nothing lost)
- Can extract specific fields later via migrations
- Faster to ship and validate

---

### Day 5: SHA-256 Deduplication

**Tasks**:
1. Compute SHA-256 before processing
2. Check database for existing hash
3. Skip if duplicate found
4. Test by reprocessing same PDFs

**Code Example** (`src/dedupe.py`):
```python
import hashlib
import base64
from pathlib import Path
from typing import Tuple

def sha256_file(path: Path) -> Tuple[str, str]:
    """Compute SHA-256 hash (hex + base64) for file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    digest = h.digest()
    return h.hexdigest(), base64.b64encode(digest).decode("ascii")

def is_duplicate(session, sha_hex: str) -> bool:
    """Check if document with this hash already exists."""
    from .models import Document
    return session.query(Document).filter_by(sha256_hex=sha_hex).first() is not None
```

**Validation**:
```bash
# Process 10 PDFs
python process_inbox.py
# Count: 10 records in DB

# Reprocess same 10 PDFs
python process_inbox.py
# Count: Still 10 records (no duplicates)
```

---

### Week 1 Success Criteria

- ✅ 100 PDFs processed successfully
- ✅ All PDFs stored in SQLite database
- ✅ Zero duplicate records (SHA-256 deduplication works)
- ✅ Structured JSON logging enabled
- ✅ Git repository initialized with meaningful commits

---

## Week 2: Resilience & Error Handling

**Goal**: Survive API failures gracefully, retry transient errors

### Day 1-2: Retry Logic with Tenacity

**Tasks**:
1. Install `tenacity` library
2. Wrap API calls with `@retry` decorator
3. Implement comprehensive retry predicate
4. Test with simulated failures

**Critical Fix**: Handle ALL retryable errors, not just rate limits

**Code Example** (`src/retry_logic.py`):
```python
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception,
)
from openai import RateLimitError, APIConnectionError, APIError, Timeout
import logging

logger = logging.getLogger(__name__)

def is_retryable_api_error(exception: Exception) -> bool:
    """
    Determine if an OpenAI API error should be retried.

    Retryable:
    - Rate limits (429)
    - Connection errors
    - Timeouts
    - Server errors (500, 502, 503, 504)

    Non-retryable:
    - Authentication errors (401)
    - Bad requests (400)
    - Content policy violations
    """
    if isinstance(exception, (RateLimitError, APIConnectionError, Timeout)):
        return True

    if isinstance(exception, APIError):
        # Retry 5xx errors (server-side issues)
        if hasattr(exception, 'status_code') and exception.status_code >= 500:
            return True
        # Don't retry 4xx errors (client errors)
        return False

    return False

@retry(
    retry=retry_if_exception(is_retryable_api_error),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    reraise=True,
)
def call_openai_with_retry(client, **kwargs):
    """
    Call OpenAI API with exponential backoff retry.

    Retry schedule:
    - Attempt 1: immediate
    - Attempt 2: wait 2s
    - Attempt 3: wait 4s
    - Attempt 4: wait 8s
    - Attempt 5: wait 16s

    Max total wait: ~30 seconds
    """
    logger.info("Calling OpenAI API", extra={"attempt": kwargs.get("_retry_count", 1)})
    return client.responses.create(**kwargs)
```

**Testing**:
```python
# tests/test_retry_logic.py
import pytest
from openai import RateLimitError, AuthenticationError
from src.retry_logic import is_retryable_api_error

def test_rate_limit_is_retryable():
    assert is_retryable_api_error(RateLimitError("rate limit")) == True

def test_auth_error_not_retryable():
    assert is_retryable_api_error(AuthenticationError("invalid key")) == False

def test_500_error_is_retryable():
    error = APIError("server error")
    error.status_code = 500
    assert is_retryable_api_error(error) == True
```

---

### Day 3-4: Transaction Safety

**Tasks**:
1. Implement compensating transaction pattern
2. Handle partial failures (DB commit succeeds, vector store upload fails)
3. Add status tracking in database
4. Document recovery procedures

**Critical Fix**: Prevent orphaned records

**Code Example** (`src/transactions.py`):
```python
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)

@contextmanager
def compensating_transaction(session, compensate_fn):
    """
    Context manager that provides compensation logic if commit fails.

    Usage:
        with compensating_transaction(session, lambda: cleanup_openai_file(file_id)):
            doc = Document(...)
            session.add(doc)
            # If commit succeeds → no compensation
            # If commit fails → compensation runs, then re-raises
    """
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        # Run compensation (cleanup external resources)
        try:
            compensate_fn()
            logger.info("Compensation completed successfully")
        except Exception as comp_err:
            # Log but don't mask original error
            logger.error(f"Compensation failed: {comp_err}", exc_info=True)
        raise e  # Re-raise original exception
```

**Alternative (Simpler)**: Best-effort pattern
```python
# Step 1: Write to DB first (source of truth)
session.add(doc)
session.commit()

# Step 2: Upload to vector store (best-effort)
try:
    vs_file_id = add_to_vector_store(file_id)
    doc.vector_store_file_id = vs_file_id
    session.commit()
except Exception as e:
    # Database is authoritative; vector store is supplementary
    logger.warning(f"Vector store upload failed for doc {doc.id}: {e}")
    # Don't fail entire pipeline - can retry later
```

---

### Day 5: Structured Logging

**Tasks**:
1. Replace print statements with JSON logging
2. Add contextual metadata (pdf_path, doc_id, duration)
3. Log stage transitions
4. Create simple dashboard (view logs with `jq`)

**Code Example** (`src/logging_config.py`):
```python
import logging
import json
from datetime import datetime

class JSONFormatter(logging.Formatter):
    """Format log records as JSON for structured logging."""

    def format(self, record):
        log_obj = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }

        # Add extra context if present
        for attr in ["pdf_path", "sha256_hex", "doc_id", "duration_ms", "cost_usd"]:
            if hasattr(record, attr):
                log_obj[attr] = getattr(record, attr)

        return json.dumps(log_obj)

def setup_logging(log_level=logging.INFO):
    """Configure structured logging."""
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())

    logger = logging.getLogger("autod")
    logger.setLevel(log_level)
    logger.addHandler(handler)

    return logger
```

**Usage**:
```python
logger = setup_logging()

logger.info("Processing PDF", extra={"pdf_path": str(pdf_path)})
logger.info("Dedupe check", extra={"sha256_hex": sha_hex, "is_duplicate": False})
logger.info("API call complete", extra={"doc_id": doc.id, "duration_ms": 1234, "cost_usd": 0.05})
```

**Querying logs**:
```bash
# Count successful vs. failed processing
cat autod.log | jq -s 'group_by(.status) | map({status: .[0].status, count: length})'

# Average processing time
cat autod.log | jq -s 'map(select(.duration_ms)) | add / length'

# Total cost
cat autod.log | jq -s 'map(select(.cost_usd)) | map(.cost_usd) | add'
```

---

### Week 2 Success Criteria

- ✅ API calls survive rate limit errors (5 retries with backoff)
- ✅ Transient errors (500, 503) automatically retried
- ✅ Permanent errors (401, 400) fail fast (no retry)
- ✅ Database remains consistent even on partial failures
- ✅ Structured JSON logs enable analysis
- ✅ 95%+ success rate on 100-PDF test corpus

---

## Week 3: Observability & Testing

**Goal**: Understand costs, performance, and reliability

### Day 1-2: Token Tracking & Cost Estimation

**Tasks**:
1. Install `tiktoken` for token counting
2. Parse actual usage from API responses
3. Calculate cost per PDF
4. Log token/cost metrics

**Code Example** (`src/token_counter.py`):
```python
import tiktoken
from .config import settings

def get_tokenizer(model: str):
    """Get tiktoken encoder for model."""
    try:
        return tiktoken.encoding_for_model(model)
    except Exception:
        # GPT-5 typically uses o200k_base encoding
        try:
            return tiktoken.get_encoding("o200k_base")
        except Exception:
            return tiktoken.get_encoding("cl100k_base")

def estimate_tokens(text: str, model: str = None) -> int:
    """Estimate token count for text."""
    model = model or settings.openai_model
    enc = get_tokenizer(model)
    return len(enc.encode(text or ""))

def calculate_cost(usage: dict) -> dict:
    """Calculate cost from API usage object."""
    prompt_tokens = usage.get("prompt_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    cached_tokens = usage.get("prompt_tokens_details", {}).get("cached_tokens", 0)

    # Billable input = total - cached
    billable_input = max(prompt_tokens - cached_tokens, 0)

    # Cost calculation (USD)
    cost = (
        (billable_input / 1000.0) * settings.input_cost_per_1k +
        (cached_tokens / 1000.0) * settings.cached_input_cost_per_1k +
        (output_tokens / 1000.0) * settings.output_cost_per_1k
    )

    return {
        "prompt_tokens": prompt_tokens,
        "cached_prompt_tokens": cached_tokens,
        "output_tokens": output_tokens,
        "estimated_cost_usd": round(cost, 6)
    }
```

**Usage**:
```python
# After API call
resp = client.responses.create(...)

# Extract and log usage
usage_stats = calculate_cost(resp.usage.__dict__)
logger.info("API call completed", extra={
    "doc_id": doc.id,
    **usage_stats
})
```

**Cost Dashboard**:
```bash
# Total cost for all PDFs
cat autod.log | jq -s 'map(select(.estimated_cost_usd)) | map(.estimated_cost_usd) | add'

# Cost per PDF (average)
cat autod.log | jq -s 'map(select(.estimated_cost_usd)) | add / length'

# Token distribution
cat autod.log | jq -s 'map(select(.prompt_tokens)) | {
  avg_prompt: (map(.prompt_tokens) | add / length),
  avg_output: (map(.output_tokens) | add / length),
  avg_cached: (map(.cached_prompt_tokens) | add / length)
}'
```

---

### Day 3-4: Unit Testing

**Tasks**:
1. Add `pytest` and `pytest-mock`
2. Write unit tests for core functions
3. Create test fixtures
4. Achieve 60% coverage

**Directory Structure**:
```
tests/
├── __init__.py
├── conftest.py          # Pytest fixtures
├── fixtures/
│   └── sample.pdf       # Test PDF file
├── test_dedupe.py       # SHA-256 tests
├── test_retry_logic.py  # Retry predicate tests
└── test_processor.py    # Integration tests
```

**Code Example** (`tests/conftest.py`):
```python
import pytest
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models import Base

@pytest.fixture
def db_session():
    """Create in-memory SQLite session for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

@pytest.fixture
def sample_pdf(tmp_path):
    """Create a sample PDF file for testing."""
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\ntest content")
    return pdf_path
```

**Code Example** (`tests/test_dedupe.py`):
```python
from src.dedupe import sha256_file, is_duplicate
from src.models import Document

def test_sha256_consistency(sample_pdf):
    """SHA-256 hash is consistent across calls."""
    sha_hex1, sha_b641 = sha256_file(sample_pdf)
    sha_hex2, sha_b642 = sha256_file(sample_pdf)

    assert sha_hex1 == sha_hex2
    assert sha_b641 == sha_b642
    assert len(sha_hex1) == 64

def test_dedupe_detection(db_session, sample_pdf):
    """Duplicate documents are detected."""
    sha_hex, sha_b64 = sha256_file(sample_pdf)

    # First check: not duplicate
    assert is_duplicate(db_session, sha_hex) == False

    # Add document
    doc = Document(sha256_hex=sha_hex, original_filename="test.pdf")
    db_session.add(doc)
    db_session.commit()

    # Second check: is duplicate
    assert is_duplicate(db_session, sha_hex) == True
```

**Running Tests**:
```bash
# Run all tests
pytest

# With coverage
pytest --cov=src --cov-report=html

# Specific test file
pytest tests/test_dedupe.py -v
```

---

### Day 5: Documentation

**Tasks**:
1. Document architecture decisions (see ADR)
2. Write runbook for common failures
3. Update README with deployment steps
4. Create troubleshooting guide

**Runbook Example** (`docs/RUNBOOK.md`):
```markdown
# Runbook: Common Failure Scenarios

## Scenario 1: API Rate Limit Exceeded

**Symptoms**: Logs show `RateLimitError` after 5 retries

**Diagnosis**:
cat autod.log | jq 'select(.level == "ERROR" and .message contains "RateLimitError")'

**Resolution**:
1. Wait 60 seconds (rate limit resets)
2. Rerun: python process_inbox.py
3. Already-processed PDFs will be skipped (deduplication)

## Scenario 2: Database Locked

**Symptoms**: `sqlite3.OperationalError: database is locked`

**Diagnosis**: Another process has exclusive lock

**Resolution**:
1. Check for running processes: ps aux | grep process_inbox
2. Kill stale process: kill <PID>
3. Rerun: python process_inbox.py

## Scenario 3: Out of Disk Space

**Symptoms**: `OSError: [Errno 28] No space left on device`

**Diagnosis**: Database file grew too large

**Resolution**:
1. Check size: du -sh paper_autopilot.db
2. Vacuum database: sqlite3 paper_autopilot.db "VACUUM;"
3. Archive old records if needed
```

---

### Week 3 Success Criteria

- ✅ Token/cost tracking for all processed PDFs
- ✅ Unit tests with 60%+ coverage
- ✅ Runbook documents common failure scenarios
- ✅ Cost dashboard using `jq` queries
- ✅ Average cost per PDF < $0.10

---

## Week 4: Production Readiness

**Goal**: Process first 1000 PDFs in production

### Day 1-2: Vector Store Integration

**Tasks**:
1. Create persistent vector store
2. Upload PDFs after DB commit
3. Add file search tool to API requests
4. Store vector_store_file_id in database

**Code Example** (`src/vector_store.py`):
```python
from openai import OpenAI
from pathlib import Path
from typing import Optional, Dict, Any
from .config import settings

client = OpenAI(api_key=settings.openai_api_key)

def get_or_create_vector_store() -> str:
    """Load persistent vector store ID or create new."""
    vs_id_path = Path(settings.vector_store_id_file)

    if vs_id_path.exists():
        return vs_id_path.read_text().strip()

    # Create new vector store
    vs = client.vector_stores.create(name=settings.vector_store_name)
    vs_id_path.write_text(vs.id)
    return vs.id

def add_file_to_vector_store(
    vector_store_id: str,
    file_id: str,
    *,
    attributes: Optional[Dict[str, Any]] = None
) -> str:
    """
    Attach file to vector store with metadata attributes.

    Max 16 key-value pairs for attributes (per OpenAI limits).
    """
    vs_file = client.vector_stores.files.create(
        vector_store_id=vector_store_id,
        file_id=file_id
    )

    # Update attributes if provided
    if attributes:
        client.vector_stores.files.update(
            vector_store_id=vector_store_id,
            file_id=vs_file.id,
            attributes=attributes
        )

    return vs_file.id
```

**API Request with File Search**:
```python
# Enable file search tool
vs_id = get_or_create_vector_store()

resp = client.responses.create(
    model=settings.openai_model,
    tools=[{"type": "file_search"}],  # ← Enable file search
    attachments=[{"vector_store_id": vs_id}],  # ← Attach vector store
    input=[...],
    text={"format": {"type": "json_object"}}
)
```

---

### Day 3-4: Database Migrations with Alembic

**Tasks**:
1. Install Alembic
2. Initialize migration directory
3. Generate initial migration from current schema
4. Test upgrade/downgrade

**Setup**:
```bash
pip install alembic
alembic init migrations
```

**Configure** (`migrations/env.py`):
```python
from src.models import Base
target_metadata = Base.metadata
```

**Generate Migration**:
```bash
# Create initial migration
alembic revision --autogenerate -m "Initial schema"

# Review generated migration in migrations/versions/

# Apply migration
alembic upgrade head

# Rollback (if needed)
alembic downgrade -1
```

**Future Schema Changes**:
```bash
# Add new column to Document model
# Then generate migration:
alembic revision --autogenerate -m "Add urgency_score column"
alembic upgrade head
```

---

### Day 5: Production Deployment

**Tasks**:
1. Test on production dataset (1000 PDFs)
2. Monitor for 24 hours
3. Document any issues
4. Celebrate shipping! 🎉

**Pre-Deployment Checklist**:
```markdown
- [ ] All tests passing (pytest)
- [ ] Code formatted (black src/ tests/)
- [ ] No secrets in git (.env in .gitignore)
- [ ] Database backup strategy documented
- [ ] Runbook covers common failures
- [ ] Cost estimation matches budget
- [ ] Monitoring dashboard created (jq queries)
```

**Production Run**:
```bash
# Set production API key
export OPENAI_API_KEY=sk-prod-...

# Use production database
export DATABASE_URL=postgresql://user:pass@host/db

# Run with logging
python process_inbox.py 2>&1 | tee production-run.log

# Monitor progress
tail -f production-run.log | jq '.'

# Check stats
cat production-run.log | jq -s '{
  total: length,
  succeeded: map(select(.status == "completed")) | length,
  failed: map(select(.status == "failed")) | length,
  total_cost: map(select(.cost_usd)) | map(.cost_usd) | add
}'
```

---

### Week 4 Success Criteria

- ✅ 1000 PDFs processed in production
- ✅ Vector store contains all PDFs with searchable metadata
- ✅ Database migrations tested (upgrade/downgrade)
- ✅ Total cost < $100 for 1000 PDFs
- ✅ 95%+ success rate
- ✅ Zero data loss on failures

---

## What NOT to Build (Yet)

These are **premature optimizations** - wait for actual problems:

### ❌ Async Processing with `asyncio`
**When to add**: When processing > 100 PDFs/day and speed matters
**Why wait**: Single-threaded is easier to debug, sufficient for current volume

### ❌ Circuit Breaker Pattern
**When to add**: After seeing sustained API failures (>10% error rate)
**Why wait**: Retry logic handles transient failures already

### ❌ Metrics/OpenTelemetry Integration
**When to add**: When simple logs aren't enough for diagnosis
**Why wait**: Adds significant complexity, structured logs work fine

### ❌ Kubernetes Deployment
**When to add**: When you need horizontal scaling across machines
**Why wait**: No service to deploy yet (runs as cron job)

### ❌ GraphQL API
**When to add**: When you have multiple frontend clients needing flexible queries
**Why wait**: No frontend yet, no query requirements

### ❌ 40-Field Database Schema
**When to add**: After validating which fields are actually used
**Why wait**: 10 fields + JSON blob covers all data, simpler to test

---

## Migration Strategy: SQLite → PostgreSQL

**When to migrate**: Week 4 or when dataset > 100,000 PDFs

**Migration Steps**:

1. **Export from SQLite**:
```bash
# Dump SQLite to SQL
sqlite3 paper_autopilot.db .dump > dump.sql

# Or use alembic to generate schema
alembic upgrade head  # Run on PostgreSQL
```

2. **Update DATABASE_URL**:
```bash
# .env
DATABASE_URL=postgresql://user:pass@localhost/paper_autopilot
```

3. **Run migrations**:
```bash
alembic upgrade head
```

4. **Import data** (if needed):
```bash
# Use pgloader for SQLite → PostgreSQL migration
pgloader sqlite://paper_autopilot.db postgresql://user:pass@localhost/paper_autopilot
```

5. **Verify**:
```sql
-- Check record count
SELECT COUNT(*) FROM documents;

-- Check sample records
SELECT * FROM documents LIMIT 10;
```

**No code changes required** - SQLAlchemy abstracts database differences.

---

## Validation Strategy

After each week, run these validation tests:

### Week 1: Database Persistence
```bash
# Process 100 PDFs
python process_inbox.py

# Verify database
sqlite3 paper_autopilot.db "SELECT COUNT(*) FROM documents;"
# Expected: 100

# Reprocess (should skip duplicates)
python process_inbox.py
sqlite3 paper_autopilot.db "SELECT COUNT(*) FROM documents;"
# Expected: Still 100
```

### Week 2: Resilience
```bash
# Simulate rate limit (requires test harness)
# Should retry 5 times with exponential backoff

# Simulate 500 error
# Should retry and succeed

# Simulate 401 error
# Should fail fast (no retry)
```

### Week 3: Observability
```bash
# Calculate total cost
cat autod.log | jq -s 'map(.cost_usd) | add'

# Calculate average processing time
cat autod.log | jq -s 'map(.duration_ms) | add / length'

# Check success rate
cat autod.log | jq -s 'group_by(.status) | map({status: .[0].status, count: length})'
```

### Week 4: Production
```bash
# Process 1000 PDFs
time python process_inbox.py

# Verify vector store
# (Use OpenAI dashboard to check file count)

# Run migrations
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

---

## Red Flags to Watch For

If you find yourself doing any of these, **STOP** and reconsider:

🚩 Writing code for "what if we scale to 1M PDFs?" when you have 10
🚩 Adding dependencies for "nice to have" features before core works
🚩 Designing abstractions before you have 3+ concrete use cases
🚩 Building infrastructure before you have an application
🚩 Optimizing for performance before measuring bottlenecks
🚩 Creating config options for things that never change
🚩 Adding features that aren't solving real problems

**The Right Approach**:
1. Ship minimal viable solution
2. Observe real problems
3. Measure actual bottlenecks
4. Build solutions for concrete issues
5. Repeat

---

## Success Metrics (After 4 Weeks)

Objective measurements of success:

### Functional
- ✅ 1000 PDFs processed successfully
- ✅ Zero duplicate records in database (deduplication works)
- ✅ 95%+ API call success rate (with retries)
- ✅ Structured logs showing stage-by-stage progress

### Cost
- ✅ < $100 total OpenAI costs for 1000-PDF test corpus
- ✅ Average cost per PDF < $0.10
- ✅ Token usage tracked and logged

### Quality
- ✅ 60%+ test coverage with pytest
- ✅ All critical paths tested (dedupe, retry, persistence)
- ✅ Runbook documents recovery procedures
- ✅ Code formatted with black, no linting errors

### Reliability
- ✅ Survives rate limits, timeouts, 500 errors
- ✅ Database consistency maintained on failures
- ✅ Vector store uploads succeed or fail gracefully
- ✅ Can replay failed PDFs without duplication

---

## Timeline Summary

| Week | Focus | Deliverable |
|------|-------|-------------|
| 1 | Foundation | 100 PDFs in database, zero duplicates |
| 2 | Resilience | Retry logic, transaction safety, 95% success rate |
| 3 | Observability | Token tracking, unit tests, cost dashboard |
| 4 | Production | 1000 PDFs processed, vector store integration, migrations |

**Total Investment**: ~15-20 hours (part-time over 4 weeks)

**Outcome**: Production-ready PDF processing system that actually works, with:
- Database persistence and deduplication
- Graceful error handling and retries
- Cost tracking and observability
- Vector store integration for cross-document intelligence
- Migration path to PostgreSQL
- Comprehensive tests and documentation

---

## Next Steps

1. **Read**: `docs/CODE_ARCHITECTURE.md` for implementation patterns
2. **Read**: `docs/adr/0001-iterative-phasing.md` for architectural decisions
3. **Start**: Week 1, Day 1 - Infrastructure setup

**Questions before starting?** Review the runbook and architecture guide first.

**Ready to ship?** Start with the smallest possible change that adds value. ✅
