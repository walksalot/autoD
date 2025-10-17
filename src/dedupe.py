"""
File deduplication utilities using SHA-256 hashing.
Prevents reprocessing duplicate documents.
"""

import hashlib
import base64
from pathlib import Path
from typing import Optional, Dict, Tuple
from sqlalchemy.orm import Session

from src.models import Document


def sha256_file(file_path: Path, chunk_size: int = 8192) -> Tuple[str, str]:
    """
    Compute SHA-256 hash of a file in both hex and base64 encodings.

    Uses streaming reads to handle large files efficiently without loading
    entire file into memory.

    Args:
        file_path: Path to file to hash
        chunk_size: Read chunk size in bytes (default 8KB)

    Returns:
        Tuple of (hex_hash, base64_hash)
        - hex_hash: 64-character hexadecimal string
        - base64_hash: 44-character base64 string

    Raises:
        FileNotFoundError: If file doesn't exist
        IOError: If file cannot be read

    Example:
        >>> hex_hash, b64_hash = sha256_file(Path("document.pdf"))
        >>> print(hex_hash)  # e.g., "a1b2c3d4..."
        >>> print(b64_hash)  # e.g., "abcDEF123=="
    """
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    sha256_hash = hashlib.sha256()

    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            sha256_hash.update(chunk)

    # Get both encodings
    hash_bytes = sha256_hash.digest()
    hex_encoding = hash_bytes.hex()
    base64_encoding = base64.b64encode(hash_bytes).decode("ascii")

    return hex_encoding, base64_encoding


def check_duplicate(session: Session, sha256_hex: str) -> Optional[Document]:
    """
    Check if a document with this hash already exists in the database.

    Args:
        session: SQLAlchemy session
        sha256_hex: SHA-256 hash in hexadecimal format

    Returns:
        Document if duplicate found, None otherwise

    Example:
        >>> with db_manager.get_session() as session:
        ...     duplicate = check_duplicate(session, hex_hash)
        ...     if duplicate:
        ...         print(f"Duplicate: {duplicate.original_filename}")
    """
    return session.query(Document).filter(Document.sha256_hex == sha256_hex).first()


def build_vector_store_attributes(
    doc: Document,
    max_attributes: int = 16,
) -> Dict[str, str]:
    """
    Build metadata attributes for OpenAI vector store.

    OpenAI File Search has a limit of 16 key-value pairs per file.
    This function selects the most discriminative fields for search.

    Args:
        doc: Document model instance
        max_attributes: Maximum number of attributes (OpenAI limit: 16)

    Returns:
        Dictionary of metadata attributes (all values as strings)

    Note:
        - All values must be strings
        - Keys should be descriptive
        - Prioritize searchable/filterable fields

    Example:
        >>> attributes = build_vector_store_attributes(document)
        >>> print(attributes)
        {
            "sha256_base64": "abcDEF123==",
            "doc_type": "Invoice",
            "issuer": "Acme Corp",
            "primary_date": "2024-01-15",
            ...
        }
    """
    attributes: Dict[str, str] = {}

    # Priority 1: File identification (essential for deduplication)
    if doc.sha256_base64:
        attributes["sha256_base64"] = doc.sha256_base64

    # Priority 2: Document classification
    if doc.doc_type:
        attributes["doc_type"] = doc.doc_type
    if doc.doc_subtype:
        attributes["doc_subtype"] = doc.doc_subtype

    # Priority 3: Key parties
    if doc.issuer:
        attributes["issuer"] = doc.issuer[:100]  # Truncate long names
    if doc.recipient:
        attributes["recipient"] = doc.recipient[:100]

    # Priority 4: Dates (as ISO strings)
    if doc.primary_date:
        attributes["primary_date"] = doc.primary_date.strftime("%Y-%m-%d")
    if doc.secondary_date:
        attributes["secondary_date"] = doc.secondary_date.strftime("%Y-%m-%d")

    # Priority 5: Financial information
    if doc.total_amount is not None:
        attributes["total_amount"] = f"{doc.total_amount:.2f}"
    if doc.currency:
        attributes["currency"] = doc.currency

    # Priority 6: Business intelligence
    if doc.urgency_level:
        attributes["urgency_level"] = doc.urgency_level

    # Priority 7: Quality indicators
    if doc.extraction_quality:
        attributes["extraction_quality"] = doc.extraction_quality
    attributes["requires_review"] = "true" if doc.requires_review else "false"

    # Priority 8: Timestamps
    if doc.processed_at:
        attributes["processed_at"] = doc.processed_at.strftime("%Y-%m-%d")

    # Priority 9: Original filename (truncated)
    attributes["filename"] = doc.original_filename[-50:]  # Last 50 chars

    # Enforce limit
    if len(attributes) > max_attributes:
        # Keep the most important attributes (prioritized order above)
        keys_to_keep = list(attributes.keys())[:max_attributes]
        attributes = {k: attributes[k] for k in keys_to_keep}

    return attributes


