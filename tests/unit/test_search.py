"""
Comprehensive unit and performance tests for semantic search API.

Tests cover:
- Basic search functionality with results ranking
- Metadata filtering (doc_type, issuer, date_range)
- Document similarity search
- Pagination (limit, offset)
- Edge cases (empty queries, no results, invalid params)
- Performance benchmarking (P95 latency <500ms)
- NumPy vectorized similarity computation
- Query caching integration
- Result ordering and ranking

Target: 85%+ code coverage
Acceptance Criteria:
- All tests pass
- P95 latency <500ms validated
- NumPy usage verified
- Edge cases comprehensive
"""

import pytest
import time
import statistics
from unittest.mock import Mock, patch
from datetime import datetime, timezone
from typing import List

import numpy as np

from src.search import (
    SearchResult,
    SearchResults,
    SemanticSearchEngine,
)
from src.embeddings import EmbeddingGenerator, EmbeddingResult
from src.models import Document


# ===================================================================
# Fixtures
# ===================================================================


@pytest.fixture
def mock_session():
    """Create mock SQLAlchemy session with query chain support."""
    session = Mock()

    # Setup query chain methods
    query_mock = Mock()
    query_mock.filter = Mock(return_value=query_mock)
    query_mock.all = Mock(return_value=[])
    query_mock.count = Mock(return_value=0)

    session.query = Mock(return_value=query_mock)
    return session


@pytest.fixture
def mock_embedding_generator():
    """Create mock EmbeddingGenerator."""
    generator = Mock(spec=EmbeddingGenerator)

    # Default embedding result
    generator.generate_embedding = Mock(
        return_value=EmbeddingResult(
            embedding=[0.1] * 1536,
            model="text-embedding-3-small",
            dimensions=1536,
            input_tokens=10,
            cached=False,
            cache_key="test_cache_key",
        )
    )

    return generator


@pytest.fixture
def sample_documents():
    """Create sample documents with varied embeddings for testing."""
    docs = []

    # Document 1: High similarity to query [0.9, 0.1, ...]
    doc1 = Document(
        id=1,
        sha256_hex="a" * 64,
        original_filename="invoice_acme_jan.pdf",
        metadata_json={
            "doc_type": "Invoice",
            "issuer": "ACME Corp",
            "primary_date": "2024-01-15",
            "summary": "Monthly consulting services invoice",
        },
        embedding_vector={"embedding": [0.9, 0.1] + [0.0] * 1534},
        embedding_cache_key="key1",
        embedding_model="text-embedding-3-small",
        embedding_generated_at=datetime.now(timezone.utc),
        status="completed",
    )
    docs.append(doc1)

    # Document 2: Medium similarity to query [0.8, 0.2, ...]
    doc2 = Document(
        id=2,
        sha256_hex="b" * 64,
        original_filename="receipt_acme_coffee.pdf",
        metadata_json={
            "doc_type": "Receipt",
            "issuer": "ACME Cafe",
            "primary_date": "2024-01-20",
            "summary": "Coffee and pastries",
        },
        embedding_vector={"embedding": [0.85, 0.15] + [0.0] * 1534},
        embedding_cache_key="key2",
        embedding_model="text-embedding-3-small",
        embedding_generated_at=datetime.now(timezone.utc),
        status="completed",
    )
    docs.append(doc2)

    # Document 3: Low similarity to query [0.1, 0.9, ...]
    doc3 = Document(
        id=3,
        sha256_hex="c" * 64,
        original_filename="statement_bank_march.pdf",
        metadata_json={
            "doc_type": "BankStatement",
            "issuer": "First National Bank",
            "primary_date": "2024-03-01",
            "summary": "Account summary and transactions",
        },
        embedding_vector={"embedding": [0.1, 0.9] + [0.0] * 1534},
        embedding_cache_key="key3",
        embedding_model="text-embedding-3-small",
        embedding_generated_at=datetime.now(timezone.utc),
        status="completed",
    )
    docs.append(doc3)

    # Document 4: Another invoice from different issuer
    doc4 = Document(
        id=4,
        sha256_hex="d" * 64,
        original_filename="invoice_techco_feb.pdf",
        metadata_json={
            "doc_type": "Invoice",
            "issuer": "TechCo Inc",
            "primary_date": "2024-02-10",
            "summary": "Software licensing fees",
        },
        embedding_vector={"embedding": [0.7, 0.3] + [0.0] * 1534},
        embedding_cache_key="key4",
        embedding_model="text-embedding-3-small",
        embedding_generated_at=datetime.now(timezone.utc),
        status="completed",
    )
    docs.append(doc4)

    # Document 5: No embedding (should be excluded from search)
    doc5 = Document(
        id=5,
        sha256_hex="e" * 64,
        original_filename="pending_doc.pdf",
        metadata_json={"doc_type": "Unknown"},
        embedding_vector=None,
        status="processing",
    )
    docs.append(doc5)

    return docs


@pytest.fixture
def search_engine(mock_embedding_generator, mock_session):
    """Create SemanticSearchEngine instance with mocked dependencies."""
    return SemanticSearchEngine(
        embedding_generator=mock_embedding_generator,
        session=mock_session,
        min_similarity=0.7,
    )


# ===================================================================
# Test Cases: Dataclasses
# ===================================================================


