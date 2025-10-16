"""
Compensating transaction pattern for external API calls.

Prevents orphaned records when DB commits but external API operations fail.
Provides cleanup logic for external resources like OpenAI Files API uploads.
"""

from contextlib import contextmanager
import logging
from sqlalchemy.orm import Session
from typing import Optional, Callable

logger = logging.getLogger(__name__)


@contextmanager
def compensating_transaction(session: Session, compensate_fn: Optional[Callable] = None):
    """
    Context manager providing compensation logic if commit fails.

    Usage:
        def cleanup_openai_file(file_id):
            client.files.delete(file_id)

        with compensating_transaction(session, lambda: cleanup_openai_file(file_id)):
            doc = Document(...)
            session.add(doc)
            # If commit succeeds → no compensation
            # If commit fails → compensation runs, then re-raises

    Args:
        session: SQLAlchemy session
        compensate_fn: Callable to run if commit fails (cleanup external resources)

    Yields:
        session: The SQLAlchemy session for database operations

    Raises:
        Exception: Re-raises the original exception after rollback and compensation
    """
    try:
        yield session
        session.commit()
        logger.info("Transaction committed successfully")
    except Exception as e:
        session.rollback()
        logger.error(f"Transaction failed, rolling back: {e}", exc_info=True)

        # Run compensation (cleanup external resources)
        if compensate_fn:
            try:
                logger.info("Running compensation logic")
                compensate_fn()
                logger.info("Compensation completed successfully")
            except Exception as comp_err:
                # Log but don't mask original error
                logger.error(f"Compensation failed: {comp_err}", exc_info=True)

        raise e  # Re-raise original exception
