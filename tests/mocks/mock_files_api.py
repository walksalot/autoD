"""Mock implementation of OpenAI Files API for testing.

This module provides a mock of the OpenAI Files API that:
- Simulates file.create() (upload)
- Simulates file.retrieve() (get metadata)
- Simulates file.delete()
- Tracks uploaded files in memory for assertions

Example usage:
    from tests.mocks.mock_files_api import MockFilesClient

    client = MockFilesClient()
    file_obj = client.files.create(file=pdf_path, purpose="assistants")
    assert file_obj.id.startswith("file-")
    assert file_obj.filename == "test.pdf"
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from pathlib import Path
import uuid


@dataclass
class FileObject:
    """Simulates OpenAI File object returned by Files API."""
    id: str
    bytes: int
    created_at: int
    filename: str
    purpose: str
    status: str = "processed"
    status_details: Optional[str] = None


class MockFilesNamespace:
    """Simulates client.files namespace."""

    def __init__(self):
        """Initialize mock files namespace.

        Maintains an in-memory registry of uploaded files for testing.
        """
        self._files: Dict[str, FileObject] = {}
        self.upload_count = 0
        self.delete_count = 0

    def create(
        self,
        file: Any,
        purpose: str = "assistants",
        **kwargs
    ) -> FileObject:
        """Simulate file upload to OpenAI Files API.

        Args:
            file: File path or file-like object
            purpose: Purpose for the file (e.g., "assistants")
            **kwargs: Additional parameters (ignored)

        Returns:
            FileObject with generated ID

        Example:
            >>> files = MockFilesNamespace()
            >>> file_obj = files.create(file=Path("test.pdf"), purpose="assistants")
            >>> assert file_obj.id.startswith("file-")
            >>> assert file_obj.purpose == "assistants"
        """
        self.upload_count += 1

        # Generate unique file ID
        file_id = f"file-{uuid.uuid4().hex[:24]}"

        # Extract filename and size
        if isinstance(file, (str, Path)):
            path = Path(file)
            filename = path.name
            try:
                file_size = path.stat().st_size
            except Exception:
                file_size = 1024  # Default size if file doesn't exist
        else:
            # File-like object
            filename = getattr(file, "name", "unknown.pdf")
            try:
                file.seek(0, 2)  # Seek to end
                file_size = file.tell()
                file.seek(0)  # Reset to beginning
            except Exception:
                file_size = 1024

        # Create file object
        file_obj = FileObject(
            id=file_id,
            bytes=file_size,
            created_at=1234567890,
            filename=filename,
            purpose=purpose,
            status="processed"
        )

        # Store in registry
        self._files[file_id] = file_obj

        return file_obj

    def retrieve(self, file_id: str) -> FileObject:
        """Retrieve file metadata by ID.

        Args:
            file_id: OpenAI file ID

        Returns:
            FileObject with file metadata

        Raises:
            KeyError: If file ID not found

        Example:
            >>> files = MockFilesNamespace()
            >>> uploaded = files.create(file=Path("test.pdf"))
            >>> retrieved = files.retrieve(uploaded.id)
            >>> assert retrieved.id == uploaded.id
        """
        if file_id not in self._files:
            raise KeyError(f"File not found: {file_id}")

        return self._files[file_id]

    def delete(self, file_id: str) -> Dict[str, Any]:
        """Delete a file by ID.

        Args:
            file_id: OpenAI file ID

        Returns:
            Dictionary with deletion confirmation

        Raises:
            KeyError: If file ID not found

        Example:
            >>> files = MockFilesNamespace()
            >>> uploaded = files.create(file=Path("test.pdf"))
            >>> result = files.delete(uploaded.id)
            >>> assert result["deleted"] == True
        """
        if file_id not in self._files:
            raise KeyError(f"File not found: {file_id}")

        self.delete_count += 1
        del self._files[file_id]

        return {
            "id": file_id,
            "object": "file",
            "deleted": True
        }

    def list(self, purpose: Optional[str] = None) -> Dict[str, Any]:
        """List all uploaded files.

        Args:
            purpose: Optional filter by purpose

        Returns:
            Dictionary with list of files

        Example:
            >>> files = MockFilesNamespace()
            >>> files.create(file=Path("test1.pdf"))
            >>> files.create(file=Path("test2.pdf"))
            >>> result = files.list()
            >>> assert len(result["data"]) == 2
        """
        file_list = list(self._files.values())

        if purpose:
            file_list = [f for f in file_list if f.purpose == purpose]

        return {
            "object": "list",
            "data": [
                {
                    "id": f.id,
                    "bytes": f.bytes,
                    "created_at": f.created_at,
                    "filename": f.filename,
                    "purpose": f.purpose,
                    "status": f.status
                }
                for f in file_list
            ]
        }

    def get_uploaded_files(self) -> List[FileObject]:
        """Get all uploaded files (test helper).

        Returns:
            List of FileObject instances

        Example:
            >>> files = MockFilesNamespace()
            >>> files.create(file=Path("test.pdf"))
            >>> uploaded = files.get_uploaded_files()
            >>> assert len(uploaded) == 1
        """
        return list(self._files.values())

    def clear(self) -> None:
        """Clear all uploaded files (test helper).

        Useful for resetting state between tests.

        Example:
            >>> files = MockFilesNamespace()
            >>> files.create(file=Path("test.pdf"))
            >>> files.clear()
            >>> assert len(files.get_uploaded_files()) == 0
        """
        self._files.clear()
        self.upload_count = 0
        self.delete_count = 0


class MockFilesClient:
    """Complete mock of OpenAI client with Files API.

    Example:
        >>> client = MockFilesClient()
        >>> file_obj = client.files.create(file=Path("test.pdf"), purpose="assistants")
        >>> assert file_obj.id.startswith("file-")
        >>>
        >>> # Retrieve file
        >>> retrieved = client.files.retrieve(file_obj.id)
        >>> assert retrieved.filename == "test.pdf"
        >>>
        >>> # Delete file
        >>> result = client.files.delete(file_obj.id)
        >>> assert result["deleted"] == True
    """

    def __init__(self):
        """Initialize mock Files API client."""
        self.files = MockFilesNamespace()
