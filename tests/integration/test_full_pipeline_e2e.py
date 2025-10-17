"""
End-to-end integration tests for the complete document processing pipeline.

Tests the full 9-step pipeline from PDF ingestion to database storage and vector
store upload, including error handling and edge cases.
"""

import json
from unittest.mock import Mock, patch

from src.processor import (
    process_document,
    process_inbox,
    ProcessingResult,
    encode_pdf_to_base64,
)
from src.database import DatabaseManager
from src.models import Document


class TestFullPipelineE2E:
    """End-to-end tests for complete document processing pipeline."""

    def test_successful_full_pipeline(self, sample_pdf, tmp_path):
        """
        Test complete pipeline with all steps successful.

        Pipeline: Hash → Dedupe → Encode → API → Validate → DB → Vector Store
        """
        # Setup
        db_path = tmp_path / "test.db"
        db_manager = DatabaseManager(f"sqlite:///{db_path}")
        db_manager.create_tables()

        # Mock API client
        api_client = Mock()
        api_client.create_response.return_value = {
            "response_id": "resp_test123",
            "output": [
                {
                    "type": "message",
                    "role": "assistant",
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(
                                {
                                    "doc_type": "invoice",
                                    "doc_subtype": "utility_bill",
                                    "confidence_score": 0.95,
                                    "issuer": "Electric Company",
                                    "recipient": "John Doe",
                                    "primary_date": "2025-01-15",
                                    "secondary_date": None,
                                    "total_amount": 150.50,
                                    "currency": "USD",
                                    "summary": "Electric bill for January",
                                    "action_items": ["Pay by due date"],
                                    "deadlines": ["2025-02-01"],
                                    "urgency_level": "medium",
                                    "tags": ["utility", "electric"],
                                    "ocr_text_excerpt": "Electric Company Invoice",
                                    "language_detected": "en",
                                    "extraction_quality": "high",
                                    "requires_review": False,
                                    "page_count": 1,
                                }
                            ),
                        }
                    ],
                }
            ],
            "usage": {
                "prompt_tokens": 5000,
                "completion_tokens": 500,
                "cached_tokens": 4000,
            },
        }

        api_client.extract_output_text.return_value = json.dumps(
            {
                "doc_type": "invoice",
                "doc_subtype": "utility_bill",
                "confidence_score": 0.95,
                "issuer": "Electric Company",
                "recipient": "John Doe",
                "primary_date": "2025-01-15",
                "secondary_date": None,
                "total_amount": 150.50,
                "currency": "USD",
                "summary": "Electric bill for January",
                "action_items": ["Pay by due date"],
                "deadlines": ["2025-02-01"],
                "urgency_level": "medium",
                "tags": ["utility", "electric"],
                "ocr_text_excerpt": "Electric Company Invoice",
                "language_detected": "en",
                "extraction_quality": "high",
                "requires_review": False,
                "page_count": 1,
            }
        )

        api_client.extract_usage.return_value = {
            "prompt_tokens": 5000,
            "completion_tokens": 500,
            "cached_tokens": 4000,
        }

        # Mock vector store manager
        vector_manager = Mock()
        vector_manager.add_file_to_vector_store.return_value = "file-abc123"

        # Mock cost calculation
        with (
            patch("src.processor.calculate_cost") as mock_cost,
            patch("src.processor.format_cost_report") as mock_format,
            patch("src.processor.check_cost_alerts") as mock_alerts,
        ):

            mock_cost.return_value = {
                "total_cost": 0.0051,
                "input_cost": 0.003,
                "output_cost": 0.0021,
                "cached_savings": 0.002,
            }
            mock_format.return_value = "Cost: $0.0051"
            mock_alerts.return_value = None

            # Execute
            result = process_document(
                sample_pdf, db_manager, api_client, vector_manager
            )

            # Assert
            assert result.success is True
            assert result.document_id is not None
            assert result.error is None
            assert result.duplicate_of is None
            assert result.cost_usd == 0.0051
            assert result.processing_time_seconds > 0

            # Verify database record
            with db_manager.get_session() as session:
                doc = session.query(Document).filter_by(id=result.document_id).first()
                assert doc is not None
                assert doc.metadata_json is not None
                assert doc.metadata_json["doc_type"] == "invoice"
                assert doc.metadata_json["issuer"] == "Electric Company"
                assert doc.metadata_json["total_amount"] == 150.50
                assert doc.vector_store_file_id == "file-abc123"

            # Verify API was called
            api_client.create_response.assert_called_once()
            vector_manager.add_file_to_vector_store.assert_called_once()

    def test_duplicate_detection_skips_processing(self, sample_pdf, tmp_path):
        """Test that duplicate documents are skipped when skip_duplicates=True."""
        # Setup - create database with existing document
        db_path = tmp_path / "test.db"
        db_manager = DatabaseManager(f"sqlite:///{db_path}")
        db_manager.create_tables()

        # Create existing document with same hash
        with db_manager.get_session() as session:
            from src.dedupe import sha256_file

            hex_hash, b64_hash = sha256_file(sample_pdf)

            existing = Document(
                sha256_hex=hex_hash,
                sha256_base64=b64_hash,
                original_filename=sample_pdf.name,
                file_size_bytes=100,
                metadata_json={"doc_type": "test"},
                status="completed",
            )
            session.add(existing)
            session.commit()
            existing_id = existing.id

        # Mock clients (should NOT be called)
        api_client = Mock()
        vector_manager = Mock()

        # Execute
        result = process_document(
            sample_pdf, db_manager, api_client, vector_manager, skip_duplicates=True
        )

        # Assert
        assert result.success is True
        assert result.duplicate_of == existing_id
        assert result.document_id is None

        # Verify API was NOT called
        api_client.create_response.assert_not_called()
        vector_manager.add_file_to_vector_store.assert_not_called()

    def test_duplicate_processing_when_skip_false(self, sample_pdf, tmp_path):
        """Test that duplicates ARE processed when skip_duplicates=False."""
        # Setup - create database with existing document
        db_path = tmp_path / "test.db"
        db_manager = DatabaseManager(f"sqlite:///{db_path}")
        db_manager.create_tables()

        # Create existing document with same hash
        with db_manager.get_session() as session:
            from src.dedupe import sha256_file

            hex_hash, b64_hash = sha256_file(sample_pdf)

            existing = Document(
                sha256_hex=hex_hash,
                sha256_base64=b64_hash,
                original_filename="original.pdf",
                file_size_bytes=100,
                metadata_json={"doc_type": "test"},
                status="completed",
            )
            session.add(existing)
            session.commit()

        # Mock API client with valid response
        api_client = Mock()
        api_client.create_response.return_value = {"response_id": "test"}
        api_client.extract_output_text.return_value = json.dumps(
            {
                "doc_type": "invoice",
                "doc_subtype": "utility_bill",
                "confidence_score": 0.95,
                "issuer": "Test Corp",
                "recipient": "Test User",
                "primary_date": "2025-01-15",
                "total_amount": 100.0,
                "currency": "USD",
                "summary": "Test document",
                "action_items": [],
                "deadlines": [],
                "urgency_level": "low",
                "tags": [],
                "ocr_text_excerpt": "Test",
                "language_detected": "en",
                "extraction_quality": "high",
                "requires_review": False,
                "page_count": 1,
            }
        )
        api_client.extract_usage.return_value = {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "cached_tokens": 0,
        }

        vector_manager = Mock()
        vector_manager.add_file_to_vector_store.return_value = "file-xyz"

        # Mock cost calculation
        with (
            patch("src.processor.calculate_cost") as mock_cost,
            patch("src.processor.format_cost_report") as mock_format,
            patch("src.processor.check_cost_alerts") as mock_alerts,
        ):

            mock_cost.return_value = {
                "total_cost": 0.001,
                "input_cost": 0.0005,
                "output_cost": 0.0005,
                "cached_savings": 0.0,
            }
            mock_format.return_value = "Cost: $0.001"
            mock_alerts.return_value = None

            # Execute with skip_duplicates=False
            result = process_document(
                sample_pdf,
                db_manager,
                api_client,
                vector_manager,
                skip_duplicates=False,
            )

            # Assert - should process as new document
            assert result.success is True
            assert result.document_id is not None
            assert result.duplicate_of is None

            # Verify API WAS called
            api_client.create_response.assert_called_once()

    def test_api_failure_returns_error_result(self, sample_pdf, tmp_path):
        """Test that API failures are handled gracefully."""
        # Setup
        db_path = tmp_path / "test.db"
        db_manager = DatabaseManager(f"sqlite:///{db_path}")
        db_manager.create_tables()

        # Mock API client to raise exception
        api_client = Mock()
        api_client.create_response.side_effect = Exception(
            "API Error: Rate limit exceeded"
        )

        vector_manager = Mock()

        # Execute
        result = process_document(sample_pdf, db_manager, api_client, vector_manager)

        # Assert
        assert result.success is False
        assert result.error is not None
        assert "Rate limit" in result.error
        assert result.document_id is None

    def test_invalid_json_response_handling(self, sample_pdf, tmp_path):
        """Test handling of invalid JSON in API response."""
        # Setup
        db_path = tmp_path / "test.db"
        db_manager = DatabaseManager(f"sqlite:///{db_path}")
        db_manager.create_tables()

        # Mock API client with invalid JSON
        api_client = Mock()
        api_client.create_response.return_value = {"response_id": "test"}
        api_client.extract_output_text.return_value = "{invalid json}"
        api_client.extract_usage.return_value = {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "cached_tokens": 0,
        }

        vector_manager = Mock()

        # Execute
        result = process_document(sample_pdf, db_manager, api_client, vector_manager)

        # Assert
        assert result.success is False
        assert "Invalid JSON" in result.error

    def test_vector_store_failure_is_non_fatal(self, sample_pdf, tmp_path):
        """Test that vector store failures don't fail the entire pipeline."""
        # Setup
        db_path = tmp_path / "test.db"
        db_manager = DatabaseManager(f"sqlite:///{db_path}")
        db_manager.create_tables()

        # Mock API client with valid response
        api_client = Mock()
        api_client.create_response.return_value = {"response_id": "test"}
        api_client.extract_output_text.return_value = json.dumps(
            {
                "doc_type": "invoice",
                "doc_subtype": "utility_bill",
                "confidence_score": 0.95,
                "issuer": "Test Corp",
                "recipient": "Test User",
                "primary_date": "2025-01-15",
                "total_amount": 100.0,
                "currency": "USD",
                "summary": "Test document",
                "action_items": [],
                "deadlines": [],
                "urgency_level": "low",
                "tags": [],
                "ocr_text_excerpt": "Test",
                "language_detected": "en",
                "extraction_quality": "high",
                "requires_review": False,
                "page_count": 1,
            }
        )
        api_client.extract_usage.return_value = {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "cached_tokens": 0,
        }

        # Mock vector store to fail
        vector_manager = Mock()
        vector_manager.add_file_to_vector_store.side_effect = Exception(
            "Vector store error"
        )

        # Mock cost calculation
        with (
            patch("src.processor.calculate_cost") as mock_cost,
            patch("src.processor.format_cost_report") as mock_format,
            patch("src.processor.check_cost_alerts") as mock_alerts,
        ):

            mock_cost.return_value = {
                "total_cost": 0.001,
                "input_cost": 0.0005,
                "output_cost": 0.0005,
                "cached_savings": 0.0,
            }
            mock_format.return_value = "Cost: $0.001"
            mock_alerts.return_value = None

            # Execute
            result = process_document(
                sample_pdf, db_manager, api_client, vector_manager
            )

            # Assert - should succeed despite vector store failure
            assert result.success is True
            assert result.document_id is not None

            # Verify document was saved without vector store ID
            with db_manager.get_session() as session:
                doc = session.query(Document).filter_by(id=result.document_id).first()
                assert doc.vector_store_file_id is None

    def test_pdf_encoding_handles_large_files(self, tmp_path):
        """Test that PDF encoding works for large files."""
        # Create a larger test PDF (100KB)
        large_pdf = tmp_path / "large.pdf"
        large_pdf.write_bytes(b"%PDF-1.4\n" + b"x" * 100000)

        # Execute
        encoded = encode_pdf_to_base64(large_pdf)

        # Assert
        assert encoded.startswith("data:application/pdf;base64,")
        assert len(encoded) > 100000  # Should be larger due to base64 encoding

    def test_processing_result_container(self):
        """Test ProcessingResult container initialization."""
        # Success case
        result = ProcessingResult(
            success=True,
            document_id=123,
            cost_usd=0.0051,
            processing_time_seconds=2.5,
        )
        assert result.success is True
        assert result.document_id == 123
        assert result.error is None
        assert result.duplicate_of is None
        assert result.cost_usd == 0.0051
        assert result.processing_time_seconds == 2.5

        # Failure case
        result = ProcessingResult(
            success=False,
            error="Test error",
            processing_time_seconds=1.0,
        )
        assert result.success is False
        assert result.error == "Test error"
        assert result.document_id is None

        # Duplicate case
        result = ProcessingResult(
            success=True,
            duplicate_of=456,
            processing_time_seconds=0.5,
        )
        assert result.success is True
        assert result.duplicate_of == 456
        assert result.document_id is None


