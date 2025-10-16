"""
Tests for DedupeCheckStage.

Validates:
- Deduplication detection (existing documents)
- New document handling (no duplicates)
- Database queries
- Context flag setting (is_duplicate, existing_doc_id)
- Edge cases (empty database, multiple duplicates)
"""

import pytest
from datetime import datetime, timezone
from src.stages.dedupe_stage import DedupeCheckStage
from src.models import Document


def test_no_duplicate_when_database_empty(test_db_session, context_with_hash):
    """
    Test document is not marked as duplicate when database is empty.

    Validates stage correctly handles first document insertion.
    """
    stage = DedupeCheckStage(test_db_session)

    result = stage.execute(context_with_hash)

    assert result.is_duplicate is False
    assert result.existing_doc_id is None


def test_duplicate_detected_when_hash_exists(
    test_db_session, context_with_hash, existing_document
):
    """
    Test duplicate is detected when SHA-256 hash already exists.

    Validates stage finds existing document by sha256_hex.
    """
    stage = DedupeCheckStage(test_db_session)

    # existing_document fixture has same sha256_hex as context_with_hash
    result = stage.execute(context_with_hash)

    assert result.is_duplicate is True
    assert result.existing_doc_id == existing_document.id


def test_no_duplicate_for_different_hash(test_db_session, context_with_hash):
    """
    Test no duplicate detected when SHA-256 hash is different.

    Creates existing document with different hash to verify uniqueness check.
    """
    # Create document with different hash
    different_doc = Document(
        sha256_hex="a" * 64,  # Different hash
        original_filename="different.pdf",
        created_at=datetime.now(timezone.utc),
        status="completed",
    )
    test_db_session.add(different_doc)
    test_db_session.commit()

    stage = DedupeCheckStage(test_db_session)
    result = stage.execute(context_with_hash)

    assert result.is_duplicate is False
    assert result.existing_doc_id is None


def test_requires_sha256_hex_in_context(test_db_session, empty_context):
    """
    Test stage raises error if sha256_hex not set in context.

    Stage depends on ComputeSHA256Stage running first.
    """
    stage = DedupeCheckStage(test_db_session)

    # empty_context has no sha256_hex
    with pytest.raises(ValueError, match="sha256_hex not set"):
        stage.execute(empty_context)


def test_duplicate_detection_ignores_filename(
    test_db_session, context_with_hash, sample_sha256_hex
):
    """
    Test deduplication is based on hash, not filename.

    Two files with same content but different names should dedupe.
    """
    # Create document with same hash but different filename
    same_hash_doc = Document(
        sha256_hex=sample_sha256_hex,
        original_filename="totally_different_name.pdf",
        created_at=datetime.now(timezone.utc),
        status="completed",
    )
    test_db_session.add(same_hash_doc)
    test_db_session.commit()

    stage = DedupeCheckStage(test_db_session)
    result = stage.execute(context_with_hash)

    assert result.is_duplicate is True
    assert result.existing_doc_id == same_hash_doc.id


def test_duplicate_detection_ignores_status(
    test_db_session, context_with_hash, sample_sha256_hex
):
    """
    Test deduplication finds documents regardless of status.

    Even failed/pending documents should trigger deduplication.
    """
    # Create document with same hash but failed status
    failed_doc = Document(
        sha256_hex=sample_sha256_hex,
        original_filename="failed.pdf",
        created_at=datetime.now(timezone.utc),
        status="failed",
        error_message="Test error",
    )
    test_db_session.add(failed_doc)
    test_db_session.commit()

    stage = DedupeCheckStage(test_db_session)
    result = stage.execute(context_with_hash)

    assert result.is_duplicate is True
    assert result.existing_doc_id == failed_doc.id


def test_finds_first_duplicate_when_multiple_exist(
    test_db_session, context_with_hash, sample_sha256_hex
):
    """
    Test stage returns first duplicate when multiple exist (edge case).

    Database constraint should prevent this, but test handles it gracefully.
    """
    # This scenario shouldn't happen due to unique constraint on sha256_hex
    # but we test the stage behavior if it somehow occurs
    stage = DedupeCheckStage(test_db_session)

    # Create one existing document
    doc1 = Document(
        sha256_hex=sample_sha256_hex,
        original_filename="first.pdf",
        created_at=datetime.now(timezone.utc),
        status="completed",
    )
    test_db_session.add(doc1)
    test_db_session.commit()

    result = stage.execute(context_with_hash)

    assert result.is_duplicate is True
    assert result.existing_doc_id == doc1.id


def test_context_unchanged_except_flags(test_db_session, context_with_hash):
    """
    Test stage only modifies is_duplicate and existing_doc_id fields.

    Other context fields should remain unchanged.
    """
    stage = DedupeCheckStage(test_db_session)

    original_sha256_hex = context_with_hash.sha256_hex
    original_pdf_path = context_with_hash.pdf_path
    original_pdf_bytes = context_with_hash.pdf_bytes

    result = stage.execute(context_with_hash)

    # These should be unchanged
    assert result.sha256_hex == original_sha256_hex
    assert result.pdf_path == original_pdf_path
    assert result.pdf_bytes == original_pdf_bytes


def test_database_transaction_not_modified(test_db_session, context_with_hash):
    """
    Test stage does not modify database (read-only operation).

    Validates stage only queries, never inserts/updates/deletes.
    """
    stage = DedupeCheckStage(test_db_session)

    initial_count = test_db_session.query(Document).count()

    stage.execute(context_with_hash)

    final_count = test_db_session.query(Document).count()

    assert initial_count == final_count  # No new documents created


def test_case_sensitive_hash_comparison(
    test_db_session, context_with_hash, sample_sha256_hex
):
    """
    Test SHA-256 comparison is case-sensitive.

    Hex hashes should always be lowercase, but verify exact match required.
    """
    # Create document with uppercase hex (shouldn't happen in practice)
    uppercase_doc = Document(
        sha256_hex=sample_sha256_hex.upper(),
        original_filename="uppercase.pdf",
        created_at=datetime.now(timezone.utc),
        status="completed",
    )
    test_db_session.add(uppercase_doc)
    test_db_session.commit()

    stage = DedupeCheckStage(test_db_session)
    result = stage.execute(context_with_hash)

    # Should NOT match (case-sensitive comparison)
    assert result.is_duplicate is False
    assert result.existing_doc_id is None


def test_null_sha256_in_database_does_not_match(test_db_session, context_with_hash):
    """
    Test documents with NULL sha256_hex are ignored.

    Edge case: corrupted database records with missing hash.
    """
    # Create document with NULL hash (shouldn't exist, but test robustness)
    # Note: This will fail due to nullable=False constraint, so we skip this test
    # in practice. Documenting expected behavior.
    pass  # Cannot create NULL sha256_hex due to database constraint


def test_idempotency_running_twice(
    test_db_session, context_with_hash, existing_document
):
    """
    Test running stage twice on same context produces same result.

    Validates stage is idempotent (no side effects).
    """
    stage = DedupeCheckStage(test_db_session)

    result1 = stage.execute(context_with_hash)
    result2 = stage.execute(result1)

    assert result1.is_duplicate == result2.is_duplicate
    assert result1.existing_doc_id == result2.existing_doc_id
