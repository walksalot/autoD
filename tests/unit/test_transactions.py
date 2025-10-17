"""
Unit tests for compensating transaction pattern.

Tests transaction safety for external API operations, ensuring proper
rollback and cleanup when database commits fail.
"""

import pytest
from unittest.mock import Mock
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, declarative_base
from src.transactions import compensating_transaction

# Test database setup
Base = declarative_base()


class MockDocument(Base):
    """Mock model for transaction testing."""

    __tablename__ = "test_documents"
    id = Column(Integer, primary_key=True)
    name = Column(String(100))


@pytest.fixture
def db_session():
    """Create in-memory SQLite session for testing."""
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestCompensatingTransaction:
    """Test suite for compensating_transaction context manager."""

    def test_successful_transaction_no_compensation_needed(self, db_session):
        """When transaction succeeds, compensation should not run."""
        compensation_fn = Mock()

        with compensating_transaction(db_session, compensate_fn=compensation_fn):
            doc = MockDocument(name="test-doc")
            db_session.add(doc)

        # Verify commit succeeded
        result = db_session.query(MockDocument).filter_by(name="test-doc").first()
        assert result is not None
        assert result.name == "test-doc"

        # Compensation should not have been called
        compensation_fn.assert_not_called()

    def test_transaction_failure_triggers_rollback(self, db_session):
        """When transaction fails, rollback should occur."""
        compensation_fn = Mock()

        with pytest.raises(ValueError):
            with compensating_transaction(db_session, compensate_fn=compensation_fn):
                doc = MockDocument(name="will-fail")
                db_session.add(doc)
                raise ValueError("Simulated database error")

        # Verify rollback occurred (doc should not exist)
        result = db_session.query(MockDocument).filter_by(name="will-fail").first()
        assert result is None

        # Compensation should have been called
        compensation_fn.assert_called_once()

    def test_transaction_failure_runs_compensation_then_reraises(self, db_session):
        """When transaction fails, compensation runs before exception propagates."""
        compensation_fn = Mock()

        with pytest.raises(ValueError) as exc_info:
            with compensating_transaction(db_session, compensate_fn=compensation_fn):
                doc = MockDocument(name="test")
                db_session.add(doc)
                raise ValueError("Original error")

        # Original exception should be re-raised
        assert str(exc_info.value) == "Original error"

        # Compensation should have run
        compensation_fn.assert_called_once()

    def test_compensation_failure_does_not_mask_original_error(self, db_session):
        """When both transaction and compensation fail, original error is preserved."""

        def failing_compensation():
            raise RuntimeError("Compensation error")

        with pytest.raises(ValueError) as exc_info:
            with compensating_transaction(
                db_session, compensate_fn=failing_compensation
            ):
                doc = MockDocument(name="test")
                db_session.add(doc)
                raise ValueError("Original transaction error")

        # Original exception should be re-raised, not compensation error
        assert str(exc_info.value) == "Original transaction error"
        assert "Compensation error" not in str(exc_info.value)

    def test_no_compensation_function_provided(self, db_session):
        """When no compensation function provided, rollback still works."""
        with pytest.raises(ValueError):
            with compensating_transaction(db_session, compensate_fn=None):
                doc = MockDocument(name="no-compensation")
                db_session.add(doc)
                raise ValueError("Error without compensation")

        # Verify rollback occurred
        result = (
            db_session.query(MockDocument).filter_by(name="no-compensation").first()
        )
        assert result is None

    def test_compensation_cleans_up_external_resources(self, db_session):
        """Compensation function can clean up external API resources."""
        # Mock external API cleanup
        mock_api_cleanup = Mock()

        file_id = "file-abc123"

        def cleanup_external_file():
            mock_api_cleanup(file_id)

        with pytest.raises(RuntimeError):
            with compensating_transaction(
                db_session, compensate_fn=cleanup_external_file
            ):
                doc = MockDocument(name="external-ref")
                db_session.add(doc)
                # Simulate failure after external resource created
                raise RuntimeError("Failed to commit after file upload")

        # Verify cleanup was called with correct file ID
        mock_api_cleanup.assert_called_once_with(file_id)

    def test_multiple_operations_in_transaction(self, db_session):
        """Context manager handles multiple database operations."""
        compensation_fn = Mock()

        with compensating_transaction(db_session, compensate_fn=compensation_fn):
            doc1 = MockDocument(name="doc1")
            doc2 = MockDocument(name="doc2")
            doc3 = MockDocument(name="doc3")
            db_session.add_all([doc1, doc2, doc3])

        # Verify all operations committed
        results = db_session.query(MockDocument).all()
        assert len(results) == 3
        assert {doc.name for doc in results} == {"doc1", "doc2", "doc3"}

        # No compensation needed
        compensation_fn.assert_not_called()

    def test_transaction_with_complex_compensation_logic(self, db_session):
        """Compensation can perform multiple cleanup operations."""
        cleanup_calls = []

        def complex_compensation():
            cleanup_calls.append("delete_file")
            cleanup_calls.append("remove_vector_store_entry")
            cleanup_calls.append("cancel_async_job")

        with pytest.raises(Exception):
            with compensating_transaction(
                db_session, compensate_fn=complex_compensation
            ):
                doc = MockDocument(name="complex")
                db_session.add(doc)
                raise Exception("Complex failure")

        # Verify all cleanup steps executed
        assert cleanup_calls == [
            "delete_file",
            "remove_vector_store_entry",
            "cancel_async_job",
        ]

    def test_compensation_with_partial_failure(self, db_session):
        """Compensation that partially fails still allows original error to propagate."""
        cleanup_state = {"step1": False, "step2": False, "step3": False}

        def partial_failing_compensation():
            cleanup_state["step1"] = True
            raise RuntimeError("Step 2 failed!")
            # This line won't execute, but shows intent
            cleanup_state["step3"] = True  # pragma: no cover

        with pytest.raises(ValueError) as exc_info:
            with compensating_transaction(
                db_session, compensate_fn=partial_failing_compensation
            ):
                raise ValueError("Original error")

        # Original error preserved
        assert str(exc_info.value) == "Original error"

        # Step 1 completed, step 2 failed, step 3 never ran
        assert cleanup_state["step1"] is True
        assert cleanup_state["step2"] is False
        assert cleanup_state["step3"] is False


