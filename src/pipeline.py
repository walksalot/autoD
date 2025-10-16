"""
Pipeline pattern for PDF processing workflow.

This module implements a discrete stage pipeline architecture where:
- Each stage performs a single, testable operation
- Context flows through stages immutably
- Errors are captured and pipeline execution stops gracefully
- Each stage can be tested in isolation

Design Pattern:
    ProcessingContext (dataclass) - Immutable state container
    ProcessingStage (ABC) - Base class for all stages
    Pipeline - Orchestrator that runs stages sequentially

Usage:
    from src.pipeline import Pipeline, ProcessingContext
    from src.stages.sha256_stage import ComputeSHA256Stage
    from pathlib import Path

    pipeline = Pipeline([
        ComputeSHA256Stage(),
        DedupeCheckStage(session),
        UploadToFilesAPIStage(client),
        CallResponsesAPIStage(client),
        PersistToDBStage(session),
    ])

    context = ProcessingContext(pdf_path=Path("inbox/doc.pdf"))
    result = pipeline.process(context)

    if result.error:
        print(f"Failed: {result.error}")
    else:
        print(f"Success: Document ID {result.document_id}")
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


@dataclass
class ProcessingContext:
    """
    Immutable context passed through pipeline stages.

    Each stage receives a context, performs its operation,
    and returns an updated context (dataclass is mutable but
    stages should treat it as immutable by convention).

    Attributes:
        pdf_path: Path to PDF file being processed
        pdf_bytes: Raw PDF file bytes (loaded by ComputeSHA256Stage)
        sha256_hex: SHA-256 hash in hexadecimal (64 chars)
        sha256_base64: SHA-256 hash in base64 (for OpenAI attributes)
        is_duplicate: True if document already exists in database
        existing_doc_id: Database ID of existing document (if duplicate)
        file_id: OpenAI Files API file ID (from upload stage)
        processed_at: ISO timestamp when processing began
        source_file_id: File ID echoed into structured output
        api_response: Full API response from Responses API
        metadata_json: Extracted metadata dictionary
        response_usage: Token usage from API call
        vector_store_id: Persistent vector store identifier (if used)
        vector_store_file_id: File ID inside vector store (if attached)
        vector_search_results: Similar document matches from File Search
        document_id: Database ID of created/updated document
        error: Exception if stage failed
        failed_at_stage: Name of stage where failure occurred
        metrics: Dictionary of timing/performance metrics
    """

    # Input
    pdf_path: Path
    pdf_bytes: Optional[bytes] = None

    # File identity (from ComputeSHA256Stage)
    sha256_hex: Optional[str] = None
    sha256_base64: Optional[str] = None

    # Deduplication (from DedupeCheckStage)
    is_duplicate: bool = False
    existing_doc_id: Optional[int] = None

    # OpenAI Files API (from UploadToFilesAPIStage)
    file_id: Optional[str] = None
    processed_at: Optional[str] = None
    source_file_id: Optional[str] = None

    # OpenAI Responses API (from CallResponsesAPIStage)
    api_response: Optional[Dict[str, Any]] = None
    metadata_json: Optional[Dict[str, Any]] = None
    response_usage: Optional[Dict[str, Any]] = None
    vector_store_id: Optional[str] = None
    vector_store_file_id: Optional[str] = None
    vector_search_results: Optional[List[Dict[str, Any]]] = None

    # Database (from PersistToDBStage)
    document_id: Optional[int] = None

    # Error tracking
    error: Optional[Exception] = None
    failed_at_stage: Optional[str] = None

    # Metrics
    metrics: Dict[str, Any] = field(default_factory=dict)


class ProcessingStage(ABC):
    """
    Abstract base class for pipeline stages.

    Each stage implements a single, testable operation.
    Stages receive context, perform their operation, and return
    updated context.

    Example:
        class MyStage(ProcessingStage):
            def execute(self, context: ProcessingContext) -> ProcessingContext:
                # Perform operation
                context.my_field = "value"
                return context
    """

    @abstractmethod
    def execute(self, context: ProcessingContext) -> ProcessingContext:
        """
        Execute this stage's logic.

        Args:
            context: Current processing context with state from previous stages

        Returns:
            Updated context with results of this stage

        Raises:
            Exception: Stage-specific errors (caught by pipeline orchestrator)
        """
        pass

    def __str__(self) -> str:
        """String representation shows stage class name."""
        return self.__class__.__name__


class Pipeline:
    """
    Orchestrates processing stages in sequence.

    Handles logging, error propagation, and metrics collection.
    If any stage raises an exception, pipeline stops and returns
    context with error information.

    Example:
        pipeline = Pipeline([
            StageA(),
            StageB(),
            StageC(),
        ])

        result = pipeline.process(ProcessingContext(pdf_path=path))

        if result.error:
            # Handle failure
            logger.error(f"Failed at {result.failed_at_stage}: {result.error}")
        else:
            # Handle success
            logger.info(f"Completed successfully: {result.document_id}")
    """

    def __init__(self, stages: List[ProcessingStage]):
        """
        Initialize pipeline with ordered list of stages.

        Args:
            stages: List of ProcessingStage instances to execute in order
        """
        self.stages = stages

    def process(self, initial_context: ProcessingContext) -> ProcessingContext:
        """
        Run all stages in sequence, passing context through.

        If any stage raises an exception, pipeline stops immediately
        and returns context with error information. Subsequent stages
        are skipped.

        Args:
            initial_context: Starting context (typically just pdf_path)

        Returns:
            Final context with results or error information
        """
        context = initial_context

        for stage in self.stages:
            # Skip remaining stages if previous stage failed
            if context.error:
                logger.warning(
                    f"Skipping {stage} due to previous error",
                    extra={
                        "pdf_path": str(context.pdf_path),
                        "stage": str(stage),
                        "previous_error": str(context.error),
                    },
                )
                break

            # Skip remaining stages if document is duplicate
            if context.is_duplicate and not isinstance(stage, self.stages[0].__class__):
                # Allow first few stages (hash, dedupe) but skip upload/processing
                # This is a simple heuristic - refine based on stage names if needed
                stage_name = str(stage)
                if stage_name not in ["ComputeSHA256Stage", "DedupeCheckStage"]:
                    logger.info(
                        f"Skipping {stage} - document is duplicate",
                        extra={
                            "pdf_path": str(context.pdf_path),
                            "stage": str(stage),
                            "existing_doc_id": context.existing_doc_id,
                        },
                    )
                    break

            try:
                logger.info(
                    f"Executing {stage}",
                    extra={
                        "pdf_path": str(context.pdf_path),
                        "stage": str(stage),
                    },
                )

                context = stage.execute(context)

                logger.info(
                    f"Completed {stage}",
                    extra={
                        "pdf_path": str(context.pdf_path),
                        "stage": str(stage),
                    },
                )

            except Exception as e:
                logger.error(
                    f"Failed at {stage}: {e}",
                    exc_info=True,
                    extra={
                        "pdf_path": str(context.pdf_path),
                        "stage": str(stage),
                        "error_type": type(e).__name__,
                    },
                )
                context.error = e
                context.failed_at_stage = str(stage)
                break

        return context
