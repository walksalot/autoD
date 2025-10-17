"""
Unit tests for cleanup_handlers module.

Tests cleanup functions for compensating transactions,
ensuring proper resource cleanup when database commits fail.
"""

import pytest
from unittest.mock import Mock
from openai import APIError

from src.cleanup_handlers import (
    cleanup_files_api_upload,
    cleanup_vector_store_upload,
    cleanup_multiple_resources,
)


class TestCleanupFilesApiUpload:
    """Test suite for cleanup_files_api_upload function."""

    def test_successful_file_deletion(self):
        """Should delete file from Files API."""
        mock_client = Mock()
        file_id = "file-abc123"

        cleanup_files_api_upload(mock_client, file_id)

        # Verify deletion was called
        mock_client.files.delete.assert_called_once_with(file_id)

    def test_deletion_failure_raises_exception(self):
        """Should re-raise exception if deletion fails."""
        mock_client = Mock()
        mock_client.files.delete.side_effect = APIError("Deletion failed")
        file_id = "file-abc123"

        with pytest.raises(APIError):
            cleanup_files_api_upload(mock_client, file_id)

        # Verify deletion was attempted
        mock_client.files.delete.assert_called_once_with(file_id)

    def test_logs_cleanup_attempt(self, caplog):
        """Should log cleanup attempt."""
        mock_client = Mock()
        file_id = "file-test123"

        with caplog.at_level("INFO"):
            cleanup_files_api_upload(mock_client, file_id)

        # Verify logging
        assert "Attempting to cleanup Files API upload" in caplog.text
        assert file_id in caplog.text

    def test_logs_successful_cleanup(self, caplog):
        """Should log successful cleanup."""
        mock_client = Mock()
        file_id = "file-test123"

        with caplog.at_level("INFO"):
            cleanup_files_api_upload(mock_client, file_id)

        assert "Successfully cleaned up Files API upload" in caplog.text
        assert file_id in caplog.text

    def test_logs_cleanup_failure(self, caplog):
        """Should log cleanup failure before re-raising."""
        mock_client = Mock()
        mock_client.files.delete.side_effect = Exception("Network error")
        file_id = "file-fail123"

        with caplog.at_level("ERROR"):
            with pytest.raises(Exception):
                cleanup_files_api_upload(mock_client, file_id)

        assert "Failed to cleanup Files API upload" in caplog.text
        assert file_id in caplog.text


class TestCleanupVectorStoreUpload:
    """Test suite for cleanup_vector_store_upload function."""

    def test_successful_vector_store_removal(self):
        """Should remove file from vector store."""
        mock_client = Mock()
        vector_store_id = "vs_abc123"
        file_id = "file-xyz789"

        cleanup_vector_store_upload(mock_client, vector_store_id, file_id)

        # Verify removal was called
        mock_client.beta.vector_stores.files.delete.assert_called_once_with(
            vector_store_id=vector_store_id, file_id=file_id
        )

    def test_removal_failure_raises_exception(self):
        """Should re-raise exception if removal fails."""
        mock_client = Mock()
        mock_client.beta.vector_stores.files.delete.side_effect = APIError(
            "Removal failed"
        )
        vector_store_id = "vs_abc123"
        file_id = "file-xyz789"

        with pytest.raises(APIError):
            cleanup_vector_store_upload(mock_client, vector_store_id, file_id)

        # Verify removal was attempted
        mock_client.beta.vector_stores.files.delete.assert_called_once()

    def test_logs_cleanup_attempt(self, caplog):
        """Should log cleanup attempt with both IDs."""
        mock_client = Mock()
        vector_store_id = "vs_test123"
        file_id = "file_test456"

        with caplog.at_level("INFO"):
            cleanup_vector_store_upload(mock_client, vector_store_id, file_id)

        assert "Attempting to cleanup vector store upload" in caplog.text
        assert vector_store_id in caplog.text
        assert file_id in caplog.text

    def test_logs_successful_cleanup(self, caplog):
        """Should log successful cleanup."""
        mock_client = Mock()
        vector_store_id = "vs_test123"
        file_id = "file_test456"

        with caplog.at_level("INFO"):
            cleanup_vector_store_upload(mock_client, vector_store_id, file_id)

        assert "Successfully cleaned up vector store upload" in caplog.text

    def test_logs_cleanup_failure(self, caplog):
        """Should log cleanup failure before re-raising."""
        mock_client = Mock()
        mock_client.beta.vector_stores.files.delete.side_effect = Exception(
            "Network error"
        )
        vector_store_id = "vs_fail123"
        file_id = "file_fail456"

        with caplog.at_level("ERROR"):
            with pytest.raises(Exception):
                cleanup_vector_store_upload(mock_client, vector_store_id, file_id)

        assert "Failed to cleanup vector store upload" in caplog.text


