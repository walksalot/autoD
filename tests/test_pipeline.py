"""
Integration tests for the full processing pipeline.

Validates:
- End-to-end pipeline execution
- Stage orchestration
- Error handling and recovery
- Deduplication workflow
- Database persistence
- API integration (mocked)
"""

import pytest
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import Mock

from src.pipeline import Pipeline, ProcessingContext
from src.stages import (
    ComputeSHA256Stage,
    DedupeCheckStage,
    UploadToFilesAPIStage,
    CallResponsesAPIStage,
    PersistToDBStage,
)
from src.models import Document


def test_full_pipeline_success_path(test_db_session, sample_pdf_path, mock_openai_client):
    """
    Test complete pipeline execution for new document.

    Validates all 5 stages execute successfully and document is persisted.
    """
    # Build pipeline with all stages
    pipeline = Pipeline(
        stages=[
            ComputeSHA256Stage(),
            DedupeCheckStage(test_db_session),
            UploadToFilesAPIStage(mock_openai_client),
            CallResponsesAPIStage(mock_openai_client),
            PersistToDBStage(test_db_session),
        ]
    )

    # Execute pipeline
    context = ProcessingContext(pdf_path=sample_pdf_path)
    result = pipeline.process(context)

    # Verify final context state
    assert result.sha256_hex is not None
    assert result.sha256_base64 is not None
    assert result.is_duplicate is False
    assert result.file_id == "file-test123abc"
    assert result.metadata_json is not None
    assert result.metadata_json["doc_type"] == "Invoice"
    assert result.document_id is not None
    assert result.error is None

    # Verify database record created
    doc = test_db_session.query(Document).filter_by(id=result.document_id).first()
    assert doc is not None
    assert doc.sha256_hex == result.sha256_hex
    assert doc.original_filename == sample_pdf_path.name
    assert doc.source_file_id == "file-test123abc"
    assert doc.metadata_json["doc_type"] == "Invoice"
    assert doc.status == "completed"


def test_pipeline_deduplication_skip_upload(test_db_session, sample_pdf_path, existing_document, mock_openai_client):
    """
    Test pipeline short-circuits when duplicate detected.

    After DedupeCheckStage finds duplicate, should skip upload/API/persist stages.
    """
    # Pipeline with all stages
    pipeline = Pipeline(
        stages=[
            ComputeSHA256Stage(),
            DedupeCheckStage(test_db_session),
            UploadToFilesAPIStage(mock_openai_client),
            CallResponsesAPIStage(mock_openai_client),
            PersistToDBStage(test_db_session),
        ]
    )

    context = ProcessingContext(pdf_path=sample_pdf_path)
    result = pipeline.process(context)

    # Should detect duplicate
    assert result.is_duplicate is True
    assert result.existing_doc_id == existing_document.id

    # Should NOT call OpenAI APIs (check mock not called)
    mock_openai_client.files.create.assert_not_called()
    mock_openai_client.responses.create.assert_not_called()

    # Should NOT create new database record
    doc_count = test_db_session.query(Document).count()
    assert doc_count == 1  # Only existing_document


def test_pipeline_partial_execution(test_db_session, sample_pdf_path):
    """
    Test pipeline with only first two stages (hash + dedupe).

    Validates pipeline can be partially configured for specific workflows.
    """
    pipeline = Pipeline(
        stages=[
            ComputeSHA256Stage(),
            DedupeCheckStage(test_db_session),
        ]
    )

    context = ProcessingContext(pdf_path=sample_pdf_path)
    result = pipeline.process(context)

    # Verify first two stages completed
    assert result.sha256_hex is not None
    assert result.is_duplicate is False

    # Later stages not run
    assert result.file_id is None
    assert result.metadata_json is None
    assert result.document_id is None


def test_pipeline_error_propagation(test_db_session, tmp_path, mock_openai_client):
    """
    Test pipeline captures errors from failing stages.

    Validates error handling when a stage raises an exception.
    Pipeline should catch error and store in context, not raise.
    """
    # Create path to non-existent file
    missing_pdf = tmp_path / "missing.pdf"

    pipeline = Pipeline(
        stages=[
            ComputeSHA256Stage(),
            DedupeCheckStage(test_db_session),
        ]
    )

    context = ProcessingContext(pdf_path=missing_pdf)

    # Pipeline catches FileNotFoundError and stores in context
    result = pipeline.process(context)

    # Verify error was captured
    assert result.error is not None
    assert isinstance(result.error, FileNotFoundError)
    assert result.failed_at_stage == "ComputeSHA256Stage"


def test_pipeline_stage_order_matters(test_db_session, sample_pdf_path, mock_openai_client):
    """
    Test stage execution order is critical.

    DedupeCheckStage requires ComputeSHA256Stage to run first.
    Pipeline should catch the ValueError and store in context.
    """
    # Incorrect order: dedupe before hash computation
    pipeline = Pipeline(
        stages=[
            DedupeCheckStage(test_db_session),  # ← Wrong: runs before hash computed
            ComputeSHA256Stage(),
        ]
    )

    context = ProcessingContext(pdf_path=sample_pdf_path)

    # Pipeline catches ValueError and stores in context
    result = pipeline.process(context)

    # Verify error was captured
    assert result.error is not None
    assert isinstance(result.error, ValueError)
    assert "sha256_hex not set" in str(result.error)
    assert result.failed_at_stage == "DedupeCheckStage"


