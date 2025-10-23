"""
Unit tests for embedding generation and caching.

Tests cover:
- Text extraction from document metadata
- Embedding generation via OpenAI API
- In-memory LRU cache operations (Tier 1)
- Database cache operations (Tier 2)
- 3-tier cache workflow (memory → DB → API)
- Batch embedding generation
- Cache key computation
- Cache invalidation (text, model, TTL)
- Error handling
- Cache statistics

Target: 95%+ code coverage
"""

import pytest
from unittest.mock import Mock, patch
from typing import List
from datetime import datetime, timezone, timedelta

from src.embeddings import (
    EmbeddingGenerator,
    EmbeddingResult,
    EMBEDDING_MODEL,
    EMBEDDING_DIMENSIONS,
    MAX_BATCH_SIZE,
)
from src.models import Document


# === Mock OpenAI Response ===


class MockEmbeddingData:
    """Mock OpenAI embedding data item."""

    def __init__(self, embedding: List[float]):
        self.embedding = embedding


class MockEmbeddingUsage:
    """Mock OpenAI embedding usage."""

    def __init__(self, total_tokens: int):
        self.total_tokens = total_tokens


class MockEmbeddingResponse:
    """Mock OpenAI embeddings.create() response."""

    def __init__(self, embeddings: List[List[float]], total_tokens: int = 100):
        self.data = [MockEmbeddingData(emb) for emb in embeddings]
        self.usage = MockEmbeddingUsage(total_tokens)


# === Fixtures ===


@pytest.fixture
def mock_client():
    """Create mock OpenAI client."""
    client = Mock()
    client.embeddings = Mock()
    client.embeddings.create = Mock()
    return client


@pytest.fixture
def generator(mock_client):
    """Create EmbeddingGenerator instance with mock client."""
    return EmbeddingGenerator(
        client=mock_client,
        model=EMBEDDING_MODEL,
        dimensions=EMBEDDING_DIMENSIONS,
        max_cache_size=10,  # Small cache for testing LRU
    )


@pytest.fixture
def sample_document():
    """Create a sample document with metadata."""
    doc = Document(
        id=1,
        sha256_hex="a" * 64,
        original_filename="invoice.pdf",
        metadata_json={
            "doc_type": "Invoice",
            "issuer": "ACME Corp",
            "summary": "Monthly service invoice for consulting",
        },
        status="completed",
    )
    return doc


@pytest.fixture
def sample_embedding():
    """Create a sample 1536-dimension embedding vector."""
    return [0.1] * EMBEDDING_DIMENSIONS


@pytest.fixture
def mock_session():
    """Create mock SQLAlchemy session."""
    session = Mock()
    session.commit = Mock()
    return session


@pytest.fixture
def generator_with_db(mock_client, mock_session):
    """Create EmbeddingGenerator with database session."""
    return EmbeddingGenerator(
        client=mock_client,
        session=mock_session,
        model=EMBEDDING_MODEL,
        dimensions=EMBEDDING_DIMENSIONS,
        max_cache_size=10,
    )


@pytest.fixture
def mock_config():
    """Create mock configuration with TTL settings."""
    config = Mock()
    config.vector_cache_ttl_days = 7
    return config


# === Test Cases ===


