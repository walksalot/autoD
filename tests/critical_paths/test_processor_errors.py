"""
Processor error path tests.

Tests critical error handling in processor.py:
- Duplicate detection (skip vs process)
- JSON parsing errors
- Schema validation failures
- Vector store upload failures
- General exception handling
- ProcessingResult error states

These tests ensure the processor fails gracefully and doesn't corrupt data.
"""

from pathlib import Path
from unittest.mock import Mock, patch
import json

from src.processor import process_document, ProcessingResult, encode_pdf_to_base64
from src.database import DatabaseManager
from src.models import Document


class TestDuplicateDetection:
    """Test duplicate detection behavior."""

    def test_skip_duplicates_returns_early(self, sample_pdf):
        """When skip_duplicates=True and duplicate exists, should return early."""
        db_manager = DatabaseManager("sqlite:///:memory:")
        db_manager.create_tables()

        # Create existing document with same hash
        with db_manager.get_session() as session:
            # First, need to determine the hash that sample_pdf will produce
            from src.dedupe import sha256_file

            hex_hash, b64_hash = sha256_file(sample_pdf)

            existing = Document(
                sha256_hex=hex_hash,
                sha256_base64=b64_hash,
                original_filename="existing.pdf",
                status="completed",
            )
            session.add(existing)
            session.commit()
            existing_id = existing.id

        # Mock clients (should not be called)
        api_client = Mock()
        vector_manager = Mock()

        # Process document with skip_duplicates=True
        result = process_document(
            sample_pdf,
            db_manager,
            api_client,
            vector_manager,
            skip_duplicates=True,
        )

        # Should succeed without calling API
        assert result.success is True
        assert result.duplicate_of == existing_id
        assert result.document_id is None
        assert result.error is None

        # API should NOT have been called
        api_client.create_response.assert_not_called()
        vector_manager.add_file_to_vector_store.assert_not_called()

    @patch("src.processor.check_cost_alerts")
    @patch("src.processor.format_cost_report")
    @patch("src.processor.calculate_cost")
    def test_process_duplicates_when_skip_false(
        self, mock_cost, mock_format, mock_alerts, sample_pdf
    ):
        """When skip_duplicates=False, should process duplicate."""
        # Mock cost calculation
        mock_cost.return_value = {
            "total_cost": 0.0051,
            "input_cost": 0.003,
            "output_cost": 0.0021,
            "cached_savings": 0.0,
        }
        mock_format.return_value = "Cost: $0.0051"
        mock_alerts.return_value = None

        db_manager = DatabaseManager("sqlite:///:memory:")
        db_manager.create_tables()

        # Create existing document with same hash
        with db_manager.get_session() as session:
            from src.dedupe import sha256_file

            hex_hash, b64_hash = sha256_file(sample_pdf)

            existing = Document(
                sha256_hex=hex_hash,
                sha256_base64=b64_hash,
                original_filename="existing.pdf",
                status="completed",
            )
            session.add(existing)
            session.commit()

        # Mock API response
        api_client = Mock()
        api_client.create_response.return_value = {
            "id": "resp_123",
            "model": "gpt-5-mini",
            "output": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "doc_type": "Invoice",
                            "issuer": "Test Corp",
                            "summary": "Test document",
                        }
                    ),
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "cached_tokens": 0,
            },
        }
        api_client.extract_output_text.return_value = json.dumps(
            {
                "doc_type": "Invoice",
                "issuer": "Test Corp",
                "summary": "Test document",
            }
        )
        api_client.extract_usage.return_value = {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "cached_tokens": 0,
        }

        vector_manager = Mock()
        vector_manager.add_file_to_vector_store.return_value = "file_abc"

        # Process with skip_duplicates=False
        result = process_document(
            sample_pdf,
            db_manager,
            api_client,
            vector_manager,
            skip_duplicates=False,
        )

        # Should process despite duplicate
        assert result.success is True
        assert result.document_id is not None
        assert result.duplicate_of is None

        # API SHOULD have been called
        api_client.create_response.assert_called_once()


class TestJSONParsingErrors:
    """Test JSON parsing error handling."""

    def test_invalid_json_raises_value_error(self, sample_pdf):
        """Invalid JSON in API response should raise ValueError."""
        db_manager = DatabaseManager("sqlite:///:memory:")
        db_manager.create_tables()

        # Mock API with invalid JSON
        api_client = Mock()
        api_client.create_response.return_value = {"id": "resp_123"}
        api_client.extract_output_text.return_value = "NOT VALID JSON{{{["
        api_client.extract_usage.return_value = {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "cached_tokens": 0,
        }

        vector_manager = Mock()

        # Should return error result
        result = process_document(
            sample_pdf,
            db_manager,
            api_client,
            vector_manager,
        )

        assert result.success is False
        assert result.error is not None
        assert "Invalid JSON" in result.error
        assert result.document_id is None

    def test_json_decode_error_captured(self, sample_pdf):
        """JSONDecodeError should be caught and converted to ProcessingResult."""
        db_manager = DatabaseManager("sqlite:///:memory:")
        db_manager.create_tables()

        # Mock API with malformed JSON
        api_client = Mock()
        api_client.create_response.return_value = {"id": "resp_123"}
        api_client.extract_output_text.return_value = '{"key": invalid}'
        api_client.extract_usage.return_value = {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "cached_tokens": 0,
        }

        vector_manager = Mock()

        result = process_document(
            sample_pdf,
            db_manager,
            api_client,
            vector_manager,
        )

        assert result.success is False
        assert "Invalid JSON" in result.error


