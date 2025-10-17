"""
Compensating transaction pattern for external API calls.

Prevents orphaned records when DB commits but external API operations fail.
Provides cleanup logic for external resources like OpenAI Files API uploads.
"""

from contextlib import contextmanager
import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from typing import Optional, Callable, Dict, Any

logger = logging.getLogger(__name__)


@contextmanager
def compensating_transaction(
    session: Session,
    compensate_fn: Optional[Callable] = None,
    audit_trail: Optional[Dict[str, Any]] = None,
):
    """
    Context manager providing compensation logic with audit trail if commit fails.

    Usage:
        audit = {}
        def cleanup_openai_file(file_id):
            client.files.delete(file_id)

        with compensating_transaction(session, cleanup_openai_file, audit):
            doc = Document(...)
            session.add(doc)
            # If commit succeeds → no compensation, audit shows success
            # If commit fails → compensation runs, audit captures all events

        print(audit)  # {'started_at': '...', 'status': 'success', ...}

    Args:
        session: SQLAlchemy session
        compensate_fn: Callable to run if commit fails (cleanup external resources)
        audit_trail: Optional dict to populate with transaction events for debugging

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
