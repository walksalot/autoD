# Week 3 Execution Plan: Vector Store + Error Handling + Cache Integration

**Created**: 2025-10-23
**Status**: In Progress (Phase 1 Complete)
**Approach**: Sequential development on main branch
**Scope**: ~30-40 hours over 5 phases

---

## Executive Summary

**Priority Workstreams**:
1. WS1: Vector Store Implementation (OpenAI Vector Store API integration)
2. TD1: Error Handling Consolidation (CompensatingTransaction pattern)
3. Cache Integration: Refactor EmbeddingGenerator to use production `src/cache.py`

**Quick Wins Completed** ✅:
- test_search.py API fixed (51/51 tests passing)
- Worktree cleanup strategy documented

**Success Criteria**:
- ✅ test_search.py: All tests passing (Phase 1.1)
- 🔄 Cache: EmbeddingGenerator refactored to use `src/cache.py` (Phase 2)
- ⏳ WS1: Full OpenAI Vector Store integration (Phase 3)
- ⏳ TD1: CompensatingTransaction pattern complete (Phase 4)
- ⏳ Documentation: Session notes, ADRs, guides (Phase 5)

---

## Phase 1: Quick Wins & Cleanup ✅ COMPLETE

### Phase 1.1: Fix test_search.py API Incompatibility ✅

**Problem**: Embedding vector format inconsistency
- Document model stores `embedding_vector` as JSON dict: `{"embedding": [floats]}`
- src/embeddings.py:268 stores as: `doc.embedding_vector = {"embedding": result.embedding}`
- src/search.py:395 expects dict: `doc.embedding_vector["embedding"]`
- Tests provided list directly: `embedding_vector=[0.9, 0.1, ...]` ❌

**Solution**: Updated all test fixtures to use correct dict format

**Files Modified**:
- `tests/unit/test_search.py`: Fixed 6 embedding_vector assignments

**Test Results**:
- Before: 13 passing, 38 failing
- After: 51 passing, 0 failing ✅

**Commit**: `d0ce3dd` - "fix(tests): correct embedding_vector format in test_search.py"

**Duration**: 30 minutes

---

### Phase 1.2: Worktree Cleanup Strategy ✅

**Decision**: Defer detailed worktree cleanup
- **Rationale**: Working sequentially on main branch (user preference)
- **Active Worktrees**: 7 total (config-management merged, others deferred)
- **Action**: Continue on main, worktrees available if needed for parallel work later

**Preserved Worktrees** (for potential future use):
- `autoD-error-handling` (TD1 - Error Handling)
- `autoD-vector-store` (WS1 - Vector Store)
- `autoD-production-hardening` (WS3 - Production Hardening)
- `autoD-test-coverage` (TD4 - Test Coverage)

**Duration**: Deferred (not critical for sequential workflow)

---

## Phase 2: Cache Integration (6-8 hours)

### Phase 2.1: Refactor EmbeddingGenerator to Use src/cache.py

**Current Architecture**:
```
EmbeddingGenerator (src/embeddings.py)
├── Embedded LRU cache (lines 120-189) ❌ DUPLICATE
├── Cache order tracking (manual LIFO)
├── Cache metrics (manual counters)
└── 3-tier caching (memory → DB → API)

Production Cache (src/cache.py)
├── LRU cache with SHA-256 keys ✅
├── CacheMetrics dataclass ✅
├── Automatic eviction ✅
└── NOT USED by EmbeddingGenerator ❌
```

**Target Architecture**:
```
EmbeddingGenerator (refactored)
├── Uses src/cache.py for memory cache ✅
├── Delegates to EmbeddingCache for DB ✅
└── Simplified 2-tier: Cache → API ✅

src/cache.py (production module)
├── Generic CacheProtocol[T] interface
├── LRU with SHA-256 keys
└── Type-safe cache operations

EmbeddingCache (src/embedding_cache.py)
├── Database-backed cache (Tier 2)
└── Wraps EmbeddingGenerator
```

**Implementation Steps**:

1. **Add CacheProtocol interface to src/cache.py**:
```python
# src/cache.py additions

from typing import Protocol, TypeVar, Generic, Optional

T = TypeVar('T')

class CacheProtocol(Protocol[T]):
    """Generic cache interface for type-safe operations."""
    def get(self, key: str) -> Optional[T]: ...
    def put(self, key: str, value: T) -> None: ...
    def clear(self) -> None: ...
    def get_metrics(self) -> CacheMetrics: ...

# Make existing EmbeddingCache generic
class LRUCache(Generic[T]):
    """LRU cache with SHA-256 keys and metrics tracking."""
    def __init__(self, max_size: int = 1000):
        self._cache: Dict[str, T] = {}
        self._order: List[str] = []  # LIFO order
        self.max_size = max_size
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[T]:
        if key in self._cache:
            # Move to end (mark as recently used)
            self._order.remove(key)
            self._order.append(key)
            self.hits += 1
            return self._cache[key]
        self.misses += 1
        return None

    def put(self, key: str, value: T) -> None:
        # Evict oldest if full
        if len(self._cache) >= self.max_size and key not in self._cache:
            oldest = self._order.pop(0)
            del self._cache[oldest]

        if key in self._cache:
            self._order.remove(key)

        self._cache[key] = value
        self._order.append(key)

    def get_metrics(self) -> CacheMetrics:
        total = self.hits + self.misses
        hit_rate = self.hits / total if total > 0 else 0.0
        return CacheMetrics(
            cache_size=len(self._cache),
            max_size=self.max_size,
            hits=self.hits,
            misses=self.misses,
            hit_rate=hit_rate
        )
```

2. **Refactor EmbeddingGenerator to use LRUCache**:
```python
# src/embeddings.py changes

from src.cache import LRUCache, CacheMetrics, generate_cache_key

class EmbeddingGenerator:
    """Generate and cache document embeddings using OpenAI API."""

    def __init__(
        self,
        client: OpenAI,
        session: Optional[Session] = None,
        model: str = EMBEDDING_MODEL,
        dimensions: int = EMBEDDING_DIMENSIONS,
        max_cache_size: int = 1000,
    ):
        self.client = client
        self.session = session
        self.model = model
        self.dimensions = dimensions

        # USE PRODUCTION CACHE (replaces lines 120-189)
        self._cache = LRUCache[EmbeddingResult](max_size=max_cache_size)

        # Statistics (2-tier cache: memory + DB)
        self.db_cache_hits = 0
        self.api_calls = 0
        self.total_tokens = 0

    def _compute_cache_key(self, text: str) -> str:
        """Compute SHA-256 cache key using production function."""
        # Use cache module's key generation
        doc_hash = hashlib.sha256(text.encode()).hexdigest()
        return generate_cache_key(
            doc_hash=doc_hash,
            model=self.model,
            schema_version="v1"
        )

    def _get_from_cache(self, cache_key: str) -> Optional[EmbeddingResult]:
        """Retrieve from production cache."""
        result = self._cache.get(cache_key)
        if result:
            result.cached = True
            logger.debug(f"Memory cache hit for key {cache_key[:12]}...")
        return result

    def _add_to_cache(self, cache_key: str, result: EmbeddingResult) -> None:
        """Add to production cache."""
        self._cache.put(cache_key, result)
        logger.debug(f"Cached embedding for key {cache_key[:12]}...")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics."""
        metrics = self._cache.get_metrics()
        total_cache_hits = metrics.hits + self.db_cache_hits
        total_requests = total_cache_hits + self.api_calls

        return {
            "cache_size": metrics.cache_size,
            "max_cache_size": metrics.max_size,
            "memory_cache_hits": metrics.hits,
            "db_cache_hits": self.db_cache_hits,
            "total_cache_hits": total_cache_hits,
            "api_calls": self.api_calls,
            "total_requests": total_requests,
            "memory_hit_rate": metrics.hit_rate,
            "overall_hit_rate": total_cache_hits / total_requests if total_requests > 0 else 0.0,
            "total_tokens": self.total_tokens,
        }

    # Rest of methods remain the same...
```

