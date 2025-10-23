"""
Integration tests for semantic search with latency benchmarking.

Tests the complete search workflow:
- Query embedding generation (via 3-tier cache)
- Metadata filtering (doc_type, issuer, dates)
- Cosine similarity ranking
- Relevance threshold filtering
- Pagination logic
- Performance benchmarking (P50, P95, P99 latency)

Acceptance Criteria:
- All tests pass
- P95 latency <500ms validated
- 80%+ test coverage on search.py
- Edge cases covered (empty results, malformed queries)
"""

import pytest
import time
import statistics
from datetime import date, datetime, timezone
from typing import List
from unittest.mock import Mock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models import Base, Document
from src.embeddings import EmbeddingGenerator
from src.search import (
    SemanticSearchEngine,
    SearchQuery,
    SearchResponse,
)


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
    """Create EmbeddingGenerator with mocked client."""
    return EmbeddingGenerator(
        client=mock_openai_client,
        session=session,
        max_cache_size=100,
    )


@pytest.fixture
def search_engine(session, embedding_generator):
    """Create SemanticSearchEngine instance."""
    return SemanticSearchEngine(session, embedding_generator)


@pytest.fixture
def sample_documents(session):
    """Create sample documents with embeddings for testing."""
    docs = [
        Document(
            sha256_hex="hash1",
            original_filename="invoice_acme_jan.pdf",
            metadata_json={
                "doc_type": "Invoice",
                "issuer": "ACME Corp",
                "summary": "Monthly consulting services invoice",
            },
            status="completed",
            embedding_vector=[0.9, 0.1]
            + [0.0] * 1534,  # High similarity to [0.8, 0.2, ...]
            embedding_cache_key="key1",
            embedding_model="text-embedding-3-small",
            embedding_generated_at=datetime.now(timezone.utc),
            created_at=datetime(2025, 1, 15, tzinfo=timezone.utc),
        ),
        Document(
            sha256_hex="hash2",
            original_filename="invoice_techco_feb.pdf",
            metadata_json={
                "doc_type": "Invoice",
                "issuer": "TechCo Inc",
                "summary": "Software licensing fees",
            },
            status="completed",
            embedding_vector=[0.1, 0.9] + [0.0] * 1534,  # Low similarity
            embedding_cache_key="key2",
            embedding_model="text-embedding-3-small",
            embedding_generated_at=datetime.now(timezone.utc),
            created_at=datetime(2025, 2, 10, tzinfo=timezone.utc),
        ),
        Document(
            sha256_hex="hash3",
            original_filename="receipt_acme_coffee.pdf",
            metadata_json={
                "doc_type": "Receipt",
                "issuer": "ACME Cafe",
                "summary": "Coffee and pastries",
            },
            status="completed",
            embedding_vector=[0.85, 0.15] + [0.0] * 1534,  # Medium-high similarity
            embedding_cache_key="key3",
            embedding_model="text-embedding-3-small",
            embedding_generated_at=datetime.now(timezone.utc),
            created_at=datetime(2025, 1, 20, tzinfo=timezone.utc),
        ),
        Document(
            sha256_hex="hash4",
            original_filename="statement_bank_march.pdf",
            metadata_json={
                "doc_type": "BankStatement",
                "issuer": "First National Bank",
                "summary": "Account summary and transactions",
            },
            status="completed",
            embedding_vector=[0.2, 0.8] + [0.0] * 1534,  # Low similarity
            embedding_cache_key="key4",
            embedding_model="text-embedding-3-small",
            embedding_generated_at=datetime.now(timezone.utc),
            created_at=datetime(2025, 3, 1, tzinfo=timezone.utc),
        ),
        # Document without embedding (should be excluded)
        Document(
            sha256_hex="hash5",
            original_filename="pending_doc.pdf",
            metadata_json={"doc_type": "Unknown"},
            status="processing",
            embedding_vector=None,
        ),
    ]

    for doc in docs:
        session.add(doc)
    session.commit()

    return docs


