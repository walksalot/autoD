"""
Database-backed embedding cache for persistent storage and retrieval.

Provides SQLAlchemy-based cache management for document embeddings with:
- Persistent storage in documents table
- Cache key-based lookup (SHA-256 hash)
- Automatic invalidation on text changes
- Integration with EmbeddingGenerator
- Cache statistics and size monitoring
- TTL-based expiration and cleanup

Architecture:
- Stores embeddings in Document.embedding_vector (JSON column)
- Cache key in Document.embedding_cache_key (indexed for fast lookup)
- Tracks model and timestamp for cache validation
- Integrates with in-memory cache for hot paths
- CacheStats dataclass for performance metrics
- CacheMonitor for size limits and cleanup

Usage:
    from openai import OpenAI
    from src.embedding_cache import EmbeddingCache, CacheStats, CacheMonitor
    from src.embeddings import EmbeddingGenerator
    from src.models import init_db

    session = init_db("sqlite:///app.db")
    client = OpenAI(api_key="sk-...")
    generator = EmbeddingGenerator(client)
    cache = EmbeddingCache(session, generator)

    # Get or generate embedding (uses cache if available)
    doc = session.query(Document).filter_by(id=1).first()
    embedding = cache.get_or_generate_embedding(doc)
    print(f"Embedding: {len(embedding)} dimensions")

    # Batch process with caching
    docs = session.query(Document).filter_by(status="completed").all()
    embeddings = cache.batch_get_or_generate_embeddings(docs)

    # Monitor cache size
    monitor = CacheMonitor(session)
    if monitor.is_over_limit():
        monitor.cleanup_oldest_entries()
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass

from sqlalchemy.orm import Session
from sqlalchemy import func

from src.models import Document
from src.embeddings import EmbeddingGenerator, EmbeddingResult
from src.config import get_config

logger = logging.getLogger(__name__)


@dataclass
class CacheStats:
    """
    Immutable cache performance statistics.

    Attributes:
        cache_size: Current number of entries in memory cache
        max_cache_size: Maximum memory cache capacity
        memory_cache_hits: Tier 1 (memory) cache hits
        db_cache_hits: Tier 2 (database) cache hits
        total_cache_hits: Combined cache hits (memory + DB)
        api_calls: Tier 3 (API) calls (cache misses)
        total_requests: Total embedding generation requests
        memory_hit_rate: Memory cache hit rate (0.0-1.0)
        overall_hit_rate: Overall cache hit rate (0.0-1.0)
        total_tokens: Total tokens processed by API
        cache_size_mb: Estimated database cache size in megabytes
        avg_response_time_ms: Average API response time in milliseconds
    """

    cache_size: int
    max_cache_size: int
    memory_cache_hits: int
    db_cache_hits: int
    total_cache_hits: int
    api_calls: int
    total_requests: int
    memory_hit_rate: float
    overall_hit_rate: float
    total_tokens: int
    cache_size_mb: Optional[float] = None
    avg_response_time_ms: Optional[float] = None

    @classmethod
    def from_dict(cls, stats: Dict[str, Any]) -> "CacheStats":
        """
        Create CacheStats from dictionary (e.g., from EmbeddingGenerator.get_cache_stats()).

        Args:
            stats: Dictionary with cache statistics

        Returns:
            CacheStats instance
        """
        return cls(
            cache_size=stats.get("cache_size", 0),
            max_cache_size=stats.get("max_cache_size", 0),
            memory_cache_hits=stats.get("memory_cache_hits", 0),
            db_cache_hits=stats.get("db_cache_hits", 0),
            total_cache_hits=stats.get("total_cache_hits", 0),
            api_calls=stats.get("api_calls", 0),
            total_requests=stats.get("total_requests", 0),
            memory_hit_rate=stats.get("memory_hit_rate", 0.0),
            overall_hit_rate=stats.get("overall_hit_rate", 0.0),
            total_tokens=stats.get("total_tokens", 0),
            cache_size_mb=stats.get("cache_size_mb"),
            avg_response_time_ms=stats.get("avg_response_time_ms"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "cache_size": self.cache_size,
            "max_cache_size": self.max_cache_size,
            "memory_cache_hits": self.memory_cache_hits,
            "db_cache_hits": self.db_cache_hits,
            "total_cache_hits": self.total_cache_hits,
            "api_calls": self.api_calls,
            "total_requests": self.total_requests,
            "memory_hit_rate": self.memory_hit_rate,
            "overall_hit_rate": self.overall_hit_rate,
            "total_tokens": self.total_tokens,
            "cache_size_mb": self.cache_size_mb,
            "avg_response_time_ms": self.avg_response_time_ms,
        }

    def is_healthy(self, min_hit_rate: float = 0.8) -> bool:
        """
        Check if cache performance meets target thresholds.

        Args:
            min_hit_rate: Minimum acceptable overall hit rate (default: 0.8)

        Returns:
            True if cache hit rate meets target, False otherwise
        """
        return self.overall_hit_rate >= min_hit_rate

    def __str__(self) -> str:
        """Human-readable cache statistics."""
        return (
            f"CacheStats("
            f"memory={self.memory_cache_hits}/{self.total_requests} "
            f"({self.memory_hit_rate:.1%}), "
            f"db={self.db_cache_hits}/{self.total_requests} "
            f"({self.db_cache_hits/max(self.total_requests,1):.1%}), "
            f"overall={self.overall_hit_rate:.1%}, "
            f"size={self.cache_size}/{self.max_cache_size}"
            f"{f', {self.cache_size_mb:.1f}MB' if self.cache_size_mb else ''}"
            f")"
        )


class CacheMonitor:
    """
    Monitor and manage database cache size limits.

    Features:
    - Calculate current cache size in MB
    - Detect when cache exceeds configured limits
    - Cleanup oldest/expired entries to enforce limits
    - TTL-based expiration for stale embeddings

    Cache Size Estimation:
    - Each embedding: 1536 floats * 8 bytes = 12,288 bytes (~12 KB)
    - Overhead (model, cache_key, timestamp): ~200 bytes
    - Total per document: ~12.5 KB
    - 1,000 documents ≈ 12.5 MB

    Example:
        monitor = CacheMonitor(session, max_size_mb=1024)

        if monitor.is_over_limit():
            print(f"Cache size: {monitor.get_cache_size_mb():.1f} MB")
            monitor.cleanup_oldest_entries(target_mb=900)
    """

    def __init__(self, session: Session, max_size_mb: Optional[int] = None):
        """
        Initialize cache monitor.

        Args:
            session: SQLAlchemy session for database queries
            max_size_mb: Maximum cache size in MB (default: from config)
        """
        self.session = session
        config = get_config()
        self.max_size_mb = max_size_mb or config.vector_cache_max_size_mb
        self.ttl_days = config.vector_cache_ttl_days

        logger.info(
            f"Initialized CacheMonitor: max_size={self.max_size_mb}MB, "
            f"ttl={self.ttl_days} days"
        )

    def get_cache_size_mb(self) -> float:
        """
        Calculate current database cache size in megabytes.

        Estimation formula:
        - Embedding vector: 1536 floats * 8 bytes = 12,288 bytes
        - Metadata overhead: ~200 bytes (model, cache_key, timestamp)
        - Total per document: ~12.5 KB

        Returns:
            Estimated cache size in MB
        """
        # Count documents with cached embeddings
        count = (
            self.session.query(func.count(Document.id))
            .filter(Document.embedding_vector.isnot(None))
            .scalar()
        )

        # Estimate size (12.5 KB per document)
        bytes_per_doc = 12_500  # 12.5 KB (embedding + overhead)
        total_bytes = count * bytes_per_doc
        size_mb = total_bytes / (1024 * 1024)

        logger.debug(
            f"Cache size: {count} documents, {size_mb:.2f} MB "
            f"(estimated {bytes_per_doc} bytes/doc)"
        )

        return size_mb

    def is_over_limit(self) -> bool:
        """
        Check if cache size exceeds configured limit.

        Returns:
            True if cache size exceeds max_size_mb, False otherwise
        """
        current_size = self.get_cache_size_mb()
        is_over = current_size > self.max_size_mb

        if is_over:
            logger.warning(
                f"Cache over limit: {current_size:.1f} MB > {self.max_size_mb} MB "
                f"({100 * current_size / self.max_size_mb:.1f}%)"
            )

        return is_over

    def get_expired_count(self) -> int:
        """
        Count embeddings that have exceeded TTL.

        Returns:
            Number of expired cache entries
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.ttl_days)

        count = (
            self.session.query(func.count(Document.id))
            .filter(
                Document.embedding_vector.isnot(None),
                Document.embedding_generated_at < cutoff,
            )
            .scalar()
        )

        return count

    def cleanup_expired_entries(self) -> int:
        """
        Remove embeddings that have exceeded TTL.

        Sets embedding_vector, embedding_cache_key, embedding_model, and
        embedding_generated_at to NULL for expired entries.

        Returns:
            Number of entries cleaned up
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.ttl_days)

        # Find expired documents
        expired = (
            self.session.query(Document)
            .filter(
                Document.embedding_vector.isnot(None),
                Document.embedding_generated_at < cutoff,
            )
            .all()
        )

        count = len(expired)

        if count == 0:
            logger.info("No expired cache entries to clean up")
            return 0

        logger.info(
            f"Cleaning up {count} expired cache entries (TTL: {self.ttl_days} days)"
        )

        # Clear embedding fields
        for doc in expired:
            doc.embedding_vector = None
            doc.embedding_cache_key = None
            doc.embedding_model = None
            doc.embedding_generated_at = None

        self.session.commit()

        logger.info(f"Successfully cleaned up {count} expired entries")
        return count

    def cleanup_oldest_entries(
        self, target_mb: Optional[float] = None, batch_size: int = 100
    ) -> int:
        """
        Remove oldest cache entries until target size is reached.

        Removes embeddings in batches, starting with oldest entries first
        (by embedding_generated_at timestamp).

        Args:
            target_mb: Target cache size in MB (default: 90% of max_size_mb)
            batch_size: Number of entries to remove per batch (default: 100)

        Returns:
            Total number of entries cleaned up
        """
        if target_mb is None:
            target_mb = self.max_size_mb * 0.9  # Default to 90% of max

        current_size = self.get_cache_size_mb()

        if current_size <= target_mb:
            logger.info(
                f"Cache size {current_size:.1f} MB already below target {target_mb:.1f} MB"
            )
            return 0

        logger.info(
            f"Cleaning up cache: {current_size:.1f} MB → {target_mb:.1f} MB target "
            f"(reducing {current_size - target_mb:.1f} MB)"
        )

        total_cleaned = 0

        while self.get_cache_size_mb() > target_mb:
            # Find oldest batch
            oldest = (
                self.session.query(Document)
                .filter(Document.embedding_vector.isnot(None))
                .order_by(Document.embedding_generated_at.asc())
                .limit(batch_size)
                .all()
            )

            if not oldest:
                break  # No more entries to clean

            # Clear embedding fields
            for doc in oldest:
                doc.embedding_vector = None
                doc.embedding_cache_key = None
                doc.embedding_model = None
                doc.embedding_generated_at = None

            self.session.commit()
            total_cleaned += len(oldest)

            logger.debug(f"Cleaned {len(oldest)} entries (total: {total_cleaned})")

        final_size = self.get_cache_size_mb()
        logger.info(
            f"Cache cleanup complete: removed {total_cleaned} entries, "
            f"size reduced to {final_size:.1f} MB"
        )

        return total_cleaned

    def get_cache_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive cache statistics including size metrics.

        Returns:
            Dictionary with cache performance and size metrics
        """
        total_docs = self.session.query(func.count(Document.id)).scalar()
        cached_docs = (
            self.session.query(func.count(Document.id))
            .filter(Document.embedding_vector.isnot(None))
            .scalar()
        )

        expired_count = self.get_expired_count()
        current_size_mb = self.get_cache_size_mb()

        return {
            "total_documents": total_docs,
            "cached_documents": cached_docs,
            "cache_coverage": cached_docs / max(total_docs, 1),
            "cache_size_mb": current_size_mb,
            "max_size_mb": self.max_size_mb,
            "size_utilization": current_size_mb / max(self.max_size_mb, 1),
            "is_over_limit": self.is_over_limit(),
            "expired_entries": expired_count,
            "ttl_days": self.ttl_days,
        }