class TestCleanupMultipleResources:
    """Test suite for cleanup_multiple_resources function."""

    def test_executes_cleanups_in_lifo_order(self):
        """Should execute cleanup functions in reverse (LIFO) order."""
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

        # Should execute in reverse order: C → B → A
        assert execution_order == ["C", "B", "A"]

    def test_continues_after_cleanup_failure(self):
        """Should continue executing remaining cleanups if one fails."""
        execution_order = []

        def cleanup_success_1():
            execution_order.append("success_1")

        def cleanup_fail():
            execution_order.append("fail")
            raise Exception("Cleanup failed")

        def cleanup_success_2():
            execution_order.append("success_2")

        cleanup_multiple_resources(
            [
                ("step_1", cleanup_success_1),
                ("step_fail", cleanup_fail),
                ("step_2", cleanup_success_2),
            ]
        )

        # All cleanups should execute despite failure
        assert "success_1" in execution_order
        assert "fail" in execution_order
        assert "success_2" in execution_order

    def test_logs_each_cleanup_step(self, caplog):
        """Should log each cleanup step execution."""

        def cleanup1():
            pass

        def cleanup2():
            pass

        with caplog.at_level("INFO"):
            cleanup_multiple_resources(
                [
                    ("file_upload", cleanup1),
                    ("vector_store", cleanup2),
                ]
            )

        assert "Running cleanup step" in caplog.text
        assert "file_upload" in caplog.text
        assert "vector_store" in caplog.text

    def test_logs_cleanup_failures(self, caplog):
        """Should log cleanup failures."""

        def failing_cleanup():
            raise Exception("Simulated failure")

        with caplog.at_level("ERROR"):
            cleanup_multiple_resources([("failing_step", failing_cleanup)])

        assert "Cleanup step failed" in caplog.text
        assert "failing_step" in caplog.text

    def test_empty_cleanup_list(self):
        """Should handle empty cleanup list gracefully."""
        # Should not raise exception
        cleanup_multiple_resources([])

    def test_single_cleanup(self):
        """Should handle single cleanup function."""
        executed = []

        def cleanup():
            executed.append(True)

        cleanup_multiple_resources([("single", cleanup)])

        assert len(executed) == 1

    def test_cleanup_with_multiple_failures(self):
        """Should execute all cleanups even if multiple fail."""
        execution_count = []

        def cleanup_fail_1():
            execution_count.append(1)
            raise Exception("Fail 1")

        def cleanup_fail_2():
            execution_count.append(2)
            raise Exception("Fail 2")

        def cleanup_success():
            execution_count.append(3)

        cleanup_multiple_resources(
            [
                ("fail1", cleanup_fail_1),
                ("fail2", cleanup_fail_2),
                ("success", cleanup_success),
            ]
        )

        # All 3 should execute
        assert len(execution_count) == 3


class TestIntegrationScenarios:
    """Integration test scenarios combining multiple cleanup operations."""

    def test_full_cleanup_sequence(self):
        """Test complete cleanup sequence for failed transaction."""
        mock_client = Mock()
        vector_store_id = "vs_integration"
        file_id = "file_integration"

        # Execute cleanup sequence
        cleanup_multiple_resources(
            [
                ("files_api", lambda: cleanup_files_api_upload(mock_client, file_id)),
                (
                    "vector_store",
                    lambda: cleanup_vector_store_upload(
                        mock_client, vector_store_id, file_id
                    ),
                ),
            ]
        )

        # Verify both cleanups executed in LIFO order
        assert mock_client.beta.vector_stores.files.delete.called
        assert mock_client.files.delete.called

    def test_partial_cleanup_failure(self):
        """Test scenario where file cleanup succeeds but vector store fails."""
        mock_client = Mock()
        mock_client.beta.vector_stores.files.delete.side_effect = Exception(
            "Vector store error"
        )

        file_id = "file_partial"
        vector_store_id = "vs_partial"

        # Should not raise - cleanup_multiple_resources continues on failure
        cleanup_multiple_resources(
            [
                ("files_api", lambda: cleanup_files_api_upload(mock_client, file_id)),
                (
                    "vector_store",
                    lambda: cleanup_vector_store_upload(
                        mock_client, vector_store_id, file_id
                    ),
                ),
            ]
        )

        # Both should have been attempted
        assert mock_client.beta.vector_stores.files.delete.called
        assert mock_client.files.delete.called
