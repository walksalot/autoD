"""
Semantic search engine for document retrieval using vector embeddings.

Provides similarity-based document search with:
- Query embedding generation
- Cosine similarity ranking
- Metadata filtering (doc_type, issuer, date ranges)
- Relevance threshold filtering
- Pagination support
- Result highlighting with similarity scores

Architecture:
- SemanticSearchEngine: Main search API
- SearchQuery: Query parameters and filters
- SearchResult: Individual search result with metadata
- SearchResponse: Paginated search results with metrics

Usage:
    from openai import OpenAI
    from src.search import SemanticSearchEngine, SearchQuery
    from src.embeddings import EmbeddingGenerator
    from src.models import init_db

    session = init_db("sqlite:///app.db")
    client = OpenAI(api_key="sk-...")
    generator = EmbeddingGenerator(client, session=session)
    search_engine = SemanticSearchEngine(session, generator)

    # Simple text search
    query = SearchQuery(text="monthly invoices from ACME Corp")
    results = search_engine.search(query)

    for result in results.results:
        print(f"{result.document.original_filename}: {result.similarity_score:.3f}")

    # Search with metadata filters
    query = SearchQuery(
        text="consulting services",
        doc_type_filter="Invoice",
        issuer_filter="ACME",
        min_similarity=0.75,
        limit=10
    )
    results = search_engine.search(query)
"""

import logging
import math
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, date

from sqlalchemy.orm import Session
from sqlalchemy import and_

from src.models import Document
from src.embeddings import EmbeddingGenerator

logger = logging.getLogger(__name__)


@dataclass
class SearchQuery:
    """
    Search query parameters and filters.

    Attributes:
        text: Natural language search query
        doc_type_filter: Filter by document type (exact match)
        issuer_filter: Filter by issuer (substring match, case-insensitive)
        date_from: Filter documents from this date onwards
        date_to: Filter documents up to this date
        min_similarity: Minimum similarity threshold (0.0-1.0, default: 0.7)
        offset: Pagination offset (default: 0)
        limit: Maximum results to return (default: 10)
    """

    text: str
    doc_type_filter: Optional[str] = None
    issuer_filter: Optional[str] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    min_similarity: float = 0.7
    offset: int = 0
    limit: int = 10

    def __post_init__(self):
        """Validate query parameters."""
        if not self.text or not self.text.strip():
            raise ValueError("Query text cannot be empty")

        if not 0.0 <= self.min_similarity <= 1.0:
            raise ValueError(
                f"min_similarity must be between 0.0 and 1.0, got {self.min_similarity}"
            )

        if self.offset < 0:
            raise ValueError(f"offset must be >= 0, got {self.offset}")

        if self.limit <= 0 or self.limit > 100:
            raise ValueError(f"limit must be between 1 and 100, got {self.limit}")


@dataclass
class SearchResult:
    """
    Single search result with similarity score and metadata.

    Attributes:
        document: Document model instance
        similarity_score: Cosine similarity score (0.0-1.0)
        highlighted_text: Relevant text passages from document
        rank: Position in search results (1-indexed)
    """

    document: Document
    similarity_score: float
    highlighted_text: str
    rank: int

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "rank": self.rank,
            "similarity_score": self.similarity_score,
            "document_id": self.document.id,
            "filename": self.document.original_filename,
            "doc_type": (
                self.document.metadata_json.get("doc_type")
                if self.document.metadata_json
                else None
            ),
            "issuer": (
                self.document.metadata_json.get("issuer")
                if self.document.metadata_json
                else None
            ),
            "summary": (
                self.document.metadata_json.get("summary")
                if self.document.metadata_json
                else None
            ),
            "highlighted_text": self.highlighted_text,
            "created_at": (
                self.document.created_at.isoformat()
                if self.document.created_at
                else None
            ),
        }


