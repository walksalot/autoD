"""
Deduplication check stage.

Queries database to check if document with same SHA-256 hash already exists.
If duplicate found, sets context.is_duplicate=True and pipeline will skip
remaining processing stages.

This prevents reprocessing the same document multiple times and saves API costs.
"""

from src.pipeline import ProcessingStage, ProcessingContext
from src.models import Document
from sqlalchemy.orm import Session


class DedupeCheckStage(ProcessingStage):
    """
    Check if document already exists in database (by SHA-256 hash).

    Outputs:
        context.is_duplicate: True if document exists, False otherwise
        context.existing_doc_id: ID of existing document (if duplicate)
        context.metrics['is_duplicate']: Same as is_duplicate

    Example:
        session = init_db("sqlite:///paper_autopilot.db")
        stage = DedupeCheckStage(session)

        context = ProcessingContext(
            pdf_path=Path("inbox/sample.pdf"),
            sha256_hex="abc123..."
        )
        result = stage.execute(context)

        if result.is_duplicate:
            print(f"Duplicate of document {result.existing_doc_id}")
        else:
            print("New document, proceed with processing")
    """

    def __init__(self, session: Session):
        """
        Initialize deduplication stage with database session.

        Args:
            session: SQLAlchemy session for querying documents table
        """
        self.session = session

    def execute(self, context: ProcessingContext) -> ProcessingContext:
        """
        Query database for existing document with same SHA-256 hash.

        Args:
            context: Processing context with sha256_hex populated

        Returns:
            Updated context with is_duplicate and existing_doc_id set

        Raises:
            ValueError: If sha256_hex not set (previous stage failed)
        """
        if not context.sha256_hex:
            raise ValueError("sha256_hex not set - ComputeSHA256Stage must run first")

        # Query for existing document
        existing = (
            self.session.query(Document)
            .filter_by(sha256_hex=context.sha256_hex)
            .first()
        )

        if existing:
            context.is_duplicate = True
            context.existing_doc_id = existing.id
        else:
            context.is_duplicate = False
            context.existing_doc_id = None

        # Track in metrics
        context.metrics["is_duplicate"] = context.is_duplicate

        return context