def monitor_cache_health(session: Session) -> Dict[str, Any]:
    """
    Perform comprehensive cache health check.

    Checks:
    - Cache size vs limit
    - Expired entry count
    - Cache coverage (% of documents with embeddings)

    Args:
        session: SQLAlchemy session

    Returns:
        Health check results with recommendations
    """
    monitor = CacheMonitor(session)
    stats = monitor.get_cache_statistics()

    # Determine health status
    issues = []
    warnings = []

    if stats["is_over_limit"]:
        issues.append(
            f"Cache size ({stats['cache_size_mb']:.1f} MB) exceeds "
            f"limit ({stats['max_size_mb']} MB)"
        )

    if stats["expired_entries"] > 0:
        warnings.append(
            f"{stats['expired_entries']} expired entries "
            f"(TTL: {stats['ttl_days']} days)"
        )

    if stats["cache_coverage"] < 0.5:
        warnings.append(
            f"Low cache coverage: {stats['cache_coverage']:.1%} "
            f"({stats['cached_documents']}/{stats['total_documents']} documents)"
        )

    # Generate recommendations
    recommendations = []

    if stats["is_over_limit"]:
        recommendations.append("Run cleanup_oldest_entries() to reduce cache size")

    if stats["expired_entries"] > 10:
        recommendations.append(
            "Run cleanup_expired_entries() to remove stale embeddings"
        )

    return {
        "status": "unhealthy" if issues else ("warning" if warnings else "healthy"),
        "statistics": stats,
        "issues": issues,
        "warnings": warnings,
        "recommendations": recommendations,
    }