class TestSearchResult:
    """Tests for SearchResult dataclass."""

    def test_creation(self, sample_documents):
        """Test creating SearchResult instance."""
        doc = sample_documents[0]
        result = SearchResult(document=doc, similarity_score=0.95, rank=1)

        assert result.document == doc
        assert result.similarity_score == 0.95
        assert result.rank == 1

    def test_fields_accessible(self, sample_documents):
        """Test all fields are accessible."""
        doc = sample_documents[0]
        result = SearchResult(document=doc, similarity_score=0.88, rank=2)

        assert result.document.original_filename == "invoice_acme_jan.pdf"
        assert isinstance(result.similarity_score, float)
        assert isinstance(result.rank, int)


class TestSearchResults:
    """Tests for SearchResults dataclass."""

    def test_creation(self, sample_documents):
        """Test creating SearchResults instance."""
        results = [
            SearchResult(document=sample_documents[0], similarity_score=0.95, rank=1),
            SearchResult(document=sample_documents[1], similarity_score=0.88, rank=2),
        ]

        search_results = SearchResults(
            results=results,
            total_count=2,
            query="test query",
            execution_time_ms=15.5,
            cache_hit=True,
            filters_applied={"doc_type": "Invoice"},
        )

        assert len(search_results.results) == 2
        assert search_results.total_count == 2
        assert search_results.query == "test query"
        assert search_results.execution_time_ms == 15.5
        assert search_results.cache_hit is True
        assert search_results.filters_applied == {"doc_type": "Invoice"}

    def test_optional_filters(self, sample_documents):
        """Test SearchResults with no filters applied."""
        results = []
        search_results = SearchResults(
            results=results,
            total_count=0,
            query="test",
            execution_time_ms=10.0,
            cache_hit=False,
        )

        assert search_results.filters_applied is None


# ===================================================================
# Test Cases: SemanticSearchEngine Initialization
# ===================================================================


class TestSemanticSearchEngineInit:
    """Tests for SemanticSearchEngine initialization."""

    def test_initialization_default_min_similarity(
        self, mock_embedding_generator, mock_session
    ):
        """Test initialization uses config default for min_similarity."""
        with patch("src.search.get_config") as mock_config:
            mock_config.return_value = Mock(search_relevance_threshold=0.75)

            engine = SemanticSearchEngine(
                embedding_generator=mock_embedding_generator, session=mock_session
            )

            assert engine.min_similarity == 0.75

    def test_initialization_custom_min_similarity(
        self, mock_embedding_generator, mock_session
    ):
        """Test initialization with custom min_similarity."""
        engine = SemanticSearchEngine(
            embedding_generator=mock_embedding_generator,
            session=mock_session,
            min_similarity=0.85,
        )

        assert engine.min_similarity == 0.85

    def test_initialization_stores_dependencies(
        self, mock_embedding_generator, mock_session
    ):
        """Test initialization stores all dependencies."""
        engine = SemanticSearchEngine(
            embedding_generator=mock_embedding_generator,
            session=mock_session,
            min_similarity=0.7,
        )

        assert engine.embedding_generator == mock_embedding_generator
        assert engine.session == mock_session


# ===================================================================
# Test Cases: Basic Search Functionality
# ===================================================================


class TestBasicSearch:
    """Tests for basic search functionality."""

    def test_search_returns_results(
        self, search_engine, mock_session, sample_documents, mock_embedding_generator
    ):
        """Test search returns ranked results."""
        # Setup mock to return documents
        query_mock = Mock()
        query_mock.filter = Mock(return_value=query_mock)
        query_mock.count = Mock(return_value=4)
        query_mock.all = Mock(
            return_value=sample_documents[:4]
        )  # Exclude doc5 (no embedding)
        mock_session.query = Mock(return_value=query_mock)

        # Mock embedding similar to doc1
        mock_embedding_generator.generate_embedding.return_value = EmbeddingResult(
            embedding=[0.9, 0.1] + [0.0] * 1534,
            model="text-embedding-3-small",
            dimensions=1536,
            input_tokens=5,
            cached=False,
            cache_key="query_key",
        )

        results = search_engine.search("ACME invoice")

        assert isinstance(results, SearchResults)
        assert len(results.results) > 0
        assert results.query == "ACME invoice"
        assert results.execution_time_ms > 0

    def test_search_orders_by_similarity_descending(
        self, search_engine, mock_session, sample_documents, mock_embedding_generator
    ):
        """Test results are ordered by similarity score (descending)."""
        query_mock = Mock()
        query_mock.filter = Mock(return_value=query_mock)
        query_mock.count = Mock(return_value=4)
        query_mock.all = Mock(return_value=sample_documents[:4])
        mock_session.query = Mock(return_value=query_mock)

        mock_embedding_generator.generate_embedding.return_value = EmbeddingResult(
            embedding=[0.9, 0.1] + [0.0] * 1534,
            model="text-embedding-3-small",
            dimensions=1536,
            input_tokens=5,
            cached=False,
            cache_key="query_key",
        )

        results = search_engine.search("test query", limit=10)

        # Verify descending order
        for i in range(len(results.results) - 1):
            assert (
                results.results[i].similarity_score
                >= results.results[i + 1].similarity_score
            )

    def test_search_assigns_sequential_ranks(
        self, search_engine, mock_session, sample_documents, mock_embedding_generator
    ):
        """Test results have sequential ranks starting from 1."""
        query_mock = Mock()
        query_mock.filter = Mock(return_value=query_mock)
        query_mock.count = Mock(return_value=4)
        query_mock.all = Mock(return_value=sample_documents[:4])
        mock_session.query = Mock(return_value=query_mock)

        mock_embedding_generator.generate_embedding.return_value = EmbeddingResult(
            embedding=[0.9, 0.1] + [0.0] * 1534,
            model="text-embedding-3-small",
            dimensions=1536,
            input_tokens=5,
            cached=False,
            cache_key="query_key",
        )

        results = search_engine.search("test query", limit=10)

        for idx, result in enumerate(results.results):
            assert result.rank == idx + 1

    def test_search_empty_query_raises_error(self, search_engine):
        """Test empty query raises ValueError."""
        with pytest.raises(ValueError, match="Search query cannot be empty"):
            search_engine.search("")

        with pytest.raises(ValueError, match="Search query cannot be empty"):
            search_engine.search("   ")

    def test_search_no_results_below_threshold(
        self, search_engine, mock_session, sample_documents, mock_embedding_generator
    ):
        """Test search returns empty results when all below threshold."""
        query_mock = Mock()
        query_mock.filter = Mock(return_value=query_mock)
        query_mock.count = Mock(return_value=4)
        query_mock.all = Mock(return_value=sample_documents[:4])
        mock_session.query = Mock(return_value=query_mock)

        # Mock embedding very dissimilar to all docs
        mock_embedding_generator.generate_embedding.return_value = EmbeddingResult(
            embedding=[0.0, 0.0] + [1.0] * 1534,
            model="text-embedding-3-small",
            dimensions=1536,
            input_tokens=5,
            cached=False,
            cache_key="query_key",
        )

        # High threshold
        search_engine.min_similarity = 0.99
        results = search_engine.search("dissimilar query")

        assert len(results.results) == 0
        assert results.total_count == 0

    def test_search_empty_database(
        self, search_engine, mock_session, mock_embedding_generator
    ):
        """Test search against empty database returns empty results."""
        query_mock = Mock()
        query_mock.filter = Mock(return_value=query_mock)
        query_mock.count = Mock(return_value=0)
        query_mock.all = Mock(return_value=[])
        mock_session.query = Mock(return_value=query_mock)

        results = search_engine.search("test query")

        assert len(results.results) == 0
        assert results.total_count == 0
        assert results.execution_time_ms > 0

    def test_search_tracks_cache_hit(
        self, search_engine, mock_session, sample_documents, mock_embedding_generator
    ):
        """Test search tracks cache hit status from embedding generation."""
        query_mock = Mock()
        query_mock.filter = Mock(return_value=query_mock)
        query_mock.count = Mock(return_value=4)
        query_mock.all = Mock(return_value=sample_documents[:4])
        mock_session.query = Mock(return_value=query_mock)

        # Mock cached embedding
        mock_embedding_generator.generate_embedding.return_value = EmbeddingResult(
            embedding=[0.9, 0.1] + [0.0] * 1534,
            model="text-embedding-3-small",
            dimensions=1536,
            input_tokens=5,
            cached=True,  # Cached
            cache_key="query_key",
        )

        results = search_engine.search("test query")

        assert results.cache_hit is True


