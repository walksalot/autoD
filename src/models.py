"""
SQLAlchemy 2.0 database models for Paper Autopilot.
Document model with 40+ fields for comprehensive metadata tracking.
"""

from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import (
    String, Integer, Float, DateTime, Boolean, Text, JSON,
    Index, CheckConstraint,
    create_engine
)
from sqlalchemy.orm import (
    DeclarativeBase, Mapped, mapped_column, Session
)
from sqlalchemy.dialects.postgresql import JSONB


class Base(DeclarativeBase):
    """Base class for all database models."""

    # Use JSONB for PostgreSQL, JSON for SQLite
    type_annotation_map = {
        Dict[str, Any]: JSON
    }


class Document(Base):
    """
    Document model storing PDF metadata extracted by OpenAI Responses API.

    This model tracks comprehensive information about processed documents including:
    - File identification (SHA-256 hashes, filenames)
    - Document metadata (type, issuer, dates, amounts)
    - Processing metadata (API usage, timestamps, costs)
    - Business intelligence (action items, deadlines, urgency)
    - Technical metadata (vector store integration, OCR excerpts)
    """

    __tablename__ = "documents"

    # === Primary Key ===
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # === File Identification ===
    sha256_hex: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        index=True,
        nullable=False,
        comment="SHA-256 hash of file (hex encoding) for deduplication"
    )

    sha256_base64: Mapped[str] = mapped_column(
        String(44),
        index=True,
        nullable=False,
        comment="SHA-256 hash of file (base64 encoding) for vector store"
    )

    original_filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Original PDF filename"
    )

    file_size_bytes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="File size in bytes"
    )

    page_count: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Number of pages in PDF"
    )

    # === Document Classification ===
    doc_type: Mapped[Optional[str]] = mapped_column(
        String(100),
        index=True,
        nullable=True,
        comment="Document type (e.g., Invoice, Receipt, BankStatement, Contract)"
    )

    doc_subtype: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Document subtype for granular classification"
    )

    confidence_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Model confidence score for classification (0.0-1.0)"
    )

    # === Document Metadata ===
    issuer: Mapped[Optional[str]] = mapped_column(
        String(255),
        index=True,
        nullable=True,
        comment="Organization or person who issued the document"
    )

    recipient: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Intended recipient of the document"
    )

    primary_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        index=True,
        nullable=True,
        comment="Primary date from document (e.g., invoice date, statement date)"
    )

    secondary_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="Secondary date (e.g., due date, payment date)"
    )

    total_amount: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Total monetary amount from document"
    )

    currency: Mapped[Optional[str]] = mapped_column(
        String(3),
        nullable=True,
        comment="Currency code (ISO 4217, e.g., USD, EUR)"
    )

    # === Business Intelligence ===
    summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Brief summary of document (≤200 words)"
    )

    action_items: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Extracted action items as JSON array"
    )

    deadlines: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Important deadlines as JSON array"
    )

    urgency_level: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Urgency assessment (low, medium, high, critical)"
    )

    tags: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="User-defined or auto-generated tags as JSON array"
    )

    # === Technical Metadata ===
    ocr_text_excerpt: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="First 500 characters of extracted text for search"
    )

    language_detected: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
        comment="Detected language code (ISO 639-1)"
    )

    # === Vector Store Integration ===
    vector_store_file_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="OpenAI vector store file ID"
    )

    vector_store_attributes: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Metadata attributes stored with vector (max 16 key-value pairs)"
    )

    # === Processing Metadata ===
    processed_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        index=True,
        nullable=False,
        comment="Timestamp when document was processed"
    )

    processing_duration_seconds: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Time taken to process document (seconds)"
    )

    # === API Usage Tracking ===
    model_used: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="OpenAI model used for extraction (e.g., gpt-5-mini)"
    )

    prompt_tokens: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Number of input tokens used"
    )

    completion_tokens: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Number of output tokens used"
    )

    cached_tokens: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Number of cached input tokens (from prompt caching)"
    )

    total_cost_usd: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Total cost for API call (USD)"
    )

    # === Quality & Validation ===
    extraction_quality: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Quality assessment (excellent, good, fair, poor)"
    )

    validation_errors: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="JSON schema validation errors (if any)"
    )

    requires_review: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        index=True,
        nullable=False,
        comment="Flag indicating manual review needed"
    )

    # === Full API Response (for debugging) ===
    raw_response_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Complete API response for debugging (optional)"
    )

    # === Audit Trail ===
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
        comment="Record creation timestamp"
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
        comment="Record last update timestamp"
    )

    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="Soft delete timestamp (NULL = active record)"
    )

    # === Indexes ===
    __table_args__ = (
        Index("idx_doc_type_date", "doc_type", "primary_date"),
        Index("idx_issuer_date", "issuer", "primary_date"),
        Index("idx_processed_at", "processed_at"),
        Index("idx_requires_review", "requires_review"),
        Index("idx_deleted_at", "deleted_at"),
        CheckConstraint("file_size_bytes > 0", name="check_file_size_positive"),
        CheckConstraint("page_count > 0 OR page_count IS NULL", name="check_page_count_positive"),
    )

    def __repr__(self) -> str:
        return (
            f"<Document(id={self.id}, "
            f"filename='{self.original_filename}', "
            f"type='{self.doc_type}', "
            f"issuer='{self.issuer}', "
            f"date={self.primary_date})>"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary for serialization."""
        return {
            "id": self.id,
            "sha256_hex": self.sha256_hex,
            "original_filename": self.original_filename,
            "doc_type": self.doc_type,
            "issuer": self.issuer,
            "primary_date": self.primary_date.isoformat() if self.primary_date else None,
            "total_amount": self.total_amount,
            "currency": self.currency,
            "summary": self.summary,
            "processed_at": self.processed_at.isoformat(),
            "model_used": self.model_used,
            "total_cost_usd": self.total_cost_usd,
        }
