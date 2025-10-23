"""
Property-based tests for SHA-256 hashing with Hypothesis.

Tests cryptographic properties:
- Determinism: Same input → same hash
- Fixed length: Always 64-char hex, 44-char base64
- Collision resistance: Different inputs → different hashes (with high probability)
- Avalanche effect: Small input changes → completely different output
"""

import tempfile
from pathlib import Path
from hypothesis import given, strategies as st, assume, settings, HealthCheck
from hypothesis.stateful import RuleBasedStateMachine, rule, invariant

from src.dedupe import sha256_file, deduplicate_and_hash, check_duplicate
from src.database import DatabaseManager
from src.models import Document


# === Property 1: Determinism ===


@given(content=st.binary(min_size=0, max_size=10_000))
@settings(max_examples=50)
def test_sha256_is_deterministic(content):
    """
    Property: Hashing the same file twice produces identical hashes.

    For any binary content, sha256_file should return the same result
    when called multiple times on the same file.
    """
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".pdf", delete=False) as f:
        test_file = Path(f.name)
        f.write(content)

    try:
        hex1, b64_1 = sha256_file(test_file)
        hex2, b64_2 = sha256_file(test_file)

        assert hex1 == hex2, "Hex hashes should be identical"
        assert b64_1 == b64_2, "Base64 hashes should be identical"
    finally:
        if test_file.exists():
            test_file.unlink()


# === Property 2: Fixed Length ===


@given(content=st.binary(min_size=1, max_size=10_000))
@settings(max_examples=50)
def test_sha256_produces_fixed_length_output(content):
    """
    Property: SHA-256 always produces 64-char hex and 44-char base64.

    Regardless of input size, output length should be constant.
    """
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".pdf", delete=False) as f:
        test_file = Path(f.name)
        f.write(content)

    try:
        hex_hash, b64_hash = sha256_file(test_file)

        assert len(hex_hash) == 64, f"Hex hash should be 64 chars, got {len(hex_hash)}"
        assert (
            len(b64_hash) == 44
        ), f"Base64 hash should be 44 chars, got {len(b64_hash)}"

        # Verify hex is all hexadecimal characters
        assert all(
            c in "0123456789abcdef" for c in hex_hash
        ), "Hex hash contains invalid characters"

        # Verify base64 is valid base64 charset
        valid_b64_chars = set(
            "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/="
        )
        assert all(
            c in valid_b64_chars for c in b64_hash
        ), "Base64 hash contains invalid characters"
    finally:
        if test_file.exists():
            test_file.unlink()


# === Property 3: Collision Resistance ===


@given(
    content1=st.binary(min_size=1, max_size=5_000),
    content2=st.binary(min_size=1, max_size=5_000),
)
@settings(max_examples=30, suppress_health_check=[HealthCheck.filter_too_much])
def test_different_content_produces_different_hashes(content1, content2):
    """
    Property: Different inputs produce different hashes (collision resistance).

    SHA-256 is cryptographically secure, so collisions should be astronomically rare.
    This test verifies we get different outputs for different inputs.
    """
    assume(content1 != content2)  # Only test when inputs are actually different

    file1 = None
    file2 = None

    try:
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".pdf", delete=False) as f:
            file1 = Path(f.name)
            f.write(content1)

        with tempfile.NamedTemporaryFile(mode="wb", suffix=".pdf", delete=False) as f:
            file2 = Path(f.name)
            f.write(content2)

        hex1, b64_1 = sha256_file(file1)
        hex2, b64_2 = sha256_file(file2)

        assert hex1 != hex2, "Different content should produce different hex hashes"
        assert (
            b64_1 != b64_2
        ), "Different content should produce different base64 hashes"
    finally:
        if file1 and file1.exists():
            file1.unlink()
        if file2 and file2.exists():
            file2.unlink()


# === Property 4: Avalanche Effect ===


