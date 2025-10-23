"""Integration tests for embedding cache with database."""

import pytest
from datetime import datetime, timezone

from src.cache import (
    EmbeddingCache,
    generate_cache_key,
    log_cache_metrics,
    CACHE_SCHEMA_VERSION,
)
from src.models import Document
from src.database import DatabaseManager


class TestCacheIntegration:
    """Integration tests for cache with database operations."""

    def test_cache_with_documents(self, db_session):
        """Test cache operations with real Document objects."""
        # Create test documents
        docs = []
        for i in range(10):
            doc = Document(
                sha256_hex=f"hash{i:02d}",
                sha256_base64=f"b64hash{i:02d}",
                original_filename=f"test{i}.pdf",
                file_size_bytes=1000 + i,
                metadata_json={"doc_type": "Invoice", "issuer": f"Company {i}"},
                status="completed",
                processed_at=datetime.now(timezone.utc),
            )
            db_session.add(doc)
            docs.append(doc)

        db_session.commit()

        # Generate cache keys for documents
        cache = EmbeddingCache()
        embeddings_by_doc = {}

        for doc in docs:
            # Generate unique cache key for each document
            cache_key = generate_cache_key(
                doc.sha256_hex, "text-embedding-3-small", CACHE_SCHEMA_VERSION
            )

            # Simulate embedding (1536 dimensions for text-embedding-3-small)
            embedding = [float(i) / 1000 for i in range(1536)]
            embeddings_by_doc[doc.id] = embedding

            # Store in cache
            cache.set(cache_key, embedding)

        # Verify all embeddings cached
        assert cache.metrics.entries == 10
        assert cache.metrics.hits == 0
        assert cache.metrics.misses == 0

        # Retrieve embeddings and verify cache hits
        for doc in docs:
            cache_key = generate_cache_key(
                doc.sha256_hex, "text-embedding-3-small", CACHE_SCHEMA_VERSION
            )
            cached_embedding = cache.get(cache_key)

            assert cached_embedding is not None
            assert cached_embedding == embeddings_by_doc[doc.id]

        # Verify cache hit metrics
        assert cache.metrics.hits == 10
        assert cache.metrics.misses == 0
        assert cache.metrics.hit_rate == 100.0

    def test_cache_with_duplicate_documents(self, db_session):
        """Test cache behavior when same content hash is reprocessed."""
        # Create a single document (duplicates are prevented by UNIQUE constraint)
        doc = Document(
            sha256_hex="duplicate_hash",
            sha256_base64="duplicate_b64",
            original_filename="invoice.pdf",
            file_size_bytes=5000,
            metadata_json={"doc_type": "Invoice"},
            status="completed",
        )
        db_session.add(doc)
        db_session.commit()

        # Cache should use same key for same content hash
        cache = EmbeddingCache()
        cache_key = generate_cache_key("duplicate_hash", "text-embedding-3-small")

        # Store embedding once
        embedding = [0.1] * 1536
        cache.set(cache_key, embedding)

        # Multiple lookups with same key should all hit cache
        assert cache.get(cache_key) == embedding
        assert cache.get(cache_key) == embedding
        assert cache.get(cache_key) == embedding
        assert cache.metrics.hits == 3
        assert cache.metrics.entries == 1  # Only one unique entry
        assert cache.metrics.hit_rate == 100.0

    def test_cache_schema_version_invalidation(self, db_session):
        """Test cache invalidation when schema version changes."""
        doc = Document(
            sha256_hex="schema_test",
            sha256_base64="schema_test_b64",
            original_filename="test.pdf",
            file_size_bytes=1000,
            metadata_json={"doc_type": "Invoice"},
            status="completed",
        )
        db_session.add(doc)
        db_session.commit()

        cache = EmbeddingCache()

        # Cache embedding with v1 schema
        key_v1 = generate_cache_key("schema_test", "text-embedding-3-small", "v1")
        embedding_v1 = [0.1] * 1536
        cache.set(key_v1, embedding_v1)

        # Cache embedding with v2 schema (simulating schema change)
        key_v2 = generate_cache_key("schema_test", "text-embedding-3-small", "v2")
        embedding_v2 = [0.2] * 1536
        cache.set(key_v2, embedding_v2)

        # Both versions should be cached separately
        assert cache.get(key_v1) == embedding_v1
        assert cache.get(key_v2) == embedding_v2
        assert cache.metrics.entries == 2
        assert key_v1 != key_v2

    def test_cache_metrics_logging(self, db_session, caplog):
        """Test structured logging of cache metrics."""
        import logging

        caplog.set_level(logging.INFO)

        cache = EmbeddingCache(max_entries=5)

        # Populate cache
        for i in range(10):
            cache.set(f"key{i}", [0.1] * 100)

        # Access some entries
        for i in range(5):
            cache.get(f"key{i}")

        # Log metrics
        log_cache_metrics(cache)

        # Verify structured log output
        assert any("cache_metrics" in record.message for record in caplog.records)

        # Verify metrics accuracy
        metrics = cache.get_metrics()
        assert metrics["entries"] == 5  # LRU eviction kept last 5
        assert metrics["evictions"] == 5  # First 5 evicted
        assert metrics["hits"] >= 0
        assert metrics["misses"] >= 5  # First 5 were misses

    def test_cache_memory_efficiency(self, db_session):
        """Test cache respects memory limits with realistic embeddings."""
        # text-embedding-3-small has 1536 dimensions
        # Each float64 = 8 bytes → 1536 * 8 = 12,288 bytes per embedding
        # Allow ~10 embeddings (10 * 12,288 = 122,880 bytes)
        cache = EmbeddingCache(max_entries=100, max_size_bytes=130_000)

        embeddings = []
        for i in range(15):
            embedding = [float(i) / 1000] * 1536
            embeddings.append(embedding)
            cache.set(f"key{i}", embedding)

        # Cache should have evicted entries to stay under memory limit
        assert cache.metrics.size_bytes <= cache.metrics.max_size_bytes
        assert cache.metrics.entries <= 11  # ~10-11 embeddings fit
        assert cache.metrics.evictions >= 4  # At least 4 evicted

    def test_cache_concurrent_operations(self, db_session):
        """Test cache with concurrent-like access patterns."""
        cache = EmbeddingCache(max_entries=20)

        # Simulate batch processing with interleaved access
        embeddings = {}
        for batch in range(3):
            # Add new embeddings
            for i in range(10):
                key = f"batch{batch}_doc{i}"
                embedding = [float(batch * 10 + i) / 1000] * 100
                cache.set(key, embedding)
                embeddings[key] = embedding

            # Access previous batch (simulating hot cache pattern)
            if batch > 0:
                for i in range(5):
                    prev_key = f"batch{batch - 1}_doc{i}"
                    if prev_key in embeddings:
                        cached = cache.get(prev_key)
                        if cached:  # May have been evicted
                            assert cached == embeddings[prev_key]

        # Verify cache stayed within limits
        assert cache.metrics.entries <= 20
        assert cache.metrics.hits > 0  # Some previous batch accesses hit

    def test_cache_clear_operation(self, db_session):
        """Test cache clearing preserves integrity."""
        cache = EmbeddingCache()

        # Populate cache
        for i in range(10):
            cache.set(f"key{i}", [0.1] * 100)

        assert cache.metrics.entries == 10

        # Clear cache
        cache.clear()

        # Verify complete reset
        assert cache.metrics.entries == 0
        assert cache.metrics.size_bytes == 0
        assert cache.get("key0") is None
        assert cache.metrics.misses == 1

    def test_cache_model_sensitivity(self, db_session):
        """Test cache distinguishes between different embedding models."""
        doc = Document(
            sha256_hex="model_test",
            sha256_base64="model_test_b64",
            original_filename="test.pdf",
            file_size_bytes=1000,
            metadata_json={"doc_type": "Invoice"},
            status="completed",
        )
        db_session.add(doc)
        db_session.commit()

        cache = EmbeddingCache()

        # Cache same document with different models
        key_small = generate_cache_key("model_test", "text-embedding-3-small")
        key_large = generate_cache_key("model_test", "text-embedding-3-large")

        embedding_small = [0.1] * 1536
        embedding_large = [0.2] * 3072  # Different dimensions

        cache.set(key_small, embedding_small)
        cache.set(key_large, embedding_large)

        # Both should be cached separately
        assert cache.get(key_small) == embedding_small
        assert cache.get(key_large) == embedding_large
        assert cache.metrics.entries == 2
        assert key_small != key_large


@pytest.fixture
def db_session():
    """Create a test database session."""
    db_manager = DatabaseManager("sqlite:///:memory:")
    db_manager.create_tables()

    with db_manager.get_session() as session:
        yield session
