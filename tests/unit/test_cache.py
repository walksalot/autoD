"""Unit tests for embedding cache module."""

import pytest
from hypothesis import given, strategies as st

from src.cache import (
    generate_cache_key,
    CacheMetrics,
    EmbeddingCache,
)


class TestCacheKey:
    """Test CacheKey dataclass and key generation."""

    def test_cache_key_determinism(self):
        """Same inputs produce same cache key."""
        key1 = generate_cache_key("abc123", "text-embedding-3-small")
        key2 = generate_cache_key("abc123", "text-embedding-3-small")
        assert key1 == key2

    def test_cache_key_length(self):
        """Cache keys are 16 characters."""
        key = generate_cache_key("abc123", "text-embedding-3-small")
        assert len(key) == 16

    def test_cache_key_hex_format(self):
        """Cache keys contain only hex characters."""
        key = generate_cache_key("abc123", "text-embedding-3-small")
        assert all(c in "0123456789abcdef" for c in key)

    def test_cache_key_collision_resistance(self):
        """Different inputs produce different keys."""
        key1 = generate_cache_key("abc123", "text-embedding-3-small")
        key2 = generate_cache_key("abc124", "text-embedding-3-small")
        assert key1 != key2

    def test_cache_key_model_sensitivity(self):
        """Different models produce different keys."""
        key1 = generate_cache_key("abc123", "text-embedding-3-small")
        key2 = generate_cache_key("abc123", "text-embedding-3-large")
        assert key1 != key2

    def test_cache_key_schema_versioning(self):
        """Schema version changes invalidate cache."""
        key_v1 = generate_cache_key("abc123", "text-embedding-3-small", "v1")
        key_v2 = generate_cache_key("abc123", "text-embedding-3-small", "v2")
        assert key_v1 != key_v2

    @given(
        doc_hash=st.text(min_size=64, max_size=64, alphabet="0123456789abcdef"),
        model=st.sampled_from(["text-embedding-3-small", "text-embedding-3-large"]),
    )
    def test_cache_key_properties(self, doc_hash: str, model: str):
        """Cache keys satisfy cryptographic properties (property-based test)."""
        key = generate_cache_key(doc_hash, model)

        # Fixed length
        assert len(key) == 16

        # Hex characters only
        assert all(c in "0123456789abcdef" for c in key)

        # Deterministic
        assert key == generate_cache_key(doc_hash, model)


class TestCacheMetrics:
    """Test CacheMetrics dataclass and calculations."""

    def test_metrics_initialization(self):
        """Metrics initialize with correct defaults."""
        metrics = CacheMetrics()
        assert metrics.hits == 0
        assert metrics.misses == 0
        assert metrics.evictions == 0
        assert metrics.entries == 0
        assert metrics.size_bytes == 0
        assert metrics.max_entries == 1000
        assert metrics.max_size_bytes == 100 * 1024 * 1024

    def test_hit_rate_calculation_zero_operations(self):
        """Hit rate is 0% with no operations."""
        metrics = CacheMetrics()
        assert metrics.hit_rate == 0.0

    def test_hit_rate_calculation_with_operations(self):
        """Hit rate calculates correctly."""
        metrics = CacheMetrics()
        metrics.hits = 2
        metrics.misses = 1
        assert metrics.hit_rate == pytest.approx(66.67, rel=0.1)

    def test_hit_rate_100_percent(self):
        """Hit rate is 100% with all hits."""
        metrics = CacheMetrics()
        metrics.hits = 10
        metrics.misses = 0
        assert metrics.hit_rate == 100.0

    def test_memory_utilization_calculation(self):
        """Memory utilization calculates correctly."""
        metrics = CacheMetrics(max_size_bytes=1000)
        metrics.size_bytes = 500
        assert metrics.memory_utilization == 50.0

    def test_metrics_to_dict(self):
        """Metrics export to dict correctly."""
        metrics = CacheMetrics()
        metrics.hits = 10
        metrics.misses = 5
        metrics.evictions = 2
        metrics.entries = 50
        metrics.size_bytes = 10 * 1024 * 1024  # 10MB

        data = metrics.to_dict()

        assert data["hits"] == 10
        assert data["misses"] == 5
        assert data["evictions"] == 2
        assert data["entries"] == 50
        assert data["hit_rate_pct"] == pytest.approx(66.67, rel=0.1)
        assert data["size_mb"] == pytest.approx(10.0, rel=0.1)


