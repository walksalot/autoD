"""
Semantic search engine for document retrieval using OpenAI embeddings.

Provides semantic search with:
- Query embedding with 3-tier caching (memory → DB → API)
- Vectorized cosine similarity computation (NumPy)
- Metadata filtering (doc_type, issuer, date_range)
- Result ranking and pagination
- Performance optimization (batch loading, early filtering)

Architecture:
- SemanticSearchEngine: Main search class
- SearchResult: Individual result with score and rank
- SearchResults: Complete search response with metadata

Usage:
    from openai import OpenAI
    from src.embeddings import EmbeddingGenerator
    from src.search import SemanticSearchEngine
    from src.models import init_db

    # Initialize
    client = OpenAI(api_key="sk-...")
    session = init_db("sqlite:///app.db")
    generator = EmbeddingGenerator(client, session)
    search_engine = SemanticSearchEngine(generator, session)

    # Search
    results = search_engine.search(
        query="invoices from ACME Corp in 2024",
        filters={"doc_type": "Invoice", "issuer": "ACME"},
        limit=10
    )

    print(f"Found {results.total_count} results in {results.execution_time_ms}ms")
    for result in results.results:
        print(f"{result.rank}. {result.document.original_filename} "
              f"({result.similarity_score:.2f})")
"""

import logging
import time
from typing import List, Dict, Optional, Any
from dataclasses import dataclass

import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import and_