@given(
    base_content=st.binary(min_size=10, max_size=1_000),
    bit_position=st.integers(min_value=0, max_value=79),  # Flip a bit in first 10 bytes
)
@settings(max_examples=30)
def test_single_bit_flip_changes_hash_completely(base_content, bit_position):
    """
    Property: Changing a single bit produces a completely different hash (avalanche effect).

    This is a key property of cryptographic hash functions - small changes
    in input should produce large, unpredictable changes in output.
    """
    assume(len(base_content) >= 10)  # Ensure we have enough bytes

    # Create modified content with one bit flipped
    byte_pos = bit_position // 8
    bit_offset = bit_position % 8

    modified_content = bytearray(base_content)
    modified_content[byte_pos] ^= 1 << bit_offset  # Flip the bit

    file1 = None
    file2 = None

    try:
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".pdf", delete=False) as f:
            file1 = Path(f.name)
            f.write(base_content)

        with tempfile.NamedTemporaryFile(mode="wb", suffix=".pdf", delete=False) as f:
            file2 = Path(f.name)
            f.write(bytes(modified_content))

        hex1, b64_1 = sha256_file(file1)
        hex2, b64_2 = sha256_file(file2)

        # Hashes should be completely different
        assert hex1 != hex2, "Single bit flip should change hex hash"
        assert b64_1 != b64_2, "Single bit flip should change base64 hash"

        # Count differing characters (avalanche effect should change most of output)
        hex_diff_count = sum(c1 != c2 for c1, c2 in zip(hex1, hex2))

        # With strong avalanche (like SHA-256), we expect most characters to differ
        # Allow range of 40-64 out of 64 characters (62-100%)
        # SHA-256 has excellent avalanche, typically changing 55-62 chars (85-97%)
        assert 40 <= hex_diff_count <= 64, (
            f"Avalanche effect too weak: only {hex_diff_count}/64 hex chars differ "
            f"(expected ≥40). Hashes: {hex1} vs {hex2}"
        )
    finally:
        if file1 and file1.exists():
            file1.unlink()
        if file2 and file2.exists():
            file2.unlink()


# === Property 5: Empty File Handling ===


def test_empty_file_hashes_consistently():
    """
    Property: Empty files should hash consistently.

    Known value test: Empty file SHA-256 is deterministic.
    """
    EMPTY_FILE_HEX = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    EMPTY_FILE_B64 = "47DEQpj8HBSa+/TImW+5JCeuQeRkm5NMpJWZG3hSuFU="

    with tempfile.NamedTemporaryFile(mode="wb", suffix=".pdf", delete=False) as f:
        test_file = Path(f.name)
        # Don't write anything - file is empty

    try:
        hex_hash, b64_hash = sha256_file(test_file)

        assert hex_hash == EMPTY_FILE_HEX, "Empty file hex hash mismatch"
        assert b64_hash == EMPTY_FILE_B64, "Empty file base64 hash mismatch"
    finally:
        if test_file.exists():
            test_file.unlink()


# === Property 6: Chunk Size Independence ===


@given(
    content=st.binary(min_size=100, max_size=10_000),
    chunk_size=st.integers(min_value=1, max_value=16384),
)
@settings(max_examples=20)
def test_chunk_size_does_not_affect_hash(content, chunk_size):
    """
    Property: Hash should be independent of chunk size used for reading.

    sha256_file reads files in chunks - the chunk size should not affect
    the final hash value.
    """
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".pdf", delete=False) as f:
        test_file = Path(f.name)
        f.write(content)

    try:
        # Hash with default chunk size
        hex_default, b64_default = sha256_file(test_file)

        # Hash with custom chunk size
        hex_custom, b64_custom = sha256_file(test_file, chunk_size=chunk_size)

        assert hex_default == hex_custom, "Chunk size should not affect hex hash"
        assert b64_default == b64_custom, "Chunk size should not affect base64 hash"
    finally:
        if test_file.exists():
            test_file.unlink()


# === Property 7: Deduplication Correctness ===


@given(content=st.binary(min_size=1, max_size=5_000))
@settings(max_examples=20)
def test_deduplicate_and_hash_detects_duplicates(content):
    """
    Property: deduplicate_and_hash correctly identifies duplicate files.

    When a file with the same content is processed twice, the second
    call should detect the duplicate.
    """
    # Create unique test database per example (avoids fixture issues)
    db_path = Path(tempfile.mktemp(suffix=".db"))
    db_manager = DatabaseManager(f"sqlite:///{db_path}")
    db_manager.create_tables()

    with tempfile.NamedTemporaryFile(mode="wb", suffix=".pdf", delete=False) as f:
        test_file = Path(f.name)
        f.write(content)

    try:
        with db_manager.get_session() as session:
            # First call: No duplicate should be found
            hex1, b64_1, dup1 = deduplicate_and_hash(test_file, session)
            assert dup1 is None, "First call should not find a duplicate"

            # Insert document into database
            doc = Document(
                sha256_hex=hex1,
                sha256_base64=b64_1,
                original_filename=test_file.name,
                file_size_bytes=len(content),
                metadata_json={"test": "data"},
                status="completed",
            )
            session.add(doc)
            session.commit()
            doc_id = doc.id

            # Second call: Duplicate should be found
            hex2, b64_2, dup2 = deduplicate_and_hash(test_file, session)
            assert hex2 == hex1, "Hashes should match"
            assert b64_2 == b64_1, "Base64 hashes should match"
            assert dup2 is not None, "Second call should find a duplicate"
            assert dup2.id == doc_id, "Duplicate should be the same document"
    finally:
        if test_file.exists():
            test_file.unlink()
        if db_path.exists():
            db_path.unlink()


