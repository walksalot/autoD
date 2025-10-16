# API Documentation — autoD Python Modules

**Purpose**: Comprehensive API reference for all Python modules in the autoD project

**Audience**: Developers integrating with autoD components, writing tests, or extending functionality

**Last Updated**: 2025-10-16

---

## Table of Contents

1. [Overview](#overview)
2. [Configuration (`src/config.py`)](#configuration-srcconfigpy)
3. [Database Models (`src/models.py`)](#database-models-srcmodelspy)
4. [Database Manager (`src/database.py`)](#database-manager-srcdatabasepy)
5. [JSON Schema (`src/schema.py`)](#json-schema-srcschempy)
6. [Prompts (`src/prompts.py`)](#prompts-srcpromptspy)
7. [Deduplication (`src/dedupe.py`)](#deduplication-srcdedupepy)
8. [API Client (`src/api_client.py`)](#api-client-srcapi_clientpy)
9. [Token Counter (`src/token_counter.py`)](#token-counter-srctoken_counterpy)
10. [Vector Store (`src/vector_store.py`)](#vector-store-srcvector_storepy)
11. [Logging (`src/logging_config.py`)](#logging-srclogging_configpy)
12. [Processor (`src/processor.py`)](#processor-srcprocessorpy)

---

## Overview

The autoD codebase is organized into 12 core modules, each with a specific responsibility:

**Configuration & Infrastructure**:
- `config.py` - Type-safe configuration with Pydantic V2
- `logging_config.py` - Structured JSON logging
- `database.py` - Database session management

**Data Models & Schema**:
- `models.py` - SQLAlchemy 2.0 Document model
- `schema.py` - JSON Schema for OpenAI structured outputs

**Processing Pipeline**:
- `processor.py` - Main orchestration layer
- `dedupe.py` - SHA-256 deduplication
- `api_client.py` - OpenAI Responses API client
- `prompts.py` - Three-role prompt architecture
- `token_counter.py` - Token counting and cost estimation
- `vector_store.py` - OpenAI Vector Store integration

**Import Hierarchy**:
```
config.py (no dependencies)
  ↓
logging_config.py → depends on config
models.py → depends on nothing (pure SQLAlchemy)
database.py → depends on models
  ↓
schema.py → depends on config
prompts.py → depends on config, schema
dedupe.py → depends on models, logging_config
api_client.py → depends on config, logging_config
token_counter.py → depends on config, logging_config
vector_store.py → depends on config, logging_config
  ↓
processor.py → depends on ALL above modules
```

---

## Configuration (`src/config.py`)

### Overview

Pydantic V2-based configuration management with strict validation, immutability, and model restrictions.

### Classes

#### `Config`

```python
class Config(BaseSettings):
    """
    Immutable application configuration loaded from environment variables.

    All fields use Field() with validation. Supports .env files for local development.
    """
```

**Key Features**:
- **Immutability**: `model_config = ConfigDict(frozen=True)` prevents accidental modification
- **Model Validation**: Only allows Frontier models (gpt-5-mini, gpt-5, gpt-5-nano, gpt-5-pro, gpt-4.1)
- **Environment Variables**: Automatically loads from `.env` file
- **Type Safety**: Full type hints with Pydantic validators

**Fields** (54 total):

**OpenAI Configuration**:
```python
openai_api_key: SecretStr  # Required, never logged
openai_model: str  # Validated against allowed_models list
openai_timeout_seconds: int = 300
max_output_tokens: int = 60_000
```

**Database Configuration**:
```python
paper_autopilot_db_url: str = "sqlite:///paper_autopilot.db"
db_pool_size: int = 5
db_max_overflow: int = 10
db_pool_timeout: int = 30
```

**Vector Store Configuration**:
```python
vector_store_name: str = "paper-autopilot-docs"
vector_store_id_file: Path = Path(".vector_store_id")
```

**Cost Configuration** (USD per 1M tokens):
```python
prompt_token_price_per_million: float = 0.075
completion_token_price_per_million: float = 0.300
cached_token_price_per_million: float = 0.0375
```

**Processing Configuration**:
```python
inbox_dir: Path = Path("inbox")
processed_dir: Path = Path("processed")
failed_dir: Path = Path("failed")
batch_size: int = 10
skip_duplicates: bool = True
```

**Logging Configuration**:
```python
log_level: str = "INFO"
log_format: str = "json"  # "json" or "text"
log_file: Path = Path("logs/paper_autopilot.log")
```

**Retry Configuration**:
```python
max_retries: int = 5
retry_min_wait_seconds: int = 2
retry_max_wait_seconds: int = 60
```

**Cost Alert Thresholds**:
```python
cost_alert_per_document_threshold: float = 1.00
cost_alert_hourly_threshold: float = 10.00
cost_alert_daily_threshold: float = 100.00
```

**Validators**:
```python
@field_validator("openai_model")
@classmethod
def validate_model(cls, v: str) -> str:
    """
    Validate OpenAI model is from approved Frontier models list.

    Raises ValueError if model is not in allowed list.
    """
```

### Functions

#### `get_config()`

```python
def get_config(env_file: Optional[Path] = None) -> Config:
    """
    Get singleton configuration instance.

    Args:
        env_file: Path to .env file (default: .env in current directory)

    Returns:
        Config: Singleton configuration instance

    Example:
        config = get_config()
        print(config.openai_model)  # "gpt-5-mini"
    """
```

**Singleton Pattern**: Ensures only one Config instance exists per process.

### Usage Examples

```python
from src.config import get_config

# Get configuration
config = get_config()

# Access configuration values
api_key = config.openai_api_key.get_secret_value()
model = config.openai_model
db_url = config.paper_autopilot_db_url

# Configuration is immutable
try:
    config.openai_model = "gpt-4o"  # Raises ValidationError
except Exception as e:
    print(f"Cannot modify: {e}")

# Environment variable override
# export OPENAI_MODEL=gpt-5-nano
# Now config.openai_model returns "gpt-5-nano"
```

---

## Database Models (`src/models.py`)

### Overview

SQLAlchemy 2.0 declarative model for the `documents` table with 40+ fields for comprehensive metadata storage.

### Classes

#### `Document`

```python
class Document(Base):
    """
    Document model representing a processed PDF in the database.

    Design:
    - Generic JSON type (not JSONB) for SQLite/PostgreSQL compatibility
    - SHA-256 hex for deduplication (unique constraint + index)
    - Comprehensive metadata fields extracted from OpenAI Responses API
    - Nullable fields for graceful degradation
    """
    __tablename__ = "documents"
```

**Primary Key**:
```python
id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
```

**File Identity** (deduplication keys):
```python
sha256_hex: Mapped[str] = mapped_column(String(64), unique=True, index=True)
sha256_base64: Mapped[str] = mapped_column(String(100))
original_filename: Mapped[str] = mapped_column(String(512))
file_size_bytes: Mapped[int]
page_count: Mapped[Optional[int]]
```

**Timestamps**:
```python
created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
processed_at: Mapped[Optional[datetime]]
```

**OpenAI References**:
```python
source_file_id: Mapped[Optional[str]] = mapped_column(String(100), index=True)
vector_store_id: Mapped[Optional[str]] = mapped_column(String(100), index=True)
vector_store_file_id: Mapped[Optional[str]] = mapped_column(String(100), index=True)
vector_store_attributes: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
```

**Classification**:
```python
doc_type: Mapped[Optional[str]] = mapped_column(String(100), index=True)
doc_subtype: Mapped[Optional[str]] = mapped_column(String(100))
confidence_score: Mapped[Optional[float]]
```

**Parties**:
```python
issuer: Mapped[Optional[str]] = mapped_column(String(255), index=True)
recipient: Mapped[Optional[str]] = mapped_column(String(255))
```

**Dates**:
```python
primary_date: Mapped[Optional[date]]
secondary_date: Mapped[Optional[date]]
```

**Financial**:
```python
total_amount: Mapped[Optional[float]]
currency: Mapped[Optional[str]] = mapped_column(String(10))
```

**Content**:
```python
summary: Mapped[Optional[str]] = mapped_column(Text)
action_items: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
deadlines: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
urgency_level: Mapped[Optional[str]] = mapped_column(String(20))
tags: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
ocr_text_excerpt: Mapped[Optional[str]] = mapped_column(Text)
language_detected: Mapped[Optional[str]] = mapped_column(String(50))
extraction_quality: Mapped[Optional[str]] = mapped_column(String(20))
requires_review: Mapped[bool] = mapped_column(default=False)
```

**Processing Metadata**:
```python
model_used: Mapped[Optional[str]] = mapped_column(String(50))
prompt_tokens: Mapped[Optional[int]]
completion_tokens: Mapped[Optional[int]]
cached_tokens: Mapped[Optional[int]] = mapped_column(default=0)
total_cost_usd: Mapped[Optional[float]]
processing_duration_seconds: Mapped[Optional[float]]
raw_response_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
```

**Methods**:
```python
def __repr__(self) -> str:
    """String representation showing ID, filename, and doc_type."""
```

### Usage Examples

```python
from src.models import Document
from src.database import DatabaseManager
from datetime import datetime, timezone, date

# Create database manager
db_manager = DatabaseManager("sqlite:///paper_autopilot.db")

# Create new document
with db_manager.get_session() as session:
    doc = Document(
        sha256_hex="abc123...",
        sha256_base64="qwE1234...",
        original_filename="invoice_2024.pdf",
        file_size_bytes=245678,
        page_count=3,
        doc_type="Invoice",
        issuer="Acme Corp",
        primary_date=date(2024, 10, 15),
        total_amount=1234.56,
        currency="USD",
        summary="Q4 2024 services invoice",
        model_used="gpt-5-mini",
        prompt_tokens=1500,
        completion_tokens=300,
        cached_tokens=1200,
        total_cost_usd=0.045,
        processing_duration_seconds=4.2,
    )
    session.add(doc)
    session.commit()

    print(f"Created document ID: {doc.id}")

# Query by SHA-256
with db_manager.get_session() as session:
    existing = session.query(Document).filter_by(sha256_hex="abc123...").first()
    if existing:
        print(f"Duplicate found: {existing.id}")

# Query by date range
from datetime import timedelta
with db_manager.get_session() as session:
    recent = session.query(Document).filter(
        Document.processed_at >= datetime.now(timezone.utc) - timedelta(days=7)
    ).all()
    print(f"Processed in last 7 days: {len(recent)} documents")
```

---

## Database Manager (`src/database.py`)

### Overview

Database session management with connection pooling, health checks, and context managers.

### Classes

#### `DatabaseManager`

```python
class DatabaseManager:
    """
    Manages database connections and sessions.

    Features:
    - Connection pooling (configurable pool size)
    - Health check method
    - Context manager for automatic commit/rollback
    - Supports SQLite (dev) and PostgreSQL (production)
    """
```

**Constructor**:
```python
def __init__(self, db_url: Optional[str] = None):
    """
    Initialize database manager.

    Args:
        db_url: SQLAlchemy database URL (default: from config)

    Example:
        db = DatabaseManager("sqlite:///paper_autopilot.db")
        db = DatabaseManager("postgresql://user:pass@localhost/paper_autopilot")
    """
```

**Methods**:

##### `create_tables()`
```python
def create_tables(self) -> None:
    """
    Create all tables defined in models.

    Idempotent - safe to call multiple times.
    """
```

##### `get_session()`
```python
@contextmanager
def get_session(self) -> Generator[Session, None, None]:
    """
    Context manager providing database session.

    Automatically commits on success, rollback on exception.

    Usage:
        with db.get_session() as session:
            doc = Document(...)
            session.add(doc)
            # Automatically committed here
    """
```

##### `health_check()`
```python
def health_check(self) -> bool:
    """
    Verify database connectivity.

    Returns:
        bool: True if database is accessible, False otherwise

    Example:
        if db.health_check():
            print("Database OK")
        else:
            print("Database connection failed")
    """
```

### Usage Examples

```python
from src.database import DatabaseManager
from src.models import Document

# Initialize with default config
db = DatabaseManager()

# Create tables (idempotent)
db.create_tables()

# Health check
if db.health_check():
    print("Database connected")

# Use session context manager
with db.get_session() as session:
    # Add document
    doc = Document(sha256_hex="abc123...", original_filename="test.pdf")
    session.add(doc)
    # Automatically committed when exiting context

# Query documents
with db.get_session() as session:
    docs = session.query(Document).limit(10).all()
    for doc in docs:
        print(doc.original_filename)

# Handle errors
try:
    with db.get_session() as session:
        doc = Document(sha256_hex=None)  # Violates NOT NULL constraint
        session.add(doc)
except Exception as e:
    print(f"Transaction rolled back: {e}")
```

---

## JSON Schema (`src/schema.py`)

### Overview

JSON Schema definition for OpenAI structured outputs with strict validation (`additionalProperties: false`).

### Functions

#### `get_document_extraction_schema()`

```python
def get_document_extraction_schema() -> Dict[str, Any]:
    """
    Get JSON Schema for document metadata extraction.

    Schema enforces strict validation with 40+ fields:
    - Required fields: schema_version, file_name, doc_type, confidence_score
    - Optional fields: issuer, dates, amounts, summaries, tags, etc.
    - additionalProperties: false (rejects unknown fields)

    Returns:
        Dict[str, Any]: JSON Schema dict conforming to draft-07

    Example:
        schema = get_document_extraction_schema()
        # Use in OpenAI API request:
        payload = {
            "text": {
                "format": {
                    "type": "json_schema",
                    "json_schema": {"name": "document_extraction", "schema": schema, "strict": True}
                }
            }
        }
    """
```

**Schema Structure** (abbreviated):
```python
{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "additionalProperties": False,  # Strict validation
    "required": ["schema_version", "file_name", "doc_type", "confidence_score"],
    "properties": {
        "schema_version": {"type": "string", "const": "1.0"},
        "file_name": {"type": "string"},
        "doc_type": {"type": "string", "enum": [...]},
        "confidence_score": {"type": "number", "minimum": 0, "maximum": 100},
        # ... 36 more fields
    }
}
```

#### `validate_response()`

```python
def validate_response(response_data: Dict[str, Any]) -> Tuple[bool, Optional[List[str]]]:
    """
    Validate API response against schema.

    Args:
        response_data: JSON object from OpenAI API

    Returns:
        Tuple of (is_valid, errors):
        - is_valid: True if valid, False otherwise
        - errors: List of validation error messages (None if valid)

    Example:
        metadata = json.loads(api_response)
        is_valid, errors = validate_response(metadata)
        if not is_valid:
            logger.warning(f"Validation failed: {errors}")
    """
```

### Schema Fields Reference

**Required Fields**:
- `schema_version` (const: "1.0")
- `file_name` (string)
- `doc_type` (enum: 25 document types)
- `confidence_score` (0-100)

**Optional Classification**:
- `doc_subtype` (string)
- `issuer`, `recipient` (string)

**Optional Dates**:
- `primary_date`, `secondary_date` (YYYY-MM-DD format)

**Optional Financial**:
- `total_amount` (number)
- `currency` (3-letter ISO code)

**Optional Content**:
- `summary` (string, ≤500 chars)
- `action_items` (array of objects)
- `deadlines` (array of objects)
- `urgency_level` (enum: low/medium/high/critical)
- `tags` (array of strings, 5-15 items)
- `ocr_text_excerpt` (string, ≤40,000 chars)
- `language_detected` (string)
- `extraction_quality` (enum: high/medium/low)
- `requires_review` (boolean)

### Usage Examples

```python
from src.schema import get_document_extraction_schema, validate_response
import json

# Get schema for API request
schema = get_document_extraction_schema()

# Use in Responses API payload
payload = {
    "model": "gpt-5-mini",
    "text": {
        "format": {
            "type": "json_schema",
            "json_schema": {
                "name": "document_extraction_v1",
                "schema": schema,
                "strict": True  # Enforce strict validation
            }
        }
    },
    "input": [...]
}

# Validate API response
response_text = '{"schema_version": "1.0", "file_name": "invoice.pdf", ...}'
metadata = json.loads(response_text)

is_valid, errors = validate_response(metadata)
if is_valid:
    print("Response valid!")
else:
    print(f"Validation errors: {errors}")
```

---

## Prompts (`src/prompts.py`)

### Overview

Three-role prompt architecture (system/developer/user) optimized for prompt caching with the OpenAI Responses API.

### Constants

#### `SYSTEM_PROMPT`

```python
SYSTEM_PROMPT: str = """You are a specialized document processing assistant..."""
```
**Purpose**: Minimal guardrails for model behavior (~100 tokens)

#### `DEVELOPER_PROMPT`

```python
DEVELOPER_PROMPT: str = """
**Metadata Extraction Guidelines**

You are analyzing scanned PDF documents to extract structured metadata...
"""
```
**Purpose**: Comprehensive extraction rules (~2000 tokens), **kept identical across calls for caching**

**Key Sections**:
1. Document Classification (25 doc_type values)
2. Field Extraction Guidelines (dates, amounts, parties)
3. Content Analysis (summaries, action items, deadlines)
4. OCR Handling (up to 40,000 chars per document)
5. Tag Generation (5-15 tags per document)
6. Quality Indicators (confidence_score, extraction_quality)

### Functions

#### `build_responses_api_payload()`

```python
def build_responses_api_payload(
    filename: str,
    pdf_base64: str,
    page_count: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Build complete Responses API request payload.

    Args:
        filename: Original PDF filename
        pdf_base64: Base64-encoded PDF with data URI prefix
        page_count: Number of pages (optional, for logging)

    Returns:
        Dict[str, Any]: Complete API request payload

    Features:
    - Three-role prompt (system/developer/user) for caching
    - PDF attached as input_file with base64 data
    - Strict JSON schema enforcement
    - Token budgets: max_output_tokens=60,000

    Example:
        pdf_base64 = encode_pdf_to_base64(Path("invoice.pdf"))
        payload = build_responses_api_payload("invoice.pdf", pdf_base64, page_count=3)
        response = client.post("/v1/responses", body=payload)
    """
```

**Payload Structure**:
```python
{
    "model": "gpt-5-mini",
    "input": [
        {
            "role": "system",
            "content": [{"type": "input_text", "text": SYSTEM_PROMPT}]
        },
        {
            "role": "developer",  # Cached for repeated calls
            "content": [{"type": "input_text", "text": DEVELOPER_PROMPT}]
        },
        {
            "role": "user",  # Per-file unique content
            "content": [
                {"type": "input_text", "text": "Extract metadata from: invoice.pdf"},
                {"type": "input_file", "filename": "invoice.pdf", "file_data": "data:application/pdf;base64,..."}
            ]
        }
    ],
    "text": {
        "format": {
            "type": "json_schema",
            "json_schema": {
                "name": "document_extraction_v1",
                "schema": {...},
                "strict": True
            }
        }
    },
    "max_output_tokens": 60000
}
```

### Usage Examples

```python
from src.prompts import build_responses_api_payload
from src.processor import encode_pdf_to_base64
from pathlib import Path

# Encode PDF
pdf_path = Path("inbox/invoice.pdf")
pdf_base64 = encode_pdf_to_base64(pdf_path)

# Build payload
payload = build_responses_api_payload(
    filename=pdf_path.name,
    pdf_base64=pdf_base64,
    page_count=3
)

# Send to API (using api_client module)
from src.api_client import ResponsesAPIClient
client = ResponsesAPIClient()
response = client.create_response(payload)

print(f"Prompt tokens: {response['usage']['prompt_tokens']}")
print(f"Cached tokens: {response['usage']['prompt_tokens_details']['cached_tokens']}")
```

---

## Deduplication (`src/dedupe.py`)

### Overview

SHA-256 file hashing, database deduplication queries, and vector store metadata building.

### Functions

#### `sha256_file()`

```python
def sha256_file(file_path: Path) -> Tuple[str, str]:
    """
    Compute SHA-256 hash of file using streaming.

    Args:
        file_path: Path to file to hash

    Returns:
        Tuple of (hex_hash, base64_hash):
        - hex_hash: 64-character hexadecimal string
        - base64_hash: Base64-encoded hash (for OpenAI attributes)

    Memory-efficient: processes file in 1MB chunks.

    Example:
        hex_hash, b64_hash = sha256_file(Path("invoice.pdf"))
        # hex_hash: "abc123..."  (64 chars)
        # b64_hash: "qwE1234..." (base64)
    """
```

#### `check_duplicate()`

```python
def check_duplicate(session: Session, sha256_hex: str) -> Optional[Document]:
    """
    Check if document with given hash exists in database.

    Args:
        session: SQLAlchemy session
        sha256_hex: SHA-256 hash in hexadecimal format

    Returns:
        Document: Existing document if found, None otherwise

    Example:
        with db.get_session() as session:
            hex_hash, _ = sha256_file(Path("invoice.pdf"))
            duplicate = check_duplicate(session, hex_hash)
            if duplicate:
                print(f"Duplicate of document ID {duplicate.id}")
    """
```

#### `deduplicate_and_hash()`

```python
def deduplicate_and_hash(
    file_path: Path,
    session: Session
) -> Tuple[Optional[str], Optional[str], Optional[Document]]:
    """
    Combined operation: compute hash and check for duplicates.

    Args:
        file_path: Path to PDF file
        session: SQLAlchemy session

    Returns:
        Tuple of (hex_hash, base64_hash, duplicate_document):
        - hex_hash: SHA-256 in hex format
        - base64_hash: SHA-256 in base64 format
        - duplicate_document: Existing Document if duplicate, None otherwise

    Example:
        with db.get_session() as session:
            hex_hash, b64_hash, duplicate = deduplicate_and_hash(
                Path("invoice.pdf"), session
            )
            if duplicate:
                logger.info(f"Skipping duplicate: {duplicate.id}")
            else:
                logger.info(f"New document, hash: {hex_hash}")
    """
```

#### `build_vector_store_attributes()`

```python
def build_vector_store_attributes(doc: Document) -> Dict[str, str]:
    """
    Build metadata attributes for vector store file.

    Args:
        doc: Document model instance

    Returns:
        Dict[str, str]: Metadata attributes (max 16 key-value pairs)

    Attributes include:
    - sha256_hex: File hash for deduplication
    - doc_type, issuer: Classification fields
    - primary_date: Date in YYYY-MM-DD format
    - document_id: Database primary key

    Note: OpenAI vector stores limit to 16 attributes per file.

    Example:
        attrs = build_vector_store_attributes(doc)
        # {
        #     "sha256_hex": "abc123...",
        #     "doc_type": "Invoice",
        #     "issuer": "Acme Corp",
        #     "primary_date": "2024-10-15",
        #     "document_id": "123"
        # }
    """
```

### Usage Examples

```python
from src.dedupe import deduplicate_and_hash, build_vector_store_attributes
from src.database import DatabaseManager
from src.models import Document
from pathlib import Path

db = DatabaseManager()

# Check for duplicate before processing
pdf_path = Path("inbox/invoice.pdf")

with db.get_session() as session:
    hex_hash, b64_hash, duplicate = deduplicate_and_hash(pdf_path, session)

    if duplicate:
        print(f"Skipping duplicate of document ID {duplicate.id}")
    else:
        print(f"New document, SHA-256: {hex_hash}")

        # Process document...
        doc = Document(
            sha256_hex=hex_hash,
            sha256_base64=b64_hash,
            original_filename=pdf_path.name,
            # ... other fields
        )
        session.add(doc)
        session.commit()

        # Build vector store attributes
        attrs = build_vector_store_attributes(doc)
        print(f"Vector store attributes: {attrs}")
```

---

## API Client (`src/api_client.py`)

### Overview

OpenAI Responses API client with retry logic, circuit breaker, and usage extraction.

### Classes

#### `ResponsesAPIClient`

```python
class ResponsesAPIClient:
    """
    OpenAI Responses API client with resilience features.

    Features:
    - Exponential backoff retry (5 attempts, 2-60 second wait)
    - Circuit breaker (opens after 5 consecutive failures)
    - Automatic timeout (300 seconds default)
    - Usage tracking (prompt/completion/cached tokens)
    - Structured error logging
    """
```

**Constructor**:
```python
def __init__(self, api_key: Optional[str] = None, timeout: Optional[int] = None):
    """
    Initialize API client.

    Args:
        api_key: OpenAI API key (default: from config)
        timeout: Request timeout in seconds (default: 300)
    """
```

**Methods**:

##### `create_response()`
```python
def create_response(self, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Call Responses API with retry and circuit breaker.

    Args:
        payload: Complete API request payload

    Returns:
        Dict[str, Any]: API response including output and usage

    Raises:
        CircuitBreakerError: If circuit breaker is open
        RateLimitError: After 5 retries on rate limit
        APIError: After 5 retries on server errors
        APITimeoutError: If request exceeds timeout

    Retry Behavior:
    - Attempt 1: immediate
    - Attempt 2: wait 2s
    - Attempt 3: wait 4s
    - Attempt 4: wait 8s
    - Attempt 5: wait 16s

    Example:
        client = ResponsesAPIClient()
        payload = build_responses_api_payload(...)
        response = client.create_response(payload)
    """
```

##### `extract_output_text()`
```python
def extract_output_text(self, response: Dict[str, Any]) -> str:
    """
    Extract model output text from API response.

    Args:
        response: API response dict

    Returns:
        str: Model's output text (JSON string if using structured outputs)

    Example:
        output = client.extract_output_text(response)
        metadata = json.loads(output)
    """
```

##### `extract_usage()`
```python
def extract_usage(self, response: Dict[str, Any]) -> Dict[str, int]:
    """
    Extract token usage from API response.

    Args:
        response: API response dict

    Returns:
        Dict with keys:
        - prompt_tokens: Total prompt tokens
        - completion_tokens: Output tokens
        - cached_tokens: Cached prompt tokens (for cost calculation)
        - total_tokens: Sum of prompt + completion tokens

    Example:
        usage = client.extract_usage(response)
        print(f"Cached: {usage['cached_tokens']} tokens")
    """
```

##### `get_circuit_breaker_status()`
```python
def get_circuit_breaker_status(self) -> Dict[str, Any]:
    """
    Get current circuit breaker state.

    Returns:
        Dict with keys:
        - state: "closed", "open", or "half_open"
        - failure_count: Number of consecutive failures
        - last_failure_time: Timestamp of last failure (if any)

    Example:
        status = client.get_circuit_breaker_status()
        if status["state"] == "open":
            print("Circuit breaker is open, waiting for cooldown")
    """
```

### Usage Examples

```python
from src.api_client import ResponsesAPIClient
from src.prompts import build_responses_api_payload
from src.processor import encode_pdf_to_base64
from pathlib import Path
import json

# Initialize client
client = ResponsesAPIClient()

# Build payload
pdf_base64 = encode_pdf_to_base64(Path("invoice.pdf"))
payload = build_responses_api_payload("invoice.pdf", pdf_base64)

# Call API with automatic retry
try:
    response = client.create_response(payload)

    # Extract output
    output_text = client.extract_output_text(response)
    metadata = json.loads(output_text)

    # Extract usage
    usage = client.extract_usage(response)
    print(f"Tokens: {usage['prompt_tokens']} prompt, {usage['completion_tokens']} completion")
    print(f"Cached: {usage['cached_tokens']} tokens (cost savings!)")

except CircuitBreakerError:
    print("Circuit breaker open, too many failures")
except RateLimitError:
    print("Rate limit exceeded, try again later")
except APITimeoutError:
    print("Request timed out after 300 seconds")
```

---

## Token Counter (`src/token_counter.py`)

### Overview

Token counting with tiktoken and cost estimation for OpenAI Responses API usage.

### Functions

#### `count_tokens()`

```python
def count_tokens(text: str, model: str = "gpt-5-mini") -> int:
    """
    Count tokens in text using tiktoken.

    Args:
        text: Text to count tokens for
        model: Model name for encoder selection

    Returns:
        int: Number of tokens

    Encoding Selection:
    - o200k_base: gpt-5*, gpt-4o*
    - cl100k_base: gpt-4, gpt-3.5-turbo

    Example:
        tokens = count_tokens("Extract metadata from this PDF", "gpt-5-mini")
        # Returns: ~8 tokens
    """
```

#### `calculate_cost()`

```python
def calculate_cost(
    prompt_tokens: int,
    completion_tokens: int,
    cached_tokens: int = 0,
    model: str = "gpt-5-mini"
) -> Dict[str, float]:
    """
    Calculate API call cost from token usage.

    Args:
        prompt_tokens: Total prompt tokens (including cached)
        completion_tokens: Output tokens
        cached_tokens: Cached prompt tokens (discounted rate)
        model: Model name (for pricing lookup)

    Returns:
        Dict with keys:
        - input_cost: Cost for uncached prompt tokens
        - output_cost: Cost for completion tokens
        - cache_cost: Cost for cached prompt tokens (50% discount)
        - total_cost: Sum of all costs in USD

    Pricing (gpt-5-mini, per 1M tokens):
    - Input: $0.075
    - Output: $0.300
    - Cached Input: $0.0375 (50% discount)

    Example:
        cost = calculate_cost(
            prompt_tokens=2000,
            completion_tokens=500,
            cached_tokens=1500
        )
        # {
        #     "input_cost": 0.0000375,  # (2000 - 1500) * 0.075 / 1M
        #     "cache_cost": 0.00005625,  # 1500 * 0.0375 / 1M
        #     "output_cost": 0.00015,    # 500 * 0.300 / 1M
        #     "total_cost": 0.00024375
        # }
    """
```

#### `format_cost_report()`

```python
def format_cost_report(cost_data: Dict[str, float]) -> str:
    """
    Format cost breakdown as human-readable string.

    Args:
        cost_data: Output from calculate_cost()

    Returns:
        str: Formatted cost report

    Example:
        cost = calculate_cost(...)
        report = format_cost_report(cost)
        # "Cost: $0.0002 (input: $0.0000, cache: $0.0001, output: $0.0002)"
    """
```

#### `check_cost_alerts()`

```python
def check_cost_alerts(cost_usd: float) -> Optional[str]:
    """
    Check if cost exceeds configured alert thresholds.

    Args:
        cost_usd: Cost for single API call

    Returns:
        str: Alert message if threshold exceeded, None otherwise

    Thresholds (from config):
    - Per-document: $1.00 (warning)
    - Hourly: $10.00
    - Daily: $100.00

    Example:
        alert = check_cost_alerts(1.25)
        if alert:
            logger.warning(alert)
        # "⚠️ Cost alert: $1.25 exceeds per-document threshold of $1.00"
    """
```

### Usage Examples

```python
from src.token_counter import count_tokens, calculate_cost, format_cost_report, check_cost_alerts

# Estimate tokens before API call
prompt_text = "Extract metadata from this PDF document..."
estimated_tokens = count_tokens(prompt_text)
print(f"Estimated prompt tokens: {estimated_tokens}")

# After API call, calculate cost
usage = {
    "prompt_tokens": 2000,
    "completion_tokens": 500,
    "cached_tokens": 1500
}

cost = calculate_cost(
    prompt_tokens=usage["prompt_tokens"],
    completion_tokens=usage["completion_tokens"],
    cached_tokens=usage["cached_tokens"]
)

# Format for logging
report = format_cost_report(cost)
logger.info(report)

# Check for cost alerts
alert = check_cost_alerts(cost["total_cost"])
if alert:
    logger.warning(alert)
```

---

## Vector Store (`src/vector_store.py`)

### Overview

OpenAI Vector Store integration for File Search and cross-document intelligence.

### Classes

#### `VectorStoreManager`

```python
class VectorStoreManager:
    """
    Manages OpenAI vector store lifecycle and file operations.

    Features:
    - Persistent vector store ID (survives restarts)
    - File upload with metadata attributes (max 16)
    - Retry logic for upload failures
    - Automatic recovery from cache deletion
    """
```

**Constructor**:
```python
def __init__(
    self,
    vector_store_name: Optional[str] = None,
    vector_store_id_file: Optional[Path] = None
):
    """
    Initialize vector store manager.

    Args:
        vector_store_name: Name for vector store (default: from config)
        vector_store_id_file: File to persist vector store ID (default: .vector_store_id)
    """
```

**Methods**:

##### `get_or_create_vector_store()`
```python
def get_or_create_vector_store(self) -> str:
    """
    Get existing vector store ID or create new one.

    Returns:
        str: Vector store ID

    Behavior:
    - If .vector_store_id file exists: load ID from file
    - If file missing or ID invalid: create new vector store, save ID

    Example:
        manager = VectorStoreManager()
        vs_id = manager.get_or_create_vector_store()
        # "vs-abc123..."
    """
```

##### `add_file_to_vector_store()`
```python
def add_file_to_vector_store(
    self,
    file_path: Path,
    metadata: Dict[str, str],
    max_retries: int = 3
) -> Optional[str]:
    """
    Upload file to vector store with metadata attributes.

    Args:
        file_path: Path to file to upload
        metadata: Metadata attributes (max 16 key-value pairs)
        max_retries: Number of upload retry attempts

    Returns:
        str: OpenAI file ID if successful, None if failed

    Raises:
        ValueError: If metadata has more than 16 attributes

    Retry Behavior:
    - Retries on upload failures
    - Exponential backoff (2-8 seconds)

    Example:
        file_id = manager.add_file_to_vector_store(
            Path("invoice.pdf"),
            metadata={
                "sha256_hex": "abc123...",
                "doc_type": "Invoice",
                "issuer": "Acme Corp",
                "primary_date": "2024-10-15",
                "document_id": "123"
            }
        )
    """
```

##### `search_vector_store()`
```python
def search_vector_store(
    self,
    query: str,
    max_results: int = 5
) -> List[Dict[str, Any]]:
    """
    Search vector store for similar documents.

    Args:
        query: Search query text
        max_results: Maximum number of results to return

    Returns:
        List[Dict]: Search results with file IDs and scores

    Example:
        results = manager.search_vector_store("utility bills from 2024", max_results=5)
        for result in results:
            print(f"{result['file_id']}: score {result['score']}")
    """
```

### Usage Examples

```python
from src.vector_store import VectorStoreManager
from src.dedupe import build_vector_store_attributes
from src.models import Document
from pathlib import Path

# Initialize manager
manager = VectorStoreManager()

# Get or create vector store
vs_id = manager.get_or_create_vector_store()
print(f"Using vector store: {vs_id}")

# Add file after processing
doc = Document(
    id=123,
    sha256_hex="abc123...",
    doc_type="Invoice",
    issuer="Acme Corp",
    primary_date="2024-10-15"
)

attrs = build_vector_store_attributes(doc)
file_id = manager.add_file_to_vector_store(
    Path("processed/invoice.pdf"),
    metadata=attrs
)

if file_id:
    print(f"File uploaded to vector store: {file_id}")
    # Update document with vector store file ID
    doc.vector_store_file_id = file_id
else:
    print("Vector store upload failed")

# Search for similar documents
results = manager.search_vector_store("invoices from Acme Corp", max_results=5)
print(f"Found {len(results)} similar documents")
```

---

## Logging (`src/logging_config.py`)

### Overview

Structured JSON logging configuration with correlation IDs and log rotation.

### Classes

#### `JSONFormatter`

```python
class JSONFormatter(logging.Formatter):
    """
    JSON log formatter for structured logging.

    Output format:
    {
        "timestamp": "2024-10-16T12:00:00Z",
        "level": "INFO",
        "logger": "paper_autopilot",
        "message": "Processing complete",
        "correlation_id": "abc-123",
        "doc_id": 456,
        "cost_usd": 0.05
    }
    """
```

### Functions

#### `setup_logging()`

```python
def setup_logging(
    log_level: str = "INFO",
    log_format: str = "json",
    log_file: str = "logs/paper_autopilot.log"
) -> logging.Logger:
    """
    Configure application logging.

    Args:
        log_level: Logging level (DEBUG/INFO/WARNING/ERROR)
        log_format: "json" or "text"
        log_file: Path to log file

    Returns:
        logging.Logger: Configured logger instance

    Features:
    - Console handler: colored text format for development
    - File handler: JSON format for production analysis
    - Automatic log rotation: 10MB max, 5 backup files

    Example:
        logger = setup_logging(log_level="INFO", log_format="json")
        logger.info("Processing started", extra={"doc_id": 123})
    """
```

#### `get_correlation_id()`

```python
def get_correlation_id() -> str:
    """
    Generate unique correlation ID for request tracing.

    Returns:
        str: UUID-based correlation ID

    Example:
        correlation_id = get_correlation_id()
        logger.info("Processing started", extra={"correlation_id": correlation_id})
    """
```

### Usage Examples

```python
from src.logging_config import setup_logging, get_correlation_id

# Setup logging
logger = setup_logging(log_level="INFO", log_format="json", log_file="logs/app.log")

# Basic logging
logger.info("Application started")

# Logging with extra context
correlation_id = get_correlation_id()
logger.info("Processing document", extra={
    "correlation_id": correlation_id,
    "doc_id": 123,
    "filename": "invoice.pdf"
})

# Logging with performance metrics
logger.info("API call completed", extra={
    "correlation_id": correlation_id,
    "duration_ms": 1234,
    "cost_usd": 0.05,
    "prompt_tokens": 2000,
    "completion_tokens": 500,
    "cached_tokens": 1500
})

# Error logging
try:
    # ... processing
    pass
except Exception as e:
    logger.error("Processing failed", exc_info=True, extra={
        "correlation_id": correlation_id,
        "doc_id": 123
    })

# Querying JSON logs with jq
# cat logs/app.log | jq 'select(.level == "ERROR")'
# cat logs/app.log | jq 'select(.cost_usd) | .cost_usd' | awk '{sum+=$1} END {print sum}'
```

---

## Processor (`src/processor.py`)

### Overview

Main document processing pipeline orchestrating all components into a cohesive 9-step workflow.

### Classes

#### `ProcessingResult`

```python
class ProcessingResult:
    """
    Container for processing result with status and metadata.

    Attributes:
        success (bool): True if processing succeeded
        document_id (Optional[int]): Database ID if success
        error (Optional[str]): Error message if failed
        duplicate_of (Optional[int]): Original document ID if duplicate
        cost_usd (Optional[float]): API cost in USD
        processing_time_seconds (Optional[float]): Total time
    """
```

### Functions

#### `encode_pdf_to_base64()`

```python
def encode_pdf_to_base64(file_path: Path) -> str:
    """
    Encode PDF to base64 data URI for API submission.

    Args:
        file_path: Path to PDF file

    Returns:
        str: Base64-encoded data URI (data:application/pdf;base64,...)

    Example:
        pdf_base64 = encode_pdf_to_base64(Path("invoice.pdf"))
        # "data:application/pdf;base64,JVBERi0xLjQ..."
    """
```

#### `process_document()`

```python
def process_document(
    file_path: Path,
    db_manager: DatabaseManager,
    api_client: ResponsesAPIClient,
    vector_manager: VectorStoreManager,
    skip_duplicates: bool = True,
) -> ProcessingResult:
    """
    Process single PDF through complete 9-step pipeline.

    Args:
        file_path: Path to PDF file
        db_manager: Database manager instance
        api_client: API client instance
        vector_manager: Vector store manager instance
        skip_duplicates: If True, skip processing duplicates

    Returns:
        ProcessingResult: Result with status and metadata

    Pipeline Steps:
    1. Hash Computation (SHA-256)
    2. Duplicate Detection (check database)
    3. PDF Encoding (base64 data URI)
    4. API Payload Construction (prompts)
    5. OpenAI API Call (Responses API)
    6. Response Parsing (extract text & usage)
    7. JSON Validation (schema validation)
    8. Database Storage (Document model)
    9. Vector Store Upload (OpenAI File Search)

    Example:
        result = process_document(
            file_path=Path("inbox/invoice.pdf"),
            db_manager=db_manager,
            api_client=api_client,
            vector_manager=vector_manager,
            skip_duplicates=True,
        )

        if result.success:
            if result.duplicate_of:
                print(f"Duplicate of document {result.duplicate_of}")
            else:
                print(f"Document ID: {result.document_id}")
                print(f"Cost: ${result.cost_usd:.4f}")
                print(f"Time: {result.processing_time_seconds:.2f}s")
        else:
            print(f"Error: {result.error}")
    """
```

#### `process_inbox()`

```python
def process_inbox(
    inbox_dir: Path = Path("inbox"),
    processed_dir: Path = Path("processed"),
    failed_dir: Path = Path("failed"),
    batch_size: int = 10,
    skip_duplicates: bool = True,
) -> Dict[str, Any]:
    """
    Batch process all PDFs in inbox directory.

    Args:
        inbox_dir: Directory containing PDFs to process
        processed_dir: Directory for successfully processed PDFs
        failed_dir: Directory for failed PDFs
        batch_size: Number of files to process (default: 10)
        skip_duplicates: Skip files that already exist in database

    Returns:
        Summary dict with keys:
        - total_files: Total PDFs found
        - processed: Successfully processed count
        - duplicates: Duplicate count
        - failed: Failed count
        - total_cost: Total API cost in USD
        - avg_processing_time: Average time per document

    File Lifecycle:
    - Success (non-duplicate): Process → DB → Vector Store → Move to processed/
    - Success (duplicate): Detect → Move to processed/
    - Failure: Attempt → Error → Move to failed/

    Example:
        results = process_inbox(
            inbox_dir=Path("inbox"),
            processed_dir=Path("processed"),
            failed_dir=Path("failed"),
            batch_size=10,
            skip_duplicates=True,
        )

        print(f"Processed: {results['processed']}")
        print(f"Duplicates: {results['duplicates']}")
        print(f"Failed: {results['failed']}")
        print(f"Total cost: ${results['total_cost']:.4f}")
        print(f"Avg time: {results['avg_processing_time']:.2f}s")
    """
```

### Usage Examples

```python
from src.processor import process_document, process_inbox, ProcessingResult
from src.database import DatabaseManager
from src.api_client import ResponsesAPIClient
from src.vector_store import VectorStoreManager
from pathlib import Path

# Initialize components
db_manager = DatabaseManager()
db_manager.create_tables()
api_client = ResponsesAPIClient()
vector_manager = VectorStoreManager()

# Process single document
result = process_document(
    file_path=Path("inbox/invoice.pdf"),
    db_manager=db_manager,
    api_client=api_client,
    vector_manager=vector_manager,
    skip_duplicates=True,
)

if result.success:
    if result.duplicate_of:
        print(f"✅ Duplicate of document {result.duplicate_of}")
    else:
        print(f"✅ Success: Document ID {result.document_id}")
        print(f"   Cost: ${result.cost_usd:.4f}")
        print(f"   Time: {result.processing_time_seconds:.2f}s")
else:
    print(f"❌ Failed: {result.error}")

# Batch process inbox
results = process_inbox(
    inbox_dir=Path("inbox"),
    processed_dir=Path("processed"),
    failed_dir=Path("failed"),
    batch_size=10,
)

print(f"\n=== Summary ===")
print(f"Total files: {results['total_files']}")
print(f"Processed: {results['processed']}")
print(f"Duplicates: {results['duplicates']}")
print(f"Failed: {results['failed']}")
print(f"Total cost: ${results['total_cost']:.4f}")
if "avg_processing_time" in results:
    print(f"Avg time: {results['avg_processing_time']:.2f}s")
```

---

## Module Dependencies

**Dependency Graph**:
```
config.py (0 dependencies)
├── logging_config.py
├── schema.py
├── prompts.py
├── api_client.py
├── token_counter.py
└── vector_store.py

models.py (0 dependencies)
└── database.py

dedupe.py ← models, logging_config

processor.py ← ALL modules
```

**Import Order** (avoid circular dependencies):
1. `config.py`
2. `logging_config.py`, `models.py`
3. `database.py`, `schema.py`, `prompts.py`
4. `dedupe.py`, `api_client.py`, `token_counter.py`, `vector_store.py`
5. `processor.py`

---

## Type Hints

All modules use comprehensive type hints:
- Function signatures: `def func(arg: Type) -> ReturnType`
- Optional values: `Optional[Type]`
- Collections: `List[Type]`, `Dict[str, Any]`
- Pydantic models: Automatic type validation

**Example**:
```python
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path

def process_document(
    file_path: Path,
    db_manager: DatabaseManager,
    api_client: ResponsesAPIClient,
    vector_manager: VectorStoreManager,
    skip_duplicates: bool = True,
) -> ProcessingResult:
    ...
```

---

## Error Handling Patterns

### Standard Pattern
```python
try:
    result = process_document(...)
    if result.success:
        logger.info(f"Success: {result.document_id}")
    else:
        logger.error(f"Failed: {result.error}")
except Exception as e:
    logger.error(f"Unexpected error: {e}", exc_info=True)
```

### Graceful Degradation
```python
# Non-fatal vector store upload
try:
    file_id = vector_manager.add_file_to_vector_store(...)
    doc.vector_store_file_id = file_id
except Exception as e:
    logger.warning(f"Vector store upload failed: {e}")
    # Continue processing - not a fatal error
```

### Circuit Breaker
```python
try:
    response = api_client.create_response(payload)
except CircuitBreakerError:
    logger.error("Circuit breaker open, too many API failures")
    # Wait for cooldown or escalate
```

---

## References

- **Configuration**: `docs/CODE_ARCHITECTURE.md` (Configuration Management section)
- **Database**: `docs/CODE_ARCHITECTURE.md` (Database Models section)
- **Pipeline**: `docs/PROCESSOR_GUIDE.md`
- **Retry Logic**: `docs/CODE_ARCHITECTURE.md` (Retry Logic section)
- **Token Tracking**: `docs/CODE_ARCHITECTURE.md` (Token Tracking section)
- **Vector Stores**: `docs/CODE_ARCHITECTURE.md` (Vector Store Integration section)
- **Logging**: `docs/CODE_ARCHITECTURE.md` (Structured Logging section)

---

*Last Updated: 2025-10-16*
*Status: Production-ready API reference*
*Maintained By: Platform Engineering Team*