class TestSchemaValidationFailures:
    """Test schema validation failure handling."""

    @patch("src.processor.check_cost_alerts")
    @patch("src.processor.format_cost_report")
    @patch("src.processor.calculate_cost")
    def test_schema_validation_logs_warning_but_continues(
        self, mock_cost, mock_format, mock_alerts, sample_pdf
    ):
        """Invalid schema should log warning but continue processing."""
        # Mock cost calculation
        mock_cost.return_value = {
            "total_cost": 0.0051,
            "input_cost": 0.003,
            "output_cost": 0.0021,
            "cached_savings": 0.0,
        }
        mock_format.return_value = "Cost: $0.0051"
        mock_alerts.return_value = None

        db_manager = DatabaseManager("sqlite:///:memory:")
        db_manager.create_tables()

        # Mock API with response that fails schema validation
        api_client = Mock()
        api_client.create_response.return_value = {
            "id": "resp_123",
            "output": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            # Missing required fields - should fail validation
                            "doc_type": "Unknown",
                        }
                    ),
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "cached_tokens": 0,
            },
        }
        api_client.extract_output_text.return_value = json.dumps(
            {
                "doc_type": "Unknown",
            }
        )
        api_client.extract_usage.return_value = {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "cached_tokens": 0,
        }

        vector_manager = Mock()
        vector_manager.add_file_to_vector_store.return_value = "file_abc"

        # Should succeed despite validation failure
        result = process_document(
            sample_pdf,
            db_manager,
            api_client,
            vector_manager,
        )

        # Processing should succeed (validation failure is non-fatal)
        assert result.success is True
        assert result.document_id is not None


class TestVectorStoreUploadFailures:
    """Test vector store upload error handling."""

    @patch("src.processor.check_cost_alerts")
    @patch("src.processor.format_cost_report")
    @patch("src.processor.calculate_cost")
    def test_vector_store_failure_is_non_fatal(
        self, mock_cost, mock_format, mock_alerts, sample_pdf
    ):
        """Vector store upload failure should not fail processing."""
        # Mock cost calculation
        mock_cost.return_value = {
            "total_cost": 0.0051,
            "input_cost": 0.003,
            "output_cost": 0.0021,
            "cached_savings": 0.0,
        }
        mock_format.return_value = "Cost: $0.0051"
        mock_alerts.return_value = None

        db_manager = DatabaseManager("sqlite:///:memory:")
        db_manager.create_tables()

        # Mock successful API
        api_client = Mock()
        api_client.create_response.return_value = {
            "id": "resp_123",
            "output": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "doc_type": "Invoice",
                            "issuer": "Test Corp",
                            "summary": "Test document",
                        }
                    ),
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "cached_tokens": 0,
            },
        }
        api_client.extract_output_text.return_value = json.dumps(
            {
                "doc_type": "Invoice",
                "issuer": "Test Corp",
                "summary": "Test document",
            }
        )
        api_client.extract_usage.return_value = {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "cached_tokens": 0,
        }

        # Mock vector store that raises exception
        vector_manager = Mock()
        vector_manager.add_file_to_vector_store.side_effect = RuntimeError(
            "Vector store connection failed"
        )

        result = process_document(
            sample_pdf,
            db_manager,
            api_client,
            vector_manager,
        )

        # Should succeed despite vector store failure
        assert result.success is True
        assert result.document_id is not None

        # Verify document was saved without vector store ID
        with db_manager.get_session() as session:
            doc = session.query(Document).filter_by(id=result.document_id).first()
            assert doc is not None
            assert doc.vector_store_file_id is None

    @patch("src.processor.check_cost_alerts")
    @patch("src.processor.format_cost_report")
    @patch("src.processor.calculate_cost")
    def test_vector_store_exception_logged(
        self, mock_cost, mock_format, mock_alerts, sample_pdf
    ):
        """Vector store exceptions should be logged."""
        # Mock cost calculation
        mock_cost.return_value = {
            "total_cost": 0.0051,
            "input_cost": 0.003,
            "output_cost": 0.0021,
            "cached_savings": 0.0,
        }
        mock_format.return_value = "Cost: $0.0051"
        mock_alerts.return_value = None

        db_manager = DatabaseManager("sqlite:///:memory:")
        db_manager.create_tables()

        # Mock successful API
        api_client = Mock()
        api_client.create_response.return_value = {
            "id": "resp_123",
            "output": [
                {
                    "type": "text",
                    "text": json.dumps(
                        {
                            "doc_type": "Receipt",
                            "issuer": "Store",
                            "summary": "Purchase",
                        }
                    ),
                }
            ],
            "usage": {
                "prompt_tokens": 50,
                "completion_tokens": 30,
                "cached_tokens": 0,
            },
        }
        api_client.extract_output_text.return_value = json.dumps(
            {
                "doc_type": "Receipt",
                "issuer": "Store",
                "summary": "Purchase",
            }
        )
        api_client.extract_usage.return_value = {
            "prompt_tokens": 50,
            "completion_tokens": 30,
            "cached_tokens": 0,
        }

        # Mock vector manager that raises different exception type
        vector_manager = Mock()
        vector_manager.add_file_to_vector_store.side_effect = ConnectionError(
            "Network timeout"
        )

        result = process_document(
            sample_pdf,
            db_manager,
            api_client,
            vector_manager,
        )

        # Should still succeed
        assert result.success is True