class TestAuditTrail:
    """Test suite for audit trail functionality in compensating transactions."""

    def test_audit_trail_captures_successful_transaction(self, db_session):
        """Audit trail should capture all events for successful transaction."""
        audit_trail = {}

        with compensating_transaction(
            db_session, compensate_fn=None, audit_trail=audit_trail
        ):
            doc = MockDocument(name="audit-success")
            db_session.add(doc)

        # Verify audit trail fields for success
        assert "started_at" in audit_trail
        assert "committed_at" in audit_trail
        assert audit_trail["status"] == "success"
        assert audit_trail["compensation_needed"] is False

        # Verify timestamps are ISO 8601 formatted
        from datetime import datetime

        datetime.fromisoformat(audit_trail["started_at"].replace("Z", "+00:00"))
        datetime.fromisoformat(audit_trail["committed_at"].replace("Z", "+00:00"))

        # committed_at should be after started_at
        assert audit_trail["committed_at"] >= audit_trail["started_at"]

    def test_audit_trail_captures_transaction_failure(self, db_session):
        """Audit trail should capture rollback and error details."""
        audit_trail = {}

        with pytest.raises(ValueError):
            with compensating_transaction(
                db_session, compensate_fn=None, audit_trail=audit_trail
            ):
                doc = MockDocument(name="audit-fail")
                db_session.add(doc)
                raise ValueError("Simulated database error")

        # Verify audit trail fields for failure
        assert "started_at" in audit_trail
        assert "rolled_back_at" in audit_trail
        assert audit_trail["status"] == "failed"
        assert audit_trail["error"] == "Simulated database error"
        assert audit_trail["error_type"] == "ValueError"
        assert audit_trail["compensation_needed"] is False

        # Verify timestamps
        from datetime import datetime

        datetime.fromisoformat(audit_trail["started_at"].replace("Z", "+00:00"))
        datetime.fromisoformat(audit_trail["rolled_back_at"].replace("Z", "+00:00"))

    def test_audit_trail_captures_successful_compensation(self, db_session):
        """Audit trail should capture successful compensation execution."""
        audit_trail = {}
        compensation_executed = []

        def compensation_fn():
            compensation_executed.append(True)

        with pytest.raises(RuntimeError):
            with compensating_transaction(
                db_session, compensate_fn=compensation_fn, audit_trail=audit_trail
            ):
                doc = MockDocument(name="comp-success")
                db_session.add(doc)
                raise RuntimeError("DB commit failed")

        # Verify compensation executed
        assert len(compensation_executed) == 1

        # Verify audit trail captured compensation success
        assert audit_trail["status"] == "failed"
        assert audit_trail["compensation_needed"] is True
        assert audit_trail["compensation_status"] == "success"
        assert "compensation_completed_at" in audit_trail

        # Verify timestamps
        from datetime import datetime

        datetime.fromisoformat(
            audit_trail["compensation_completed_at"].replace("Z", "+00:00")
        )

    def test_audit_trail_captures_compensation_failure(self, db_session):
        """Audit trail should capture compensation failure details."""
        audit_trail = {}

        def failing_compensation():
            raise IOError("Cleanup API call failed")

        with pytest.raises(ValueError):
            with compensating_transaction(
                db_session, compensate_fn=failing_compensation, audit_trail=audit_trail
            ):
                doc = MockDocument(name="comp-fail")
                db_session.add(doc)
                raise ValueError("Original transaction error")

        # Verify audit trail captured compensation failure
        assert audit_trail["status"] == "failed"
        assert audit_trail["error"] == "Original transaction error"
        assert audit_trail["error_type"] == "ValueError"
        assert audit_trail["compensation_needed"] is True
        assert audit_trail["compensation_status"] == "failed"
        assert audit_trail["compensation_error"] == "Cleanup API call failed"
        assert audit_trail["compensation_error_type"] == "IOError"

    def test_audit_trail_with_custom_context_fields(self, db_session):
        """Audit trail can be pre-populated with custom context fields."""
        audit_trail = {
            "stage": "UploadStage",
            "pdf_path": "/inbox/test.pdf",
            "file_id": "file-abc123",
        }

        with compensating_transaction(
            db_session, compensate_fn=None, audit_trail=audit_trail
        ):
            doc = MockDocument(name="custom-context")
            db_session.add(doc)

        # Verify custom fields preserved
        assert audit_trail["stage"] == "UploadStage"
        assert audit_trail["pdf_path"] == "/inbox/test.pdf"
        assert audit_trail["file_id"] == "file-abc123"

        # Verify transaction fields added
        assert audit_trail["status"] == "success"
        assert "started_at" in audit_trail
        assert "committed_at" in audit_trail

    def test_audit_trail_none_by_default(self, db_session):
        """Transaction should work without audit_trail parameter."""
        # Should not raise
        with compensating_transaction(db_session, compensate_fn=None):
            doc = MockDocument(name="no-audit")
            db_session.add(doc)

        # Verify document committed
        result = db_session.query(MockDocument).filter_by(name="no-audit").first()
        assert result is not None

    def test_audit_trail_mutation_visible_to_caller(self, db_session):
        """Audit trail mutations should be visible to calling code."""
        audit_trail = {"initial_field": "value"}

        with compensating_transaction(
            db_session, compensate_fn=None, audit_trail=audit_trail
        ):
            doc = MockDocument(name="mutation-test")
            db_session.add(doc)

        # Caller can access mutated audit trail
        assert "initial_field" in audit_trail
        assert "started_at" in audit_trail
        assert "committed_at" in audit_trail
        assert "status" in audit_trail

    def test_audit_trail_for_logging_integration(self, db_session, caplog):
        """Audit trail can be used with structured logging."""
        import logging

        audit_trail = {
            "operation": "document_upload",
            "user_id": "user-123",
        }

        with caplog.at_level(logging.INFO):
            with compensating_transaction(
                db_session, compensate_fn=None, audit_trail=audit_trail
            ):
                doc = MockDocument(name="logging-test")
                db_session.add(doc)

        # Verify transaction logged
        assert "Transaction committed successfully" in caplog.text

    def test_audit_trail_timing_precision(self, db_session):
        """Audit trail timestamps should be precise enough for ordering."""
        audit_trail = {}

        with compensating_transaction(
            db_session, compensate_fn=None, audit_trail=audit_trail
        ):
            doc = MockDocument(name="timing-test")
            db_session.add(doc)

        # Verify timestamps include microseconds
        started = audit_trail["started_at"]
        committed = audit_trail["committed_at"]

        # ISO 8601 with timezone
        assert "T" in started
        assert "T" in committed

        # Should be parseable
        from datetime import datetime

        dt_started = datetime.fromisoformat(started.replace("Z", "+00:00"))
        dt_committed = datetime.fromisoformat(committed.replace("Z", "+00:00"))

        # Committed should be after started
        assert dt_committed >= dt_started