**Files Modified**:
- `src/cache.py`: Add CacheProtocol, make LRUCache generic (~50 lines added)
- `src/embeddings.py`: Refactor to use LRUCache (~70 lines removed, ~20 added)
- `src/embedding_cache.py`: Update for compatibility (~10 lines modified)

**Tests Required**:
- Update `tests/unit/test_cache.py` for CacheProtocol
- Update `tests/unit/test_embeddings.py` for new cache integration
- Add integration test: EmbeddingGenerator → LRUCache → metrics

**Success Criteria**:
- ✅ EmbeddingGenerator uses production `src/cache.py`
- ✅ All embedding tests passing
- ✅ Cache metrics accurate (hit rate, latency)
- ✅ <0.1ms cache latency maintained
- ✅ 70%+ hit rate maintained
- ✅ MyPy strict passing (0 errors)

**Duration**: 5-6 hours

---

### Phase 2.2: Cache Integration Testing

**Test Categories**:

1. **Unit Tests** (tests/unit/test_cache.py):
   - CacheProtocol interface compliance
   - LRUCache generic type safety
   - Metrics calculation accuracy
   - Eviction policy correctness

2. **Integration Tests** (tests/integration/test_cache_integration.py):
   - EmbeddingGenerator + LRUCache integration
   - Cache metrics aggregation (memory + DB)
   - Multi-tier cache behavior (memory → DB → API)

3. **Performance Tests** (tests/performance/test_cache_performance.py):
   - Latency: <0.1ms P50, <0.2ms P95
   - Throughput: >1M lookups/sec
   - Hit rate: 70%+ with temporal locality
   - Memory efficiency: >90%

**Test Execution**:
```bash
# Run all cache tests
pytest tests/unit/test_cache.py tests/integration/test_cache_integration.py tests/performance/test_cache_performance.py -v

# Expected results:
# - 41 Wave 2 tests (from original WS2)
# - 10-15 new integration tests
# - Total: ~55 cache tests passing
```

**Success Criteria**:
- ✅ All cache tests passing (100%)
- ✅ Performance targets met
- ✅ Integration validated

**Duration**: 1-2 hours

---

## Phase 3: WS1 Vector Store Implementation (10-14 hours)

### Phase 3.1: OpenAI Vector Store API Integration

**Latest 2025 Best Practices** (from web search research):

**OpenAI Vector Store API** (March 2025 release):
- ✅ Hybrid search: semantic + keyword (automatic)
- ✅ Built-in reranking
- ✅ Limits: 10,000 files per vector store
- ✅ Cost: $0.10/GB/day after first free GB
- ✅ Async file processing (use `create_and_poll` helpers)
- ✅ Metadata filtering capabilities

**Implementation**: Complete `src/vector_store.py`

