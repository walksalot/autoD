# Deferred Work: TD3 + WS2 Implementation Plan

**Status:** Ready for Wave 2
**Total Scope:** 16-22 hours (2-3 days focused development)
**Priority:** High (technical debt + cost optimization)
**Dependencies:** Wave 1 complete ✅
**Related:** ADR-024-workstream-deferral-td3-ws2.md

---

## Overview

This document provides actionable implementation plans for two deferred Wave 1 workstreams:

1. **TD3: MyPy Strict Mode** (8-12 hours) - Achieve 100% type coverage
2. **WS2: Embedding Cache Optimization** (8-10 hours) - Reduce API costs 20-40%

Both workstreams were deferred from Wave 1 to maintain focus on core infrastructure (CompensatingTransaction, Pydantic V2, E2E testing, vector store, production hardening). See ADR-024 for deferral rationale.

---

## TD3: MyPy Strict Mode + Type Coverage (8-12 hours)

### Current State

**Quality Gate Results (Wave 1):**
```
mypy src/ --strict
Found 49 errors in 8 files (checked 12 source files)
```

**Error Categories:**
- Missing return type annotations: 18 errors
- Untyped function parameters: 15 errors
- Implicit `Any` types from third-party libraries: 12 errors
- Missing type stubs: 4 errors

**Files with Issues:**
1. `src/config.py` - 8 errors (Settings class, environment variables)
2. `src/processor.py` - 12 errors (API response parsing, metadata handling)
3. `src/dedupe.py` - 6 errors (hash functions, vector store attributes)
4. `src/transactions.py` - 7 errors (context manager, rollback handlers)
5. `src/pipeline.py` - 5 errors (generic stage protocol)
6. `src/stages/upload_stage.py` - 4 errors (API client responses)
7. `src/stages/persist_stage.py` - 4 errors (session management)
8. `src/database.py` - 3 errors (SQLAlchemy session types)

### Implementation Plan

#### Phase 1: Enable Strict Mode (2 hours)

**Task 1.1: Update pyproject.toml (30 min)**
```toml
[tool.mypy]
python_version = "3.9"
strict = true
warn_return_any = true
warn_unused_configs = true
warn_redundant_casts = true
warn_unused_ignores = true
disallow_any_generics = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
disallow_untyped_decorators = true
no_implicit_optional = true
warn_unreachable = true

# Exclude tests initially (fix separately)
exclude = ['^tests/']

[[tool.mypy.overrides]]
module = [
    "requests.*",
    "openai.*",
]
ignore_missing_imports = true
```

**Task 1.2: Create Type Stubs Directory (30 min)**
```bash
mkdir -p src/stubs
touch src/stubs/__init__.py
```

**Task 1.3: Baseline Current Errors (30 min)**
```bash
mypy src/ --strict > mypy_baseline.txt
# Create tracking document for fixing errors file-by-file
```

**Task 1.4: Update Pre-commit Hook (30 min)**
```yaml
# .pre-commit-config.yaml
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.11.2
    hooks:
      - id: mypy
        args: [--strict, --ignore-missing-imports]
        additional_dependencies: [types-requests==2.31.0]
```

