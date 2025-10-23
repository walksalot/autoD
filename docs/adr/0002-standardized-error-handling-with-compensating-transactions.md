# ADR 0002: Standardized Error Handling with Compensating Transactions

**Date**: 2025-10-16
**Status**: Accepted
**Deciders**: System Architect, Development Team
**Related**: TECHNICAL_DEBT_ANALYSIS.md (Section 1.2), ERROR_HANDLING.md

---

## Context

Prior to this decision, autoD had **6 different error handling patterns** scattered across the codebase:

1. **Manual retry loops** in `vector_store.py` (exponential backoff)
2. **Inline `@retry` decorators** in `api_client.py` (using tenacity directly)
3. **Circuit breaker pattern** in `api_client.py` (custom implementation)
4. **Basic try/catch** in pipeline stages (no retries)
5. **Simple rollback** in database operations (no external resource cleanup)
6. **Ad-hoc error logging** (inconsistent structured logging)

### Problems

1. **Code Duplication**: Retry logic duplicated across modules
2. **Inconsistent Behavior**: Some APIs retry, others don't
3. **Orphaned Resources**: Files uploaded to OpenAI but not in database due to failed commits
4. **Hard to Test**: Inline retry logic difficult to mock and verify
5. **No Audit Trail**: Failures logged but no structured transaction history
6. **Maintenance Burden**: Each new API call required re-implementing retry logic

### Example Orphaned Resource Scenario

```python
# BEFORE (Problem): Orphaned file if database commit fails

# Step 1: Upload file to OpenAI (succeeds)
file_obj = client.files.create(file=pdf_bytes, purpose="assistants")
# ✅ file-abc123 now exists in OpenAI Files API

# Step 2: Save to database (fails)
doc = Document(file_id=file_obj.id)
session.add(doc)
session.commit()  # ❌ IntegrityError: duplicate SHA-256

# Result: file-abc123 orphaned in OpenAI (costs money, clutters storage)
```

---

## Decision

We will standardize on **two core error handling patterns**:

### 1. Retry Logic (`src/retry_logic.py`)

**Single source of truth** for retry behavior across all external API calls.

**Implementation**:
```python
from src.retry_logic import retry

@retry(max_attempts=5, initial_wait=2.0, max_wait=60.0)
def call_external_api():
    return client.api_call()
```

**Retryable Errors**:
- `RateLimitError` (429)
- `APIConnectionError` (network issues)
- `Timeout` (request timeout)
- `APIError` with 5xx status codes

**Non-Retryable Errors** (fail fast):
- 4xx client errors (400, 401, 403, 404)

**Retry Schedule**:
- Attempt 1: Immediate
- Attempt 2: 2 seconds
- Attempt 3: 4 seconds
- Attempt 4: 8 seconds
- Attempt 5: 16 seconds (final)

### 2. Compensating Transactions (`src/transactions.py`)

**Pattern** for rolling back external resources when database commits fail.

**Implementation**:
```python
from src.transactions import compensating_transaction
from src.cleanup_handlers import cleanup_files_api_upload

def cleanup():
    cleanup_files_api_upload(client, file_id)

with compensating_transaction(session, compensate_fn=cleanup):
    # Upload file
    file_obj = client.files.create(...)

    # Save to database
    doc = Document(file_id=file_obj.id)
    session.add(doc)
    # Commit happens here
    # If commit fails → cleanup() deletes the uploaded file
```

**Features**:
- Automatic rollback on database commit failure
- Cleanup functions run in **LIFO order** (most recent first)
- Audit trail captures all transaction events
- Errors logged with structured context

---

## Rationale

### Why Not Other Approaches?

#### Alternative 1: Two-Phase Commit (2PC)

**Rejected** because:
- OpenAI APIs don't support transactions
- Can't rollback file uploads atomically
- Requires distributed transaction coordinator (complex)
- Performance overhead (prepare + commit phases)

