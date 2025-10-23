"""
Unit tests for embedding cache monitoring and statistics.

Tests cover:
- CacheStats dataclass (serialization, health checks, string formatting)
- CacheMonitor class (size calculation, TTL expiration, cleanup operations)
- monitor_cache_health() function (health checks, warnings, recommendations)
- Edge cases (empty DB, expired entries, over-limit scenarios)

Target: 90%+ code coverage
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timezone, timedelta

from src.embedding_cache import (
    CacheStats,
    CacheMonitor,
    monitor_cache_health,
)
from src.models import Document


# === Fixtures ===


@pytest.fixture
def mock_session():
    """Create mock SQLAlchemy session."""
    session = Mock()
    session.commit = Mock()
    session.query = Mock()
    return session


@pytest.fixture
def mock_config():
    """Create mock configuration."""
    config = Mock()
    config.vector_cache_max_size_mb = 1024
    config.vector_cache_ttl_days = 7
    return config


@pytest.fixture
def sample_document():
    """Create a sample document with embedding."""
    doc = Document(
        id=1,
        sha256_hex="a" * 64,
        original_filename="test.pdf",
        metadata_json={"doc_type": "Invoice", "issuer": "ACME Corp"},
        status="completed",
        embedding_vector={"embedding": [0.1] * 1536},
        embedding_cache_key="test_cache_key",
        embedding_model="text-embedding-3-small",
        embedding_generated_at=datetime.now(timezone.utc),
    )
    return doc


@pytest.fixture
def sample_cache_stats():
    """Create sample cache statistics dictionary."""
    return {
        "cache_size": 100,
        "max_cache_size": 1000,
        "memory_cache_hits": 80,
        "db_cache_hits": 15,
        "total_cache_hits": 95,
        "api_calls": 5,
        "total_requests": 100,
        "memory_hit_rate": 0.8,
        "overall_hit_rate": 0.95,
        "total_tokens": 50000,
        "cache_size_mb": 12.5,
        "avg_response_time_ms": 150.0,
    }


# === Test Cases ===


class TestCacheStats:
    """Tests for CacheStats dataclass."""

    def test_from_dict_creates_instance(self, sample_cache_stats):
        """Test creating CacheStats from dictionary."""
        stats = CacheStats.from_dict(sample_cache_stats)

        assert stats.cache_size == 100
        assert stats.max_cache_size == 1000
        assert stats.memory_cache_hits == 80
        assert stats.db_cache_hits == 15
        assert stats.total_cache_hits == 95
        assert stats.api_calls == 5
        assert stats.total_requests == 100
        assert stats.memory_hit_rate == 0.8
        assert stats.overall_hit_rate == 0.95
        assert stats.total_tokens == 50000
        assert stats.cache_size_mb == 12.5
        assert stats.avg_response_time_ms == 150.0

    def test_from_dict_with_missing_optional_fields(self):
        """Test creating CacheStats from dict with missing optional fields."""
        minimal_stats = {
            "cache_size": 10,
            "max_cache_size": 100,
            "memory_cache_hits": 5,
            "db_cache_hits": 3,
            "total_cache_hits": 8,
            "api_calls": 2,
            "total_requests": 10,
            "memory_hit_rate": 0.5,
            "overall_hit_rate": 0.8,
            "total_tokens": 1000,
        }

        stats = CacheStats.from_dict(minimal_stats)

        assert stats.cache_size_mb is None
        assert stats.avg_response_time_ms is None

    def test_from_dict_with_missing_required_fields(self):
        """Test creating CacheStats with missing required fields uses defaults."""
        empty_stats = {}

        stats = CacheStats.from_dict(empty_stats)

        assert stats.cache_size == 0
        assert stats.max_cache_size == 0
        assert stats.memory_cache_hits == 0
        assert stats.overall_hit_rate == 0.0

    def test_to_dict_serialization(self, sample_cache_stats):
        """Test serializing CacheStats to dictionary."""
        stats = CacheStats.from_dict(sample_cache_stats)
        result = stats.to_dict()

        assert result == sample_cache_stats

    def test_to_dict_round_trip(self, sample_cache_stats):
        """Test round-trip serialization (from_dict -> to_dict)."""
        stats1 = CacheStats.from_dict(sample_cache_stats)
        dict_repr = stats1.to_dict()
        stats2 = CacheStats.from_dict(dict_repr)

        assert stats1 == stats2

    def test_is_healthy_with_good_hit_rate(self):
        """Test is_healthy returns True when hit rate meets threshold."""
        stats = CacheStats(
            cache_size=100,
            max_cache_size=1000,
            memory_cache_hits=80,
            db_cache_hits=10,
            total_cache_hits=90,
            api_calls=10,
            total_requests=100,
            memory_hit_rate=0.8,
            overall_hit_rate=0.9,  # Above default threshold of 0.8
            total_tokens=5000,
        )

        assert stats.is_healthy() is True

    def test_is_healthy_with_exact_threshold(self):
        """Test is_healthy returns True when hit rate equals threshold."""
        stats = CacheStats(
            cache_size=100,
            max_cache_size=1000,
            memory_cache_hits=80,
            db_cache_hits=0,
            total_cache_hits=80,
            api_calls=20,
            total_requests=100,
            memory_hit_rate=0.8,
            overall_hit_rate=0.8,  # Exactly at threshold
            total_tokens=5000,
        )

        assert stats.is_healthy() is True

    def test_is_healthy_with_low_hit_rate(self):
        """Test is_healthy returns False when hit rate below threshold."""
        stats = CacheStats(
            cache_size=100,
            max_cache_size=1000,
            memory_cache_hits=50,
            db_cache_hits=10,
            total_cache_hits=60,
            api_calls=40,
            total_requests=100,
            memory_hit_rate=0.5,
            overall_hit_rate=0.6,  # Below default threshold of 0.8
            total_tokens=5000,
        )

        assert stats.is_healthy() is False

    def test_is_healthy_with_custom_threshold(self):
        """Test is_healthy with custom min_hit_rate threshold."""
        stats = CacheStats(
            cache_size=100,
            max_cache_size=1000,
            memory_cache_hits=50,
            db_cache_hits=10,
            total_cache_hits=60,
            api_calls=40,
            total_requests=100,
            memory_hit_rate=0.5,
            overall_hit_rate=0.6,
            total_tokens=5000,
        )

        # Healthy with lower threshold
        assert stats.is_healthy(min_hit_rate=0.5) is True

        # Unhealthy with higher threshold
        assert stats.is_healthy(min_hit_rate=0.7) is False

    def test_str_formatting_with_all_fields(self):
        """Test string formatting includes all metrics."""
        stats = CacheStats(
            cache_size=100,
            max_cache_size=1000,
            memory_cache_hits=80,
            db_cache_hits=15,
            total_cache_hits=95,
            api_calls=5,
            total_requests=100,
            memory_hit_rate=0.8,
            overall_hit_rate=0.95,
            total_tokens=5000,
            cache_size_mb=12.5,
        )

        result = str(stats)

        assert "CacheStats(" in result
        assert "memory=80/100" in result
        assert "(80.0%)" in result
        assert "db=15/100" in result
        assert "(15.0%)" in result
        assert "overall=95.0%" in result
        assert "size=100/1000" in result
        assert "12.5MB" in result

    def test_str_formatting_without_cache_size_mb(self):
        """Test string formatting when cache_size_mb is None."""
        stats = CacheStats(
            cache_size=50,
            max_cache_size=500,
            memory_cache_hits=40,
            db_cache_hits=5,
            total_cache_hits=45,
            api_calls=5,
            total_requests=50,
            memory_hit_rate=0.8,
            overall_hit_rate=0.9,
            total_tokens=2500,
            cache_size_mb=None,
        )

        result = str(stats)

        assert "CacheStats(" in result
        assert "size=50/500" in result
        assert "MB" not in result  # Should not include MB when None


class TestCacheMonitor:
    """Tests for CacheMonitor class."""

    @patch("src.embedding_cache.get_config")
    def test_initialization_with_defaults(
        self, mock_get_config, mock_session, mock_config
    ):
        """Test CacheMonitor initialization with default parameters."""
        mock_get_config.return_value = mock_config

        monitor = CacheMonitor(mock_session)

        assert monitor.session == mock_session
        assert monitor.max_size_mb == 1024
        assert monitor.ttl_days == 7

    @patch("src.embedding_cache.get_config")
    def test_initialization_with_custom_max_size(
        self, mock_get_config, mock_session, mock_config
    ):
        """Test CacheMonitor initialization with custom max_size_mb."""
        mock_get_config.return_value = mock_config

        monitor = CacheMonitor(mock_session, max_size_mb=2048)

        assert monitor.max_size_mb == 2048
        assert monitor.ttl_days == 7

    @patch("src.embedding_cache.get_config")
    def test_get_cache_size_mb_empty_database(
        self, mock_get_config, mock_session, mock_config
    ):
        """Test get_cache_size_mb with no cached embeddings."""
        mock_get_config.return_value = mock_config

        # Mock query to return 0 documents
        mock_query = Mock()
        mock_query.filter.return_value.scalar.return_value = 0
        mock_session.query.return_value = mock_query

        monitor = CacheMonitor(mock_session)
        size_mb = monitor.get_cache_size_mb()

        assert size_mb == 0.0

    @patch("src.embedding_cache.get_config")
    def test_get_cache_size_mb_with_documents(
        self, mock_get_config, mock_session, mock_config
    ):
        """Test get_cache_size_mb calculates size correctly."""
        mock_get_config.return_value = mock_config

        # Mock query to return 100 documents
        mock_query = Mock()
        mock_query.filter.return_value.scalar.return_value = 100
        mock_session.query.return_value = mock_query

        monitor = CacheMonitor(mock_session)
        size_mb = monitor.get_cache_size_mb()

        # Expected: 100 docs * 12,500 bytes/doc / (1024 * 1024) = ~1.192 MB
        expected_mb = (100 * 12_500) / (1024 * 1024)
        assert abs(size_mb - expected_mb) < 0.01

    @patch("src.embedding_cache.get_config")
    def test_get_cache_size_mb_large_cache(
        self, mock_get_config, mock_session, mock_config
    ):
        """Test get_cache_size_mb with large number of documents."""
        mock_get_config.return_value = mock_config

        # Mock query to return 10,000 documents
        mock_query = Mock()
        mock_query.filter.return_value.scalar.return_value = 10_000
        mock_session.query.return_value = mock_query

        monitor = CacheMonitor(mock_session)
        size_mb = monitor.get_cache_size_mb()

        # Expected: ~119.2 MB
        expected_mb = (10_000 * 12_500) / (1024 * 1024)
        assert abs(size_mb - expected_mb) < 1.0

    @patch("src.embedding_cache.get_config")
    def test_is_over_limit_when_under_limit(
        self, mock_get_config, mock_session, mock_config
    ):
        """Test is_over_limit returns False when cache is under limit."""
        mock_get_config.return_value = mock_config

        # Mock query to return 100 documents (~1.2 MB, under 1024 MB limit)
        mock_query = Mock()
        mock_query.filter.return_value.scalar.return_value = 100
        mock_session.query.return_value = mock_query

        monitor = CacheMonitor(mock_session)
        _is_over = monitor.is_over_limit()

        assert _is_over is False

    @patch("src.embedding_cache.get_config")
    def test_is_over_limit_when_over_limit(
        self, mock_get_config, mock_session, mock_config
    ):
        """Test is_over_limit returns True when cache exceeds limit."""
        mock_get_config.return_value = mock_config

        # Mock query to return 100,000 documents (~1192 MB, over 1024 MB limit)
        mock_query = Mock()
        mock_query.filter.return_value.scalar.return_value = 100_000
        mock_session.query.return_value = mock_query

        monitor = CacheMonitor(mock_session)
        _is_over = monitor.is_over_limit()

        assert _is_over is True

    @patch("src.embedding_cache.get_config")
    def test_is_over_limit_at_exact_boundary(
        self, mock_get_config, mock_session, mock_config
    ):
        """Test is_over_limit at exact size limit boundary."""
        mock_get_config.return_value = mock_config
        mock_config.vector_cache_max_size_mb = 10  # Small limit for testing

        # Calculate docs for exactly 10 MB
        # 10 MB = 10 * 1024 * 1024 bytes = 10,485,760 bytes
        # docs = 10,485,760 / 12,500 = 838.86... ≈ 839 docs
        mock_query = Mock()
        mock_query.filter.return_value.scalar.return_value = 839
        mock_session.query.return_value = mock_query

        monitor = CacheMonitor(mock_session, max_size_mb=10)
        _is_over = monitor.is_over_limit()

        # Should be exactly at or slightly over limit
        size_mb = monitor.get_cache_size_mb()
        assert size_mb >= 10.0 or abs(size_mb - 10.0) < 0.01

    @patch("src.embedding_cache.get_config")
    def test_get_expired_count_no_expired_entries(
        self, mock_get_config, mock_session, mock_config
    ):
        """Test get_expired_count returns 0 when no entries expired."""
        mock_get_config.return_value = mock_config

        # Mock query to return 0 expired documents
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.scalar.return_value = 0
        mock_query.filter.return_value = mock_filter
        mock_session.query.return_value = mock_query

        monitor = CacheMonitor(mock_session)
        expired = monitor.get_expired_count()

        assert expired == 0

    @patch("src.embedding_cache.get_config")
    def test_get_expired_count_with_expired_entries(
        self, mock_get_config, mock_session, mock_config
    ):
        """Test get_expired_count returns correct count."""
        mock_get_config.return_value = mock_config

        # Mock query to return 15 expired documents
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.scalar.return_value = 15
        mock_query.filter.return_value = mock_filter
        mock_session.query.return_value = mock_query

        monitor = CacheMonitor(mock_session)
        expired = monitor.get_expired_count()

        assert expired == 15

    @patch("src.embedding_cache.get_config")
    def test_cleanup_expired_entries_no_entries(
        self, mock_get_config, mock_session, mock_config
    ):
        """Test cleanup_expired_entries when no entries expired."""
        mock_get_config.return_value = mock_config

        # Mock query to return empty list
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.all.return_value = []
        mock_query.filter.return_value = mock_filter
        mock_session.query.return_value = mock_query

        monitor = CacheMonitor(mock_session)
        count = monitor.cleanup_expired_entries()

        assert count == 0
        mock_session.commit.assert_not_called()

    @patch("src.embedding_cache.get_config")
    def test_cleanup_expired_entries_success(
        self, mock_get_config, mock_session, mock_config
    ):
        """Test cleanup_expired_entries removes expired embeddings."""
        mock_get_config.return_value = mock_config

        # Create mock expired documents
        expired_docs = []
        for i in range(5):
            doc = Mock(spec=Document)
            doc.id = i
            doc.embedding_vector = {"embedding": [0.1] * 1536}
            doc.embedding_cache_key = f"key_{i}"
            doc.embedding_model = "text-embedding-3-small"
            doc.embedding_generated_at = datetime.now(timezone.utc) - timedelta(days=10)
            expired_docs.append(doc)

        # Mock query to return expired documents
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.all.return_value = expired_docs
        mock_query.filter.return_value = mock_filter
        mock_session.query.return_value = mock_query

        monitor = CacheMonitor(mock_session)
        count = monitor.cleanup_expired_entries()

        assert count == 5

        # Verify embedding fields were cleared
        for doc in expired_docs:
            assert doc.embedding_vector is None
            assert doc.embedding_cache_key is None
            assert doc.embedding_model is None
            assert doc.embedding_generated_at is None

        # Verify commit was called
        mock_session.commit.assert_called_once()

    @patch("src.embedding_cache.get_config")
    def test_cleanup_oldest_entries_already_under_target(
        self, mock_get_config, mock_session, mock_config
    ):
        """Test cleanup_oldest_entries when cache already under target."""
        mock_get_config.return_value = mock_config

        # Mock query to return 10 documents (~0.12 MB, well under 90% of 1024 MB)
        mock_query = Mock()
        mock_query.filter.return_value.scalar.return_value = 10
        mock_session.query.return_value = mock_query

        monitor = CacheMonitor(mock_session)
        count = monitor.cleanup_oldest_entries()

        assert count == 0
        mock_session.commit.assert_not_called()

    @patch("src.embedding_cache.get_config")
    def test_cleanup_oldest_entries_with_custom_target(
        self, mock_get_config, mock_session, mock_config
    ):
        """Test cleanup_oldest_entries with custom target size."""
        mock_get_config.return_value = mock_config

        # Setup: 1000 docs (~11.9 MB), target 5 MB
        # Need to remove ~580 docs to reach 5 MB

        # Mock initial size query (1000 docs)
        # Mock subsequent queries for cleanup loop
        call_count = [0]
        doc_count = [1000]

        def mock_scalar_side_effect():
            call_count[0] += 1
            return doc_count[0]

        mock_scalar = Mock(side_effect=mock_scalar_side_effect)

        # Mock oldest documents query
        def mock_all_side_effect():
            if doc_count[0] <= 0:
                return []
            # Return batch of 100 oldest docs
            batch = []
            for i in range(min(100, doc_count[0])):
                doc = Mock(spec=Document)
                doc.id = i
                doc.embedding_vector = {"embedding": [0.1] * 1536}
                doc.embedding_cache_key = f"key_{i}"
                batch.append(doc)
            doc_count[0] -= len(batch)
            return batch

        mock_all = Mock(side_effect=mock_all_side_effect)

        # Setup query mocks
        mock_order = Mock()
        mock_order.limit.return_value.all = mock_all

        mock_filter = Mock()
        mock_filter.scalar = mock_scalar
        mock_filter.order_by.return_value = mock_order

        mock_query = Mock()
        mock_query.filter.return_value = mock_filter

        mock_session.query.return_value = mock_query

        monitor = CacheMonitor(mock_session)
        count = monitor.cleanup_oldest_entries(target_mb=5.0)

        # Should have removed entries (exact count depends on loop iterations)
        assert count > 0

    @patch("src.embedding_cache.get_config")
    def test_cleanup_oldest_entries_default_target_90_percent(
        self, mock_get_config, mock_session, mock_config
    ):
        """Test cleanup_oldest_entries uses 90% of max_size_mb as default target."""
        mock_get_config.return_value = mock_config
        mock_config.vector_cache_max_size_mb = 100  # 100 MB limit

        # Setup: 10000 docs (~119 MB, over limit)
        # Default target should be 90 MB (90% of 100 MB)

        call_count = [0]
        doc_count = [10_000]

        def mock_scalar_side_effect():
            call_count[0] += 1
            return doc_count[0]

        mock_scalar = Mock(side_effect=mock_scalar_side_effect)

        def mock_all_side_effect():
            if doc_count[0] <= 0:
                return []
            batch_size = min(100, doc_count[0])
            batch = [Mock(spec=Document) for _ in range(batch_size)]
            for doc in batch:
                doc.embedding_vector = {"embedding": [0.1] * 1536}
                doc.embedding_cache_key = "key"
            doc_count[0] -= batch_size
            return batch

        mock_all = Mock(side_effect=mock_all_side_effect)

        mock_order = Mock()
        mock_order.limit.return_value.all = mock_all

        mock_filter = Mock()
        mock_filter.scalar = mock_scalar
        mock_filter.order_by.return_value = mock_order

        mock_query = Mock()
        mock_query.filter.return_value = mock_filter

        mock_session.query.return_value = mock_query

        monitor = CacheMonitor(mock_session, max_size_mb=100)
        count = monitor.cleanup_oldest_entries()  # Should use default 90 MB target

        assert count > 0

    @patch("src.embedding_cache.get_config")
    def test_cleanup_oldest_entries_removes_in_batches(
        self, mock_get_config, mock_session, mock_config
    ):
        """Test cleanup_oldest_entries processes in batches."""
        mock_get_config.return_value = mock_config

        # Track batch operations
        batches_processed = []

        # Setup: 250 docs need to be removed
        doc_count = [300]
        target_docs = 50  # Need to remove 250 to reach target

        def mock_scalar_side_effect():
            return doc_count[0]

        def mock_all_side_effect():
            if doc_count[0] <= target_docs:
                return []

            batch_size = min(100, doc_count[0] - target_docs)
            batch = []
            for i in range(batch_size):
                doc = Mock(spec=Document)
                doc.embedding_vector = {"embedding": [0.1] * 1536}
                batch.append(doc)

            doc_count[0] -= batch_size
            batches_processed.append(batch_size)
            return batch

        mock_scalar = Mock(side_effect=mock_scalar_side_effect)
        mock_all = Mock(side_effect=mock_all_side_effect)

        mock_order = Mock()
        mock_order.limit.return_value.all = mock_all

        mock_filter = Mock()
        mock_filter.scalar = mock_scalar
        mock_filter.order_by.return_value = mock_order

        mock_query = Mock()
        mock_query.filter.return_value = mock_filter

        mock_session.query.return_value = mock_query

        monitor = CacheMonitor(mock_session)
        count = monitor.cleanup_oldest_entries(target_mb=0.6)  # ~50 docs

        # Should process in multiple batches (100, 100, 50)
        assert len(batches_processed) >= 2
        assert count == sum(batches_processed)

    @patch("src.embedding_cache.get_config")
    def test_get_cache_statistics_comprehensive(
        self, mock_get_config, mock_session, mock_config
    ):
        """Test get_cache_statistics returns complete metrics."""
        mock_get_config.return_value = mock_config

        # Instead of side_effect, use return_value with a mock that handles chaining
        def create_query_mock():
            mock_query = Mock()

            # Setup default filter chain
            mock_filter = Mock()
            mock_filter.scalar = Mock()
            mock_query.filter = Mock(return_value=mock_filter)
            mock_query.scalar = Mock()

            return mock_query, mock_filter

        # Track calls to return correct values
        call_counter = [0]
        query_results = {
            0: 1000,  # total_docs
            1: 750,  # cached_docs
            2: 50,  # get_expired_count
            3: 750,  # get_cache_size_mb
            4: 750,  # is_over_limit -> get_cache_size_mb
        }

        def scalar_side_effect():
            result = query_results.get(call_counter[0], 0)
            call_counter[0] += 1
            return result

        mock_query, mock_filter = create_query_mock()
        mock_query.scalar.side_effect = scalar_side_effect
        mock_filter.scalar.side_effect = scalar_side_effect
        mock_session.query.return_value = mock_query

        monitor = CacheMonitor(mock_session)
        stats = monitor.get_cache_statistics()

        assert stats["total_documents"] == 1000
        assert stats["cached_documents"] == 750
        assert stats["cache_coverage"] == 0.75  # 750/1000
        assert stats["cache_size_mb"] > 0
        assert stats["max_size_mb"] == 1024
        assert stats["size_utilization"] > 0
        assert stats["is_over_limit"] is False
        assert stats["expired_entries"] == 50
        assert stats["ttl_days"] == 7

    @patch("src.embedding_cache.get_config")
    def test_get_cache_statistics_empty_database(
        self, mock_get_config, mock_session, mock_config
    ):
        """Test get_cache_statistics with empty database."""
        mock_get_config.return_value = mock_config

        # Mock all queries to return 0
        mock_query = Mock()
        mock_query.scalar.return_value = 0
        mock_filter = Mock()
        mock_filter.scalar.return_value = 0
        mock_query.filter.return_value = mock_filter

        mock_session.query.return_value = mock_query

        monitor = CacheMonitor(mock_session)
        stats = monitor.get_cache_statistics()

        assert stats["total_documents"] == 0
        assert stats["cached_documents"] == 0
        assert stats["cache_coverage"] == 0.0
        assert stats["cache_size_mb"] == 0.0
        assert stats["is_over_limit"] is False
        assert stats["expired_entries"] == 0


class TestMonitorCacheHealth:
    """Tests for monitor_cache_health() function."""

    def setup_query_mock(self, mock_session, query_results):
        """Helper to setup query mock with call counter."""
        call_counter = [0]

        def scalar_side_effect():
            result = query_results.get(call_counter[0], 0)
            call_counter[0] += 1
            return result

        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.scalar = Mock(side_effect=scalar_side_effect)
        mock_query.scalar = Mock(side_effect=scalar_side_effect)
        mock_query.filter = Mock(return_value=mock_filter)
        mock_session.query.return_value = mock_query

    @patch("src.embedding_cache.get_config")
    def test_healthy_cache_status(self, mock_get_config, mock_session, mock_config):
        """Test monitor_cache_health returns healthy status."""
        mock_get_config.return_value = mock_config

        self.setup_query_mock(
            mock_session,
            {
                0: 100,  # total_docs
                1: 80,  # cached_docs
                2: 0,  # get_expired_count
                3: 80,  # get_cache_size_mb
                4: 80,  # is_over_limit -> get_cache_size_mb
            },
        )

        result = monitor_cache_health(mock_session)

        assert result["status"] == "healthy"
        assert len(result["issues"]) == 0
        assert len(result["warnings"]) == 0
        assert len(result["recommendations"]) == 0

    @patch("src.embedding_cache.get_config")
    def test_warning_status_low_coverage(
        self, mock_get_config, mock_session, mock_config
    ):
        """Test monitor_cache_health warns on low cache coverage."""
        mock_get_config.return_value = mock_config

        self.setup_query_mock(
            mock_session,
            {
                0: 100,  # total_docs
                1: 30,  # cached_docs (low coverage)
                2: 0,  # get_expired_count
                3: 30,  # get_cache_size_mb
                4: 30,  # is_over_limit -> get_cache_size_mb
            },
        )

        result = monitor_cache_health(mock_session)

        assert result["status"] == "warning"
        assert len(result["warnings"]) == 1
        assert "Low cache coverage" in result["warnings"][0]
        assert "30.0%" in result["warnings"][0]

    @patch("src.embedding_cache.get_config")
    def test_warning_status_expired_entries(
        self, mock_get_config, mock_session, mock_config
    ):
        """Test monitor_cache_health warns on expired entries."""
        mock_get_config.return_value = mock_config

        self.setup_query_mock(
            mock_session,
            {
                0: 100,  # total_docs
                1: 80,  # cached_docs
                2: 20,  # get_expired_count (20 expired entries)
                3: 80,  # get_cache_size_mb
                4: 80,  # is_over_limit -> get_cache_size_mb
            },
        )

        result = monitor_cache_health(mock_session)

        assert result["status"] == "warning"
        assert len(result["warnings"]) == 1
        assert "20 expired entries" in result["warnings"][0]

    @patch("src.embedding_cache.get_config")
    def test_unhealthy_status_over_limit(
        self, mock_get_config, mock_session, mock_config
    ):
        """Test monitor_cache_health returns unhealthy when over limit."""
        mock_get_config.return_value = mock_config
        mock_config.vector_cache_max_size_mb = 10  # Small limit

        def create_mock_query(scalar_value):
            mock_query = Mock()
            mock_filter = Mock()
            mock_filter.scalar.return_value = scalar_value
            mock_query.scalar.return_value = scalar_value
            mock_query.filter.return_value = mock_filter
            return mock_query

        # Mock queries for over-limit cache (1000 docs = ~11.9 MB)
        mock_session.query.side_effect = [
            create_mock_query(1000),  # total_docs
            create_mock_query(1000),  # cached_docs
            create_mock_query(1000),  # get_cache_size_mb
            create_mock_query(0),  # get_expired_count
            create_mock_query(1000),  # is_over_limit -> get_cache_size_mb
        ]

        result = monitor_cache_health(mock_session)

        assert result["status"] == "unhealthy"
        assert len(result["issues"]) == 1
        assert "exceeds limit" in result["issues"][0]

    @patch("src.embedding_cache.get_config")
    def test_recommendations_cleanup_oldest(
        self, mock_get_config, mock_session, mock_config
    ):
        """Test monitor_cache_health recommends cleanup when over limit."""
        mock_get_config.return_value = mock_config
        mock_config.vector_cache_max_size_mb = 10

        def create_mock_query(scalar_value):
            mock_query = Mock()
            mock_filter = Mock()
            mock_filter.scalar.return_value = scalar_value
            mock_query.scalar.return_value = scalar_value
            mock_query.filter.return_value = mock_filter
            return mock_query

        # Mock queries for over-limit cache
        mock_session.query.side_effect = [
            create_mock_query(1000),  # total_docs
            create_mock_query(1000),  # cached_docs
            create_mock_query(1000),  # get_cache_size_mb
            create_mock_query(0),  # get_expired_count
            create_mock_query(1000),  # is_over_limit -> get_cache_size_mb
        ]

        result = monitor_cache_health(mock_session)

        assert len(result["recommendations"]) >= 1
        assert any("cleanup_oldest_entries" in rec for rec in result["recommendations"])

    @patch("src.embedding_cache.get_config")
    def test_recommendations_cleanup_expired(
        self, mock_get_config, mock_session, mock_config
    ):
        """Test monitor_cache_health recommends cleanup expired entries."""
        mock_get_config.return_value = mock_config

        def create_mock_query(scalar_value):
            mock_query = Mock()
            mock_filter = Mock()
            mock_filter.scalar.return_value = scalar_value
            mock_query.scalar.return_value = scalar_value
            mock_query.filter.return_value = mock_filter
            return mock_query

        # Mock queries with many expired entries (>10)
        mock_session.query.side_effect = [
            create_mock_query(100),  # total_docs
            create_mock_query(80),  # cached_docs
            create_mock_query(80),  # get_cache_size_mb
            create_mock_query(25),  # get_expired_count (>10 threshold)
            create_mock_query(80),  # is_over_limit -> get_cache_size_mb
        ]

        result = monitor_cache_health(mock_session)

        assert len(result["recommendations"]) >= 1
        assert any(
            "cleanup_expired_entries" in rec for rec in result["recommendations"]
        )

    @patch("src.embedding_cache.get_config")
    def test_multiple_warnings_and_recommendations(
        self, mock_get_config, mock_session, mock_config
    ):
        """Test monitor_cache_health with multiple issues."""
        mock_get_config.return_value = mock_config
        mock_config.vector_cache_max_size_mb = 10

        def create_mock_query(scalar_value):
            mock_query = Mock()
            mock_filter = Mock()
            mock_filter.scalar.return_value = scalar_value
            mock_query.scalar.return_value = scalar_value
            mock_query.filter.return_value = mock_filter
            return mock_query

        # Mock queries for over-limit cache with expired entries
        mock_session.query.side_effect = [
            create_mock_query(1000),  # total_docs
            create_mock_query(1000),  # cached_docs
            create_mock_query(1000),  # get_cache_size_mb
            create_mock_query(50),  # get_expired_count
            create_mock_query(1000),  # is_over_limit -> get_cache_size_mb
        ]

        result = monitor_cache_health(mock_session)

        assert result["status"] == "unhealthy"
        assert len(result["issues"]) >= 1
        assert len(result["warnings"]) >= 1
        assert len(result["recommendations"]) >= 2

    @patch("src.embedding_cache.get_config")
    def test_statistics_included_in_result(
        self, mock_get_config, mock_session, mock_config
    ):
        """Test monitor_cache_health includes full statistics."""
        mock_get_config.return_value = mock_config

        self.setup_query_mock(
            mock_session,
            {
                0: 100,  # total_docs
                1: 75,  # cached_docs
                2: 5,  # get_expired_count
                3: 75,  # get_cache_size_mb
                4: 75,  # is_over_limit -> get_cache_size_mb
            },
        )

        result = monitor_cache_health(mock_session)

        assert "statistics" in result
        stats = result["statistics"]
        assert stats["total_documents"] == 100
        assert stats["cached_documents"] == 75
        assert stats["cache_coverage"] == 0.75
        assert stats["expired_entries"] == 5
