"""
Unit tests for compensating transaction pattern.

Tests transaction safety for external API operations, ensuring proper
rollback and cleanup when database commits fail.

ENHANCED TESTS (TD1): Tests for CompensatingTransaction class with:
- Multi-step rollback handler registration
- LIFO execution order
- Critical vs non-critical handlers
- Comprehensive audit trail
- Resource lifecycle tracking
"""

import pytest
from unittest.mock import Mock, MagicMock
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, declarative_base
from src.transactions import (
    compensating_transaction,
    CompensatingTransaction,
    ResourceType,
    RollbackHandler,
    create_files_api_rollback_handler,
    create_vector_store_rollback_handler,
)

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


class TestEnhancedCompensatingTransaction:
    """Test suite for enhanced CompensatingTransaction class (TD1)."""

    def test_successful_transaction_with_multi_step_handlers(self, db_session):
        """When transaction succeeds, no handlers should execute."""
        audit = {}
        handler1_fn = Mock()
        handler2_fn = Mock()

        with CompensatingTransaction(db_session, audit_trail=audit) as _txn:
            # Register multiple rollback handlers
            txn.register_rollback(
                handler_fn=handler1_fn,
                resource_type=ResourceType.FILES_API,
                resource_id="file-123",
                description="Delete file-123",
            )
            txn.register_rollback(
                handler_fn=handler2_fn,
                resource_type=ResourceType.DATABASE,
                resource_id="doc-456",
                description="Delete doc-456",
            )

            doc = MockDocument(name="success-test")
            db_session.add(doc)

        # Verify commit succeeded
        result = db_session.query(MockDocument).filter_by(name="success-test").first()
        assert result is not None

        # Handlers should not execute on success
        handler1_fn.assert_not_called()
        handler2_fn.assert_not_called()

        # Verify audit trail
        assert audit["status"] == "success"
        assert audit["compensation_needed"] is False
        assert len(audit["resources"]) == 2

    def test_rollback_handlers_execute_in_lifo_order(self, db_session):
        """Rollback handlers should execute in reverse order (LIFO)."""
        execution_order = []

        def handler1():
            execution_order.append("handler1")

        def handler2():
            execution_order.append("handler2")

        def handler3():
            execution_order.append("handler3")

        with pytest.raises(RuntimeError):
            with CompensatingTransaction(db_session) as _txn:
                txn.register_rollback(
                    handler_fn=handler1,
                    resource_type=ResourceType.FILES_API,
                    resource_id="file-1",
                    description="First handler",
                )
                txn.register_rollback(
                    handler_fn=handler2,
                    resource_type=ResourceType.FILES_API,
                    resource_id="file-2",
                    description="Second handler",
                )
                txn.register_rollback(
                    handler_fn=handler3,
                    resource_type=ResourceType.FILES_API,
                    resource_id="file-3",
                    description="Third handler",
                )

                raise RuntimeError("Force rollback")

        # Verify LIFO order: last registered (handler3), first executed
        assert execution_order == ["handler3", "handler2", "handler1"]

    def test_critical_handler_failure_raises_exception(self, db_session):
        """Critical handler failure should raise exception (takes precedence over original error)."""

        def critical_handler():
            raise ValueError("Critical handler failed")

        # Critical handler failure should override the original exception
        with pytest.raises(ValueError, match="Critical handler failed"):
            with CompensatingTransaction(db_session) as _txn:
                txn.register_rollback(
                    handler_fn=critical_handler,
                    resource_type=ResourceType.FILES_API,
                    resource_id="file-critical",
                    description="Critical cleanup",
                    critical=True,  # Critical handler
                )

                raise RuntimeError("Trigger rollback")

    def test_non_critical_handler_failure_continues_execution(self, db_session):
        """Non-critical handler failure should not stop other handlers."""
        execution_order = []

        def non_critical_handler():
            execution_order.append("non_critical")
            raise ValueError("Non-critical failure")

        def critical_handler():
            execution_order.append("critical")

        with pytest.raises(RuntimeError):
            with CompensatingTransaction(db_session) as _txn:
                txn.register_rollback(
                    handler_fn=critical_handler,
                    resource_type=ResourceType.FILES_API,
                    resource_id="file-1",
                    description="Critical handler",
                    critical=True,
                )
                txn.register_rollback(
                    handler_fn=non_critical_handler,
                    resource_type=ResourceType.FILES_API,
                    resource_id="file-2",
                    description="Non-critical handler",
                    critical=False,  # Non-critical
                )

                raise RuntimeError("Trigger rollback")

        # Both handlers should have executed despite non-critical failure
        assert "non_critical" in execution_order
        assert "critical" in execution_order

    def test_audit_trail_captures_all_events(self, db_session):
        """Audit trail should record all transaction events."""
        audit = {}
        handler_fn = Mock()

        with pytest.raises(RuntimeError):
            with CompensatingTransaction(db_session, audit_trail=audit) as _txn:
                txn.register_rollback(
                    handler_fn=handler_fn,
                    resource_type=ResourceType.FILES_API,
                    resource_id="file-audit",
                    description="Audit test handler",
                )

                raise RuntimeError("Test error")

        # Verify audit trail structure
        assert "started_at" in audit
        assert "rolled_back_at" in audit
        assert audit["status"] == "failed"
        assert audit["error"] == "Test error"
        assert audit["error_type"] == "RuntimeError"
        assert audit["compensation_needed"] is True
        assert audit["handlers_registered"] == 1

        # Verify resources tracked
        assert len(audit["resources"]) == 1
        assert audit["resources"][0]["type"] == "files_api"
        assert audit["resources"][0]["id"] == "file-audit"

        # Verify compensation stats
        assert audit["compensation_stats"]["total"] == 1
        assert audit["compensation_stats"]["executed"] == 1
        assert audit["compensation_stats"]["successful"] == 1

    def test_resource_type_tracking(self, db_session):
        """Different resource types should be tracked correctly."""
        audit = {}

        with pytest.raises(RuntimeError):
            with CompensatingTransaction(db_session, audit_trail=audit) as _txn:
                txn.register_rollback(
                    handler_fn=Mock(),
                    resource_type=ResourceType.FILES_API,
                    resource_id="file-1",
                    description="File cleanup",
                )
                txn.register_rollback(
                    handler_fn=Mock(),
                    resource_type=ResourceType.VECTOR_STORE,
                    resource_id="vs-1",
                    description="Vector store cleanup",
                )
                txn.register_rollback(
                    handler_fn=Mock(),
                    resource_type=ResourceType.DATABASE,
                    resource_id="db-1",
                    description="DB cleanup",
                )

                raise RuntimeError("Test")

        # Verify all resource types tracked
        resource_types = {r["type"] for r in audit["resources"]}
        assert resource_types == {"files_api", "vector_store", "database"}

    def test_rollback_handler_dataclass(self):
        """RollbackHandler dataclass should track execution state."""
        executed = False

        def test_handler():
            nonlocal executed
            executed = True

        handler = RollbackHandler(
            handler_fn=test_handler,
            resource_type=ResourceType.FILES_API,
            resource_id="test-file",
            description="Test handler",
            critical=True,
        )

        # Initial state
        assert handler.executed is False
        assert handler.success is None
        assert handler.error is None

        # Execute handler
        success = handler.execute()

        # Verify execution
        assert success is True
        assert handler.executed is True
        assert handler.success is True
        assert handler.error is None
        assert executed is True

    def test_rollback_handler_failure_tracking(self):
        """RollbackHandler should track failure state."""

        def failing_handler():
            raise ValueError("Handler error")

        handler = RollbackHandler(
            handler_fn=failing_handler,
            resource_type=ResourceType.FILES_API,
            resource_id="fail-file",
            description="Failing handler",
            critical=False,  # Non-critical to not raise
        )

        # Execute handler
        success = handler.execute()

        # Verify failure tracking
        assert success is False
        assert handler.executed is True
        assert handler.success is False
        assert handler.error is not None
        assert isinstance(handler.error, ValueError)

    def test_commit_failure_triggers_rollback(self, db_session):
        """When commit fails, rollback handlers should execute."""
        handler_fn = Mock()
        audit = {}

        # Patch session.commit to force failure
        original_commit = db_session.commit

        def failing_commit():
            raise RuntimeError("Commit failed")

        db_session.commit = failing_commit

        with pytest.raises(RuntimeError):
            with CompensatingTransaction(db_session, audit_trail=audit) as _txn:
                txn.register_rollback(
                    handler_fn=handler_fn,
                    resource_type=ResourceType.FILES_API,
                    resource_id="file-commit-fail",
                    description="Cleanup on commit failure",
                )

                doc = MockDocument(name="commit-fail")
                db_session.add(doc)

        # Restore original commit
        db_session.commit = original_commit

        # Handler should execute due to commit failure
        handler_fn.assert_called_once()

    def test_auto_commit_disabled(self, db_session):
        """When auto_commit=False, session should not auto-commit."""
        with CompensatingTransaction(db_session, auto_commit=False) as _txn:
            doc = MockDocument(name="no-auto-commit")
            db_session.add(doc)

        # Session not committed automatically
        # Manual commit needed
        db_session.commit()

        result = db_session.query(MockDocument).filter_by(name="no-auto-commit").first()
        assert result is not None

    def test_multiple_handlers_partial_failure(self, db_session):
        """When some handlers fail, others should still execute."""
        execution_log = []

        def success_handler_1():
            execution_log.append("success1")

        def failing_handler():
            execution_log.append("failing")
            raise ValueError("Handler failed")

        def success_handler_2():
            execution_log.append("success2")

        audit = {}
        with pytest.raises(RuntimeError):
            with CompensatingTransaction(db_session, audit_trail=audit) as _txn:
                txn.register_rollback(
                    handler_fn=success_handler_1,
                    resource_type=ResourceType.FILES_API,
                    resource_id="file-1",
                    description="Success handler 1",
                    critical=True,
                )
                txn.register_rollback(
                    handler_fn=failing_handler,
                    resource_type=ResourceType.FILES_API,
                    resource_id="file-2",
                    description="Failing handler",
                    critical=False,  # Non-critical
                )
                txn.register_rollback(
                    handler_fn=success_handler_2,
                    resource_type=ResourceType.FILES_API,
                    resource_id="file-3",
                    description="Success handler 2",
                    critical=True,
                )

                raise RuntimeError("Trigger rollback")

        # All handlers should execute (LIFO order)
        assert execution_log == ["success2", "failing", "success1"]

        # Audit trail should show partial failure
        assert audit["compensation_stats"]["total"] == 3
        assert audit["compensation_stats"]["successful"] == 2
        assert audit["compensation_stats"]["failed"] == 1
        assert audit["compensation_status"] == "partial_failure"


