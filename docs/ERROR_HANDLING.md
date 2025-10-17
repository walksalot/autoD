# Error Handling Standardization

## Overview

autoD uses **two standardized error handling patterns** across all API calls and database operations:

1. **Retry Logic** (`src/retry_logic.py`) - Automatic retry for transient errors
2. **Compensating Transactions** (`src/transactions.py`) - Rollback external resources on database failures

These patterns consolidate 6 previous error handling approaches into a unified, testable system.

---

## 1. Retry Logic

### When to Use

Use the `@retry` decorator for **any external API call** (OpenAI Responses API, Files API, Vector Store operations).

### What Gets Retried

**Transient Errors** (automatically retried up to 5 times):
- `RateLimitError` (429) - Rate limit exceeded
- `APIConnectionError` - Network connectivity issues
- `Timeout` - Request timed out
- `APIError` with 5xx status - Server-side errors (500, 502, 503, 504)

**Non-Retryable Errors** (fail fast):
- `AuthenticationError` (401) - Invalid API key
- `PermissionDeniedError` (403) - Insufficient permissions
- `BadRequestError` (400) - Malformed request
- `Not FoundError` (404) - Resource doesn't exist

### Retry Schedule

- **Attempt 1**: Immediate
- **Attempt 2**: Wait 2 seconds
- **Attempt 3**: Wait 4 seconds
- **Attempt 4**: Wait 8 seconds
- **Attempt 5**: Wait 16 seconds (final attempt)

**Total max wait**: ~30 seconds across all retries

### Usage Examples

#### Basic API Call

```python
from src.retry_logic import retry
from openai import OpenAI

client = OpenAI(api_key="sk-...")

@retry(max_attempts=5, initial_wait=2.0, max_wait=60.0)
def upload_file_to_openai(file_path):
    with open(file_path, "rb") as f:
        return client.files.create(file=f, purpose="assistants")

# Automatically retries on rate limits, timeouts, connection errors
file_obj = upload_file_to_openai("document.pdf")
```

#### Pipeline Stage with Retry

```python
from src.pipeline import ProcessingStage, ProcessingContext
from src.retry_logic import retry

class UploadToFilesAPIStage(ProcessingStage):
    @retry(max_attempts=5, initial_wait=2.0, max_wait=60.0)
    def execute(self, context: ProcessingContext) -> ProcessingContext:
        # This method will automatically retry on transient failures
        response = self.client.files.create(
            file=(context.pdf_path.name, context.pdf_bytes, "application/pdf"),
            purpose="user_data",
        )
        context.file_id = response.id
        return context
```

#### Custom Retry Configuration

```python
from src.retry_logic import retry

# Faster retries for less critical operations
@retry(max_attempts=3, initial_wait=1.0, max_wait=30.0)
def fetch_lightweight_data():
    return client.some_api_call()

# Slower retries for heavy operations
@retry(max_attempts=5, initial_wait=4.0, max_wait=120.0)
def process_large_file():
    return client.heavy_operation()
```

---

## 2. Compensating Transactions

### When to Use

Use `compensating_transaction` when:
1. You make **external API calls** (file uploads, vector store operations)
2. Then **commit to database**
3. Need to **cleanup external resources** if database commit fails

### The Problem

Without compensating transactions:
```python
# BAD: Orphaned file if database commit fails
file_obj = client.files.create(file=f, purpose="assistants")  # ✅ Succeeds
doc = Document(file_id=file_obj.id)
session.add(doc)
session.commit()  # ❌ Fails → file_obj orphaned in OpenAI Files API!
```

### The Solution

With compensating transactions:
```python
from src.transactions import compensating_transaction
from src.cleanup_handlers import cleanup_files_api_upload

def cleanup():
    cleanup_files_api_upload(client, file_obj.id)

with compensating_transaction(session, compensate_fn=cleanup):
    file_obj = client.files.create(file=f, purpose="assistants")  # ✅ Succeeds
    doc = Document(file_id=file_obj.id)
    session.add(doc)
    # Commit happens in context manager
    # If commit fails → cleanup() runs → file deleted from OpenAI
```

### Usage Examples

#### Simple Cleanup (Single Resource)

```python
from src.transactions import compensating_transaction
from src.cleanup_handlers import cleanup_files_api_upload

# Upload file, save to database, cleanup on failure
def process_document(file_path, session, client):
    with open(file_path, "rb") as f:
        file_obj = client.files.create(file=f, purpose="assistants")

    # Define cleanup function
    def cleanup():
        cleanup_files_api_upload(client, file_obj.id)

    # Use compensating transaction
    with compensating_transaction(session, compensate_fn=cleanup):
        doc = Document(
            file_id=file_obj.id,
            filename=file_path.name
        )
        session.add(doc)
        # Commit happens here
        # If it fails, cleanup() deletes the uploaded file

    return doc.id
```

#### Multiple Resources Cleanup