class TestEmbeddingGenerator:
    """Tests for EmbeddingGenerator class."""

    def test_initialization(self, mock_client):
        """Test generator initialization with default parameters."""
        gen = EmbeddingGenerator(client=mock_client)

        assert gen.client == mock_client
        assert gen.session is None
        assert gen.model == EMBEDDING_MODEL
        assert gen.dimensions == EMBEDDING_DIMENSIONS
        assert gen.max_cache_size == 1000  # Default
        # Cache is now LRUCache object, check metrics instead
        cache_metrics = gen._cache.get_metrics()
        assert cache_metrics["entries"] == 0
        assert cache_metrics["hits"] == 0
        assert gen.db_cache_hits == 0
        assert gen.api_calls == 0
        assert gen.total_tokens == 0

    def test_initialization_custom_params(self, mock_client):
        """Test generator initialization with custom parameters."""
        gen = EmbeddingGenerator(
            client=mock_client,
            model="custom-model",
            dimensions=512,
            max_cache_size=100,
        )

        assert gen.model == "custom-model"
        assert gen.dimensions == 512
        assert gen.max_cache_size == 100

    def test_extract_text_success(self, generator, sample_document):
        """Test text extraction from document metadata."""
        text = generator.extract_text(sample_document)

        # Should combine filename, doc_type, issuer, summary
        assert "invoice.pdf" in text
        assert "Invoice" in text
        assert "ACME Corp" in text
        assert "Monthly service invoice for consulting" in text

    def test_extract_text_no_metadata(self, generator):
        """Test text extraction fails for document without metadata."""
        doc = Document(
            id=1,
            sha256_hex="a" * 64,
            original_filename="test.pdf",
            metadata_json=None,
            status="pending",
        )

        with pytest.raises(ValueError) as exc_info:
            generator.extract_text(doc)

        assert "has no metadata" in str(exc_info.value)
        assert "Must be processed" in str(exc_info.value)

    def test_extract_text_empty_metadata(self, generator):
        """Test text extraction works with empty metadata fields."""
        doc = Document(
            id=1,
            sha256_hex="a" * 64,
            original_filename="test.pdf",
            metadata_json={},
            status="completed",
        )

        text = generator.extract_text(doc)

        # Should at least have filename
        assert "test.pdf" in text

    def test_extract_text_partial_metadata(self, generator):
        """Test text extraction works with partial metadata fields."""
        doc = Document(
            id=1,
            sha256_hex="a" * 64,
            original_filename="report.pdf",
            metadata_json={
                "doc_type": "Report",
                # Missing issuer and summary
            },
            status="completed",
        )

        text = generator.extract_text(doc)

        assert "report.pdf" in text
        assert "Report" in text

    def test_compute_cache_key_deterministic(self, generator):
        """Test cache key computation is deterministic."""
        text = "test document text"

        key1 = generator._compute_cache_key(text)
        key2 = generator._compute_cache_key(text)

        assert key1 == key2
        assert len(key1) == 16  # From generate_cache_key() - 16-char hex

    def test_compute_cache_key_includes_model(self, generator):
        """Test cache key includes model name for model upgrades."""
        text = "test document text"

        # Change model
        generator.model = "model-v1"
        key1 = generator._compute_cache_key(text)

        generator.model = "model-v2"
        key2 = generator._compute_cache_key(text)

        # Keys should differ because model changed
        assert key1 != key2

    def test_cache_miss(self, generator):
        """Test cache miss returns None."""
        result = generator._get_from_cache("nonexistent_key")

        assert result is None
        # Cache misses are tracked implicitly via api_calls, not _get_from_cache

    def test_cache_hit(self, generator, sample_embedding):
        """Test cache hit returns cached result and updates LRU."""
        cache_key = "test_key"
        cached_result = EmbeddingResult(
            embedding=sample_embedding,
            model=EMBEDDING_MODEL,
            dimensions=EMBEDDING_DIMENSIONS,
            input_tokens=100,
            cache_key=cache_key,
        )

        # Add to cache
        generator._add_to_cache(cache_key, cached_result)

        # Retrieve from cache
        result = generator._get_from_cache(cache_key)

        assert result is not None
        assert result.embedding == sample_embedding
        assert result.cached is True
        # Memory cache hits tracked by LRUCache
        assert generator._cache.get_metrics()["hits"] == 1

    def test_cache_lru_eviction(self, generator, sample_embedding):
        """Test LRU eviction when cache is full."""
        # Fill cache to max (10 items)
        for i in range(10):
            key = f"key_{i}"
            result = EmbeddingResult(
                embedding=sample_embedding,
                model=EMBEDDING_MODEL,
                dimensions=EMBEDDING_DIMENSIONS,
                input_tokens=100,
                cache_key=key,
            )
            generator._add_to_cache(key, result)

        # Check cache is at max capacity
        assert generator._cache.get_metrics()["entries"] == 10
        assert generator._cache.get("key_0") is not None  # Oldest entry present

        # Add one more - should evict oldest (key_0)
        new_key = "key_new"
        new_result = EmbeddingResult(
            embedding=sample_embedding,
            model=EMBEDDING_MODEL,
            dimensions=EMBEDDING_DIMENSIONS,
            input_tokens=100,
            cache_key=new_key,
        )
        generator._add_to_cache(new_key, new_result)

        # Cache should still be at max, oldest evicted
        assert generator._cache.get_metrics()["entries"] == 10
        assert generator._cache.get_metrics()["evictions"] >= 1
        assert generator._cache.get("key_0") is None  # Evicted
        assert generator._cache.get(new_key) is not None  # Present

    def test_cache_lru_update_on_access(self, generator, sample_embedding):
        """Test accessing cache updates LRU order."""
        # Fill cache to max capacity (10 items)
        for i in range(10):
            key = f"key_{i}"
            result = EmbeddingResult(
                embedding=sample_embedding,
                model=EMBEDDING_MODEL,
                dimensions=EMBEDDING_DIMENSIONS,
                input_tokens=100,
                cache_key=key,
            )
            generator._add_to_cache(key, result)

        # Access key_0 to move it to end of LRU order (mark as recently used)
        generator._get_from_cache("key_0")

        # Add one more item - should evict key_1 (now oldest), not key_0
        new_key = "key_new"
        new_result = EmbeddingResult(
            embedding=sample_embedding,
            model=EMBEDDING_MODEL,
            dimensions=EMBEDDING_DIMENSIONS,
            input_tokens=100,
            cache_key=new_key,
        )
        generator._add_to_cache(new_key, new_result)

        # key_0 should NOT be evicted because we accessed it recently
        assert generator._cache.get("key_0") is not None
        # key_1 should be evicted (was oldest after key_0 access)
        assert generator._cache.get("key_1") is None

    def test_generate_embedding_success(
        self, generator, sample_document, sample_embedding
    ):
        """Test successful embedding generation."""
        # Mock API response
        generator.client.embeddings.create.return_value = MockEmbeddingResponse(
            embeddings=[sample_embedding],
            total_tokens=500,
        )

        result = generator.generate_embedding(sample_document)

        assert result.embedding == sample_embedding
        assert result.model == EMBEDDING_MODEL
        assert result.dimensions == EMBEDDING_DIMENSIONS
        assert result.cached is False
        assert result.cache_key is not None
        assert generator.total_tokens == 500

        # Verify API was called
        generator.client.embeddings.create.assert_called_once()
        call_args = generator.client.embeddings.create.call_args[1]
        assert call_args["model"] == EMBEDDING_MODEL
        assert call_args["dimensions"] == EMBEDDING_DIMENSIONS
        assert len(call_args["input"]) == 1

    def test_generate_embedding_uses_cache_on_second_call(
        self, generator, sample_document, sample_embedding
    ):
        """Test second call uses cache instead of API."""
        # Mock API response for first call
        generator.client.embeddings.create.return_value = MockEmbeddingResponse(
            embeddings=[sample_embedding],
            total_tokens=500,
        )

        # First call - should hit API
        result1 = generator.generate_embedding(sample_document)
        assert result1.cached is False
        assert generator.api_calls == 1

        # Second call - should hit cache
        result2 = generator.generate_embedding(sample_document)
        assert result2.cached is True
        assert result2.embedding == sample_embedding
        assert generator._cache.get_metrics()["hits"] == 1

        # API should only be called once
        assert generator.client.embeddings.create.call_count == 1

    def test_batch_generate_embeddings_all_cache_misses(
        self, generator, sample_embedding
    ):
        """Test batch generation with all cache misses."""
        # Create 3 documents
        docs = [
            Document(
                id=i,
                sha256_hex=f"{i:064d}",
                original_filename=f"doc{i}.pdf",
                metadata_json={
                    "doc_type": "Invoice",
                    "issuer": f"Company {i}",
                    "summary": f"Document {i}",
                },
                status="completed",
            )
            for i in range(3)
        ]

        # Mock API response (3 embeddings)
        generator.client.embeddings.create.return_value = MockEmbeddingResponse(
            embeddings=[sample_embedding] * 3,
            total_tokens=1500,
        )

        results = generator.batch_generate_embeddings(docs)

        assert len(results) == 3
        assert all(r.embedding == sample_embedding for r in results)
        assert all(r.cached is False for r in results)
        assert generator.api_calls == 3

        # API should be called once for batch
        generator.client.embeddings.create.assert_called_once()

    def test_batch_generate_embeddings_partial_cache_hits(
        self, generator, sample_embedding
    ):
        """Test batch generation with some cached embeddings."""
        # Create 3 documents
        docs = [
            Document(
                id=i,
                sha256_hex=f"{i:064d}",
                original_filename=f"doc{i}.pdf",
                metadata_json={
                    "doc_type": "Invoice",
                    "issuer": f"Company {i}",
                    "summary": f"Document {i}",
                },
                status="completed",
            )
            for i in range(3)
        ]

        # Pre-cache first document
        text0 = generator.extract_text(docs[0])
        cache_key0 = generator._compute_cache_key(text0)
        cached_result = EmbeddingResult(
            embedding=sample_embedding,
            model=EMBEDDING_MODEL,
            dimensions=EMBEDDING_DIMENSIONS,
            input_tokens=100,
            cache_key=cache_key0,
        )
        generator._add_to_cache(cache_key0, cached_result)

        # Mock API response for remaining 2 documents
        generator.client.embeddings.create.return_value = MockEmbeddingResponse(
            embeddings=[sample_embedding] * 2,
            total_tokens=1000,
        )

        results = generator.batch_generate_embeddings(docs)

        assert len(results) == 3
        assert all(r.embedding == sample_embedding for r in results)
        assert generator._cache.get_metrics()["hits"] == 1  # First doc cached
        assert generator.api_calls == 2  # Other 2 docs

        # API should be called once for 2 uncached docs
        generator.client.embeddings.create.assert_called_once()

    def test_batch_generate_embeddings_empty_list(self, generator):
        """Test batch generation with empty document list."""
        results = generator.batch_generate_embeddings([])

        assert results == []
        generator.client.embeddings.create.assert_not_called()

    def test_batch_generate_embeddings_respects_max_batch_size(
        self, generator, sample_embedding
    ):
        """Test batch generation splits large batches."""
        # Create MAX_BATCH_SIZE + 10 documents
        num_docs = MAX_BATCH_SIZE + 10
        docs = [
            Document(
                id=i,
                sha256_hex=f"{i:064d}",
                original_filename=f"doc{i}.pdf",
                metadata_json={
                    "doc_type": "Invoice",
                    "issuer": f"Company {i}",
                    "summary": f"Document {i}",
                },
                status="completed",
            )
            for i in range(num_docs)
        ]

        # Mock API responses
        def create_response(*args, **kwargs):
            input_count = len(kwargs["input"])
            return MockEmbeddingResponse(
                embeddings=[sample_embedding] * input_count,
                total_tokens=input_count * 100,
            )

        generator.client.embeddings.create.side_effect = create_response

        results = generator.batch_generate_embeddings(docs)

        assert len(results) == num_docs

        # Should split into 2 API calls (100 + 10)
        assert generator.client.embeddings.create.call_count == 2

    def test_get_cache_stats_legacy(self, generator, sample_embedding):
        """Test cache statistics reporting with production cache."""
        # Generate some cache activity
        cache_key = "test_key"
        result = EmbeddingResult(
            embedding=sample_embedding,
            model=EMBEDDING_MODEL,
            dimensions=EMBEDDING_DIMENSIONS,
            input_tokens=100,
            cache_key=cache_key,
        )
        generator._add_to_cache(cache_key, result)
        generator._get_from_cache(cache_key)  # Hit
        # Add an API call to simulate a miss
        generator.api_calls = 1

        stats = generator.get_cache_stats()

        # Check structure includes production cache metrics
        assert "cache_metrics" in stats
        assert stats["cache_metrics"]["entries"] == 1
        assert stats["cache_metrics"]["hits"] == 1
        assert stats["total_cache_hits"] == 1  # memory + db
        assert stats["api_calls"] == 1
        assert stats["overall_hit_rate"] == 0.5  # 1 hit / 2 requests
        assert stats["total_tokens"] == 0  # No tokens tracked

    def test_get_cache_stats_empty_cache_legacy(self, generator):
        """Test cache stats with no cache activity."""
        stats = generator.get_cache_stats()

        assert "cache_metrics" in stats
        assert stats["cache_metrics"]["entries"] == 0
        assert stats["cache_metrics"]["hits"] == 0
        assert stats["db_cache_hits"] == 0
        assert stats["overall_hit_rate"] == 0.0

    def test_clear_cache_legacy(self, generator, sample_embedding):
        """Test cache clearing resets state (legacy test updated)."""
        # Add some cached data
        for i in range(5):
            key = f"key_{i}"
            result = EmbeddingResult(
                embedding=sample_embedding,
                model=EMBEDDING_MODEL,
                dimensions=EMBEDDING_DIMENSIONS,
                input_tokens=100,
                cache_key=key,
            )
            generator._add_to_cache(key, result)
            generator._get_from_cache(key)  # Create hits

        generator.total_tokens = 1000

        # Clear cache
        generator.clear_cache()

        # Check production cache is cleared
        assert generator._cache.get_metrics()["entries"] == 0
        assert generator._cache.get_metrics()["hits"] == 0
        # EmbeddingGenerator stats reset
        assert generator.db_cache_hits == 0
        assert generator.api_calls == 0
        assert generator.total_tokens == 0