class EmbeddingCache:
    """Database-backed persistent cache for document embeddings.

    Features:
    - Stores embeddings in Document table (embedding_vector column)
    - Cache key-based lookup (SHA-256 hash in embedding_cache_key)
    - Automatic invalidation when text changes
    - Integrates with EmbeddingGenerator for in-memory cache
    - Batch operations for efficiency

    Cache Validation:
    - Cache key must match SHA-256(model + text)
    - Model must match generator.model
    - If text changes, cache is invalidated

    Performance:
    - Database lookups indexed on embedding_cache_key
    - In-memory cache used for hot embeddings
    - Batch operations minimize database round-trips
    """

    def __init__(self, session: Session, generator: EmbeddingGenerator):
        """Initialize embedding cache.

        Args:
            session: SQLAlchemy session for database operations
            generator: EmbeddingGenerator instance for cache misses
        """
        self.session = session
        self.generator = generator

        # Statistics
        self.db_cache_hits = 0
        self.db_cache_misses = 0

        logger.info("Initialized EmbeddingCache with database backend")

    def _is_cache_valid(self, document: Document, cache_key: str) -> bool:
        """Check if cached embedding is still valid.

        Cache is valid if:
        1. Cache key matches (text hasn't changed)
        2. Model matches (same embedding model)
        3. Embedding vector exists

        Args:
            document: Document with cached embedding
            cache_key: Computed cache key for current text

        Returns:
            True if cache is valid, False otherwise
        """
        if not document.embedding_cache_key:
            return False

        if document.embedding_cache_key != cache_key:
            logger.debug(
                f"Cache key mismatch for doc {document.id}: "
                f"stored={document.embedding_cache_key[:12]}..., "
                f"computed={cache_key[:12]}..."
            )
            return False

        if document.embedding_model != self.generator.model:
            logger.debug(
                f"Model mismatch for doc {document.id}: "
                f"stored={document.embedding_model}, "
                f"current={self.generator.model}"
            )
            return False

        if not document.embedding_vector:
            logger.debug(f"No embedding vector for doc {document.id}")
            return False

        return True

    def _load_from_db(
        self, document: Document, cache_key: str
    ) -> Optional[EmbeddingResult]:
        """Load embedding from database cache.

        Args:
            document: Document to load embedding for
            cache_key: Computed cache key for validation

        Returns:
            EmbeddingResult if cache is valid, None otherwise
        """
        if not self._is_cache_valid(document, cache_key):
            self.db_cache_misses += 1
            return None

        # Cache is valid - load embedding
        embedding = document.embedding_vector["embedding"]  # type: ignore

        result = EmbeddingResult(
            embedding=embedding,
            model=document.embedding_model,  # type: ignore
            dimensions=len(embedding),
            input_tokens=0,  # Not tracked for cached embeddings
            cached=True,
            cache_key=cache_key,
        )

        self.db_cache_hits += 1
        logger.debug(f"Database cache hit for doc {document.id}")
        return result

    def _save_to_db(self, document: Document, result: EmbeddingResult) -> None:
        """Save embedding to database cache.

        Args:
            document: Document to save embedding for
            result: EmbeddingResult to cache
        """
        document.embedding_cache_key = result.cache_key
        document.embedding_vector = {"embedding": result.embedding}
        document.embedding_model = result.model
        document.embedding_generated_at = datetime.now(timezone.utc)

        self.session.commit()
        logger.debug(f"Saved embedding to database for doc {document.id}")

    def get_or_generate_embedding(self, document: Document) -> List[float]:
        """Get embedding from cache or generate new one.

        Workflow:
        1. Compute cache key from document text
        2. Check database cache
        3. If miss, check in-memory cache (in generator)
        4. If miss, generate via OpenAI API
        5. Save to database cache
        6. Return embedding vector

        Args:
            document: Document to get embedding for

        Returns:
            List of floats representing the embedding vector

        Raises:
            ValueError: If document has no metadata
            Exception: If API call fails after retries
        """
        # Compute cache key
        text = self.generator.extract_text(document)
        cache_key = self.generator._compute_cache_key(text)

        # Try database cache first
        cached_result = self._load_from_db(document, cache_key)
        if cached_result:
            # Also populate in-memory cache for future calls
            self.generator._add_to_cache(cache_key, cached_result)
            return cached_result.embedding

        # Database miss - generate (uses in-memory cache internally)
        result = self.generator.generate_embedding(document)

        # Save to database for persistence
        self._save_to_db(document, result)

        return result.embedding

    def batch_get_or_generate_embeddings(
        self, documents: List[Document]
    ) -> List[List[float]]:
        """Get embeddings for multiple documents with caching.

        Workflow:
        1. Check database cache for all documents
        2. For cache misses, batch generate via API
        3. Save new embeddings to database
        4. Return all embeddings in input order

        Args:
            documents: List of Document instances

        Returns:
            List of embedding vectors (same order as input documents)

        Raises:
            ValueError: If any document has no metadata
            Exception: If API call fails after retries
        """
        if not documents:
            return []

        logger.info(f"Batch processing {len(documents)} documents")

        embeddings: List[Optional[List[float]]] = [None] * len(documents)
        docs_to_generate: List[Document] = []
        generate_indices: List[int] = []

        # Phase 1: Check database cache
        for idx, doc in enumerate(documents):
            text = self.generator.extract_text(doc)
            cache_key = self.generator._compute_cache_key(text)

            cached_result = self._load_from_db(doc, cache_key)
            if cached_result:
                embeddings[idx] = cached_result.embedding
                # Populate in-memory cache
                self.generator._add_to_cache(cache_key, cached_result)
            else:
                docs_to_generate.append(doc)
                generate_indices.append(idx)

        # Phase 2: Generate missing embeddings (uses in-memory cache too)
        if docs_to_generate:
            logger.info(
                f"Database cache misses: {len(docs_to_generate)}/{len(documents)} "
                f"({100 * len(docs_to_generate) / len(documents):.1f}%)"
            )

            # Batch generate (uses in-memory cache internally)
            results = self.generator.batch_generate_embeddings(docs_to_generate)

            # Save to database and populate results
            for result, doc, idx in zip(results, docs_to_generate, generate_indices):
                self._save_to_db(doc, result)
                embeddings[idx] = result.embedding

        # Verify all embeddings populated
        assert all(e is not None for e in embeddings), "Missing embeddings in results"

        logger.info(
            f"Batch complete: {len(embeddings)} embeddings, "
            f"{self.db_cache_hits} DB hits, {self.db_cache_misses} misses"
        )

        return embeddings  # type: ignore

    def invalidate_cache(self, document: Document) -> None:
        """Invalidate cached embedding for a document.

        Useful when document text changes (e.g., metadata update).

        Args:
            document: Document to invalidate cache for
        """
        if document.embedding_cache_key:
            logger.info(f"Invalidating cache for doc {document.id}")
            document.embedding_cache_key = None
            document.embedding_vector = None
            document.embedding_model = None
            document.embedding_generated_at = None
            self.session.commit()

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get combined cache statistics (DB + in-memory).

        Returns:
            Dictionary with cache metrics:
            - db_cache_hits: Database cache hits
            - db_cache_misses: Database cache misses
            - db_hit_rate: Database cache hit rate (0-1)
            - memory_cache_stats: In-memory cache stats from generator
        """
        total_db_requests = self.db_cache_hits + self.db_cache_misses
        db_hit_rate = (
            self.db_cache_hits / total_db_requests if total_db_requests > 0 else 0.0
        )

        return {
            "db_cache_hits": self.db_cache_hits,
            "db_cache_misses": self.db_cache_misses,
            "db_hit_rate": db_hit_rate,
            "memory_cache_stats": self.generator.get_cache_stats(),
        }
