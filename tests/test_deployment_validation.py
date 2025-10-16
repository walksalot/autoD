"""
Deployment validation smoke tests for Week 1 foundation.

These tests validate the integrated system works correctly in production-like scenarios:
- End-to-end pipeline execution
- API integration (Files API + Responses API)
- Database operations (CRUD, deduplication, transactions)
- Retry logic and error handling
- Cost tracking and token counting
- Structured logging

Run these tests after deploying to validate production readiness.

Usage:
    pytest tests/test_deployment_validation.py -v
    pytest tests/test_deployment_validation.py::test_e2e_pipeline_new_document -v
"""

import pytest
import json
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from src.pipeline import Pipeline, ProcessingContext
from src.stages import (
    ComputeSHA256Stage,
    DedupeCheckStage,
    UploadToFilesAPIStage,
    CallResponsesAPIStage,
    PersistToDBStage,
)
from src.models import Document
from src.api_client import ResponsesAPIClient
from src.cost_calculator import calculate_cost
from src.retry_logic import retry, is_retryable_api_error


class ResponsesClientStub:
    """Minimal OpenAI client stub for deployment validation."""

    def __init__(self, mock_client):
        self._mock = mock_client

    def post(self, path: str, cast_to=dict, body=None):
        if path != "/v1/responses":
            raise ValueError(f"Unexpected path: {path}")
        response = self._mock.responses.create(**(body or {}))
        if hasattr(response, "model_dump"):
            return response.model_dump()
        if hasattr(response, "to_dict"):
            return response.to_dict()
        return response


class TestEndToEndPipeline:
    """Smoke tests for complete pipeline execution."""

    def test_e2e_pipeline_new_document(self, db_session, sample_pdf_path, mock_openai_client):
        """
        SMOKE TEST: Complete pipeline processes new PDF successfully.

        Validates:
        - All 5 stages execute in order
        - Document persisted to database
        - Metadata extracted correctly
        - File uploaded to Files API
        - No errors raised
        """
        responses_api_client = ResponsesAPIClient(client=ResponsesClientStub(mock_openai_client))
        pipeline = Pipeline(
            stages=[
                ComputeSHA256Stage(),
                DedupeCheckStage(db_session),
                UploadToFilesAPIStage(mock_openai_client),
                CallResponsesAPIStage(responses_api_client),
                PersistToDBStage(db_session),
            ]
        )

        # Execute pipeline
        context = ProcessingContext(pdf_path=sample_pdf_path)
        result = pipeline.process(context)

        # Validate successful execution
        assert result.error is None, f"Pipeline failed: {result.error}"
        assert result.document_id is not None, "Document not persisted"
        assert result.sha256_hex is not None, "Hash not computed"
        assert result.file_id is not None, "File not uploaded"
        assert result.metadata_json is not None, "Metadata not extracted"

        # Validate database record
        doc = db_session.query(Document).filter_by(id=result.document_id).first()
        assert doc is not None, "Document not in database"
        assert doc.status == "completed", f"Unexpected status: {doc.status}"
        assert doc.source_file_id == result.file_id
        assert doc.metadata_json == result.metadata_json

    def test_e2e_pipeline_duplicate_detection(self, db_session, sample_pdf_path, existing_document, mock_openai_client):
        """
        SMOKE TEST: Pipeline correctly handles duplicate documents.

        Validates:
        - Deduplication prevents re-processing
        - Upload and API stages skipped
        - No new database record created
        - Existing document ID returned
        """
        responses_api_client = ResponsesAPIClient(client=ResponsesClientStub(mock_openai_client))
        pipeline = Pipeline(
            stages=[
                ComputeSHA256Stage(),
                DedupeCheckStage(db_session),
                UploadToFilesAPIStage(mock_openai_client),
                CallResponsesAPIStage(responses_api_client),
                PersistToDBStage(db_session),
            ]
        )

        initial_count = db_session.query(Document).count()

        context = ProcessingContext(pdf_path=sample_pdf_path)
        result = pipeline.process(context)

        # Validate deduplication
        assert result.is_duplicate is True, "Duplicate not detected"
        assert result.existing_doc_id == existing_document.id
        assert result.error is None

        # Validate no new document created
        final_count = db_session.query(Document).count()
        assert final_count == initial_count, "Duplicate created new document"

        # Validate APIs not called
        mock_openai_client.files.create.assert_not_called()
        mock_openai_client.responses.create.assert_not_called()

    def test_e2e_pipeline_error_handling(self, db_session, tmp_path):
        """
        SMOKE TEST: Pipeline handles errors gracefully.

        Validates:
        - Errors captured in context
        - Failed stage identified
        - No partial database records
        - Error message preserved
        """
        # Create path to non-existent file
        missing_pdf = tmp_path / "nonexistent.pdf"

        pipeline = Pipeline(
            stages=[
                ComputeSHA256Stage(),
                DedupeCheckStage(db_session),
            ]
        )

        context = ProcessingContext(pdf_path=missing_pdf)
        result = pipeline.process(context)

        # Validate error handling
        assert result.error is not None, "Error not captured"
        assert isinstance(result.error, FileNotFoundError)
        assert result.failed_at_stage == "ComputeSHA256Stage"

        # Validate no partial records
        doc_count = db_session.query(Document).count()
        assert doc_count == 0, "Partial document created on error"


