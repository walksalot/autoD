"""
Database session management and connection handling.
Provides context managers for safe database operations.
"""

from contextlib import contextmanager
from typing import Generator
from sqlalchemy import create_engine, event, Engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from src.models import Base


class DatabaseManager:
    """
    Manages database connections and session lifecycle.
    Handles connection pooling, health checks, and migrations.
    """

    def __init__(self, db_url: str, echo: bool = False):
        """
        Initialize database manager.

        Args:
            db_url: SQLAlchemy database URL
            echo: If True, log all SQL statements
        """
        self.db_url = db_url
        self.echo = echo

        # Configure engine based on database type
        if db_url.startswith("sqlite"):
            # SQLite-specific configuration
            self.engine = create_engine(
                db_url,
                echo=echo,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,  # Use static pool for SQLite
            )

            # Enable foreign keys for SQLite
            @event.listens_for(Engine, "connect")
            def set_sqlite_pragma(dbapi_conn, connection_record):
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()

        else:
            # PostgreSQL configuration
            self.engine = create_engine(
                db_url,
                echo=echo,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True,  # Verify connections before use
                pool_recycle=3600,  # Recycle connections after 1 hour
            )

        self.SessionLocal = sessionmaker(
            bind=self.engine,
            autocommit=False,
            autoflush=False,
        )

    def create_tables(self) -> None:
        """Create all database tables."""
        Base.metadata.create_all(bind=self.engine)

    def drop_tables(self) -> None:
        """Drop all database tables. Use with caution!"""
        Base.metadata.drop_all(bind=self.engine)

    def health_check(self) -> bool:
        """
        Perform database health check.

        Returns:
            True if database is accessible, False otherwise
        """
        try:
            from sqlalchemy import text

            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """
        Context manager for database sessions.
        Automatically commits on success, rolls back on error.

        Usage:
            with db_manager.get_session() as session:
                document = Document(...)
                session.add(document)
                # Automatic commit on exit

        Yields:
            SQLAlchemy Session instance
        """
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


# Example usage
if __name__ == "__main__":
    from src.models import Document
    import os

    # Use test database
    db_url = os.getenv("PAPER_AUTOPILOT_DB_URL", "sqlite:///test_paper_autopilot.db")
    db_manager = DatabaseManager(db_url, echo=True)

    # Create tables
    print("Creating tables...")
    db_manager.create_tables()

    # Health check
    print("\nHealth check...")
    if db_manager.health_check():
        print("✅ Database is healthy")
    else:
        print("❌ Database connection failed")

    # Insert test document
    print("\nInserting test document...")
    with db_manager.get_session() as session:
        doc = Document(
            sha256_hex="a" * 64,
            sha256_base64="b" * 44,
            original_filename="test.pdf",
            file_size_bytes=1024,
            model_used="gpt-5-mini",
        )
        session.add(doc)
        print(f"✅ Inserted: {doc}")

    # Query test document
    print("\nQuerying documents...")
    with db_manager.get_session() as session:
        docs = session.query(Document).all()
        print(f"✅ Found {len(docs)} documents")
        for doc in docs:
            print(f"   {doc}")
