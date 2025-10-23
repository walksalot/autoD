"""
Compensating transaction pattern for external API calls.

Prevents orphaned records when DB commits but external API operations fail.
Provides cleanup logic for external resources like OpenAI Files API uploads.

ENHANCED VERSION (TD1 - Error Handling Consolidation):
- Multi-step rollback handler registration
- Resource lifecycle tracking
- Comprehensive audit trail
- Critical vs non-critical operations
- Integration with retry logic and circuit breaker
- Pre-built handlers for Files API, Vector Store, Database
"""

from contextlib import contextmanager
import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from typing import Optional, Callable, Dict, Any, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ResourceType(Enum):
    """Types of external resources that can be cleaned up."""

    FILES_API = "files_api"
    VECTOR_STORE = "vector_store"
    DATABASE = "database"
    CUSTOM = "custom"


@dataclass
class RollbackHandler:
    """
    Handler for rolling back a specific resource operation.

    Attributes:
        handler_fn: Callable to execute rollback (e.g., delete file)
        resource_type: Type of resource being cleaned up
        resource_id: Unique identifier for the resource (e.g., file_id)
        description: Human-readable description of the operation
        critical: If True, rollback failure causes transaction to fail
        executed: Whether this handler has been executed
        success: Whether handler execution succeeded
        error: Exception if handler failed

    Example:
        def cleanup_file():
            client.files.delete("file-abc123")

        handler = RollbackHandler(
            handler_fn=cleanup_file,
            resource_type=ResourceType.FILES_API,
            resource_id="file-abc123",
            description="Delete uploaded PDF from Files API",
            critical=True
        )
    """

    handler_fn: Callable[[], None]
    resource_type: ResourceType
    resource_id: str
    description: str
    critical: bool = True
    executed: bool = False
    success: Optional[bool] = None
    error: Optional[Exception] = None

    def execute(self) -> bool:
        """
        Execute the rollback handler.

        Returns:
            True if successful, False otherwise

        Raises:
            Exception: Only if critical=True and handler fails
        """
        self.executed = True
        try:
            logger.info(
                f"Executing rollback: {self.description}",
                extra={
                    "resource_type": self.resource_type.value,
                    "resource_id": self.resource_id,
                    "critical": self.critical,
                },
            )
            self.handler_fn()
            self.success = True
            logger.info(
                f"Rollback succeeded: {self.description}",
                extra={
                    "resource_type": self.resource_type.value,
                    "resource_id": self.resource_id,
                },
            )
            return True
        except Exception as e:
            self.error = e
            self.success = False
            level = logging.ERROR if self.critical else logging.WARNING
            logger.log(
                level,
                f"Rollback failed: {self.description} - {e}",
                exc_info=True,
                extra={
                    "resource_type": self.resource_type.value,
                    "resource_id": self.resource_id,
                    "critical": self.critical,
                    "error": str(e),
                },
            )
            if self.critical:
                raise
            return False


