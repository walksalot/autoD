# Processor Module Guide

## Overview

The `src/processor.py` module is the main orchestration layer for Paper Autopilot. It integrates all foundation phases (0-8) into a cohesive document processing pipeline.

## Architecture

### Pipeline Steps (9-Step Process)

```
┌─────────────────────────────────────────────────────────────┐
│                    process_document()                        │
│                                                               │
│  1. Hash Computation (SHA-256)                                │
│  2. Duplicate Detection (check database)                      │
│  3. PDF Encoding (base64 data URI)                            │
│  4. API Payload Construction (prompts)                        │
│  5. OpenAI API Call (Responses API)                           │
│  6. Response Parsing (extract text & usage)                   │
│  7. JSON Validation (schema validation)                       │
│  8. Database Storage (Document model)                         │
│  9. Vector Store Upload (OpenAI File Search)                  │
│                                                               │
│  Result: ProcessingResult with status and metadata            │
└─────────────────────────────────────────────────────────────┘
```

## Key Components

### ProcessingResult Class

Container for processing results with structured return values:

```python
result = ProcessingResult(
    success=bool,              # True if processing succeeded
    document_id=int,           # Database ID (if success)
    error=str,                 # Error message (if failed)
    duplicate_of=int,          # Original doc ID (if duplicate)
    cost_usd=float,            # API cost in USD
    processing_time_seconds=float  # Total time
)
```

### encode_pdf_to_base64()

Converts PDF file to base64 data URI for API submission:

```python
pdf_base64 = encode_pdf_to_base64(Path("invoice.pdf"))
# Returns: "data:application/pdf;base64,JVBERi0xLjQ..."
```

### process_document()

Main single-document processing function:

```python
from src.processor import process_document
from src.database import DatabaseManager
from src.api_client import ResponsesAPIClient
from src.vector_store import VectorStoreManager
from pathlib import Path

# Initialize managers
db_manager = DatabaseManager("sqlite:///paper_autopilot.db")
api_client = ResponsesAPIClient()
vector_manager = VectorStoreManager()

# Process document
result = process_document(
    file_path=Path("inbox/invoice.pdf"),
    db_manager=db_manager,
    api_client=api_client,
    vector_manager=vector_manager,
    skip_duplicates=True,
)

if result.success:
    if result.duplicate_of:
        print(f"Duplicate of document {result.duplicate_of}")
    else:
        print(f"Document ID: {result.document_id}")
        print(f"Cost: ${result.cost_usd:.4f}")
        print(f"Time: {result.processing_time_seconds:.2f}s")
else:
    print(f"Error: {result.error}")
```

### process_inbox()

Batch processing function for multiple PDFs:

```python
from src.processor import process_inbox
from pathlib import Path

# Process all PDFs in inbox
results = process_inbox(
    inbox_dir=Path("inbox"),
    processed_dir=Path("processed"),
    failed_dir=Path("failed"),
    batch_size=10,
    skip_duplicates=True,
)

print(f"Processed: {results['processed']}")
print(f"Duplicates: {results['duplicates']}")
print(f"Failed: {results['failed']}")
print(f"Total cost: ${results['total_cost']:.4f}")
print(f"Avg time: {results['avg_processing_time']:.2f}s")
```

## Error Handling

### Duplicate Detection

When a duplicate is detected (same SHA-256 hash):

```python
result = process_document(...)
if result.success and result.duplicate_of:
    print(f"Duplicate of document ID {result.duplicate_of}")
    # File is still moved to processed/ directory
```

### API Errors

API errors are caught and returned in ProcessingResult:

```python
result = process_document(...)
if not result.success:
    print(f"Error: {result.error}")
    # File is moved to failed/ directory
```

### Schema Validation Errors

Schema validation errors are logged as warnings but don't fail processing:

```python
# Invalid schema logs warning:
# "Schema validation failed: {'field': ['error message']}"
# Processing continues, document saved to database
```

### Vector Store Errors

Vector store upload errors are non-fatal:

```python
# Vector store error logs:
# "Vector store upload failed: <error>"
# Document is still saved to database
# Processing continues
```

## File Lifecycle

### Directory Structure

```
project/
├── inbox/           # Unprocessed PDFs (input)
├── processed/       # Successfully processed PDFs
├── failed/          # PDFs that failed processing
└── logs/            # Application logs
```

### File Movement

1. **Success (non-duplicate):**
   - Process document → Save to database → Upload to vector store → Move to `processed/`

2. **Success (duplicate):**
   - Detect duplicate → Skip processing → Move to `processed/`

3. **Failure:**
   - Attempt processing → Error occurs → Move to `failed/`

### Atomic Operations

File moves use `Path.rename()` which is atomic:

```python
# Original file
inbox/invoice.pdf

# After successful processing
processed/invoice.pdf

# After failed processing
failed/invoice.pdf
```

## Observability

### Structured Logging

All operations are logged with structured fields:

```json
{
  "timestamp": "2025-10-16T20:45:00Z",
  "level": "INFO",
  "logger": "paper_autopilot",
  "message": "Processing document: invoice.pdf",
  "correlation_id": "abc123",
  "filename": "invoice.pdf"
}
```

### Correlation IDs

Each processing run gets a unique correlation ID for tracing:

```python
correlation_id = get_correlation_id()
logger.info("Processing started", extra={"correlation_id": correlation_id})
```

### Cost Tracking

Per-document cost tracking with alerts:

```python
cost_data = calculate_cost(
    prompt_tokens=usage["prompt_tokens"],
    completion_tokens=usage["completion_tokens"],
    cached_tokens=usage["cached_tokens"],
    model="gpt-5-mini",
)

logger.info(format_cost_report(cost_data))
# Logs: "Cost breakdown: $0.0123 (prompt: $0.0050, completion: $0.0060, cached: $0.0013)"
```

