"""Integration tests for error recovery with CompensatingTransaction.

These tests verify end-to-end error recovery scenarios including:
- Files API upload failures with rollback
- Vector Store upload failures with rollback
- Database commit failures with compensation
- Multi-step operations with LIFO cleanup
- Critical vs non-critical handler behavior
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import Session, declarative_base
from datetime import datetime

from src.transactions import (
    CompensatingTransaction,
    ResourceType,
    create_files_api_rollback_handler,
    create_vector_store_rollback_handler,
)

Base = declarative_base()


class TestDocument(Base):
    """Test model for integration tests."""

    __tablename__ = "test_documents"

    id = Column(Integer, primary_key=True)
    sha256_hex = Column(String, unique=True, nullable=False)
    file_id = Column(String, nullable=True)
    vector_store_id = Column(String, nullable=True)


class TestErrorRecoveryFilesAPI:
    """Test Files API error recovery scenarios."""

    @pytest.fixture
    def db_session(self):
        """Create in-memory database session for testing."""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        session = Session(engine)
        yield session
        session.close()

    @pytest.fixture
    def mock_openai_client(self):
        """Mock OpenAI client for Files API."""
        client = Mock()
        client.files = Mock()
        client.files.create = Mock(return_value=Mock(id="file-abc123"))
        client.files.delete = Mock()
        return client

    def test_files_api_upload_success_no_rollback(self, db_session, mock_openai_client):
        """Test successful Files API upload with DB commit - no rollback."""
        audit = {}

        with CompensatingTransaction(db_session, audit_trail=audit) as txn:
            # Upload file
            file_obj = mock_openai_client.files.create(file="test.pdf")

            # Register rollback
            handler_fn = create_files_api_rollback_handler(
                mock_openai_client, file_obj.id
            )
            txn.register_rollback(
                handler_fn=handler_fn,
                resource_type=ResourceType.FILES_API,
                resource_id=file_obj.id,
                description="Delete test.pdf from Files API",
            )

            # Create DB record
            doc = TestDocument(
                sha256_hex="abc123",
                file_id=file_obj.id,
            )
            db_session.add(doc)

        # Verify success
        assert audit["status"] == "success"
        assert audit["compensation_needed"] is False
        assert mock_openai_client.files.create.called
        assert not mock_openai_client.files.delete.called  # No rollback

        # Verify DB record exists
        assert db_session.query(TestDocument).count() == 1

    def test_files_api_upload_db_commit_failure_triggers_rollback(
        self, db_session, mock_openai_client
    ):
        """Test Files API upload → DB commit fails → Files API rollback."""
        audit = {}

        # Patch commit to fail
        original_commit = db_session.commit
        def failing_commit():
            raise RuntimeError("Database connection lost")
        db_session.commit = failing_commit

        try:
            with pytest.raises(RuntimeError, match="Database connection lost"):
                with CompensatingTransaction(db_session, audit_trail=audit) as txn:
                    # Upload file
                    file_obj = mock_openai_client.files.create(file="test.pdf")

                    # Register rollback
                    handler_fn = create_files_api_rollback_handler(
                        mock_openai_client, file_obj.id
                    )
                    txn.register_rollback(
                        handler_fn=handler_fn,
                        resource_type=ResourceType.FILES_API,
                        resource_id=file_obj.id,
                        description="Delete test.pdf from Files API",
                    )

                    # Create DB record
                    doc = TestDocument(
                        sha256_hex="abc123",
                        file_id=file_obj.id,
                    )
                    db_session.add(doc)
        finally:
            # Restore commit
            db_session.commit = original_commit

        # Verify rollback executed
        assert audit["status"] == "failed"
        assert audit["compensation_needed"] is True
        assert audit["compensation_status"] == "success"
        assert mock_openai_client.files.delete.called_with("file-abc123")

        # Verify DB record does not exist
        assert db_session.query(TestDocument).count() == 0

    def test_files_api_upload_and_rollback_both_fail(
        self, db_session, mock_openai_client
    ):
        """Test Files API upload succeeds, DB fails, Files API rollback fails."""
        audit = {}

        # Make Files API delete fail
        mock_openai_client.files.delete.side_effect = Exception(
            "Files API unavailable"
        )

        # Patch commit to fail
        original_commit = db_session.commit
        def failing_commit():
            raise RuntimeError("Database connection lost")
        db_session.commit = failing_commit

        try:
            # Should raise the Files API rollback exception (critical handler)
            with pytest.raises(Exception, match="Files API unavailable"):
                with CompensatingTransaction(db_session, audit_trail=audit) as txn:
                    # Upload file
                    file_obj = mock_openai_client.files.create(file="test.pdf")

                    # Register rollback (critical=True by default)
                    handler_fn = create_files_api_rollback_handler(
                        mock_openai_client, file_obj.id
                    )
                    txn.register_rollback(
                        handler_fn=handler_fn,
                        resource_type=ResourceType.FILES_API,
                        resource_id=file_obj.id,
                        description="Delete test.pdf from Files API",
                    )

                    # Create DB record
                    doc = TestDocument(
                        sha256_hex="abc123",
                        file_id=file_obj.id,
                    )
                    db_session.add(doc)
        finally:
            # Restore commit
            db_session.commit = original_commit

        # Verify rollback attempted but failed
        assert audit["status"] == "failed"
        assert audit["compensation_needed"] is True
        assert audit["compensation_status"] == "partial_failure"
        assert audit["compensation_stats"]["failed"] == 1


class TestErrorRecoveryVectorStore:
    """Test Vector Store error recovery scenarios."""

    @pytest.fixture
    def db_session(self):
        """Create in-memory database session for testing."""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        session = Session(engine)
        yield session
        session.close()

    @pytest.fixture
    def mock_openai_client(self):
        """Mock OpenAI client for Vector Store API."""
        client = Mock()
        client.files = Mock()
        client.files.create = Mock(return_value=Mock(id="file-abc123"))
        client.files.delete = Mock()

        client.beta = Mock()
        client.beta.vector_stores = Mock()
        client.beta.vector_stores.files = Mock()
        client.beta.vector_stores.files.create = Mock(
            return_value=Mock(id="file-abc123")
        )
        client.beta.vector_stores.files.delete = Mock()

        return client

    def test_multi_step_files_and_vector_store_success(
        self, db_session, mock_openai_client
    ):
        """Test Files API + Vector Store → DB commit succeeds."""
        audit = {}
        vector_store_id = "vs_test123"

        with CompensatingTransaction(db_session, audit_trail=audit) as txn:
            # Step 1: Upload to Files API
            file_obj = mock_openai_client.files.create(file="test.pdf")

            # Register Files API rollback
            files_handler = create_files_api_rollback_handler(
                mock_openai_client, file_obj.id
            )
            txn.register_rollback(
                handler_fn=files_handler,
                resource_type=ResourceType.FILES_API,
                resource_id=file_obj.id,
                description="Delete file from Files API",
            )

            # Step 2: Upload to Vector Store
            vs_file = mock_openai_client.beta.vector_stores.files.create(
                vector_store_id=vector_store_id,
                file_id=file_obj.id,
            )

            # Register Vector Store rollback
            vs_handler = create_vector_store_rollback_handler(
                mock_openai_client, vector_store_id, vs_file.id
            )
            txn.register_rollback(
                handler_fn=vs_handler,
                resource_type=ResourceType.VECTOR_STORE,
                resource_id=vs_file.id,
                description="Remove file from Vector Store",
            )

            # Step 3: Create DB record
            doc = TestDocument(
                sha256_hex="abc123",
                file_id=file_obj.id,
                vector_store_id=vector_store_id,
            )
            db_session.add(doc)

        # Verify success - no rollback
        assert audit["status"] == "success"
        assert audit["compensation_needed"] is False
        assert audit["handlers_registered"] == 2
        assert not mock_openai_client.files.delete.called
        assert not mock_openai_client.beta.vector_stores.files.delete.called

    def test_multi_step_db_commit_fails_lifo_rollback(
        self, db_session, mock_openai_client
    ):
        """Test Files API + Vector Store → DB fails → LIFO rollback."""
        audit = {}
        vector_store_id = "vs_test123"

        # Patch commit to fail
        original_commit = db_session.commit
        def failing_commit():
            raise RuntimeError("Database deadlock")
        db_session.commit = failing_commit

        try:
            with pytest.raises(RuntimeError, match="Database deadlock"):
                with CompensatingTransaction(db_session, audit_trail=audit) as txn:
                    # Step 1: Upload to Files API
                    file_obj = mock_openai_client.files.create(file="test.pdf")

                    files_handler = create_files_api_rollback_handler(
                        mock_openai_client, file_obj.id
                    )
                    txn.register_rollback(
                        handler_fn=files_handler,
                        resource_type=ResourceType.FILES_API,
                        resource_id=file_obj.id,
                        description="Delete file from Files API",
                    )

                    # Step 2: Upload to Vector Store
                    vs_file = mock_openai_client.beta.vector_stores.files.create(
                        vector_store_id=vector_store_id,
                        file_id=file_obj.id,
                    )

                    vs_handler = create_vector_store_rollback_handler(
                        mock_openai_client, vector_store_id, vs_file.id
                    )
                    txn.register_rollback(
                        handler_fn=vs_handler,
                        resource_type=ResourceType.VECTOR_STORE,
                        resource_id=vs_file.id,
                        description="Remove file from Vector Store",
                    )

                    # Step 3: Create DB record
                    doc = TestDocument(
                        sha256_hex="abc123",
                        file_id=file_obj.id,
                        vector_store_id=vector_store_id,
                    )
                    db_session.add(doc)
        finally:
            # Restore commit
            db_session.commit = original_commit

        # Verify LIFO rollback (Vector Store first, then Files API)
        assert audit["status"] == "failed"
        assert audit["compensation_needed"] is True
        assert audit["compensation_status"] == "success"
        assert audit["compensation_stats"]["total"] == 2
        assert audit["compensation_stats"]["successful"] == 2

        # Verify both rollbacks executed
        assert mock_openai_client.beta.vector_stores.files.delete.called
        assert mock_openai_client.files.delete.called

        # Verify order: Vector Store deleted first (LIFO)
        handlers = audit["compensation_handlers"]
        assert len(handlers) == 2
        assert handlers[0]["resource_type"] == "vector_store"  # First
        assert handlers[1]["resource_type"] == "files_api"     # Second


class TestErrorRecoveryCriticalVsNonCritical:
    """Test critical vs non-critical handler behavior."""

    @pytest.fixture
    def db_session(self):
        """Create in-memory database session for testing."""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        session = Session(engine)
        yield session
        session.close()

    def test_non_critical_handler_failure_allows_graceful_degradation(
        self, db_session
    ):
        """Test that non-critical handler failures don't stop execution."""
        audit = {}

        # Create handlers with different criticality
        critical_handler = Mock()
        non_critical_handler_1 = Mock(side_effect=Exception("Analytics API down"))
        non_critical_handler_2 = Mock()

        # Patch commit to fail
        original_commit = db_session.commit
        def failing_commit():
            raise RuntimeError("Network timeout")
        db_session.commit = failing_commit

        try:
            with pytest.raises(RuntimeError, match="Network timeout"):
                with CompensatingTransaction(db_session, audit_trail=audit) as txn:
                    # Register handlers in order
                    txn.register_rollback(
                        handler_fn=critical_handler,
                        resource_type=ResourceType.FILES_API,
                        resource_id="file-123",
                        description="Critical: Delete uploaded file",
                        critical=True,
                    )

                    txn.register_rollback(
                        handler_fn=non_critical_handler_1,
                        resource_type=ResourceType.CUSTOM,
                        resource_id="analytics-123",
                        description="Non-critical: Send analytics event",
                        critical=False,
                    )

                    txn.register_rollback(
                        handler_fn=non_critical_handler_2,
                        resource_type=ResourceType.CUSTOM,
                        resource_id="cache-123",
                        description="Non-critical: Invalidate cache",
                        critical=False,
                    )

                    # Trigger commit failure
                    doc = TestDocument(sha256_hex="test")
                    db_session.add(doc)
        finally:
            db_session.commit = original_commit

        # Verify graceful degradation
        assert audit["compensation_status"] == "partial_failure"
        assert audit["compensation_stats"]["total"] == 3
        assert audit["compensation_stats"]["successful"] == 2  # critical + 1 non-critical
        assert audit["compensation_stats"]["failed"] == 1      # 1 non-critical

        # Verify all handlers attempted (LIFO order)
        assert non_critical_handler_2.called
        assert non_critical_handler_1.called
        assert critical_handler.called

    def test_critical_handler_failure_raises_exception(self, db_session):
        """Test that critical handler failures raise exceptions."""
        audit = {}

        critical_handler = Mock(side_effect=Exception("Files API unavailable"))

        # Patch commit to fail
        original_commit = db_session.commit
        def failing_commit():
            raise RuntimeError("DB error")
        db_session.commit = failing_commit

        try:
            # Critical handler failure should raise
            with pytest.raises(Exception, match="Files API unavailable"):
                with CompensatingTransaction(db_session, audit_trail=audit) as txn:
                    txn.register_rollback(
                        handler_fn=critical_handler,
                        resource_type=ResourceType.FILES_API,
                        resource_id="file-123",
                        description="Critical: Delete file",
                        critical=True,
                    )

                    doc = TestDocument(sha256_hex="test")
                    db_session.add(doc)
        finally:
            db_session.commit = original_commit

        # Verify critical failure recorded
        assert audit["compensation_status"] == "partial_failure"
        assert audit["compensation_stats"]["failed"] == 1