class TestEmbeddingResult:
    """Tests for EmbeddingResult dataclass."""

    def test_embedding_result_creation(self):
        """Test creating EmbeddingResult instance."""
        embedding = [0.1] * EMBEDDING_DIMENSIONS
        result = EmbeddingResult(
            embedding=embedding,
            model="test-model",
            dimensions=1536,
            input_tokens=500,
            cached=True,
            cache_key="abc123",
        )

        assert result.embedding == embedding
        assert result.model == "test-model"
        assert result.dimensions == 1536
        assert result.input_tokens == 500
        assert result.cached is True
        assert result.cache_key == "abc123"

    def test_embedding_result_defaults(self):
        """Test EmbeddingResult default values."""
        embedding = [0.1] * EMBEDDING_DIMENSIONS
        result = EmbeddingResult(
            embedding=embedding,
            model="test-model",
            dimensions=1536,
            input_tokens=500,
        )

        assert result.cached is False  # Default
        assert result.cache_key is None  # Default


class TestDatabaseCache:
    """Tests for database cache (Tier 2) functionality."""

    def test_initialization_with_session(self, mock_client, mock_session):
        """Test generator initialization with database session."""
        gen = EmbeddingGenerator(client=mock_client, session=mock_session)

        assert gen.session == mock_session
        assert gen.db_cache_hits == 0

    def test_db_cache_miss_no_embedding_vector(
        self, generator_with_db, sample_document
    ):
        """Test DB cache miss when document has no embedding_vector."""
        sample_document.embedding_vector = None

        result = generator_with_db._get_from_db_cache(sample_document)

        assert result is None

    def test_db_cache_miss_no_session(
        self, generator, sample_document, sample_embedding
    ):
        """Test DB cache miss when generator has no session."""
        # Setup document with embedding
        sample_document.embedding_vector = sample_embedding
        sample_document.embedding_cache_key = "test_key"
        sample_document.embedding_model = EMBEDDING_MODEL

        result = generator._get_from_db_cache(sample_document)

        assert result is None

    def test_db_cache_miss_cache_key_mismatch(
        self, generator_with_db, sample_document, sample_embedding
    ):
        """Test DB cache miss when cache key doesn't match current text."""
        # Setup document with embedding but wrong cache key
        sample_document.embedding_vector = sample_embedding
        sample_document.embedding_cache_key = "wrong_key"
        sample_document.embedding_model = EMBEDDING_MODEL

        result = generator_with_db._get_from_db_cache(sample_document)

        assert result is None

    def test_db_cache_miss_model_mismatch(
        self, generator_with_db, sample_document, sample_embedding
    ):
        """Test DB cache miss when model doesn't match."""
        # Compute correct cache key
        text = generator_with_db.extract_text(sample_document)
        cache_key = generator_with_db._compute_cache_key(text)

        # Setup document with embedding but wrong model
        sample_document.embedding_vector = sample_embedding
        sample_document.embedding_cache_key = cache_key
        sample_document.embedding_model = "wrong-model"

        result = generator_with_db._get_from_db_cache(sample_document)

        assert result is None

    @patch("src.config.get_config")
    def test_db_cache_miss_ttl_expired(
        self,
        mock_get_config,
        generator_with_db,
        sample_document,
        sample_embedding,
        mock_config,
    ):
        """Test DB cache miss when TTL has expired."""
        mock_get_config.return_value = mock_config

        # Compute correct cache key
        text = generator_with_db.extract_text(sample_document)
        cache_key = generator_with_db._compute_cache_key(text)

        # Setup document with expired embedding (8 days old, TTL is 7 days)
        sample_document.embedding_vector = sample_embedding
        sample_document.embedding_cache_key = cache_key
        sample_document.embedding_model = EMBEDDING_MODEL
        sample_document.embedding_generated_at = datetime.now(timezone.utc) - timedelta(
            days=8
        )

        result = generator_with_db._get_from_db_cache(sample_document)

        assert result is None

    @patch("src.config.get_config")
    def test_db_cache_hit_valid_cache(
        self,
        mock_get_config,
        generator_with_db,
        sample_document,
        sample_embedding,
        mock_config,
    ):
        """Test DB cache hit with valid cached embedding."""
        mock_get_config.return_value = mock_config

        # Compute correct cache key
        text = generator_with_db.extract_text(sample_document)
        cache_key = generator_with_db._compute_cache_key(text)

        # Setup document with valid embedding (2 days old, TTL is 7 days)
        sample_document.embedding_vector = sample_embedding
        sample_document.embedding_cache_key = cache_key
        sample_document.embedding_model = EMBEDDING_MODEL
        sample_document.embedding_generated_at = datetime.now(timezone.utc) - timedelta(
            days=2
        )

        result = generator_with_db._get_from_db_cache(sample_document)

        assert result is not None
        assert result.embedding == sample_embedding
        assert result.model == EMBEDDING_MODEL
        assert result.dimensions == len(sample_embedding)
        assert result.cached is True
        assert result.cache_key == cache_key

    def test_db_cache_hit_no_ttl_field(
        self, generator_with_db, sample_document, sample_embedding
    ):
        """Test DB cache hit when embedding_generated_at is None (no TTL check)."""
        # Compute correct cache key
        text = generator_with_db.extract_text(sample_document)
        cache_key = generator_with_db._compute_cache_key(text)

        # Setup document with valid embedding but no timestamp
        sample_document.embedding_vector = sample_embedding
        sample_document.embedding_cache_key = cache_key
        sample_document.embedding_model = EMBEDDING_MODEL
        sample_document.embedding_generated_at = None

        result = generator_with_db._get_from_db_cache(sample_document)

        assert result is not None
        assert result.cached is True

    def test_save_to_db_cache_no_session(
        self, generator, sample_document, sample_embedding
    ):
        """Test save to DB cache when no session is available."""
        result = EmbeddingResult(
            embedding=sample_embedding,
            model=EMBEDDING_MODEL,
            dimensions=EMBEDDING_DIMENSIONS,
            input_tokens=100,
            cache_key="test_key",
        )

        # Should not raise, just return early
        generator._save_to_db_cache(sample_document, result)

    def test_save_to_db_cache_success(
        self, generator_with_db, mock_session, sample_document, sample_embedding
    ):
        """Test successful save to database cache."""
        result = EmbeddingResult(
            embedding=sample_embedding,
            model=EMBEDDING_MODEL,
            dimensions=EMBEDDING_DIMENSIONS,
            input_tokens=100,
            cache_key="test_key",
        )

        generator_with_db._save_to_db_cache(sample_document, result)

        # Verify document was updated
        assert sample_document.embedding_vector == sample_embedding
        assert sample_document.embedding_cache_key == "test_key"
        assert sample_document.embedding_model == EMBEDDING_MODEL
        assert sample_document.embedding_generated_at is not None

        # Verify session commit was called
        mock_session.commit.assert_called_once()

    @patch("src.config.get_config")
    def test_three_tier_cache_memory_hit(
        self, mock_get_config, generator_with_db, sample_document, sample_embedding
    ):
        """Test 3-tier cache: Tier 1 (memory) hit."""
        # Pre-populate memory cache
        text = generator_with_db.extract_text(sample_document)
        cache_key = generator_with_db._compute_cache_key(text)
        cached_result = EmbeddingResult(
            embedding=sample_embedding,
            model=EMBEDDING_MODEL,
            dimensions=EMBEDDING_DIMENSIONS,
            input_tokens=100,
            cache_key=cache_key,
        )
        generator_with_db._add_to_cache(cache_key, cached_result)

        # Mock API to verify it's not called
        generator_with_db.client.embeddings.create = Mock()

        result = generator_with_db.generate_embedding(sample_document)

        assert result.embedding == sample_embedding
        assert result.cached is True
        assert generator_with_db.memory_cache_hits == 1
        assert generator_with_db.db_cache_hits == 0
        assert generator_with_db.api_calls == 0

        # API should not be called
        generator_with_db.client.embeddings.create.assert_not_called()

    @patch("src.config.get_config")
    def test_three_tier_cache_db_hit_promotes_to_memory(
        self,
        mock_get_config,
        generator_with_db,
        sample_document,
        sample_embedding,
        mock_config,
    ):
        """Test 3-tier cache: Tier 2 (DB) hit promotes to Tier 1 (memory)."""
        mock_get_config.return_value = mock_config

        # Setup document with DB cached embedding
        text = generator_with_db.extract_text(sample_document)
        cache_key = generator_with_db._compute_cache_key(text)
        sample_document.embedding_vector = sample_embedding
        sample_document.embedding_cache_key = cache_key
        sample_document.embedding_model = EMBEDDING_MODEL
        sample_document.embedding_generated_at = datetime.now(timezone.utc)

        # Mock API to verify it's not called
        generator_with_db.client.embeddings.create = Mock()

        result = generator_with_db.generate_embedding(sample_document)

        assert result.embedding == sample_embedding
        assert result.cached is True
        assert generator_with_db.memory_cache_hits == 0
        assert generator_with_db.db_cache_hits == 1
        assert generator_with_db.api_calls == 0

        # Verify promoted to memory cache
        assert cache_key in generator_with_db._cache

        # API should not be called
        generator_with_db.client.embeddings.create.assert_not_called()

    def test_three_tier_cache_api_call_caches_both_tiers(
        self, generator_with_db, mock_session, sample_document, sample_embedding
    ):
        """Test 3-tier cache: Tier 3 (API) call caches in both tiers."""
        # Mock API response
        generator_with_db.client.embeddings.create.return_value = MockEmbeddingResponse(
            embeddings=[sample_embedding],
            total_tokens=500,
        )

        result = generator_with_db.generate_embedding(sample_document)

        assert result.embedding == sample_embedding
        assert result.cached is False
        assert generator_with_db.memory_cache_hits == 0
        assert generator_with_db.db_cache_hits == 0
        assert generator_with_db.api_calls == 1

        # Verify cached in memory
        text = generator_with_db.extract_text(sample_document)
        cache_key = generator_with_db._compute_cache_key(text)
        assert cache_key in generator_with_db._cache

        # Verify saved to database
        assert sample_document.embedding_vector == sample_embedding
        assert sample_document.embedding_cache_key == cache_key
        mock_session.commit.assert_called_once()

    @patch("src.config.get_config")
    def test_batch_generate_with_db_cache_hits(
        self, mock_get_config, generator_with_db, sample_embedding, mock_config
    ):
        """Test batch generation with DB cache hits."""
        mock_get_config.return_value = mock_config

        # Create 3 documents
        docs = [
            Document(
                id=i,
                sha256_hex=f"{i:064d}",
                original_filename=f"doc{i}.pdf",
                metadata_json={
                    "doc_type": "Invoice",
                    "issuer": f"Company {i}",
                    "summary": f"Document {i}",
                },
                status="completed",
            )
            for i in range(3)
        ]

        # Pre-cache first doc in DB
        text0 = generator_with_db.extract_text(docs[0])
        cache_key0 = generator_with_db._compute_cache_key(text0)
        docs[0].embedding_vector = sample_embedding
        docs[0].embedding_cache_key = cache_key0
        docs[0].embedding_model = EMBEDDING_MODEL
        docs[0].embedding_generated_at = datetime.now(timezone.utc)

        # Mock API for remaining 2 docs
        generator_with_db.client.embeddings.create.return_value = MockEmbeddingResponse(
            embeddings=[sample_embedding] * 2,
            total_tokens=1000,
        )

        results = generator_with_db.batch_generate_embeddings(docs)

        assert len(results) == 3
        assert generator_with_db.db_cache_hits == 1
        assert generator_with_db.api_calls == 2


