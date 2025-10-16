# autoD Quick Reference

**Single-page cheat sheet for common commands, configurations, and troubleshooting.**

---

## Quick Start

```bash
# 1. Setup environment
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure API key
export OPENAI_API_KEY=sk-...

# 3. Initialize database
alembic upgrade head

# 4. Process PDFs
python process_inbox.py
```

---

## Common Commands

### Processing
```bash
# Process all PDFs in inbox/
python process_inbox.py

# Process single file
python process_inbox.py --file invoice.pdf

# Dry run (validate config only)
python process_inbox.py --dry-run

# Custom batch size
python process_inbox.py --batch-size 5

# Include duplicates
python process_inbox.py --no-skip-duplicates
```

### Database
```bash
# Query documents
sqlite3 paper_autopilot.db "SELECT COUNT(*) FROM documents;"

# View recent documents
sqlite3 paper_autopilot.db "SELECT id, original_filename, doc_type, processed_at FROM documents ORDER BY processed_at DESC LIMIT 10;"

# Find duplicates
sqlite3 paper_autopilot.db "SELECT sha256_hex, COUNT(*) FROM documents GROUP BY sha256_hex HAVING COUNT(*) > 1;"

# Check vector store files
sqlite3 paper_autopilot.db "SELECT COUNT(*) FROM documents WHERE vector_store_file_id IS NOT NULL;"
```

### Migrations
```bash
# Apply all pending migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# Create new migration
alembic revision --autogenerate -m "Description"

# View migration history
alembic history
```

### Logs
```bash
# Tail logs
tail -f logs/paper_autopilot.log

# Filter by level
grep "ERROR" logs/paper_autopilot.log

# JSON log analysis
cat logs/paper_autopilot.log | jq 'select(.level == "ERROR")'

# Count by status
cat logs/paper_autopilot.log | jq -s 'group_by(.status) | map({status: .[0].status, count: length})'

# Total cost
cat logs/paper_autopilot.log | jq -s 'map(select(.cost_usd)) | map(.cost_usd) | add'
```

---

## Configuration Quick Reference

### Environment Variables (.env)
```bash
# Required
OPENAI_API_KEY=sk-...

# Optional (with defaults)
OPENAI_MODEL=gpt-5-mini
DATABASE_URL=sqlite:///paper_autopilot.db
VECTOR_STORE_NAME=paper-autopilot-docs
LOG_LEVEL=INFO
MAX_RETRIES=5
```

### Config Validation
```python
from src.config import get_config

config = get_config()
print(config.openai_model)  # Prints configured model
```

---

## API Endpoints

### OpenAI Responses API
```bash
# Endpoint
POST https://api.openai.com/v1/responses

# Headers
Authorization: Bearer $OPENAI_API_KEY
Content-Type: application/json

# Request body (minimal)
{
  "model": "gpt-5-mini",
  "input": [
    {
      "role": "user",
      "content": [
        {"type": "input_text", "text": "Extract metadata"},
        {"type": "input_file", "file_id": "file-abc123"}
      ]
    }
  ],
  "text": {"format": {"type": "json_object"}}
}
```

### Files API
```bash
# Upload PDF
curl https://api.openai.com/v1/files \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -F purpose="user_data" \
  -F file="@invoice.pdf"

# List files
curl https://api.openai.com/v1/files \
  -H "Authorization: Bearer $OPENAI_API_KEY"

# Delete file
curl -X DELETE https://api.openai.com/v1/files/file-abc123 \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

---

## Database Schema Quick Reference

### Document Table
```sql
CREATE TABLE documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sha256_hex VARCHAR(64) UNIQUE NOT NULL,
    original_filename VARCHAR(512) NOT NULL,
    doc_type VARCHAR(100),
    issuer VARCHAR(255),
    primary_date DATE,
    total_amount FLOAT,
    currency VARCHAR(10),
    summary TEXT,
    vector_store_file_id VARCHAR(64),
    processed_at TIMESTAMP,
    metadata_json JSON
);
```

### Common Queries
```sql
-- Count by document type
SELECT doc_type, COUNT(*) FROM documents GROUP BY doc_type;

-- Total amount by issuer
SELECT issuer, SUM(total_amount) FROM documents GROUP BY issuer;

-- Documents this week
SELECT COUNT(*) FROM documents
WHERE processed_at >= datetime('now', '-7 days');