### Processing Statistics

Batch processing provides comprehensive statistics:

```python
{
  "total_files": 10,
  "processed": 8,
  "duplicates": 1,
  "failed": 1,
  "total_cost": 0.0987,
  "avg_processing_time": 4.23,
  "processing_times": [3.2, 4.5, 5.1, ...]
}
```

## Integration Points

### Configuration

```python
from src.config import get_config

config = get_config()
# Access: config.openai_model, config.paper_autopilot_db_url, etc.
```

### Database

```python
from src.database import DatabaseManager

db_manager = DatabaseManager(config.paper_autopilot_db_url)
db_manager.create_tables()  # Ensure schema exists

with db_manager.get_session() as session:
    # Use session for queries
    pass
```

### API Client

```python
from src.api_client import ResponsesAPIClient

api_client = ResponsesAPIClient()
response = api_client.create_response(payload)
```

### Vector Store

```python
from src.vector_store import VectorStoreManager

vector_manager = VectorStoreManager()
file_id = vector_manager.add_file_to_vector_store(file_path, metadata)
```

### Deduplication

```python
from src.dedupe import deduplicate_and_hash

hex_hash, b64_hash, duplicate = deduplicate_and_hash(file_path, session)
```

### Schema Validation

```python
from src.schema import validate_response

is_valid, errors = validate_response(metadata)
```

### Prompts

```python
from src.prompts import build_responses_api_payload

payload = build_responses_api_payload(
    filename="invoice.pdf",
    pdf_base64=pdf_base64,
    page_count=5,
)
```

### Token Counter

```python
from src.token_counter import calculate_cost, check_cost_alerts

cost_data = calculate_cost(prompt_tokens, completion_tokens, cached_tokens, model)
alert = check_cost_alerts(cost_data["total_cost"])
```

## CLI Usage

See CLI documentation in main README, but key commands:

```bash
# Process inbox
python3 process_inbox.py

# Process single file
python3 process_inbox.py --file invoice.pdf

# Dry run (validate config)
python3 process_inbox.py --dry-run

# Custom batch size
python3 process_inbox.py --batch-size 5

# Process duplicates
python3 process_inbox.py --no-skip-duplicates
```

## Testing

### Module Import Test

```bash
python3 -c "from src.processor import ProcessingResult; print('OK')"
```

### ProcessingResult Test

```python
from src.processor import ProcessingResult

result = ProcessingResult(
    success=True,
    document_id=123,
    cost_usd=0.05,
    processing_time_seconds=3.2,
)

assert result.success == True
assert result.document_id == 123
```

### Empty Inbox Test

```bash
python3 process_inbox.py --batch-size 1
# Should handle gracefully with zero files
```

## Performance Considerations

### Sequential Processing

Current implementation processes files sequentially:

```python
for pdf_file in pdf_files[:batch_size]:
    result = process_document(...)
    # Process one at a time
```

**Future enhancement:** Parallel processing with `asyncio` or `multiprocessing`.

### Memory Management

Files are processed one at a time to manage memory:

```python
# Only one PDF in memory at a time
pdf_base64 = encode_pdf_to_base64(file_path)
response = api_client.create_response(payload)
# PDF data released after processing
```

### API Client Reuse

API client session is reused across batch:

```python
api_client = ResponsesAPIClient()  # Single session
for pdf_file in pdf_files:
    response = api_client.create_response(...)  # Reuse session
```

## Security Considerations

### API Key Handling

API keys managed via environment variables:

```bash
export OPENAI_API_KEY=sk-...
```

### File Path Validation

All file paths use `pathlib.Path` for safety:

```python
file_path = Path("inbox/invoice.pdf")
# Prevents directory traversal attacks
```

### SQL Injection Protection

SQLAlchemy ORM prevents SQL injection:

```python
doc = Document(sha256_hex=hex_hash, ...)
session.add(doc)
# Parameters properly escaped
```

### Error Message Safety

Error messages don't expose sensitive data:

```python
except Exception as e:
    return ProcessingResult(success=False, error=str(e))
    # Generic error, no API keys or internal details
```

## Troubleshooting

### Common Issues

#### "No PDF files found in inbox"

**Solution:** Add PDF files to the `inbox/` directory.

#### "Configuration error: Missing required field"

**Solution:** Check `.env` file has all required fields (see `.env.example`).

#### "API error: 401 Unauthorized"

**Solution:** Verify `OPENAI_API_KEY` environment variable is set.

#### "Vector store upload failed"

**Solution:** Non-fatal error. Document still saved to database. Check vector store ID in config.

#### "Schema validation failed"

**Solution:** Warning only. Document still processed. Check schema in `src/schema.py`.

### Debug Logging

Enable debug logging:

```bash
export PAPER_AUTOPILOT_LOG_LEVEL=DEBUG
python3 process_inbox.py
```

### Check Processing Logs

```bash
tail -f logs/paper_autopilot.log
```

## Next Steps

1. **Add Unit Tests:** Test individual functions in `tests/test_processor.py`
2. **Add Integration Tests:** Test full pipeline with sample PDFs
3. **Add Performance Benchmarks:** Measure processing time and cost
4. **Consider Parallelization:** Add async processing for production scale
5. **Add Retry Logic:** Retry failed documents automatically
6. **Add Progress Bar:** Show progress for large batches

## References

- [Configuration Guide](../src/README_CONFIG.md)
- [Database Schema](./DATABASE_SCHEMA.md)
- [API Client](./API_CLIENT.md)
- [Vector Store](./VECTOR_STORE.md)
- [Token Counter](./TOKEN_COUNTER.md)