class TestCacheStatistics:
    """Tests for 3-tier cache statistics."""

    def test_get_cache_stats_empty(self, generator):
        """Test cache stats with no activity."""
        stats = generator.get_cache_stats()

        assert stats["cache_size"] == 0
        assert stats["max_cache_size"] == 10
        assert stats["memory_cache_hits"] == 0
        assert stats["db_cache_hits"] == 0
        assert stats["total_cache_hits"] == 0
        assert stats["api_calls"] == 0
        assert stats["total_requests"] == 0
        assert stats["memory_hit_rate"] == 0.0
        assert stats["overall_hit_rate"] == 0.0
        assert stats["total_tokens"] == 0

    def test_get_cache_stats_memory_only(self, generator, sample_embedding):
        """Test cache stats with only memory cache hits."""
        # Create some memory cache activity
        for i in range(3):
            key = f"key_{i}"
            result = EmbeddingResult(
                embedding=sample_embedding,
                model=EMBEDDING_MODEL,
                dimensions=EMBEDDING_DIMENSIONS,
                input_tokens=100,
                cache_key=key,
            )
            generator._add_to_cache(key, result)
            generator._get_from_cache(key)  # Hit

        stats = generator.get_cache_stats()

        assert stats["cache_size"] == 3
        assert stats["memory_cache_hits"] == 3
        assert stats["db_cache_hits"] == 0
        assert stats["total_cache_hits"] == 3
        assert stats["api_calls"] == 0
        assert stats["total_requests"] == 3
        assert stats["memory_hit_rate"] == 1.0
        assert stats["overall_hit_rate"] == 1.0

    def test_get_cache_stats_with_db_hits(self, generator_with_db):
        """Test cache stats with DB cache hits."""
        generator_with_db.memory_cache_hits = 5
        generator_with_db.db_cache_hits = 3
        generator_with_db.api_calls = 2

        stats = generator_with_db.get_cache_stats()

        assert stats["memory_cache_hits"] == 5
        assert stats["db_cache_hits"] == 3
        assert stats["total_cache_hits"] == 8
        assert stats["api_calls"] == 2
        assert stats["total_requests"] == 10
        assert stats["memory_hit_rate"] == 0.5  # 5/10
        assert stats["overall_hit_rate"] == 0.8  # 8/10

    def test_get_cache_stats_with_api_calls_only(self, generator):
        """Test cache stats with only API calls (no cache hits)."""
        generator.api_calls = 10
        generator.total_tokens = 5000

        stats = generator.get_cache_stats()

        assert stats["memory_cache_hits"] == 0
        assert stats["db_cache_hits"] == 0
        assert stats["total_cache_hits"] == 0
        assert stats["api_calls"] == 10
        assert stats["total_requests"] == 10
        assert stats["memory_hit_rate"] == 0.0
        assert stats["overall_hit_rate"] == 0.0
        assert stats["total_tokens"] == 5000

    def test_clear_cache_resets_all_statistics(
        self, generator_with_db, sample_embedding
    ):
        """Test clear_cache resets all statistics."""
        # Create some cache activity
        for i in range(5):
            key = f"key_{i}"
            result = EmbeddingResult(
                embedding=sample_embedding,
                model=EMBEDDING_MODEL,
                dimensions=EMBEDDING_DIMENSIONS,
                input_tokens=100,
                cache_key=key,
            )
            generator_with_db._add_to_cache(key, result)

        generator_with_db.memory_cache_hits = 10
        generator_with_db.db_cache_hits = 5
        generator_with_db.api_calls = 3
        generator_with_db.total_tokens = 1500

        # Clear cache
        generator_with_db.clear_cache()

        assert generator_with_db._cache == {}
        assert generator_with_db._cache_order == []
        assert generator_with_db.memory_cache_hits == 0
        assert generator_with_db.db_cache_hits == 0
        assert generator_with_db.api_calls == 0
        assert generator_with_db.total_tokens == 0

    def test_clear_cache_does_not_affect_db_cache(
        self, generator_with_db, sample_document, sample_embedding
    ):
        """Test clear_cache only clears memory, not database cache."""
        # Setup document with DB cached embedding
        text = generator_with_db.extract_text(sample_document)
        cache_key = generator_with_db._compute_cache_key(text)
        sample_document.embedding_vector = sample_embedding
        sample_document.embedding_cache_key = cache_key
        sample_document.embedding_model = EMBEDDING_MODEL

        # Clear memory cache
        generator_with_db.clear_cache()

        # DB cache should still be intact
        assert sample_document.embedding_vector == sample_embedding
        assert sample_document.embedding_cache_key == cache_key