-- Unprocessed documents
SELECT COUNT(*) FROM documents WHERE processed_at IS NULL;
```

---

## Cost Estimation

### Token-to-Cost Formula
```python
# GPT-5 pricing (USD per 1K tokens)
INPUT_COST = 0.01
CACHED_INPUT_COST = 0.005
OUTPUT_COST = 0.03

# Calculate cost
billable_input = prompt_tokens - cached_tokens
cost = (billable_input / 1000 * INPUT_COST) + \
       (cached_tokens / 1000 * CACHED_INPUT_COST) + \
       (output_tokens / 1000 * OUTPUT_COST)
```

### Typical Costs
- **Invoice (1 page)**: ~$0.01 - $0.03
- **Multi-page PDF (10 pages)**: ~$0.05 - $0.15
- **Large document (50 pages)**: ~$0.25 - $0.75
- **Monthly processing (1000 PDFs)**: ~$10 - $50

---

## Troubleshooting Quick Checks

### System Health
```bash
# Database connectivity
python3 -c "from src.database import DatabaseManager; from src.config import get_config; db = DatabaseManager(get_config().paper_autopilot_db_url); print('OK' if db.health_check() else 'FAILED')"

# API connectivity
python3 -c "from src.api_client import ResponsesAPIClient; client = ResponsesAPIClient(); print('OK')"

# Vector store access
python3 -c "from src.vector_store import VectorStoreManager; vm = VectorStoreManager(); print('OK' if vm.get_or_create_vector_store() else 'FAILED')"
```

### Common Issues
```bash
# Missing API key
export OPENAI_API_KEY=sk-...

# Database locked (SQLite)
sqlite3 paper_autopilot.db "PRAGMA journal_mode=WAL;"

# Migration out of sync
alembic stamp head  # Mark current state
alembic upgrade head  # Apply pending

# Vector store ID lost
rm .vector_store_id  # Recreates on next run

# Clear logs (rotate)
mv logs/paper_autopilot.log logs/paper_autopilot.log.$(date +%Y%m%d)
```

---

## File Structure Overview

```
autoD/
├── inbox/              # PDFs to process (git-ignored)
├── processed/          # Successfully processed PDFs
├── failed/             # Failed PDFs
├── logs/               # Application logs
├── migrations/         # Alembic migrations
├── src/                # Application code
│   ├── config.py       # Configuration (Pydantic)
│   ├── models.py       # Database models
│   ├── processor.py    # Main pipeline
│   ├── api_client.py   # OpenAI API client
│   ├── vector_store.py # Vector store operations
│   ├── dedupe.py       # SHA-256 deduplication
│   ├── schema.py       # JSON schema validation
│   ├── prompts.py      # Prompt templates
│   ├── token_counter.py# Token/cost tracking
│   ├── logging_config.py # Structured logging
│   └── database.py     # Database manager
├── tests/              # Test suite
├── docs/               # Documentation
└── process_inbox.py    # CLI entry point
```

---

## Python Module Quick Reference

### Import Patterns
```python
# Configuration
from src.config import get_config
config = get_config()

# Database
from src.database import DatabaseManager
db = DatabaseManager(config.paper_autopilot_db_url)

# Processing
from src.processor import process_document, process_inbox
result = process_document(pdf_path, db, api_client, vector_manager)

# API Client
from src.api_client import ResponsesAPIClient
client = ResponsesAPIClient()

# Vector Store
from src.vector_store import VectorStoreManager
vm = VectorStoreManager()

# Models
from src.models import Document
doc = session.query(Document).first()

# Token Counting
from src.token_counter import calculate_cost
cost_data = calculate_cost(prompt_tokens, completion_tokens, cached_tokens, model)
```

### Common Workflows

**Process single PDF**:
```python
from pathlib import Path
from src.config import get_config
from src.database import DatabaseManager
from src.api_client import ResponsesAPIClient
from src.vector_store import VectorStoreManager
from src.processor import process_document

config = get_config()
db = DatabaseManager(config.paper_autopilot_db_url)
api_client = ResponsesAPIClient()
vector_manager = VectorStoreManager()

result = process_document(
    Path("inbox/invoice.pdf"),
    db, api_client, vector_manager
)

if result.success:
    print(f"Document ID: {result.document_id}")
else:
    print(f"Error: {result.error}")
```

**Query documents**:
```python
from src.database import DatabaseManager
from src.config import get_config
from src.models import Document

