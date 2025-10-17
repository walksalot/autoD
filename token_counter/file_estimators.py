"""File token estimators for OpenAI API inputs.

This module provides conservative token estimates for file inputs (PDFs, images, etc.)
that are sent to OpenAI's Responses API. Since we cannot directly tokenize binary file
content, we use heuristics based on file characteristics.

Key principles:
- Conservative estimates (prefer overestimate to avoid surprises)
- Confidence levels (high/medium/low) based on available information
- Min/max ranges to communicate uncertainty
- Extensible architecture for adding new file types
"""

from __future__ import annotations

import base64
import io
from abc import ABC, abstractmethod
from pathlib import Path

try:
    from pypdf import PdfReader

    HAS_PYPDF2 = True
except ImportError:
    HAS_PYPDF2 = False

from .exceptions import ConfigurationError
from .models import TokenEstimate


class FileTokenEstimator(ABC):
    """Abstract base class for file token estimators.

    Subclasses must implement estimate() to provide token estimates
    for specific file types.
    """

    @abstractmethod
    def estimate(
        self,
        file_path: str | Path | None = None,
        file_data: str | None = None,
    ) -> TokenEstimate:
        """Estimate tokens for a file.

        Args:
            file_path: Path to the file on disk
            file_data: Base64-encoded file data (data URI or raw base64)

        Returns:
            TokenEstimate with min/max tokens and confidence level

        Raises:
            ValueError: If neither file_path nor file_data is provided
        """
        pass

    @abstractmethod
    def supports_file_type(self, filename: str) -> bool:
        """Check if this estimator supports the given file type.

        Args:
            filename: Name of the file (extension will be checked)

        Returns:
            True if this estimator can handle this file type
        """
        pass


class PDFTokenEstimator(FileTokenEstimator):
    """Token estimator for PDF files.

    Uses conservative per-page estimates based on OpenAI documentation and
    empirical observations:
    - Minimum: 85 tokens/page (sparse content, mostly images)
    - Maximum: 1,100 tokens/page (dense text content)

    Confidence levels:
    - High: When we can count exact pages from file
    - Medium: When estimating from base64 size
    - Low: When fallback estimates are used
    """

    # Conservative token estimates per page
    MIN_TOKENS_PER_PAGE = 85
    MAX_TOKENS_PER_PAGE = 1100

    # Fallback estimates when page count unavailable
    FALLBACK_PAGES_PER_MB = 50  # Conservative estimate

    def __init__(self):
        """Initialize PDF estimator."""
        if not HAS_PYPDF2:
            raise ConfigurationError(
                "pypdf is required for PDF token estimation. "
                "Install it with: pip install pypdf>=4.0.0"
            )

    def estimate(
        self,
        file_path: str | Path | None = None,
        file_data: str | None = None,
    ) -> TokenEstimate:
        """Estimate tokens for a PDF file.

        Args:
            file_path: Path to PDF file on disk
            file_data: Base64-encoded PDF data

        Returns:
            TokenEstimate with conservative min/max bounds

        Raises:
            ValueError: If neither file_path nor file_data is provided
        """
        if file_path is None and file_data is None:
            raise ValueError("Either file_path or file_data must be provided")

        # Try to get exact page count
        page_count = None
        confidence = "medium"
        basis = "Estimated from file size"

        if file_path:
            page_count = self._count_pages_from_file(Path(file_path))
            if page_count is not None:
                confidence = "high"
                basis = f"Counted {page_count} pages from PDF file"

        # Fallback to base64 size estimation
        if page_count is None and file_data:
            page_count = self._estimate_pages_from_base64(file_data)
            confidence = "medium"
            basis = f"Estimated ~{page_count} pages from file size"

        # Final fallback
        if page_count is None:
            page_count = 5  # Conservative default
            confidence = "low"
            basis = "Using fallback estimate (no file access)"

        # Calculate token range
        min_tokens = page_count * self.MIN_TOKENS_PER_PAGE
        max_tokens = page_count * self.MAX_TOKENS_PER_PAGE

        return TokenEstimate(
            min_tokens=min_tokens,
            max_tokens=max_tokens,
            confidence=confidence,
            basis=basis,
        )

    def supports_file_type(self, filename: str) -> bool:
        """Check if file is a PDF.

        Args:
            filename: Name of the file

        Returns:
            True if filename ends with .pdf (case-insensitive)
        """
        return filename.lower().endswith(".pdf")

    def _count_pages_from_file(self, file_path: Path) -> int | None:
        """Count pages in a PDF file using pypdf.

        Args:
            file_path: Path to PDF file

        Returns:
            Number of pages, or None if counting fails
        """
        try:
            with open(file_path, "rb") as f:
                reader = PdfReader(f)
                return len(reader.pages)
        except Exception:
            # Silently fail and return None - we'll use fallback
            return None

    def _estimate_pages_from_base64(self, file_data: str) -> int:
        """Estimate page count from base64 file size.

        Args:
            file_data: Base64-encoded PDF (data URI or raw base64)

        Returns:
            Estimated number of pages
        """
        # Strip data URI prefix if present
        if "base64," in file_data:
            file_data = file_data.split("base64,")[1]

        # Decode base64 to get file size in bytes
        try:
            decoded = base64.b64decode(file_data)
            size_bytes = len(decoded)
        except Exception:
            # If decode fails, estimate from base64 string length
            # Base64 is ~4/3 of original size
            size_bytes = int(len(file_data) * 0.75)

        # Estimate pages from file size
        size_mb = size_bytes / (1024 * 1024)
        estimated_pages = max(1, int(size_mb * self.FALLBACK_PAGES_PER_MB))

        return estimated_pages

    def _count_pages_from_base64(self, file_data: str) -> int | None:
        """Try to count pages from base64 PDF data using pypdf.

        Args:
            file_data: Base64-encoded PDF

        Returns:
            Number of pages, or None if counting fails
        """
        try:
            # Strip data URI prefix if present
            if "base64," in file_data:
                file_data = file_data.split("base64,")[1]

            # Decode and read with pypdf
            pdf_bytes = base64.b64decode(file_data)
            pdf_stream = io.BytesIO(pdf_bytes)
            reader = PdfReader(pdf_stream)
            return len(reader.pages)
        except Exception:
            return None


# Factory function for getting the right estimator
def get_file_estimator(filename: str) -> FileTokenEstimator | None:
    """Get the appropriate file token estimator for a file.

    Args:
        filename: Name of the file

    Returns:
        FileTokenEstimator instance if file type is supported, None otherwise

    Example:
        >>> estimator = get_file_estimator("document.pdf")
        >>> if estimator:
        ...     estimate = estimator.estimate(file_path="document.pdf")
        ...     print(f"Tokens: {estimate.min_tokens}-{estimate.max_tokens}")
    """
    # Check PDF estimator
    try:
        pdf_estimator = PDFTokenEstimator()
        if pdf_estimator.supports_file_type(filename):
            return pdf_estimator
    except ConfigurationError:
        # pypdf not available
        pass

    # Add more estimators here in the future:
    # - ImageTokenEstimator for PNG/JPEG/etc.
    # - AudioTokenEstimator for audio files
    # - etc.

    return None
