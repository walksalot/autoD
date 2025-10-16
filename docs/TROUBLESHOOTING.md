# Troubleshooting Guide — autoD

**Purpose**: Consolidated troubleshooting reference for common issues and their solutions

**Audience**: Developers, operators, and support engineers

**Last Updated**: 2025-10-16

---

## Table of Contents

1. [Quick Diagnostic Commands](#quick-diagnostic-commands)
2. [Configuration Issues](#configuration-issues)
3. [Database Problems](#database-problems)
4. [API Client Errors](#api-client-errors)
5. [Processing Pipeline Failures](#processing-pipeline-failures)
6. [Vector Store Issues](#vector-store-issues)
7. [Performance Problems](#performance-problems)
8. [Cost & Token Tracking](#cost--token-tracking)
9. [Logging & Debugging](#logging--debugging)
10. [Common Error Messages](#common-error-messages)

---

## Quick Diagnostic Commands

### System Health Check
```bash
# Check Python version
python --version  # Should be 3.11+

# Verify dependencies installed
python -c "from src.config import get_config; print('✅ Config OK')"
python -c "from src.database import DatabaseManager; print('✅ Database OK')"
python -c "from openai import OpenAI; print('✅ OpenAI SDK OK')"

# Check environment variables
echo $OPENAI_API_KEY  # Should start with sk-

# Check database connectivity
python -c "from src.database import DatabaseManager; db = DatabaseManager(); print('✅ DB connected' if db.health_check() else '❌ DB failed')"

# Check disk space
df -h .  # Should have > 2GB free

# Check log file size
du -h logs/paper_autopilot.log
```

### Configuration Validation
```bash
# Validate configuration loads without errors
python -c "from src.config import get_config; config = get_config(); print(f'Model: {config.openai_model}')"

# Check model is allowed
python -c "from src.config import get_config; config = get_config(); \
    allowed = {'gpt-5-mini', 'gpt-5', 'gpt-5-nano', 'gpt-5-pro', 'gpt-4.1'}; \
    print('✅ Model allowed' if config.openai_model in allowed else '❌ Invalid model')"
```

### Processing Test
```bash
# Test single file processing
python -m src.processor inbox/sample.pdf

# Expected output:
# ✅ Success: Document ID 123
#    Cost: $0.0543
#    Time: 4.23s
```

---

## Configuration Issues

### Problem: Missing API Key

**Symptoms**:
```
pydantic_core._pydantic_core.ValidationError: 1 validation error for Config
openai_api_key
  Field required [type=missing, input_value={'openai_model': 'gpt-5-mini', ...}, input_type=dict]
```

**Solution**:
```bash
# Set API key in environment
export OPENAI_API_KEY=sk-your-key-here

# OR create .env file
cat > .env <<EOF
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-5-mini
DATABASE_URL=sqlite:///paper_autopilot.db
EOF

# Verify
python -c "from src.config import get_config; config = get_config(); print('✅ API key loaded')"
```

### Problem: Invalid Model Name

**Symptoms**:
```
pydantic_core._pydantic_core.ValidationError: 1 validation error for Config
openai_model
  Value error, Model 'gpt-4o' not allowed. Must be one of: gpt-4.1, gpt-5, gpt-5-mini, gpt-5-nano, gpt-5-pro. NEVER use gpt-4o or chat completions models per project requirements.
```

**Solution**:
```bash
# Use only Frontier models
export OPENAI_MODEL=gpt-5-mini  # ✅ Correct

# Avoid these models:
# gpt-4o ❌ (Chat Completions model, not Responses API)
# gpt-4-turbo ❌
# gpt-3.5-turbo ❌

# Verify
python -c "from src.config import get_config; print(get_config().openai_model)"
```

### Problem: Frozen Config Modification

**Symptoms**:
```
pydantic_core._pydantic_core.ValidationError: Instance is frozen
```

**Solution**:
```python
# ❌ WRONG: Cannot modify frozen config
config = get_config()
config.openai_model = "gpt-5"  # Raises ValidationError

# ✅ CORRECT: Use environment variables
import os
os.environ["OPENAI_MODEL"] = "gpt-5"
config = get_config()  # Loads new value
```

### Problem: Missing .env File

**Symptoms**:
```
INFO: .env file not found, using environment variables only
```

**Solution**:
```bash
# Create .env from template
cp .env.example .env

# Edit .env with your values
nano .env

# Required fields:
# OPENAI_API_KEY=sk-...
# OPENAI_MODEL=gpt-5-mini
# DATABASE_URL=sqlite:///paper_autopilot.db
```

---

## Database Problems

### Problem: Database Locked (SQLite)

**Symptoms**:
```
sqlite3.OperationalError: database is locked
```

**Cause**: Multiple processes trying to write to SQLite simultaneously

**Solution 1** - Use PostgreSQL for production:
```bash
# Install PostgreSQL
brew install postgresql  # macOS
sudo apt install postgresql  # Ubuntu

# Create database
createdb paper_autopilot

# Update .env
DATABASE_URL=postgresql://user:password@localhost/paper_autopilot

# Run migrations
alembic upgrade head
```

**Solution 2** - Enable WAL mode for SQLite:
```bash
# Enable Write-Ahead Logging
sqlite3 paper_autopilot.db "PRAGMA journal_mode=WAL;"

# Verify
sqlite3 paper_autopilot.db "PRAGMA journal_mode;"
# Should return: wal
```

### Problem: Missing Tables

**Symptoms**:
```
sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) no such table: documents
```

**Solution**:
```python
# Create tables programmatically
from src.database import DatabaseManager

db = DatabaseManager()
db.create_tables()
print("✅ Tables created")
```

Or use Alembic:
```bash
# Run migrations
alembic upgrade head

# Verify
sqlite3 paper_autopilot.db ".tables"
# Should show: alembic_version  documents
```

### Problem: Duplicate SHA-256 Hash

**Symptoms**:
```
sqlalchemy.exc.IntegrityError: (sqlite3.IntegrityError) UNIQUE constraint failed: documents.sha256_hex
```

**Cause**: Attempting to insert document that already exists

**Solution**:
```python
# Enable skip_duplicates
result = process_document(
    file_path=Path("invoice.pdf"),
    db_manager=db_manager,
    api_client=api_client,
    vector_manager=vector_manager,
    skip_duplicates=True  # ✅ Skip duplicates
)

if result.duplicate_of:
    print(f"Duplicate of document ID {result.duplicate_of}")
```

### Problem: Connection Pool Exhausted

**Symptoms**:
```
sqlalchemy.exc.TimeoutError: QueuePool limit of size 5 overflow 10 reached
```

**Cause**: Too many concurrent connections

**Solution**:
```bash
# Increase pool size in .env
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=20

# Restart application
python process_inbox.py
```

---

## API Client Errors

### Problem: Rate Limit Exceeded

**Symptoms**:
```
openai.RateLimitError: Error code: 429 - Rate limit exceeded
```

**Solution**: Retry logic is automatic, but if persistent:
```bash
# Check rate limit tier in OpenAI dashboard
# https://platform.openai.com/settings/organization/limits

# Reduce batch size
python process_inbox.py --batch-size 1

# Or wait for rate limit reset (typically 1 minute)
```

### Problem: API Timeout

**Symptoms**:
```
openai.APITimeoutError: Request timed out after 300.0 seconds
```

**Solution**:
```bash
# Increase timeout in .env
OPENAI_TIMEOUT_SECONDS=600  # 10 minutes

# For large PDFs, increase further
OPENAI_TIMEOUT_SECONDS=900  # 15 minutes
```

### Problem: Invalid API Key

**Symptoms**:
```
openai.AuthenticationError: Error code: 401 - Incorrect API key provided
```

**Solution**:
```bash
# Verify API key format
echo $OPENAI_API_KEY  # Should start with sk-

# Test API key directly
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY" | jq .

# If invalid, generate new key:
# https://platform.openai.com/api-keys

# Update .env
OPENAI_API_KEY=sk-new-key-here
```

### Problem: Circuit Breaker Open

**Symptoms**:
```
CircuitBreakerError: Circuit breaker is open after 5 consecutive failures
```

**Cause**: Too many consecutive API failures

**Solution**:
```python
# Check circuit breaker status
from src.api_client import ResponsesAPIClient

client = ResponsesAPIClient()
status = client.get_circuit_breaker_status()
print(status)
# {'state': 'open', 'failure_count': 5, 'last_failure_time': '...'}

# Wait for cooldown (default: 60 seconds)
import time
time.sleep(60)

# Circuit breaker auto-resets to half-open, then closed if next call succeeds
```

### Problem: Model Not Found

**Symptoms**:
```
openai.NotFoundError: Error code: 404 - The model 'gpt-5-pro' does not exist
```

**Solution**:
```bash
# Check model availability in OpenAI dashboard
# https://platform.openai.com/docs/models

# Use available model
export OPENAI_MODEL=gpt-5-mini  # Most widely available

# Or check model access:
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY" | jq '.data[].id'
```

---

## Processing Pipeline Failures

### Problem: PDF Encoding Fails

**Symptoms**:
```
FileNotFoundError: [Errno 2] No such file or directory: 'inbox/invoice.pdf'
```

**Solution**:
```bash
# Verify file exists
ls -lh inbox/invoice.pdf

# Check file permissions
chmod 644 inbox/invoice.pdf

# Verify it's a valid PDF
file inbox/invoice.pdf
# Should output: PDF document, version 1.4
```

### Problem: JSON Schema Validation Failed

**Symptoms**:
```
WARNING: Schema validation failed: {'doc_type': ["'UnknownType' is not one of ['Invoice', 'Receipt', ...]"]}
```

**Cause**: API returned invalid value not in enum

**Solution**: This is a **non-fatal warning** - processing continues

```python
# Document is still saved to database
# Review raw response to see what model returned
from src.database import DatabaseManager

with db.get_session() as session:
    doc = session.query(Document).filter_by(id=123).first()
    print(doc.raw_response_json)  # Full API response
```

### Problem: Processing Stuck in Loop

**Symptoms**:
```
INFO: Processing document: invoice.pdf
INFO: Processing document: invoice.pdf
INFO: Processing document: invoice.pdf
...
```

**Cause**: File not being moved after processing

**Solution**:
```bash
# Check processed/ and failed/ directories exist
mkdir -p processed failed

# Check permissions
chmod 755 processed failed

# Verify file ownership
ls -l inbox/invoice.pdf

# If stuck, manually move file
mv inbox/invoice.pdf processed/
```

### Problem: Large PDF Fails

**Symptoms**:
```
openai.BadRequestError: Error code: 400 - Request payload too large
```

**Cause**: PDF exceeds 10MB per file limit

**Solution**:
```bash
# Check file size
ls -lh invoice.pdf
# -rw-r--r--  1 user  staff   15M Oct 16 12:00 invoice.pdf

# Split PDF or compress
# Use external tools to reduce size

# Or skip file
mv inbox/large.pdf failed/
```

---

## Vector Store Issues

### Problem: Vector Store Upload Failed

**Symptoms**:
```
ERROR: Vector store upload failed: Error uploading file to vector store
```

**Cause**: Network issues, API errors, or invalid file

**Solution**: This is **non-fatal** - document is still saved to database

```python
# Retry manually
from src.vector_store import VectorStoreManager
from src.database import DatabaseManager
from src.dedupe import build_vector_store_attributes

db = DatabaseManager()
manager = VectorStoreManager()

with db.get_session() as session:
    # Find documents without vector store file ID
    docs = session.query(Document).filter(
        Document.vector_store_file_id.is_(None)
    ).all()

    for doc in docs:
        try:
            attrs = build_vector_store_attributes(doc)
            file_id = manager.add_file_to_vector_store(
                Path(f"processed/{doc.original_filename}"),
                metadata=attrs
            )
            doc.vector_store_file_id = file_id
            session.commit()
            print(f"✅ Uploaded {doc.id}")
        except Exception as e:
            print(f"❌ Failed {doc.id}: {e}")
```

### Problem: Vector Store ID Lost

**Symptoms**:
```
WARNING: Vector store file not found, creating new vector store
```

**Cause**: `.vector_store_id` file deleted

**Solution**:
```bash
# Check if file exists
ls -la .vector_store_id

# If missing, new vector store will be created automatically
# Previous files are not lost - they remain in old vector store

# To recover old vector store ID:
# 1. Check OpenAI dashboard for vector store name
# 2. Manually create .vector_store_id file
echo "vs-abc123..." > .vector_store_id
```

### Problem: Too Many Metadata Attributes

**Symptoms**:
```
ValueError: Metadata has 20 attributes, max 16 allowed
```

**Cause**: Attempting to add > 16 metadata attributes to vector store file

**Solution**:
```python
# Limit attributes in build_vector_store_attributes()
# Keep only essential fields:
# - sha256_hex (deduplication)
# - doc_type (classification)
# - issuer (search)
# - primary_date (filtering)
# - document_id (linking)

# Max 16 total attributes per OpenAI API limit
```

---

## Performance Problems

### Problem: Slow Processing

**Symptoms**: Documents take > 30 seconds to process

**Diagnosis**:
```bash
# Check processing times in logs
cat logs/paper_autopilot.log | jq -s 'map(select(.processing_time)) | map(.processing_time) | sort | reverse | .[0:10]'

# Check API response times
cat logs/paper_autopilot.log | jq -s 'map(select(.duration_ms)) | map(.duration_ms) | add / length'
```

**Solutions**:

1. **Increase API Timeout**:
```bash
export OPENAI_TIMEOUT_SECONDS=600  # 10 minutes
```

2. **Check Network Latency**:
```bash
# Test API connectivity
time curl -o /dev/null -s -w "Time: %{time_total}s\n" https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

3. **Optimize Database**:
```bash
# SQLite optimization
sqlite3 paper_autopilot.db "ANALYZE;"
sqlite3 paper_autopilot.db "VACUUM;"

# PostgreSQL optimization
psql -d paper_autopilot -c "ANALYZE documents;"
psql -d paper_autopilot -c "VACUUM ANALYZE documents;"
```

4. **Check Vector Store Performance**:
```bash
# Monitor vector store upload time
cat logs/paper_autopilot.log | grep "vector store" | jq .duration_ms
```

### Problem: High Memory Usage

**Symptoms**: Process using > 2GB RAM

**Diagnosis**:
```bash
# Monitor memory during processing
ps aux | grep python

# Check for memory leaks
# Run with single file and monitor
python -m src.processor inbox/sample.pdf &
PID=$!
while kill -0 $PID 2>/dev/null; do
    ps -p $PID -o rss= | awk '{print $1/1024 " MB"}'
    sleep 1
done
```

**Solutions**:

1. **Process in Batches**:
```bash
# Reduce batch size
python process_inbox.py --batch-size 1
```

2. **Clear Completed Sessions**:
```bash
# Database connection pooling
# Increase pool recycle time
export DB_POOL_RECYCLE=3600  # 1 hour
```

---

## Cost & Token Tracking

### Problem: High API Costs

**Symptoms**: Monthly cost exceeding budget

**Diagnosis**:
```bash
# Identify expensive documents
python -c "from src.database import DatabaseManager; \
    from src.models import Document; \
    db = DatabaseManager(); \
    with db.get_session() as session: \
        docs = session.query(Document).order_by(Document.total_cost_usd.desc()).limit(10).all(); \
        for doc in docs: \
            print(f'{doc.original_filename}: \${doc.total_cost_usd:.4f} ({doc.prompt_tokens} tokens)')"

# Total cost by date
python -c "from src.database import DatabaseManager; \
    from src.models import Document; \
    from datetime import datetime, timedelta; \
    db = DatabaseManager(); \
    with db.get_session() as session: \
        start = datetime.now() - timedelta(days=7); \
        docs = session.query(Document).filter(Document.processed_at >= start).all(); \
        total = sum(doc.total_cost_usd or 0 for doc in docs); \
        print(f'Last 7 days: \${total:.2f}')"
```

**Solutions**:

1. **Review Prompt Caching**:
```bash
# Check cache hit rate
cat logs/paper_autopilot.log | jq -s 'map(select(.cached_tokens)) | \
    {total_prompt: map(.prompt_tokens) | add, \
     total_cached: map(.cached_tokens) | add} | \
    "Cache rate: \((.total_cached / .total_prompt * 100) | round)%"'

# Target > 90% cache hit rate
```

2. **Switch to Smaller Model**:
```bash
# Use nano model for simple documents
export OPENAI_MODEL=gpt-5-nano  # 10x cheaper
```

3. **Optimize Prompts**:
```python
# Reduce developer prompt size (currently ~2000 tokens)
# Keep it stable for caching but minimize unnecessary instructions
```

### Problem: Token Count Mismatch

**Symptoms**: Estimated tokens != actual tokens from API

**Diagnosis**:
```bash
# Compare estimated vs actual
cat logs/paper_autopilot.log | jq -s 'map(select(.prompt_tokens)) | \
    {estimated: map(.estimated_tokens // 0) | add, \
     actual: map(.prompt_tokens) | add} | \
    "Estimated: \(.estimated), Actual: \(.actual), Diff: \((.actual - .estimated) / .actual * 100 | round)%"'
```

**Cause**: tiktoken estimation vs API actual count

**Solution**: Use API's `usage` field as authoritative source
```python
# Always use actual usage from API response
usage = api_client.extract_usage(response)
doc.prompt_tokens = usage["prompt_tokens"]  # Authoritative
doc.cached_tokens = usage["cached_tokens"]
```

---

## Logging & Debugging

### Problem: Missing Logs

**Symptoms**: `logs/paper_autopilot.log` file doesn't exist

**Solution**:
```bash
# Create logs directory
mkdir -p logs

# Verify log file path in config
python -c "from src.config import get_config; print(get_config().log_file)"

# Check permissions
chmod 755 logs
```

### Problem: Log File Too Large

**Symptoms**: Log file > 100MB

**Solution**:
```bash
# Check log file size
du -h logs/paper_autopilot.log

# Rotate logs manually
mv logs/paper_autopilot.log logs/paper_autopilot.log.$(date +%Y%m%d)
gzip logs/paper_autopilot.log.*

# Or configure automatic rotation
# (Already enabled in logging_config.py with 10MB max, 5 backups)
```

### Problem: Can't Parse JSON Logs

**Symptoms**: Logs are plain text, not JSON

**Solution**:
```bash
# Set log format to JSON in .env
LOG_FORMAT=json

# Verify
python -c "from src.config import get_config; print(get_config().log_format)"

# Restart application
python process_inbox.py
```

### Problem: Missing Correlation IDs

**Symptoms**: Logs don't have correlation_id field

**Solution**:
```python
# Ensure correlation ID is generated
from src.logging_config import get_correlation_id

correlation_id = get_correlation_id()
logger.info("Processing started", extra={"correlation_id": correlation_id})

# Use same correlation_id throughout request lifecycle
```

---

## Common Error Messages

### `ModuleNotFoundError: No module named 'src'`

**Cause**: Not running from project root directory

**Solution**:
```bash
# Navigate to project root
cd /path/to/autoD

# Verify
ls src/  # Should show: config.py, models.py, etc.

# Run from root
python -m src.processor
```

### `ImportError: cannot import name 'Document' from 'src.models'`

**Cause**: Import order issue or circular dependency

**Solution**:
```python
# ❌ WRONG: Importing from processor in models
from src.processor import ProcessingResult  # Circular!

# ✅ CORRECT: Models should have no dependencies on processor
# Use proper import hierarchy (see API_DOCS.md)
```

### `TypeError: 'NoneType' object is not iterable`

**Cause**: Trying to iterate over None value

**Solution**:
```python
# Add None checks
docs = session.query(Document).all() or []
for doc in docs:  # Safe even if None
    print(doc.id)
```

### `KeyError: 'output'`

**Cause**: API response missing expected fields

**Solution**:
```python
# Check response structure
print(json.dumps(response, indent=2))

# Use safe extraction
output = response.get("output", [])
if not output:
    raise ValueError("Empty API response")
```

---

## Debug Checklist

When troubleshooting any issue, run through this checklist:

**Environment**:
- [ ] Python version 3.11+ (`python --version`)
- [ ] All dependencies installed (`pip list | grep openai`)
- [ ] Environment variables set (`env | grep OPENAI`)
- [ ] .env file exists and valid

**Configuration**:
- [ ] API key valid and active
- [ ] Model name in allowed list
- [ ] Database URL correct
- [ ] Log level appropriate (DEBUG for troubleshooting)

**Database**:
- [ ] Tables exist (`alembic upgrade head`)
- [ ] Database connectable (`db.health_check()`)
- [ ] Sufficient disk space (> 2GB)

**Files**:
- [ ] Directories exist (inbox/, processed/, failed/, logs/)
- [ ] Permissions correct (755 for directories, 644 for files)
- [ ] PDF files valid (`file *.pdf`)

**Logs**:
- [ ] Logs being written (`tail -f logs/paper_autopilot.log`)
- [ ] No errors in recent logs (`grep ERROR logs/paper_autopilot.log`)
- [ ] Correlation IDs present (for request tracing)

**API**:
- [ ] API connectivity (`curl https://api.openai.com/v1/models`)
- [ ] Rate limits not exceeded
- [ ] Circuit breaker not open
- [ ] Timeout sufficient for PDF size

---

## Getting Help

If you're still stuck after trying the solutions above:

1. **Check Logs**:
```bash
# Show last 50 error lines
cat logs/paper_autopilot.log | jq 'select(.level == "ERROR")' | tail -50
```

2. **Collect Diagnostics**:
```bash
# Create diagnostic report
python -m src.processor --dry-run > diagnostics.txt 2>&1
```

3. **Search Documentation**:
- `docs/RUNBOOK.md` - Production operations
- `docs/PROCESSOR_GUIDE.md` - Processing pipeline
- `docs/CODE_ARCHITECTURE.md` - Architecture patterns

4. **Check GitHub Issues**:
```bash
# Search existing issues
# https://github.com/your-repo/issues?q=is%3Aissue+error-message
```

5. **Create Support Request**:
Include:
- Error message (full stack trace)
- Configuration (sanitize API keys!)
- Diagnostic output
- Steps to reproduce

---

*Last Updated: 2025-10-16*
*Status: Living document - report issues via GitHub*
*Maintained By: Platform Engineering Team*