class TestEmbeddingCache:
    """Test EmbeddingCache functionality."""

    def test_cache_initialization(self):
        """Cache initializes with correct defaults."""
        cache = EmbeddingCache()
        assert cache.metrics.max_entries == 1000
        assert cache.metrics.max_size_bytes == 100 * 1024 * 1024
        assert cache.metrics.entries == 0
        assert cache.metrics.size_bytes == 0

    def test_cache_set_and_get(self):
        """Cache stores and retrieves embeddings."""
        cache = EmbeddingCache()
        embedding = [0.1, 0.2, 0.3]

        cache.set("key1", embedding)
        result = cache.get("key1")

        assert result == embedding
        assert cache.metrics.hits == 1
        assert cache.metrics.misses == 0
        assert cache.metrics.entries == 1

    def test_cache_miss(self):
        """Cache miss increments miss counter."""
        cache = EmbeddingCache()
        result = cache.get("nonexistent_key")

        assert result is None
        assert cache.metrics.hits == 0
        assert cache.metrics.misses == 1

    def test_cache_lru_eviction(self):
        """LRU eviction removes oldest entry."""
        cache = EmbeddingCache(max_entries=2)

        embedding1 = [0.1] * 100
        embedding2 = [0.2] * 100
        embedding3 = [0.3] * 100

        cache.set("key1", embedding1)
        cache.set("key2", embedding2)
        cache.set("key3", embedding3)  # Should evict key1 (LRU)

        assert cache.get("key1") is None  # Evicted
        assert cache.get("key2") == embedding2  # Still present
        assert cache.get("key3") == embedding3  # Most recent
        assert cache.metrics.evictions == 1
        assert cache.metrics.entries == 2

    def test_cache_lru_order_update_on_access(self):
        """Accessing entry moves it to end of LRU list."""
        cache = EmbeddingCache(max_entries=2)

        embedding1 = [0.1] * 100
        embedding2 = [0.2] * 100
        embedding3 = [0.3] * 100

        cache.set("key1", embedding1)
        cache.set("key2", embedding2)
        cache.get("key1")  # Access key1, making it most recent
        cache.set("key3", embedding3)  # Should evict key2, not key1

        assert cache.get("key1") == embedding1  # Not evicted
        assert cache.get("key2") is None  # Evicted
        assert cache.get("key3") == embedding3  # Present
        assert cache.metrics.evictions == 1

    def test_cache_memory_limit_eviction(self):
        """Cache evicts when memory limit reached."""
        cache = EmbeddingCache(max_entries=10, max_size_bytes=2000)  # ~2KB limit

        # Each embedding ~800 bytes (100 floats * 8 bytes)
        embedding = [0.1] * 100

        cache.set("key1", embedding)
        cache.set("key2", embedding)
        cache.set("key3", embedding)  # Should trigger eviction

        # Cache should respect memory limit
        assert cache.metrics.size_bytes <= cache.metrics.max_size_bytes
        assert cache.metrics.evictions >= 1

    def test_cache_clear(self):
        """Cache clear removes all entries."""
        cache = EmbeddingCache()

        cache.set("key1", [0.1] * 100)
        cache.set("key2", [0.2] * 100)
        cache.clear()

        assert cache.metrics.entries == 0
        assert cache.metrics.size_bytes == 0
        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_cache_metrics_tracking(self):
        """Cache metrics track all operations."""
        cache = EmbeddingCache()

        cache.set("key1", [0.1] * 100)
        cache.get("key1")  # Hit
        cache.get("key2")  # Miss
        cache.get("key1")  # Hit

        assert cache.metrics.hits == 2
        assert cache.metrics.misses == 1
        assert cache.metrics.hit_rate == pytest.approx(66.67, rel=0.1)

    @given(
        embeddings=st.lists(
            st.lists(st.floats(), min_size=100, max_size=100), min_size=1, max_size=10
        )
    )
    def test_cache_eviction_under_memory_pressure(self, embeddings):
        """Property test: cache respects memory limits under pressure."""
        cache = EmbeddingCache(max_entries=5, max_size_bytes=4000)  # ~5 embeddings

        for i, emb in enumerate(embeddings):
            cache.set(f"key{i}", emb)

        # Cache size should never exceed limits
        assert cache.metrics.entries <= cache.metrics.max_entries
        assert cache.metrics.size_bytes <= cache.metrics.max_size_bytes

    def test_get_metrics(self):
        """get_metrics returns metrics dict."""
        cache = EmbeddingCache()
        cache.set("key1", [0.1] * 100)
        cache.get("key1")

        metrics = cache.get_metrics()

        assert isinstance(metrics, dict)
        assert "hits" in metrics
        assert "misses" in metrics
        assert "hit_rate_pct" in metrics
        assert metrics["hits"] == 1