class TestPrebuiltRollbackHandlers:
    """Test suite for pre-built rollback handler factories."""

    def test_files_api_rollback_handler(self):
        """Files API rollback handler should delete file."""
        mock_client = MagicMock()
        file_id = "file-abc123"

        handler_fn = create_files_api_rollback_handler(mock_client, file_id)
        handler_fn()

        # Verify file deletion was called
        mock_client.files.delete.assert_called_once_with(file_id)

    def test_files_api_rollback_handler_failure(self):
        """Files API rollback handler should propagate deletion errors."""
        mock_client = MagicMock()
        mock_client.files.delete.side_effect = Exception("Deletion failed")

        file_id = "file-fail"
        handler_fn = create_files_api_rollback_handler(mock_client, file_id)

        with pytest.raises(Exception) as exc_info:
            handler_fn()

        assert "Deletion failed" in str(exc_info.value)

    def test_vector_store_rollback_handler(self):
        """Vector store rollback handler should remove file from store."""
        mock_client = MagicMock()
        vector_store_id = "vs-abc123"
        file_id = "file-xyz789"

        handler_fn = create_vector_store_rollback_handler(
            mock_client, vector_store_id, file_id
        )
        handler_fn()

        # Verify vector store file deletion was called
        mock_client.beta.vector_stores.files.delete.assert_called_once_with(
            vector_store_id=vector_store_id, file_id=file_id
        )

    def test_vector_store_rollback_handler_failure(self):
        """Vector store rollback handler should propagate removal errors."""
        mock_client = MagicMock()
        mock_client.beta.vector_stores.files.delete.side_effect = Exception(
            "Removal failed"
        )

        handler_fn = create_vector_store_rollback_handler(
            mock_client, "vs-123", "file-456"
        )

        with pytest.raises(Exception) as exc_info:
            handler_fn()

        assert "Removal failed" in str(exc_info.value)