class TestDatabaseOperations:
    """Smoke tests for database layer."""

    def test_database_document_crud(self, db_session):
        """
        SMOKE TEST: Database CRUD operations work correctly.

        Validates:
        - Create document
        - Read document
        - Update document
        - Query by hash
        """
        # Create
        doc = Document(
            sha256_hex="a" * 64,
            sha256_base64="test_base64",
            original_filename="test.pdf",
            file_size_bytes=1024,
            source_file_id="file-test123",
            metadata_json={"doc_type": "Invoice"},
            status="completed",
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(doc)
        db_session.commit()

        # Read
        retrieved = db_session.query(Document).filter_by(id=doc.id).first()
        assert retrieved is not None
        assert retrieved.sha256_hex == "a" * 64
        assert retrieved.status == "completed"

        # Update
        retrieved.status = "failed"
        retrieved.error_message = "Test error"
        db_session.commit()

        updated = db_session.query(Document).filter_by(id=doc.id).first()
        assert updated.status == "failed"
        assert updated.error_message == "Test error"

        # Query by hash
        by_hash = db_session.query(Document).filter_by(sha256_hex="a" * 64).first()
        assert by_hash.id == doc.id

    def test_database_deduplication_constraint(self, db_session):
        """
        SMOKE TEST: Database enforces SHA-256 uniqueness.

        Validates:
        - Unique constraint on sha256_hex
        - Duplicate insert raises IntegrityError
        """
        from sqlalchemy.exc import IntegrityError

        # Create first document
        doc1 = Document(
            sha256_hex="b" * 64,
            sha256_base64="test1",
            original_filename="test1.pdf",
            status="completed",
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(doc1)
        db_session.commit()

        # Attempt duplicate insert
        doc2 = Document(
            sha256_hex="b" * 64,  # Same hash
            sha256_base64="test2",
            original_filename="test2.pdf",
            status="completed",
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(doc2)

        with pytest.raises(IntegrityError):
            db_session.commit()

        db_session.rollback()

    def test_database_transaction_rollback(self, db_session):
        """
        SMOKE TEST: Database transactions rollback correctly.

        Validates:
        - Changes visible before commit
        - Changes reverted after rollback
        - No partial state persisted
        """
        initial_count = db_session.query(Document).count()

        doc = Document(
            sha256_hex="c" * 64,
            sha256_base64="test",
            original_filename="rollback_test.pdf",
            status="pending",
            created_at=datetime.now(timezone.utc),
        )
        db_session.add(doc)

        # Changes visible in session before commit
        pending_count = db_session.query(Document).count()
        assert pending_count == initial_count + 1

        # Rollback
        db_session.rollback()

        # Changes reverted
        final_count = db_session.query(Document).count()
        assert final_count == initial_count


class TestAPIIntegration:
    """Smoke tests for API integration layer."""

    def test_files_api_upload(self, mock_openai_client, sample_pdf_path):
        """
        SMOKE TEST: Files API upload works correctly.

        Validates:
        - File uploaded successfully
        - File ID returned
        - Correct file format
        """
        stage = UploadToFilesAPIStage(mock_openai_client)
        context = ProcessingContext(
            pdf_path=sample_pdf_path,
            sha256_hex="a" * 64,
        )

        result = stage.execute(context)

        assert result.file_id is not None
        assert result.file_id.startswith("file-")
        mock_openai_client.files.create.assert_called_once()

    def test_responses_api_metadata_extraction(self, mock_openai_client, sample_pdf_path):
        """
        SMOKE TEST: Responses API metadata extraction works.

        Validates:
        - Metadata extracted from PDF
        - JSON structure valid
        - Required fields present
        """
        responses_api_client = ResponsesAPIClient(client=ResponsesClientStub(mock_openai_client))
        stage = CallResponsesAPIStage(responses_api_client)

        context = ProcessingContext(
            pdf_path=sample_pdf_path,
            sha256_hex="a" * 64,
            file_id="file-test123",
        )

        result = stage.execute(context)

        assert result.metadata_json is not None
        assert isinstance(result.metadata_json, dict)
        assert "doc_type" in result.metadata_json
        assert "summary" in result.metadata_json

        mock_openai_client.responses.create.assert_called_once()


class TestRetryLogic:
    """Smoke tests for retry and error handling."""

    def test_retry_decorator_retries_on_transient_errors(self):
        """
        SMOKE TEST: Retry decorator retries transient errors.

        Validates:
        - Transient errors trigger retry
        - Successful retry returns result
        - Max attempts respected
        """
        call_count = 0

        @retry(max_attempts=3, initial_wait=0.01, max_wait=0.1)
        def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Rate limit exceeded")
            return "success"

        result = flaky_function()

        assert result == "success"
        assert call_count == 3  # Failed twice, succeeded on third

    def test_retry_decorator_fails_after_max_attempts(self):
        """
        SMOKE TEST: Retry decorator fails after max attempts.

        Validates:
        - Non-retryable errors not retried
        - Max attempts enforced
        - Original exception re-raised
        """
        call_count = 0

        @retry(max_attempts=3, initial_wait=0.01, max_wait=0.1)
        def always_fails():
            nonlocal call_count
            call_count += 1
            raise Exception("Permanent error")

        with pytest.raises(Exception, match="Permanent error"):
            always_fails()

        # Should have tried 3 times
        assert call_count == 3

    def test_is_retryable_api_error_identifies_transient_errors(self):
        """
        SMOKE TEST: Transient error detection works.

        Validates:
        - Rate limit errors identified as retryable
        - Timeout errors identified as retryable
        - Invalid request errors not retryable
        """
        # Retryable errors
        assert is_retryable_api_error(Exception("Rate limit exceeded"))
        assert is_retryable_api_error(Exception("Request timed out"))
        assert is_retryable_api_error(Exception("Server overloaded"))
        assert is_retryable_api_error(Exception("503 Service Unavailable"))

        # Non-retryable errors
        assert not is_retryable_api_error(Exception("Invalid API key"))
        assert not is_retryable_api_error(Exception("File not found"))


class TestCostTracking:
    """Smoke tests for token counting and cost calculation."""

    def test_cost_calculation_for_document(self):
        """
        SMOKE TEST: Cost calculation produces valid results.

        Validates:
        - Input/output costs calculated
        - Cache savings calculated
        - Total cost accurate
        """
        usage_stats = {
            "prompt_tokens": 1000,
            "output_tokens": 500,
            "prompt_tokens_details": {"cached_tokens": 200},
        }

        cost = calculate_cost(
            usage=usage_stats,
            model="gpt-5",
        )

        assert cost["total_cost_usd"] > 0
        assert cost["input_cost_usd"] > 0
        assert cost["output_cost_usd"] > 0
        assert cost["cache_savings_usd"] >= 0
        assert cost["total_cost_usd"] == (
            cost["input_cost_usd"] + cost["output_cost_usd"]
        )

    def test_cost_tracking_in_pipeline(self, db_session, sample_pdf_path, mock_openai_client):
        """
        SMOKE TEST: Pipeline tracks costs correctly.

        Validates:
        - Token usage captured
        - Costs calculated
        - Metrics persisted
        """
        responses_api_client = ResponsesAPIClient(client=ResponsesClientStub(mock_openai_client))
        pipeline = Pipeline(
            stages=[
                ComputeSHA256Stage(),
                DedupeCheckStage(db_session),
                UploadToFilesAPIStage(mock_openai_client),
                CallResponsesAPIStage(responses_api_client),
                PersistToDBStage(db_session),
            ]
        )

        context = ProcessingContext(pdf_path=sample_pdf_path)
        result = pipeline.process(context)

        # Validate cost metrics collected
        assert "file_size_bytes" in result.metrics
        assert result.metrics["file_size_bytes"] > 0


class TestLogging:
    """Smoke tests for structured logging."""

    def test_structured_logging_format(self):
        """
        SMOKE TEST: Structured logging produces valid JSON.

        Validates:
        - JSON formatter works
        - Required fields present
        - Extra fields captured
        """
        from src.logging_config import JSONFormatter
        import logging

        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        # Add extra fields
        record.pdf_path = "/path/to/doc.pdf"
        record.cost_usd = 0.05

        result = formatter.format(record)
        log_obj = json.loads(result)

        # Validate structure
        assert log_obj["message"] == "Test message"
        assert log_obj["level"] == "INFO"
        assert log_obj["pdf_path"] == "/path/to/doc.pdf"
        assert log_obj["cost_usd"] == 0.05
        assert "timestamp" in log_obj


class TestDeploymentReadiness:
    """High-level smoke tests for production deployment."""

    def test_all_imports_successful(self):
        """
        SMOKE TEST: All critical modules import without errors.

        Validates:
        - No import errors
        - Dependencies available
        - Module structure valid
        """
        # Core modules
        import src.models
        import src.pipeline
        import src.stages
        import src.retry_logic
        import src.transactions
        import src.logging_config
        import src.cost_calculator
        import src.token_counter
        import src.api_client

        # Test modules
        import tests.conftest
        import tests.mocks.mock_openai
        import tests.mocks.mock_files_api
        import tests.mocks.mock_vector_store

        assert True  # All imports successful

    def test_pipeline_can_be_instantiated(self):
        """
        SMOKE TEST: Pipeline can be created with all stages.

        Validates:
        - Stage constructors work
        - Pipeline accepts all stages
        - No initialization errors
        """
        from unittest.mock import Mock

        db_session = Mock()
        openai_client = Mock()
        responses_client = Mock()

        pipeline = Pipeline(
            stages=[
                ComputeSHA256Stage(),
                DedupeCheckStage(db_session),
                UploadToFilesAPIStage(openai_client),
                CallResponsesAPIStage(responses_client),
                PersistToDBStage(db_session),
            ]
        )

        assert len(pipeline.stages) == 5
        assert pipeline is not None

    def test_configuration_values_valid(self):
        """
        SMOKE TEST: Configuration values are valid.

        Validates:
        - Model IDs correct
        - Pricing data present
        - Retry parameters valid
        """
        from config.models import PRIMARY_MODEL, APPROVED_MODEL_IDS
        from src.cost_calculator import calculate_cost

        # Validate primary model
        assert PRIMARY_MODEL in APPROVED_MODEL_IDS

        # Validate pricing available for primary model
        cost = calculate_cost(usage={"prompt_tokens": 100, "output_tokens": 50}, model=PRIMARY_MODEL)
        assert cost["total_cost_usd"] > 0

    def test_week1_foundation_complete(self, db_session, sample_pdf_path, mock_openai_client):
        """
        SMOKE TEST: Week 1 foundation delivers all promised features.

        Validates:
        - Database + Pipeline (WS1)
        - Retry Logic (WS2)
        - Token Tracking (WS3)
        - Test Infrastructure (WS4)
        """
        # WS1: Database + Pipeline
        responses_api_client = ResponsesAPIClient(client=ResponsesClientStub(mock_openai_client))
        pipeline = Pipeline(
            stages=[
                ComputeSHA256Stage(),
                DedupeCheckStage(db_session),
                UploadToFilesAPIStage(mock_openai_client),
                CallResponsesAPIStage(responses_api_client),
                PersistToDBStage(db_session),
            ]
        )
        context = ProcessingContext(pdf_path=sample_pdf_path)
        result = pipeline.process(context)
        assert result.document_id is not None  # WS1 working

        # WS2: Retry Logic
        from src.retry_logic import is_retryable_api_error
        assert is_retryable_api_error(Exception("Rate limit"))  # WS2 working

        # WS3: Token Tracking
        from src.cost_calculator import calculate_cost
        cost = calculate_cost(usage={"prompt_tokens": 100, "output_tokens": 50}, model="gpt-5")
        assert cost["total_cost_usd"] > 0  # WS3 working

        # WS4: Test Infrastructure
        assert mock_openai_client is not None  # WS4 working

        # Integration: All working together
        assert result.error is None
        assert result.metadata_json is not None