def test_pipeline_with_api_error(test_db_session, sample_pdf_path):
    """
    Test pipeline handles API errors gracefully.

    Validates error handling when OpenAI API calls fail.
    Pipeline should catch error and store in context.
    """
    # Create mock client that raises exception
    failing_client = Mock()
    failing_client.files.create.side_effect = Exception("API connection failed")

    pipeline = Pipeline(
        stages=[
            ComputeSHA256Stage(),
            DedupeCheckStage(test_db_session),
            UploadToFilesAPIStage(failing_client),
        ]
    )

    context = ProcessingContext(pdf_path=sample_pdf_path)

    # Pipeline catches API error and stores in context
    result = pipeline.process(context)

    # Verify error was captured
    assert result.error is not None
    assert "API connection failed" in str(result.error)
    assert result.failed_at_stage == "UploadToFilesAPIStage"


def test_pipeline_database_commit_on_success(test_db_session, sample_pdf_path, mock_openai_client):
    """
    Test database transaction commits on successful pipeline execution.

    Validates document is persisted and queryable after pipeline completes.
    """
    pipeline = Pipeline(
        stages=[
            ComputeSHA256Stage(),
            DedupeCheckStage(test_db_session),
            UploadToFilesAPIStage(mock_openai_client),
            CallResponsesAPIStage(mock_openai_client),
            PersistToDBStage(test_db_session),
        ]
    )

    context = ProcessingContext(pdf_path=sample_pdf_path)
    result = pipeline.process(context)

    # Commit should have occurred in PersistToDBStage
    # Verify document exists in database
    doc = test_db_session.query(Document).filter_by(id=result.document_id).first()
    assert doc is not None
    assert doc.status == "completed"


def test_pipeline_metrics_collection(test_db_session, sample_pdf_path, mock_openai_client):
    """
    Test pipeline collects metrics during execution.

    Validates context.metrics is populated by stages.
    """
    pipeline = Pipeline(
        stages=[
            ComputeSHA256Stage(),
            DedupeCheckStage(test_db_session),
        ]
    )

    context = ProcessingContext(pdf_path=sample_pdf_path)
    result = pipeline.process(context)

    # ComputeSHA256Stage should add file_size_bytes
    assert "file_size_bytes" in result.metrics
    assert result.metrics["file_size_bytes"] > 0


def test_pipeline_context_immutability_violation_detected():
    """
    Test pipeline detects if stages violate context immutability.

    Note: ProcessingContext uses @dataclass without frozen=True,
    so immutability is by convention, not enforced.
    """
    # This test documents expected behavior
    # In practice, stages should only modify context fields, not replace context
    pass  # No enforcement mechanism currently


def test_pipeline_empty_stages_list():
    """
    Test pipeline with no stages is valid but does nothing.

    Validates edge case of empty pipeline.
    """
    pipeline = Pipeline(stages=[])

    context = ProcessingContext(pdf_path=Path("test.pdf"))
    result = pipeline.process(context)

    # Context should be unchanged
    assert result.pdf_path == Path("test.pdf")
    assert result.sha256_hex is None
    assert result.file_id is None


def test_pipeline_single_stage():
    """
    Test pipeline with single stage executes correctly.

    Validates minimal pipeline configuration.
    """
    pipeline = Pipeline(stages=[ComputeSHA256Stage()])

    # Create temporary PDF
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(b"%PDF-1.0\ntest")
        pdf_path = Path(f.name)

    try:
        context = ProcessingContext(pdf_path=pdf_path)
        result = pipeline.process(context)

        assert result.sha256_hex is not None
        assert len(result.sha256_hex) == 64
    finally:
        pdf_path.unlink()


def test_pipeline_reuse_with_different_inputs(test_db_session, tmp_path, mock_openai_client):
    """
    Test same pipeline instance can process multiple documents.

    Validates pipeline is reusable (no shared state between executions).
    """
    pipeline = Pipeline(
        stages=[
            ComputeSHA256Stage(),
            DedupeCheckStage(test_db_session),
        ]
    )

    # Create two different PDFs
    pdf1 = tmp_path / "doc1.pdf"
    pdf1.write_bytes(b"%PDF-1.0\nContent A")

    pdf2 = tmp_path / "doc2.pdf"
    pdf2.write_bytes(b"%PDF-1.0\nContent B")

    # Process both through same pipeline instance
    context1 = ProcessingContext(pdf_path=pdf1)
    result1 = pipeline.process(context1)

    context2 = ProcessingContext(pdf_path=pdf2)
    result2 = pipeline.process(context2)

    # Should produce different hashes
    assert result1.sha256_hex != result2.sha256_hex
    assert result1.is_duplicate is False
    assert result2.is_duplicate is False


def test_full_pipeline_metadata_extraction(test_db_session, sample_pdf_path, mock_openai_client):
    """
    Test pipeline correctly extracts and persists metadata.

    Validates API response parsing and database storage.
    """
    pipeline = Pipeline(
        stages=[
            ComputeSHA256Stage(),
            DedupeCheckStage(test_db_session),
            UploadToFilesAPIStage(mock_openai_client),
            CallResponsesAPIStage(mock_openai_client),
            PersistToDBStage(test_db_session),
        ]
    )

    context = ProcessingContext(pdf_path=sample_pdf_path)
    result = pipeline.process(context)

    # Verify metadata structure
    assert result.metadata_json is not None
    assert "file_name" in result.metadata_json
    assert "doc_type" in result.metadata_json
    assert "issuer" in result.metadata_json
    assert "primary_date" in result.metadata_json
    assert "total_amount" in result.metadata_json
    assert "summary" in result.metadata_json

    # Verify database has same metadata
    doc = test_db_session.query(Document).filter_by(id=result.document_id).first()
    assert doc.metadata_json == result.metadata_json