@dataclass
class SearchResponse:
    """
    Paginated search results with metadata.

    Attributes:
        query: Original search query
        results: List of search results (ranked by similarity)
        total_results: Total number of results before pagination
        offset: Pagination offset used
        limit: Pagination limit used
        search_time_ms: Time taken for search in milliseconds
    """

    query: SearchQuery
    results: List[SearchResult] = field(default_factory=list)
    total_results: int = 0
    offset: int = 0
    limit: int = 10
    search_time_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "query": {
                "text": self.query.text,
                "doc_type_filter": self.query.doc_type_filter,
                "issuer_filter": self.query.issuer_filter,
                "min_similarity": self.query.min_similarity,
            },
            "results": [r.to_dict() for r in self.results],
            "total_results": self.total_results,
            "offset": self.offset,
            "limit": self.limit,
            "has_more": self.offset + len(self.results) < self.total_results,
            "search_time_ms": self.search_time_ms,
        }


class SemanticSearchEngine:
    """
    Semantic search engine using vector embeddings and cosine similarity.

    Features:
    - Natural language query understanding via embeddings
    - Cosine similarity ranking for relevance
    - Metadata filtering (doc_type, issuer, date)
    - Relevance threshold filtering
    - Pagination for large result sets
    - Result highlighting with passage extraction
    - Performance tracking (search latency)

    Performance Targets:
    - P95 latency: <500ms for typical queries
    - Throughput: 10-20 queries/second
    - Cache hit rate: 80%+ for repeated queries
    """

    def __init__(self, session: Session, generator: EmbeddingGenerator):
        """
        Initialize semantic search engine.

        Args:
            session: SQLAlchemy session for database queries
            generator: EmbeddingGenerator for query embedding
        """
        self.session = session
        self.generator = generator

        logger.info("Initialized SemanticSearchEngine")

    def _compute_cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """
        Compute cosine similarity between two vectors.

        Cosine similarity = (A · B) / (||A|| * ||B||)

        Args:
            vec1: First embedding vector
            vec2: Second embedding vector

        Returns:
            Cosine similarity score (0.0 to 1.0)
        """
        if len(vec1) != len(vec2):
            raise ValueError(f"Vector dimension mismatch: {len(vec1)} != {len(vec2)}")

        # Dot product
        dot_product = sum(a * b for a, b in zip(vec1, vec2))

        # Magnitudes
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(b * b for b in vec2))

        if magnitude1 == 0.0 or magnitude2 == 0.0:
            return 0.0

        # Cosine similarity (normalized to 0-1 range)
        similarity = dot_product / (magnitude1 * magnitude2)

        # Clamp to [0, 1] (handle floating point errors)
        return max(0.0, min(1.0, similarity))

    def _apply_metadata_filters(self, base_query, filters: SearchQuery):
        """
        Apply metadata filters to SQLAlchemy query.

        Args:
            base_query: Base SQLAlchemy query object
            filters: SearchQuery with filter parameters

        Returns:
            Filtered query object
        """
        conditions = []

        # Filter by doc_type (exact match)
        if filters.doc_type_filter:
            conditions.append(
                Document.metadata_json.op("->>")("doc_type") == filters.doc_type_filter
            )

        # Filter by issuer (substring match, case-insensitive)
        if filters.issuer_filter:
            conditions.append(
                Document.metadata_json.op("->>")("issuer").ilike(
                    f"%{filters.issuer_filter}%"
                )
            )

        # Filter by date range
        if filters.date_from:
            conditions.append(
                Document.created_at
                >= datetime.combine(filters.date_from, datetime.min.time())
            )

        if filters.date_to:
            conditions.append(
                Document.created_at
                <= datetime.combine(filters.date_to, datetime.max.time())
            )

        if conditions:
            return base_query.filter(and_(*conditions))

        return base_query

    def _extract_highlighted_text(self, document: Document) -> str:
        """
        Extract relevant text passages from document for highlighting.

        Combines metadata fields into a concise summary.

        Args:
            document: Document to extract text from

        Returns:
            Highlighted text snippet (max 200 characters)
        """
        if not document.metadata_json:
            return document.original_filename

        parts = []

        # Add document type
        if doc_type := document.metadata_json.get("doc_type"):
            parts.append(f"[{doc_type}]")

        # Add issuer
        if issuer := document.metadata_json.get("issuer"):
            parts.append(f"from {issuer}")

        # Add summary (truncated)
        if summary := document.metadata_json.get("summary"):
            summary_truncated = summary[:150] + "..." if len(summary) > 150 else summary
            parts.append(f"- {summary_truncated}")

        highlighted = " ".join(parts) if parts else document.original_filename

        # Final truncation to 200 chars
        if len(highlighted) > 200:
            highlighted = highlighted[:197] + "..."

        return highlighted

    def search(self, query: SearchQuery) -> SearchResponse:
        """
        Perform semantic search for documents matching query.

        Workflow:
        1. Generate embedding for query text
        2. Retrieve candidate documents from database (with metadata filters)
        3. Compute cosine similarity for each candidate
        4. Filter by minimum similarity threshold
        5. Sort by similarity (descending)
        6. Apply pagination (offset + limit)
        7. Return results with metadata

        Args:
            query: SearchQuery with search parameters

        Returns:
            SearchResponse with ranked results

        Raises:
            ValueError: If query parameters are invalid
        """
        import time

        start_time = time.time()

        logger.info(
            f"Search query: '{query.text}' "
            f"(filters: doc_type={query.doc_type_filter}, "
            f"issuer={query.issuer_filter}, "
            f"min_similarity={query.min_similarity})"
        )

        # Step 1: Generate query embedding
        # Create a temporary document for embedding generation
        query_doc = Document(
            id=-1,  # Temporary ID
            sha256_hex="query",
            original_filename=query.text,
            metadata_json={
                "doc_type": "",
                "issuer": "",
                "summary": query.text,
            },
            status="completed",
        )

        query_result = self.generator.generate_embedding(query_doc)
        query_embedding = query_result.embedding

        logger.debug(f"Generated query embedding ({len(query_embedding)} dimensions)")

        # Step 2: Retrieve candidate documents with metadata filters
        base_query = self.session.query(Document).filter(
            Document.status == "completed",
            Document.embedding_vector.isnot(
                None
            ),  # Only documents with cached embeddings
        )

        filtered_query = self._apply_metadata_filters(base_query, query)
        candidates = filtered_query.all()

        logger.debug(f"Retrieved {len(candidates)} candidate documents")

        # Step 3-4: Compute similarities and filter by threshold
        results_with_scores: List[Tuple[Document, float]] = []

        for doc in candidates:
            doc_embedding = doc.embedding_vector

            # Compute similarity
            similarity = self._compute_cosine_similarity(query_embedding, doc_embedding)

            # Filter by threshold
            if similarity >= query.min_similarity:
                results_with_scores.append((doc, similarity))

        logger.debug(
            f"Filtered to {len(results_with_scores)} results "
            f"(min_similarity={query.min_similarity})"
        )

        # Step 5: Sort by similarity (descending)
        results_with_scores.sort(key=lambda x: x[1], reverse=True)

        # Step 6: Apply pagination
        total_results = len(results_with_scores)
        paginated = results_with_scores[query.offset : query.offset + query.limit]

        # Step 7: Create SearchResult objects with highlighting
        search_results = [
            SearchResult(
                document=doc,
                similarity_score=score,
                highlighted_text=self._extract_highlighted_text(doc),
                rank=query.offset + idx + 1,
            )
            for idx, (doc, score) in enumerate(paginated)
        ]

        # Calculate search time
        search_time_ms = (time.time() - start_time) * 1000

        logger.info(
            f"Search complete: {len(search_results)} results returned "
            f"(total: {total_results}, time: {search_time_ms:.1f}ms)"
        )

        return SearchResponse(
            query=query,
            results=search_results,
            total_results=total_results,
            offset=query.offset,
            limit=query.limit,
            search_time_ms=search_time_ms,
        )

    def search_by_document(
        self, document: Document, limit: int = 10, min_similarity: float = 0.7
    ) -> SearchResponse:
        """
        Find documents similar to a given document.

        Args:
            document: Source document for similarity search
            limit: Maximum results to return
            min_similarity: Minimum similarity threshold

        Returns:
            SearchResponse with similar documents
        """
        # Extract text from document for query
        text = self.generator.extract_text(document)

        query = SearchQuery(
            text=text,
            min_similarity=min_similarity,
            limit=limit,
        )

        return self.search(query)
