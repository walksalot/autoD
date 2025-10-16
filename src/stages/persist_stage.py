"""
Database persistence stage.

Creates Document record in database with all extracted metadata.
This is the final stage in the pipeline that commits the processed document.
"""

from src.pipeline import ProcessingStage, ProcessingContext
from src.models import Document
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


class PersistToDBStage(ProcessingStage):
    """
    Save document record to database.

    Outputs:
        context.document_id: Database ID of created document

    Example:
        session = init_db("sqlite:///paper_autopilot.db")
        stage = PersistToDBStage(session)

        context = ProcessingContext(
            pdf_path=Path("inbox/sample.pdf"),
            sha256_hex="abc123...",
            file_id="file-xyz789...",
            metadata_json={"doc_type": "Invoice", ...}
        )
        result = stage.execute(context)

        print(result.document_id)  # 42
    """

    def __init__(self, session: Session):
        """
        Initialize persistence stage with database session.

        Args:
            session: SQLAlchemy session for writing to documents table
        """
        self.session = session

    def execute(self, context: ProcessingContext) -> ProcessingContext:
        """
        Create Document record in database.

        Args:
            context: Processing context with all fields populated

        Returns:
            Updated context with document_id set

        Raises:
            ValueError: If required fields not set
            sqlalchemy.exc.IntegrityError: If duplicate sha256_hex (shouldn't happen if dedupe ran)
        """
        # Validate required fields
        if not context.sha256_hex:
            raise ValueError("sha256_hex not set")
        if not context.file_id:
            raise ValueError("file_id not set")

        logger.info(
            f"Creating database record",
            extra={
                "pdf_path": str(context.pdf_path),
                "sha256_hex": context.sha256_hex,
                "file_id": context.file_id,
            },
        )

        # Create Document record
        doc = Document(
            sha256_hex=context.sha256_hex,
            original_filename=context.pdf_path.name,
            created_at=datetime.now(timezone.utc),
            processed_at=datetime.now(timezone.utc),
            source_file_id=context.file_id,
            vector_store_file_id=None,  # Will be populated in Workstream 4
            metadata_json=context.metadata_json or {},
            status="completed",
            error_message=None,
        )

        # Add and commit
        self.session.add(doc)
        self.session.commit()

        # Store document ID in context
        context.document_id = doc.id

        logger.info(
            f"Database record created",
            extra={
                "pdf_path": str(context.pdf_path),
                "document_id": doc.id,
                "doc_type": context.metadata_json.get("doc_type") if context.metadata_json else None,
            },
        )

        return context