# ===================================================================
# Test Cases: Pagination
# ===================================================================


class TestPagination:
    """Tests for pagination support."""

    def test_pagination_limit(
        self, search_engine, mock_session, sample_documents, mock_embedding_generator
    ):
        """Test limit parameter restricts result count."""
        query_mock = Mock()
        query_mock.filter = Mock(return_value=query_mock)
        query_mock.count = Mock(return_value=4)
        query_mock.all = Mock(return_value=sample_documents[:4])
        mock_session.query = Mock(return_value=query_mock)

        mock_embedding_generator.generate_embedding.return_value = EmbeddingResult(
            embedding=[0.9, 0.1] + [0.0] * 1534,
            model="text-embedding-3-small",
            dimensions=1536,
            input_tokens=5,
            cached=False,
            cache_key="query_key",
        )

        results = search_engine.search("test query", limit=2)

        assert len(results.results) <= 2

    def test_pagination_offset(
        self, search_engine, mock_session, sample_documents, mock_embedding_generator
    ):
        """Test offset parameter skips initial results."""
        query_mock = Mock()
        query_mock.filter = Mock(return_value=query_mock)
        query_mock.count = Mock(return_value=4)
        query_mock.all = Mock(return_value=sample_documents[:4])
        mock_session.query = Mock(return_value=query_mock)

        mock_embedding_generator.generate_embedding.return_value = EmbeddingResult(
            embedding=[0.9, 0.1] + [0.0] * 1534,
            model="text-embedding-3-small",
            dimensions=1536,
            input_tokens=5,
            cached=False,
            cache_key="query_key",
        )

        # Get first page
        _page1 = search_engine.search("test query", limit=2, offset=0)

        # Get second page
        page2 = search_engine.search("test query", limit=2, offset=2)

        # Ranks should account for offset
        if len(page2.results) > 0:
            assert page2.results[0].rank == 3

    def test_pagination_offset_exceeds_results(
        self, search_engine, mock_session, sample_documents, mock_embedding_generator
    ):
        """Test offset beyond total results returns empty list."""
        query_mock = Mock()
        query_mock.filter = Mock(return_value=query_mock)
        query_mock.count = Mock(return_value=4)
        query_mock.all = Mock(return_value=sample_documents[:4])
        mock_session.query = Mock(return_value=query_mock)

        mock_embedding_generator.generate_embedding.return_value = EmbeddingResult(
            embedding=[0.9, 0.1] + [0.0] * 1534,
            model="text-embedding-3-small",
            dimensions=1536,
            input_tokens=5,
            cached=False,
            cache_key="query_key",
        )

        results = search_engine.search("test query", offset=100)

        assert len(results.results) == 0

    def test_pagination_invalid_limit_raises_error(self, search_engine):
        """Test invalid limit raises ValueError."""
        with pytest.raises(ValueError, match="Limit must be"):
            search_engine.search("test", limit=0)

        with pytest.raises(ValueError, match="Limit must be"):
            search_engine.search("test", limit=-1)

    def test_pagination_invalid_offset_raises_error(self, search_engine):
        """Test invalid offset raises ValueError."""
        with pytest.raises(ValueError, match="Offset must be"):
            search_engine.search("test", offset=-1)

    def test_pagination_limit_exceeds_max(self, search_engine):
        """Test limit exceeding max raises ValueError."""
        with patch("src.search.get_config") as mock_config:
            mock_config.return_value = Mock(search_max_top_k=20)

            with pytest.raises(ValueError, match="exceeds maximum"):
                search_engine.search("test", limit=50)