class TestProcessInboxE2E:
    """End-to-end tests for batch processing via process_inbox()."""

    def test_process_inbox_with_multiple_files(self, tmp_path):
        """Test processing multiple PDF files from inbox."""
        # Setup inbox with 3 PDFs
        inbox = tmp_path / "inbox"
        inbox.mkdir()

        processed_dir = tmp_path / "processed"
        failed_dir = tmp_path / "failed"

        # Create test PDFs
        for i in range(3):
            pdf = inbox / f"test_{i}.pdf"
            pdf.write_bytes(b"%PDF-1.4\nTest content " + str(i).encode())

        # Mock the entire process_document function
        with patch("src.processor.process_document") as mock_process:
            mock_process.side_effect = [
                ProcessingResult(
                    success=True,
                    document_id=1,
                    cost_usd=0.01,
                    processing_time_seconds=1.0,
                ),
                ProcessingResult(
                    success=True,
                    document_id=2,
                    cost_usd=0.01,
                    processing_time_seconds=1.1,
                ),
                ProcessingResult(
                    success=True,
                    document_id=3,
                    cost_usd=0.01,
                    processing_time_seconds=0.9,
                ),
            ]

            # Execute
            results = process_inbox(
                inbox_dir=inbox,
                processed_dir=processed_dir,
                failed_dir=failed_dir,
                batch_size=10,
            )

            # Assert
            assert results["total_files"] == 3
            assert results["processed"] == 3
            assert results["failed"] == 0
            assert results["duplicates"] == 0
            assert results["total_cost"] == 0.03
            assert "avg_processing_time" in results

            # Verify files were moved
            assert len(list(inbox.glob("*.pdf"))) == 0
            assert len(list(processed_dir.glob("*.pdf"))) == 3

    def test_process_inbox_handles_failures(self, tmp_path):
        """Test that failed documents are moved to failed directory."""
        # Setup
        inbox = tmp_path / "inbox"
        inbox.mkdir()

        processed_dir = tmp_path / "processed"
        failed_dir = tmp_path / "failed"

        # Create 2 PDFs
        for i in range(2):
            pdf = inbox / f"test_{i}.pdf"
            pdf.write_bytes(b"%PDF-1.4\n")

        # Mock process_document - one success, one failure
        with patch("src.processor.process_document") as mock_process:
            mock_process.side_effect = [
                ProcessingResult(
                    success=True,
                    document_id=1,
                    cost_usd=0.01,
                    processing_time_seconds=1.0,
                ),
                ProcessingResult(
                    success=False, error="API error", processing_time_seconds=0.5
                ),
            ]

            # Execute
            results = process_inbox(
                inbox_dir=inbox,
                processed_dir=processed_dir,
                failed_dir=failed_dir,
            )

            # Assert
            assert results["total_files"] == 2
            assert results["processed"] == 1
            assert results["failed"] == 1
            assert len(list(processed_dir.glob("*.pdf"))) == 1
            assert len(list(failed_dir.glob("*.pdf"))) == 1

    def test_process_inbox_empty_directory(self, tmp_path):
        """Test processing empty inbox directory."""
        # Setup
        inbox = tmp_path / "inbox"
        inbox.mkdir()

        # Execute
        results = process_inbox(inbox_dir=inbox)

        # Assert
        assert results["total_files"] == 0
        assert results["processed"] == 0
        assert results["failed"] == 0

    def test_process_inbox_batch_size_limit(self, tmp_path):
        """Test that batch_size parameter limits processing."""
        # Setup
        inbox = tmp_path / "inbox"
        inbox.mkdir()

        # Create 5 PDFs
        for i in range(5):
            pdf = inbox / f"test_{i}.pdf"
            pdf.write_bytes(b"%PDF-1.4\n")

        # Mock process_document
        with patch("src.processor.process_document") as mock_process:
            mock_process.return_value = ProcessingResult(
                success=True,
                document_id=1,
                cost_usd=0.01,
                processing_time_seconds=1.0,
            )

            # Execute with batch_size=2
            results = process_inbox(inbox_dir=inbox, batch_size=2)

            # Assert - only 2 files should be processed
            assert mock_process.call_count == 2
            assert results["processed"] == 2

    def test_process_inbox_handles_duplicates(self, tmp_path):
        """Test that duplicate documents are counted separately."""
        # Setup
        inbox = tmp_path / "inbox"
        inbox.mkdir()

        processed_dir = tmp_path / "processed"

        # Create 3 PDFs
        for i in range(3):
            pdf = inbox / f"test_{i}.pdf"
            pdf.write_bytes(b"%PDF-1.4\n")

        # Mock process_document - 1 new, 2 duplicates
        with patch("src.processor.process_document") as mock_process:
            mock_process.side_effect = [
                ProcessingResult(
                    success=True,
                    document_id=1,
                    cost_usd=0.01,
                    processing_time_seconds=1.0,
                ),
                ProcessingResult(
                    success=True, duplicate_of=1, processing_time_seconds=0.1
                ),
                ProcessingResult(
                    success=True, duplicate_of=1, processing_time_seconds=0.1
                ),
            ]

            # Execute
            results = process_inbox(
                inbox_dir=inbox,
                processed_dir=processed_dir,
            )

            # Assert
            assert results["total_files"] == 3
            assert results["processed"] == 1
            assert results["duplicates"] == 2
            assert results["failed"] == 0
            assert results["total_cost"] == 0.01  # Only non-duplicate charged

            # All files should be moved to processed (duplicates are successful)
            assert len(list(processed_dir.glob("*.pdf"))) == 3