**Validation:**
- [ ] `mypy --version` shows 1.11.2+
- [ ] Baseline file created with 49 errors
- [ ] Pre-commit hook runs (warns but doesn't block)
- [ ] CI pipeline includes mypy check

---

#### Phase 2: Fix Core Modules (4-6 hours)

**Priority Order:** Fix modules from most-used to least-used

##### Module 1: src/config.py (45 min)

**Current Issues (8 errors):**
```python
# Before (untyped)
class Settings(BaseSettings):
    openai_api_key: str
    openai_model: str = "gpt-5-mini"

    def get_database_url(self):  # Missing return type
        return self.database_url or "sqlite:///app.db"
```

**Fixes:**
```python
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Application configuration with environment variable overrides."""

    openai_api_key: str
    openai_model: str = "gpt-5-mini"
    database_url: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    def get_database_url(self) -> str:
        """Return database URL with fallback to SQLite default."""
        return self.database_url or "sqlite:///app.db"

# Global instance with explicit type
_settings: Optional[Settings] = None

def get_config() -> Settings:
    """Lazy-initialized global config singleton."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
```

**Tests:**
```bash
mypy src/config.py --strict  # Should pass
pytest tests/unit/test_config.py -v
```

##### Module 2: src/processor.py (1.5 hours)

**Current Issues (12 errors):**
- API response parsing returns `dict` (should be `Dict[str, Any]`)
- Metadata enrichment has implicit `Any` types
- Missing return type for `process_document()`

**Fixes:**
```python
from typing import Dict, Any, Tuple, Optional
from pathlib import Path
import requests

def call_responses_api(
    pdf_path: Path,
    encoded_pdf: str,
) -> Dict[str, Any]:
    """Call OpenAI Responses API with typed response."""
    response = requests.post(
        "https://api.openai.com/v1/responses",
        headers={
            "Authorization": f"Bearer {get_config().openai_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": get_config().openai_model,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": PROMPT_TEMPLATE},
                        {
                            "type": "input_file",
                            "filename": pdf_path.name,
                            "file_data": encoded_pdf,
                        },
                    ],
                }
            ],
            "text": {"format": {"type": "json_object"}},
        },
        timeout=300,
    )
    response.raise_for_status()
    return response.json()  # type: ignore[no-any-return]

def enrich_metadata(
    metadata: Dict[str, Any],
    usage: Dict[str, int],
    cost_data: Dict[str, float],
    model: str,
) -> Dict[str, Any]:
    """Add processing metadata with explicit typing."""
    return {
        **metadata,
        "_processing": {
            "model_used": model,
            "prompt_tokens": usage["prompt_tokens"],
            "output_tokens": usage["output_tokens"],
            "total_cost_usd": cost_data["total_cost"],
        },
    }

def process_document(pdf_path: Path) -> Tuple[str, str, Dict[str, Any]]:
    """
    Process PDF and return (sha256_hex, sha256_base64, metadata).

    Returns:
        Tuple of (hex_hash, base64_hash, enriched_metadata_dict)
    """
    # Implementation with full type annotations
    ...
```

**Tests:**
```bash
mypy src/processor.py --strict
pytest tests/unit/test_processor.py -v
```

##### Module 3: src/dedupe.py (45 min)

**Current Issues (6 errors):**
- Hash function return types not explicit
- Vector store attribute building has untyped dict

**Fixes:**
```python
from typing import Dict, Optional, Tuple
from pathlib import Path
import hashlib
import base64

def sha256_file(
    pdf_path: Path,
    chunk_size: int = 8192,
) -> Tuple[str, str]:
    """
    Compute SHA-256 hash of file.

    Args:
        pdf_path: Path to PDF file
        chunk_size: Bytes per read chunk

    Returns:
        Tuple of (hex_digest, base64_digest)
    """
    hasher = hashlib.sha256()
    with open(pdf_path, "rb") as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)

    hex_digest = hasher.hexdigest()
    b64_digest = base64.b64encode(hasher.digest()).decode("ascii")
    return hex_digest, b64_digest

def build_vector_store_attributes(doc: Document) -> Dict[str, str]:
    """
    Build vector store file metadata from Document.

    Args:
        doc: Document ORM instance

    Returns:
        Dictionary of string key-value pairs for vector store metadata
    """
    attributes: Dict[str, str] = {}
    metadata: Dict[str, Any] = doc.metadata_json or {}

    if doc_type := metadata.get("doc_type"):
        attributes["doc_type"] = str(doc_type)

    if issuer := metadata.get("issuer"):
        attributes["issuer"] = str(issuer)

    return attributes
```

**Tests:**
```bash
mypy src/dedupe.py --strict
pytest tests/unit/test_dedupe.py tests/property_based/test_hash_properties.py -v
```

##### Module 4: src/transactions.py (1 hour)

**Current Issues (7 errors):**
- Context manager protocol missing return types
- Rollback handler callbacks untyped
- Audit trail mutations have implicit `Any`

**Fixes:**
```python
from typing import Optional, Callable, Dict, Any, List
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class ResourceType(Enum):
    """Enumeration of external resource types for cleanup."""
    FILE = "file"
    VECTOR_STORE_FILE = "vector_store_file"
    DATABASE_RECORD = "database_record"

@dataclass
class RollbackHandler:
    """Encapsulation of rollback logic for a resource."""
    handler_fn: Callable[[], None]
    resource_type: ResourceType
    resource_id: str
    description: str
    critical: bool = True

class CompensatingTransaction:
    """
    Enhanced transaction manager with multi-step rollback support.

    Manages database transactions with LIFO rollback handlers for
    external resource cleanup (Files API, Vector Store).
    """

    def __init__(
        self,
        session: Session,
        audit_trail: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Initialize transaction manager.

        Args:
            session: SQLAlchemy database session
            audit_trail: Optional dict for event logging
        """
        self.session = session
        self.audit_trail = audit_trail if audit_trail is not None else {}
        self.rollback_handlers: List[RollbackHandler] = []

    def register_rollback(
        self,
        handler_fn: Callable[[], None],
        resource_type: ResourceType,
        resource_id: str,
        description: str,
        critical: bool = True,
    ) -> RollbackHandler:
        """
        Register rollback handler executed in LIFO order.

        Args:
            handler_fn: Cleanup function with no arguments
            resource_type: Type of resource to clean up
            resource_id: Unique identifier for resource
            description: Human-readable description
            critical: Whether failure should raise exception

        Returns:
            RollbackHandler instance for tracking
        """
        handler = RollbackHandler(
            handler_fn=handler_fn,
            resource_type=resource_type,
            resource_id=resource_id,
            description=description,
            critical=critical,
        )
        self.rollback_handlers.append(handler)
        return handler

    def __enter__(self) -> "CompensatingTransaction":
        """Enter transaction context."""
        self.audit_trail["started_at"] = datetime.utcnow().isoformat() + "Z"
        return self

    def __exit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[Exception],
        exc_tb: Any,
    ) -> bool:
        """
        Exit transaction context with rollback handling.

        Returns:
            False to propagate exceptions (never suppress)
        """
        if exc_type is None:
            # Success path
            try:
                self.session.commit()
                self.audit_trail["committed_at"] = datetime.utcnow().isoformat() + "Z"
                self.audit_trail["status"] = "success"
                self.audit_trail["compensation_needed"] = False
                logger.info("Transaction committed successfully")
            except Exception as commit_error:
                logger.error(f"Commit failed: {commit_error}")
                self._handle_rollback(commit_error)
                raise
        else:
            # Failure path
            logger.error(f"Transaction failed: {exc_val}")
            self._handle_rollback(exc_val)

        return False  # Never suppress exceptions

    def _handle_rollback(self, original_error: Optional[Exception]) -> None:
        """Execute rollback handlers in LIFO order."""
        self.session.rollback()
        self.audit_trail["rolled_back_at"] = datetime.utcnow().isoformat() + "Z"
        self.audit_trail["status"] = "failed"

        if original_error:
            self.audit_trail["error"] = str(original_error)
            self.audit_trail["error_type"] = type(original_error).__name__

        if not self.rollback_handlers:
            self.audit_trail["compensation_needed"] = False
            return

        self.audit_trail["compensation_needed"] = True

        # Execute handlers in LIFO order
        for handler in reversed(self.rollback_handlers):
            try:
                logger.info(f"Executing rollback: {handler.description}")
                handler.handler_fn()
                self.audit_trail["compensation_status"] = "success"
                self.audit_trail["compensation_completed_at"] = (
                    datetime.utcnow().isoformat() + "Z"
                )
            except Exception as cleanup_error:
                logger.error(f"Rollback failed: {cleanup_error}")
                self.audit_trail["compensation_status"] = "failed"
                self.audit_trail["compensation_error"] = str(cleanup_error)
                self.audit_trail["compensation_error_type"] = (
                    type(cleanup_error).__name__
                )
                if handler.critical:
                    # Log but don't mask original error
                    logger.critical(
                        f"Critical rollback failed for {handler.resource_id}"
                    )
```

**Tests:**
```bash
mypy src/transactions.py --strict
pytest tests/unit/test_transactions.py tests/integration/test_error_recovery.py -v
```

##### Modules 5-8: Remaining Files (2 hours)

**src/pipeline.py** (30 min):
- Add `Protocol` for `ProcessingStage` with typed `execute()` method
- Annotate `ProcessingContext` dataclass fields

**src/stages/upload_stage.py** (30 min):
- Type OpenAI client responses: `Mock | OpenAI` union
- Annotate `FileObject` return type

**src/stages/persist_stage.py** (30 min):
- Type SQLAlchemy session: `Session` from `sqlalchemy.orm`
- Annotate document creation return type

**src/database.py** (30 min):
- Add `Generator` type for `get_session()` context manager
- Type `DatabaseManager` methods

**Combined Tests:**
```bash
mypy src/ --strict  # Should show 0 errors
pytest tests/unit/ -v
```

---

#### Phase 3: Add Type Stubs (2-3 hours)

**Task 3.1: OpenAI Library Stubs (1 hour)**
```python
# src/stubs/openai.pyi
from typing import Any, Dict, Optional

class FileObject:
    id: str
    filename: str
    purpose: str

class OpenAI:
    def __init__(self, api_key: str) -> None: ...

    class files:
        @staticmethod
        def create(file: Any, purpose: str) -> FileObject: ...

        @staticmethod
        def delete(file_id: str) -> None: ...

    class beta:
        class vector_stores:
            class files:
                @staticmethod
                def delete(
                    vector_store_id: str,
                    file_id: str,
                ) -> None: ...
```

**Task 3.2: Internal Type Definitions (1 hour)**
```python
# src/types.py
from typing import TypedDict, Optional

class APIUsage(TypedDict):
    """OpenAI API usage statistics."""
    prompt_tokens: int
    output_tokens: int
    total_tokens: int

class CostData(TypedDict):
    """Cost calculation breakdown."""
    prompt_cost: float
    output_cost: float
    total_cost: float

class DocumentMetadata(TypedDict, total=False):
    """Extracted document metadata schema."""
    file_name: str
    doc_type: str
    issuer: Optional[str]
    primary_date: Optional[str]
    total_amount: Optional[float]
    summary: str
    _processing: ProcessingMetadata
    _raw_response: dict

class ProcessingMetadata(TypedDict):
    """Processing-specific metadata."""
    model_used: str
    prompt_tokens: int
    output_tokens: int
    total_cost_usd: float
```

**Task 3.3: Stage Protocol Definition (30 min)**
```python
# src/pipeline.py
from typing import Protocol
from dataclasses import dataclass

@dataclass
class ProcessingContext:
    """Immutable context passed between pipeline stages."""
    pdf_path: Path
    sha256_hex: Optional[str] = None
    sha256_base64: Optional[str] = None
    file_id: Optional[str] = None
    vector_store_file_id: Optional[str] = None
    metadata_json: Optional[Dict[str, Any]] = None
    document_id: Optional[int] = None
    error: Optional[Exception] = None
    audit_trail: Dict[str, Any] = field(default_factory=dict)

class ProcessingStage(Protocol):
    """Protocol for pipeline stages with typed execute method."""

    def execute(self, context: ProcessingContext) -> ProcessingContext:
        """
        Execute stage logic and return updated context.

        Args:
            context: Input processing context

        Returns:
            Updated context with stage-specific fields populated
        """
        ...
```

---

#### Phase 4: CI Integration (1 hour)

**Task 4.1: Update GitHub Actions (30 min)**
```yaml
# .github/workflows/ci.yml
name: CI

on: [push, pull_request]

jobs:
  type-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: |
          pip install mypy types-requests
          pip install -r requirements.txt
      - name: MyPy type check (strict)
        run: mypy src/ --strict --show-error-codes
```

**Task 4.2: Add Badge to README (15 min)**
```markdown
[![Type Check](https://github.com/user/autoD/workflows/CI/badge.svg)](https://github.com/user/autoD/actions)
```

**Task 4.3: Documentation Update (15 min)**
```markdown
## Type Safety

This project uses strict mypy type checking. All code must pass:

\`\`\`bash
mypy src/ --strict
\`\`\`

See `pyproject.toml` for configuration details.
```

---

### Success Criteria

**Phase Completion Checklist:**
- [ ] `mypy src/ --strict` exits with 0 errors
- [ ] All 49 baseline errors resolved
- [ ] Type stubs added for third-party libraries (`openai`, `requests`)
- [ ] Internal types documented in `src/types.py`
- [ ] Pre-commit hook enforces strict mode
- [ ] CI pipeline fails on type violations
- [ ] IDE autocomplete fully functional for all modules
- [ ] Documentation updated with type annotation guidelines
- [ ] 100% of functions have complete type signatures
- [ ] No `# type: ignore` comments without justification

**Validation Commands:**
```bash
# Type checking
mypy src/ --strict --show-error-codes

# Run all tests to ensure no regressions
pytest tests/ -v

# Pre-commit validation
pre-commit run --all-files

# CI simulation
.github/workflows/ci.yml  # Verify passes locally
```

---

## WS2: Embedding Cache Optimization (8-10 hours)

### Current State

**Existing Implementation (WS1):**
- Basic embedding cache exists in `src/search.py`
- Uses document SHA-256 as cache key
- No cache metrics or observability
- No eviction policy (unbounded growth)
- No cache warming strategy

**Performance Gaps:**
- Unknown cache hit rate (no instrumentation)
- Potential memory exhaustion (no size limits)
- No invalidation strategy for schema changes
- Cache lookups not profiled

**Cost Opportunity:**
- Embedding API calls: $0.0001 per 1K tokens
- Average document: 5,000 tokens = $0.0005 per embedding
- Estimated 200 documents/day with 40% duplicates
- Potential savings: 80 calls/day * $0.0005 = **$1.20/day = $36/month**
- With optimized cache (60% hit rate): **$50-100/month savings**

### Implementation Plan

#### Phase 1: Cache Key Strategy (2 hours)

**Task 1.1: Implement Stable Cache Keys (1 hour)**

**Current Implementation:**
```python
# src/search.py (WS1 baseline)
def get_embedding_from_cache(doc_hash: str) -> Optional[List[float]]:
    """Retrieve cached embedding by document hash."""
    # Simple SHA-256 lookup, no versioning
    ...
```

**Enhanced Implementation:**
```python
# src/cache.py (new module)
import hashlib
from typing import Optional, List
from dataclasses import dataclass

@dataclass
class CacheKey:
    """Structured cache key with version tracking."""
    doc_hash: str
    model: str
    schema_version: str = "v1"

    def to_string(self) -> str:
        """Generate stable cache key string."""
        key_material = f"{self.doc_hash}:{self.model}:{self.schema_version}"
        return hashlib.sha256(key_material.encode()).hexdigest()[:16]

def generate_cache_key(
    doc_hash: str,
    model: str = "text-embedding-3-small",
    schema_version: str = "v1",
) -> str:
    """
    Generate deterministic cache key.

    Args:
        doc_hash: Document SHA-256 hash (hex)
        model: OpenAI embedding model identifier
        schema_version: Schema version for invalidation

    Returns:
        16-character hex cache key

    Example:
        >>> generate_cache_key("abc123", "text-embedding-3-small")
        'e8f5a3b2c1d4e7f6'
    """
    key = CacheKey(doc_hash, model, schema_version)
    return key.to_string()
```

**Task 1.2: Add Cache Key Tests (1 hour)**
```python
# tests/unit/test_cache.py
from hypothesis import given, strategies as st
from src.cache import generate_cache_key

def test_cache_key_determinism():
    """Same inputs produce same cache key."""
    key1 = generate_cache_key("abc123", "text-embedding-3-small")
    key2 = generate_cache_key("abc123", "text-embedding-3-small")
    assert key1 == key2

@given(
    doc_hash=st.text(min_size=64, max_size=64, alphabet="0123456789abcdef"),
    model=st.sampled_from(["text-embedding-3-small", "text-embedding-3-large"]),
)
def test_cache_key_properties(doc_hash: str, model: str):
    """Cache keys satisfy cryptographic properties."""
    key = generate_cache_key(doc_hash, model)

    # Fixed length
    assert len(key) == 16

    # Hex characters only
    assert all(c in "0123456789abcdef" for c in key)

    # Deterministic
    assert key == generate_cache_key(doc_hash, model)

def test_cache_key_collision_resistance():
    """Different inputs produce different keys."""
    key1 = generate_cache_key("abc123", "text-embedding-3-small")
    key2 = generate_cache_key("abc124", "text-embedding-3-small")
    assert key1 != key2

def test_cache_key_schema_versioning():
    """Schema version changes invalidate cache."""
    key_v1 = generate_cache_key("abc123", "text-embedding-3-small", "v1")
    key_v2 = generate_cache_key("abc123", "text-embedding-3-small", "v2")
    assert key_v1 != key_v2
```

---

#### Phase 2: Cache Metrics (3 hours)

**Task 2.1: Create Metrics Dataclass (45 min)**
```python
# src/cache.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict

@dataclass
class CacheMetrics:
    """Embedding cache performance metrics."""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    size_bytes: int = 0
    max_size_bytes: int = 100 * 1024 * 1024  # 100MB default
    entries: int = 0
    max_entries: int = 1000  # LRU limit
    last_reset: datetime = field(default_factory=datetime.utcnow)

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate percentage."""
        total = self.hits + self.misses
        return (self.hits / total * 100) if total > 0 else 0.0

    @property
    def memory_utilization(self) -> float:
        """Calculate memory usage percentage."""
        return (self.size_bytes / self.max_size_bytes * 100)

    def to_dict(self) -> Dict[str, Any]:
        """Export metrics as dictionary for logging."""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "entries": self.entries,
            "hit_rate_pct": round(self.hit_rate, 2),
            "memory_utilization_pct": round(self.memory_utilization, 2),
            "size_mb": round(self.size_bytes / (1024 * 1024), 2),
        }
```

**Task 2.2: Instrument Cache Operations (1 hour)**
```python
# src/cache.py
import logging

logger = logging.getLogger(__name__)

class EmbeddingCache:
    """Thread-safe embedding cache with metrics."""

    def __init__(
        self,
        max_entries: int = 1000,
        max_size_bytes: int = 100 * 1024 * 1024,
    ) -> None:
        self._cache: Dict[str, List[float]] = {}
        self._access_order: List[str] = []  # For LRU
        self.metrics = CacheMetrics(
            max_entries=max_entries,
            max_size_bytes=max_size_bytes,
        )

    def get(self, key: str) -> Optional[List[float]]:
        """Retrieve embedding from cache."""
        if key in self._cache:
            self.metrics.hits += 1
            self._access_order.remove(key)
            self._access_order.append(key)  # Move to end (most recent)
            logger.debug(f"Cache hit: {key}")
            return self._cache[key]
        else:
            self.metrics.misses += 1
            logger.debug(f"Cache miss: {key}")
            return None

    def set(self, key: str, embedding: List[float]) -> None:
        """Store embedding in cache with LRU eviction."""
        embedding_size = len(embedding) * 8  # 8 bytes per float64

        # Evict if at capacity
        while (
            self.metrics.entries >= self.metrics.max_entries
            or self.metrics.size_bytes + embedding_size > self.metrics.max_size_bytes
        ):
            self._evict_lru()

        self._cache[key] = embedding
        self._access_order.append(key)
        self.metrics.entries += 1
        self.metrics.size_bytes += embedding_size
        logger.debug(f"Cache set: {key} ({embedding_size} bytes)")

    def _evict_lru(self) -> None:
        """Evict least recently used entry."""
        if not self._access_order:
            return

        lru_key = self._access_order.pop(0)
        embedding = self._cache.pop(lru_key)
        embedding_size = len(embedding) * 8

        self.metrics.evictions += 1
        self.metrics.entries -= 1
        self.metrics.size_bytes -= embedding_size
        logger.info(f"Cache eviction: {lru_key} ({self.metrics.hit_rate:.1f}% hit rate)")

    def get_metrics(self) -> Dict[str, Any]:
        """Export current metrics."""
        return self.metrics.to_dict()
```

**Task 2.3: Add Structured Logging (45 min)**
```python
# src/cache.py
import json

def log_cache_metrics(cache: EmbeddingCache) -> None:
    """Log cache metrics as structured JSON."""
    metrics = cache.get_metrics()
    logger.info(json.dumps({
        "event": "cache_metrics",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        **metrics,
    }))

# Call periodically (e.g., every 100 operations or 5 minutes)
```

**Task 2.4: Grafana Dashboard Spec (30 min)**
```yaml
# docs/observability/embedding_cache_dashboard.yaml
dashboard:
  title: "Embedding Cache Performance"
  panels:
    - title: "Hit Rate"
      type: "gauge"
      query: "cache.hit_rate_pct"
      thresholds:
        - value: 40, color: red
        - value: 60, color: yellow
        - value: 80, color: green

    - title: "Memory Utilization"
      type: "gauge"
      query: "cache.memory_utilization_pct"
      thresholds:
        - value: 80, color: yellow
        - value: 95, color: red

    - title: "Cache Operations (Hits/Misses/Evictions)"
      type: "graph"
      queries:
        - "rate(cache.hits[5m])"
        - "rate(cache.misses[5m])"
        - "rate(cache.evictions[5m])"
```

---

#### Phase 3: Cache Management (2-3 hours)

**Task 3.1: LRU Eviction Policy (implemented in Phase 2)**

**Task 3.2: Cache Invalidation Strategy (1 hour)**
```python
# src/cache.py

CACHE_SCHEMA_VERSION = "v1"  # Increment on breaking changes

def invalidate_cache_on_schema_change() -> None:
    """
    Clear cache when schema version changes.

    Called during application startup to detect schema drift.
    Prevents serving embeddings from incompatible schema versions.
    """
    stored_version = get_stored_schema_version()  # From config/database

    if stored_version != CACHE_SCHEMA_VERSION:
        logger.warning(
            f"Schema version changed: {stored_version} → {CACHE_SCHEMA_VERSION}. "
            "Clearing embedding cache."
        )
        cache.clear()
        update_stored_schema_version(CACHE_SCHEMA_VERSION)

def get_stored_schema_version() -> str:
    """Retrieve schema version from persistent storage."""
    # Could use: config file, database metadata table, or .cache_version file
    ...

def update_stored_schema_version(version: str) -> None:
    """Persist new schema version."""
    ...
```

**Task 3.3: Cache Warming Strategy (1 hour)**
```python
# src/cache.py

def warm_cache(
    session: Session,
    cache: EmbeddingCache,
    doc_types: Optional[List[str]] = None,
) -> int:
    """
    Pre-populate cache with embeddings for common document types.

    Args:
        session: Database session
        cache: Embedding cache instance
        doc_types: Optional list of document types to warm (e.g., ["Invoice", "Receipt"])

    Returns:
        Number of embeddings cached
    """
    from src.models import Document

    query = session.query(Document)

    if doc_types:
        # Filter by document type from metadata
        query = query.filter(
            Document.metadata_json["doc_type"].astext.in_(doc_types)
        )

    # Get most recent 500 documents (or top N by frequency)
    documents = query.order_by(Document.created_at.desc()).limit(500).all()

    warmed = 0
    for doc in documents:
        if doc.embedding_vector:  # Only warm if embedding exists
            cache_key = generate_cache_key(doc.sha256_hex, "text-embedding-3-small")
            cache.set(cache_key, doc.embedding_vector)
            warmed += 1

    logger.info(f"Cache warming completed: {warmed} embeddings cached")
    return warmed
```

**Task 3.4: Admin CLI (30 min)**
```python
# scripts/cache_admin.py
import click
from src.cache import EmbeddingCache, warm_cache
from src.database import DatabaseManager

@click.group()
def cli():
    """Embedding cache administration CLI."""
    pass

@cli.command()
def stats():
    """Display cache statistics."""
    cache = get_global_cache()
    metrics = cache.get_metrics()

    click.echo("Embedding Cache Statistics:")
    click.echo(f"  Hit Rate: {metrics['hit_rate_pct']:.1f}%")
    click.echo(f"  Entries: {metrics['entries']}")
    click.echo(f"  Memory: {metrics['size_mb']:.1f} MB")
    click.echo(f"  Evictions: {metrics['evictions']}")

@cli.command()
def clear():
    """Clear all cache entries."""
    cache = get_global_cache()
    cache.clear()
    click.echo("Cache cleared successfully")

@cli.command()
@click.option("--doc-types", multiple=True, help="Document types to warm")
def warm(doc_types):
    """Pre-populate cache with common documents."""
    db = DatabaseManager("sqlite:///app.db")
    cache = get_global_cache()

    with db.get_session() as session:
        count = warm_cache(session, cache, list(doc_types) if doc_types else None)

    click.echo(f"Warmed cache with {count} embeddings")

if __name__ == "__main__":
    cli()
```

---

#### Phase 4: Testing (2-3 hours)

**Task 4.1: Unit Tests (1.5 hours)**
```python
# tests/unit/test_cache.py
import pytest
from hypothesis import given, strategies as st
from src.cache import EmbeddingCache, generate_cache_key

def test_cache_basic_operations():
    """Test cache get/set/eviction."""
    cache = EmbeddingCache(max_entries=2, max_size_bytes=1024)

    embedding1 = [0.1] * 100
    embedding2 = [0.2] * 100
    embedding3 = [0.3] * 100

    # Set and retrieve
    cache.set("key1", embedding1)
    assert cache.get("key1") == embedding1
    assert cache.metrics.hits == 1
    assert cache.metrics.misses == 0

    # Cache miss
    assert cache.get("key_nonexistent") is None
    assert cache.metrics.misses == 1

    # LRU eviction
    cache.set("key2", embedding2)
    cache.set("key3", embedding3)  # Should evict key1 (LRU)
    assert cache.get("key1") is None
    assert cache.get("key2") == embedding2
    assert cache.metrics.evictions == 1

def test_cache_metrics_calculation():
    """Test hit rate and memory calculations."""
    cache = EmbeddingCache()

    cache.set("key1", [0.1] * 100)
    cache.get("key1")  # Hit
    cache.get("key2")  # Miss
    cache.get("key1")  # Hit

    assert cache.metrics.hits == 2
    assert cache.metrics.misses == 1
    assert cache.metrics.hit_rate == pytest.approx(66.67, rel=0.1)

@given(embeddings=st.lists(st.lists(st.floats(), min_size=100, max_size=100), min_size=1, max_size=10))
def test_cache_eviction_under_memory_pressure(embeddings):
    """Property test: cache respects memory limits."""
    cache = EmbeddingCache(max_entries=5, max_size_bytes=4000)  # ~5 embeddings

    for i, emb in enumerate(embeddings):
        cache.set(f"key{i}", emb)

    # Cache size should never exceed limits
    assert cache.metrics.entries <= cache.metrics.max_entries
    assert cache.metrics.size_bytes <= cache.metrics.max_size_bytes
```

**Task 4.2: Integration Tests (1 hour)**
```python
# tests/integration/test_cache_integration.py
import pytest
from src.cache import EmbeddingCache, warm_cache
from src.database import DatabaseManager
from src.models import Document

def test_cache_warming_from_database(db_session):
    """Test cache population from database."""
    # Insert test documents
    for i in range(10):
        doc = Document(
            sha256_hex=f"hash{i}",
            sha256_base64=f"b64hash{i}",
            metadata_json={"doc_type": "Invoice"},
            embedding_vector=[0.1 * i] * 100,
            status="completed",
        )
        db_session.add(doc)
    db_session.commit()

    # Warm cache
    cache = EmbeddingCache()
    count = warm_cache(db_session, cache, doc_types=["Invoice"])

    assert count == 10
    assert cache.metrics.entries == 10

def test_cache_schema_invalidation(db_session):
    """Test cache clearing on schema version change."""
    cache = EmbeddingCache()
    cache.set("key1", [0.1] * 100)

    # Simulate schema change
    invalidate_cache_on_schema_change()  # Should clear cache

    assert cache.metrics.entries == 0
    assert cache.get("key1") is None
```

**Task 4.3: Performance Benchmarks (30 min)**
```python
# tests/performance/test_cache_performance.py
import time
import pytest
from src.cache import EmbeddingCache

def test_cache_lookup_latency():
    """Benchmark cache lookup performance."""
    cache = EmbeddingCache()
    embedding = [0.1] * 1536  # text-embedding-3-small dimension

    # Populate cache
    for i in range(1000):
        cache.set(f"key{i}", embedding)

    # Measure lookup time
    start = time.perf_counter()
    for i in range(1000):
        _ = cache.get(f"key{i}")
    elapsed_ms = (time.perf_counter() - start) * 1000

    avg_latency_ms = elapsed_ms / 1000
    assert avg_latency_ms < 5, f"Cache lookup too slow: {avg_latency_ms:.2f}ms (target: <5ms)"

def test_cache_memory_overhead():
    """Verify cache memory efficiency."""
    cache = EmbeddingCache()
    embedding = [0.1] * 1536

    cache.set("key1", embedding)

    expected_size = len(embedding) * 8  # 8 bytes per float64
    actual_size = cache.metrics.size_bytes

    # Allow 10% overhead for metadata
    assert actual_size <= expected_size * 1.1
```

---

### Success Criteria

**Phase Completion Checklist:**
- [ ] Cache keys generated deterministically with SHA-256
- [ ] Cache metrics tracked (hits, misses, evictions, size)
- [ ] LRU eviction policy implemented and tested
- [ ] Cache hit rate ≥60% for repeated documents
- [ ] Cache lookup latency <5ms P95
- [ ] Memory footprint ≤100MB with 1000 entries
- [ ] Schema invalidation strategy documented and tested
- [ ] Cache warming CLI functional
- [ ] Grafana dashboard spec created
- [ ] Comprehensive test suite (unit + integration + performance)
- [ ] Observability: structured logs + metrics exported
- [ ] Documentation: cache architecture + admin guide

**Validation Commands:**
```bash
# Unit tests
pytest tests/unit/test_cache.py -v

# Integration tests
pytest tests/integration/test_cache_integration.py -v

# Performance benchmarks
pytest tests/performance/test_cache_performance.py -v

# Admin CLI
python scripts/cache_admin.py stats
python scripts/cache_admin.py warm --doc-types Invoice Receipt

# Metrics verification
grep "cache_metrics" logs/app.log | jq '.hit_rate_pct'
```

---

## Wave 2 Timeline

**Total Scope:** 16-22 hours (2-3 days focused development)

**Proposed Schedule:**
```
Day 1 (8 hours):
  08:00-10:00  TD3 Phase 1: Enable strict mode + baseline
  10:00-12:00  TD3 Phase 2: Fix src/config.py, src/processor.py
  13:00-15:00  TD3 Phase 2: Fix src/dedupe.py, src/transactions.py
  15:00-17:00  TD3 Phase 2: Fix remaining modules

Day 2 (8 hours):
  08:00-11:00  TD3 Phase 3: Add type stubs + internal types
  11:00-12:00  TD3 Phase 4: CI integration + docs
  13:00-15:00  WS2 Phase 1: Cache key strategy + tests
  15:00-17:00  WS2 Phase 2: Cache metrics + logging

Day 3 (6 hours):
  08:00-11:00  WS2 Phase 3: Cache management (warming, CLI)
  11:00-14:00  WS2 Phase 4: Comprehensive testing

Buffer: 2-4 hours for unexpected issues
```

**Dependencies:**
- None (both workstreams independent)
- Can be parallelized if multiple developers available

**Risks:**
- Type stub complexity for OpenAI library (mitigated by simple `.pyi` files)
- LRU eviction edge cases (mitigated by property-based tests)
- Cache memory profiling may reveal need for optimization

---

## Post-Wave 2 Success Metrics

**TD3 Impact:**
- MyPy warnings: 49 → 0 (100% reduction)
- Type coverage: ~60% → 100% (+67% improvement)
- IDE autocomplete: Partial → Full (developer experience)
- Onboarding time: -20% (better code discoverability)

**WS2 Impact:**
- API calls: -20-40% (cache hit rate 60%+)
- Monthly costs: -$50-100 (embedding API savings)
- Pipeline latency: -10-20% (cached lookups faster)
- Observability: 0 → Full (metrics + logs)

**Combined Business Value:**
- Development velocity: +5-10% (type safety + faster debugging)
- Cost savings: $600-1,200/year (API costs)
- Quality: Higher (type safety catches bugs earlier)
- Maintainability: Improved (explicit contracts)

---

## References

**TD3 (MyPy Strict Mode):**
- [MyPy Documentation - Strict Mode](https://mypy.readthedocs.io/en/stable/command_line.html#cmdoption-mypy-strict)
- [PEP 484 - Type Hints](https://peps.python.org/pep-0484/)
- [Python Type Checking Guide](https://realpython.com/python-type-checking/)

**WS2 (Embedding Cache):**
- [LRU Cache Implementation Patterns](https://en.wikipedia.org/wiki/Cache_replacement_policies#Least_recently_used_(LRU))
- [OpenAI Embeddings Pricing](https://openai.com/pricing)
- [Cache Warming Strategies](https://aws.amazon.com/caching/best-practices/)

**Internal Documentation:**
- ADR-024: Workstream Deferral Decision
- docs/sessions/2025-10-23.md: Wave 1 Integration Audit Trail
- CHANGELOG.md: Version History

---

**Last Updated:** 2025-10-23
**Owner:** Technical Lead
**Next Review:** 2025-10-24 (Wave 2 kickoff)