```python
from src.transactions import compensating_transaction
from src.cleanup_handlers import cleanup_files_api_upload, cleanup_vector_store_upload

def process_with_vector_store(file_path, session, client, vector_store_id):
    # Upload file
    with open(file_path, "rb") as f:
        file_obj = client.files.create(file=f, purpose="assistants")

    # Add to vector store
    vs_file = client.beta.vector_stores.files.create(
        vector_store_id=vector_store_id,
        file_id=file_obj.id
    )

    # Define cleanup for both resources (LIFO order)
    def cleanup():
        # Clean vector store first (most recent operation)
        cleanup_vector_store_upload(client, vector_store_id, file_obj.id)
        # Then clean file
        cleanup_files_api_upload(client, file_obj.id)

    # Use compensating transaction
    with compensating_transaction(session, compensate_fn=cleanup):
        doc = Document(
            file_id=file_obj.id,
            vector_store_file_id=vs_file.id
        )
        session.add(doc)
        # If commit fails, both resources cleaned up

    return doc.id
```

#### With Audit Trail

```python
from src.transactions import compensating_transaction
from src.cleanup_handlers import cleanup_files_api_upload

def process_with_audit(file_path, session, client):
    file_obj = client.files.create(...)

    # Create audit trail dict
    audit_trail = {
        "file_path": str(file_path),
        "file_id": file_obj.id,
    }

    def cleanup():
        cleanup_files_api_upload(client, file_obj.id)

    # Pass audit_trail to capture transaction events
    with compensating_transaction(session, cleanup, audit_trail):
        doc = Document(file_id=file_obj.id)
        session.add(doc)

    # Audit trail now contains:
    # {
    #     "file_path": "...",
    #     "file_id": "file-abc123",
    #     "started_at": "2025-10-16T14:30:00Z",
    #     "committed_at": "2025-10-16T14:30:01Z",
    #     "status": "success",
    #     "compensation_needed": False
    # }

    logger.info("Transaction audit", extra=audit_trail)
    return doc.id
```

### Audit Trail Fields

When using `audit_trail` parameter:

**Success Path:**
- `started_at` (ISO timestamp)
- `committed_at` (ISO timestamp)
- `status` ("success")
- `compensation_needed` (False)

**Failure Path:**
- `started_at` (ISO timestamp)
- `rolled_back_at` (ISO timestamp)
- `status` ("failed")
- `error` (error message)
- `error_type` (exception class name)
- `compensation_needed` (True if cleanup_fn provided)
- `compensation_status` ("success" or "failed")
- `compensation_completed_at` (ISO timestamp, if successful)
- `compensation_error` (error message, if failed)
- `compensation_error_type` (exception class name, if failed)

---

## 3. Cleanup Handlers

Pre-built cleanup functions for common external resources.

### Available Handlers

#### `cleanup_files_api_upload(client, file_id)`

Deletes file from OpenAI Files API.

```python
from src.cleanup_handlers import cleanup_files_api_upload
from openai import OpenAI

client = OpenAI(api_key="sk-...")
cleanup_files_api_upload(client, "file-abc123")
# Logs: "Successfully cleaned up Files API upload: file-abc123"
```

#### `cleanup_vector_store_upload(client, vector_store_id, file_id)`

Removes file from OpenAI vector store.

```python
from src.cleanup_handlers import cleanup_vector_store_upload

cleanup_vector_store_upload(client, "vs_abc123", "file-xyz789")
# Logs: "Successfully cleaned up vector store upload: file-xyz789"
```

#### `cleanup_multiple_resources(cleanup_fns)`

Executes multiple cleanup functions in **LIFO order** (reverse).

```python
from src.cleanup_handlers import cleanup_multiple_resources

def cleanup_step1():
    print("Cleanup 1")

def cleanup_step2():
    print("Cleanup 2")

cleanup_multiple_resources([
    ("step1", cleanup_step1),
    ("step2", cleanup_step2),
])
# Executes step2 first (LIFO), then step1
# Output:
#   Cleanup 2
#   Cleanup 1
```

### Creating Custom Cleanup Handlers

```python
import logging
logger = logging.getLogger(__name__)

def cleanup_custom_resource(client, resource_id):
    """
    Custom cleanup handler template.

    Args:
        client: API client instance
        resource_id: ID of resource to cleanup

    Raises:
        Exception: Re-raises to signal cleanup failure
    """
    try:
        logger.info(f"Attempting cleanup: {resource_id}")

        # Perform cleanup operation
        client.custom_api.delete(resource_id)

        logger.info(f"Successfully cleaned up: {resource_id}")

    except Exception as e:
        logger.error(f"Cleanup failed: {e}", exc_info=True)
        raise  # Re-raise to signal failure
```

---

## 4. Pipeline Integration

### Standard Pipeline Stage Pattern

