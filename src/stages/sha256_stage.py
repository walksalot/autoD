"""
SHA-256 hash computation stage.

Computes SHA-256 hash of PDF file in both hexadecimal and base64 formats:
- Hexadecimal (64 chars): Used for database deduplication (unique key)
- Base64 (44 chars): Used for OpenAI vector store file attributes

This is the first stage in the pipeline and loads the PDF file into memory.
"""

import hashlib
import base64
from src.pipeline import ProcessingStage, ProcessingContext


class ComputeSHA256Stage(ProcessingStage):
    """
    Compute SHA-256 hash of PDF file.

    Outputs:
        context.pdf_bytes: Raw PDF file bytes (loaded from disk)
        context.sha256_hex: Hexadecimal hash string (64 characters)
        context.sha256_base64: Base64-encoded hash (for OpenAI attributes)
        context.metrics['file_size_bytes']: File size in bytes

    Example:
        stage = ComputeSHA256Stage()
        context = ProcessingContext(pdf_path=Path("inbox/sample.pdf"))
        result = stage.execute(context)

        print(result.sha256_hex)  # "abc123..."
        print(result.sha256_base64)  # "qwER..."
        print(result.metrics['file_size_bytes'])  # 52480
    """

    def execute(self, context: ProcessingContext) -> ProcessingContext:
        """
        Compute SHA-256 hash of PDF file.

        Args:
            context: Processing context with pdf_path set

        Returns:
            Updated context with sha256_hex, sha256_base64, and pdf_bytes populated

        Raises:
            FileNotFoundError: If PDF file doesn't exist
            IOError: If file cannot be read
        """
        # Read file if not already loaded
        if context.pdf_bytes is None:
            with open(context.pdf_path, "rb") as f:
                context.pdf_bytes = f.read()

        # Compute SHA-256 hash
        h = hashlib.sha256(context.pdf_bytes)
        digest = h.digest()

        # Store both hex and base64 formats
        context.sha256_hex = h.hexdigest()  # 64 chars: "abc123..."
        context.sha256_base64 = base64.b64encode(digest).decode(
            "ascii"
        )  # 44 chars: "qwER..."

        # Track file size metric
        context.metrics["file_size_bytes"] = len(context.pdf_bytes)

        return context