class CompensatingTransaction:
    """
    Enhanced transaction manager with multi-step rollback support.

    Features:
    - Register multiple rollback handlers (executed in LIFO order)
    - Track resource lifecycle (created, committed, rolled back)
    - Comprehensive audit trail with timestamps
    - Critical vs non-critical operations
    - Graceful degradation for non-critical failures

    Usage:
        with CompensatingTransaction(session) as txn:
            # Upload file
            file_obj = client.files.create(file=pdf)
            txn.register_rollback(
                handler_fn=lambda: client.files.delete(file_obj.id),
                resource_type=ResourceType.FILES_API,
                resource_id=file_obj.id,
                description="Delete uploaded file",
                critical=True
            )

            # Create database record
            doc = Document(file_id=file_obj.id, ...)
            session.add(doc)

            # If commit succeeds → no rollback
            # If commit fails → deletes file, rolls back DB

        # Access audit trail
        print(txn.audit_trail)
    """

    def __init__(
        self,
        session: Session,
        audit_trail: Optional[Dict[str, Any]] = None,
        auto_commit: bool = True,
    ):
        """
        Initialize compensating transaction.

        Args:
            session: SQLAlchemy session for database operations
            audit_trail: Optional dict to populate with transaction events
            auto_commit: If True, commit on __exit__ success (default: True)
        """
        self.session = session
        self.rollback_handlers: List[RollbackHandler] = []
        self.audit_trail = audit_trail if audit_trail is not None else {}
        self.auto_commit = auto_commit
        self._committed = False
        self._rolled_back = False

    def register_rollback(
        self,
        handler_fn: Callable[[], None],
        resource_type: ResourceType,
        resource_id: str,
        description: str,
        critical: bool = True,
    ) -> RollbackHandler:
        """
        Register a rollback handler for a resource operation.

        Handlers are executed in LIFO order (last registered, first executed).
        This ensures dependencies are cleaned up in reverse order.

        Args:
            handler_fn: Callable to execute rollback (e.g., delete file)
            resource_type: Type of resource being cleaned up
            resource_id: Unique identifier for the resource
            description: Human-readable description of the operation
            critical: If True, rollback failure causes transaction to fail

        Returns:
            The created RollbackHandler instance

        Example:
            txn.register_rollback(
                handler_fn=lambda: client.files.delete("file-abc"),
                resource_type=ResourceType.FILES_API,
                resource_id="file-abc",
                description="Delete file-abc from Files API",
                critical=True
            )
        """
        handler = RollbackHandler(
            handler_fn=handler_fn,
            resource_type=resource_type,
            resource_id=resource_id,
            description=description,
            critical=critical,
        )
        self.rollback_handlers.append(handler)

        logger.debug(
            f"Registered rollback handler: {description}",
            extra={
                "resource_type": resource_type.value,
                "resource_id": resource_id,
                "critical": critical,
                "total_handlers": len(self.rollback_handlers),
            },
        )

        return handler

    def __enter__(self) -> "CompensatingTransaction":
        """Begin transaction and start audit trail."""
        self.audit_trail["started_at"] = datetime.now(timezone.utc).isoformat()
        self.audit_trail["handlers_registered"] = 0
        self.audit_trail["resources"] = []

        logger.info(
            "Compensating transaction started",
            extra={"audit_trail": self.audit_trail},
        )

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Commit or rollback with compensation.

        If no exception occurred:
        - Commit database session (if auto_commit=True)
        - Mark transaction as successful
        - No rollback handlers executed

        If exception occurred:
        - Rollback database session
        - Execute rollback handlers in LIFO order
        - Record audit trail for all operations
        - Re-raise original exception

        Args:
            exc_type: Exception type (None if no exception)
            exc_val: Exception value (None if no exception)
            exc_tb: Exception traceback (None if no exception)

        Returns:
            False to re-raise exception (if any)
        """
        self.audit_trail["handlers_registered"] = len(self.rollback_handlers)
        self.audit_trail["resources"] = [
            {
                "type": h.resource_type.value,
                "id": h.resource_id,
                "description": h.description,
                "critical": h.critical,
            }
            for h in self.rollback_handlers
        ]

        commit_error_occurred = None

        if exc_type is None:
            # No exception - commit if auto_commit enabled
            try:
                if self.auto_commit:
                    self.session.commit()
                    self._committed = True

                self.audit_trail["committed_at"] = datetime.now(
                    timezone.utc
                ).isoformat()
                self.audit_trail["status"] = "success"
                self.audit_trail["compensation_needed"] = False

                logger.info(
                    "Transaction committed successfully",
                    extra={"audit_trail": self.audit_trail},
                )

                return False  # Don't suppress any exception

            except Exception as commit_error:
                # Commit failed - trigger rollback
                logger.error(
                    f"Commit failed: {commit_error}",
                    exc_info=True,
                    extra={"audit_trail": self.audit_trail},
                )
                # Store commit error for re-raising
                commit_error_occurred = commit_error
                exc_type = type(commit_error)
                exc_val = commit_error

        # Exception occurred or commit failed - rollback
        try:
            self._execute_rollback(exc_type, exc_val)
        except Exception as rollback_error:
            # Critical handler failed during rollback - this takes precedence
            raise rollback_error

        # Re-raise exception - either from original context or from commit failure
        if commit_error_occurred:
            raise commit_error_occurred

        return False  # Re-raise original exception

    def _execute_rollback(self, exc_type, exc_val):
        """
        Execute rollback of database and all registered handlers.

        Args:
            exc_type: Exception type that triggered rollback
            exc_val: Exception value
        """
        self.audit_trail["rolled_back_at"] = datetime.now(timezone.utc).isoformat()
        self.audit_trail["status"] = "failed"
        self.audit_trail["error"] = str(exc_val)
        self.audit_trail["error_type"] = exc_type.__name__ if exc_type else "Unknown"

        logger.error(
            f"Transaction failed, executing rollback: {exc_val}",
            exc_info=True,
            extra={"audit_trail": self.audit_trail},
        )

        # Rollback database session
        try:
            self.session.rollback()
            self._rolled_back = True
            logger.info("Database session rolled back")
        except Exception as db_rollback_error:
            logger.error(
                f"Database rollback failed: {db_rollback_error}",
                exc_info=True,
            )

        # Execute compensation handlers in LIFO order
        critical_handler_error = None  # Track critical handler failures

        if self.rollback_handlers:
            self.audit_trail["compensation_needed"] = True
            self.audit_trail["compensation_handlers"] = []

            logger.info(
                f"Executing {len(self.rollback_handlers)} rollback handlers (LIFO order)"
            )

            # Reverse order (LIFO)
            for handler in reversed(self.rollback_handlers):
                handler_result = {
                    "resource_type": handler.resource_type.value,
                    "resource_id": handler.resource_id,
                    "description": handler.description,
                    "critical": handler.critical,
                }

                try:
                    success = handler.execute()
                    handler_result["executed"] = True
                    handler_result["success"] = success
                    if handler.error:
                        handler_result["error"] = str(handler.error)
                except Exception as handler_error:
                    handler_result["executed"] = True
                    handler_result["success"] = False
                    handler_result["error"] = str(handler_error)
                    logger.error(
                        f"Critical rollback handler failed: {handler.description}",
                        exc_info=True,
                    )
                    # Store first critical handler failure
                    if handler.critical and critical_handler_error is None:
                        critical_handler_error = handler_error

                self.audit_trail["compensation_handlers"].append(handler_result)

            # Calculate compensation stats
            total_handlers = len(self.rollback_handlers)
            executed_handlers = sum(1 for h in self.rollback_handlers if h.executed)
            successful_handlers = sum(
                1 for h in self.rollback_handlers if h.success is True
            )
            failed_handlers = sum(
                1 for h in self.rollback_handlers if h.success is False
            )

            self.audit_trail["compensation_stats"] = {
                "total": total_handlers,
                "executed": executed_handlers,
                "successful": successful_handlers,
                "failed": failed_handlers,
            }

            if failed_handlers > 0:
                self.audit_trail["compensation_status"] = "partial_failure"
                logger.warning(
                    f"Compensation completed with {failed_handlers} failures"
                )
            else:
                self.audit_trail["compensation_status"] = "success"
                logger.info("All compensation handlers succeeded")

            # Re-raise critical handler failure if one occurred
            if critical_handler_error:
                raise critical_handler_error

        else:
            self.audit_trail["compensation_needed"] = False
            logger.info("No compensation handlers registered")


# Pre-built rollback handlers for common operations


def create_files_api_rollback_handler(client, file_id: str) -> Callable[[], None]:
    """
    Create a rollback handler for OpenAI Files API upload.

    Args:
        client: OpenAI client instance
        file_id: File ID to delete

    Returns:
        Callable that deletes the file

    Example:
        handler_fn = create_files_api_rollback_handler(client, "file-abc")
        txn.register_rollback(
            handler_fn=handler_fn,
            resource_type=ResourceType.FILES_API,
            resource_id="file-abc",
            description="Delete uploaded file",
        )
    """

    def cleanup():
        logger.info(f"Deleting file from Files API: {file_id}")
        try:
            client.files.delete(file_id)
            logger.info(f"Successfully deleted file: {file_id}")
        except Exception as e:
            logger.error(f"Failed to delete file {file_id}: {e}", exc_info=True)
            raise

    return cleanup


def create_vector_store_rollback_handler(
    client, vector_store_id: str, file_id: str
) -> Callable[[], None]:
    """
    Create a rollback handler for Vector Store file upload.

    Args:
        client: OpenAI client instance
        vector_store_id: Vector store ID
        file_id: File ID within vector store

    Returns:
        Callable that removes the file from vector store

    Example:
        handler_fn = create_vector_store_rollback_handler(
            client, "vs_abc", "file_xyz"
        )
        txn.register_rollback(
            handler_fn=handler_fn,
            resource_type=ResourceType.VECTOR_STORE,
            resource_id=file_id,
            description="Remove file from vector store",
        )
    """

    def cleanup():
        logger.info(f"Removing file {file_id} from vector store {vector_store_id}")
        try:
            client.beta.vector_stores.files.delete(
                vector_store_id=vector_store_id, file_id=file_id
            )
            logger.info(f"Successfully removed file {file_id} from vector store")
        except Exception as e:
            logger.error(
                f"Failed to remove file {file_id} from vector store: {e}",
                exc_info=True,
            )
            raise

    return cleanup


# Backward compatibility: Keep original simple function


@contextmanager
def compensating_transaction(
    session: Session,
    compensate_fn: Optional[Callable] = None,
    audit_trail: Optional[Dict[str, Any]] = None,
):
    """
    Simple context manager providing compensation logic if commit fails.

    DEPRECATED: Use CompensatingTransaction class for new code.
    This function is kept for backward compatibility with existing code.

    Usage:
        def cleanup_openai_file(file_id):
            client.files.delete(file_id)

        audit = {}
        with compensating_transaction(session, cleanup_openai_file, audit):
            doc = Document(...)
            session.add(doc)
            # If commit succeeds → no compensation, audit shows success
            # If commit fails → compensation runs, audit captures all events

        print(audit)  # {'started_at': '...', 'status': 'success', ...}

    Args:
        session: SQLAlchemy session
        compensate_fn: Callable to run if commit fails (cleanup external resources)
        audit_trail: Optional dict to populate with transaction events

    Yields:
        session: The SQLAlchemy session for database operations

    Raises:
        Exception: Re-raises the original exception after rollback and compensation
    """
    if audit_trail is None:
        audit_trail = {}

    # Record transaction start
    audit_trail["started_at"] = datetime.now(timezone.utc).isoformat()

    try:
        yield session
        session.commit()

        # Record successful commit
        audit_trail["committed_at"] = datetime.now(timezone.utc).isoformat()
        audit_trail["status"] = "success"
        audit_trail["compensation_needed"] = False

        logger.info("Transaction committed successfully", extra=audit_trail)

    except Exception as e:
        session.rollback()

        # Record rollback
        audit_trail["rolled_back_at"] = datetime.now(timezone.utc).isoformat()
        audit_trail["status"] = "failed"
        audit_trail["error"] = str(e)
        audit_trail["error_type"] = type(e).__name__

        logger.error(
            f"Transaction failed, rolling back: {e}", exc_info=True, extra=audit_trail
        )

        # Run compensation (cleanup external resources)
        if compensate_fn:
            audit_trail["compensation_needed"] = True
            try:
                logger.info("Running compensation logic", extra=audit_trail)
                compensate_fn()

                # Record successful compensation
                audit_trail["compensation_completed_at"] = datetime.now(
                    timezone.utc
                ).isoformat()
                audit_trail["compensation_status"] = "success"

                logger.info("Compensation completed successfully", extra=audit_trail)

            except Exception as comp_err:
                # Record compensation failure
                audit_trail["compensation_status"] = "failed"
                audit_trail["compensation_error"] = str(comp_err)
                audit_trail["compensation_error_type"] = type(comp_err).__name__

                # Log but don't mask original error
                logger.error(
                    f"Compensation failed: {comp_err}", exc_info=True, extra=audit_trail
                )
        else:
            audit_trail["compensation_needed"] = False

        raise e  # Re-raise original exception
