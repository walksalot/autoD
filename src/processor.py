"""
Main document processing pipeline.
Orchestrates deduplication, API calls, validation, and database storage.
"""

from pathlib import Path
from typing import Optional, Dict, Any
import base64
import json
import time
from datetime import datetime

import logging

from src.config import get_config
from src.logging_config import setup_logging, get_correlation_id
from src.models import Document
from src.database import DatabaseManager
from src.dedupe import deduplicate_and_hash, build_vector_store_attributes
from src.schema import validate_response
from src.prompts import build_responses_api_payload
from src.api_client import ResponsesAPIClient
from src.vector_store import VectorStoreManager
from src.token_counter import calculate_cost, format_cost_report, check_cost_alerts


# Use basic logger at module level, configure lazily
logger = logging.getLogger(__name__)
_logger_configured = False


def _ensure_logging() -> None:
    """Ensure logging is configured (called lazily on first use)."""
    global _logger_configured
    if not _logger_configured:
        try:
            config = get_config()
            setup_logging(
                log_level=getattr(config, "log_level", "INFO"),
                log_format=getattr(config, "log_format", "json"),
                log_file=str(getattr(config, "log_file", "logs/paper_autopilot.log")),
            )
        except Exception:
            # In tests, config might be mocked - use basic logging config
            logging.basicConfig(level=logging.INFO)
        _logger_configured = True


class ProcessingResult:
    """Container for processing result with status and metadata."""

    def __init__(
        self,
        success: bool,
        document_id: Optional[int] = None,
        error: Optional[str] = None,
        duplicate_of: Optional[int] = None,
        cost_usd: Optional[float] = None,
        processing_time_seconds: Optional[float] = None,
    ):
        self.success = success
        self.document_id = document_id
        self.error = error
        self.duplicate_of = duplicate_of
        self.cost_usd = cost_usd
        self.processing_time_seconds = processing_time_seconds


def encode_pdf_to_base64(file_path: Path) -> str:
    """
    Encode PDF to base64 data URI.

    Args:
        file_path: Path to PDF file

    Returns:
        Base64-encoded data URI string
    """
    with open(file_path, "rb") as f:
        pdf_bytes = f.read()

    base64_data = base64.b64encode(pdf_bytes).decode("ascii")
    return f"data:application/pdf;base64,{base64_data}"


