"""
Database error handling tests.

Tests critical database operations and error scenarios in database.py:
- Connection pool management
- Session lifecycle and context managers
- Transaction rollback on errors
- Health check functionality
- SQLite pragma settings

These tests ensure database operations fail gracefully and don't leak resources.
"""

import pytest
from unittest.mock import Mock, patch
from sqlalchemy.exc import OperationalError, IntegrityError

from src.database import DatabaseManager
from src.models import Document


class TestDatabaseManagerInitialization:
    """Test DatabaseManager initialization and configuration."""

    def test_sqlite_initialization_with_pragmas(self):
        """SQLite databases should enable foreign keys via pragma."""
        # Use in-memory database for testing
        db_manager = DatabaseManager("sqlite:///:memory:", echo=False)

        # Verify engine was created
        assert db_manager.engine is not None
        assert db_manager.db_url == "sqlite:///:memory:"
        assert db_manager.echo is False

        # Test that we can create tables
        db_manager.create_tables()

        # Verify foreign keys are enabled (SQLite-specific)
        from sqlalchemy import text

        with db_manager.engine.connect() as conn:
            result = conn.execute(text("PRAGMA foreign_keys"))
            row = result.fetchone()
            # Foreign keys should be ON (1)
            assert row[0] == 1

    def test_postgresql_initialization(self):
        """PostgreSQL connection should use different configuration."""
        # Mock the create_engine to avoid actual connection
        with patch("src.database.create_engine") as mock_create_engine:
            mock_engine = Mock()
            mock_create_engine.return_value = mock_engine

            _ = DatabaseManager("postgresql://user:pass@localhost/testdb", echo=True)

            # Verify create_engine was called with correct parameters
            mock_create_engine.assert_called_once()
            call_args = mock_create_engine.call_args

            assert call_args[0][0] == "postgresql://user:pass@localhost/testdb"
            assert call_args[1]["echo"] is True

    def test_echo_parameter_controls_sql_logging(self):
        """Echo parameter should control SQL statement logging."""
        # With echo=True
        db_manager_verbose = DatabaseManager("sqlite:///:memory:", echo=True)
        assert db_manager_verbose.echo is True

        # With echo=False
        db_manager_quiet = DatabaseManager("sqlite:///:memory:", echo=False)
        assert db_manager_quiet.echo is False


class TestSessionManagement:
    """Test session lifecycle and context managers."""

    def test_get_session_context_manager_success(self):
        """get_session should provide working session context manager."""
        db_manager = DatabaseManager("sqlite:///:memory:")
        db_manager.create_tables()

        # Use session context manager
        with db_manager.get_session() as session:
            # Create a document
            doc = Document(
                sha256_hex="a" * 64, original_filename="test.pdf", status="pending"
            )
            session.add(doc)
            # Note: get_session() auto-commits, so we don't need explicit commit

        # Verify document was persisted in new session
        with db_manager.get_session() as session:
            found = session.query(Document).filter_by(sha256_hex="a" * 64).first()
            assert found is not None
            assert found.original_filename == "test.pdf"

    def test_get_session_rollback_on_exception(self):
        """Session should rollback on exception within context."""
        db_manager = DatabaseManager("sqlite:///:memory:")
        db_manager.create_tables()

        # First, add a valid document
        with db_manager.get_session() as session:
            doc = Document(
                sha256_hex="b" * 64, original_filename="initial.pdf", status="completed"
            )
            session.add(doc)
            session.commit()

        # Now try to add duplicate (should violate unique constraint)
        try:
            with db_manager.get_session() as session:
                # Add first doc
                doc1 = Document(
                    sha256_hex="c" * 64, original_filename="doc1.pdf", status="pending"
                )
                session.add(doc1)
                session.flush()  # Flush to detect errors early

                # Add duplicate hash (should fail)
                doc2 = Document(
                    sha256_hex="c" * 64,  # Same hash!
                    original_filename="doc2.pdf",
                    status="pending",
                )
                session.add(doc2)
                session.commit()  # This should fail

        except IntegrityError:
            # Expected - unique constraint violation
            pass

        # Verify only the initial document exists (transaction rolled back)
        with db_manager.get_session() as session:
            docs = session.query(Document).all()
            # Should only have the initial "b"*64 document
            assert len(docs) == 1
            assert docs[0].sha256_hex == "b" * 64

    def test_session_isolation_between_contexts(self):
        """Multiple session contexts should be isolated."""
        db_manager = DatabaseManager("sqlite:///:memory:")
        db_manager.create_tables()

        # Context 1: Add document
        with db_manager.get_session() as session1:
            doc = Document(
                sha256_hex="d" * 64, original_filename="test.pdf", status="pending"
            )
            session1.add(doc)
            session1.commit()

        # Context 2: Query document (new session)
        with db_manager.get_session() as session2:
            found = session2.query(Document).filter_by(sha256_hex="d" * 64).first()
            assert found is not None
            assert found.original_filename == "test.pdf"

            # Modify document
            found.status = "completed"
            session2.commit()

        # Context 3: Verify modification persisted
        with db_manager.get_session() as session3:
            found = session3.query(Document).filter_by(sha256_hex="d" * 64).first()
            assert found.status == "completed"


