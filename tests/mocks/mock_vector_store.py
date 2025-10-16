"""Mock implementation of OpenAI Vector Stores API for testing.

This module provides a mock of the OpenAI Vector Stores API that:
- Simulates vector_stores.create()
- Simulates vector_stores.files.create() (attach file to vector store)
- Simulates vector_stores.files.update() (update file attributes)
- Tracks vector stores and attached files in memory

Example usage:
    from tests.mocks.mock_vector_store import MockVectorStoreClient

    client = MockVectorStoreClient()
    vs = client.vector_stores.create(name="test-store")
    vs_file = client.vector_stores.files.create(vector_store_id=vs.id, file_id="file-123")
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass, field
import uuid


@dataclass
class VectorStore:
    """Simulates OpenAI Vector Store object."""

    id: str
    name: str
    created_at: int = 1234567890
    file_counts: Dict[str, int] = field(
        default_factory=lambda: {"total": 0, "completed": 0}
    )
    status: str = "completed"


@dataclass
class VectorStoreFile:
    """Simulates OpenAI Vector Store File object."""

    id: str
    vector_store_id: str
    file_id: str
    created_at: int = 1234567890
    status: str = "completed"
    attributes: Optional[Dict[str, Any]] = None


class MockVectorStoreFilesNamespace:
    """Simulates client.vector_stores.files namespace."""

    def __init__(self):
        """Initialize mock vector store files namespace."""
        self._files: Dict[str, VectorStoreFile] = {}
        self.create_count = 0
        self.update_count = 0

    def create(self, vector_store_id: str, file_id: str, **kwargs) -> VectorStoreFile:
        """Attach a file to a vector store.

        Args:
            vector_store_id: Vector store ID
            file_id: OpenAI file ID to attach
            **kwargs: Additional parameters

        Returns:
            VectorStoreFile object

        Example:
            >>> vs_files = MockVectorStoreFilesNamespace()
            >>> vs_file = vs_files.create(
            ...     vector_store_id="vs-123",
            ...     file_id="file-456"
            ... )
            >>> assert vs_file.vector_store_id == "vs-123"
            >>> assert vs_file.file_id == "file-456"
        """
        self.create_count += 1

        # Generate unique vector store file ID
        vs_file_id = f"vsfile-{uuid.uuid4().hex[:24]}"

        vs_file = VectorStoreFile(
            id=vs_file_id,
            vector_store_id=vector_store_id,
            file_id=file_id,
            status="completed",
        )

        self._files[vs_file_id] = vs_file

        return vs_file

    def update(
        self, vector_store_id: str, file_id: str, attributes: Dict[str, Any], **kwargs
    ) -> VectorStoreFile:
        """Update file attributes in vector store.

        Args:
            vector_store_id: Vector store ID
            file_id: Vector store file ID (vsfile-xxx format)
            attributes: Metadata attributes (max 16 key-value pairs)
            **kwargs: Additional parameters

        Returns:
            Updated VectorStoreFile object

        Example:
            >>> vs_files = MockVectorStoreFilesNamespace()
            >>> vs_file = vs_files.create("vs-123", "file-456")
            >>> updated = vs_files.update(
            ...     vector_store_id="vs-123",
            ...     file_id=vs_file.id,
            ...     attributes={"sha256": "abc123", "doc_type": "Invoice"}
            ... )
            >>> assert updated.attributes["doc_type"] == "Invoice"
        """
        self.update_count += 1

        if file_id not in self._files:
            raise KeyError(f"Vector store file not found: {file_id}")

        vs_file = self._files[file_id]

        # Limit to 16 attributes (OpenAI API limit)
        limited_attrs = dict(list(attributes.items())[:16])
        vs_file.attributes = limited_attrs

        return vs_file

    def retrieve(self, vector_store_id: str, file_id: str) -> VectorStoreFile:
        """Retrieve a vector store file by ID.

        Args:
            vector_store_id: Vector store ID
            file_id: Vector store file ID

        Returns:
            VectorStoreFile object

        Raises:
            KeyError: If file not found
        """
        if file_id not in self._files:
            raise KeyError(f"Vector store file not found: {file_id}")

        return self._files[file_id]

    def delete(self, vector_store_id: str, file_id: str) -> Dict[str, Any]:
        """Delete a file from vector store.

        Args:
            vector_store_id: Vector store ID
            file_id: Vector store file ID

        Returns:
            Deletion confirmation dictionary
        """
        if file_id not in self._files:
            raise KeyError(f"Vector store file not found: {file_id}")

        del self._files[file_id]

        return {"id": file_id, "object": "vector_store.file", "deleted": True}

    def list(self, vector_store_id: str) -> Dict[str, Any]:
        """List all files in a vector store.

        Args:
            vector_store_id: Vector store ID

        Returns:
            Dictionary with list of files
        """
        files = [
            f for f in self._files.values() if f.vector_store_id == vector_store_id
        ]

        return {
            "object": "list",
            "data": [
                {
                    "id": f.id,
                    "vector_store_id": f.vector_store_id,
                    "file_id": f.file_id,
                    "created_at": f.created_at,
                    "status": f.status,
                    "attributes": f.attributes,
                }
                for f in files
            ],
        }


class MockVectorStoresNamespace:
    """Simulates client.vector_stores namespace."""

    def __init__(self):
        """Initialize mock vector stores namespace."""
        self._stores: Dict[str, VectorStore] = {}
        self.create_count = 0
        self.files = MockVectorStoreFilesNamespace()

    def create(self, name: str = "test-store", **kwargs) -> VectorStore:
        """Create a new vector store.

        Args:
            name: Name for the vector store
            **kwargs: Additional parameters

        Returns:
            VectorStore object

        Example:
            >>> vs_namespace = MockVectorStoresNamespace()
            >>> vs = vs_namespace.create(name="paper-autopilot-docs")
            >>> assert vs.id.startswith("vs-")
            >>> assert vs.name == "paper-autopilot-docs"
        """
        self.create_count += 1

        # Generate unique vector store ID
        vs_id = f"vs-{uuid.uuid4().hex[:24]}"

        vs = VectorStore(id=vs_id, name=name, status="completed")

        self._stores[vs_id] = vs

        return vs

    def retrieve(self, vector_store_id: str) -> VectorStore:
        """Retrieve a vector store by ID.

        Args:
            vector_store_id: Vector store ID

        Returns:
            VectorStore object

        Raises:
            KeyError: If vector store not found
        """
        if vector_store_id not in self._stores:
            raise KeyError(f"Vector store not found: {vector_store_id}")

        return self._stores[vector_store_id]

    def delete(self, vector_store_id: str) -> Dict[str, Any]:
        """Delete a vector store.

        Args:
            vector_store_id: Vector store ID

        Returns:
            Deletion confirmation dictionary
        """
        if vector_store_id not in self._stores:
            raise KeyError(f"Vector store not found: {vector_store_id}")

        del self._stores[vector_store_id]

        return {"id": vector_store_id, "object": "vector_store", "deleted": True}

    def list(self) -> Dict[str, Any]:
        """List all vector stores.

        Returns:
            Dictionary with list of vector stores
        """
        return {
            "object": "list",
            "data": [
                {
                    "id": vs.id,
                    "name": vs.name,
                    "created_at": vs.created_at,
                    "file_counts": vs.file_counts,
                    "status": vs.status,
                }
                for vs in self._stores.values()
            ],
        }


class MockVectorStoreClient:
    """Complete mock of OpenAI client with Vector Stores API.

    Example:
        >>> client = MockVectorStoreClient()
        >>>
        >>> # Create vector store
        >>> vs = client.vector_stores.create(name="test-docs")
        >>> assert vs.id.startswith("vs-")
        >>>
        >>> # Attach file
        >>> vs_file = client.vector_stores.files.create(
        ...     vector_store_id=vs.id,
        ...     file_id="file-123"
        ... )
        >>> assert vs_file.file_id == "file-123"
        >>>
        >>> # Update file attributes
        >>> updated = client.vector_stores.files.update(
        ...     vector_store_id=vs.id,
        ...     file_id=vs_file.id,
        ...     attributes={"sha256": "abc123", "doc_type": "Invoice"}
        ... )
        >>> assert "doc_type" in updated.attributes
    """

    def __init__(self):
        """Initialize mock Vector Store API client."""
        self.vector_stores = MockVectorStoresNamespace()
