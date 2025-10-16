# Code Architecture Guide

**Purpose**: Practical patterns and examples for implementing the autoD → Paper Autopilot transformation

**Audience**: Developers implementing the 4-week roadmap

**Status**: Living document (update as patterns evolve)

**Related Docs**:
- [`IMPLEMENTATION_ROADMAP.md`](./IMPLEMENTATION_ROADMAP.md) - 4-week implementation plan
- [`CHANGES_FROM_ORIGINAL_PLAN.md`](./CHANGES_FROM_ORIGINAL_PLAN.md) - Architectural improvements
- [`adr/0001-iterative-phasing-over-parallel-development.md`](./adr/0001-iterative-phasing-over-parallel-development.md) - ADR for iterative approach

---

## Table of Contents

1. [Project Structure](#project-structure)
2. [Configuration Management](#configuration-management)
3. [Database Models](#database-models)
4. [Pipeline Pattern](#pipeline-pattern)
5. [Retry Logic](#retry-logic)
6. [Transaction Safety](#transaction-safety)
7. [Structured Logging](#structured-logging)
8. [Token Tracking](#token-tracking)
9. [Vector Store Integration](#vector-store-integration)
10. [Testing Patterns](#testing-patterns)
11. [Migration Strategy](#migration-strategy)
12. [Error Handling](#error-handling)

---

## Project Structure

### Directory Layout
```
/Users/krisstudio/Developer/Projects/autoD/
├── README.md                       # Project overview
├── CLAUDE.md                       # Claude Code instructions
├── AGENTS.md                       # Repository conventions
├── requirements.txt                # Python dependencies
├── .env.example                    # Environment template
├── .gitignore                      # Git ignore rules
│
├── src/                            # Application code
│   ├── __init__.py
│   ├── config.py                   # Configuration (Pydantic)
│   ├── models.py                   # SQLAlchemy models
│   ├── pipeline.py                 # Pipeline pattern
│   ├── stages/                     # Processing stages
│   │   ├── __init__.py
│   │   ├── sha256_stage.py
│   │   ├── dedupe_stage.py
│   │   ├── api_stage.py
│   │   └── vector_store_stage.py
│   ├── retry_logic.py              # Tenacity retry decorators
│   ├── logging_config.py           # Structured logging
│   ├── token_counter.py            # Token/cost tracking
│   └── vector_store.py             # Vector store operations
│
├── tests/                          # Test suite
│   ├── __init__.py
│   ├── conftest.py                 # Pytest fixtures
│   ├── fixtures/
│   │   └── sample.pdf
│   ├── test_sha256_stage.py
│   ├── test_dedupe_stage.py
│   ├── test_retry_logic.py
│   └── test_pipeline.py
│
├── inbox/                          # PDF input (git-ignored)
│   └── .gitkeep
│
├── migrations/                     # Alembic migrations
│   ├── versions/
│   └── env.py
│
└── docs/                           # Documentation
    ├── IMPLEMENTATION_ROADMAP.md
    ├── CHANGES_FROM_ORIGINAL_PLAN.md
    ├── CODE_ARCHITECTURE.md        # This file
    ├── RUNBOOK.md                  # Operations guide
    ├── adr/                        # Architectural decisions
    │   └── 0001-iterative-phasing-over-parallel-development.md
    └── orientation/
        └── ORIENTATION-2025-10-16.md
```

---

## Configuration Management

### Pattern: Pydantic Settings with Environment Variables

**Why**: Type-safe configuration, environment-based overrides, clear defaults

**File**: `src/config.py`

```python
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional

class Settings(BaseSettings):
    """
    Application configuration loaded from environment variables.

    Example .env file:
        OPENAI_API_KEY=sk-...
        OPENAI_MODEL=gpt-5
        DATABASE_URL=sqlite:///paper_autopilot.db
    """

    # OpenAI Configuration
    openai_api_key: str = Field(..., description="OpenAI API key (required)")
    openai_model: str = Field(default="gpt-5", description="Model to use for processing")
    openai_timeout_seconds: int = Field(default=300, description="API timeout in seconds")
    max_output_tokens: int = Field(default=60000, description="Max tokens for model output")

    # Database Configuration
    database_url: str = Field(
        default="sqlite:///paper_autopilot.db",
        description="SQLAlchemy database URL"
    )

    # Vector Store Configuration
    vector_store_name: str = Field(
        default="paper-autopilot-docs",
        description="Name for OpenAI vector store"
    )
    vector_store_id_file: str = Field(
        default=".vector_store_id",
        description="File to persist vector store ID"
    )

    # Cost Configuration (USD per 1K tokens)
    input_cost_per_1k: float = Field(default=0.01, description="Cost per 1K input tokens")
    cached_input_cost_per_1k: float = Field(default=0.005, description="Cost per 1K cached tokens")
    output_cost_per_1k: float = Field(default=0.03, description="Cost per 1K output tokens")

    # Processing Configuration
    inbox_directory: str = Field(default="inbox", description="Directory to scan for PDFs")
    log_level: str = Field(default="INFO", description="Logging level")
    max_retries: int = Field(default=5, description="Max API retry attempts")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

# Global settings instance
settings = Settings()
```

### Usage
```python
from src.config import settings

# Access configuration
print(f"Using model: {settings.openai_model}")
print(f"Database: {settings.database_url}")

# Environment override
# $ export OPENAI_MODEL=gpt-5-mini
# Now settings.openai_model returns "gpt-5-mini"
```

---

## Database Models

### Pattern: SQLAlchemy 2.0 Declarative Models with Generic JSON Type

**Why**: Cross-database compatibility (SQLite + PostgreSQL), type hints, modern SQLAlchemy

**File**: `src/models.py`

```python
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime, timezone
from typing import Optional, Dict, Any

Base = declarative_base()

class Document(Base):
    """
    Represents a processed PDF document in the system.

    Design Decisions:
    - Uses generic JSON type (not JSONB) for cross-database compatibility
    - SHA-256 hex format for deduplication (unique constraint + index)
    - status field for tracking processing state
    - Stores full API response in metadata_json (nothing lost)
    - Can extract specific fields later via migrations
    """

    __tablename__ = "documents"

    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # File identity (deduplication)
    sha256_hex = Column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
        comment="SHA-256 hash in hexadecimal format for deduplication"
    )
    original_filename = Column(
        String(512),
        nullable=False,
        comment="Original PDF filename from inbox"
    )

    # Timestamps
    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="UTC timestamp when document was first discovered"
    )
    processed_at = Column(
        DateTime,
        nullable=True,
        comment="UTC timestamp when processing completed successfully"
    )

    # OpenAI references
    source_file_id = Column(
        String(64),
        index=True,
        nullable=True,
        comment="OpenAI file ID from Files API upload"
    )
    vector_store_file_id = Column(
        String(64),
        index=True,
        nullable=True,
        comment="OpenAI vector store file ID for cross-document search"
    )

    # Extracted metadata (full JSON response from API)
    metadata_json = Column(
        JSON,  # ← Generic JSON type, works on SQLite AND PostgreSQL
        nullable=True,
        comment="Full structured output from OpenAI Responses API"
    )

    # Status tracking
    status = Column(
        String(32),
        default="pending",
        index=True,
        nullable=False,
        comment="Processing status: pending|processing|completed|failed|vector_upload_failed"
    )
    error_message = Column(
        Text,
        nullable=True,
        comment="Error message if status is failed"
    )

    def __repr__(self) -> str:
        return f"<Document id={self.id} filename={self.original_filename} status={self.status}>"

def init_db(db_url: str):
    """
    Initialize database and return session factory.

    Usage:
        session = init_db("sqlite:///paper_autopilot.db")
        doc = session.query(Document).first()
    """
    engine = create_engine(db_url, future=True, echo=False)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()
```

### Querying Examples
```python
from src.models import Document, init_db

session = init_db("sqlite:///paper_autopilot.db")

# Find by SHA-256
doc = session.query(Document).filter_by(sha256_hex="abc123...").first()

# Find pending documents
pending = session.query(Document).filter_by(status="pending").all()

# Find recent completions
from datetime import timedelta
recent = session.query(Document).filter(
    Document.processed_at >= datetime.now(timezone.utc) - timedelta(days=7)
).all()

# Extract metadata fields
for doc in session.query(Document).filter_by(status="completed").limit(10):
    metadata = doc.metadata_json
    print(f"{doc.original_filename}: {metadata.get('doc_type')}")
```

---

## Pipeline Pattern

### Pattern: Abstract Base Class with Discrete Processing Stages

**Why**: Testable, composable, clear transaction boundaries, observable

**File**: `src/pipeline.py`

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

@dataclass
class ProcessingContext:
    """
    Immutable context passed through pipeline stages.

    Each stage receives a context, performs its operation,
    and returns an updated context.
    """
    # Input
    pdf_path: Path
    pdf_bytes: Optional[bytes] = None

    # File identity
    sha256_hex: Optional[str] = None
    sha256_base64: Optional[str] = None

    # Deduplication
    is_duplicate: bool = False
    existing_doc_id: Optional[int] = None

    # OpenAI
    file_id: Optional[str] = None
    api_response: Optional[Dict[str, Any]] = None
    metadata_json: Optional[Dict[str, Any]] = None

    # Vector store
    vector_store_file_id: Optional[str] = None

    # Database
    document_id: Optional[int] = None

    # Error tracking
    error: Optional[Exception] = None
    failed_at_stage: Optional[str] = None

    # Metrics
    metrics: Dict[str, Any] = field(default_factory=dict)

class ProcessingStage(ABC):
    """
    Abstract base class for pipeline stages.

    Each stage implements a single, testable operation.
    """

    @abstractmethod
    def execute(self, context: ProcessingContext) -> ProcessingContext:
        """
        Execute this stage's logic.

        Args:
            context: Current processing context

        Returns:
            Updated context with results of this stage

        Raises:
            Exception: Stage-specific errors (caught by pipeline)
        """
        pass

    def __str__(self) -> str:
        return self.__class__.__name__

class Pipeline:
    """
    Orchestrates processing stages in sequence.

    Handles logging, error propagation, and metrics collection.
    """

    def __init__(self, stages: List[ProcessingStage]):
        self.stages = stages

    def process(self, initial_context: ProcessingContext) -> ProcessingContext:
        """
        Run all stages in sequence, passing context through.

        If any stage raises an exception, pipeline stops and
        returns context with error information.
        """
        context = initial_context

        for stage in self.stages:
            if context.error:
                # Previous stage failed, skip remaining stages
                logger.warning(f"Skipping {stage} due to previous error")
                break

            try:
                logger.info(f"Executing {stage}", extra={
                    "pdf_path": str(context.pdf_path),
                    "stage": str(stage)
                })

                context = stage.execute(context)

                logger.info(f"Completed {stage}", extra={
                    "pdf_path": str(context.pdf_path),
                    "stage": str(stage)
                })

            except Exception as e:
                logger.error(f"Failed at {stage}: {e}", exc_info=True, extra={
                    "pdf_path": str(context.pdf_path),
                    "stage": str(stage)
                })
                context.error = e
                context.failed_at_stage = str(stage)
                break

        return context
```

### Example Stage Implementations

**File**: `src/stages/sha256_stage.py`
```python
import hashlib
import base64
from src.pipeline import ProcessingStage, ProcessingContext

class ComputeSHA256Stage(ProcessingStage):
    """
    Compute SHA-256 hash of PDF file.

    Outputs:
    - context.sha256_hex: Hexadecimal hash string (64 chars)
    - context.sha256_base64: Base64-encoded hash (for OpenAI attributes)
    """

    def execute(self, context: ProcessingContext) -> ProcessingContext:
        # Read file if not already loaded
        if context.pdf_bytes is None:
            with open(context.pdf_path, "rb") as f:
                context.pdf_bytes = f.read()

        # Compute hash
        h = hashlib.sha256(context.pdf_bytes)
        digest = h.digest()

        context.sha256_hex = h.hexdigest()
        context.sha256_base64 = base64.b64encode(digest).decode("ascii")

        context.metrics["file_size_bytes"] = len(context.pdf_bytes)

        return context
```

**File**: `src/stages/dedupe_stage.py`
```python
from src.pipeline import ProcessingStage, ProcessingContext
from src.models import Document

class DedupeCheckStage(ProcessingStage):
    """
    Check if document already exists in database (by SHA-256).

    Outputs:
    - context.is_duplicate: True if document exists
    - context.existing_doc_id: ID of existing document (if duplicate)
    """

    def __init__(self, session):
        self.session = session

    def execute(self, context: ProcessingContext) -> ProcessingContext:
        existing = self.session.query(Document).filter_by(
            sha256_hex=context.sha256_hex
        ).first()

        if existing:
            context.is_duplicate = True
            context.existing_doc_id = existing.id
        else:
            context.is_duplicate = False

        context.metrics["is_duplicate"] = context.is_duplicate

        return context
```

### Pipeline Usage
```python
from src.pipeline import Pipeline, ProcessingContext
from src.stages.sha256_stage import ComputeSHA256Stage
from src.stages.dedupe_stage import DedupeCheckStage
from pathlib import Path

# Construct pipeline
session = init_db("sqlite:///paper_autopilot.db")
pipeline = Pipeline([
    ComputeSHA256Stage(),
    DedupeCheckStage(session),
    # Add more stages here
])

# Process a PDF
pdf_path = Path("inbox/sample.pdf")
context = ProcessingContext(pdf_path=pdf_path)
result = pipeline.process(context)

if result.error:
    print(f"Failed at {result.failed_at_stage}: {result.error}")
elif result.is_duplicate:
    print(f"Duplicate of document {result.existing_doc_id}")
else:
    print(f"New document, SHA-256: {result.sha256_hex}")
```

---

## Retry Logic

### Pattern: Comprehensive Retry Predicate with Tenacity

**Why**: Handle ALL transient errors, not just rate limits

**File**: `src/retry_logic.py`

```python
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception,
    before_sleep_log,
)
from openai import RateLimitError, APIConnectionError, APIError, Timeout
import logging

logger = logging.getLogger(__name__)

def is_retryable_api_error(exception: Exception) -> bool:
    """
    Determine if an OpenAI API error should be retried.

    Retryable errors (transient):
    - RateLimitError (429): Rate limit exceeded
    - APIConnectionError: Network connectivity issues
    - Timeout: Request timed out
    - APIError with 5xx status: Server-side errors

    Non-retryable errors (permanent):
    - AuthenticationError (401): Invalid API key
    - PermissionDeniedError (403): Insufficient permissions
    - BadRequestError (400): Malformed request
    - NotFoundError (404): Resource doesn't exist
    - APIError with 4xx status: Client errors

    Returns:
        True if error should be retried, False otherwise
    """
    # Always retry rate limits, connection errors, timeouts
    if isinstance(exception, (RateLimitError, APIConnectionError, Timeout)):
        logger.info(f"Retryable error: {type(exception).__name__}")
        return True

    # Retry server errors (5xx), but not client errors (4xx)
    if isinstance(exception, APIError):
        if hasattr(exception, 'status_code'):
            status_code = exception.status_code
            is_server_error = status_code >= 500
            logger.info(f"API error {status_code}: retryable={is_server_error}")
            return is_server_error
        # Unknown API error - don't retry
        return False

    # Don't retry unknown exceptions
    return False

@retry(
    retry=retry_if_exception(is_retryable_api_error),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def call_openai_with_retry(client, **kwargs):
    """
    Call OpenAI Responses API with exponential backoff retry.

    Retry schedule:
    - Attempt 1: immediate
    - Attempt 2: wait 2s
    - Attempt 3: wait 4s
    - Attempt 4: wait 8s
    - Attempt 5: wait 16s (then give up)

    Max total wait: ~30 seconds across all retries

    Args:
        client: OpenAI client instance
        **kwargs: Arguments to pass to client.responses.create()

    Returns:
        API response object

    Raises:
        Exception: After 5 failed attempts, re-raises the last exception
    """
    logger.info("Calling OpenAI Responses API")
    return client.responses.create(**kwargs)
```

### Usage Example
```python
from openai import OpenAI
from src.config import settings
from src.retry_logic import call_openai_with_retry

client = OpenAI(api_key=settings.openai_api_key)

try:
    response = call_openai_with_retry(
        client,
        model=settings.openai_model,
        input=[{
            "role": "user",
            "content": [
                {"type": "input_text", "text": "Extract metadata"},
                {"type": "input_file", "filename": "doc.pdf", "file_data": "data:..."}
            ]
        }],
        text={"format": {"type": "json_object"}}
    )
    print("Success!")
except Exception as e:
    print(f"Failed after 5 retries: {e}")
```

---

## Transaction Safety

### Pattern: Compensating Transactions for External API Calls

**Why**: Prevent orphaned records when DB commits but vector store uploads fail

**File**: `src/transactions.py`

```python
from contextlib import contextmanager
import logging
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

@contextmanager
def compensating_transaction(session: Session, compensate_fn=None):
    """
    Context manager providing compensation logic if commit fails.

    Usage:
        def cleanup_openai_file(file_id):
            client.files.delete(file_id)

        with compensating_transaction(session, lambda: cleanup_openai_file(file_id)):
            doc = Document(...)
            session.add(doc)
            # If commit succeeds → no compensation
            # If commit fails → compensation runs, then re-raises

    Args:
        session: SQLAlchemy session
        compensate_fn: Callable to run if commit fails (cleanup external resources)
    """
    try:
        yield session
        session.commit()
        logger.info("Transaction committed successfully")
    except Exception as e:
        session.rollback()
        logger.error(f"Transaction failed, rolling back: {e}", exc_info=True)

        # Run compensation (cleanup external resources)
        if compensate_fn:
            try:
                logger.info("Running compensation logic")
                compensate_fn()
                logger.info("Compensation completed successfully")
            except Exception as comp_err:
                # Log but don't mask original error
                logger.error(f"Compensation failed: {comp_err}", exc_info=True)

        raise e  # Re-raise original exception
```

### Alternative: Best-Effort Pattern (Simpler)
```python
from src.models import Document

# Step 1: Write to DB first (source of truth)
doc = Document(
    sha256_hex=sha_hex,
    original_filename=pdf_path.name,
    source_file_id=file_id,
    status="pending_vector_upload"
)
session.add(doc)
session.commit()

# Step 2: Upload to vector store (best-effort)
try:
    vs_file_id = add_to_vector_store(vector_store_id, file_id)
    doc.vector_store_file_id = vs_file_id
    doc.status = "completed"
    session.commit()
    logger.info(f"Vector store upload succeeded for doc {doc.id}")
except Exception as e:
    # Database is authoritative; vector store is supplementary
    doc.status = "vector_upload_failed"
    doc.error_message = str(e)
    session.commit()
    logger.warning(f"Vector store upload failed for doc {doc.id}: {e}")
    # Don't fail entire pipeline - can retry later
```

---

## Structured Logging

### Pattern: JSON Formatter with Contextual Metadata

**Why**: Queryable logs, cost/performance analysis, production debugging

**File**: `src/logging_config.py`

```python
import logging
import json
from datetime import datetime
from typing import Any, Dict

class JSONFormatter(logging.Formatter):
    """
    Format log records as JSON for structured logging.

    Automatically extracts extra fields from LogRecord and
    includes them in JSON output.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_obj: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }

        # Add exception info if present
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        # Add extra context from logger.info(..., extra={...})
        extra_fields = [
            "pdf_path", "sha256_hex", "doc_id", "stage",
            "duration_ms", "cost_usd", "prompt_tokens", "output_tokens",
            "is_duplicate", "status", "file_size_bytes"
        ]
        for field in extra_fields:
            if hasattr(record, field):
                log_obj[field] = getattr(record, field)

        return json.dumps(log_obj)

def setup_logging(log_level: str = "INFO", log_file: str = "autod.log"):
    """
    Configure structured logging for the application.

    Args:
        log_level: Logging level (INFO, DEBUG, WARNING, ERROR)
        log_file: File to write logs to (default: autod.log)

    Returns:
        Configured logger instance
    """
    # Create logger
    logger = logging.getLogger("autod")
    logger.setLevel(getattr(logging, log_level.upper()))

    # Console handler (pretty-printed for development)
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s"
    ))

    # File handler (JSON for production analysis)
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(JSONFormatter())

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger
```

### Usage
```python
from src.logging_config import setup_logging

logger = setup_logging(log_level="INFO", log_file="autod.log")

# Basic logging
logger.info("Processing started")

# With contextual metadata
logger.info("PDF discovered", extra={
    "pdf_path": str(pdf_path),
    "file_size_bytes": pdf_path.stat().st_size
})

# With performance metrics
logger.info("API call completed", extra={
    "doc_id": doc.id,
    "duration_ms": 1234,
    "cost_usd": 0.05,
    "prompt_tokens": 500,
    "output_tokens": 200
})
```

### Querying JSON Logs
```bash
# Count by status
cat autod.log | jq -s 'group_by(.status) | map({status: .[0].status, count: length})'

# Average processing time
cat autod.log | jq -s 'map(select(.duration_ms)) | add / length'

# Total cost
cat autod.log | jq -s 'map(select(.cost_usd)) | map(.cost_usd) | add'

# Find errors
cat autod.log | jq 'select(.level == "ERROR")'

# Cost per PDF
cat autod.log | jq -s 'group_by(.pdf_path) | map({pdf: .[0].pdf_path, cost: map(.cost_usd) | add})'
```

---

## Token Tracking

### Pattern: tiktoken for Estimation, API Response for Actuals

**Why**: Accurate cost tracking, performance monitoring, budget validation

**File**: `src/token_counter.py`

```python
import tiktoken
from typing import Dict, Any
from src.config import settings

def get_tokenizer(model: str):
    """
    Get tiktoken encoder for a given model.

    Falls back to o200k_base (GPT-5) if model not found,
    then to cl100k_base (GPT-4) as last resort.
    """
    try:
        return tiktoken.encoding_for_model(model)
    except KeyError:
        # GPT-5 typically uses o200k_base encoding
        try:
            return tiktoken.get_encoding("o200k_base")
        except Exception:
            # Fallback to cl100k_base (GPT-4)
            return tiktoken.get_encoding("cl100k_base")

def estimate_tokens(text: str, model: str = None) -> int:
    """
    Estimate token count for text.

    Use this for pre-flight cost estimation.
    """
    model = model or settings.openai_model
    enc = get_tokenizer(model)
    return len(enc.encode(text or ""))

def calculate_cost(usage: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate cost from API response usage object.

    Args:
        usage: Usage object from OpenAI API response
               (response.usage.__dict__)

    Returns:
        Dictionary with token counts and estimated cost
    """
    prompt_tokens = usage.get("prompt_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)

    # Extract cached tokens (if prompt caching enabled)
    prompt_details = usage.get("prompt_tokens_details", {})
    cached_tokens = prompt_details.get("cached_tokens", 0)

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
        "billable_prompt_tokens": billable_input,
        "output_tokens": output_tokens,
        "total_tokens": prompt_tokens + output_tokens,
        "estimated_cost_usd": round(cost, 6)
    }
```

### Usage
```python
from openai import OpenAI
from src.config import settings
from src.token_counter import estimate_tokens, calculate_cost

client = OpenAI(api_key=settings.openai_api_key)

# Pre-flight estimation
prompt_text = "Extract metadata from this PDF..."
estimated = estimate_tokens(prompt_text, settings.openai_model)
print(f"Estimated prompt tokens: {estimated}")

# After API call
response = client.responses.create(...)

# Extract actual usage and cost
usage_stats = calculate_cost(response.usage.__dict__)
print(f"Actual cost: ${usage_stats['estimated_cost_usd']:.4f}")
print(f"Cached tokens: {usage_stats['cached_prompt_tokens']}")

# Log for analysis
logger.info("API call completed", extra={
    **usage_stats,
    "doc_id": doc.id
})
```

---

## Vector Store Integration

### Pattern: Persistent Vector Store with File Attributes

**Why**: Cross-document context, deduplication, File Search tool

**File**: `src/vector_store.py`

```python
from openai import OpenAI
from pathlib import Path
from typing import Optional, Dict, Any
from src.config import settings
import logging

logger = logging.getLogger(__name__)

client = OpenAI(api_key=settings.openai_api_key)

def get_or_create_vector_store() -> str:
    """
    Load persistent vector store ID or create new.

    Vector store ID is saved to file so it persists across runs.
    """
    vs_id_path = Path(settings.vector_store_id_file)

    if vs_id_path.exists():
        vs_id = vs_id_path.read_text().strip()
        logger.info(f"Using existing vector store: {vs_id}")
        return vs_id

    # Create new vector store
    vs = client.vector_stores.create(name=settings.vector_store_name)
    vs_id_path.write_text(vs.id)
    logger.info(f"Created new vector store: {vs.id}")
    return vs.id

def add_file_to_vector_store(
    vector_store_id: str,
    file_id: str,
    *,
    attributes: Optional[Dict[str, Any]] = None
) -> str:
    """
    Attach file to vector store with optional metadata attributes.

    Args:
        vector_store_id: ID of vector store
        file_id: OpenAI file ID (from Files API upload)
        attributes: Metadata attributes (max 16 key-value pairs)

    Returns:
        Vector store file ID

    Raises:
        Exception: If upload fails
    """
    vs_file = client.vector_stores.files.create(
        vector_store_id=vector_store_id,
        file_id=file_id
    )

    # Update attributes if provided
    if attributes:
        # Limit to 16 attributes (OpenAI API limit)
        limited_attrs = dict(list(attributes.items())[:16])

        client.vector_stores.files.update(
            vector_store_id=vector_store_id,
            file_id=vs_file.id,
            attributes=limited_attrs
        )

    logger.info(f"Added file {file_id} to vector store {vector_store_id}")
    return vs_file.id

def create_api_request_with_file_search(
    vector_store_id: str,
    prompt: str,
    model: str = None
) -> Dict[str, Any]:
    """
    Create Responses API request with File Search tool enabled.

    Usage:
        vs_id = get_or_create_vector_store()
        request = create_api_request_with_file_search(vs_id, "Extract metadata...")
        response = client.responses.create(**request)
    """
    model = model or settings.openai_model

    return {
        "model": model,
        "tools": [{"type": "file_search"}],  # Enable File Search
        "attachments": [{"vector_store_id": vector_store_id}],
        "input": [{
            "role": "user",
            "content": [{"type": "input_text", "text": prompt}]
        }],
        "text": {"format": {"type": "json_object"}}
    }
```

### Usage
```python
from src.vector_store import get_or_create_vector_store, add_file_to_vector_store

# One-time setup
vs_id = get_or_create_vector_store()

# After uploading file to OpenAI
file_id = "file-abc123..."
vs_file_id = add_file_to_vector_store(
    vs_id,
    file_id,
    attributes={
        "sha256": sha_hex,
        "filename": pdf_path.name,
        "doc_type": "UtilityBill"
    }
)

# Store in database
doc.vector_store_file_id = vs_file_id
session.commit()

# Later: Use File Search in API requests
from src.vector_store import create_api_request_with_file_search

request = create_api_request_with_file_search(vs_id, "Find similar documents")
response = client.responses.create(**request)
```

---

## Testing Patterns

### Pattern: Pytest with Fixtures and Mocks

**Why**: Isolated tests, fast feedback, high coverage

**File**: `tests/conftest.py`

```python
import pytest
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models import Base

@pytest.fixture
def db_session():
    """
    Create in-memory SQLite session for testing.

    Each test gets a fresh database with no state carryover.
    """
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

@pytest.fixture
def sample_pdf(tmp_path):
    """
    Create a minimal PDF file for testing.

    Returns path to temporary PDF file.
    """
    pdf_path = tmp_path / "sample.pdf"
    # Minimal valid PDF structure
    pdf_content = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n%%EOF"
    pdf_path.write_bytes(pdf_content)
    return pdf_path

@pytest.fixture
def mock_openai_client(monkeypatch):
    """
    Mock OpenAI client for testing without API calls.
    """
    class MockResponse:
        def __init__(self):
            self.usage = type('obj', (object,), {
                'prompt_tokens': 100,
                'output_tokens': 50,
                'prompt_tokens_details': {'cached_tokens': 0}
            })
            self.output = [{
                "role": "assistant",
                "content": [{"type": "output_text", "text": '{"doc_type": "Invoice"}'}]
            }]

    class MockClient:
        class responses:
            @staticmethod
            def create(**kwargs):
                return MockResponse()

    return MockClient()
```

### Test Examples

**File**: `tests/test_sha256_stage.py`
```python
from src.stages.sha256_stage import ComputeSHA256Stage
from src.pipeline import ProcessingContext

def test_sha256_computation(sample_pdf):
    """SHA-256 hash is computed correctly."""
    stage = ComputeSHA256Stage()
    context = ProcessingContext(pdf_path=sample_pdf)

    result = stage.execute(context)

    assert result.sha256_hex is not None
    assert len(result.sha256_hex) == 64  # SHA-256 hex = 64 chars
    assert result.sha256_base64 is not None

def test_sha256_consistency(sample_pdf):
    """Same file produces same hash."""
    stage = ComputeSHA256Stage()
    context = ProcessingContext(pdf_path=sample_pdf)

    result1 = stage.execute(context)
    result2 = stage.execute(context)

    assert result1.sha256_hex == result2.sha256_hex
```

**File**: `tests/test_dedupe_stage.py`
```python
from src.stages.dedupe_stage import DedupeCheckStage
from src.pipeline import ProcessingContext
from src.models import Document

def test_detects_duplicate(db_session, sample_pdf):
    """Duplicate documents are detected."""
    sha_hex = "abc123..."

    # Add document to DB
    doc = Document(sha256_hex=sha_hex, original_filename="test.pdf")
    db_session.add(doc)
    db_session.commit()

    # Check for duplicate
    stage = DedupeCheckStage(db_session)
    context = ProcessingContext(pdf_path=sample_pdf, sha256_hex=sha_hex)
    result = stage.execute(context)

    assert result.is_duplicate == True
    assert result.existing_doc_id == doc.id

def test_detects_new_document(db_session, sample_pdf):
    """New documents are not flagged as duplicates."""
    stage = DedupeCheckStage(db_session)
    context = ProcessingContext(pdf_path=sample_pdf, sha256_hex="new_hash_123")
    result = stage.execute(context)

    assert result.is_duplicate == False
    assert result.existing_doc_id is None
```

### Running Tests
```bash
# Run all tests
pytest

# With coverage
pytest --cov=src --cov-report=html

# Specific test file
pytest tests/test_sha256_stage.py -v

# Run only tests matching pattern
pytest -k "dedupe" -v

# Stop on first failure
pytest -x
```

---

## Migration Strategy

### Pattern: Alembic for Schema Evolution

**Why**: Version control for database schema, safe upgrades/downgrades

**Setup**:
```bash
pip install alembic
alembic init migrations
```

**Configure**: Edit `migrations/env.py`
```python
from src.models import Base

# Set target metadata
target_metadata = Base.metadata
```

**Generate Migration**:
```bash
# Initial schema
alembic revision --autogenerate -m "Initial schema: documents table"

# Review generated file in migrations/versions/

# Apply migration
alembic upgrade head

# Rollback one version
alembic downgrade -1
```

**Example Migration** (adding a new column):
```python
# migrations/versions/abc123_add_urgency_score.py
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.add_column('documents', sa.Column('urgency_score', sa.Integer, nullable=True))

def downgrade():
    op.drop_column('documents', 'urgency_score')
```

### SQLite → PostgreSQL Migration
```bash
# 1. Update .env
DATABASE_URL=postgresql://user:pass@localhost/paper_autopilot

# 2. Run migrations on PostgreSQL
alembic upgrade head

# 3. Use pgloader to copy data
pgloader sqlite://paper_autopilot.db postgresql://user:pass@localhost/paper_autopilot

# 4. Verify
psql -U user -d paper_autopilot -c "SELECT COUNT(*) FROM documents;"
```

---

## Error Handling

### Pattern: Graceful Degradation with Audit Trail

**Why**: No data loss on failures, clear recovery path

**Example: API Call with Fallback**
```python
from src.models import Document

try:
    # Attempt API call
    response = call_openai_with_retry(client, ...)

    # Success path
    doc.metadata_json = extract_metadata(response)
    doc.status = "completed"
    doc.processed_at = datetime.now(timezone.utc)

except Exception as e:
    # Failure path - preserve document for retry
    doc.status = "failed"
    doc.error_message = str(e)[:1000]  # Truncate long errors

    logger.error(f"Processing failed for {pdf_path}: {e}", exc_info=True, extra={
        "pdf_path": str(pdf_path),
        "doc_id": doc.id,
        "sha256_hex": doc.sha256_hex
    })

finally:
    # Always commit (preserves audit trail)
    session.commit()
```

**Example: Retry Failed Documents**
```python
# Find all failed documents
failed_docs = session.query(Document).filter_by(status="failed").all()

for doc in failed_docs:
    try:
        # Reprocess
        pdf_path = Path("inbox") / doc.original_filename
        if not pdf_path.exists():
            logger.warning(f"File not found: {pdf_path}")
            continue

        # Run pipeline again
        context = pipeline.process(ProcessingContext(pdf_path=pdf_path))

        if not context.error:
            doc.status = "completed"
            doc.error_message = None
    except Exception as e:
        logger.error(f"Retry failed for doc {doc.id}: {e}")

    session.commit()
```

---

## Summary: Key Patterns

1. **Configuration**: Pydantic Settings for type-safe, environment-based config
2. **Database**: SQLAlchemy with generic JSON type for cross-database compatibility
3. **Pipeline**: Abstract stages for testability and composability
4. **Retry**: Comprehensive predicate handles all transient errors
5. **Transactions**: Compensating transactions or best-effort for external APIs
6. **Logging**: Structured JSON logs with contextual metadata
7. **Tokens**: tiktoken for estimation, API response for actuals
8. **Vector Stores**: Persistent vector store with file attributes
9. **Testing**: Pytest with fixtures and mocks for isolation
10. **Migrations**: Alembic for schema evolution
11. **Errors**: Graceful degradation with audit trail

---

## References

- [`IMPLEMENTATION_ROADMAP.md`](./IMPLEMENTATION_ROADMAP.md) - Week-by-week plan
- [`CHANGES_FROM_ORIGINAL_PLAN.md`](./CHANGES_FROM_ORIGINAL_PLAN.md) - Architectural improvements
- [`adr/0001-iterative-phasing-over-parallel-development.md`](./adr/0001-iterative-phasing-over-parallel-development.md) - ADR for iterative approach
- [SQLAlchemy 2.0 Docs](https://docs.sqlalchemy.org/en/20/)
- [Tenacity Docs](https://tenacity.readthedocs.io/)
- [tiktoken Docs](https://github.com/openai/tiktoken)
- [Alembic Docs](https://alembic.sqlalchemy.org/)

---

*Last Updated: 2025-10-16*
*Status: Living document - update as patterns evolve*
