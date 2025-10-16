# Phase 2: Database Layer - Quick Reference

## Import & Setup

```python
from src.database import DatabaseManager
from src.models import Document
import os

# Initialize
db_url = os.getenv("PAPER_AUTOPILOT_DB_URL", "sqlite:///paper_autopilot.db")
db_manager = DatabaseManager(db_url)

# Create tables (first run)
db_manager.create_tables()

# Health check
assert db_manager.health_check()
```

## Basic Operations

### Insert Document
```python
with db_manager.get_session() as session:
    doc = Document(
        sha256_hex="abc123...",
        sha256_base64="xyz789...",
        original_filename="invoice.pdf",
        file_size_bytes=102400,
        model_used="gpt-5-mini",
    )
    session.add(doc)
    # Auto-commits on success, rollback on error
```

### Query by Hash (Deduplication)
```python
with db_manager.get_session() as session:
    existing = session.query(Document).filter_by(sha256_hex="abc123...").first()
    if existing:
        print(f"Already processed: {existing.id}")
```

### Query Recent Documents
```python
from datetime import datetime, timedelta

with db_manager.get_session() as session:
    recent = session.query(Document).filter(
        Document.processed_at >= datetime.utcnow() - timedelta(days=7)
    ).all()
```

### Find by Issuer
```python
with db_manager.get_session() as session:
    docs = session.query(Document).filter_by(issuer="Acme Corp").all()
```

### Update Document
```python
with db_manager.get_session() as session:
    doc = session.query(Document).filter_by(sha256_hex="abc123...").first()
    doc.requires_review = True
    # Auto-commits on exit
```

### Soft Delete
```python
from datetime import datetime

with db_manager.get_session() as session:
    doc = session.query(Document).filter_by(id=123).first()
    doc.deleted_at = datetime.utcnow()
    # Auto-commits on exit
```

### Query Active Documents (Not Deleted)
```python
with db_manager.get_session() as session:
    active = session.query(Document).filter(Document.deleted_at.is_(None)).all()
```

## Common Queries

### Documents Requiring Review
```python
with db_manager.get_session() as session:
    review_needed = session.query(Document).filter_by(requires_review=True).all()
```

### Documents by Type and Date Range
```python
from datetime import datetime

with db_manager.get_session() as session:
    invoices = session.query(Document).filter(
        Document.doc_type == "Invoice",
        Document.primary_date >= datetime(2025, 1, 1),
        Document.primary_date < datetime(2025, 12, 31),
    ).all()
```

### Total Cost by Month
```python
from sqlalchemy import func, extract

with db_manager.get_session() as session:
    monthly_costs = session.query(
        extract('year', Document.processed_at).label('year'),
        extract('month', Document.processed_at).label('month'),
        func.sum(Document.total_cost_usd).label('total_cost')
    ).group_by('year', 'month').all()
```

### Count by Document Type
```python
from sqlalchemy import func

with db_manager.get_session() as session:
    counts = session.query(
        Document.doc_type,
        func.count(Document.id).label('count')
    ).group_by(Document.doc_type).all()
```

## Migration Commands

```bash
# Apply all migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# Show current version
alembic current

# Show history
alembic history --verbose

# Create new migration (after model changes)
alembic revision --autogenerate -m "Description"

# Manually set version (use with caution)
alembic stamp head
```

## Environment Variables

```bash
# Required
export PAPER_AUTOPILOT_DB_URL="sqlite:///paper_autopilot.db"

# Or for PostgreSQL
export PAPER_AUTOPILOT_DB_URL="postgresql://user:password@localhost:5432/paper_autopilot"
```

## Model Fields (40+ total)

### Required Fields
- `sha256_hex` (str, unique)
- `sha256_base64` (str)
- `original_filename` (str)
- `file_size_bytes` (int, > 0)
- `model_used` (str)
- `processed_at` (datetime, auto)
- `requires_review` (bool, default False)
- `created_at` (datetime, auto)
- `updated_at` (datetime, auto)

### Optional Fields
- `page_count` (int, > 0)
- `doc_type` (str)
- `doc_subtype` (str)
- `confidence_score` (float)
- `issuer` (str)
- `recipient` (str)
- `primary_date` (datetime)
- `secondary_date` (datetime)
- `total_amount` (float)
- `currency` (str, ISO 4217)
- `summary` (text)
- `action_items` (JSON)
- `deadlines` (JSON)
- `urgency_level` (str)
- `tags` (JSON)
- `ocr_text_excerpt` (text)
- `language_detected` (str, ISO 639-1)
- `vector_store_file_id` (str)
- `vector_store_attributes` (JSON, max 16 KV)
- `processing_duration_seconds` (float)
- `prompt_tokens` (int)
- `completion_tokens` (int)
- `cached_tokens` (int)
- `total_cost_usd` (float)
- `extraction_quality` (str)
- `validation_errors` (JSON)
- `raw_response_json` (JSON)
- `deleted_at` (datetime, soft delete)

## Validation Script

```bash
# Run all validation tests
./scripts/validate_phase2.sh

# Expected output:
# ✅ Models import successfully
# ✅ Database operations work correctly
# ✅ Health check works
# ✅ Migrations are reversible
# ✅ Model constraints enforced correctly
```

## Troubleshooting

### "No such table" error
```bash
alembic upgrade head
```

### "Table already exists" error
```python
# Drop and recreate (CAUTION: data loss)
db_manager.drop_tables()
db_manager.create_tables()
```

### Connection issues
```python
# Check health
if not db_manager.health_check():
    print("Database connection failed")
```

### View schema
```bash
# SQLite
sqlite3 paper_autopilot.db ".schema documents"

# PostgreSQL
psql -d paper_autopilot -c "\d documents"
```

## Key Indexes

- `sha256_hex` - Unique, for deduplication
- `sha256_base64` - For vector store lookup
- `doc_type` - For type-based queries
- `issuer` - For issuer-based queries
- `primary_date` - For date-based queries
- `processed_at` - For processing time queries
- `requires_review` - For review workflow
- `deleted_at` - For soft delete queries
- Composite: `(doc_type, primary_date)` - For type+date queries
- Composite: `(issuer, primary_date)` - For issuer+date queries

## File Locations

```
/Users/krisstudio/Developer/Projects/autoD/
├── src/
│   ├── models.py       # ORM models
│   └── database.py     # Session management
├── alembic/
│   ├── env.py          # Migration environment
│   └── versions/       # Migration files
├── alembic.ini         # Alembic config
└── scripts/
    └── validate_phase2.sh  # Tests
```

## Documentation

- **Complete Guide:** `/Users/krisstudio/Developer/Projects/autoD/docs/phase2_database_layer.md`
- **Handoff Report:** `/Users/krisstudio/Developer/Projects/autoD/docs/phase2_handoff.json`
- **Quick Reference:** `/Users/krisstudio/Developer/Projects/autoD/docs/phase2_quick_reference.md` (this file)
