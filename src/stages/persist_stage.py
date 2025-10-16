"""
Database persistence stage.

Creates Document record in database with all extracted metadata.
This is the final stage in the pipeline that commits the processed document.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.models import Document
from src.pipeline import ProcessingContext, ProcessingStage
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
        if context.metadata_json is None:
            raise ValueError("metadata_json not set - CallResponsesAPIStage must run first")

        logger.info(
            f"Creating database record",
            extra={
                "pdf_path": str(context.pdf_path),
                "sha256_hex": context.sha256_hex,
                "file_id": context.file_id,
            },
        )

        metadata = context.metadata_json
        processed_date_str = metadata.get("processed_date")
        processed_dt = None
        if processed_date_str:
            try:
                iso_str = processed_date_str.replace("Z", "+00:00")
                processed_dt = datetime.fromisoformat(iso_str)
            except ValueError:
                logger.warning(
                    "Unable to parse processed_date '%s'; defaulting to now.",
                    processed_date_str,
                    extra={"pdf_path": str(context.pdf_path)},
                )
                processed_dt = datetime.now(timezone.utc)
        else:
            processed_dt = datetime.now(timezone.utc)

        # Create Document record
        doc = Document(
            sha256_hex=context.sha256_hex,
            sha256_base64=context.sha256_base64,
            original_filename=context.pdf_path.name,
            file_size_bytes=context.metrics.get("file_size_bytes"),
            created_at=datetime.now(timezone.utc),
            processed_at=processed_dt,
            source_file_id=context.source_file_id or context.file_id,
            vector_store_file_id=context.vector_store_file_id,
            metadata_json=metadata,
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
