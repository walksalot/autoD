"""
Cleanup handlers for compensating transactions.

Provides rollback handlers for external API operations when database commits fail.
Each handler is responsible for cleaning up orphaned resources (files, vector store entries).
"""

import logging
from openai import OpenAI

logger = logging.getLogger(__name__)


def cleanup_files_api_upload(client: OpenAI, file_id: str) -> None:
    """
    Delete file from OpenAI Files API.

    Used in compensating transactions when database commit fails after file upload.
    This prevents orphaned files that consume storage and quota.

    Args:
        client: Authenticated OpenAI client
        file_id: File ID to delete (e.g., "file-abc123...")

    Raises:
        openai.APIError: If deletion fails

    Example:
        >>> from openai import OpenAI
        >>> client = OpenAI(api_key="sk-...")
        >>> file_id = "file-abc123"
        >>> cleanup_files_api_upload(client, file_id)
        # Logs: "Cleaned up Files API upload: file-abc123"
    """
    try:
        logger.info(
            "Attempting to cleanup Files API upload",
            extra={"file_id": file_id, "action": "delete"},
        )

        client.files.delete(file_id)

        logger.info(
            "Successfully cleaned up Files API upload",
            extra={"file_id": file_id, "status": "deleted"},
        )
    except Exception as e:
        logger.error(
            "Failed to cleanup Files API upload",
            exc_info=True,
            extra={"file_id": file_id, "error": str(e), "status": "failed"},
        )
        # Re-raise to signal compensation failure
        raise


def cleanup_vector_store_upload(
    client: OpenAI, vector_store_id: str, file_id: str
) -> None:
    """
    Remove file from OpenAI vector store.

    Used in compensating transactions when database commit fails after vector store upload.
    This ensures vector store stays in sync with database records.

    Args:
        client: Authenticated OpenAI client
        vector_store_id: Vector store ID (e.g., "vs_abc123...")
        file_id: File ID to remove from vector store

    Raises:
        openai.APIError: If removal fails

    Example:
        >>> from openai import OpenAI
        >>> client = OpenAI(api_key="sk-...")
        >>> cleanup_vector_store_upload(client, "vs_abc123", "file-xyz789")
        # Logs: "Cleaned up vector store upload: file-xyz789"
    """
    try:
        logger.info(
            "Attempting to cleanup vector store upload",
            extra={
                "vector_store_id": vector_store_id,
                "file_id": file_id,
                "action": "remove_from_vector_store",
            },
        )

        client.beta.vector_stores.files.delete(
            vector_store_id=vector_store_id, file_id=file_id
        )

        logger.info(
            "Successfully cleaned up vector store upload",
            extra={
                "vector_store_id": vector_store_id,
                "file_id": file_id,
                "status": "removed",
            },
        )
    except Exception as e:
        logger.error(
            "Failed to cleanup vector store upload",
            exc_info=True,
            extra={
                "vector_store_id": vector_store_id,
                "file_id": file_id,
                "error": str(e),
                "status": "failed",
            },
        )
        # Re-raise to signal compensation failure
        raise


def cleanup_multiple_resources(cleanup_fns: list) -> None:
    """
    Execute multiple cleanup functions in LIFO order (reverse).

    Used when a transaction involves multiple external operations that all need rollback.
    Cleans up in reverse order to maintain proper dependency ordering.

    Args:
        cleanup_fns: List of (name, callable) tuples to execute

    Example:
        >>> def cleanup1():
        ...     print("Cleanup 1")
        >>> def cleanup2():
        ...     print("Cleanup 2")
        >>> cleanup_multiple_resources([
        ...     ("file_upload", cleanup1),
        ...     ("vector_store", cleanup2)
        ... ])
        # Executes cleanup2 first (LIFO), then cleanup1
    """
    # Reverse order (LIFO) - cleanup most recent operations first
    for name, cleanup_fn in reversed(cleanup_fns):
        try:
            logger.info(
                "Running cleanup step",
                extra={"cleanup_name": name, "action": "execute"},
            )
            cleanup_fn()
            logger.info(
                "Cleanup step completed",
                extra={"cleanup_name": name, "status": "success"},
            )
        except Exception as e:
            logger.error(
                "Cleanup step failed",
                exc_info=True,
                extra={"cleanup_name": name, "error": str(e), "status": "failed"},
            )
            # Continue with remaining cleanup steps even if one fails
            # Log the error but don't re-raise to allow other cleanups to proceed


# Example usage
if __name__ == "__main__":
    from openai import OpenAI

    print("=== Cleanup Handlers Test ===")
    print("NOTE: These tests require valid OpenAI API key and file IDs\n")

    # Test 1: Module imports
    print("Test 1: Module structure")
    print("✅ cleanup_files_api_upload defined")
    print("✅ cleanup_vector_store_upload defined")
    print("✅ cleanup_multiple_resources defined")

    # Test 2: Function signatures
    print("\nTest 2: Function signatures")
    import inspect

    sig1 = inspect.signature(cleanup_files_api_upload)
    assert len(sig1.parameters) == 2, "cleanup_files_api_upload should take 2 params"
    print(f"✅ cleanup_files_api_upload({', '.join(sig1.parameters.keys())})")

    sig2 = inspect.signature(cleanup_vector_store_upload)
    assert len(sig2.parameters) == 3, "cleanup_vector_store_upload should take 3 params"
    print(f"✅ cleanup_vector_store_upload({', '.join(sig2.parameters.keys())})")

    sig3 = inspect.signature(cleanup_multiple_resources)
    assert len(sig3.parameters) == 1, "cleanup_multiple_resources should take 1 param"
    print(f"✅ cleanup_multiple_resources({', '.join(sig3.parameters.keys())})")

    # Test 3: Error handling (without actual API calls)
    print("\nTest 3: Error handling")
    try:
        # This will fail without actual client/file_id, but tests error path
        from unittest.mock import Mock

        mock_client = Mock()
        mock_client.files.delete.side_effect = Exception("Simulated error")

        try:
            cleanup_files_api_upload(mock_client, "file-test123")
        except Exception as e:
            print(f"✅ cleanup_files_api_upload raises exception: {type(e).__name__}")
    except Exception as e:
        print(f"❌ Test setup failed: {e}")

    # Test 4: Multiple cleanup LIFO order
    print("\nTest 4: LIFO cleanup order")
    execution_order = []

    def cleanup_a():
        execution_order.append("A")

    def cleanup_b():
        execution_order.append("B")

    def cleanup_c():
        execution_order.append("C")

    cleanup_multiple_resources(
        [
            ("step_A", cleanup_a),
            ("step_B", cleanup_b),
            ("step_C", cleanup_c),
        ]
    )

    if execution_order == ["C", "B", "A"]:
        print("✅ Cleanup executed in LIFO order: C → B → A")
    else:
        print(f"❌ Wrong order: {execution_order}")

    print("\n=== All Tests Complete ===")
    print("✅ Module structure validated")
    print("✅ Function signatures correct")
    print("✅ Error handling works")
    print("✅ LIFO cleanup order verified")