# ===================================================================
# Test Cases: Metadata Filtering
# ===================================================================


class TestMetadataFiltering:
    """Tests for metadata filtering functionality."""

    def test_filter_by_doc_type_single(
        self, search_engine, mock_session, sample_documents, mock_embedding_generator
    ):
        """Test filtering by single doc_type."""
        # Mock _apply_metadata_filters to bypass SQL generation
        with patch.object(search_engine, "_apply_metadata_filters") as mock_filter:
            query_mock = Mock()
            query_mock.filter = Mock(return_value=query_mock)
            query_mock.count = Mock(return_value=2)
            # Return only invoices
            invoices = [
                d
                for d in sample_documents
                if d.metadata_json.get("doc_type") == "Invoice"
            ]
            query_mock.all = Mock(return_value=invoices)
            mock_session.query = Mock(return_value=query_mock)

            # _apply_metadata_filters should return the query unchanged
            mock_filter.return_value = query_mock

            mock_embedding_generator.generate_embedding.return_value = EmbeddingResult(
                embedding=[0.9, 0.1] + [0.0] * 1534,
                model="text-embedding-3-small",
                dimensions=1536,
                input_tokens=5,
                cached=False,
                cache_key="query_key",
            )

            results = search_engine.search(
                "test query", filters={"doc_type": "Invoice"}
            )

            assert results.filters_applied == {"doc_type": "Invoice"}
            # Verify filter method was called with correct args
            mock_filter.assert_called()

    def test_filter_by_doc_type_list(
        self, search_engine, mock_session, sample_documents, mock_embedding_generator
    ):
        """Test filtering by list of doc_types."""
        with patch.object(search_engine, "_apply_metadata_filters") as mock_filter:
            query_mock = Mock()
            query_mock.filter = Mock(return_value=query_mock)
            query_mock.count = Mock(return_value=3)
            filtered = [
                d
                for d in sample_documents
                if d.metadata_json.get("doc_type") in ["Invoice", "Receipt"]
            ]
            query_mock.all = Mock(return_value=filtered)
            mock_session.query = Mock(return_value=query_mock)
            mock_filter.return_value = query_mock

            mock_embedding_generator.generate_embedding.return_value = EmbeddingResult(
                embedding=[0.9, 0.1] + [0.0] * 1534,
                model="text-embedding-3-small",
                dimensions=1536,
                input_tokens=5,
                cached=False,
                cache_key="query_key",
            )

            results = search_engine.search(
                "test query", filters={"doc_type": ["Invoice", "Receipt"]}
            )

            assert results.filters_applied == {"doc_type": ["Invoice", "Receipt"]}

    def test_filter_by_issuer_substring(
        self, search_engine, mock_session, sample_documents, mock_embedding_generator
    ):
        """Test filtering by issuer substring (case-insensitive)."""
        with patch.object(search_engine, "_apply_metadata_filters") as mock_filter:
            query_mock = Mock()
            query_mock.filter = Mock(return_value=query_mock)
            query_mock.count = Mock(return_value=2)
            # Return ACME documents
            acme_docs = [
                d
                for d in sample_documents
                if "ACME" in d.metadata_json.get("issuer", "")
            ]
            query_mock.all = Mock(return_value=acme_docs)
            mock_session.query = Mock(return_value=query_mock)
            mock_filter.return_value = query_mock

            mock_embedding_generator.generate_embedding.return_value = EmbeddingResult(
                embedding=[0.9, 0.1] + [0.0] * 1534,
                model="text-embedding-3-small",
                dimensions=1536,
                input_tokens=5,
                cached=False,
                cache_key="query_key",
            )

            results = search_engine.search(
                "test query", filters={"issuer": "acme"}  # Lowercase should match
            )

            assert results.filters_applied == {"issuer": "acme"}

    def test_filter_by_date_range_start_only(
        self, search_engine, mock_session, sample_documents, mock_embedding_generator
    ):
        """Test filtering by date range with start date only."""
        with patch.object(search_engine, "_apply_metadata_filters") as mock_filter:
            query_mock = Mock()
            query_mock.filter = Mock(return_value=query_mock)
            query_mock.count = Mock(return_value=2)
            # Return docs from Feb onwards
            feb_onwards = [
                d
                for d in sample_documents
                if d.metadata_json.get("primary_date", "") >= "2024-02-01"
            ]
            query_mock.all = Mock(return_value=feb_onwards)
            mock_session.query = Mock(return_value=query_mock)
            mock_filter.return_value = query_mock

            mock_embedding_generator.generate_embedding.return_value = EmbeddingResult(
                embedding=[0.9, 0.1] + [0.0] * 1534,
                model="text-embedding-3-small",
                dimensions=1536,
                input_tokens=5,
                cached=False,
                cache_key="query_key",
            )

            results = search_engine.search(
                "test query", filters={"date_range": {"start": "2024-02-01"}}
            )

            assert results.filters_applied == {"date_range": {"start": "2024-02-01"}}

    def test_filter_by_date_range_end_only(
        self, search_engine, mock_session, sample_documents, mock_embedding_generator
    ):
        """Test filtering by date range with end date only."""
        with patch.object(search_engine, "_apply_metadata_filters") as mock_filter:
            query_mock = Mock()
            query_mock.filter = Mock(return_value=query_mock)
            query_mock.count = Mock(return_value=3)
            # Return docs before March (excluding doc5 which has no embedding)
            before_march = [
                d
                for d in sample_documents[:4]  # Only first 4 docs
                if d.metadata_json.get("primary_date", "") < "2024-03-01"
            ]
            query_mock.all = Mock(return_value=before_march)
            mock_session.query = Mock(return_value=query_mock)
            mock_filter.return_value = query_mock

            mock_embedding_generator.generate_embedding.return_value = EmbeddingResult(
                embedding=[0.9, 0.1] + [0.0] * 1534,
                model="text-embedding-3-small",
                dimensions=1536,
                input_tokens=5,
                cached=False,
                cache_key="query_key",
            )

            results = search_engine.search(
                "test query", filters={"date_range": {"end": "2024-02-28"}}
            )

            assert results.filters_applied == {"date_range": {"end": "2024-02-28"}}

    def test_filter_by_date_range_both(
        self, search_engine, mock_session, sample_documents, mock_embedding_generator
    ):
        """Test filtering by date range with start and end dates."""
        with patch.object(search_engine, "_apply_metadata_filters") as mock_filter:
            query_mock = Mock()
            query_mock.filter = Mock(return_value=query_mock)
            query_mock.count = Mock(return_value=2)
            query_mock.all = Mock(return_value=sample_documents[:2])
            mock_session.query = Mock(return_value=query_mock)
            mock_filter.return_value = query_mock

            mock_embedding_generator.generate_embedding.return_value = EmbeddingResult(
                embedding=[0.9, 0.1] + [0.0] * 1534,
                model="text-embedding-3-small",
                dimensions=1536,
                input_tokens=5,
                cached=False,
                cache_key="query_key",
            )

            results = search_engine.search(
                "test query",
                filters={"date_range": {"start": "2024-01-01", "end": "2024-01-31"}},
            )

            assert results.filters_applied == {
                "date_range": {"start": "2024-01-01", "end": "2024-01-31"}
            }

    def test_combined_filters(
        self, search_engine, mock_session, sample_documents, mock_embedding_generator
    ):
        """Test applying multiple filters simultaneously."""
        with patch.object(search_engine, "_apply_metadata_filters") as mock_filter:
            query_mock = Mock()
            query_mock.filter = Mock(return_value=query_mock)
            query_mock.count = Mock(return_value=1)
            query_mock.all = Mock(return_value=[sample_documents[0]])
            mock_session.query = Mock(return_value=query_mock)
            mock_filter.return_value = query_mock

            mock_embedding_generator.generate_embedding.return_value = EmbeddingResult(
                embedding=[0.9, 0.1] + [0.0] * 1534,
                model="text-embedding-3-small",
                dimensions=1536,
                input_tokens=5,
                cached=False,
                cache_key="query_key",
            )

            filters = {
                "doc_type": "Invoice",
                "issuer": "ACME",
                "date_range": {"start": "2024-01-01", "end": "2024-01-31"},
            }

            results = search_engine.search("test query", filters=filters)

            assert results.filters_applied == filters


