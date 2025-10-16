"""
Unit tests for compensating transaction pattern.

Tests transaction safety for external API operations, ensuring proper
rollback and cleanup when database commits fail.
"""

import pytest
from unittest.mock import Mock, MagicMock, call
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, declarative_base
from src.transactions import compensating_transaction

# Test database setup
Base = declarative_base()


class TestDocument(Base):
    """Test model for transaction testing."""
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
            doc = TestDocument(name="test-doc")
            db_session.add(doc)

        # Verify commit succeeded
        result = db_session.query(TestDocument).filter_by(name="test-doc").first()
        assert result is not None
        assert result.name == "test-doc"

        # Compensation should not have been called
        compensation_fn.assert_not_called()

    def test_transaction_failure_triggers_rollback(self, db_session):
        """When transaction fails, rollback should occur."""
        compensation_fn = Mock()

        with pytest.raises(ValueError):
            with compensating_transaction(db_session, compensate_fn=compensation_fn):
                doc = TestDocument(name="will-fail")
                db_session.add(doc)
                raise ValueError("Simulated database error")

        # Verify rollback occurred (doc should not exist)
        result = db_session.query(TestDocument).filter_by(name="will-fail").first()
        assert result is None

        # Compensation should have been called
        compensation_fn.assert_called_once()

    def test_transaction_failure_runs_compensation_then_reraises(self, db_session):
        """When transaction fails, compensation runs before exception propagates."""
        compensation_fn = Mock()

        with pytest.raises(ValueError) as exc_info:
            with compensating_transaction(db_session, compensate_fn=compensation_fn):
                doc = TestDocument(name="test")
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
            with compensating_transaction(db_session, compensate_fn=failing_compensation):
                doc = TestDocument(name="test")
                db_session.add(doc)
                raise ValueError("Original transaction error")

        # Original exception should be re-raised, not compensation error
        assert str(exc_info.value) == "Original transaction error"
        assert "Compensation error" not in str(exc_info.value)

    def test_no_compensation_function_provided(self, db_session):
        """When no compensation function provided, rollback still works."""
        with pytest.raises(ValueError):
            with compensating_transaction(db_session, compensate_fn=None):
                doc = TestDocument(name="no-compensation")
                db_session.add(doc)
                raise ValueError("Error without compensation")

        # Verify rollback occurred
        result = db_session.query(TestDocument).filter_by(name="no-compensation").first()
        assert result is None

    def test_compensation_cleans_up_external_resources(self, db_session):
        """Compensation function can clean up external API resources."""
        # Mock external API cleanup
        mock_api_cleanup = Mock()

        file_id = "file-abc123"

        def cleanup_external_file():
            mock_api_cleanup(file_id)

        with pytest.raises(RuntimeError):
            with compensating_transaction(db_session, compensate_fn=cleanup_external_file):
                doc = TestDocument(name="external-ref")
                db_session.add(doc)
                # Simulate failure after external resource created
                raise RuntimeError("Failed to commit after file upload")

        # Verify cleanup was called with correct file ID
        mock_api_cleanup.assert_called_once_with(file_id)

    def test_multiple_operations_in_transaction(self, db_session):
        """Context manager handles multiple database operations."""
        compensation_fn = Mock()

        with compensating_transaction(db_session, compensate_fn=compensation_fn):
            doc1 = TestDocument(name="doc1")
            doc2 = TestDocument(name="doc2")
            doc3 = TestDocument(name="doc3")
            db_session.add_all([doc1, doc2, doc3])

        # Verify all operations committed
        results = db_session.query(TestDocument).all()
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
            with compensating_transaction(db_session, compensate_fn=complex_compensation):
                doc = TestDocument(name="complex")
                db_session.add(doc)
                raise Exception("Complex failure")

        # Verify all cleanup steps executed
        assert cleanup_calls == [
            "delete_file",
            "remove_vector_store_entry",
            "cancel_async_job"
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
            with compensating_transaction(db_session, compensate_fn=partial_failing_compensation):
                raise ValueError("Original error")

        # Original error preserved
        assert str(exc_info.value) == "Original error"

        # Step 1 completed, step 2 failed, step 3 never ran
        assert cleanup_state["step1"] is True
        assert cleanup_state["step2"] is False
        assert cleanup_state["step3"] is False