config = get_config()
db = DatabaseManager(config.paper_autopilot_db_url)

with db.get_session() as session:
    docs = session.query(Document).filter_by(doc_type="Invoice").all()
    for doc in docs:
        print(f"{doc.original_filename}: {doc.issuer}")
```

**Calculate costs**:
```python
from src.token_counter import calculate_cost

cost_data = calculate_cost(
    prompt_tokens=500,
    completion_tokens=200,
    cached_tokens=450,
    model="gpt-5-mini"
)

print(f"Total cost: ${cost_data['total_cost']:.4f}")
print(f"Cached tokens: {cost_data['cached_tokens']}")
```

---

## Testing Quick Reference

### Run Tests
```bash
# All tests
pytest

# With coverage
pytest --cov=src --cov-report=html

# Specific test file
pytest tests/test_processor.py -v

# Stop on first failure
pytest -x

# Run only tests matching pattern
pytest -k "dedupe" -v
```

### Test Fixtures
```python
# Use database fixture
def test_dedupe(db_session):
    doc = Document(sha256_hex="abc123", original_filename="test.pdf")
    db_session.add(doc)
    db_session.commit()

    assert session.query(Document).count() == 1

# Use sample PDF fixture
def test_processing(sample_pdf):
    result = process_document(sample_pdf, ...)
    assert result.success
```

---

## Performance Tuning

### SQLite Optimization
```sql
-- Enable WAL mode
PRAGMA journal_mode=WAL;

-- Increase cache size (64MB)
PRAGMA cache_size=-64000;

-- Analyze tables
ANALYZE;

-- Vacuum
VACUUM;
```

### PostgreSQL Optimization
```sql
-- Analyze tables
ANALYZE documents;

-- Create index on common queries
CREATE INDEX idx_doc_type_processed ON documents(doc_type, processed_at);

-- Update statistics
VACUUM ANALYZE documents;
```

### API Performance
- **Reuse API client** across multiple requests
- **Target >90% cache hit rate** for prompt caching
- **Monitor cached_tokens** in logs
- **Keep developer prompt identical** across requests

---

## Security Checklist

- ✅ API keys stored in environment variables (never in code)
- ✅ .env file in .gitignore
- ✅ Rotate API keys quarterly
- ✅ Use PostgreSQL role-based access in production
- ✅ Sanitize logs before sharing (no API keys, no PII)
- ✅ HTTPS only for API calls
- ✅ Validate file uploads (PDF only, size limits)
- ✅ Enable database backups
- ✅ Monitor logs for security events

---

## Monitoring Metrics

### Key Metrics to Track
- **Processing rate**: Documents per hour
- **Error rate**: Failed / Total
- **Duplicate rate**: Duplicates / Total
- **API success rate**: Successful calls / Total calls
- **Average processing time**: Seconds per document
- **Total cost**: USD per day/week/month
- **Cache hit rate**: Cached tokens / Total prompt tokens (target >90%)
- **Vector store upload success**: Uploads / Total documents

### Log Analysis Commands
```bash
# Processing rate
cat logs/paper_autopilot.log | jq -s 'map(select(.message | contains("Processing complete"))) | group_by(.timestamp[:13]) | map({hour: .[0].timestamp[:13], count: length})'

# Error rate
cat logs/paper_autopilot.log | jq -s 'map(select(.level == "ERROR")) | length'

# Average cost
cat logs/paper_autopilot.log | jq -s 'map(select(.cost_usd)) | map(.cost_usd) | add / length'

# Cache hit rate
cat logs/paper_autopilot.log | jq -s 'map(select(.cached_tokens)) | {total_prompt: map(.prompt_tokens) | add, total_cached: map(.cached_tokens) | add} | .cache_rate = (.total_cached / .total_prompt * 100)'
```

---

## References

- **Full Documentation**: `docs/` directory
- **Code Architecture**: `docs/CODE_ARCHITECTURE.md`
- **Runbook**: `docs/RUNBOOK.md`
- **API Reference**: `docs/API_DOCS.md`
- **Troubleshooting**: `docs/TROUBLESHOOTING.md`
- **Processor Guide**: `docs/PROCESSOR_GUIDE.md`
- **OpenAI Docs**: https://platform.openai.com/docs

---

**Last Updated**: 2025-10-16
**Version**: 1.0.0
**Maintained By**: Platform Engineering Team