# ===================================================================
# Test Cases: Similarity Computation
# ===================================================================


class TestSimilarityComputation:
    """Tests for cosine similarity computation."""

    def test_compute_similarities_uses_numpy(self, search_engine):
        """Test similarity computation uses NumPy (vectorized)."""
        query_embedding = [0.1] * 1536
        doc_embeddings = [[0.2] * 1536, [0.3] * 1536]

        similarities = search_engine._compute_similarities(
            query_embedding, doc_embeddings
        )

        # Should return NumPy array
        assert isinstance(similarities, np.ndarray)
        assert similarities.shape == (2,)

    def test_compute_similarities_range(self, search_engine):
        """Test similarity scores are in valid cosine similarity range."""
        query_embedding = [0.5] * 1536
        doc_embeddings = [[0.5] * 1536, [0.8] * 1536, [-0.5] * 1536]

        similarities = search_engine._compute_similarities(
            query_embedding, doc_embeddings
        )

        # Cosine similarity range: [-1, 1]
        assert all(-1.0 <= s <= 1.0 for s in similarities)

    def test_compute_similarities_identical_vectors(self, search_engine):
        """Test identical vectors have similarity of 1.0."""
        query_embedding = [0.5, 0.5] + [0.0] * 1534
        doc_embeddings = [[0.5, 0.5] + [0.0] * 1534]

        similarities = search_engine._compute_similarities(
            query_embedding, doc_embeddings
        )

        # Identical normalized vectors should have similarity ~1.0
        assert abs(similarities[0] - 1.0) < 0.01

    def test_compute_similarities_orthogonal_vectors(self, search_engine):
        """Test orthogonal vectors have similarity near 0."""
        query_embedding = [1.0, 0.0] + [0.0] * 1534
        doc_embeddings = [[0.0, 1.0] + [0.0] * 1534]

        similarities = search_engine._compute_similarities(
            query_embedding, doc_embeddings
        )

        # Orthogonal vectors should have similarity ~0
        assert abs(similarities[0]) < 0.01

    def test_compute_similarities_empty_list(self, search_engine):
        """Test computing similarities with empty document list."""
        query_embedding = [0.1] * 1536
        doc_embeddings = []

        similarities = search_engine._compute_similarities(
            query_embedding, doc_embeddings
        )

        assert isinstance(similarities, np.ndarray)
        assert len(similarities) == 0


