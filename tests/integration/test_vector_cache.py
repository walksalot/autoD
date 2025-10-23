"""
Integration tests for vector cache with hit rate validation.

Tests the complete 3-tier caching system:
- Tier 1: In-memory LRU cache (EmbeddingGenerator)
- Tier 2: Database cache (embedding_vector column)
- Tier 3: OpenAI API (cache miss)

Acceptance Criteria:
- 80%+ cache hit rate validated
- TTL-based expiration works correctly
- LRU eviction functions properly
- Cache size limits enforced
- Cleanup operations function correctly
- Integration with monitoring system
"""

import pytest
from datetime import datetime, timezone, timedelta
from typing import List
from unittest.mock import Mock

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.models import Base, Document
from src.embeddings import EmbeddingGenerator
from src.embedding_cache import CacheMonitor, CacheStats, monitor_cache_health
from src.monitoring import get_cache_metrics


@pytest.fixture
def engine():
    """Create in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def session(engine):
    """Create database session."""
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def mock_openai_client():
    """Mock OpenAI client for embedding generation."""
    client = Mock()
    # Mock embeddings.create response
    client.embeddings.create.return_value = Mock(
        data=[Mock(embedding=[0.1] * 1536)],
        usage=Mock(prompt_tokens=10, total_tokens=10),
    )
    return client


@pytest.fixture
def embedding_generator(mock_openai_client, session):
    """Create EmbeddingGenerator with mocked client and DB session."""
    return EmbeddingGenerator(
        client=mock_openai_client,
        session=session,
        max_cache_size=10,  # Small cache for testing eviction
    )


@pytest.fixture
def cache_monitor(session):
    """Create CacheMonitor instance."""
    return CacheMonitor(session, max_size_mb=10)


@pytest.fixture
def sample_document(session):
    """Create a single test document."""
    doc = Document(
        sha256_hex="test_hash_1",
        original_filename="test_doc.pdf",
        metadata_json={
            "doc_type": "Invoice",
            "issuer": "Test Corp",
            "summary": "Test document for caching",
        },
        status="completed",
        created_at=datetime.now(timezone.utc),
    )
    session.add(doc)
    session.commit()
    return doc


def create_test_documents(session: Session, count: int) -> List[Document]:
    """Create multiple test documents."""
    docs = []
    for i in range(count):
        doc = Document(
            sha256_hex=f"hash_{i}",
            original_filename=f"doc_{i}.pdf",
            metadata_json={
                "doc_type": "Invoice",
                "issuer": f"Company {i}",
                "summary": f"Document number {i}",
            },
            status="completed",
            created_at=datetime.now(timezone.utc),
        )
        session.add(doc)
        docs.append(doc)
    session.commit()
    return docs


class TestMemoryCacheTier:
    """Test Tier 1: In-memory LRU cache."""

    def test_memory_cache_hit(self, embedding_generator, sample_document):
        """First call should miss, second call should hit memory cache."""
        # First call - cache miss
        result1 = embedding_generator.generate_embedding(sample_document)
        assert not result1.cached
        assert embedding_generator.memory_cache_hits == 0
        assert embedding_generator.api_calls == 1

        # Second call - memory cache hit
        result2 = embedding_generator.generate_embedding(sample_document)
        assert result2.cached
        assert embedding_generator.memory_cache_hits == 1
        assert embedding_generator.api_calls == 1  # No additional API call

    def test_lru_eviction_on_cache_full(self, embedding_generator, session):
        """LRU eviction should remove oldest entries when memory cache is full."""
        docs = create_test_documents(session, 15)  # More than max_cache_size (10)

        # Generate embeddings for all documents
        for doc in docs:
            embedding_generator.generate_embedding(doc)

        # Memory cache should be at max size (LRU eviction occurred)
        stats = embedding_generator.get_cache_stats()
        assert stats["cache_size"] == 10  # Only last 10 in memory cache

        # Re-access first 5 documents (evicted from memory but still in DB cache)
        embedding_generator.memory_cache_hits = 0
        embedding_generator.db_cache_hits = 0
        embedding_generator.api_calls = 0

        for doc in docs[:5]:
            embedding_generator.generate_embedding(doc)

        # Should hit DB cache (Tier 2) since evicted from memory (Tier 1)
        # but NOT require API calls (Tier 3)
        assert embedding_generator.db_cache_hits == 5, "Should retrieve from DB cache"
        assert (
            embedding_generator.memory_cache_hits == 0
        ), "Should not be in memory cache"
        assert (
            embedding_generator.api_calls == 0
        ), "Should not need API calls (DB cache hit)"

        # Verify entries are promoted back to memory cache
        stats_after = embedding_generator.get_cache_stats()
        assert (
            stats_after["cache_size"] == 10
        ), "Memory cache should still be at max size"

    def test_cache_clear(self, embedding_generator, sample_document):
        """Cache clear should remove all entries."""
        # Populate cache
        embedding_generator.generate_embedding(sample_document)
        assert embedding_generator.get_cache_stats()["cache_size"] == 1

        # Clear cache
        embedding_generator.clear_cache()
        assert embedding_generator.get_cache_stats()["cache_size"] == 0
        assert embedding_generator.memory_cache_hits == 0
        assert embedding_generator.db_cache_hits == 0
        assert embedding_generator.api_calls == 0


class TestDatabaseCacheTier:
    """Test Tier 2: Database cache with TTL."""

    def test_database_cache_hit(self, embedding_generator, sample_document, session):
        """Database cache should persist across generator instances."""
        # First generator - generate and cache
        result1 = embedding_generator.generate_embedding(sample_document)
        assert not result1.cached

        # Verify saved to database
        session.refresh(sample_document)
        assert sample_document.embedding_vector is not None
        assert sample_document.embedding_cache_key is not None
        assert sample_document.embedding_generated_at is not None

        # Create new generator (empty memory cache)
        new_generator = EmbeddingGenerator(
            client=embedding_generator.client,
            session=session,
        )

        # Should hit database cache
        result2 = new_generator.generate_embedding(sample_document)
        assert result2.cached
        assert new_generator.db_cache_hits == 1
        assert new_generator.api_calls == 0

    def test_database_cache_invalidation_on_text_change(
        self, embedding_generator, sample_document, session
    ):
        """Cache should be invalidated when document text changes."""
        # Generate initial embedding
        embedding_generator.generate_embedding(sample_document)

        # Modify document text (flag_modified needed for JSON field changes)
        from sqlalchemy.orm.attributes import flag_modified

        sample_document.metadata_json["summary"] = "Modified summary text"
        flag_modified(sample_document, "metadata_json")
        session.commit()

        # Refresh to ensure we have latest data
        session.expire(sample_document)
        session.refresh(sample_document)

        # Create new generator
        new_generator = EmbeddingGenerator(
            client=embedding_generator.client,
            session=session,
        )

        # Should not hit database cache (text changed, cache_key mismatch)
        new_generator.generate_embedding(sample_document)
        assert (
            new_generator.db_cache_hits == 0
        ), "Should miss DB cache due to text change"
        assert new_generator.api_calls == 1, "Should call API for new text"

    def test_database_cache_invalidation_on_model_change(
        self, embedding_generator, sample_document, session
    ):
        """Cache should be invalidated when embedding model changes."""
        # Generate with default model
        embedding_generator.generate_embedding(sample_document)

        # Create generator with different model
        new_generator = EmbeddingGenerator(
            client=embedding_generator.client,
            session=session,
            model="text-embedding-3-large",  # Different model
        )

        # Should not hit database cache (model changed)
        new_generator.generate_embedding(sample_document)
        assert new_generator.db_cache_hits == 0
        assert new_generator.api_calls == 1


class TestTTLExpiration:
    """Test TTL-based cache expiration."""

    def test_expired_cache_not_used(
        self, embedding_generator, sample_document, session
    ):
        """Expired cache entries should not be used."""
        # Generate initial embedding
        embedding_generator.generate_embedding(sample_document)

        # Manually set expiration date to past
        sample_document.embedding_generated_at = datetime.now(timezone.utc) - timedelta(
            days=100
        )
        session.commit()

        # Create new generator
        new_generator = EmbeddingGenerator(
            client=embedding_generator.client,
            session=session,
        )

        # Should not use expired cache
        new_generator.generate_embedding(sample_document)
        assert new_generator.db_cache_hits == 0
        assert new_generator.api_calls == 1

    def test_ttl_cleanup_removes_expired(self, cache_monitor, session):
        """TTL cleanup should remove expired entries."""
        # Create documents with expired embeddings
        docs = create_test_documents(session, 10)
        expired_time = datetime.now(timezone.utc) - timedelta(days=100)

        for doc in docs:
            doc.embedding_vector = {"embedding": [0.1] * 1536}
            doc.embedding_cache_key = "test_key"
            doc.embedding_model = "text-embedding-3-small"
            doc.embedding_generated_at = expired_time

        session.commit()

        # Run TTL cleanup
        removed = cache_monitor.cleanup_expired_entries()

        assert removed == 10
        assert cache_monitor.get_expired_count() == 0


class TestCacheSizeManagement:
    """Test cache size monitoring and cleanup."""

    def test_cache_size_calculation(self, cache_monitor, session):
        """Cache size should be calculated correctly."""
        # Create documents with embeddings
        docs = create_test_documents(session, 100)

        for doc in docs:
            doc.embedding_vector = {"embedding": [0.1] * 1536}
            doc.embedding_cache_key = "test_key"
            doc.embedding_model = "text-embedding-3-small"
            doc.embedding_generated_at = datetime.now(timezone.utc)

        session.commit()

        size_mb = cache_monitor.get_cache_size_mb()

        # 100 documents * 12.5 KB = 1.25 MB
        assert 1.0 < size_mb < 1.5  # Allow some variance

    def test_is_over_limit_detection(self, cache_monitor, session):
        """Should detect when cache exceeds size limit."""
        # Create enough documents to exceed 10MB limit
        docs = create_test_documents(session, 1000)  # ~12.5 MB

        for doc in docs:
            doc.embedding_vector = {"embedding": [0.1] * 1536}
            doc.embedding_cache_key = f"key_{doc.id}"
            doc.embedding_model = "text-embedding-3-small"
            doc.embedding_generated_at = datetime.now(timezone.utc)

        session.commit()

        assert cache_monitor.is_over_limit()

    def test_cleanup_oldest_entries(self, cache_monitor, session):
        """Cleanup should remove oldest entries until target size reached."""
        docs = create_test_documents(session, 200)

        # Add embeddings with different timestamps
        for idx, doc in enumerate(docs):
            doc.embedding_vector = {"embedding": [0.1] * 1536}
            doc.embedding_cache_key = f"key_{idx}"
            doc.embedding_model = "text-embedding-3-small"
            doc.embedding_generated_at = datetime.now(timezone.utc) - timedelta(
                hours=idx
            )

        session.commit()

        initial_size = cache_monitor.get_cache_size_mb()
        assert initial_size > 2.0  # Should be over 2MB

        # Cleanup to 1MB target
        removed = cache_monitor.cleanup_oldest_entries(target_mb=1.0)

        assert removed > 0
        final_size = cache_monitor.get_cache_size_mb()
        assert final_size <= 1.1  # Should be close to 1MB (allow 10% variance)


class TestCacheHitRate:
    """Test cache hit rate validation (target: 80%+)."""

    def test_batch_processing_achieves_80_percent_hit_rate(
        self, embedding_generator, session
    ):
        """Batch processing with repeated accesses should achieve 80%+ hit rate."""
        docs = create_test_documents(session, 20)

        # First pass - all cache misses
        for doc in docs:
            embedding_generator.generate_embedding(doc)

        # Reset stats
        initial_api_calls = embedding_generator.api_calls
        embedding_generator.memory_cache_hits = 0
        embedding_generator.db_cache_hits = 0

        # Second pass - should be all cache hits (5x repeated access)
        for _ in range(5):
            for doc in docs:
                embedding_generator.generate_embedding(doc)

        # Calculate hit rate
        stats = embedding_generator.get_cache_stats()
        total_requests = stats["total_requests"] - initial_api_calls
        total_hits = stats["total_cache_hits"]
        hit_rate = total_hits / total_requests if total_requests > 0 else 0.0

        # Should achieve >80% hit rate (actually should be 100% for this test)
        assert hit_rate >= 0.8, f"Hit rate {hit_rate:.1%} below 80% target"
        assert hit_rate > 0.95  # Should be near 100% for repeated access

    def test_realistic_workload_hit_rate(self, embedding_generator, session):
        """Realistic workload with mix of new and repeat accesses."""
        # Create initial set of documents
        docs_set_1 = create_test_documents(session, 30)

        # Create second set with different hashes (offset by 30 to avoid duplicates)
        docs_set_2 = []
        for i in range(30, 45):  # 15 documents with indices 30-44
            doc = Document(
                sha256_hex=f"hash_{i}",
                original_filename=f"doc_{i}.pdf",
                metadata_json={
                    "doc_type": "Invoice",
                    "issuer": f"Company {i}",
                    "summary": f"Document number {i}",
                },
                status="completed",
                created_at=datetime.now(timezone.utc),
            )
            session.add(doc)
            docs_set_2.append(doc)
        session.commit()

        # Phase 1: Process first set (cache misses)
        for doc in docs_set_1:
            embedding_generator.generate_embedding(doc)

        # Phase 2: Mix of repeats (80%) and new documents (20%)
        embedding_generator.memory_cache_hits = 0
        embedding_generator.db_cache_hits = 0
        embedding_generator.api_calls = 0

        # 80% repeats from set 1
        for _ in range(3):
            for doc in docs_set_1[:24]:  # 80% of 30
                embedding_generator.generate_embedding(doc)

        # 20% new from set 2
        for doc in docs_set_2[:12]:  # 20% of total accesses
            embedding_generator.generate_embedding(doc)

        # Calculate hit rate
        stats = embedding_generator.get_cache_stats()
        hit_rate = stats["overall_hit_rate"]

        assert hit_rate >= 0.8, f"Realistic workload hit rate {hit_rate:.1%} below 80%"


class TestCacheStatistics:
    """Test cache statistics and monitoring integration."""

    def test_cache_stats_includes_all_tiers(self, embedding_generator, sample_document):
        """Cache stats should include metrics from all 3 tiers."""
        # Generate embedding (API call)
        embedding_generator.generate_embedding(sample_document)

        # Hit memory cache
        embedding_generator.generate_embedding(sample_document)

        stats = embedding_generator.get_cache_stats()

        assert "cache_size" in stats
        assert "memory_cache_hits" in stats
        assert "db_cache_hits" in stats
        assert "api_calls" in stats
        assert "total_requests" in stats
        assert "overall_hit_rate" in stats

    def test_cache_stats_dataclass(self, embedding_generator, sample_document):
        """CacheStats dataclass should be created correctly."""
        embedding_generator.generate_embedding(sample_document)
        stats_dict = embedding_generator.get_cache_stats()
        cache_stats = CacheStats.from_dict(stats_dict)

        assert isinstance(cache_stats, CacheStats)
        assert cache_stats.total_requests > 0
        assert 0.0 <= cache_stats.overall_hit_rate <= 1.0

    def test_cache_health_check(self, session):
        """Cache health check should identify issues."""
        # Create documents with embeddings
        docs = create_test_documents(session, 10)
        for doc in docs:
            doc.embedding_vector = {"embedding": [0.1] * 1536}
            doc.embedding_cache_key = f"key_{doc.id}"
            doc.embedding_model = "text-embedding-3-small"
            doc.embedding_generated_at = datetime.now(timezone.utc)
        session.commit()

        health = monitor_cache_health(session)

        assert "status" in health
        assert "statistics" in health
        assert "issues" in health
        assert "warnings" in health
        assert "recommendations" in health


class TestBatchCaching:
    """Test batch embedding generation with caching."""

    def test_batch_generate_uses_cache(self, embedding_generator, session):
        """Batch generation should use cache for previously seen documents."""
        docs = create_test_documents(session, 20)

        # First batch - all misses
        results1 = embedding_generator.batch_generate_embeddings(docs)
        _first_api_calls = embedding_generator.api_calls

        # Second batch - should use cache
        embedding_generator.api_calls = 0
        results2 = embedding_generator.batch_generate_embeddings(docs)

        assert embedding_generator.api_calls == 0  # All hits
        assert len(results1) == len(results2) == 20

    def test_batch_partial_cache_hits(self, embedding_generator, session):
        """Batch with mix of cached and uncached documents."""
        docs = create_test_documents(session, 20)

        # Cache first 10
        for doc in docs[:10]:
            embedding_generator.generate_embedding(doc)

        # Batch all 20
        embedding_generator.api_calls = 0
        _results = embedding_generator.batch_generate_embeddings(docs)

        # Should only call API for last 10
        assert embedding_generator.api_calls == 1  # 1 batch API call for 10 docs
        assert len(_results) == 20


class TestCacheIntegrationWithMonitoring:
    """Test integration with monitoring system."""

    def test_cache_metrics_collection(self, embedding_generator, sample_document):
        """Cache operations should be tracked by monitoring system."""
        cache_metrics = get_cache_metrics()

        # Record some cache operations
        cache_metrics.record_cache_hit(tier="memory", hit_latency_ms=0.5)
        cache_metrics.record_cache_miss(api_latency_ms=150.0)
        cache_metrics.record_cache_size(
            memory_entries=10, db_entries=100, db_size_mb=1.25
        )

        # Verify metrics recorded
        hit_rate_data = cache_metrics.get_cache_hit_rate(window_minutes=5)
        assert hit_rate_data["total_requests"] > 0

    def test_cache_health_monitoring(self):
        """Cache health check should work with monitoring integration."""
        cache_metrics = get_cache_metrics()

        # Simulate healthy cache
        for _ in range(80):
            cache_metrics.record_cache_hit(tier="memory")
        for _ in range(20):
            cache_metrics.record_cache_miss()

        cache_metrics.record_cache_size(
            memory_entries=100, db_entries=500, db_size_mb=6.25
        )

        health = cache_metrics.check_cache_health(min_hit_rate=0.7, max_size_mb=10)

        assert health["status"] == "healthy"
        assert health["hit_rate"] >= 0.7


class TestEdgeCases:
    """Test edge cases and error scenarios."""

    def test_empty_cache_statistics(self, embedding_generator):
        """Empty cache should return valid statistics."""
        stats = embedding_generator.get_cache_stats()

        assert stats["cache_size"] == 0
        assert stats["total_requests"] == 0
        assert stats["overall_hit_rate"] == 0.0

    def test_cache_monitor_with_no_cached_documents(self, cache_monitor):
        """Cache monitor should handle empty cache."""
        assert cache_monitor.get_cache_size_mb() == 0.0
        assert not cache_monitor.is_over_limit()
        assert cache_monitor.get_expired_count() == 0
        assert cache_monitor.cleanup_expired_entries() == 0

    def test_cache_health_with_zero_requests(self, session):
        """Health check should handle zero requests gracefully."""
        health = monitor_cache_health(session)

        assert health["status"] in ["healthy", "warning"]
        assert "No cache requests" in str(health.get("warnings", []))
