"""
Embedding generation for document semantic search.

Provides text extraction from processed documents and embedding generation
via OpenAI Embeddings API with aggressive caching for cost efficiency.

Architecture:
- EmbeddingGenerator: Main class for generating and caching embeddings
- Text extraction from Document.metadata_json
- OpenAI text-embedding-3-small (1536 dimensions)
- In-memory + database cache for cost reduction
- Retry logic for transient API errors

Usage:
    from openai import OpenAI
    from src.embeddings import EmbeddingGenerator
    from src.models import Document, init_db

    client = OpenAI(api_key="sk-...")
    generator = EmbeddingGenerator(client)

    # Generate embedding for a document
    session = init_db("sqlite:///app.db")
    doc = session.query(Document).first()
    embedding = generator.generate_embedding(doc)
    print(f"Embedding: {len(embedding)} dimensions")

    # Batch generate embeddings
    docs = session.query(Document).filter_by(status="completed").all()
    embeddings = generator.batch_generate_embeddings(docs)
"""

import hashlib
import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timezone

from openai import OpenAI
from sqlalchemy.orm import Session

from src.retry_logic import retry
from src.models import Document

logger = logging.getLogger(__name__)

# OpenAI Embeddings API constants
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536
MAX_BATCH_SIZE = 100  # OpenAI API limit for batch embeddings


@dataclass
class EmbeddingResult:
    """Result of embedding generation operation.

    Attributes:
        embedding: List of floats representing the embedding vector
        model: OpenAI model used for generation
        dimensions: Number of dimensions in the embedding
        input_tokens: Number of tokens in the input text
        cached: Whether the embedding was retrieved from cache
        cache_key: SHA-256 hash of the input text (for cache lookup)
    """

    embedding: List[float]
    model: str
    dimensions: int
    input_tokens: int
    cached: bool = False
    cache_key: Optional[str] = None