#### Alternative 2: Saga Pattern

**Rejected** because:
- Overkill for simple upload → database workflow
- Requires complex choreography/orchestration
- Better suited for multi-service architectures
- Our use case is simpler: single service, single database

#### Alternative 3: Event Sourcing

**Rejected** because:
- Requires event store infrastructure
- Adds complexity for little benefit
- Replay logic difficult to implement with external APIs
- Not needed for current scale (~1000 docs/day)

### Why Compensating Transactions?

**Chosen** because:
1. ✅ **Simple** - Single context manager, easy to understand
2. ✅ **Testable** - Mock cleanup functions, verify they run
3. ✅ **Explicit** - Developer defines cleanup logic inline
4. ✅ **Flexible** - Works with any external API
5. ✅ **Observable** - Audit trail for debugging
6. ✅ **Proven** - Standard pattern in distributed systems

---

## Consequences

### Positive

1. **Consistency**: All API calls use same retry logic
2. **No Orphaned Resources**: Cleanup runs automatically on failure
3. **Testability**: Mock cleanup functions in tests
4. **Observability**: Audit trail for every transaction
5. **Maintainability**: Single source of truth for error handling
6. **Performance**: Retry logic optimized (exponential backoff)

### Negative

1. **Learning Curve**: Developers must learn compensating transaction pattern
2. **Boilerplate**: Every database commit requires cleanup function definition
3. **Cleanup Failures**: If cleanup fails, manual intervention required
4. **Not Atomic**: Small time window where file exists but database doesn't

### Mitigations

| Risk | Mitigation |
|------|-----------|
| Cleanup failure | Log errors, provide manual cleanup tools |
| Forgotten cleanup | Code review checklist, linting rules |
| Audit trail overhead | Async logging, sampling for low-priority operations |
| Retry storm | Circuit breaker pattern (already implemented) |

---

## Implementation

### Phase 1: Consolidate Retry Logic

**Files Modified**:
- `src/api_client.py` - Replace inline retry with `@retry` decorator
- `src/stages/upload_stage.py` - Add `@retry` to file upload
- `src/vector_store.py` - Replace manual retry loop

### Phase 2: Add Compensating Transactions

**Files Created**:
- `src/cleanup_handlers.py` - Pre-built cleanup functions
  - `cleanup_files_api_upload()`
  - `cleanup_vector_store_upload()`
  - `cleanup_multiple_resources()`

**Files Modified**:
- `src/transactions.py` - Add audit trail support
- `src/stages/persist_stage.py` - Wrap database commits

### Phase 3: Testing

**Files Created**:
- `tests/unit/test_cleanup_handlers.py` - Unit tests for cleanup logic
- `tests/integration/test_error_recovery.py` - End-to-end tests

**Files Modified**:
- `tests/unit/test_transactions.py` - Test audit trail

---

## Examples

### Before: Inconsistent Retry Logic

```python
# api_client.py (tenacity inline)
@retry(wait=wait_exponential(...), stop=stop_after_attempt(5), ...)
def _call_responses_api_with_retry(self, payload):
    ...

# vector_store.py (manual loop)
for attempt in range(max_retries):
    try:
        return self.client.files.create(...)
    except Exception as e:
        if attempt < max_retries - 1:
            wait_time = 2**attempt
            time.sleep(wait_time)
```

### After: Unified Retry Logic

```python
# All modules use same decorator
from src.retry_logic import retry

@retry(max_attempts=5, initial_wait=2.0, max_wait=60.0)
def call_api():
    return client.api_call()
```

### Before: Orphaned Resources

```python
# No cleanup → file orphaned if commit fails
file_obj = client.files.create(...)
doc = Document(file_id=file_obj.id)
session.add(doc)
session.commit()  # If this fails, file-abc123 orphaned
```

### After: Compensating Transactions