# === Property 8: Database Duplicate Check Consistency ===


@given(
    content1=st.binary(min_size=1, max_size=5_000),
    content2=st.binary(min_size=1, max_size=5_000),
)
@settings(max_examples=20, suppress_health_check=[HealthCheck.filter_too_much])
def test_check_duplicate_only_finds_exact_matches(content1, content2):
    """
    Property: check_duplicate only returns True for exact hash matches.

    Different content (different hash) should not trigger false positives.
    """
    assume(content1 != content2)

    # Create unique test database per example (avoids fixture issues)
    db_path = Path(tempfile.mktemp(suffix=".db"))
    db_manager = DatabaseManager(f"sqlite:///{db_path}")
    db_manager.create_tables()

    file1 = None
    file2 = None

    try:
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".pdf", delete=False) as f:
            file1 = Path(f.name)
            f.write(content1)

        with tempfile.NamedTemporaryFile(mode="wb", suffix=".pdf", delete=False) as f:
            file2 = Path(f.name)
            f.write(content2)

        hex1, _ = sha256_file(file1)
        hex2, b64_2 = sha256_file(file2)

        with db_manager.get_session() as session:
            # Insert document with hash1
            doc1 = Document(
                sha256_hex=hex1,
                original_filename=file1.name,
                file_size_bytes=len(content1),
                metadata_json={},
                status="completed",
            )
            session.add(doc1)
            session.commit()

            # Check for hex1: Should find duplicate
            dup1 = check_duplicate(session, hex1)
            assert dup1 is not None, "Should find document with hash1"
            assert dup1.id == doc1.id, "Should return correct document"

            # Check for hex2: Should NOT find duplicate (different hash)
            dup2 = check_duplicate(session, hex2)
            assert dup2 is None, "Should not find document with different hash"
    finally:
        if file1 and file1.exists():
            file1.unlink()
        if file2 and file2.exists():
            file2.unlink()
        if db_path.exists():
            db_path.unlink()


# === Stateful Testing: Hash Database State Machine ===


class HashDatabaseStateMachine(RuleBasedStateMachine):
    """
    Stateful property-based testing for hash + database operations.

    This tests sequences of operations (hash, insert, check duplicate)
    to ensure consistency across multiple operations.
    """

    def __init__(self):
        super().__init__()
        self.db_path = Path(tempfile.mktemp(suffix=".db"))
        self.db_manager = DatabaseManager(f"sqlite:///{self.db_path}")
        self.db_manager.create_tables()
        self.known_hashes = {}  # hash -> document_id
        self.temp_files = []

    @rule(content=st.binary(min_size=1, max_size=1000))
    def hash_and_insert(self, content):
        """Hash a file and insert it into the database."""
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".pdf", delete=False) as f:
            test_file = Path(f.name)
            f.write(content)
            self.temp_files.append(test_file)

        hex_hash, b64_hash = sha256_file(test_file)

        if hex_hash not in self.known_hashes:
            with self.db_manager.get_session() as session:
                doc = Document(
                    sha256_hex=hex_hash,
                    sha256_base64=b64_hash,
                    original_filename=test_file.name,
                    file_size_bytes=len(content),
                    metadata_json={},
                    status="completed",
                )
                session.add(doc)
                session.commit()
                self.known_hashes[hex_hash] = doc.id

    @rule(content=st.binary(min_size=1, max_size=1000))
    def check_known_hash(self, content):
        """Verify that hashed content can be looked up correctly."""
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".pdf", delete=False) as f:
            test_file = Path(f.name)
            f.write(content)
            self.temp_files.append(test_file)

        hex_hash, _ = sha256_file(test_file)

        with self.db_manager.get_session() as session:
            dup = check_duplicate(session, hex_hash)

            if hex_hash in self.known_hashes:
                assert dup is not None, f"Should find duplicate for {hex_hash}"
                assert dup.id == self.known_hashes[hex_hash], "Returned wrong document"
            else:
                assert (
                    dup is None
                ), f"Should not find duplicate for unknown hash {hex_hash}"

    @invariant()
    def database_consistency(self):
        """Invariant: All known hashes exist in database with correct IDs."""
        with self.db_manager.get_session() as session:
            for hex_hash, expected_id in self.known_hashes.items():
                doc = check_duplicate(session, hex_hash)
                assert doc is not None, f"Hash {hex_hash} should exist in database"
                assert (
                    doc.id == expected_id
                ), f"Document ID mismatch for hash {hex_hash}"

    def teardown(self):
        """Clean up temporary files and database."""
        for temp_file in self.temp_files:
            if temp_file.exists():
                temp_file.unlink()
        if self.db_path.exists():
            self.db_path.unlink()


# Run the state machine test
TestHashDatabase = HashDatabaseStateMachine.TestCase