from src.embeddings import EmbeddingGenerator, EmbeddingResult
from src.models import Document
from src.config import get_config

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Individual search result with document, score, and rank.

    Attributes:
        document: Document model instance
        similarity_score: Cosine similarity score (0.0-1.0)
        rank: Result position in ranked list (1-based)
    """

    document: Document
    similarity_score: float
    rank: int


@dataclass
class SearchResults:
    """Complete search response with results and metadata.

    Attributes:
        results: List of SearchResult objects (ranked by similarity)
        total_count: Total number of matching documents (before pagination)
        query: Original search query text
        execution_time_ms: Query execution time in milliseconds
        cache_hit: Whether query embedding was retrieved from cache
        filters_applied: Filters used for this search
    """

    results: List[SearchResult]
    total_count: int
    query: str
    execution_time_ms: float
    cache_hit: bool
    filters_applied: Optional[Dict[str, Any]] = None


class SemanticSearchEngine:
    """Semantic search engine for document retrieval.

    Features:
    - Query embedding with 3-tier caching (memory → DB → API)
    - Vectorized cosine similarity computation (NumPy)
    - Metadata filtering (doc_type, issuer, date_range)
    - Result ranking by similarity score
    - Pagination support (limit + offset)
    - Performance optimization (batch loading, early filtering)

    Performance Targets:
    - P95 latency: <500ms for 10-result queries
    - Query cache hit rate: 80%+ for repeated queries
    - Vectorized operations: NumPy-accelerated similarity

    Example:
        >>> search_engine = SemanticSearchEngine(generator, session)
        >>> results = search_engine.search(
        ...     query="utility bills from January 2024",
        ...     filters={"doc_type": "UtilityBill", "date_range": {"start": "2024-01-01"}},
        ...     limit=5
        ... )
        >>> print(f"Found {len(results.results)} documents")
    """

    def __init__(
        self,
        embedding_generator: EmbeddingGenerator,
        session: Session,
        min_similarity: Optional[float] = None,
    ):
        """Initialize semantic search engine.

        Args:
            embedding_generator: EmbeddingGenerator instance for query embeddings
            session: SQLAlchemy session for database queries
            min_similarity: Minimum cosine similarity threshold for results
                           (default: from config.search_relevance_threshold)
        """
        self.embedding_generator = embedding_generator
        self.session = session

        config = get_config()
        self.min_similarity = (
            min_similarity
            if min_similarity is not None
            else config.search_relevance_threshold
        )

        logger.info(
            f"Initialized SemanticSearchEngine: "
            f"min_similarity={self.min_similarity:.2f}"
        )

    def _compute_similarities(
        self, query_embedding: List[float], document_embeddings: List[List[float]]
    ) -> np.ndarray:
        """Compute cosine similarity between query and documents (vectorized).

        Uses NumPy for efficient batch computation of cosine similarity:
        similarity = (A · B) / (||A|| * ||B||)

        Args:
            query_embedding: Query embedding vector (1536 dimensions)
            document_embeddings: List of document embedding vectors

        Returns:
            NumPy array of similarity scores (0.0-1.0)
        """
        if not document_embeddings:
            return np.array([])

        # Convert to NumPy arrays
        query_vec = np.array(query_embedding, dtype=np.float32)
        doc_matrix = np.array(document_embeddings, dtype=np.float32)

        # Normalize vectors (L2 normalization)
        query_norm = query_vec / np.linalg.norm(query_vec)
        doc_norms = doc_matrix / np.linalg.norm(doc_matrix, axis=1, keepdims=True)

        # Compute cosine similarity (dot product of normalized vectors)
        similarities = np.dot(doc_norms, query_norm)

        return similarities

    def _apply_metadata_filters(
        self, query: Any, filters: Optional[Dict[str, Any]]
    ) -> Any:
        """Apply metadata filters to SQLAlchemy query.

        Supported filters:
        - doc_type: Exact match or list of types
          Examples: {"doc_type": "Invoice"}, {"doc_type": ["Invoice", "Receipt"]}
        - issuer: Case-insensitive substring match
          Example: {"issuer": "ACME"}
        - date_range: Filter by primary_date field
          Example: {"date_range": {"start": "2024-01-01", "end": "2024-12-31"}}

        Args:
            query: SQLAlchemy query object
            filters: Filter dictionary (None for no filters)

        Returns:
            Filtered SQLAlchemy query object
        """
        if not filters:
            return query

        filter_conditions = []

        # Filter by doc_type (exact match or list)
        if "doc_type" in filters:
            doc_type = filters["doc_type"]
            if isinstance(doc_type, list):
                # Multiple types (OR condition)
                filter_conditions.append(
                    Document.metadata_json["doc_type"].astext.in_(doc_type)
                )
            else:
                # Single type
                filter_conditions.append(
                    Document.metadata_json["doc_type"].astext == doc_type
                )

        # Filter by issuer (case-insensitive substring)
        if "issuer" in filters:
            issuer = filters["issuer"]
            # Use ILIKE for case-insensitive substring match (PostgreSQL)
            # SQLite: Use LIKE (case-insensitive by default for ASCII)
            filter_conditions.append(
                Document.metadata_json["issuer"].astext.ilike(f"%{issuer}%")
            )

        # Filter by date_range (primary_date field)
        if "date_range" in filters:
            date_range = filters["date_range"]

            # Start date (inclusive)
            if "start" in date_range:
                start_date = date_range["start"]
                filter_conditions.append(
                    Document.metadata_json["primary_date"].astext >= start_date
                )

            # End date (inclusive)
            if "end" in date_range:
                end_date = date_range["end"]
                filter_conditions.append(
                    Document.metadata_json["primary_date"].astext <= end_date
                )

        # Apply all filters (AND condition)
        if filter_conditions:
            query = query.filter(and_(*filter_conditions))

        return query

    def _create_temporary_document(self, query: str) -> Document:
        """Create a temporary Document object from query text.

        This allows us to reuse EmbeddingGenerator's caching logic for queries.

        Args:
            query: Natural language search query

        Returns:
            Temporary Document instance (not persisted to database)
        """
        # Create temporary document with query as metadata
        temp_doc = Document(
            sha256_hex="query_temp",  # Not used for cache lookup
            original_filename="query",  # Not persisted
            metadata_json={
                "doc_type": "Query",
                "issuer": "",
                "summary": query,
            },
            status="completed",
        )

        return temp_doc

    def search(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10,
        offset: int = 0,
    ) -> SearchResults:
        """Perform semantic search with metadata filtering.

        Workflow:
        1. Generate query embedding (with caching)
        2. Apply metadata filters to narrow candidates
        3. Load document embeddings (batch query)
        4. Compute cosine similarities (vectorized NumPy)
        5. Filter by similarity threshold
        6. Rank results by score
        7. Apply pagination

        Args:
            query: Natural language search query
            filters: Optional metadata filters:
                - doc_type: str or List[str] (exact match)
                - issuer: str (case-insensitive substring)
                - date_range: Dict[str, str] with "start" and/or "end" (ISO dates)
            limit: Maximum number of results to return (default: 10)
            offset: Pagination offset (default: 0)

        Returns:
            SearchResults with ranked documents and metadata

        Raises:
            ValueError: If query is empty or limit/offset are invalid

        Examples:
            >>> # Basic search
            >>> results = search_engine.search("utility bills")
            >>> print(f"Found {len(results.results)} results")

            >>> # Search with filters
            >>> results = search_engine.search(
            ...     query="invoices",
            ...     filters={
            ...         "doc_type": "Invoice",
            ...         "issuer": "ACME",
            ...         "date_range": {"start": "2024-01-01", "end": "2024-12-31"}
            ...     },
            ...     limit=5
            ... )

            >>> # Multiple doc types
            >>> results = search_engine.search(
            ...     query="financial documents",
            ...     filters={"doc_type": ["Invoice", "Receipt", "BankStatement"]}
            ... )
        """
        start_time = time.time()

        # Validate inputs
        if not query.strip():
            raise ValueError("Search query cannot be empty")
        if limit < 1:
            raise ValueError(f"Limit must be >= 1, got {limit}")
        if offset < 0:
            raise ValueError(f"Offset must be >= 0, got {offset}")

        config = get_config()
        if limit > config.search_max_top_k:
            raise ValueError(f"Limit {limit} exceeds maximum {config.search_max_top_k}")

        logger.info(
            f"Search query: '{query}', filters={filters}, limit={limit}, offset={offset}"
        )

        # Step 1: Generate query embedding (with caching)
        temp_doc = self._create_temporary_document(query)
        embedding_result: EmbeddingResult = self.embedding_generator.generate_embedding(
            temp_doc
        )
        query_embedding = embedding_result.embedding
        cache_hit = embedding_result.cached

        logger.debug(
            f"Query embedding generated: cached={cache_hit}, "
            f"dimensions={len(query_embedding)}"
        )

        # Step 2: Build base query with filters (early filtering)
        base_query = self.session.query(Document).filter(
            Document.status == "completed",
            Document.embedding_vector.isnot(None),  # Only documents with embeddings
        )

        # Apply metadata filters BEFORE loading embeddings (efficiency)
        filtered_query = self._apply_metadata_filters(base_query, filters)

        # Get total count for pagination metadata
        total_count = filtered_query.count()

        if total_count == 0:
            logger.info("No documents match filters")
            execution_time = (time.time() - start_time) * 1000
            return SearchResults(
                results=[],
                total_count=0,
                query=query,
                execution_time_ms=execution_time,
                cache_hit=cache_hit,
                filters_applied=filters,
            )

        # Step 3: Load documents with embeddings (batch query)
        # Note: We load ALL filtered documents (no SQL pagination yet)
        # because we need to compute similarity scores before ranking
        documents = filtered_query.all()

        logger.debug(f"Loaded {len(documents)} documents with embeddings")

        # Step 4: Extract embeddings for similarity computation
        document_embeddings = [doc.embedding_vector for doc in documents]

        # Step 5: Compute cosine similarities (vectorized NumPy)
        similarities = self._compute_similarities(query_embedding, document_embeddings)

        logger.debug(
            f"Computed similarities: min={similarities.min():.3f}, "
            f"max={similarities.max():.3f}, mean={similarities.mean():.3f}"
        )

        # Step 6: Filter by similarity threshold
        mask = similarities >= self.min_similarity
        filtered_docs = [doc for doc, keep in zip(documents, mask) if keep]
        filtered_scores = similarities[mask]

        logger.debug(
            f"Filtered {len(filtered_docs)}/{len(documents)} documents "
            f"above threshold {self.min_similarity:.2f}"
        )

        if len(filtered_docs) == 0:
            logger.info(
                f"No documents above similarity threshold {self.min_similarity:.2f}"
            )
            execution_time = (time.time() - start_time) * 1000
            return SearchResults(
                results=[],
                total_count=0,
                query=query,
                execution_time_ms=execution_time,
                cache_hit=cache_hit,
                filters_applied=filters,
            )

        # Step 7: Sort by similarity score (descending)
        sorted_indices = np.argsort(-filtered_scores)  # Negative for descending
        sorted_docs = [filtered_docs[i] for i in sorted_indices]
        sorted_scores = [filtered_scores[i] for i in sorted_indices]

        # Step 8: Apply pagination
        paginated_docs = sorted_docs[offset : offset + limit]
        paginated_scores = sorted_scores[offset : offset + limit]

        logger.debug(
            f"Pagination applied: offset={offset}, limit={limit}, "
            f"returned={len(paginated_docs)}"
        )

        # Step 9: Create SearchResult objects with ranks
        results = [
            SearchResult(
                document=doc, similarity_score=float(score), rank=offset + i + 1
            )
            for i, (doc, score) in enumerate(zip(paginated_docs, paginated_scores))
        ]

        # Calculate execution time
        execution_time = (time.time() - start_time) * 1000

        logger.info(
            f"Search complete: {len(results)} results, "
            f"{execution_time:.1f}ms, cache_hit={cache_hit}"
        )

        return SearchResults(
            results=results,
            total_count=len(filtered_docs),  # Total after threshold filtering
            query=query,
            execution_time_ms=execution_time,
            cache_hit=cache_hit,
            filters_applied=filters,
        )

    def search_by_document(
        self,
        document: Document,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10,
        exclude_self: bool = True,
    ) -> SearchResults:
        """Find similar documents to a given document.

        Uses the document's cached embedding for similarity search.
        Useful for "find similar" features.

        Args:
            document: Source document to find similar documents for
            filters: Optional metadata filters (same as search())
            limit: Maximum number of results to return
            exclude_self: Whether to exclude the source document from results

        Returns:
            SearchResults with similar documents

        Raises:
            ValueError: If document has no embedding

        Example:
            >>> doc = session.query(Document).first()
            >>> similar = search_engine.search_by_document(doc, limit=5)
            >>> for result in similar.results:
            ...     print(f"Similar: {result.document.original_filename}")
        """
        if not document.embedding_vector:
            raise ValueError(
                f"Document {document.id} has no embedding. "
                "Generate embedding first using EmbeddingGenerator."
            )

        start_time = time.time()

        logger.info(
            f"Searching for documents similar to: {document.original_filename} "
            f"(id={document.id})"
        )

        # Use document's embedding directly (already cached in DB)
        query_embedding = document.embedding_vector

        # Build query with filters (exclude source document if requested)
        base_query = self.session.query(Document).filter(
            Document.status == "completed",
            Document.embedding_vector.isnot(None),
        )

        if exclude_self:
            base_query = base_query.filter(Document.id != document.id)

        # Apply metadata filters
        filtered_query = self._apply_metadata_filters(base_query, filters)
        documents = filtered_query.all()

        if not documents:
            execution_time = (time.time() - start_time) * 1000
            return SearchResults(
                results=[],
                total_count=0,
                query=f"Similar to: {document.original_filename}",
                execution_time_ms=execution_time,
                cache_hit=True,  # Used cached embedding from DB
                filters_applied=filters,
            )

        # Compute similarities
        document_embeddings = [doc.embedding_vector for doc in documents]
        similarities = self._compute_similarities(query_embedding, document_embeddings)

        # Filter by threshold and sort
        mask = similarities >= self.min_similarity
        filtered_docs = [doc for doc, keep in zip(documents, mask) if keep]
        filtered_scores = similarities[mask]

        if len(filtered_docs) == 0:
            execution_time = (time.time() - start_time) * 1000
            return SearchResults(
                results=[],
                total_count=0,
                query=f"Similar to: {document.original_filename}",
                execution_time_ms=execution_time,
                cache_hit=True,
                filters_applied=filters,
            )

        # Sort and paginate
        sorted_indices = np.argsort(-filtered_scores)
        sorted_docs = [filtered_docs[i] for i in sorted_indices[:limit]]
        sorted_scores = [filtered_scores[i] for i in sorted_indices[:limit]]

        # Create results
        results = [
            SearchResult(document=doc, similarity_score=float(score), rank=i + 1)
            for i, (doc, score) in enumerate(zip(sorted_docs, sorted_scores))
        ]

        execution_time = (time.time() - start_time) * 1000

        logger.info(f"Found {len(results)} similar documents in {execution_time:.1f}ms")

        return SearchResults(
            results=results,
            total_count=len(filtered_docs),
            query=f"Similar to: {document.original_filename}",
            execution_time_ms=execution_time,
            cache_hit=True,
            filters_applied=filters,
        )