class TestBasicSearch:
    """Test basic search functionality."""

    def test_search_returns_ranked_results(
        self, search_engine, sample_documents, mock_openai_client
    ):
        """Search should return results ranked by similarity."""
        # Mock query embedding similar to doc1
        mock_openai_client.embeddings.create.return_value = Mock(
            data=[Mock(embedding=[0.8, 0.2] + [0.0] * 1534)],
            usage=Mock(prompt_tokens=5, total_tokens=5),
        )

        query = SearchQuery(text="ACME consulting invoice", min_similarity=0.5)
        response = search_engine.search(query)

        assert isinstance(response, SearchResponse)
        assert len(response.results) >= 2  # At least doc1 and doc3

        # Results should be sorted by similarity (descending)
        for i in range(len(response.results) - 1):
            assert (
                response.results[i].similarity_score
                >= response.results[i + 1].similarity_score
            )

        # Ranks should be sequential starting from 1
        for idx, result in enumerate(response.results):
            assert result.rank == idx + 1

    def test_search_excludes_documents_without_embeddings(
        self, search_engine, sample_documents, mock_openai_client
    ):
        """Search should only consider documents with cached embeddings."""
        query = SearchQuery(text="test query", min_similarity=0.0)
        response = search_engine.search(query)

        # Should have 4 results (hash5 excluded - no embedding)
        assert len(response.results) == 4
        assert all(r.document.embedding_vector is not None for r in response.results)

    def test_search_respects_similarity_threshold(
        self, search_engine, sample_documents, mock_openai_client
    ):
        """Search should filter out results below min_similarity."""
        # Mock query embedding with lower similarity to most docs
        # [0.3, 0.7] will have low similarity to doc1 [0.9, 0.1] and doc3 [0.85, 0.15]
        # But moderate similarity to doc2 [0.1, 0.9] and doc4 [0.2, 0.8]
        mock_openai_client.embeddings.create.return_value = Mock(
            data=[Mock(embedding=[0.3, 0.7] + [0.0] * 1534)],
            usage=Mock(prompt_tokens=5, total_tokens=5),
        )

        query_low_threshold = SearchQuery(text="test", min_similarity=0.3)
        response_low = search_engine.search(query_low_threshold)

        query_high_threshold = SearchQuery(text="test", min_similarity=0.8)
        response_high = search_engine.search(query_high_threshold)

        # High threshold should return fewer or equal results
        assert len(response_high.results) <= len(response_low.results)

        # All results should meet threshold
        for result in response_high.results:
            assert result.similarity_score >= 0.8


class TestMetadataFiltering:
    """Test metadata filtering functionality."""

    def test_filter_by_doc_type(
        self, search_engine, sample_documents, mock_openai_client
    ):
        """Search should filter by exact doc_type match."""
        query = SearchQuery(
            text="test query",
            doc_type_filter="Invoice",
            min_similarity=0.0,
        )
        response = search_engine.search(query)

        assert len(response.results) == 2  # doc1 and doc2
        assert all(
            r.document.metadata_json.get("doc_type") == "Invoice"
            for r in response.results
        )

    def test_filter_by_issuer_substring(
        self, search_engine, sample_documents, mock_openai_client
    ):
        """Search should filter by case-insensitive issuer substring."""
        query = SearchQuery(
            text="test query",
            issuer_filter="acme",  # Lowercase, should match "ACME Corp" and "ACME Cafe"
            min_similarity=0.0,
        )
        response = search_engine.search(query)

        assert len(response.results) == 2  # doc1 and doc3
        assert all(
            "ACME" in r.document.metadata_json.get("issuer", "")
            for r in response.results
        )

    def test_filter_by_date_range(
        self, search_engine, sample_documents, mock_openai_client
    ):
        """Search should filter by document creation date range."""
        query = SearchQuery(
            text="test query",
            date_from=date(2025, 1, 1),
            date_to=date(2025, 1, 31),
            min_similarity=0.0,
        )
        response = search_engine.search(query)

        # Should include doc1 (Jan 15) and doc3 (Jan 20), exclude doc2 (Feb 10) and doc4 (Mar 1)
        assert len(response.results) == 2
        for result in response.results:
            doc_date = result.document.created_at.date()
            assert date(2025, 1, 1) <= doc_date <= date(2025, 1, 31)

    def test_combined_filters(
        self, search_engine, sample_documents, mock_openai_client
    ):
        """Search should apply multiple filters simultaneously."""
        query = SearchQuery(
            text="test query",
            doc_type_filter="Invoice",
            issuer_filter="ACME",
            date_from=date(2025, 1, 1),
            date_to=date(2025, 1, 31),
            min_similarity=0.0,
        )
        response = search_engine.search(query)

        # Should only match doc1 (Invoice, ACME Corp, Jan 15)
        assert len(response.results) == 1
        assert response.results[0].document.sha256_hex == "hash1"


