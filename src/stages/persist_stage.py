"""
Database persistence stage.

Creates Document record in database with all extracted metadata.
This is the final stage in the pipeline that commits the processed document.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session
from openai import OpenAI

from src.models import Document
from src.pipeline import ProcessingContext, ProcessingStage
from src.transactions import compensating_transaction
from src.cleanup_handlers import cleanup_files_api_upload, cleanup_vector_store_upload

logger = logging.getLogger(__name__)


class PersistToDBStage(ProcessingStage):
    """
    Save document record to database with compensating transactions.

    Outputs:
        context.document_id: Database ID of created document
        context.audit_trail: Transaction audit information

    Example:
        from openai import OpenAI
        session = init_db("sqlite:///paper_autopilot.db")
        client = OpenAI(api_key="sk-...")
        stage = PersistToDBStage(session, client)

        context = ProcessingContext(
            pdf_path=Path("inbox/sample.pdf"),
            sha256_hex="abc123...",
            file_id="file-xyz789...",
            metadata_json={"doc_type": "Invoice", ...}
        )
        result = stage.execute(context)

        print(result.document_id)  # 42
        print(result.audit_trail)  # {'status': 'success', ...}
    """

    def __init__(self, session: Session, openai_client: Optional[OpenAI] = None):
        """
        Initialize persistence stage with database session and OpenAI client.

        Args:
            session: SQLAlchemy session for writing to documents table
            openai_client: Optional OpenAI client for cleanup operations
        """
        self.session = session
        self.client = openai_client

    def execute(self, context: ProcessingContext) -> ProcessingContext:
        """
        Create Document record in database with compensating transaction.

        If database commit fails after file uploads, cleanup handlers will:
        - Delete the uploaded file from Files API
        - Remove the file from vector store (if applicable)

        Args:
            context: Processing context with all fields populated

        Returns:
            Updated context with document_id and audit_trail set

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
            raise ValueError(
                "metadata_json not set - CallResponsesAPIStage must run first"
            )

        logger.info(
            "Creating database record",
            extra={
                "pdf_path": str(context.pdf_path),
                "sha256_hex": context.sha256_hex,
                "file_id": context.file_id,
            },
        )

        # Setup audit trail for transaction
        audit_trail = {
            "stage": "PersistToDBStage",
            "pdf_path": str(context.pdf_path),
            "sha256_hex": context.sha256_hex,
            "file_id": context.file_id,
        }

        # Define cleanup function for compensating transaction
        def cleanup():
            """Cleanup external resources if database commit fails."""
            if self.client and context.file_id:
                cleanup_files_api_upload(self.client, context.file_id)

            if self.client and context.vector_store_file_id and context.vector_store_id:
                cleanup_vector_store_upload(
                    self.client, context.vector_store_id, context.vector_store_file_id
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

        # Use compensating transaction to ensure cleanup on failure
        with compensating_transaction(
            self.session, compensate_fn=cleanup, audit_trail=audit_trail
        ):
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

            self.session.add(doc)
            # Commit happens in context manager

        # Store results in context (only reached if commit succeeded)
        context.document_id = doc.id
        context.audit_trail = audit_trail

        logger.info(
            "Database record created",
            extra={
                "pdf_path": str(context.pdf_path),
                "document_id": doc.id,
                "doc_type": (
                    context.metadata_json.get("doc_type")
                    if context.metadata_json
                    else None
                ),
                "audit_trail": audit_trail,
            },
        )

        return context