```python
from src.pipeline import ProcessingStage, ProcessingContext
from src.retry_logic import retry
from src.transactions import compensating_transaction
from src.cleanup_handlers import cleanup_files_api_upload

class MyStage(ProcessingStage):
    def __init__(self, session, client):
        self.session = session
        self.client = client

    @retry(max_attempts=5, initial_wait=2.0, max_wait=60.0)
    def execute(self, context: ProcessingContext) -> ProcessingContext:
        # Step 1: External API call (with retry)
        file_obj = self.client.files.create(...)
        context.file_id = file_obj.id

        # Step 2: Database persistence (with compensation)
        def cleanup():
            cleanup_files_api_upload(self.client, context.file_id)

        with compensating_transaction(self.session, cleanup):
            doc = Document(file_id=context.file_id)
            self.session.add(doc)

        context.document_id = doc.id
        return context
```

---

## 5. Testing Error Scenarios

### Testing Retry Logic

```python
from unittest.mock import Mock
from openai import RateLimitError
from src.retry_logic import retry

def test_retries_on_rate_limit(monkeypatch):
    mock_client = Mock()
    mock_response = {"success": True}

    # First 2 calls raise RateLimitError, 3rd succeeds
    mock_client.api_call.side_effect = [
        RateLimitError("rate limit"),
        RateLimitError("rate limit"),
        mock_response,
    ]

    @retry()
    def call_api():
        return mock_client.api_call()

    result = call_api()

    assert result == mock_response
    assert mock_client.api_call.call_count == 3  # Retried twice
```

### Testing Compensating Transactions

```python
from src.transactions import compensating_transaction
from unittest.mock import Mock

def test_compensation_runs_on_db_failure():
    mock_client = Mock()
    mock_session = Mock()
    mock_session.commit.side_effect = Exception("DB error")

    cleanup_called = []

    def cleanup():
        cleanup_called.append(True)
        mock_client.files.delete("file-123")

    with pytest.raises(Exception):
        with compensating_transaction(mock_session, cleanup):
            pass  # Commit fails

    # Verify cleanup ran
    assert len(cleanup_called) == 1
    mock_client.files.delete.assert_called_once_with("file-123")
```

---

## 6. Best Practices

### ✅ DO

- **Use `@retry` for all external API calls**
- **Use `compensating_transaction` for multi-step operations**
- **Define cleanup functions inline** (captures context)
- **Include audit trails** for debugging complex failures
- **Test both success and failure paths**
- **Log cleanup attempts and results**

### ❌ DON'T

- **Don't manually implement retry logic** - use `@retry` decorator
- **Don't commit without cleanup handlers** if external resources created
- **Don't suppress cleanup errors** - they signal incomplete rollback
- **Don't use compensating transactions for read-only operations**
- **Don't retry non-transient errors** (4xx errors are permanent)

---

## 7. Troubleshooting

### Orphaned Files in OpenAI

**Symptom**: Files exist in OpenAI Files API but not in database

**Diagnosis**:
```bash
# List files in OpenAI
curl https://api.openai.com/v1/files \
  -H "Authorization: Bearer $OPENAI_API_KEY"

# Compare with database
SELECT file_id FROM documents;
```

**Prevention**: Always use `compensating_transaction` when uploading files

### Retry Exhaustion

**Symptom**: All 5 retry attempts fail

**Diagnosis**: Check logs for error type
```python
# In logs:
"Retryable error: RateLimitError"  # Transient - expected
"API error 401: retryable=False"    # Permanent - check API key
```

**Solution**:
- **Transient errors (5xx, rate limits)**: Wait and retry manually
- **Permanent errors (4xx)**: Fix root cause (API key, request format)

### Compensation Failures

**Symptom**: Database rollback succeeded but cleanup failed

**Diagnosis**: Check audit trail
```python
audit_trail = {
    "status": "failed",
    "compensation_status": "failed",
    "compensation_error": "file not found"
}
```

**Solution**: Manual cleanup required - use cleanup handlers directly:
```python
from src.cleanup_handlers import cleanup_files_api_upload
cleanup_files_api_upload(client, orphaned_file_id)
```

---

## 8. Migration Checklist

When adding error handling to existing code:

- [ ] Replace manual retry loops with `@retry` decorator
- [ ] Import from `src.retry_logic`, not inline `tenacity` usage
- [ ] Wrap database commits in `compensating_transaction`
- [ ] Define cleanup handlers for all external resources
- [ ] Add audit trail for debugging
- [ ] Write tests for retry behavior
- [ ] Write tests for compensation behavior
- [ ] Update documentation

---

## References

- `src/retry_logic.py` - Retry decorator implementation
- `src/transactions.py` - Compensating transaction pattern
- `src/cleanup_handlers.py` - Pre-built cleanup functions
- `tests/unit/test_retry_logic.py` - Retry test examples
- `tests/unit/test_transactions.py` - Transaction test examples
- `tests/unit/test_cleanup_handlers.py` - Cleanup test examples