```python
# src/vector_store.py (full implementation)

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timezone

from openai import OpenAI
from openai.types.beta.vector_stores import VectorStore
from openai.types.beta.vector_stores.vector_store_file import VectorStoreFile

from src.config import get_config
from src.models import Document
from src.retry_logic import retry

logger = logging.getLogger(__name__)


@dataclass
class VectorStoreMetrics:
    """Metrics for vector store operations."""
    total_files: int
    ready_files: int
    failed_files: int
    processing_files: int
    status: str  # "ready", "processing", "error"
    last_updated: datetime
    size_estimate_mb: float


class VectorStoreManager:
    """
    Manages OpenAI Vector Store operations with file upload and hybrid search.

    Features:
    - Automatic PDF chunking and embedding
    - Hybrid search (semantic + keyword)
    - Built-in reranking
    - Async file processing with polling
    - Cost tracking ($0.10/GB/day)

    2025 Best Practices:
    - Use create_and_poll for reliable async uploads
    - Monitor file processing status
    - Track storage costs
    - Implement retry logic for transient failures

    Example:
        client = OpenAI(api_key="sk-...")
        manager = VectorStoreManager(client)

        # Upload document
        vs_file = manager.upload_document(document)

        # Search
        results = manager.search("invoices from ACME", limit=10)
    """

    def __init__(self, client: OpenAI, vector_store_id: Optional[str] = None):
        """
        Initialize Vector Store Manager.

        Args:
            client: OpenAI client instance
            vector_store_id: Existing vector store ID (or None to create new)
        """
        self.client = client
        self.config = get_config()

        # Create or connect to vector store
        if vector_store_id:
            self.vector_store = self._get_vector_store(vector_store_id)
            logger.info(f"Connected to existing vector store: {vector_store_id}")
        else:
            self.vector_store = self._create_vector_store()
            logger.info(f"Created new vector store: {self.vector_store.id}")

    @retry()
    def _create_vector_store(self) -> VectorStore:
        """Create new vector store with project metadata."""
        return self.client.beta.vector_stores.create(
            name=f"autoD-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}",
            metadata={
                "project": "autoD",
                "environment": self.config.environment,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "version": "1.0"
            }
        )

    @retry()
    def _get_vector_store(self, vector_store_id: str) -> VectorStore:
        """Retrieve existing vector store by ID."""
        return self.client.beta.vector_stores.retrieve(vector_store_id)

    @retry()
    def upload_document(self, document: Document) -> VectorStoreFile:
        """
        Upload PDF to vector store with automatic chunking/embedding.

        Workflow:
        1. Upload file to Files API
        2. Add to vector store (async processing)
        3. Poll until processing complete
        4. Return vector store file object

        Args:
            document: Document model instance with file_path

        Returns:
            VectorStoreFile with status "completed"

        Raises:
            ValueError: If document.file_path doesn't exist
            Exception: If upload or processing fails

        Cost: ~$0.00002/1K tokens for embedding + $0.10/GB/day storage
        """
        # Step 1: Upload to Files API
        with open(document.file_path, "rb") as f:
            file = self.client.files.create(
                file=f,
                purpose="assistants"  # Required for vector stores
            )

        logger.info(
            f"Uploaded file to Files API: {file.id}",
            extra={
                "document_id": document.id,
                "filename": document.original_filename,
                "file_id": file.id
            }
        )

        # Step 2: Add to vector store (async, with polling)
        vs_file = self.client.beta.vector_stores.files.create_and_poll(
            vector_store_id=self.vector_store.id,
            file_id=file.id
        )

        logger.info(
            f"Document processing complete: {vs_file.status}",
            extra={
                "document_id": document.id,
                "file_id": file.id,
                "vector_store_id": self.vector_store.id,
                "status": vs_file.status
            }
        )

        return vs_file

    @retry()
    def search(
        self,
        query: str,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Hybrid search via OpenAI Responses API with file_search tool.

        Features:
        - Semantic + keyword search (automatic)
        - Built-in reranking
        - Metadata filtering (if supported by API)

        Args:
            query: Search query text
            limit: Maximum number of results (default: 10)
            filters: Optional metadata filters (doc_type, issuer, etc.)

        Returns:
            List of search results with relevance scores

        Cost: Standard Responses API pricing (gpt-5-mini: $0.25/1M input)

        Example:
            results = manager.search(
                query="invoices from ACME Corp in 2024",
                limit=10,
                filters={"doc_type": "Invoice"}
            )
        """
        # Use Responses API with file_search tool
        response = self.client.responses.create(
            model=self.config.openai_model,  # gpt-5-mini by default
            input=[
                {
                    "role": "user",
                    "content": query
                }
            ],
            tools=[{
                "type": "file_search",
                "file_search": {
                    "vector_stores": [self.vector_store.id],
                    "max_num_results": limit
                }
            }],
            reasoning_effort="minimal",  # 2025 best practice for search
            verbosity="low"  # Concise output for search results
        )

        # Parse response and extract file references
        # Note: Actual parsing depends on Responses API output format
        results = self._parse_search_response(response)

        logger.info(
            f"Search complete: {len(results)} results",
            extra={
                "query": query,
                "result_count": len(results),
                "vector_store_id": self.vector_store.id
            }
        )

        return results

    def _parse_search_response(self, response: Any) -> List[Dict[str, Any]]:
        """
        Parse Responses API output to extract search results.

        Expected output format (varies by model):
        - response.output: Text with embedded file references
        - response.reasoning: Optional reasoning trace
        - Need to extract file IDs and relevance indicators

        Returns:
            List of dicts with: file_id, relevance_score, snippet
        """
        # TODO: Implement based on actual Responses API format
        # This will depend on how GPT-5 formats file_search results
        return []

    def get_metrics(self) -> VectorStoreMetrics:
        """
        Get vector store usage and performance metrics.

        Returns:
            VectorStoreMetrics with file counts, status, size estimate
        """
        vs = self._get_vector_store(self.vector_store.id)

        # Calculate size estimate (rough)
        # Average PDF: ~2MB, embedded: ~12KB overhead
        size_mb = vs.file_counts.completed * 2.012  # 2MB + 12KB

        return VectorStoreMetrics(
            total_files=vs.file_counts.total,
            ready_files=vs.file_counts.completed,
            failed_files=vs.file_counts.failed,
            processing_files=vs.file_counts.in_progress,
            status=vs.status,
            last_updated=datetime.now(timezone.utc),
            size_estimate_mb=size_mb
        )

    def get_cost_estimate(self) -> Dict[str, Any]:
        """
        Estimate monthly storage costs.

        Returns:
            Dict with daily_cost, monthly_cost, size_gb

        Pricing: $0.10/GB/day after first free GB
        """
        metrics = self.get_metrics()
        size_gb = metrics.size_estimate_mb / 1024

        # Free tier: 1 GB
        billable_gb = max(0, size_gb - 1.0)
        daily_cost = billable_gb * 0.10
        monthly_cost = daily_cost * 30

        return {
            "size_gb": size_gb,
            "billable_gb": billable_gb,
            "daily_cost_usd": daily_cost,
            "monthly_cost_usd": monthly_cost,
            "free_tier_gb": 1.0
        }

    @retry()
    def cleanup(self) -> None:
        """Delete vector store and all associated files."""
        self.client.beta.vector_stores.delete(self.vector_store.id)
        logger.info(f"Deleted vector store: {self.vector_store.id}")
```

**Integration with Processor Pipeline**:

```python
# src/processor.py additions

from src.vector_store import VectorStoreManager

class DocumentProcessor:
    def __init__(self, client: OpenAI, session: Session):
        self.client = client
        self.session = session

        # Initialize vector store manager
        self.vector_store_manager = VectorStoreManager(
            client=client,
            vector_store_id=get_config().vector_store_id  # From config
        )

    def process_document(self, document: Document) -> ProcessingResult:
        """Process document with vector store upload."""
        try:
            # ... existing stages (upload, extract, save) ...

            # NEW: Upload to vector store (after DB save)
            if document.status == "completed":
                vs_file = self.vector_store_manager.upload_document(document)

                # Store vector store file ID in document
                document.vector_store_file_id = vs_file.id
                self.session.commit()

                logger.info(
                    f"Uploaded to vector store: {vs_file.id}",
                    extra={"document_id": document.id}
                )

            return ProcessingResult(success=True, document=document)

        except Exception as e:
            logger.error(f"Processing failed: {e}")
            raise
```

**Files Modified**:
- `src/vector_store.py`: Complete implementation (~400 lines)
- `src/processor.py`: Add vector store upload stage (~30 lines)
- `src/models.py`: Add `vector_store_file_id` field if not exists
- `src/config.py`: Add `vector_store_id` config field

**Tests Required**:
- `tests/unit/test_vector_store.py` (new file, ~200 lines)
  - Upload document tests (mocked)
  - Search tests (mocked)
  - Metrics tests
  - Error handling tests
  - Cost calculation tests

- `tests/integration/test_vector_store_integration.py` (new file, ~150 lines)
  - End-to-end upload → search workflow
  - Async processing validation
  - File limits testing (10K max)

**Success Criteria**:
- ✅ Documents successfully uploaded to OpenAI Vector Store
- ✅ Async processing handled correctly (polling until "ready")
- ✅ Search returns relevant results (hybrid semantic + keyword)
- ✅ Metrics reporting accurate (file counts, status)
- ✅ Cost tracking implemented ($0.10/GB/day)
- ✅ All tests passing (100%)
- ✅ MyPy strict passing (0 errors)

**Duration**: 6-8 hours

---

### Phase 3.2: Vector Store Configuration & Observability

