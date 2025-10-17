"""
Unit tests for vector store functionality.

Tests VectorStoreManager class including:
- Vector store creation and retrieval
- Cache persistence and recovery
- File upload with retry logic
- Batch upload operations
- Status polling and timeout handling
- Error handling scenarios
- Metadata validation

Target: 90%+ code coverage
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
from dataclasses import dataclass

from src.vector_store import (
    VectorStoreManager,
    FileStatus,
    UploadResult,
    VECTOR_STORE_CACHE_FILE,
    BACKUP_CACHE_FILE,
)


@dataclass
class MockVectorStore:
    """Mock vector store object."""

    id: str
    name: str
    status: str = "completed"


@dataclass
class MockFile:
    """Mock OpenAI file object."""

    id: str
    filename: str
    purpose: str = "assistants"


@dataclass
class MockVectorStoreFile:
    """Mock vector store file object."""

    id: str
    status: str = "in_progress"


class TestVectorStoreManager:
    """Test VectorStoreManager class."""

    @pytest.fixture
    def mock_client(self):
        """Create mock OpenAI client."""
        client = Mock()
        client.beta.vector_stores.create.return_value = MockVectorStore(
            id="vs_test123", name="test_store"
        )
        client.beta.vector_stores.retrieve.return_value = MockVectorStore(
            id="vs_test123", name="test_store"
        )
        return client

    @pytest.fixture
    def manager(self, mock_client):
        """Create VectorStoreManager with mock client."""
        return VectorStoreManager(client=mock_client)

    @pytest.fixture
    def temp_pdf(self, tmp_path):
        """Create temporary PDF file for testing."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 test content")
        return pdf_file

    def test_manager_initialization(self, mock_client):
        """Test VectorStoreManager initialization."""
        manager = VectorStoreManager(client=mock_client)

        assert manager.client == mock_client
        assert manager.vector_store_id is None
        assert manager.config is not None

    def test_manager_initialization_without_client(self):
        """Test VectorStoreManager creates client if not provided."""
        with patch("src.vector_store.OpenAI") as mock_openai:
            manager = VectorStoreManager()
            assert manager.client is not None
            mock_openai.assert_called_once()

    def test_get_or_create_vector_store_creates_new(self, manager, tmp_path):
        """Test creating new vector store when no cache exists."""
        # Mock config to use tmp_path for cache
        cache_file = tmp_path / VECTOR_STORE_CACHE_FILE

        # Use object.__setattr__ to bypass frozen model
        object.__setattr__(manager.config, "vector_store_cache_file", cache_file)

        vector_store = manager.get_or_create_vector_store()

        # Verify vector store was created
        assert vector_store.id == "vs_test123"
        assert manager.vector_store_id == "vs_test123"

        # Verify cache was saved
        assert cache_file.exists()
        assert cache_file.read_text().strip() == "vs_test123"

    def test_get_or_create_vector_store_uses_cache(self, manager, tmp_path):
        """Test loading vector store from cache."""
        # Create cache file
        cache_file = tmp_path / VECTOR_STORE_CACHE_FILE
        cache_file.write_text("vs_cached456")

        # Use object.__setattr__ to bypass frozen model
        object.__setattr__(manager.config, "vector_store_cache_file", cache_file)

        vector_store = manager.get_or_create_vector_store()

        # Should retrieve cached vector store
        assert vector_store.id == "vs_test123"  # From mock retrieve
        manager.client.beta.vector_stores.retrieve.assert_called_once_with(
            "vs_cached456"
        )

    def test_get_or_create_vector_store_recreates_on_stale_cache(
        self, manager, tmp_path
    ):
        """Test recreating vector store when cached ID is invalid."""
        # Create cache with invalid ID
        cache_file = tmp_path / VECTOR_STORE_CACHE_FILE
        cache_file.write_text("vs_invalid999")

        # Mock retrieve to fail (stale cache)
        manager.client.beta.vector_stores.retrieve.side_effect = Exception("Not found")

        # Use object.__setattr__ to bypass frozen model
        object.__setattr__(manager.config, "vector_store_cache_file", cache_file)

        vector_store = manager.get_or_create_vector_store()

        # Should create new vector store
        assert vector_store.id == "vs_test123"
        manager.client.beta.vector_stores.create.assert_called_once()

    def test_save_cache_creates_backup(self, manager, tmp_path):
        """Test cache save creates backup of existing cache."""
        cache_file = tmp_path / VECTOR_STORE_CACHE_FILE
        # Backup uses the constant BACKUP_CACHE_FILE in current directory
        backup_file = Path(BACKUP_CACHE_FILE)

        # Create existing cache
        cache_file.write_text("vs_old123")

        # Use object.__setattr__ to bypass frozen model
        object.__setattr__(manager.config, "vector_store_cache_file", cache_file)

        try:
            # Save new cache
            manager._save_cache("vs_new456")

            # Verify new cache
            assert cache_file.read_text() == "vs_new456"

            # Verify backup exists with old content
            assert backup_file.exists()
            assert backup_file.read_text() == "vs_old123"
        finally:
            # Cleanup backup file
            if backup_file.exists():
                backup_file.unlink()

    def test_add_file_to_vector_store_success(self, manager, temp_pdf):
        """Test successful file upload to vector store."""
        # Setup mocks
        manager.vector_store_id = "vs_test123"

        mock_file = MockFile(id="file_abc123", filename="test.pdf")
        manager.client.files.create.return_value = mock_file

        mock_vs_file = MockVectorStoreFile(id="vsf_def456", status="completed")
        manager.client.beta.vector_stores.files.create.return_value = mock_vs_file

        # Mock status polling to return completed immediately
        manager.client.beta.vector_stores.files.retrieve.return_value = (
            MockVectorStoreFile(id="vsf_def456", status="completed")
        )

        # Upload file
        result = manager.add_file_to_vector_store(temp_pdf, wait_for_completion=False)

        # Verify result
        assert result.success is True
        assert result.file_id == "file_abc123"
        assert result.vector_store_file_id == "vsf_def456"
        assert result.status == FileStatus.COMPLETED
        assert result.bytes_processed > 0

    def test_add_file_to_vector_store_file_not_found(self, manager):
        """Test upload fails when file doesn't exist."""
        manager.vector_store_id = "vs_test123"

        fake_path = Path("/nonexistent/file.pdf")

        with pytest.raises(FileNotFoundError):
            manager.add_file_to_vector_store(fake_path)

    def test_add_file_to_vector_store_metadata_limit(self, manager, temp_pdf):
        """Test upload fails when metadata exceeds 16 attributes."""
        manager.vector_store_id = "vs_test123"

        # Create metadata with 17 attributes (exceeds limit)
        metadata = {f"key_{i}": f"value_{i}" for i in range(17)}

        with pytest.raises(ValueError, match="max 16 allowed"):
            manager.add_file_to_vector_store(temp_pdf, metadata=metadata)

    def test_add_file_to_vector_store_creates_vector_store_if_needed(
        self, manager, temp_pdf, tmp_path
    ):
        """Test upload creates vector store if not exists."""
        # Vector store ID not set
        assert manager.vector_store_id is None

        cache_file = tmp_path / VECTOR_STORE_CACHE_FILE

        # Use object.__setattr__ to bypass frozen model
        object.__setattr__(manager.config, "vector_store_cache_file", cache_file)

        mock_file = MockFile(id="file_abc123", filename="test.pdf")
        manager.client.files.create.return_value = mock_file

        mock_vs_file = MockVectorStoreFile(id="vsf_def456", status="completed")
        manager.client.beta.vector_stores.files.create.return_value = mock_vs_file

        # Mock status return
        manager.client.beta.vector_stores.files.retrieve.return_value = (
            MockVectorStoreFile(id="vsf_def456", status="completed")
        )

        _ = manager.add_file_to_vector_store(temp_pdf, wait_for_completion=False)

        # Verify vector store was created
        assert manager.vector_store_id is not None
        manager.client.beta.vector_stores.create.assert_called_once()

    def test_add_file_to_vector_store_handles_upload_failure(self, manager, temp_pdf):
        """Test upload handles file creation failure gracefully."""
        manager.vector_store_id = "vs_test123"

        # Mock file upload to fail
        manager.client.files.create.side_effect = Exception("Upload failed")

        result = manager.add_file_to_vector_store(temp_pdf, wait_for_completion=False)

        # Verify result indicates failure
        assert result.success is False
        assert result.status == FileStatus.FAILED
        assert result.error == "Upload failed"
        assert result.file_id is None
        assert result.vector_store_file_id is None

    def test_add_file_to_vector_store_handles_vector_store_add_failure(
        self, manager, temp_pdf
    ):
        """Test upload handles vector store add failure gracefully."""
        manager.vector_store_id = "vs_test123"

        mock_file = MockFile(id="file_abc123", filename="test.pdf")
        manager.client.files.create.return_value = mock_file

        # Mock vector store file creation to fail
        manager.client.beta.vector_stores.files.create.side_effect = Exception(
            "Vector store add failed"
        )

        result = manager.add_file_to_vector_store(temp_pdf, wait_for_completion=False)

        # Verify result indicates failure
        assert result.success is False
        assert result.status == FileStatus.FAILED
        assert "Vector store add failed" in result.error

    def test_wait_for_file_processing_completes(self, manager):
        """Test waiting for file processing to complete."""
        manager.vector_store_id = "vs_test123"

        # Mock status progression: in_progress -> completed
        manager.client.beta.vector_stores.files.retrieve.side_effect = [
            MockVectorStoreFile(id="vsf_test", status="in_progress"),
            MockVectorStoreFile(id="vsf_test", status="in_progress"),
            MockVectorStoreFile(id="vsf_test", status="completed"),
        ]

        status = manager._wait_for_file_processing("vsf_test", timeout_seconds=60)

        assert status == FileStatus.COMPLETED
        assert manager.client.beta.vector_stores.files.retrieve.call_count == 3

    def test_wait_for_file_processing_timeout(self, manager):
        """Test timeout when file processing takes too long."""
        manager.vector_store_id = "vs_test123"

        # Mock status to always return in_progress
        manager.client.beta.vector_stores.files.retrieve.return_value = (
            MockVectorStoreFile(id="vsf_test", status="in_progress")
        )

        with pytest.raises(TimeoutError, match="File processing timeout"):
            manager._wait_for_file_processing("vsf_test", timeout_seconds=1)

    def test_wait_for_file_processing_failed(self, manager):
        """Test handling of failed file processing."""
        manager.vector_store_id = "vs_test123"

        # Mock status to return failed
        manager.client.beta.vector_stores.files.retrieve.return_value = (
            MockVectorStoreFile(id="vsf_test", status="failed")
        )

        status = manager._wait_for_file_processing("vsf_test", timeout_seconds=60)

        assert status == FileStatus.FAILED

    def test_batch_upload_files_success(self, manager, tmp_path):
        """Test batch upload of multiple files."""
        # Create test files
        files = [
            tmp_path / "test1.pdf",
            tmp_path / "test2.pdf",
            tmp_path / "test3.pdf",
        ]
        for f in files:
            f.write_bytes(b"%PDF-1.4 content")

        manager.vector_store_id = "vs_test123"

        # Mock file uploads
        call_count = [0]

        def mock_upload(file_path, metadata, wait_for_completion):
            call_count[0] += 1
            return UploadResult(
                file_id=f"file_{call_count[0]}",
                vector_store_file_id=f"vsf_{call_count[0]}",
                status=FileStatus.COMPLETED,
                bytes_processed=file_path.stat().st_size,
                processing_time_seconds=0.1,
            )

        manager.add_file_to_vector_store = mock_upload

        results = manager.batch_upload_files(files, max_concurrent=2)

        # Verify results
        assert len(results) == 3
        assert all(r.success for r in results)
        assert call_count[0] == 3

    def test_batch_upload_files_with_metadata_generator(self, manager, tmp_path):
        """Test batch upload with metadata generation."""
        files = [tmp_path / "test1.pdf", tmp_path / "test2.pdf"]
        for f in files:
            f.write_bytes(b"%PDF-1.4 content")

        manager.vector_store_id = "vs_test123"

        metadata_calls = []

        def metadata_generator(path: Path):
            metadata = {"filename": path.name}
            metadata_calls.append(metadata)
            return metadata

        def mock_upload(file_path, metadata, wait_for_completion):
            return UploadResult(
                file_id="file_test",
                vector_store_file_id="vsf_test",
                status=FileStatus.COMPLETED,
                bytes_processed=100,
            )

        manager.add_file_to_vector_store = mock_upload

        _ = manager.batch_upload_files(
            files, metadata_generator=metadata_generator, max_concurrent=1
        )

        # Verify metadata was generated for each file
        assert len(metadata_calls) == 2
        assert metadata_calls[0]["filename"] == "test1.pdf"
        assert metadata_calls[1]["filename"] == "test2.pdf"

    def test_batch_upload_handles_partial_failures(self, manager, tmp_path):
        """Test batch upload handles some files failing."""
        files = [tmp_path / "test1.pdf", tmp_path / "test2.pdf"]
        for f in files:
            f.write_bytes(b"%PDF-1.4 content")

        manager.vector_store_id = "vs_test123"

        call_count = [0]

        def mock_upload(file_path, metadata, wait_for_completion):
            call_count[0] += 1
            if call_count[0] == 1:
                # First file succeeds
                return UploadResult(
                    file_id="file_1",
                    vector_store_file_id="vsf_1",
                    status=FileStatus.COMPLETED,
                )
            else:
                # Second file fails
                raise Exception("Upload failed")

        manager.add_file_to_vector_store = mock_upload

        results = manager.batch_upload_files(files, max_concurrent=1)

        # Verify results
        assert len(results) == 2
        assert results[0].success is True
        assert results[1].success is False
        assert "Upload failed" in results[1].error

    def test_cleanup_orphaned_files(self, manager):
        """Test cleanup of orphaned files in vector store."""
        manager.vector_store_id = "vs_test123"

        # Mock file listing
        mock_file_list = Mock()
        mock_file_list.data = [
            Mock(id="file_1"),
            Mock(id="file_2"),
            Mock(id="file_3"),
        ]
        manager.client.beta.vector_stores.files.list.return_value = mock_file_list

        deleted_count = manager.cleanup_orphaned_files(keep_recent_days=7)

        # Currently returns 0 (placeholder implementation)
        assert deleted_count == 0
        manager.client.beta.vector_stores.files.list.assert_called_once()

    def test_rebuild_vector_store(self, manager, tmp_path):
        """Test rebuilding vector store from scratch."""
        cache_file = tmp_path / VECTOR_STORE_CACHE_FILE
        cache_file.write_text("vs_old123")

        # Use object.__setattr__ to bypass frozen model
        object.__setattr__(manager.config, "vector_store_cache_file", cache_file)

        vector_store = manager.rebuild_vector_store()

        # rebuild_vector_store deletes the cache, then get_or_create_vector_store creates a new one
        # So the cache file should exist again with the new ID
        assert cache_file.exists()
        assert cache_file.read_text() == "vs_test123"

        # Verify new vector store was created
        assert vector_store.id == "vs_test123"
        manager.client.beta.vector_stores.create.assert_called_once()