class TestPagination:
    """Test pagination logic."""

    def test_pagination_offset_and_limit(
        self, search_engine, sample_documents, mock_openai_client
    ):
        """Search should respect offset and limit parameters."""
        query_page1 = SearchQuery(text="test", offset=0, limit=2, min_similarity=0.0)
        response_page1 = search_engine.search(query_page1)

        query_page2 = SearchQuery(text="test", offset=2, limit=2, min_similarity=0.0)
        response_page2 = search_engine.search(query_page2)

        assert len(response_page1.results) == 2
        assert len(response_page2.results) == 2

        # Pages should not overlap
        page1_ids = {r.document.sha256_hex for r in response_page1.results}
        page2_ids = {r.document.sha256_hex for r in response_page2.results}
        assert len(page1_ids & page2_ids) == 0

        # Ranks should account for offset
        assert response_page1.results[0].rank == 1
        assert response_page1.results[1].rank == 2
        assert response_page2.results[0].rank == 3
        assert response_page2.results[1].rank == 4

    def test_pagination_metadata(
        self, search_engine, sample_documents, mock_openai_client
    ):
        """SearchResponse should include pagination metadata."""
        query = SearchQuery(text="test", offset=1, limit=2, min_similarity=0.0)
        response = search_engine.search(query)

        assert response.total_results == 4  # Total matches before pagination
        assert response.offset == 1
        assert response.limit == 2
        assert len(response.results) == 2

        # has_more flag
        response_dict = response.to_dict()
        assert response_dict["has_more"]   # 1 + 2 < 4

    def test_pagination_last_page(
        self, search_engine, sample_documents, mock_openai_client
    ):
        """Last page should have has_more=False."""
        query = SearchQuery(text="test", offset=3, limit=10, min_similarity=0.0)
        response = search_engine.search(query)

        response_dict = response.to_dict()
        assert not response_dict["has_more"]  # 3 + 1 == 4


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_query_text_raises_error(self, search_engine):
        """Empty query text should raise ValueError."""
        with pytest.raises(ValueError, match="Query text cannot be empty"):
            SearchQuery(text="")

        with pytest.raises(ValueError, match="Query text cannot be empty"):
            SearchQuery(text="   ")

    def test_invalid_similarity_threshold_raises_error(self, search_engine):
        """Invalid min_similarity should raise ValueError."""
        with pytest.raises(ValueError, match="min_similarity must be between"):
            SearchQuery(text="test", min_similarity=-0.1)

        with pytest.raises(ValueError, match="min_similarity must be between"):
            SearchQuery(text="test", min_similarity=1.5)

    def test_invalid_pagination_raises_error(self, search_engine):
        """Invalid offset/limit should raise ValueError."""
        with pytest.raises(ValueError, match="offset must be"):
            SearchQuery(text="test", offset=-1)

        with pytest.raises(ValueError, match="limit must be between"):
            SearchQuery(text="test", limit=0)

        with pytest.raises(ValueError, match="limit must be between"):
            SearchQuery(text="test", limit=101)

    def test_search_with_no_results(
        self, search_engine, sample_documents, mock_openai_client
    ):
        """Search with no matches should return empty results."""
        query = SearchQuery(text="test", min_similarity=0.99)
        response = search_engine.search(query)

        assert len(response.results) == 0
        assert response.total_results == 0
        assert response.search_time_ms > 0  # Should still record time

    def test_search_with_empty_database(self, search_engine, mock_openai_client):
        """Search against empty database should return empty results."""
        query = SearchQuery(text="test query", min_similarity=0.0)
        response = search_engine.search(query)

        assert len(response.results) == 0
        assert response.total_results == 0


class TestSearchByDocument:
    """Test document similarity search."""

    def test_search_by_document(
        self, search_engine, sample_documents, mock_openai_client
    ):
        """Should find documents similar to given document."""
        source_doc = sample_documents[0]  # doc1 with embedding [0.9, 0.1, ...]

        # Mock the embedding generation to return similar vector to doc1
        mock_openai_client.embeddings.create.return_value = Mock(
            data=[Mock(embedding=[0.9, 0.1] + [0.0] * 1534)],  # Same as doc1
            usage=Mock(prompt_tokens=10, total_tokens=10),
        )

        response = search_engine.search_by_document(
            document=source_doc,
            limit=3,
            min_similarity=0.5,
        )

        assert isinstance(response, SearchResponse)
        assert len(response.results) <= 3
        assert len(response.results) >= 1  # Should find at least one match

        # Results should include similar documents (doc1 and doc3 are similar)
        doc_hashes = {r.document.sha256_hex for r in response.results}
        assert "hash1" in doc_hashes or "hash3" in doc_hashes