def process_document(
    file_path: Path,
    db_manager: DatabaseManager,
    api_client: ResponsesAPIClient,
    vector_manager: VectorStoreManager,
    skip_duplicates: bool = True,
) -> ProcessingResult:
    """
    Process a single PDF document through the complete pipeline.

    Pipeline Steps:
    1. Compute SHA-256 hash
    2. Check for duplicates in database
    3. Encode PDF to base64
    4. Build API payload with prompts
    5. Call OpenAI Responses API
    6. Parse and validate response
    7. Store in database
    8. Upload to vector store
    9. Move file to processed directory

    Args:
        file_path: Path to PDF file
        db_manager: Database manager instance
        api_client: API client instance
        vector_manager: Vector store manager instance
        skip_duplicates: If True, skip processing duplicates

    Returns:
        ProcessingResult with status and metadata
    """
    _ensure_logging()  # Lazy logger initialization
    correlation_id = get_correlation_id()
    start_time = time.time()

    logger.info(
        f"Processing document: {file_path.name}",
        extra={"correlation_id": correlation_id, "document_filename": file_path.name},
    )

    try:
        with db_manager.get_session() as session:
            # Step 1: Compute hash and check duplicates
            logger.info("Computing file hash", extra={"correlation_id": correlation_id})
            hex_hash, b64_hash, duplicate = deduplicate_and_hash(file_path, session)

            if duplicate and skip_duplicates:
                logger.info(
                    f"Duplicate detected: {file_path.name} (original ID: {duplicate.id})",
                    extra={
                        "correlation_id": correlation_id,
                        "duplicate_id": duplicate.id,
                    },
                )
                return ProcessingResult(
                    success=True,
                    duplicate_of=duplicate.id,
                    processing_time_seconds=time.time() - start_time,
                )

            # Step 2: Encode PDF
            logger.info("Encoding PDF", extra={"correlation_id": correlation_id})
            pdf_base64 = encode_pdf_to_base64(file_path)
            file_size = file_path.stat().st_size

            # Step 3: Build API payload
            logger.info(
                "Building API payload", extra={"correlation_id": correlation_id}
            )
            payload = build_responses_api_payload(
                filename=file_path.name,
                pdf_base64=pdf_base64,
                page_count=None,  # Could extract from PDF metadata if needed
            )

            # Step 4: Call API
            logger.info(
                "Calling OpenAI Responses API", extra={"correlation_id": correlation_id}
            )
            response = api_client.create_response(payload)

            # Step 5: Extract output
            output_text = api_client.extract_output_text(response)
            usage = api_client.extract_usage(response)

            # Step 6: Parse and validate JSON
            logger.info(
                "Parsing and validating response",
                extra={"correlation_id": correlation_id},
            )
            try:
                metadata = json.loads(output_text)
            except json.JSONDecodeError as e:
                logger.error(
                    f"Invalid JSON in response: {e}",
                    extra={"correlation_id": correlation_id},
                )
                raise ValueError(f"Invalid JSON: {e}")

            is_valid, errors = validate_response(metadata)
            if not is_valid:
                logger.warning(
                    f"Schema validation failed: {errors}",
                    extra={
                        "correlation_id": correlation_id,
                        "validation_errors": errors,
                    },
                )

            # Step 7: Calculate cost
            cost_data = calculate_cost(
                prompt_tokens=usage["prompt_tokens"],
                completion_tokens=usage["completion_tokens"],
                cached_tokens=usage["cached_tokens"],
                model=get_config().openai_model,
            )

            logger.info(
                format_cost_report(cost_data), extra={"correlation_id": correlation_id}
            )

            # Check cost alerts
            alert = check_cost_alerts(cost_data["total_cost"])
            if alert:
                logger.warning(alert, extra={"correlation_id": correlation_id})

            # Step 8: Create or update Document record (simplified 10-field schema)
            logger.info("Saving to database", extra={"correlation_id": correlation_id})

            # Enrich metadata with processing details before storing
            enriched_metadata = {
                **metadata,  # All extracted fields from API response
                "_processing": {
                    "model_used": get_config().openai_model,
                    "prompt_tokens": usage["prompt_tokens"],
                    "completion_tokens": usage["completion_tokens"],
                    "cached_tokens": usage["cached_tokens"],
                    "total_cost_usd": cost_data["total_cost"],
                    "processing_duration_seconds": time.time() - start_time,
                    "processed_at": datetime.now().isoformat(),
                },
                "_raw_response": response,  # Full API response for debugging
            }

            # If duplicate exists and skip_duplicates=False, update existing record
            if duplicate and not skip_duplicates:
                logger.info(
                    f"Updating existing document (ID: {duplicate.id}) with new processing results",
                    extra={
                        "correlation_id": correlation_id,
                        "document_id": duplicate.id,
                    },
                )
                duplicate.metadata_json = enriched_metadata
                duplicate.status = "completed"
                duplicate.processed_at = datetime.now()
                duplicate.original_filename = file_path.name  # Update filename
                duplicate.file_size_bytes = file_size
                doc = duplicate  # Use existing document
                session.commit()
            else:
                # No duplicate, create new document
                doc = Document(
                    sha256_hex=hex_hash,
                    sha256_base64=b64_hash,
                    original_filename=file_path.name,
                    file_size_bytes=file_size,
                    source_file_id=None,  # Will be set when uploaded to vector store
                    metadata_json=enriched_metadata,  # All extracted data in JSON blob (includes page_count)
                    status="completed",
                    processed_at=datetime.now(),
                )
                session.add(doc)
                session.commit()

            logger.info(
                f"Document saved: ID {doc.id}",
                extra={"correlation_id": correlation_id, "document_id": doc.id},
            )

            # Step 9: Upload to vector store
            try:
                logger.info(
                    "Uploading to vector store",
                    extra={"correlation_id": correlation_id},
                )
                metadata_attrs = build_vector_store_attributes(doc)
                upload_result = vector_manager.add_file_to_vector_store(
                    file_path, metadata_attrs
                )

                if upload_result.vector_store_file_id:
                    doc.vector_store_file_id = upload_result.vector_store_file_id
                    session.commit()
                    logger.info(
                        f"Vector store file ID: {upload_result.vector_store_file_id}",
                        extra={"correlation_id": correlation_id},
                    )
            except Exception as e:
                logger.error(
                    f"Vector store upload failed: {e}",
                    extra={"correlation_id": correlation_id},
                )
                # Non-fatal: continue processing

            processing_time = time.time() - start_time

            logger.info(
                f"Processing complete: {file_path.name} ({processing_time:.2f}s)",
                extra={
                    "correlation_id": correlation_id,
                    "processing_time": processing_time,
                },
            )

            return ProcessingResult(
                success=True,
                document_id=doc.id,
                cost_usd=cost_data["total_cost"],
                processing_time_seconds=processing_time,
            )

    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(
            f"Processing failed: {file_path.name} - {str(e)}",
            exc_info=True,
            extra={"correlation_id": correlation_id, "error": str(e)},
        )

        return ProcessingResult(
            success=False,
            error=str(e),
            processing_time_seconds=processing_time,
        )