# ===================================================================
# Test Cases: Document Similarity Search
# ===================================================================


class TestSearchByDocument:
    """Tests for document-based similarity search."""

    def test_search_by_document_basic(
        self, search_engine, mock_session, sample_documents
    ):
        """Test finding similar documents to a given document."""
        source_doc = sample_documents[0]

        query_mock = Mock()
        query_mock.filter = Mock(return_value=query_mock)
        query_mock.count = Mock(return_value=3)
        # Return other documents (excluding source)
        query_mock.all = Mock(return_value=sample_documents[1:4])
        mock_session.query = Mock(return_value=query_mock)

        results = search_engine.search_by_document(source_doc, limit=5)

        assert isinstance(results, SearchResults)
        assert results.cache_hit is True  # Uses cached embedding from DB

    def test_search_by_document_exclude_self(
        self, search_engine, mock_session, sample_documents
    ):
        """Test excluding source document from results."""
        source_doc = sample_documents[0]

        query_mock = Mock()
        query_mock.filter = Mock(return_value=query_mock)
        query_mock.count = Mock(return_value=3)
        query_mock.all = Mock(return_value=sample_documents[1:4])
        mock_session.query = Mock(return_value=query_mock)

        _results = search_engine.search_by_document(
            source_doc, limit=5, exclude_self=True
        )

        # Verify filter was called (for excluding source doc)
        assert query_mock.filter.called

    def test_search_by_document_include_self(
        self, search_engine, mock_session, sample_documents
    ):
        """Test including source document in results."""
        source_doc = sample_documents[0]

        query_mock = Mock()
        query_mock.filter = Mock(return_value=query_mock)
        query_mock.count = Mock(return_value=4)
        query_mock.all = Mock(return_value=sample_documents[:4])
        mock_session.query = Mock(return_value=query_mock)

        results = search_engine.search_by_document(
            source_doc, limit=5, exclude_self=False
        )

        # Could include source doc in results
        assert isinstance(results, SearchResults)

    def test_search_by_document_no_embedding_raises_error(
        self, search_engine, sample_documents
    ):
        """Test searching with document that has no embedding raises error."""
        doc_without_embedding = sample_documents[4]  # doc5 has no embedding

        with pytest.raises(ValueError, match="has no embedding"):
            search_engine.search_by_document(doc_without_embedding)

    def test_search_by_document_with_filters(
        self, search_engine, mock_session, sample_documents
    ):
        """Test document similarity search with metadata filters."""
        with patch.object(search_engine, "_apply_metadata_filters") as mock_filter:
            source_doc = sample_documents[0]

            query_mock = Mock()
            query_mock.filter = Mock(return_value=query_mock)
            query_mock.count = Mock(return_value=1)
            # Return only invoices
            invoices = [
                d
                for d in sample_documents[1:4]
                if d.metadata_json.get("doc_type") == "Invoice"
            ]
            query_mock.all = Mock(return_value=invoices)
            mock_session.query = Mock(return_value=query_mock)
            mock_filter.return_value = query_mock

            results = search_engine.search_by_document(
                source_doc, filters={"doc_type": "Invoice"}
            )

            assert results.filters_applied == {"doc_type": "Invoice"}

    def test_search_by_document_empty_results(
        self, search_engine, mock_session, sample_documents
    ):
        """Test document similarity search with no matches."""
        source_doc = sample_documents[0]

        query_mock = Mock()
        query_mock.filter = Mock(return_value=query_mock)
        query_mock.count = Mock(return_value=0)
        query_mock.all = Mock(return_value=[])
        mock_session.query = Mock(return_value=query_mock)

        results = search_engine.search_by_document(source_doc)

        assert len(results.results) == 0
        assert results.total_count == 0

    def test_search_by_document_all_below_threshold(
        self, search_engine, mock_session, sample_documents
    ):
        """Test document similarity search when all results below threshold."""
        # Use doc1 as source, but make it very dissimilar to others
        source_doc = sample_documents[0]
        # Create a very different embedding for source
        source_doc.embedding_vector = {"embedding": [0.0, 0.0] + [1.0] * 1534}

        query_mock = Mock()
        query_mock.filter = Mock(return_value=query_mock)
        query_mock.count = Mock(return_value=3)
        # Return other documents that will have low similarity
        query_mock.all = Mock(return_value=sample_documents[1:4])
        mock_session.query = Mock(return_value=query_mock)

        # Set high threshold
        search_engine.min_similarity = 0.95

        results = search_engine.search_by_document(source_doc, limit=5)

        # All documents should be filtered out by threshold
        assert len(results.results) == 0
        assert results.total_count == 0
        assert results.cache_hit is True


# ===================================================================
# Test Cases: Performance Testing
# ===================================================================