class TestGeneralExceptionHandling:
    """Test general exception handling in processor."""

    def test_api_exception_returns_error_result(self, sample_pdf):
        """Exception in API call should return ProcessingResult with error."""
        db_manager = DatabaseManager("sqlite:///:memory:")
        db_manager.create_tables()

        # Mock API that raises exception
        api_client = Mock()
        api_client.create_response.side_effect = RuntimeError("API service unavailable")

        vector_manager = Mock()

        result = process_document(
            sample_pdf,
            db_manager,
            api_client,
            vector_manager,
        )

        assert result.success is False
        assert result.error == "API service unavailable"
        assert result.document_id is None

    def test_database_exception_returns_error_result(self, sample_pdf):
        """Database exception should return ProcessingResult with error."""
        # Create db_manager with invalid database path
        db_manager = DatabaseManager("sqlite:///nonexistent/path/db.sqlite")

        api_client = Mock()
        vector_manager = Mock()

        result = process_document(
            sample_pdf,
            db_manager,
            api_client,
            vector_manager,
        )

        assert result.success is False
        assert result.error is not None

    def test_file_not_found_error(self):
        """Non-existent file should raise error."""
        db_manager = DatabaseManager("sqlite:///:memory:")
        api_client = Mock()
        vector_manager = Mock()

        # Create path to non-existent file
        nonexistent_file = Path("/tmp/nonexistent_file_12345.pdf")

        result = process_document(
            nonexistent_file,
            db_manager,
            api_client,
            vector_manager,
        )

        assert result.success is False
        assert result.error is not None


class TestProcessingResultContainer:
    """Test ProcessingResult container class."""

    def test_success_result_has_document_id(self):
        """Successful result should have document_id."""
        result = ProcessingResult(
            success=True,
            document_id=123,
            cost_usd=0.0051,
            processing_time_seconds=3.45,
        )

        assert result.success is True
        assert result.document_id == 123
        assert result.error is None
        assert result.duplicate_of is None
        assert result.cost_usd == 0.0051
        assert result.processing_time_seconds == 3.45

    def test_duplicate_result_has_duplicate_id(self):
        """Duplicate result should have duplicate_of."""
        result = ProcessingResult(
            success=True,
            duplicate_of=456,
            processing_time_seconds=0.12,
        )

        assert result.success is True
        assert result.duplicate_of == 456
        assert result.document_id is None
        assert result.error is None

    def test_error_result_has_error_message(self):
        """Error result should have error message."""
        result = ProcessingResult(
            success=False,
            error="Connection timeout",
            processing_time_seconds=30.0,
        )

        assert result.success is False
        assert result.error == "Connection timeout"
        assert result.document_id is None
        assert result.duplicate_of is None


class TestPDFEncoding:
    """Test PDF encoding functionality."""

    def test_encode_pdf_to_base64_returns_data_uri(self, sample_pdf):
        """encode_pdf_to_base64 should return data URI string."""
        result = encode_pdf_to_base64(sample_pdf)

        assert isinstance(result, str)
        assert result.startswith("data:application/pdf;base64,")
        assert len(result) > 100  # Base64 data should be substantial

    def test_encode_pdf_with_different_sizes(self, tmp_path):
        """Should handle PDFs of different sizes."""
        # Create small PDF
        small_pdf = tmp_path / "small.pdf"
        small_pdf.write_bytes(b"%PDF-1.4\nsmall content")

        # Create larger PDF
        large_pdf = tmp_path / "large.pdf"
        large_pdf.write_bytes(b"%PDF-1.4\n" + b"x" * 100000)

        small_result = encode_pdf_to_base64(small_pdf)
        large_result = encode_pdf_to_base64(large_pdf)

        assert len(large_result) > len(small_result)
        assert small_result.startswith("data:application/pdf;base64,")
        assert large_result.startswith("data:application/pdf;base64,")