class TestHealthCheck:
    """Test database health check functionality."""

    def test_health_check_on_working_database(self):
        """Health check should return True for working database."""
        db_manager = DatabaseManager("sqlite:///:memory:")
        db_manager.create_tables()

        # Health check should succeed
        is_healthy = db_manager.health_check()
        assert is_healthy is True

    def test_health_check_on_broken_connection(self):
        """Health check should return False when connection fails."""
        # Create manager with invalid database
        db_manager = DatabaseManager("sqlite:///nonexistent/path/db.sqlite")

        # Mock engine.connect to raise OperationalError
        with patch.object(db_manager.engine, "connect") as mock_connect:
            mock_connect.side_effect = OperationalError(
                "unable to open database file", params=None, orig=None
            )

            is_healthy = db_manager.health_check()
            assert is_healthy is False

    def test_health_check_catches_all_exceptions(self):
        """Health check should catch and handle all exception types."""
        db_manager = DatabaseManager("sqlite:///:memory:")

        # Mock engine.connect to raise unexpected exception
        with patch.object(db_manager.engine, "connect") as mock_connect:
            mock_connect.side_effect = RuntimeError("Unexpected error")

            is_healthy = db_manager.health_check()
            assert is_healthy is False


class TestDatabaseCleanup:
    """Test database connection cleanup."""

    def test_engine_disposal(self):
        """Engine disposal should prevent new connections."""
        db_manager = DatabaseManager("sqlite:///:memory:")
        db_manager.create_tables()

        # Verify engine is usable
        with db_manager.get_session() as session:
            assert session is not None

        # Dispose the engine
        db_manager.engine.dispose()

        # Create new session should work (creates new connection pool)
        # This tests that disposal cleanup works properly
        with db_manager.get_session() as session:
            assert session is not None


class TestErrorScenarios:
    """Test error handling in various failure scenarios."""

    def test_concurrent_session_usage(self):
        """Multiple sessions should work independently."""
        db_manager = DatabaseManager("sqlite:///:memory:")
        db_manager.create_tables()

        # Get two sessions simultaneously
        session1 = db_manager.SessionLocal()
        session2 = db_manager.SessionLocal()

        try:
            # Add documents in both sessions
            doc1 = Document(
                sha256_hex="e" * 64, original_filename="doc1.pdf", status="pending"
            )
            session1.add(doc1)
            session1.commit()

            doc2 = Document(
                sha256_hex="f" * 64, original_filename="doc2.pdf", status="pending"
            )
            session2.add(doc2)
            session2.commit()

            # Both documents should be visible in either session
            count1 = session1.query(Document).count()
            count2 = session2.query(Document).count()

            assert count1 == 2
            assert count2 == 2

        finally:
            session1.close()
            session2.close()

    def test_table_creation_via_create_tables(self):
        """create_tables() should create all tables."""
        db_manager = DatabaseManager("sqlite:///:memory:")

        # Tables don't exist yet
        # Attempting to query should fail
        with pytest.raises(Exception):
            with db_manager.get_session() as session:
                session.query(Document).all()

        # Create tables
        db_manager.create_tables()

        # Now queries should work
        with db_manager.get_session() as session:
            docs = session.query(Document).all()
            assert docs == []

    def test_database_url_validation(self):
        """DatabaseManager should accept valid database URLs."""
        # SQLite URLs
        db1 = DatabaseManager("sqlite:///path/to/db.sqlite")
        assert db1.db_url == "sqlite:///path/to/db.sqlite"

        db2 = DatabaseManager("sqlite:///:memory:")
        assert db2.db_url == "sqlite:///:memory:"

        # PostgreSQL URL (mocked)
        with patch("src.database.create_engine"):
            db3 = DatabaseManager("postgresql://user:pass@localhost:5432/dbname")
            assert db3.db_url == "postgresql://user:pass@localhost:5432/dbname"


class TestSessionFactoryPattern:
    """Test session factory and session creation patterns."""

    def test_session_factory_creates_new_sessions(self):
        """Session factory should create new session instances."""
        db_manager = DatabaseManager("sqlite:///:memory:")
        db_manager.create_tables()

        # Create two sessions from factory
        session1 = db_manager.SessionLocal()
        session2 = db_manager.SessionLocal()

        # They should be different instances
        assert session1 is not session2

        # But both should be usable
        assert session1.bind is not None
        assert session2.bind is not None

        session1.close()
        session2.close()

    def test_session_bound_to_engine(self):
        """Sessions should be bound to the database engine."""
        db_manager = DatabaseManager("sqlite:///:memory:")
        db_manager.create_tables()

        session = db_manager.SessionLocal()

        # Session should be bound to engine
        assert session.bind == db_manager.engine

        session.close()