**Configuration Additions** (src/config.py):

```python
# src/config.py additions

class Config(BaseSettings):
    # ... existing fields ...

    # Vector Store Configuration
    vector_store_id: Optional[str] = Field(
        default=None,
        env="VECTOR_STORE_ID",
        description="OpenAI Vector Store ID (or None to create new)"
    )

    vector_store_max_files: int = Field(
        default=10000,
        env="VECTOR_STORE_MAX_FILES",
        description="Maximum files per vector store (OpenAI limit: 10K)"
    )

    vector_store_cost_alert_threshold_usd: float = Field(
        default=50.0,
        env="VECTOR_STORE_COST_ALERT_THRESHOLD_USD",
        description="Alert when monthly storage cost exceeds this (USD)"
    )

    @model_validator(mode="after")
    def validate_vector_store_limits(self) -> "Config":
        """Validate vector store configuration."""
        if self.vector_store_max_files > 10000:
            raise ValueError("vector_store_max_files exceeds OpenAI limit (10K)")
        return self
```

**Monitoring Integration** (src/monitoring.py):

```python
# src/monitoring.py additions

from src.vector_store import VectorStoreManager

class MonitoringService:
    def __init__(self, vector_store_manager: VectorStoreManager):
        self.vs_manager = vector_store_manager

    def collect_vector_store_metrics(self) -> Dict[str, Any]:
        """Collect vector store metrics for monitoring."""
        metrics = self.vs_manager.get_metrics()
        cost_estimate = self.vs_manager.get_cost_estimate()

        return {
            "vector_store": {
                "total_files": metrics.total_files,
                "ready_files": metrics.ready_files,
                "failed_files": metrics.failed_files,
                "processing_files": metrics.processing_files,
                "status": metrics.status,
                "size_mb": metrics.size_estimate_mb,
                "daily_cost_usd": cost_estimate["daily_cost_usd"],
                "monthly_cost_usd": cost_estimate["monthly_cost_usd"],
                "alert": cost_estimate["monthly_cost_usd"] > get_config().vector_store_cost_alert_threshold_usd
            }
        }
```

**Admin CLI** (scripts/vector_store_admin.py):

```python
#!/usr/bin/env python3
"""Vector Store administration CLI."""

import click
from openai import OpenAI

from src.config import get_config
from src.vector_store import VectorStoreManager


@click.group()
def cli():
    """Vector Store administration commands."""
    pass


@cli.command()
def status():
    """Show vector store status and metrics."""
    config = get_config()
    client = OpenAI(api_key=config.api_key)
    manager = VectorStoreManager(client, vector_store_id=config.vector_store_id)

    metrics = manager.get_metrics()
    cost_estimate = manager.get_cost_estimate()

    click.echo(f"Vector Store ID: {manager.vector_store.id}")
    click.echo(f"Status: {metrics.status}")
    click.echo(f"Total Files: {metrics.total_files}")
    click.echo(f"Ready: {metrics.ready_files}")
    click.echo(f"Processing: {metrics.processing_files}")
    click.echo(f"Failed: {metrics.failed_files}")
    click.echo(f"Size: {metrics.size_estimate_mb:.2f} MB ({cost_estimate['size_gb']:.2f} GB)")
    click.echo(f"Daily Cost: ${cost_estimate['daily_cost_usd']:.4f}")
    click.echo(f"Monthly Cost: ${cost_estimate['monthly_cost_usd']:.2f}")


@cli.command()
@click.argument('query')
@click.option('--limit', default=10, help='Number of results')
def search(query, limit):
    """Search vector store."""
    config = get_config()
    client = OpenAI(api_key=config.api_key)
    manager = VectorStoreManager(client, vector_store_id=config.vector_store_id)

    results = manager.search(query, limit=limit)

    click.echo(f"Found {len(results)} results:")
    for i, result in enumerate(results, 1):
        click.echo(f"{i}. {result}")


@cli.command()
@click.confirmation_option(prompt='Are you sure you want to delete the vector store?')
def cleanup():
    """Delete vector store and all files."""
    config = get_config()
    client = OpenAI(api_key=config.api_key)
    manager = VectorStoreManager(client, vector_store_id=config.vector_store_id)

    manager.cleanup()
    click.echo(f"Deleted vector store: {manager.vector_store.id}")


if __name__ == "__main__":
    cli()
```

**Files Modified**:
- `src/config.py`: Add vector store config fields (~20 lines)
- `src/monitoring.py`: Add vector store metrics (~30 lines)
- `scripts/vector_store_admin.py`: New CLI tool (~80 lines)

**Duration**: 2-3 hours

---

### Phase 3.3: Vector Store Documentation

**ADR-030: Vector Store Integration Architecture**

Create `docs/adr/ADR-030-vector-store-integration.md`:

```markdown
# ADR-030: OpenAI Vector Store Integration for Semantic Search

**Status:** Accepted
**Date:** 2025-10-23
**Deciders:** Technical Leadership
**Related ADRs:** ADR-028 (LRU Cache), ADR-029 (Cache Module)

## Context

autoD requires semantic search capabilities to enable natural language
document retrieval across the entire corpus. Previous approach used local
embeddings with in-memory/DB caching. OpenAI released official Vector Store
API in March 2025 with enterprise features.

### Requirements

1. **Semantic Search**: Natural language queries (e.g., "invoices from ACME in 2024")
2. **Scale**: Support 10K+ documents with <500ms P95 latency
3. **Cost Efficiency**: Minimize API calls, track storage costs
4. **Reliability**: Async processing, automatic retries, error handling

### OpenAI Vector Store API Features (2025)

- **Hybrid Search**: Combines semantic (embeddings) + keyword search
- **Built-in Reranking**: Automatic relevance scoring
- **Async Processing**: Upload PDFs, automatic chunking/embedding
- **Metadata Filtering**: Filter by doc_type, issuer, date_range
- **Limits**: 10,000 files per vector store
- **Cost**: $0.10/GB/day storage after 1 GB free tier

## Decision

**Use OpenAI Vector Store API as primary search infrastructure** while maintaining
local embedding cache for offline/backup scenarios.

### Architecture

```
┌─────────────────────────────────────────────┐
│  DocumentProcessor                           │
│  - Upload to Files API                       │
│  - Add to Vector Store (async)               │
│  - Store vector_store_file_id in DB          │
└─────────────────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────┐
│  VectorStoreManager                          │
│  - upload_document()                         │
│  - search() (Responses API + file_search)    │
│  - get_metrics()                             │
│  - get_cost_estimate()                       │
└─────────────────────────────────────────────┘
                   ↓
