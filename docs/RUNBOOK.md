# Production Runbook — autoD

**Purpose**: Operations guide for running autoD in production
**Audience**: DevOps engineers, system administrators, on-call engineers
**Last Updated**: 2025-10-16

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [System Health Checks](#system-health-checks)
3. [Monitoring](#monitoring)
4. [Troubleshooting](#troubleshooting)
5. [Backup & Recovery](#backup--recovery)
6. [Performance Tuning](#performance-tuning)
7. [Security](#security)
8. [Incident Response](#incident-response)

---

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 14+ (production) or SQLite (development)
- OpenAI API key with Responses API access
- 2GB RAM minimum, 4GB recommended
- 10GB disk space for database and logs

### Initial Deployment

```bash
# 1. Clone repository
git clone <repository-url>
cd autoD

# 2. Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set environment variables
cp .env.example .env
# Edit .env with production values

# 5. Run database migrations
alembic upgrade head

# 6. Verify configuration
python3 -c "from src.config import get_config; config = get_config(); print('✅ Config OK')"

# 7. Create required directories
mkdir -p inbox processed failed logs

# 8. Test with single PDF
python3 -m src.processor --file test.pdf

# 9. Start the daemon (automatic processing)
python3 run_daemon.py
```

**Note**: Paper Autopilot runs as an automatic daemon that watches for new PDFs. See **[Daemon Mode Setup](./DAEMON_MODE.md)** for complete instructions on macOS LaunchAgent and Linux systemd configuration for automatic startup.

---

## System Health Checks

### Daily Health Check Script

```bash
#!/bin/bash
# Save as: scripts/health_check.sh

set -e

echo "=== autoD Health Check ==="
echo "Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"

# 1. Database connectivity
echo -n "Database: "
python3 -c "from src.database import DatabaseManager; from src.config import get_config; \
    db = DatabaseManager(get_config().paper_autopilot_db_url); \
    print('✅ OK' if db.health_check() else '❌ FAILED')"

# 2. API connectivity
echo -n "OpenAI API: "
python3 -c "from src.api_client import ResponsesAPIClient; \
    client = ResponsesAPIClient(); \
    print('✅ OK')" 2>/dev/null || echo "❌ FAILED"

# 3. Vector store access
echo -n "Vector Store: "
python3 -c "from src.vector_store import VectorStoreManager; \
    vm = VectorStoreManager(); \
    print('✅ OK' if vm.get_or_create_vector_store() else '❌ FAILED')"

# 4. Disk space (require > 2GB free)
FREE_GB=$(df -BG . | tail -1 | awk '{print $4}' | sed 's/G//')
if [ "$FREE_GB" -gt 2 ]; then
    echo "Disk Space: ✅ OK (${FREE_GB}GB free)"
else
    echo "Disk Space: ⚠️  WARNING (${FREE_GB}GB free - recommend > 2GB)"
fi

# 5. Log file size (warn if > 100MB)
if [ -f logs/paper_autopilot.log ]; then
    LOG_SIZE_MB=$(du -m logs/paper_autopilot.log | cut -f1)
    if [ "$LOG_SIZE_MB" -gt 100 ]; then
        echo "Log File: ⚠️  WARNING (${LOG_SIZE_MB}MB - consider rotation)"
    else
        echo "Log File: ✅ OK (${LOG_SIZE_MB}MB)"
    fi
fi

# 6. Recent processing activity
RECENT_DOCS=$(python3 -c "from src.database import DatabaseManager; from src.config import get_config; \
    from datetime import datetime, timedelta; from src.models import Document; \
    db = DatabaseManager(get_config().paper_autopilot_db_url); \
    with db.get_session() as session: \
        count = session.query(Document).filter(Document.processed_at >= datetime.now() - timedelta(hours=24)).count(); \
        print(count)")
echo "Docs (24h): ${RECENT_DOCS} processed"

echo "=== Health Check Complete ==="
```

### Automated Monitoring (Cron Job)

```bash
# Add to crontab: crontab -e
# Run health check every hour, alert on failure
0 * * * * /path/to/autoD/scripts/health_check.sh || mail -s "autoD Health Check Failed" alerts@example.com
```

---

## Monitoring

### Key Metrics to Track

**Processing Metrics**:
- Documents processed per hour/day
- Average processing time per document
- Duplicate detection rate
- Error rate (failed / total)

**Cost Metrics**:
- Total API cost per day/week/month
- Cost per document
- Cached token percentage (target > 90%)
- Token usage trends

**Quality Metrics**:
- Schema validation success rate
- Documents requiring manual review
- Vector store upload success rate

### Log Analysis Commands

```bash
# Total documents processed today
cat logs/paper_autopilot.log | jq -s \
    'map(select(.message == "Processing complete" and .timestamp | startswith("2025-10-16"))) | length'

# Total cost today
cat logs/paper_autopilot.log | jq -s \
    'map(select(.cost_usd)) | map(.cost_usd) | add'

# Average processing time
cat logs/paper_autopilot.log | jq -s \
    'map(select(.processing_time)) | map(.processing_time) | add / length'

# Error count by type
cat logs/paper_autopilot.log | jq -s \
    'map(select(.level == "ERROR")) | group_by(.error) | \
    map({error: .[0].error, count: length}) | sort_by(.count) | reverse'

# Hourly processing volume
cat logs/paper_autopilot.log | jq -r \
    'select(.message | contains("Processing complete")) | .timestamp[:13]' | \
    uniq -c
```

### Cost Tracking

```python
# Get cost summary for date range
from src.database import DatabaseManager
from src.config import get_config
from src.models import Document
from datetime import datetime, timedelta

db = DatabaseManager(get_config().paper_autopilot_db_url)

with db.get_session() as session:
    # Last 7 days
    start_date = datetime.now() - timedelta(days=7)

    docs = session.query(Document).filter(
        Document.processed_at >= start_date
    ).all()

    total_cost = sum(doc.total_cost_usd or 0 for doc in docs)
    total_docs = len(docs)

    print(f"Last 7 days:")
    print(f"  Documents: {total_docs}")
    print(f"  Total cost: ${total_cost:.2f}")
    print(f"  Avg cost/doc: ${total_cost / total_docs:.4f}")
```

---

## Troubleshooting

### Problem: Processing is slow

**Symptoms**: Documents take > 30 seconds to process

**Diagnosis**:
```bash
# Check processing times in logs
cat logs/paper_autopilot.log | jq -s \
    'map(select(.processing_time)) | map(.processing_time) | sort | reverse | .[0:10]'
```

**Solutions**:
1. Check API timeout setting (increase if needed)
2. Verify network latency to OpenAI API
3. Check if large PDFs are causing slowdowns
4. Review database query performance
5. Check vector store upload performance

### Problem: High API costs

**Symptoms**: Monthly cost exceeding budget

**Diagnosis**:
```bash
# Identify expensive documents
python3 -c "from src.database import DatabaseManager; from src.config import get_config; \
    from src.models import Document; \
    db = DatabaseManager(get_config().paper_autopilot_db_url); \
    with db.get_session() as session: \
        docs = session.query(Document).order_by(Document.total_cost_usd.desc()).limit(10).all(); \
        for doc in docs: \
            print(f'{doc.original_filename}: ${doc.total_cost_usd:.4f} ({doc.prompt_tokens} tokens)')"
```

**Solutions**:
1. Review prompt caching percentage (target > 90%)
2. Optimize prompts to reduce token usage
3. Check for duplicate processing
4. Consider model downgrade (gpt-5-mini → gpt-5-nano)
5. Implement batch processing for better cache utilization

### Problem: Duplicate detection not working

**Symptoms**: Same PDF processed multiple times

**Diagnosis**:
```bash
# Find duplicate hashes
python3 -c "from src.database import DatabaseManager; from src.config import get_config; \
    from src.models import Document; from sqlalchemy import func; \
    db = DatabaseManager(get_config().paper_autopilot_db_url); \
    with db.get_session() as session: \
        dupes = session.query(Document.sha256_hex, func.count(Document.id)).group_by(Document.sha256_hex).having(func.count(Document.id) > 1).all(); \
        print(f'Found {len(dupes)} duplicate hashes')"
```

**Solutions**:
1. Verify `skip_duplicates=True` in `process_document()` call
2. Check database index on `sha256_hex` column
3. Verify hash computation is consistent
4. Check for file modifications between scans

### Problem: Vector store upload failures

**Symptoms**: Logs show "Vector store upload failed"

**Diagnosis**:
```bash
# Count vector store failures
cat logs/paper_autopilot.log | jq -s \
    'map(select(.message | contains("Vector store upload failed"))) | length'
```

**Solutions**:
1. Verify OpenAI API key has vector store access
2. Check file size limits (max 10MB per file)
3. Verify network connectivity to OpenAI
4. Review vector store ID in configuration
5. Check OpenAI service status

### Problem: Database connection errors

**Symptoms**: "OperationalError: database is locked" or connection timeouts

**Diagnosis**:
```bash
# Check active database connections (PostgreSQL)
psql -c "SELECT count(*) FROM pg_stat_activity WHERE datname='paper_autopilot';"
```

**Solutions**:
1. **SQLite**: Switch to PostgreSQL for concurrent writes
2. **PostgreSQL**: Increase connection pool size
3. Check for long-running queries
4. Verify database server resources (CPU, RAM, disk)
5. Review database configuration (max_connections)

---

## Backup & Recovery

### Database Backup

**SQLite**:
```bash
#!/bin/bash
# Daily SQLite backup

BACKUP_DIR="/backups/autoD"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DB_FILE="paper_autopilot.db"

mkdir -p "$BACKUP_DIR"

# Create backup
sqlite3 "$DB_FILE" ".backup '$BACKUP_DIR/paper_autopilot_$TIMESTAMP.db'"

# Compress
gzip "$BACKUP_DIR/paper_autopilot_$TIMESTAMP.db"

# Keep last 30 days
find "$BACKUP_DIR" -name "paper_autopilot_*.db.gz" -mtime +30 -delete

echo "Backup complete: paper_autopilot_$TIMESTAMP.db.gz"
```

**PostgreSQL**:
```bash
#!/bin/bash
# Daily PostgreSQL backup

BACKUP_DIR="/backups/autoD"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DB_NAME="paper_autopilot"

mkdir -p "$BACKUP_DIR"

# Create backup
pg_dump "$DB_NAME" | gzip > "$BACKUP_DIR/paper_autopilot_$TIMESTAMP.sql.gz"

# Keep last 30 days
find "$BACKUP_DIR" -name "paper_autopilot_*.sql.gz" -mtime +30 -delete

echo "Backup complete: paper_autopilot_$TIMESTAMP.sql.gz"
```

### Restore from Backup

**SQLite**:
```bash
# Restore from backup
gunzip -c paper_autopilot_20251016.db.gz > paper_autopilot.db
```

**PostgreSQL**:
```bash
# Restore from backup
gunzip -c paper_autopilot_20251016.sql.gz | psql paper_autopilot
```

### Vector Store Backup

Vector store is managed by OpenAI and backed up automatically. To recreate:

```python
from src.vector_store import VectorStoreManager
from src.database import DatabaseManager
from src.config import get_config

# Get all processed documents
db = DatabaseManager(get_config().paper_autopilot_db_url)
with db.get_session() as session:
    docs = session.query(Document).filter(
        Document.vector_store_file_id.isnot(None)
    ).all()

    print(f"Total documents in vector store: {len(docs)}")
```

---

## Performance Tuning

### Database Optimization

**SQLite**:
```sql
-- Analyze tables for query optimization
ANALYZE;

-- Vacuum to reclaim space
VACUUM;

-- Enable Write-Ahead Logging (WAL) mode
PRAGMA journal_mode=WAL;

-- Increase cache size (in KB)
PRAGMA cache_size=-64000;  -- 64MB cache
```

**PostgreSQL**:
```sql
-- Analyze tables
ANALYZE documents;

-- Create additional indexes for common queries
CREATE INDEX IF NOT EXISTS idx_doc_type_processed
    ON documents(doc_type, processed_at);

-- Update statistics
VACUUM ANALYZE documents;
```

### API Performance

**Prompt Caching Optimization**:
- Keep developer prompt identical across all requests
- Target > 90% cache hit rate
- Monitor `cached_tokens` in logs

**Batch Processing**:
```python
# Process multiple files with same API client (reuse connection)
api_client = ResponsesAPIClient()  # Create once

for pdf_file in pdf_files:
    result = process_document(pdf_file, db_manager, api_client, vector_manager)
    # Reuses HTTP connection, better performance
```

### Logging Performance

```python
# Disable debug logging in production
PAPER_AUTOPILOT_LOG_LEVEL=WARNING
```

---

## Security

### API Key Rotation

```bash
# 1. Generate new API key in OpenAI dashboard
# 2. Update .env file
# 3. Restart application
# 4. Verify with health check
# 5. Delete old API key
```

### Database Access Control

**PostgreSQL Production Setup**:
```sql
-- Create read-only user for reporting
CREATE USER autod_readonly WITH PASSWORD 'secure_password';
GRANT CONNECT ON DATABASE paper_autopilot TO autod_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO autod_readonly;

-- Create read-write user for application
CREATE USER autod_app WITH PASSWORD 'secure_password';
GRANT CONNECT ON DATABASE paper_autopilot TO autod_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO autod_app;
```

### Log Sanitization

Ensure logs don't contain sensitive data:
```python
# Config module automatically redacts API keys in logs
# Review logs before sharing:
grep -i "api.*key\|password\|secret" logs/paper_autopilot.log
```

---

## Incident Response

### Severity Levels

**P0 (Critical)**: Complete system outage
**P1 (High)**: Processing failures affecting > 50% of documents
**P2 (Medium)**: Degraded performance or partial failures
**P3 (Low)**: Non-urgent issues, feature requests

### P0: System Down

**Checklist**:
1. Run health check script
2. Check database connectivity
3. Verify OpenAI API status (https://status.openai.com)
4. Review error logs for root cause
5. Restart application if needed
6. Verify recovery with test document
7. Document incident in post-mortem

### P1: High Failure Rate

**Checklist**:
1. Check error rate in logs
2. Identify common error pattern
3. Review recent code changes
4. Check API rate limits
5. Verify database capacity
6. Implement hot fix if needed
7. Monitor recovery

### Communication Template

```
Incident: [Brief description]
Severity: [P0/P1/P2/P3]
Start Time: [UTC timestamp]
Status: [Investigating/Identified/Monitoring/Resolved]
Impact: [Number of affected documents/users]
Root Cause: [Once identified]
Mitigation: [Actions taken]
Next Steps: [Planned actions]
```

---

## On-Call Runbook

### First Responder Actions

1. **Acknowledge alert** (< 5 min)
2. **Assess severity** (P0/P1/P2/P3)
3. **Run health check** script
4. **Check monitoring** dashboards
5. **Review recent logs** (last 1 hour)
6. **Identify root cause**
7. **Implement fix** or escalate
8. **Verify recovery**
9. **Document incident**

### Escalation Path

1. **Primary On-Call** → System Administrator
2. **Secondary On-Call** → Platform Engineer
3. **Escalation** → Engineering Manager

### Common Alerts

| Alert | Severity | Response |
|-------|----------|----------|
| Database down | P0 | Restart database service, verify backups |
| API errors > 50% | P1 | Check OpenAI status, verify API key, review rate limits |
| Disk space < 2GB | P2 | Clean up old logs, rotate backups, increase disk |
| High cost alert | P2 | Review token usage, check for duplicate processing |
| Vector store failures | P3 | Verify vector store ID, check API permissions |

---

## References

- **Daemon Mode Setup**: `docs/DAEMON_MODE.md` (automatic file watching for ScanSnap integration)
- **Code Architecture**: `docs/CODE_ARCHITECTURE.md`
- **Processor Guide**: `docs/PROCESSOR_GUIDE.md`
- **Troubleshooting**: `docs/TROUBLESHOOTING.md`
- **OpenAI Status**: https://status.openai.com

---

**Maintained By**: Platform Engineering Team
**Last Updated**: 2025-10-16
**Next Review**: Monthly
