"""
OpenAI Files API upload stage.

Uploads PDF file to OpenAI Files API which returns a file_id.
This file_id is required for the Responses API call in the next stage.

Files are uploaded with purpose="assistants" to make them available
for the Responses API.
"""

import logging
from datetime import datetime, timezone

from openai import OpenAI

from src.pipeline import ProcessingContext, ProcessingStage

logger = logging.getLogger(__name__)


class UploadToFilesAPIStage(ProcessingStage):
    """
    Upload PDF to OpenAI Files API.

    Outputs:
        context.file_id: OpenAI file ID (e.g., "file-abc123...")

    Example:
        from openai import OpenAI
        client = OpenAI(api_key="sk-...")

        stage = UploadToFilesAPIStage(client)
        context = ProcessingContext(
            pdf_path=Path("inbox/sample.pdf"),
            pdf_bytes=b"...",
            sha256_hex="abc123..."
        )
        result = stage.execute(context)

        print(result.file_id)  # "file-abc123..."
    """

    def __init__(self, client: OpenAI):
        """
        Initialize upload stage with OpenAI client.

        Args:
            client: Authenticated OpenAI client instance
        """
        self.client = client

    def execute(self, context: ProcessingContext) -> ProcessingContext:
        """
        Upload PDF file to OpenAI Files API.

        Args:
            context: Processing context with pdf_bytes and pdf_path set

        Returns:
            Updated context with file_id populated

        Raises:
            ValueError: If pdf_bytes not set (previous stage failed)
            openai.APIError: If upload fails
        """
        if not context.pdf_bytes:
            raise ValueError("pdf_bytes not set - ComputeSHA256Stage must run first")

        logger.info(
            f"Uploading PDF to Files API",
            extra={
                "pdf_path": str(context.pdf_path),
                "file_size_bytes": len(context.pdf_bytes),
                "sha256_hex": context.sha256_hex,
            },
        )

        # Upload file to OpenAI Files API
        # purpose="assistants" makes it available for Responses API
        response = self.client.files.create(
            file=(context.pdf_path.name, context.pdf_bytes, "application/pdf"),
            purpose="user_data",
        )

        context.file_id = response.id
        context.source_file_id = response.id
        if not context.processed_at:
            context.processed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

        logger.info(
            f"Upload successful",
            extra={
                "pdf_path": str(context.pdf_path),
                "file_id": context.file_id,
            },
        )

        return context
