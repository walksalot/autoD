"""
SQLAlchemy 2.0 database models for Paper Autopilot.

Simplified Document model with 10 core fields per CODE_ARCHITECTURE.md.
Uses generic JSON type (NOT JSONB) for cross-database compatibility.

Design Decisions:
- 10 fields only (no token tracking - that's Workstream 3)
- Generic JSON type works on SQLite AND PostgreSQL
- Full API response stored in metadata_json (nothing lost)
- Can extract specific fields later via migrations
- Simple to test and validate
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy import String, DateTime, Text, JSON, Integer, create_engine, BigInteger
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    Session,
    sessionmaker,
)


class Base(DeclarativeBase):
    """Base class for all database models."""

    # Use generic JSON type for cross-database compatibility
    # This works on both SQLite and PostgreSQL
    type_annotation_map = {Dict[str, Any]: JSON}


class Document(Base):
    """
    Document model storing PDF metadata extracted by OpenAI Responses API.

    Simplified schema (10 fields) with full API response in JSON blob.
    Token tracking removed (Workstream 3 concern).

    Fields:
        id: Primary key
        sha256_hex: SHA-256 hash for deduplication (unique constraint + index)
        original_filename: Original PDF filename
        created_at: UTC timestamp when document discovered
        processed_at: UTC timestamp when processing completed successfully
        source_file_id: OpenAI Files API file ID
        vector_store_file_id: OpenAI vector store file ID (optional, Workstream 4)
        metadata_json: Full structured output from Responses API (JSON blob)
        embedding_cache_key: SHA-256 hash of text used for embedding
        embedding_vector: Cached embedding vector (1536 floats)
        embedding_model: OpenAI model used for embedding
        embedding_generated_at: Timestamp when embedding was generated
        status: Processing status (pending|processing|completed|failed)
        error_message: Error message if status is failed

    Example:
        doc = Document(
            sha256_hex="abc123...",
            original_filename="invoice.pdf",
            source_file_id="file-xyz789...",
            metadata_json={"doc_type": "Invoice", "issuer": "ACME Corp", ...},
            status="completed"
        )
        session.add(doc)
        session.commit()
    """

    __tablename__ = "documents"

    # === Primary Key ===
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # === File Identification (Deduplication) ===
    sha256_hex: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
        comment="SHA-256 hash in hexadecimal format for deduplication",
    )

    sha256_base64: Mapped[Optional[str]] = mapped_column(
        String(88),
        nullable=True,
        comment="SHA-256 hash encoded in base64 (useful for OpenAI attributes)",
    )

    original_filename: Mapped[str] = mapped_column(
        String(512),
        nullable=False,
        comment="Original PDF filename from inbox",
    )

    file_size_bytes: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        comment="Size of the PDF file in bytes",
    )

    page_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Number of pages in the PDF document",
    )

    # === Timestamps ===
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="UTC timestamp when document was first discovered",
    )

    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="UTC timestamp when processing completed successfully",
    )

    # === OpenAI References ===
    source_file_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        index=True,
        nullable=True,
        comment="OpenAI file ID from Files API upload",
    )

    vector_store_file_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        index=True,
        nullable=True,
        comment="OpenAI vector store file ID for cross-document search (Workstream 4)",
    )

    # === Extracted Metadata (Full JSON Response) ===
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,  # ← Generic JSON type, works on SQLite AND PostgreSQL (NOT JSONB)
        nullable=True,
        comment="Full structured output from OpenAI Responses API",
    )

    # === Embedding Cache (Workstream 1) ===
    embedding_cache_key: Mapped[Optional[str]] = mapped_column(
        String(64),
        index=True,
        nullable=True,
        comment="SHA-256 hash of text used for embedding (for cache invalidation)",
    )

    embedding_vector: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Cached embedding vector (list of 1536 floats) to avoid regeneration",
    )

    embedding_model: Mapped[Optional[str]] = mapped_column(
        String(64),
        nullable=True,
        comment="OpenAI model used to generate embedding (e.g., text-embedding-3-small)",
    )

    embedding_generated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="UTC timestamp when embedding was generated",
    )

    # === Status Tracking ===
    status: Mapped[str] = mapped_column(
        String(32),
        default="pending",
        index=True,
        nullable=False,
        comment="Processing status: pending|processing|completed|failed|vector_upload_failed",
    )

    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if status is failed",
    )

    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"<Document id={self.id} "
            f"filename={self.original_filename!r} "
            f"status={self.status!r}>"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary for serialization."""
        return {
            "id": self.id,
            "sha256_hex": self.sha256_hex,
            "sha256_base64": self.sha256_base64,
            "original_filename": self.original_filename,
            "file_size_bytes": self.file_size_bytes,
            "page_count": self.page_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "processed_at": (
                self.processed_at.isoformat() if self.processed_at else None
            ),
            "source_file_id": self.source_file_id,
            "vector_store_file_id": self.vector_store_file_id,
            "metadata_json": self.metadata_json,
            "embedding_cache_key": self.embedding_cache_key,
            "embedding_vector": self.embedding_vector,
            "embedding_model": self.embedding_model,
            "embedding_generated_at": (
                self.embedding_generated_at.isoformat()
                if self.embedding_generated_at
                else None
            ),
            "status": self.status,
            "error_message": self.error_message,
        }


def init_db(db_url: str) -> Session:
    """
    Initialize database and return session factory.

    Creates all tables if they don't exist (development mode).
    In production, use Alembic migrations instead.

    Args:
        db_url: SQLAlchemy database URL
                Examples:
                - "sqlite:///paper_autopilot.db" (SQLite)
                - "postgresql://user:pass@localhost/paper_autopilot" (PostgreSQL)

    Returns:
        SQLAlchemy session instance

    Example:
        session = init_db("sqlite:///paper_autopilot.db")
        doc = session.query(Document).first()
        print(doc)
    """
    engine = create_engine(db_url, future=True, echo=False)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, future=True)
    return SessionLocal()
