#!/bin/bash
# Phase 2 Validation Script
# Tests database layer implementation

set -e

echo "=== Phase 2: Database Layer Validation ==="
echo ""

# Activate virtual environment
source venv/bin/activate

# Test 1: Models import
echo "Test 1: Models import..."
python -c "from src.models import Document, Base; print('✅ Models imported successfully')"
echo ""

# Test 2: Database operations
echo "Test 2: Database operations..."
rm -f test_validation.db
python -c "
from src.database import DatabaseManager
from src.models import Document

db = DatabaseManager('sqlite:///test_validation.db', echo=False)
db.create_tables()

# Insert test document
with db.get_session() as session:
    doc = Document(
        sha256_hex='a' * 64,
        sha256_base64='b' * 44,
        original_filename='test_validation.pdf',
        file_size_bytes=2048,
        model_used='gpt-5-mini',
        page_count=5,
    )
    session.add(doc)

# Query test document
with db.get_session() as session:
    docs = session.query(Document).all()
    assert len(docs) == 1, f'Expected 1 document, got {len(docs)}'
    assert docs[0].original_filename == 'test_validation.pdf'
    assert docs[0].file_size_bytes == 2048
    assert docs[0].page_count == 5

print('✅ Database operations work correctly')
"
rm -f test_validation.db
echo ""

# Test 3: Health check
echo "Test 3: Health check..."
python -c "
from src.database import DatabaseManager

db = DatabaseManager('sqlite:///test_health.db')
db.create_tables()
assert db.health_check() == True, 'Health check failed'
print('✅ Health check works')
"
rm -f test_health.db
echo ""

# Test 4: Alembic migrations
echo "Test 4: Alembic migrations..."
rm -f test_migration.db
export PAPER_AUTOPILOT_DB_URL=sqlite:///test_migration.db

alembic upgrade head > /dev/null 2>&1
echo "  ✓ Migration upgrade successful"

alembic downgrade -1 > /dev/null 2>&1
echo "  ✓ Migration downgrade successful"

alembic upgrade head > /dev/null 2>&1
echo "  ✓ Migration re-upgrade successful"

rm -f test_migration.db
echo "✅ Migrations are reversible"
echo ""

# Test 5: Model constraints
echo "Test 5: Model constraints..."
python -c "
from src.database import DatabaseManager
from src.models import Document
import sys

db = DatabaseManager('sqlite:///test_constraints.db', echo=False)
db.create_tables()

# Test: file_size_bytes must be positive
try:
    with db.get_session() as session:
        doc = Document(
            sha256_hex='c' * 64,
            sha256_base64='d' * 44,
            original_filename='test_neg_size.pdf',
            file_size_bytes=-100,  # Invalid: negative size
            model_used='gpt-5-mini',
        )
        session.add(doc)
    print('❌ Constraint check failed: negative file size allowed')
    sys.exit(1)
except Exception:
    print('  ✓ Check constraint working: negative file_size_bytes rejected')

# Test: page_count must be positive or null
try:
    with db.get_session() as session:
        doc = Document(
            sha256_hex='e' * 64,
            sha256_base64='f' * 44,
            original_filename='test_neg_pages.pdf',
            file_size_bytes=100,
            page_count=-5,  # Invalid: negative pages
            model_used='gpt-5-mini',
        )
        session.add(doc)
    print('❌ Constraint check failed: negative page_count allowed')
    sys.exit(1)
except Exception:
    print('  ✓ Check constraint working: negative page_count rejected')

print('✅ Model constraints enforced correctly')
"
rm -f test_constraints.db
echo ""

echo "=== All Phase 2 Validations Passed ==="
echo ""
echo "Artifacts created:"
echo "  - src/models.py (Document model with 40+ fields)"
echo "  - src/database.py (DatabaseManager with session handling)"
echo "  - alembic.ini (Alembic configuration)"
echo "  - alembic/env.py (Migration environment)"
echo "  - alembic/versions/68503a3a3e10_*.py (Initial migration)"