┌─────────────────────────────────────────────┐
│  OpenAI Vector Store API                     │
│  - Automatic chunking (OpenAI)               │
│  - Automatic embedding (text-embedding-3)    │
│  - Hybrid search (semantic + keyword)        │
│  - Reranking (built-in)                      │
└─────────────────────────────────────────────┘
```

### Key Design Decisions

1. **Async Upload with Polling**:
   - Use `create_and_poll` helper for reliable async uploads
   - Wait for "completed" status before marking upload successful
   - Store `vector_store_file_id` in Document model for tracking

2. **Responses API Integration**:
   - Use `file_search` tool type (not direct embedding search)
   - Set `reasoning_effort="minimal"` for search queries
   - Set `verbosity="low"` for concise search results

3. **Cost Management**:
   - Track storage costs ($0.10/GB/day)
   - Alert when monthly cost exceeds threshold ($50 default)
   - Implement file limits (10K max per vector store)

4. **Fallback Strategy**:
   - Keep local embedding cache for offline scenarios
   - Use `SemanticSearchEngine` as fallback if Vector Store API unavailable
   - Dual-search capability: Vector Store (primary) + local (fallback)

## Consequences

### Positive

**Performance**:
- Hybrid search (semantic + keyword) better than pure semantic
- Built-in reranking improves relevance
- Offload embedding compute to OpenAI (no local GPU needed)
- Automatic chunking handles large PDFs efficiently

**Reliability**:
- OpenAI manages vector store infrastructure
- Automatic retries for transient failures
- Async processing prevents timeout issues

**Cost**:
- $0.10/GB/day cheaper than self-hosted vector DB
- Free tier (1 GB) covers small deployments
- No infrastructure maintenance costs

### Negative

**Vendor Lock-in**:
- Depends on OpenAI Vector Store API availability
- Migration to alternative vendor requires code changes
- Mitigation: Keep local embedding cache as fallback

**Cost Scaling**:
- $0.10/GB/day = $3/GB/month = $36/GB/year
- 10 GB storage = $360/year
- Mitigation: Implement cost alerts, file limits

**API Limits**:
- 10,000 files per vector store (OpenAI limit)
- Need multi-store strategy for >10K documents
- Mitigation: Implement store sharding if needed

### Neutral

**Complexity**:
- Adds Vector Store Manager class (~400 lines)
- Requires async processing logic (polling)
- But: Simplifies embedding management (no local compute)

## Implementation

### Phase 1: Core Integration (6-8 hours)
- Implement `VectorStoreManager` class
- Add upload stage to processor pipeline
- Integrate with Responses API `file_search` tool

### Phase 2: Observability (2-3 hours)
- Add vector store metrics to monitoring
- Implement cost tracking
- Create admin CLI for management

### Phase 3: Documentation (2-3 hours)
- Create ADR-030 (this document)
- Update docs/VECTOR_STORE_GUIDE.md
- Update README.md with search features

### Total Scope: 10-14 hours

## Alternatives Considered

### Alternative 1: Self-Hosted Vector DB (Pinecone, Weaviate, Qdrant)

**Pros**:
- No vendor lock-in
- More control over infrastructure
- Potentially lower long-term costs at scale

**Cons**:
- Infrastructure management overhead
- Need to manage embeddings separately
- More complex deployment
- Higher initial setup cost

**Rejected**: OpenAI Vector Store simpler for MVP, can migrate later if needed

### Alternative 2: Local Embeddings Only (No Vector Store)

**Pros**:
- Zero API costs for storage
- Full offline capability
- Complete data control

**Cons**:
- No hybrid search (keyword + semantic)
- No automatic reranking
- Requires local compute for embeddings
- Slower at scale (no distributed search)

**Rejected**: Hybrid search is significant quality improvement

### Alternative 3: OpenAI Assistants API (File Search Tool)

**Pros**:
- Higher-level abstraction (easier to use)
- Integrated with conversations

**Cons**:
- Designed for chat, not batch document retrieval
- Less control over search parameters
- Higher cost (Assistants API overhead)

**Rejected**: Responses API with `file_search` tool provides more control

## References

**OpenAI Documentation**:
- Vector Store API: https://platform.openai.com/docs/api-reference/vector-stores
- File Search Tool: https://platform.openai.com/docs/guides/file-search
- Responses API: https://platform.openai.com/docs/api-reference/responses

**Internal Documentation**:
- docs/VECTOR_STORE_GUIDE.md (new)
- docs/ARCHITECTURE.md (updated)
- src/vector_store.py (implementation)

**Cost References**:
- Vector Store Pricing: $0.10/GB/day
- Embeddings Pricing: $0.00002/1K tokens (text-embedding-3-small)
- Responses API Pricing: $0.25/1M input (gpt-5-mini)

---

**Last Updated**: 2025-10-23
**Next Review**: After Week 4 completion
**Owner**: Technical Lead
```

**Vector Store Guide** (`docs/VECTOR_STORE_GUIDE.md`):

Create comprehensive guide (~300 lines) covering:
- Setup and configuration
- Upload workflows
- Search best practices
- Cost management
- Troubleshooting
- Admin CLI usage

**README.md Update**:

Add Vector Store features to "What It Does" section and Architecture description.

**Duration**: 2-3 hours

---

## Phase 4: TD1 Error Handling Consolidation (8-10 hours)

### Phase 4.1: Complete CompensatingTransaction Pattern

**Current State** (src/transactions.py):
- RollbackHandler dataclass defined (lines 37-73)
- ResourceType enum defined (lines 28-35)
- Basic structure in place (~100 lines)
- Needs: Context manager, rollback execution, integration with pipeline

**Target Implementation**:

```python
# src/transactions.py complete implementation

from contextlib import contextmanager
import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from typing import Optional, Callable, Dict, Any, List, Generator, Type
from types import TracebackType
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ResourceType(Enum):
    """Types of external resources that can be cleaned up."""
    FILES_API = "files_api"
    VECTOR_STORE = "vector_store"
    DATABASE = "database"
    CUSTOM = "custom"


@dataclass
class RollbackHandler:
    """
    Handler for rolling back a specific resource operation.

    Example:
        def cleanup_file():
            client.files.delete("file-abc123")

        handler = RollbackHandler(
            handler_fn=cleanup_file,
            resource_type=ResourceType.FILES_API,
            resource_id="file-abc123",
            description="Delete uploaded PDF from Files API",
            critical=True
        )
    """
    handler_fn: Callable[[], None]
    resource_type: ResourceType
    resource_id: str
    description: str
    critical: bool = True
    executed: bool = False
    success: Optional[bool] = None
    error: Optional[Exception] = None

    def execute(self) -> bool:
        """Execute the rollback handler."""
        self.executed = True
        try:
            logger.info(
                f"Executing rollback: {self.description}",
                extra={
                    "resource_type": self.resource_type.value,
                    "resource_id": self.resource_id,
                    "critical": self.critical,
                }
            )
            self.handler_fn()
            self.success = True
            logger.info(f"Rollback succeeded: {self.description}")
            return True
        except Exception as e:
            self.success = False
            self.error = e
            logger.error(
                f"Rollback failed: {self.description}",
                extra={
                    "error": str(e),
                    "resource_type": self.resource_type.value,
                    "resource_id": self.resource_id
                },
                exc_info=True
            )
            if self.critical:
                raise TransactionRollbackError(
                    f"Critical rollback failed: {self.description}"
                ) from e
            return False


class TransactionRollbackError(Exception):
    """Raised when critical rollback handlers fail."""
    pass


class CompensatingTransactionContext:
    """
    Context manager for multi-resource transactions with automatic rollback.

    Features:
    - Register cleanup handlers for each resource operation
    - Automatic rollback on exception (LIFO order)
    - Critical vs non-critical handler distinction
    - Comprehensive audit trail

    Example:
        with CompensatingTransactionContext("upload_document") as txn:
            # Stage 1: Upload to Files API
            file = client.files.create(...)
            txn.register_rollback(
                handler_fn=lambda: client.files.delete(file.id),
                resource_type=ResourceType.FILES_API,
                resource_id=file.id,
                description="Delete Files API upload",
                critical=True
            )

            # Stage 2: Save to database
            session.add(document)
            session.commit()
            txn.register_rollback(
                handler_fn=lambda: session.delete(document),
                resource_type=ResourceType.DATABASE,
                resource_id=str(document.id),
                description="Delete database record",
                critical=True
            )

            # All successful
            txn.commit()
    """

    def __init__(self, description: str):
        self.description = description
        self.handlers: List[RollbackHandler] = []
        self.committed = False
        self.start_time = datetime.now(timezone.utc)

        logger.info(f"Transaction started: {description}")

    def register_rollback(
        self,
        handler_fn: Callable[[], None],
        resource_type: ResourceType,
        resource_id: str,
        description: str,
        critical: bool = True
    ) -> None:
        """Register a cleanup handler for a resource operation."""
        handler = RollbackHandler(
            handler_fn=handler_fn,
            resource_type=resource_type,
            resource_id=resource_id,
            description=description,
            critical=critical
        )
        self.handlers.append(handler)
        logger.debug(
            f"Registered rollback handler: {description}",
            extra={
                "resource_type": resource_type.value,
                "resource_id": resource_id,
                "critical": critical,
                "total_handlers": len(self.handlers)
            }
        )

    def commit(self) -> None:
        """Mark transaction as successful (skip rollback on exit)."""
        self.committed = True
        duration = (datetime.now(timezone.utc) - self.start_time).total_seconds()
        logger.info(
            f"Transaction committed: {self.description}",
            extra={
                "duration_seconds": duration,
                "handlers_registered": len(self.handlers)
            }
        )

    def rollback(self) -> None:
        """Execute all rollback handlers in reverse order (LIFO)."""
        if self.committed:
            logger.info(f"Transaction already committed, skipping rollback: {self.description}")
            return

        logger.warning(
            f"Rolling back transaction: {self.description}",
            extra={"handlers_count": len(self.handlers)}
        )

        # Execute in reverse order (LIFO)
        failed_critical = []
        failed_non_critical = []

        for handler in reversed(self.handlers):
            success = handler.execute()
            if not success:
                if handler.critical:
                    failed_critical.append(handler)
                else:
                    failed_non_critical.append(handler)

        # Log summary
        logger.info(
            f"Rollback complete: {self.description}",
            extra={
                "total_handlers": len(self.handlers),
                "critical_failures": len(failed_critical),
                "non_critical_failures": len(failed_non_critical)
            }
        )

        # Raise if critical handlers failed
        if failed_critical:
            raise TransactionRollbackError(
                f"Critical rollback failures: {len(failed_critical)} of {len(self.handlers)} handlers"
            )

    def __enter__(self) -> "CompensatingTransactionContext":
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType]
    ) -> bool:
        """Context manager exit - rollback on exception."""
        if exc_type is not None:
            # Exception occurred, rollback
            logger.error(
                f"Transaction failed: {self.description}",
                extra={
                    "exception_type": exc_type.__name__,
                    "exception": str(exc_val)
                },
                exc_info=True
            )
            try:
                self.rollback()
            except TransactionRollbackError as rollback_error:
                # Re-raise rollback error (more critical than original)
                logger.critical(
                    f"Rollback failed for transaction: {self.description}",
                    extra={"original_error": str(exc_val)},
                    exc_info=True
                )
                raise rollback_error from exc_val

        return False  # Don't suppress original exception


# Pre-built handler factories

def files_api_rollback_handler(
    client,
    file_id: str
) -> RollbackHandler:
    """Pre-built handler for Files API cleanup."""
    def cleanup():
        client.files.delete(file_id)

    return RollbackHandler(
        handler_fn=cleanup,
        resource_type=ResourceType.FILES_API,
        resource_id=file_id,
        description=f"Delete Files API file {file_id}",
        critical=True
    )


def vector_store_rollback_handler(
    client,
    vector_store_id: str,
    file_id: str
) -> RollbackHandler:
    """Pre-built handler for Vector Store cleanup."""
    def cleanup():
        client.beta.vector_stores.files.delete(
            vector_store_id=vector_store_id,
            file_id=file_id
        )

    return RollbackHandler(
        handler_fn=cleanup,
        resource_type=ResourceType.VECTOR_STORE,
        resource_id=file_id,
        description=f"Delete vector store file {file_id}",
        critical=False  # Non-critical (can be retried)
    )


def database_rollback_handler(
    session: Session,
    model_instance: Any,
    action: str = "delete"
) -> RollbackHandler:
    """Pre-built handler for database cleanup."""
    def cleanup():
        if action == "delete":
            session.delete(model_instance)
            session.commit()
        elif action == "rollback":
            session.rollback()

    return RollbackHandler(
        handler_fn=cleanup,
        resource_type=ResourceType.DATABASE,
        resource_id=str(getattr(model_instance, 'id', 'unknown')),
        description=f"Database {action}: {model_instance.__class__.__name__}",
        critical=True
    )
```

**Integration with Processor Pipeline**:

```python
# src/processor.py integration

from src.transactions import (
    CompensatingTransactionContext,
    files_api_rollback_handler,
    vector_store_rollback_handler,
    database_rollback_handler
)

def process_document(self, document: Document) -> ProcessingResult:
    """Process document with compensating transactions."""

    with CompensatingTransactionContext("process_document") as txn:
        try:
            # Stage 1: Upload to Files API
            file = self._upload_to_files_api(document)
            txn.register_rollback(
                handler_fn=lambda: self.client.files.delete(file.id),
                resource_type=ResourceType.FILES_API,
                resource_id=file.id,
                description=f"Delete Files API upload {file.id}",
                critical=True
            )

            # Stage 2: Call Responses API (idempotent, no rollback needed)
            response = self._call_responses_api(file.id, document)

            # Stage 3: Save to database
            self._save_to_database(document, response)
            txn.register_rollback(
                handler_fn=lambda: self._delete_from_database(document.id),
                resource_type=ResourceType.DATABASE,
                resource_id=str(document.id),
                description=f"Delete database record {document.id}",
                critical=True
            )

            # Stage 4: Upload to Vector Store
            vs_file = self._upload_to_vector_store(document, file.id)
            txn.register_rollback(
                handler_fn=lambda: self._delete_from_vector_store(vs_file.id),
                resource_type=ResourceType.VECTOR_STORE,
                resource_id=vs_file.id,
                description=f"Delete vector store file {vs_file.id}",
                critical=False  # Non-critical (can be retried)
            )

            # All stages successful
            txn.commit()
            return ProcessingResult(success=True, document=document)

        except Exception as e:
            logger.error(f"Processing failed: {e}")
            # Automatic rollback via context manager
            raise
```

**Files Modified**:
- `src/transactions.py`: Complete implementation (~300 lines total)
- `src/processor.py`: Integrate compensating transactions (~50 lines modified)
- `src/stages/*.py`: Add transaction support to each stage (~10 lines each)
- `src/vector_store.py`: Add transaction support (~20 lines)

**Tests Required**:
- `tests/unit/test_transactions.py`: Update for full implementation
  - Context manager tests (enter/exit)
  - Rollback execution (LIFO order)
  - Critical vs non-critical handlers
  - Nested transactions
  - Pre-built handler factories

- `tests/integration/test_compensating_transactions.py`: New file
  - End-to-end pipeline with rollback
  - Multi-stage failure scenarios
  - Rollback audit trail verification
  - Performance impact (<5ms overhead target)

**Success Criteria**:
- ✅ All external API calls protected by compensating transactions
- ✅ Rollback handlers execute in correct order (LIFO)
- ✅ Critical failures propagate correctly
- ✅ Non-critical failures logged but don't block
- ✅ Comprehensive audit trail in logs
- ✅ Performance overhead <5ms per transaction
- ✅ All tests passing (100%)
- ✅ MyPy strict passing (0 errors)

**Duration**: 5-6 hours

---

### Phase 4.2: Error Handling Documentation

**ADR-031: Compensating Transaction Pattern** (`docs/adr/ADR-031-compensating-transaction-pattern.md`):

Create comprehensive ADR documenting:
- Context and motivation
- Pattern description
- Implementation details
- Usage examples
- Alternatives considered
- Trade-offs

**Error Handling Guide** (`docs/ERROR_HANDLING.md`):

Create practical guide covering:
- CompensatingTransaction pattern usage
- Pre-built handler factories
- Integration with retry logic
- Audit trail analysis
- Troubleshooting common issues
- Best practices

**RUNBOOK.md Update**:

Add error recovery procedures:
- Manual rollback procedures
- Recovery from partial failures
- Audit log analysis
- Incident response

**Duration**: 2-3 hours

---

### Phase 4.3: Error Handling Integration Testing

**Test Scenarios**:

1. **Partial Upload Failure**:
   - Files API succeeds
   - Responses API fails
   - Verify: Files API upload cleaned up

2. **Database Failure**:
   - Files API succeeds
   - Responses API succeeds
   - Database commit fails
   - Verify: Files API upload cleaned up

3. **Vector Store Failure** (non-critical):
   - All stages succeed except Vector Store
   - Verify: Document marked as completed, Vector Store marked for retry

4. **Nested Transaction Failure**:
   - Outer transaction fails
   - Inner transaction rollback succeeds
   - Verify: All resources cleaned up

5. **Performance Impact**:
   - Measure transaction overhead
   - Verify: <5ms per operation

**Test Execution**:
```bash
pytest tests/integration/test_compensating_transactions.py -v --tb=short

# Expected: All failure scenarios handled correctly
```

**Duration**: 1-2 hours

---

## Phase 5: Documentation & Integration (3-4 hours)

### Phase 5.1: Week 3 Session Documentation

**Create**: `docs/sessions/2025-10-23-week3-complete.md` (~600-800 lines)

**Structure**:
```markdown
# Session: Week 3 Complete (WS1 + TD1 + Cache Integration)

## Executive Summary
[High-level achievements, metrics, outcomes]

## Work Completed

### Phase 1: Quick Wins
[test_search.py fix, worktree cleanup]

### Phase 2: Cache Integration
[EmbeddingGenerator refactor, integration testing]

### Phase 3: Vector Store Implementation (WS1)
[OpenAI Vector Store API integration, metrics, documentation]

### Phase 4: Error Handling (TD1)
[CompensatingTransaction pattern, integration, testing]

### Phase 5: Documentation
[Session notes, ADRs, guides]

## Git Operations
[Branches, commits, merge strategy]

## Quality Validation
[MyPy results, pytest results, coverage]

## Performance Metrics
[Cache latency, Vector Store upload time, transaction overhead]

## Architectural Decisions
[ADR-030 Vector Store, ADR-031 CompensatingTransaction]

## Technical Debt
[Known issues, deferred work]

## Files Changed
[Comprehensive list with line counts]

## Next Session Preparation
[Week 4 priorities: TD4 Test Coverage, WS3 Production Hardening]
```

**Updates**:
- `CHANGELOG.md`: Add Week 3 entry
- `docs/overview.md`: Update current phase, progress metrics
- `docs/tasks.yaml`: Mark WS1 and TD1 as completed, update priorities
- `README.md`: Update features (Vector Store, error handling)

**Duration**: 2 hours

---

### Phase 5.2: Quality Gates & Final Validation

**Quality Gate Checklist**:

1. **MyPy Strict**: `mypy src/ tests/ --strict`
   - Expected: 0 errors
   - Target: 100% type coverage

2. **Pytest**: `pytest -v`
   - Expected: 100% pass rate
   - Target: All new tests passing

3. **Coverage**: `pytest --cov=src`
   - Expected: ≥60% (maintain from Wave 2)
   - Stretch: 70%+ (defer to TD4 if not reached)

4. **Pre-commit**: `pre-commit run --all-files`
   - Expected: All hooks passing

5. **Integration Test**: End-to-end pipeline
   - Upload document → Extract → Save → Vector Store → Search
   - With compensating transactions
   - Verify all stages complete successfully

**Test Execution**:
```bash
# Run all quality gates
mypy src/ tests/ --strict
pytest -v --cov=src
pre-commit run --all-files

# Run integration test
pytest tests/integration/test_end_to_end.py -v
```

**Success Criteria**:
- ✅ MyPy: 0 errors
- ✅ Pytest: 100% pass rate
- ✅ Coverage: ≥60%
- ✅ Pre-commit: All passing
- ✅ Integration: Full pipeline working

**Duration**: 1-2 hours

---

## API Best Practices (2025 Updates from Web Search)