class TestErrorRecoveryAuditTrail:
    """Test comprehensive audit trail functionality."""

    @pytest.fixture
    def db_session(self):
        """Create in-memory database session for testing."""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        session = Session(engine)
        yield session
        session.close()

    def test_audit_trail_captures_complete_lifecycle(self, db_session):
        """Test that audit trail captures all transaction events."""
        audit = {}

        # Patch commit to fail
        original_commit = db_session.commit
        def failing_commit():
            raise RuntimeError("Commit failed")
        db_session.commit = failing_commit

        try:
            with pytest.raises(RuntimeError):
                with CompensatingTransaction(db_session, audit_trail=audit) as txn:
                    txn.register_rollback(
                        handler_fn=Mock(),
                        resource_type=ResourceType.FILES_API,
                        resource_id="file-123",
                        description="Test rollback",
                    )

                    doc = TestDocument(sha256_hex="test")
                    db_session.add(doc)
        finally:
            db_session.commit = original_commit

        # Verify audit trail completeness
        assert "started_at" in audit
        assert "rolled_back_at" in audit
        assert "status" in audit
        assert audit["status"] == "failed"
        assert "error" in audit
        assert audit["error"] == "Commit failed"
        assert "error_type" in audit
        assert audit["error_type"] == "RuntimeError"

        assert "handlers_registered" in audit
        assert audit["handlers_registered"] == 1

        assert "resources" in audit
        assert len(audit["resources"]) == 1
        assert audit["resources"][0]["type"] == "files_api"
        assert audit["resources"][0]["id"] == "file-123"

        assert "compensation_needed" in audit
        assert audit["compensation_needed"] is True

        assert "compensation_handlers" in audit
        assert len(audit["compensation_handlers"]) == 1

        assert "compensation_stats" in audit
        assert audit["compensation_stats"]["total"] == 1
        assert audit["compensation_stats"]["executed"] == 1
        assert audit["compensation_stats"]["successful"] == 1

        assert "compensation_status" in audit
        assert audit["compensation_status"] == "success"