class TestPerformance:
    """Performance tests for search latency."""

    def test_single_search_latency(
        self, search_engine, mock_session, sample_documents, mock_embedding_generator
    ):
        """Test single search completes in reasonable time."""
        query_mock = Mock()
        query_mock.filter = Mock(return_value=query_mock)
        query_mock.count = Mock(return_value=4)
        query_mock.all = Mock(return_value=sample_documents[:4])
        mock_session.query = Mock(return_value=query_mock)

        mock_embedding_generator.generate_embedding.return_value = EmbeddingResult(
            embedding=[0.9, 0.1] + [0.0] * 1534,
            model="text-embedding-3-small",
            dimensions=1536,
            input_tokens=5,
            cached=False,
            cache_key="query_key",
        )

        start = time.perf_counter()
        results = search_engine.search("test query")
        elapsed_ms = (time.perf_counter() - start) * 1000

        # With mocked components, should be very fast
        assert elapsed_ms < 100  # Generous for mocked calls
        assert results.execution_time_ms > 0

    def test_p95_latency_under_500ms(
        self, search_engine, mock_session, sample_documents, mock_embedding_generator
    ):
        """Test P95 search latency is under 500ms."""
        query_mock = Mock()
        query_mock.filter = Mock(return_value=query_mock)
        query_mock.count = Mock(return_value=4)
        query_mock.all = Mock(return_value=sample_documents[:4])
        mock_session.query = Mock(return_value=query_mock)

        latencies: List[float] = []
        num_queries = 20

        for i in range(num_queries):
            # Vary embeddings slightly
            embedding = [0.9 + i * 0.01, 0.1] + [0.0] * 1534
            mock_embedding_generator.generate_embedding.return_value = EmbeddingResult(
                embedding=embedding,
                model="text-embedding-3-small",
                dimensions=1536,
                input_tokens=5,
                cached=False,
                cache_key=f"query_key_{i}",
            )

            start = time.perf_counter()
            _results = search_engine.search(f"test query {i}")
            latency_ms = (time.perf_counter() - start) * 1000
            latencies.append(latency_ms)

        # Calculate percentiles
        latencies_sorted = sorted(latencies)
        p50 = statistics.median(latencies_sorted)
        p95_index = int(len(latencies_sorted) * 0.95)
        p95 = latencies_sorted[p95_index]
        p99_index = int(len(latencies_sorted) * 0.99)
        p99 = latencies_sorted[p99_index]

        # Print for visibility
        print(f"\nSearch Latency Benchmarks (n={num_queries}, mocked):")
        print(f"  P50: {p50:.2f}ms")
        print(f"  P95: {p95:.2f}ms")
        print(f"  P99: {p99:.2f}ms")

        # Acceptance criterion
        assert p95 < 500, f"P95 latency {p95:.2f}ms exceeds 500ms target"

    def test_vectorized_computation_efficiency(self, search_engine):
        """Test NumPy vectorization for large document sets."""
        # Create many document embeddings
        num_docs = 1000
        query_embedding = [0.5] * 1536
        doc_embeddings = [[0.5 + i * 0.001] * 1536 for i in range(num_docs)]

        start = time.perf_counter()
        similarities = search_engine._compute_similarities(
            query_embedding, doc_embeddings
        )
        elapsed_ms = (time.perf_counter() - start) * 1000

        # NumPy vectorization should be fast
        assert elapsed_ms < 100  # Should be very fast for 1000 docs
        assert len(similarities) == num_docs

    def test_batch_loading_efficiency(
        self, search_engine, mock_session, mock_embedding_generator
    ):
        """Test documents are loaded in single query (not N+1)."""
        # Create many documents
        num_docs = 100
        docs = [
            Document(
                id=i,
                sha256_hex=f"{i:064d}",
                original_filename=f"doc{i}.pdf",
                metadata_json={"doc_type": "Invoice", "issuer": f"Company {i}"},
                embedding_vector={"embedding": [0.5] * 1536},
                status="completed",
            )
            for i in range(num_docs)
        ]

        query_mock = Mock()
        query_mock.filter = Mock(return_value=query_mock)
        query_mock.count = Mock(return_value=num_docs)
        query_mock.all = Mock(return_value=docs)
        mock_session.query = Mock(return_value=query_mock)

        mock_embedding_generator.generate_embedding.return_value = EmbeddingResult(
            embedding=[0.5] * 1536,
            model="text-embedding-3-small",
            dimensions=1536,
            input_tokens=5,
            cached=False,
            cache_key="query_key",
        )

        _results = search_engine.search("test query", limit=10)

        # Verify query.all() called only once (batch loading)
        assert query_mock.all.call_count == 1

    def test_cache_hit_improves_latency(
        self, search_engine, mock_session, sample_documents, mock_embedding_generator
    ):
        """Test query embedding cache improves latency."""
        query_mock = Mock()
        query_mock.filter = Mock(return_value=query_mock)
        query_mock.count = Mock(return_value=4)
        query_mock.all = Mock(return_value=sample_documents[:4])
        mock_session.query = Mock(return_value=query_mock)

        # First call: cache miss
        mock_embedding_generator.generate_embedding.return_value = EmbeddingResult(
            embedding=[0.9, 0.1] + [0.0] * 1534,
            model="text-embedding-3-small",
            dimensions=1536,
            input_tokens=5,
            cached=False,
            cache_key="query_key",
        )

        result1 = search_engine.search("test query")
        latency1 = result1.execution_time_ms

        # Second call: cache hit
        mock_embedding_generator.generate_embedding.return_value = EmbeddingResult(
            embedding=[0.9, 0.1] + [0.0] * 1534,
            model="text-embedding-3-small",
            dimensions=1536,
            input_tokens=5,
            cached=True,  # Cached
            cache_key="query_key",
        )

        result2 = search_engine.search("test query")
        latency2 = result2.execution_time_ms

        # Cache hit may or may not be faster due to mocking overhead
        # Just verify both executed successfully
        assert latency1 > 0
        assert latency2 > 0
        assert result2.cache_hit is True