### OpenAI Responses API ✅

**Already Implemented**:
- ✅ Using Responses API (`/v1/responses`) not Chat Completions
- ✅ `previous_response_id` for multi-turn conversations
- ✅ Structured outputs with JSON Schema + `strict: true`

**New Best Practices (2025)**:
- 🆕 `reasoning_effort`: "minimal", "low", "medium", "high"
- 🆕 `verbosity`: "low", "medium", "high"
- 🆕 Context-Free Grammar (CFG) support for strict output formatting

**Usage**:
```python
response = client.responses.create(
    model="gpt-5-mini",
    input=[{"role": "user", "content": query}],
    reasoning_effort="minimal",  # For search/extraction tasks
    verbosity="low",  # Concise outputs
    text={
        "format": {
            "type": "json_schema",
            "json_schema": {...},
            "strict": True
        }
    }
)
```

---

### Embeddings API ✅

**Already Implemented**:
- ✅ `text-embedding-3-small` (1536 dimensions)
- ✅ SHA-256 cache keys
- ✅ SQLite-based caching

**New Features (2025)**:
- 🆕 Adjustable dimensions (256-1536) for cost/quality trade-off
- 🆕 Improved multilingual support (100+ languages)
- 🆕 Better context understanding

**Pricing**:
- $0.00002/1K tokens (text-embedding-3-small)
- $0.0001/1K tokens (text-embedding-3-large)

---

### Vector Store API 🆕

**March 2025 Release**:
- 🆕 Official Vector Store API (not beta)
- 🆕 Hybrid search (semantic + keyword, automatic)
- 🆕 Built-in reranking
- 🆕 Metadata filtering
- 🆕 10,000 files per vector store limit
- 🆕 `create_and_poll` async helpers

**Pricing**:
- $0.10/GB/day storage (after 1 GB free)
- Embedding costs: $0.00002/1K tokens

**Usage**:
```python
# Upload (async with polling)
vs_file = client.beta.vector_stores.files.create_and_poll(
    vector_store_id=vector_store_id,
    file_id=file_id
)

# Search via Responses API
response = client.responses.create(
    model="gpt-5-mini",
    input=[{"role": "user", "content": query}],
    tools=[{
        "type": "file_search",
        "file_search": {
            "vector_stores": [vector_store_id],
            "max_num_results": 10
        }
    }],
    reasoning_effort="minimal"
)
```

---

### GPT-5 Model Updates 🆕

**Available Models** (2025):
- `gpt-5-mini` ✅ (default, most cost-effective)
- `gpt-5-nano` 🆕 (fastest, cheapest)
- `gpt-5` (best for complex reasoning)
- `gpt-5-pro` (highest quality)
- `gpt-4.1` (smartest non-reasoning model)

**Pricing**:
- gpt-5-nano: $0.05/1M input, $0.40/1M output
- gpt-5-mini: $0.25/1M input, $2/1M output ✅
- gpt-5: $1.25/1M input, $10/1M output
- gpt-5-pro: Higher pricing for premium quality

---

## Success Metrics (Week 3)

### Functional ✅
- ✅ test_search.py: 51/51 tests passing (Phase 1.1)
- 🔄 Cache Integration: EmbeddingGenerator refactored (Phase 2)
- ⏳ Vector Store: Full OpenAI integration (Phase 3)
- ⏳ Error Handling: CompensatingTransaction complete (Phase 4)

### Technical Quality
- ✅ MyPy strict: 0 errors (maintain from Wave 2)
- ⏳ Test coverage: ≥60% (target: 70%+)
- ⏳ All tests passing: 100% pass rate
- ⏳ Pre-commit hooks: All passing

### Performance
- ⏳ Cache latency: <0.1ms (maintain from Wave 2)
- ⏳ Cache hit rate: 70%+ (maintain from Wave 2)
- ⏳ Vector store upload: <30s per document
- ⏳ Transaction overhead: <5ms per operation

### Cost Efficiency
- ⏳ Vector Store: Cost tracking implemented ($0.10/GB/day)
- ⏳ Cache: 70%+ hit rate reduces API calls
- ⏳ GPT-5-mini: Most cost-effective model

### Documentation
- ⏳ 2 new ADRs (ADR-030 Vector Store, ADR-031 Error Handling)
- ⏳ Week 3 session documentation (~600-800 lines)
- ⏳ CHANGELOG.md updated
- ⏳ Vector Store guide created
- ⏳ Error handling guide created

---

## Timeline Estimate

| Phase | Duration | Status |
|-------|----------|--------|
| Phase 1: Quick Wins | 3-4 hours | ✅ COMPLETE (2/2) |
| Phase 2: Cache Integration | 6-8 hours | 🔄 IN PROGRESS (0/2) |
| Phase 3: Vector Store | 10-14 hours | ⏳ PENDING (0/3) |
| Phase 4: Error Handling | 8-10 hours | ⏳ PENDING (0/3) |
| Phase 5: Documentation | 3-4 hours | ⏳ PENDING (0/2) |
| **Total** | **30-40 hours** | **~4-5 days** |

**Progress**: Phase 1 complete (Quick Wins), Phase 2 started (Cache Integration)

---

## Open Questions

1. **Vector Store**: One global store or per-user/per-property stores?
   - Recommendation: Start with single global store, shard if >10K files

2. **Cache Integration**: Deprecate `src/embedding_cache.py` after refactor?
   - Recommendation: Keep as wrapper for backward compatibility

3. **Error Handling**: Add distributed tracing (OpenTelemetry)?
   - Recommendation: Defer to WS3 (Production Hardening)

4. **Test Coverage**: Target 70%+ in Week 3 or defer to TD4?
   - Recommendation: Maintain 60%+, expand to 70%+ in TD4 (Week 4)

---

## Next Steps

**Immediate** (Phase 2 - Cache Integration):
1. Add CacheProtocol interface to src/cache.py
2. Refactor EmbeddingGenerator to use LRUCache
3. Run cache integration tests
4. Validate performance targets

**After Cache Integration** (Phase 3 - Vector Store):
1. Implement VectorStoreManager class
2. Integrate with processor pipeline
3. Add observability and cost tracking
4. Write Vector Store documentation (ADR-030, guide)

**After Vector Store** (Phase 4 - Error Handling):
1. Complete CompensatingTransaction pattern
2. Integrate with all pipeline stages
3. Write error handling documentation (ADR-031, guide)

**Final** (Phase 5 - Documentation & Validation):
1. Write Week 3 session documentation
2. Update CHANGELOG.md, overview.md, tasks.yaml
3. Run all quality gates
4. Validate end-to-end integration

---

**Created By**: Claude Code (Sonnet 4.5)
**Last Updated**: 2025-10-23 (Phase 1 complete)
**Next Review**: After each phase completion
**Owner**: Technical Lead