class TestFileStatus:
    """Test FileStatus enum."""

    def test_file_status_values(self):
        """Test FileStatus enum values."""
        assert FileStatus.IN_PROGRESS == "in_progress"
        assert FileStatus.COMPLETED == "completed"
        assert FileStatus.FAILED == "failed"
        assert FileStatus.CANCELLED == "cancelled"

    def test_file_status_from_string(self):
        """Test creating FileStatus from string."""
        status = FileStatus("completed")
        assert status == FileStatus.COMPLETED


class TestUploadResult:
    """Test UploadResult dataclass."""

    def test_upload_result_success_property(self):
        """Test success property of UploadResult."""
        # Successful result
        result = UploadResult(
            file_id="file_123",
            vector_store_file_id="vsf_456",
            status=FileStatus.COMPLETED,
        )
        assert result.success is True

        # Failed result
        result = UploadResult(
            file_id=None, vector_store_file_id=None, status=FileStatus.FAILED
        )
        assert result.success is False

    def test_upload_result_with_error(self):
        """Test UploadResult with error message."""
        result = UploadResult(
            file_id=None,
            vector_store_file_id=None,
            status=FileStatus.FAILED,
            error="Connection timeout",
        )

        assert result.success is False
        assert result.error == "Connection timeout"

    def test_upload_result_with_metrics(self):
        """Test UploadResult with processing metrics."""
        result = UploadResult(
            file_id="file_123",
            vector_store_file_id="vsf_456",
            status=FileStatus.COMPLETED,
            bytes_processed=1024000,
            processing_time_seconds=3.5,
        )

        assert result.bytes_processed == 1024000
        assert result.processing_time_seconds == 3.5