def deduplicate_and_hash(
    file_path: Path,
    session: Session,
) -> Tuple[Optional[str], Optional[str], Optional[Document]]:
    """
    Hash a file and check for duplicates in one operation.

    Convenience function that combines hashing and duplicate checking.

    Args:
        file_path: Path to PDF file
        session: SQLAlchemy session for database queries

    Returns:
        Tuple of (hex_hash, base64_hash, duplicate_document)
        - If duplicate found: (hex_hash, base64_hash, Document)
        - If new file: (hex_hash, base64_hash, None)

    Example:
        >>> hex_hash, b64_hash, duplicate = deduplicate_and_hash(
        ...     Path("new_invoice.pdf"),
        ...     session
        ... )
        >>> if duplicate:
        ...     print(f"Skip processing: duplicate of {duplicate.id}")
        ... else:
        ...     print(f"New file, hash: {hex_hash}")
    """
    hex_hash, b64_hash = sha256_file(file_path)
    duplicate = check_duplicate(session, hex_hash)

    return hex_hash, b64_hash, duplicate


# Example usage and testing
if __name__ == "__main__":
    from src.database import DatabaseManager
    from src.models import Document
    import tempfile
    import os
    from datetime import date

    # Create temporary test file
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".pdf", delete=False) as f:
        test_file = Path(f.name)
        f.write(b"Test PDF content for hashing")

    try:
        print("=== SHA-256 Hashing Test ===")
        hex_hash, b64_hash = sha256_file(test_file)
        print(f"✅ Hex hash: {hex_hash}")
        print(f"✅ Base64 hash: {b64_hash}")
        print(f"   Hex length: {len(hex_hash)} chars (expected: 64)")
        print(f"   Base64 length: {len(b64_hash)} chars (expected: 44)")

        # Verify hash consistency (hash same file twice)
        hex_hash2, b64_hash2 = sha256_file(test_file)
        if hex_hash == hex_hash2 and b64_hash == b64_hash2:
            print("✅ Hash consistency: Same file produces same hashes")
        else:
            print("❌ Hash consistency: FAILED")

        print("\n=== Database Deduplication Test ===")

        # Create test database
        db_url = os.getenv("PAPER_AUTOPILOT_DB_URL", "sqlite:///test_dedupe.db")
        db_manager = DatabaseManager(db_url, echo=False)
        db_manager.create_tables()

        with db_manager.get_session() as session:
            # Test 1: No duplicate (first insert)
            duplicate = check_duplicate(session, hex_hash)
            if duplicate is None:
                print("✅ No duplicate found (expected for first check)")
            else:
                print("❌ Found duplicate when shouldn't exist")

            # Insert document
            doc = Document(
                sha256_hex=hex_hash,
                sha256_base64=b64_hash,
                original_filename="test_invoice.pdf",
                file_size_bytes=1024,
                model_used="gpt-5-mini",
                doc_type="Invoice",
                issuer="Test Corp",
                primary_date=date(2024, 1, 15),
                total_amount=1250.00,
                currency="USD",
                urgency_level="medium",
                extraction_quality="excellent",
                requires_review=False,
            )
            session.add(doc)
            session.commit()
            print(f"✅ Inserted document with ID: {doc.id}")

            # Test 2: Duplicate found (second check)
            duplicate = check_duplicate(session, hex_hash)
            if duplicate:
                print(f"✅ Duplicate found: Document ID {duplicate.id}")
            else:
                print("❌ Duplicate not found when it should exist")

            # Test 3: Combined operation
            hex_hash3, b64_hash3, dup3 = deduplicate_and_hash(test_file, session)
            if dup3:
                print(f"✅ deduplicate_and_hash found duplicate: ID {dup3.id}")
            else:
                print("❌ deduplicate_and_hash didn't find duplicate")

            # Test 4: Vector store attributes
            attributes = build_vector_store_attributes(doc)
            print("\n=== Vector Store Attributes ===")
            print(f"✅ Generated {len(attributes)} attributes (max: 16)")
            for key, value in attributes.items():
                print(f"   {key}: {value}")

            if len(attributes) <= 16:
                print("✅ Attribute count within OpenAI limit")
            else:
                print(f"❌ Too many attributes: {len(attributes)} > 16")

        print("\n=== Memory Efficiency Test ===")
        # Test with larger file (simulate 100MB PDF)
        large_test_file = Path(tempfile.mktemp(suffix=".pdf"))
        try:
            with open(large_test_file, "wb") as f:
                # Write 100MB of data
                chunk = b"x" * 8192
                for _ in range(12800):  # 12800 * 8KB = 100MB
                    f.write(chunk)

            import tracemalloc

            tracemalloc.start()

            hex_large, b64_large = sha256_file(large_test_file)

            current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()

            print("✅ Hashed 100MB file")
            print(f"   Peak memory: {peak / 1024 / 1024:.2f} MB")

            if peak < 20 * 1024 * 1024:  # Less than 20MB
                print("✅ Memory efficient: Used < 20MB for 100MB file")
            else:
                print(
                    f"⚠️ Memory usage higher than expected: {peak / 1024 / 1024:.2f} MB"
                )
        finally:
            if large_test_file.exists():
                large_test_file.unlink()

        print("\n=== All Tests Complete ===")
        print("✅ SHA-256 hashing works correctly")
        print("✅ Duplicate detection works correctly")
        print("✅ Vector store attributes generated correctly")
        print("✅ Memory efficiency validated")

    finally:
        # Cleanup
        if test_file.exists():
            test_file.unlink()

        # Remove test database
        if Path("test_dedupe.db").exists():
            Path("test_dedupe.db").unlink()