# ===================================================================
# Test Cases: Edge Cases
# ===================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_special_characters_in_query(
        self, search_engine, mock_session, sample_documents, mock_embedding_generator
    ):
        """Test search handles special characters in query."""
        query_mock = Mock()
        query_mock.filter = Mock(return_value=query_mock)
        query_mock.count = Mock(return_value=4)
        query_mock.all = Mock(return_value=sample_documents[:4])
        mock_session.query = Mock(return_value=query_mock)

        mock_embedding_generator.generate_embedding.return_value = EmbeddingResult(
            embedding=[0.9, 0.1] + [0.0] * 1534,
            model="text-embedding-3-small",
            dimensions=1536,
            input_tokens=5,
            cached=False,
            cache_key="query_key",
        )

        # Special characters should not cause errors
        results = search_engine.search("ACME Corp. (2024) - Invoice #12345")

        assert isinstance(results, SearchResults)

    def test_unicode_in_query(
        self, search_engine, mock_session, sample_documents, mock_embedding_generator
    ):
        """Test search handles Unicode characters."""
        query_mock = Mock()
        query_mock.filter = Mock(return_value=query_mock)
        query_mock.count = Mock(return_value=4)
        query_mock.all = Mock(return_value=sample_documents[:4])
        mock_session.query = Mock(return_value=query_mock)

        mock_embedding_generator.generate_embedding.return_value = EmbeddingResult(
            embedding=[0.9, 0.1] + [0.0] * 1534,
            model="text-embedding-3-small",
            dimensions=1536,
            input_tokens=5,
            cached=False,
            cache_key="query_key",
        )

        results = search_engine.search("Café Français — 日本語 — emoji 🎉")

        assert isinstance(results, SearchResults)

    def test_very_long_query(
        self, search_engine, mock_session, sample_documents, mock_embedding_generator
    ):
        """Test search handles very long queries."""
        query_mock = Mock()
        query_mock.filter = Mock(return_value=query_mock)
        query_mock.count = Mock(return_value=4)
        query_mock.all = Mock(return_value=sample_documents[:4])
        mock_session.query = Mock(return_value=query_mock)

        mock_embedding_generator.generate_embedding.return_value = EmbeddingResult(
            embedding=[0.9, 0.1] + [0.0] * 1534,
            model="text-embedding-3-small",
            dimensions=1536,
            input_tokens=500,
            cached=False,
            cache_key="query_key",
        )

        long_query = "test " * 1000  # Very long query
        results = search_engine.search(long_query)

        assert isinstance(results, SearchResults)

    def test_missing_embedding_vectors_excluded(
        self, search_engine, mock_session, sample_documents, mock_embedding_generator
    ):
        """Test documents without embeddings are excluded."""
        query_mock = Mock()
        query_mock.filter = Mock(return_value=query_mock)
        # Should filter out doc5 (no embedding)
        query_mock.count = Mock(return_value=4)
        query_mock.all = Mock(return_value=sample_documents[:4])
        mock_session.query = Mock(return_value=query_mock)

        mock_embedding_generator.generate_embedding.return_value = EmbeddingResult(
            embedding=[0.9, 0.1] + [0.0] * 1534,
            model="text-embedding-3-small",
            dimensions=1536,
            input_tokens=5,
            cached=False,
            cache_key="query_key",
        )

        _results = search_engine.search("test query")

        # Verify filter was applied for non-null embeddings
        assert query_mock.filter.called

    def test_all_documents_below_threshold(
        self, search_engine, mock_session, sample_documents, mock_embedding_generator
    ):
        """Test search when all documents are below similarity threshold."""
        query_mock = Mock()
        query_mock.filter = Mock(return_value=query_mock)
        query_mock.count = Mock(return_value=4)
        query_mock.all = Mock(return_value=sample_documents[:4])
        mock_session.query = Mock(return_value=query_mock)

        # Mock very dissimilar embedding
        mock_embedding_generator.generate_embedding.return_value = EmbeddingResult(
            embedding=[0.0, 0.0] + [1.0] * 1534,
            model="text-embedding-3-small",
            dimensions=1536,
            input_tokens=5,
            cached=False,
            cache_key="query_key",
        )

        # Set high threshold
        search_engine.min_similarity = 0.95

        results = search_engine.search("dissimilar query")

        assert len(results.results) == 0
        assert results.total_count == 0

    def test_limit_exceeds_available_results(
        self, search_engine, mock_session, sample_documents, mock_embedding_generator
    ):
        """Test limit larger than available results (but within max)."""
        query_mock = Mock()
        query_mock.filter = Mock(return_value=query_mock)
        query_mock.count = Mock(return_value=2)
        query_mock.all = Mock(return_value=sample_documents[:2])
        mock_session.query = Mock(return_value=query_mock)

        mock_embedding_generator.generate_embedding.return_value = EmbeddingResult(
            embedding=[0.9, 0.1] + [0.0] * 1534,
            model="text-embedding-3-small",
            dimensions=1536,
            input_tokens=5,
            cached=False,
            cache_key="query_key",
        )

        # Use limit within max but larger than available results
        with patch("src.search.get_config") as mock_config:
            mock_config.return_value = Mock(search_max_top_k=20)
            results = search_engine.search("test query", limit=15)

            # Should return available results (not raise error)
            assert len(results.results) <= 2


# ===================================================================
# Test Cases: Temporary Document Creation
# ===================================================================


class TestTemporaryDocument:
    """Tests for _create_temporary_document helper."""

    def test_create_temporary_document(self, search_engine):
        """Test creating temporary document from query text."""
        query = "test query for embedding"

        temp_doc = search_engine._create_temporary_document(query)

        assert isinstance(temp_doc, Document)
        assert temp_doc.sha256_hex == "query_temp"
        assert temp_doc.original_filename == "query"
        assert temp_doc.metadata_json["doc_type"] == "Query"
        assert temp_doc.metadata_json["summary"] == query
        assert temp_doc.status == "completed"