class TestPerformanceBenchmarking:
    """Test search latency performance."""

    def test_single_search_latency(
        self, search_engine, sample_documents, mock_openai_client
    ):
        """Single search should complete in reasonable time."""
        query = SearchQuery(text="test query", min_similarity=0.5)

        start = time.time()
        response = search_engine.search(query)
        elapsed_ms = (time.time() - start) * 1000

        # Should be fast (most time is mocked API call)
        assert elapsed_ms < 100  # Very generous for mocked calls
        assert response.search_time_ms > 0

    def test_p95_latency_under_500ms(
        self, search_engine, sample_documents, mock_openai_client
    ):
        """P95 search latency should be under 500ms."""
        latencies: List[float] = []
        num_queries = 20

        for i in range(num_queries):
            query = SearchQuery(text=f"test query {i}", min_similarity=0.5)
            response = search_engine.search(query)
            latencies.append(response.search_time_ms)

        # Calculate percentiles
        latencies.sort()
        p50 = statistics.median(latencies)
        p95_index = int(len(latencies) * 0.95)
        p95 = latencies[p95_index]
        p99_index = int(len(latencies) * 0.99)
        p99 = latencies[p99_index]

        # Log performance metrics
        print(f"\nSearch Latency Benchmarks (n={num_queries}):")
        print(f"  P50: {p50:.1f}ms")
        print(f"  P95: {p95:.1f}ms")
        print(f"  P99: {p99:.1f}ms")

        # Acceptance criterion: P95 < 500ms
        assert p95 < 500, f"P95 latency {p95:.1f}ms exceeds 500ms target"

    def test_cache_integration_improves_latency(
        self, search_engine, sample_documents, mock_openai_client
    ):
        """Cached embeddings should improve search latency."""
        query = SearchQuery(text="test query", min_similarity=0.5)

        # First search (cache miss)
        response1 = search_engine.search(query)
        latency1 = response1.search_time_ms

        # Second search with same query (cache hit)
        response2 = search_engine.search(query)
        latency2 = response2.search_time_ms

        # Cache hit should be faster or equal
        assert latency2 <= latency1 * 1.1  # Allow 10% variance


class TestResultHighlighting:
    """Test highlighted text extraction."""

    def test_highlighted_text_includes_metadata(
        self, search_engine, sample_documents, mock_openai_client
    ):
        """Highlighted text should include doc_type, issuer, and summary."""
        query = SearchQuery(text="test", min_similarity=0.0)
        response = search_engine.search(query)

        for result in response.results:
            highlighted = result.highlighted_text
            metadata = result.document.metadata_json

            # Should contain key metadata
            if metadata.get("doc_type"):
                assert metadata["doc_type"] in highlighted or len(highlighted) <= 200

            if metadata.get("issuer"):
                assert metadata["issuer"] in highlighted or len(highlighted) <= 200

    def test_highlighted_text_truncated_to_200_chars(
        self, search_engine, session, mock_openai_client
    ):
        """Highlighted text should not exceed 200 characters."""
        # Create document with very long summary
        long_doc = Document(
            sha256_hex="long_hash",
            original_filename="long_summary.pdf",
            metadata_json={
                "doc_type": "Report",
                "issuer": "Long Company Name Inc.",
                "summary": "A" * 500,  # Very long summary
            },
            status="completed",
            embedding_vector=[0.5] * 1536,
            embedding_cache_key="long_key",
            embedding_model="text-embedding-3-small",
            embedding_generated_at=datetime.now(timezone.utc),
        )
        session.add(long_doc)
        session.commit()

        query = SearchQuery(text="test", min_similarity=0.0)
        response = search_engine.search(query)

        for result in response.results:
            assert len(result.highlighted_text) <= 200


class TestSearchResponseSerialization:
    """Test SearchResponse.to_dict() serialization."""

    def test_to_dict_includes_all_fields(
        self, search_engine, sample_documents, mock_openai_client
    ):
        """to_dict() should include all response metadata."""
        query = SearchQuery(
            text="test query",
            doc_type_filter="Invoice",
            min_similarity=0.7,
            offset=0,
            limit=5,
        )
        response = search_engine.search(query)
        response_dict = response.to_dict()

        # Query parameters
        assert "query" in response_dict
        assert response_dict["query"]["text"] == "test query"
        assert response_dict["query"]["doc_type_filter"] == "Invoice"
        assert response_dict["query"]["min_similarity"] == 0.7

        # Results
        assert "results" in response_dict
        assert isinstance(response_dict["results"], list)

        # Pagination
        assert "total_results" in response_dict
        assert "offset" in response_dict
        assert "limit" in response_dict
        assert "has_more" in response_dict

        # Performance
        assert "search_time_ms" in response_dict
        assert response_dict["search_time_ms"] > 0

    def test_result_to_dict_includes_document_metadata(
        self, search_engine, sample_documents, mock_openai_client
    ):
        """SearchResult.to_dict() should include document details."""
        query = SearchQuery(text="test", min_similarity=0.0, limit=1)
        response = search_engine.search(query)

        if response.results:
            result_dict = response.results[0].to_dict()

            assert "rank" in result_dict
            assert "similarity_score" in result_dict
            assert "document_id" in result_dict
            assert "filename" in result_dict
            assert "doc_type" in result_dict
            assert "issuer" in result_dict
            assert "summary" in result_dict
            assert "highlighted_text" in result_dict
            assert "created_at" in result_dict