def process_inbox(
    inbox_dir: Path = Path("inbox"),
    processed_dir: Path = Path("processed"),
    failed_dir: Path = Path("failed"),
    batch_size: int = 10,
    skip_duplicates: bool = True,
) -> Dict[str, Any]:
    """
    Process all PDFs in inbox directory.

    Args:
        inbox_dir: Directory containing PDFs to process
        processed_dir: Directory for successfully processed PDFs
        failed_dir: Directory for failed PDFs
        batch_size: Number of files to process (not parallelized yet)
        skip_duplicates: Skip files that already exist in database

    Returns:
        Summary dict with success/failure counts and total cost
    """
    _ensure_logging()  # Lazy logger initialization
    config = get_config()

    # Create output directories
    processed_dir.mkdir(exist_ok=True)
    failed_dir.mkdir(exist_ok=True)

    # Initialize clients
    db_manager = DatabaseManager(config.paper_autopilot_db_url)
    db_manager.create_tables()  # Ensure tables exist

    api_client = ResponsesAPIClient()
    vector_manager = VectorStoreManager()

    # Find PDFs
    pdf_files = sorted(inbox_dir.glob("*.pdf"))

    if not pdf_files:
        logger.info("No PDF files found in inbox")
        return {
            "total_files": 0,
            "processed": 0,
            "failed": 0,
            "duplicates": 0,
            "total_cost": 0.0,
        }

    logger.info(f"Found {len(pdf_files)} PDF files")

    # Process files
    results: Dict[str, Any] = {
        "total_files": len(pdf_files),
        "processed": 0,
        "failed": 0,
        "duplicates": 0,
        "total_cost": 0.0,
        "processing_times": [],
    }

    for pdf_file in pdf_files[:batch_size]:
        result = process_document(
            pdf_file,
            db_manager,
            api_client,
            vector_manager,
            skip_duplicates=skip_duplicates,
        )

        if result.success:
            if result.duplicate_of:
                results["duplicates"] += 1
                # Still move to processed (duplicate is successful case)
                dest = processed_dir / pdf_file.name
                pdf_file.rename(dest)
            else:
                results["processed"] += 1
                results["total_cost"] += result.cost_usd or 0.0
                results["processing_times"].append(result.processing_time_seconds)

                # Move to processed directory
                dest = processed_dir / pdf_file.name
                pdf_file.rename(dest)
        else:
            results["failed"] += 1

            # Move to failed directory
            dest = failed_dir / pdf_file.name
            pdf_file.rename(dest)

    # Calculate average processing time
    if results["processing_times"]:
        avg_time = sum(results["processing_times"]) / len(results["processing_times"])
        results["avg_processing_time"] = avg_time

    logger.info(f"Processing complete: {results}")

    return results


# Example usage
if __name__ == "__main__":
    import sys

    # Simple test run
    if len(sys.argv) > 1:
        # Process specific file
        file_path = Path(sys.argv[1])
        if not file_path.exists():
            print(f"File not found: {file_path}")
            sys.exit(1)

        config = get_config()
        db_manager = DatabaseManager(config.paper_autopilot_db_url)
        db_manager.create_tables()

        api_client = ResponsesAPIClient()
        vector_manager = VectorStoreManager()

        result = process_document(file_path, db_manager, api_client, vector_manager)

        if result.success:
            print(f"✅ Success: Document ID {result.document_id}")
            print(f"   Cost: ${result.cost_usd:.4f}")
            print(f"   Time: {result.processing_time_seconds:.2f}s")
        else:
            print(f"❌ Failed: {result.error}")
    else:
        # Process inbox
        print("Processing inbox...")
        results = process_inbox()
        print("\n=== Summary ===")
        print(f"Total files: {results['total_files']}")
        print(f"Processed: {results['processed']}")
        print(f"Duplicates: {results['duplicates']}")
        print(f"Failed: {results['failed']}")
        print(f"Total cost: ${results['total_cost']:.4f}")
        if "avg_processing_time" in results:
            print(f"Avg time: {results['avg_processing_time']:.2f}s")
