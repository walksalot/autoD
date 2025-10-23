"""
Generic cache module with LRU eviction and metrics.

Provides deterministic cache key generation, cache metrics tracking,
and LRU eviction policy. Supports generic types via CacheProtocol.

Wave 2 + Phase 2 Enhancement:
- Generic LRUCache[T] supporting any type
- CacheProtocol interface for type safety
- Backward compatible EmbeddingCache alias
"""

import hashlib
import logging
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional, TypeVar, Generic, Protocol

logger = logging.getLogger(__name__)

# Generic type variable for cache values
T = TypeVar("T")


class CacheProtocol(Protocol[T]):
    """
    Generic cache interface for type-safe cache operations.

    Supports any value type T through Python's Protocol (structural subtyping).

    Example:
        def use_cache(cache: CacheProtocol[List[float]]) -> None:
            embedding = cache.get("key123")
            if embedding:
                print(f"Found embedding: {len(embedding)} dimensions")
    """

    def get(self, key: str) -> Optional[T]:
        """Retrieve value from cache."""
        ...

    def set(self, key: str, value: T) -> None:
        """Store value in cache."""
        ...

    def clear(self) -> None:
        """Clear all cache entries."""
        ...

    def get_metrics(self) -> Dict[str, Any]:
        """Get cache performance metrics."""
        ...


@dataclass
class CacheKey:
    """Structured cache key with version tracking."""

    doc_hash: str
    model: str
    schema_version: str = "v1"

    def to_string(self) -> str:
        """
        Generate stable cache key string.

        Returns:
            16-character hex cache key

        Example:
            >>> key = CacheKey("abc123", "text-embedding-3-small")
            >>> key.to_string()
            'e8f5a3b2c1d4e7f6'
        """
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
        return self.size_bytes / self.max_size_bytes * 100

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


class LRUCache(Generic[T]):
    """
    Generic LRU cache with metrics and automatic eviction.

    Supports any value type T through generics. Implements CacheProtocol[T]
    for type safety.

    Features:
    - Type-safe generic interface
    - LRU eviction policy
    - Metrics tracking (hits, misses, evictions)
    - Memory limit enforcement

    Example:
        # Cache for embeddings
        embedding_cache = LRUCache[List[float]](max_entries=1000)
        embedding_cache.set("key1", [0.1, 0.2, 0.3])
        result = embedding_cache.get("key1")  # Type: Optional[List[float]]

        # Cache for any type
        from src.embeddings import EmbeddingResult
        result_cache = LRUCache[EmbeddingResult](max_entries=500)
    """

    def __init__(
        self,
        max_entries: int = 1000,
        max_size_bytes: int = 100 * 1024 * 1024,
    ) -> None:
        """
        Initialize LRU cache.

        Args:
            max_entries: Maximum number of cache entries
            max_size_bytes: Maximum cache size in bytes (default 100MB)
        """
        self._cache: Dict[str, T] = {}
        self._access_order: List[str] = []  # For LRU tracking
        self.metrics = CacheMetrics(
            max_entries=max_entries,
            max_size_bytes=max_size_bytes,
        )

    def get(self, key: str) -> Optional[T]:
        """
        Retrieve value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value if found, None otherwise
        """
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

    def set(self, key: str, value: T) -> None:
        """
        Store value in cache with LRU eviction.

        Args:
            key: Cache key
            value: Value to cache
        """
        # Estimate size (rough approximation)
        # For List[float]: len * 8 bytes
        # For other types: use a conservative estimate
        if isinstance(value, list):
            value_size = len(value) * 8  # type: ignore
        else:
            value_size = 1024  # Conservative 1KB estimate

        # Evict if at capacity
        while (
            self.metrics.entries >= self.metrics.max_entries
            or self.metrics.size_bytes + value_size > self.metrics.max_size_bytes
        ):
            self._evict_lru()

        self._cache[key] = value
        self._access_order.append(key)
        self.metrics.entries += 1
        self.metrics.size_bytes += value_size
        logger.debug(f"Cache set: {key} (~{value_size} bytes)")

    def _evict_lru(self) -> None:
        """Evict least recently used entry."""
        if not self._access_order:
            return

        lru_key = self._access_order.pop(0)
        value = self._cache.pop(lru_key)

        # Estimate size for metrics update
        if isinstance(value, list):
            value_size = len(value) * 8  # type: ignore
        else:
            value_size = 1024

        self.metrics.evictions += 1
        self.metrics.entries -= 1
        self.metrics.size_bytes -= value_size
        logger.info(
            f"Cache eviction: {lru_key} ({self.metrics.hit_rate:.1f}% hit rate)"
        )

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()
        self._access_order.clear()
        self.metrics.entries = 0
        self.metrics.size_bytes = 0
        logger.info("Cache cleared")

    def get_metrics(self) -> Dict[str, Any]:
        """Export current metrics."""
        return self.metrics.to_dict()


# Backward compatibility alias
EmbeddingCache = LRUCache[List[float]]


def log_cache_metrics(cache: EmbeddingCache) -> None:
    """
    Log cache metrics as structured JSON.

    Args:
        cache: EmbeddingCache instance
    """
    metrics = cache.get_metrics()
    logger.info(
        json.dumps(
            {
                "event": "cache_metrics",
                "timestamp": datetime.utcnow().isoformat() + "Z",
                **metrics,
            }
        )
    )


# Global cache schema version - increment on breaking changes
CACHE_SCHEMA_VERSION = "v1"
