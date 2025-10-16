"""
OpenAI Responses API call stage.

Calls OpenAI Responses API with the uploaded PDF file to extract metadata.
Uses structured output (JSON object) to ensure parseable responses.

This stage does NOT implement retry logic - that's Workstream 2.
This stage does NOT track tokens/cost - that's Workstream 3.
"""

from src.pipeline import ProcessingStage, ProcessingContext
from openai import OpenAI
from src.config import get_config
import logging
import json

logger = logging.getLogger(__name__)


class CallResponsesAPIStage(ProcessingStage):
    """
    Call OpenAI Responses API for metadata extraction.

    Outputs:
        context.api_response: Full API response dictionary
        context.metadata_json: Extracted metadata from response

    Example:
        from openai import OpenAI
        client = OpenAI(api_key="sk-...")

        stage = CallResponsesAPIStage(client)
        context = ProcessingContext(
            pdf_path=Path("inbox/sample.pdf"),
            file_id="file-abc123..."
        )
        result = stage.execute(context)

        print(result.metadata_json)  # {"doc_type": "Invoice", ...}
    """

    # Extraction prompt template
    PROMPT_TEMPLATE = """Extract metadata from this PDF document.

Return a JSON object with these fields:
- file_name: Original filename
- doc_type: Document type (UtilityBill, BankStatement, Invoice, Receipt, or Unknown)
- issuer: Organization or person who issued the document
- primary_date: Primary date in ISO format YYYY-MM-DD (or null)
- total_amount: Total monetary amount (numeric or null)
- summary: Brief summary (max 40 words)

Be precise and concise."""

    def __init__(self, client: OpenAI):
        """
        Initialize API call stage with OpenAI client.

        Args:
            client: Authenticated OpenAI client instance
        """
        self.client = client
        self.config = get_config()

    def execute(self, context: ProcessingContext) -> ProcessingContext:
        """
        Call OpenAI Responses API to extract metadata from PDF.

        Args:
            context: Processing context with file_id set

        Returns:
            Updated context with api_response and metadata_json populated

        Raises:
            ValueError: If file_id not set (previous stage failed)
            openai.APIError: If API call fails
        """
        if not context.file_id:
            raise ValueError("file_id not set - UploadToFilesAPIStage must run first")

        logger.info(
            f"Calling Responses API",
            extra={
                "pdf_path": str(context.pdf_path),
                "file_id": context.file_id,
                "model": self.config.openai_model,
            },
        )

        # Call Responses API with structured output
        response = self.client.responses.create(
            model=self.config.openai_model,
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": self.PROMPT_TEMPLATE},
                        {
                            "type": "input_file",
                            "filename": context.pdf_path.name,
                            "file_id": context.file_id,
                        },
                    ],
                }
            ],
            text={"format": {"type": "json_object"}},  # Enforce JSON output
            max_output_tokens=self.config.max_output_tokens,
            timeout=self.config.api_timeout_seconds,
        )

        # Store full response
        context.api_response = response.model_dump()

        # Extract metadata from response
        # Response structure: response.output[0].content[0].text (JSON string)
        if response.output and len(response.output) > 0:
            content = response.output[0].content
            if content and len(content) > 0:
                text_content = content[0].text
                try:
                    context.metadata_json = json.loads(text_content)
                except json.JSONDecodeError as e:
                    logger.warning(
                        f"Failed to parse metadata JSON: {e}",
                        extra={
                            "pdf_path": str(context.pdf_path),
                            "raw_text": text_content[:200],
                        },
                    )
                    # Store raw text in metadata for debugging
                    context.metadata_json = {"_raw_text": text_content, "_error": str(e)}

        logger.info(
            f"API call successful",
            extra={
                "pdf_path": str(context.pdf_path),
                "doc_type": context.metadata_json.get("doc_type") if context.metadata_json else None,
            },
        )

        return context