class EmbeddingGenerator:
    """Generate and cache document embeddings using OpenAI API.

    Features:
    - Extracts searchable text from Document.metadata_json
    - Generates embeddings via text-embedding-3-small (1536d)
    - In-memory LRU cache for hot embeddings
    - SHA-256-based cache keys for deterministic lookup
    - Retry logic for transient API errors
    - Batch generation for efficiency

    Cache Strategy:
    - Cache key: SHA-256(model + text content)
    - In-memory: LRU cache (1000 embeddings max)
    - Database: embeddings table (future enhancement)
    - TTL: None (embeddings are immutable for given text)

    Cost Tracking:
    - text-embedding-3-small: $0.00002/1K tokens
    - Typical document: 500-2000 tokens
    - Cache hit rate target: 80%+
    """

    def __init__(
        self,
        client: OpenAI,
        session: Optional[Session] = None,
        model: str = EMBEDDING_MODEL,
        dimensions: int = EMBEDDING_DIMENSIONS,
        max_cache_size: int = 1000,
    ):
        """Initialize embedding generator.

        Args:
            client: OpenAI client instance
            session: Optional SQLAlchemy session for database cache
            model: Embedding model name (default: text-embedding-3-small)
            dimensions: Embedding vector dimensions (default: 1536)
            max_cache_size: Maximum number of embeddings in memory cache
        """
        self.client = client
        self.session = session
        self.model = model
        self.dimensions = dimensions
        self.max_cache_size = max_cache_size

        # In-memory LRU cache: {cache_key: EmbeddingResult}
        self._cache: Dict[str, EmbeddingResult] = {}
        self._cache_order: List[str] = []  # For LRU eviction

        # Statistics (3-tier cache)
        self.memory_cache_hits = 0
        self.db_cache_hits = 0
        self.api_calls = 0
        self.total_tokens = 0

        logger.info(
            f"Initialized EmbeddingGenerator: model={model}, "
            f"dimensions={dimensions}, cache_size={max_cache_size}, "
            f"db_cache={'enabled' if session else 'disabled'}"
        )

    def _compute_cache_key(self, text: str) -> str:
        """Compute SHA-256 cache key for deterministic lookup.

        Cache key includes model name to handle model upgrades.

        Args:
            text: Input text to embed

        Returns:
            64-character hex SHA-256 hash
        """
        cache_input = f"{self.model}:{text}"
        return hashlib.sha256(cache_input.encode("utf-8")).hexdigest()

    def _get_from_cache(self, cache_key: str) -> Optional[EmbeddingResult]:
        """Retrieve embedding from in-memory cache (LRU).

        Args:
            cache_key: SHA-256 hash of model + text

        Returns:
            Cached EmbeddingResult if found, None otherwise
        """
        if cache_key in self._cache:
            # Move to end of LRU order (mark as recently used)
            self._cache_order.remove(cache_key)
            self._cache_order.append(cache_key)

            result = self._cache[cache_key]
            result.cached = True
            self.memory_cache_hits += 1

            logger.debug(f"Memory cache hit for key {cache_key[:12]}...")
            return result

        return None

    def _add_to_cache(self, cache_key: str, result: EmbeddingResult) -> None:
        """Add embedding to in-memory cache with LRU eviction.

        Args:
            cache_key: SHA-256 hash of model + text
            result: EmbeddingResult to cache
        """
        # Evict oldest entry if cache is full
        if len(self._cache) >= self.max_cache_size:
            oldest_key = self._cache_order.pop(0)
            del self._cache[oldest_key]
            logger.debug(f"Evicted cache key {oldest_key[:12]}... (LRU)")

        self._cache[cache_key] = result
        self._cache_order.append(cache_key)
        logger.debug(f"Cached embedding for key {cache_key[:12]}...")

    def _get_from_db_cache(self, doc: Document) -> Optional[EmbeddingResult]:
        """Check database for cached embedding (Tier 2 cache).

        Cache hit conditions:
        - Document has embedding_vector field populated
        - embedding_cache_key matches current text hash
        - embedding_model matches current model
        - embedding not expired (TTL check)

        Args:
            doc: Document model instance

        Returns:
            Cached EmbeddingResult if valid cache exists, None otherwise
        """
        if not self.session or not doc.embedding_vector:
            return None

        # Verify cache key matches current text
        text = self.extract_text(doc)
        current_key = self._compute_cache_key(text)
        if doc.embedding_cache_key != current_key:
            logger.debug(f"DB cache miss: cache key mismatch for doc {doc.id}")
            return None  # Text changed, cache invalid

        # Verify model matches
        if doc.embedding_model != self.model:
            logger.debug(
                f"DB cache miss: model mismatch for doc {doc.id} "
                f"(cached={doc.embedding_model}, current={self.model})"
            )
            return None  # Different model = invalid cache

        # Check TTL expiration
        if doc.embedding_generated_at:
            from src.config import get_config

            config = get_config()
            age = datetime.now(timezone.utc) - doc.embedding_generated_at
            if age.days > config.vector_cache_ttl_days:
                logger.debug(
                    f"DB cache miss: TTL expired for doc {doc.id} "
                    f"(age={age.days} days > {config.vector_cache_ttl_days})"
                )
                return None  # Cache expired

        # Valid cache - return result
        logger.debug(f"DB cache hit for document {doc.id}")
        return EmbeddingResult(
            embedding=doc.embedding_vector,
            model=doc.embedding_model,
            dimensions=len(doc.embedding_vector),
            input_tokens=0,  # Not tracked in cache
            cached=True,
            cache_key=doc.embedding_cache_key,
        )

    def _save_to_db_cache(self, doc: Document, result: EmbeddingResult) -> None:
        """Persist embedding to database cache (Tier 2 cache).

        Args:
            doc: Document model instance
            result: EmbeddingResult to cache
        """
        if not self.session:
            return

        doc.embedding_vector = result.embedding
        doc.embedding_cache_key = result.cache_key
        doc.embedding_model = result.model
        doc.embedding_generated_at = datetime.now(timezone.utc)

        self.session.commit()
        logger.debug(f"Saved embedding to DB cache for document {doc.id}")

    def extract_text(self, document: Document) -> str:
        """Extract searchable text from document metadata.

        Combines multiple text fields for comprehensive semantic search:
        - filename (for file-based queries)
        - doc_type (for type filtering)
        - issuer (for entity search)
        - summary (for content search)

        Args:
            document: Document model instance with metadata_json

        Returns:
            Concatenated text for embedding generation

        Raises:
            ValueError: If document has no metadata or is not processed
        """
        if document.metadata_json is None:
            raise ValueError(
                f"Document {document.id} has no metadata. "
                "Must be processed before embedding."
            )

        metadata = document.metadata_json

        # Extract key text fields
        parts = [
            document.original_filename,
            metadata.get("doc_type", ""),
            metadata.get("issuer", ""),
            metadata.get("summary", ""),
        ]

        # Join with spaces, filter empty strings
        text = " ".join(part for part in parts if part)

        if not text.strip():
            raise ValueError(f"Document {document.id} metadata contains no text fields")

        return text

    @retry()
    def _call_embeddings_api(self, texts: List[str]) -> List[List[float]]:
        """Call OpenAI Embeddings API with retry logic.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors (one per input text)

        Raises:
            Exception: After 5 failed retry attempts
        """
        logger.info(f"Calling embeddings API: {len(texts)} texts")

        response = self.client.embeddings.create(
            model=self.model,
            input=texts,
            dimensions=self.dimensions,
        )

        # Extract embeddings in same order as input
        embeddings = [item.embedding for item in response.data]

        # Track token usage
        total_tokens = response.usage.total_tokens
        self.total_tokens += total_tokens

        logger.info(
            f"Embeddings API success: {len(embeddings)} embeddings, "
            f"{total_tokens} tokens"
        )

        return embeddings

    def generate_embedding(self, document: Document) -> EmbeddingResult:
        """Generate embedding for a single document with 3-tier caching.

        Workflow (3-tier cache):
        1. Extract text from document metadata
        2. Compute cache key (SHA-256)
        3. Check Tier 1: In-memory LRU cache
        4. Check Tier 2: Database cache (if session provided)
        5. Call Tier 3: OpenAI API (if both caches miss)
        6. Cache result in both tiers

        Args:
            document: Document model instance

        Returns:
            EmbeddingResult with embedding vector and metadata

        Raises:
            ValueError: If document has no metadata
            Exception: If API call fails after retries
        """
        # Extract text
        text = self.extract_text(document)
        cache_key = self._compute_cache_key(text)

        # Tier 1: Check in-memory cache
        cached_result = self._get_from_cache(cache_key)
        if cached_result:
            logger.debug(f"Tier 1 cache hit (memory) for document {document.id}")
            return cached_result

        # Tier 2: Check database cache
        db_cached = self._get_from_db_cache(document)
        if db_cached:
            self.db_cache_hits += 1
            # Promote to in-memory cache
            self._add_to_cache(cache_key, db_cached)
            logger.debug(f"Tier 2 cache hit (database) for document {document.id}")
            return db_cached

        # Tier 3: Call API (both caches missed)
        self.api_calls += 1
        logger.info(f"Cache miss - calling API for document {document.id}")

        embeddings = self._call_embeddings_api([text])

        # Create result
        result = EmbeddingResult(
            embedding=embeddings[0],
            model=self.model,
            dimensions=self.dimensions,
            input_tokens=len(text.split()),  # Approximate token count
            cached=False,
            cache_key=cache_key,
        )

        # Cache in both tiers
        self._add_to_cache(cache_key, result)
        self._save_to_db_cache(document, result)

        logger.info(f"Generated embedding for document {document.id}")
        return result

    def batch_generate_embeddings(
        self,
        documents: List[Document],
    ) -> List[EmbeddingResult]:
        """Generate embeddings for multiple documents efficiently.

        Features:
        - 3-tier caching (memory → DB → API)
        - Batch API calls (up to 100 texts per request)
        - Cache lookup before API calls
        - Preserves input order in results
        - Handles partial cache hits

        Args:
            documents: List of Document instances

        Returns:
            List of EmbeddingResult (same order as input documents)

        Raises:
            ValueError: If any document has no metadata
            Exception: If API call fails after retries
        """
        if not documents:
            return []

        logger.info(f"Batch generating embeddings for {len(documents)} documents")

        results: List[Optional[EmbeddingResult]] = [None] * len(documents)
        texts_to_fetch: List[str] = []
        fetch_indices: List[int] = []
        cache_keys: List[str] = []

        # Phase 1: Extract text and check 3-tier cache
        for idx, doc in enumerate(documents):
            text = self.extract_text(doc)
            cache_key = self._compute_cache_key(text)
            cache_keys.append(cache_key)

            # Tier 1: Check in-memory cache
            cached_result = self._get_from_cache(cache_key)
            if cached_result:
                results[idx] = cached_result
                continue

            # Tier 2: Check database cache
            db_cached = self._get_from_db_cache(doc)
            if db_cached:
                self.db_cache_hits += 1
                # Promote to in-memory cache
                self._add_to_cache(cache_key, db_cached)
                results[idx] = db_cached
                logger.debug(f"Batch: DB cache hit for document {doc.id}")
                continue

            # Both caches missed - need to fetch
            texts_to_fetch.append(text)
            fetch_indices.append(idx)

        # Phase 2: Fetch missing embeddings in batches
        if texts_to_fetch:
            self.api_calls += len(texts_to_fetch)
            logger.info(
                f"Cache misses: {len(texts_to_fetch)}/{len(documents)} "
                f"({100 * len(texts_to_fetch) / len(documents):.1f}%)"
            )

            # Split into batches of MAX_BATCH_SIZE
            for batch_start in range(0, len(texts_to_fetch), MAX_BATCH_SIZE):
                batch_end = min(batch_start + MAX_BATCH_SIZE, len(texts_to_fetch))
                batch_texts = texts_to_fetch[batch_start:batch_end]
                batch_indices = fetch_indices[batch_start:batch_end]

                # Call API for batch
                embeddings = self._call_embeddings_api(batch_texts)

                # Store results and cache in both tiers
                for i, (embedding, doc_idx) in enumerate(
                    zip(embeddings, batch_indices)
                ):
                    result = EmbeddingResult(
                        embedding=embedding,
                        model=self.model,
                        dimensions=self.dimensions,
                        input_tokens=len(batch_texts[i].split()),
                        cached=False,
                        cache_key=cache_keys[doc_idx],
                    )

                    results[doc_idx] = result
                    # Cache in memory
                    self._add_to_cache(cache_keys[doc_idx], result)
                    # Cache in database
                    self._save_to_db_cache(documents[doc_idx], result)

        # Verify all results populated
        assert all(r is not None for r in results), "Missing embeddings in results"

        # Calculate cache statistics
        total_cache_hits = self.memory_cache_hits + self.db_cache_hits
        cache_misses = len(texts_to_fetch)
        logger.info(
            f"Batch complete: {len(results)} embeddings, "
            f"{total_cache_hits} cache hits "
            f"(memory: {self.memory_cache_hits}, db: {self.db_cache_hits}), "
            f"{cache_misses} API calls"
        )

        return results  # type: ignore

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics.

        Returns:
            Dictionary with 3-tier cache metrics:
            - cache_size: Current number of in-memory cached embeddings
            - max_cache_size: Maximum in-memory cache capacity
            - memory_cache_hits: Tier 1 (memory) cache hits
            - db_cache_hits: Tier 2 (database) cache hits
            - total_cache_hits: Combined cache hits (memory + DB)
            - api_calls: Tier 3 (API) calls (cache misses)
            - total_requests: Total embedding requests
            - memory_hit_rate: Memory cache hit rate (0-1)
            - overall_hit_rate: Overall cache hit rate (0-1)
            - total_tokens: Total tokens processed by API
        """
        total_cache_hits = self.memory_cache_hits + self.db_cache_hits
        total_requests = total_cache_hits + self.api_calls

        memory_hit_rate = (
            self.memory_cache_hits / total_requests if total_requests > 0 else 0.0
        )
        overall_hit_rate = (
            total_cache_hits / total_requests if total_requests > 0 else 0.0
        )

        return {
            "cache_size": len(self._cache),
            "max_cache_size": self.max_cache_size,
            "memory_cache_hits": self.memory_cache_hits,
            "db_cache_hits": self.db_cache_hits,
            "total_cache_hits": total_cache_hits,
            "api_calls": self.api_calls,
            "total_requests": total_requests,
            "memory_hit_rate": memory_hit_rate,
            "overall_hit_rate": overall_hit_rate,
            "total_tokens": self.total_tokens,
        }

    def clear_cache(self) -> None:
        """Clear in-memory cache and reset statistics.

        Note: This only clears the in-memory cache (Tier 1).
        Database cache (Tier 2) remains intact.
        """
        self._cache.clear()
        self._cache_order.clear()
        self.memory_cache_hits = 0
        self.db_cache_hits = 0
        self.api_calls = 0
        self.total_tokens = 0
        logger.info("In-memory cache cleared, statistics reset")