```python
# Cleanup runs automatically on failure
from src.transactions import compensating_transaction
from src.cleanup_handlers import cleanup_files_api_upload

def cleanup():
    cleanup_files_api_upload(client, file_obj.id)

with compensating_transaction(session, cleanup):
    file_obj = client.files.create(...)
    doc = Document(file_id=file_obj.id)
    session.add(doc)
    # If commit fails, cleanup() deletes file
```

---

## Monitoring & Observability

### Metrics to Track

1. **Retry Success Rate**:
   ```
   retries_successful / (retries_successful + retries_exhausted)
   ```
   Target: >95%

2. **Compensation Execution Rate**:
   ```
   compensations_run / database_commit_failures
   ```
   Target: 100% (every failure should trigger compensation)

3. **Cleanup Success Rate**:
   ```
   cleanups_successful / cleanups_attempted
   ```
   Target: >99%

4. **Orphaned Resources**:
   ```
   files_in_openai - files_in_database
   ```
   Target: 0

### Alerts

- **Alert**: Retry exhaustion rate >5%
  **Action**: Check OpenAI service health, increase rate limits

- **Alert**: Compensation failure rate >1%
  **Action**: Manual cleanup required, investigate API connectivity

- **Alert**: Orphaned resources detected
  **Action**: Run cleanup script, investigate compensation logic

### Logging

All transactions log structured JSON:
```json
{
  "timestamp": "2025-10-16T14:30:00Z",
  "level": "INFO",
  "stage": "PersistToDBStage",
  "status": "success",
  "compensation_needed": false,
  "started_at": "2025-10-16T14:29:59Z",
  "committed_at": "2025-10-16T14:30:00Z",
  "file_id": "file-abc123",
  "document_id": 42
}
```

---

## Testing Strategy

### Unit Tests

- `test_retry_logic.py`: Verify retry predicate, backoff timing
- `test_cleanup_handlers.py`: Mock API calls, verify cleanup
- `test_transactions.py`: Test audit trail, compensation execution

### Integration Tests

- `test_error_recovery.py`: End-to-end retry + compensation
  - Upload file → DB commit fails → verify file deleted
  - API rate limit → verify 5 retries → success
  - Vector store failure → verify non-fatal (document still saved)

### Load Tests

- Trigger 100 concurrent file uploads
- Inject 10% database failures
- Verify: 100% cleanup execution, 0 orphaned files

---

## Future Enhancements

1. **Async Cleanup** (Q2 2026):
   - Queue cleanup tasks for async execution
   - Reduces transaction latency

2. **Idempotency Tokens** (Q3 2026):
   - Generate UUID per operation
   - Prevent duplicate uploads on retry

3. **Cleanup Verification** (Q4 2026):
   - Periodic scan for orphaned resources
   - Auto-cleanup with confirmation

4. **Circuit Breaker Metrics** (Q1 2027):
   - Expose circuit breaker state in /metrics endpoint
   - Alert when circuit opens

---

## References

- **Compensating Transactions**: [Microsoft Cloud Design Patterns](https://learn.microsoft.com/en-us/azure/architecture/patterns/compensating-transaction)
- **Retry Pattern**: [AWS Best Practices](https://aws.amazon.com/blogs/architecture/exponential-backoff-and-jitter/)
- **Saga Pattern**: [Microservices.io](https://microservices.io/patterns/data/saga.html)
- **Two-Phase Commit**: [Martin Kleppmann](https://martin.kleppmann.com/2015/12/08/consensus-replication.html)

---

## Approval

| Role | Name | Date | Signature |
|------|------|------|-----------|
| System Architect | Claude Code | 2025-10-16 | ✅ Approved |
| Tech Lead | [Pending] | [Pending] | [Pending] |
| Senior Developer | [Pending] | [Pending] | [Pending] |

---

## Changelog

- **2025-10-16**: Initial ADR created
- **2025-10-16**: Phases 1-3 implemented
- **2025-10-16**: Documentation completed
