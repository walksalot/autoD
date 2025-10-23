# Testing Recommendations for Wave 2 Integration
**Branch**: `integration/wave1-config`
**Date**: 2025-10-16
**Status**: 95% Pass Rate, 65.86% Coverage

## Executive Decision Matrix

| Fix Priority | Tests | Impact | Effort | Block Production? |
|--------------|-------|--------|--------|-------------------|
| 🔴 HIGH | 5 | Processor fails in non-default mode | 15 min | **YES** |
| 🟡 MEDIUM | 4 | Retry logic may not work | 1-2 hrs | **YES** |
| 🟢 LOW | 9 | Test assertions only | 30 min | NO |
| 🟢 LOW | 1 | Policy compliance | 15 min | NO |

## Immediate Action Plan

### Step 1: Fix Processor Schema Bug (BLOCKING - 15 minutes)

**File**: `/Users/krisstudio/Developer/Projects/autoD/src/processor.py`
**Lines**: 196-235

**Current Code** (BROKEN):
```python
# processor.py lines ~210-230
doc = Document(
    sha256_hex=sha256_hex,
    openai_file_id=file_id,
    page_count=metadata.page_count,
    doc_type=metadata.doc_type,
    issuer=metadata.issuer,
    primary_date=metadata.primary_date,
    total_amount=metadata.total_amount,
    summary=metadata.summary,
    action_items=metadata.action_items,
    status="processed",
)
```

**Fixed Code**:
```python
# Use metadata_json field for simplified Document model
doc = Document(
    sha256_hex=sha256_hex,
    openai_file_id=file_id,
    metadata_json=metadata.model_dump(),  # Store all metadata as JSON
    status="processed",
)
```

**Verification**:
```bash
# After fixing, run these tests:
pytest tests/critical_paths/test_processor_errors.py::TestDuplicateDetection::test_process_duplicates_when_skip_false -v
pytest tests/critical_paths/test_processor_errors.py::TestSchemaValidationFailures -v
pytest tests/critical_paths/test_processor_errors.py::TestVectorStoreUploadFailures -v
```

**Expected Result**: 5 tests change from FAILED → PASSED

---

### Step 2: Investigate Retry/Error Recovery (BLOCKING - 1-2 hours)

**Failing Tests**:
1. `test_files_api_upload_retries_on_rate_limit`
2. `test_files_api_upload_retries_on_connection_error`
3. `test_api_call_fails_fast_on_authentication_error`
4. `test_full_pipeline_with_transient_errors`

**Investigation Steps**:

#### 2.1 Check Mock API Response Structure
```bash
# Run single test with verbose output
pytest tests/integration/test_error_recovery.py::TestRetryBehavior::test_files_api_upload_retries_on_rate_limit -vv -s
```

Look for:
- Exception type mismatch (OpenAI SDK vs mock)
- Response structure differences
- Timeout behavior

#### 2.2 Verify Retry Decorator Logic
```python
# src/retry_logic.py - Check is_retryable_api_error()
def is_retryable_api_error(e: Exception) -> bool:
    if isinstance(e, openai.APIError):
        return e.status_code in {429, 500, 502, 503, 504}
    # Add more cases if needed
    return False
```

#### 2.3 Check OpenAI SDK Exception Types
```bash
# List available exception types
python3 -c "import openai; print([x for x in dir(openai) if 'Error' in x])"
```

Common issues:
- `RateLimitError` vs `APIError` with status 429
- `Timeout` exception structure
- `APIConnectionError` handling

#### 2.4 Fix Example (if needed)
```python
# If RateLimitError is separate from APIError
from openai import RateLimitError, APIConnectionError, APITimeoutError

def is_retryable_api_error(e: Exception) -> bool:
    if isinstance(e, RateLimitError):
        return True
    if isinstance(e, (APIConnectionError, APITimeoutError)):
        return True
    if isinstance(e, openai.APIError):
        return e.status_code in {500, 502, 503, 504}
    return False
```

**Verification**:
```bash
# After fixing, run all retry tests
pytest tests/integration/test_error_recovery.py::TestRetryBehavior -v
```

---

### Step 3: Update Logging Test Assertions (NON-BLOCKING - 30 minutes)

**Affected Tests**: 9 tests in `test_cleanup_handlers.py` and `test_transactions.py`

**Problem**: Tests check `assert file_id in caplog.text` but structured logging uses `extra={}`.

**Solution**: Update tests to check structured log records instead of text:

**Before** (FAILS):
```python
def test_logs_cleanup_attempt(self, caplog):
    mock_client = Mock()
    file_id = "file-test123"

    with caplog.at_level("INFO"):
        cleanup_files_api_upload(mock_client, file_id)

    # FAILS - file_id not in message text
    assert file_id in caplog.text
```

**After** (PASSES):
```python
def test_logs_cleanup_attempt(self, caplog):
    mock_client = Mock()
    file_id = "file-test123"

    with caplog.at_level("INFO"):
        cleanup_files_api_upload(mock_client, file_id)

    # Check structured log records instead
    assert any(
        record.message == "Attempting to cleanup Files API upload"
        and record.file_id == file_id
        for record in caplog.records
    )
    # Or check extra dict directly:
    assert any(
        "file_id" in record.__dict__
        and record.__dict__["file_id"] == file_id
        for record in caplog.records
    )
```

**Files to Update**:
1. `tests/unit/test_cleanup_handlers.py` (8 tests)
2. `tests/unit/test_transactions.py` (1 test)

**Pattern to Follow**:
```python
# Instead of checking caplog.text, use caplog.records
for record in caplog.records:
    if record.message == "Expected message":
        # Check extra fields from record.__dict__
        assert "file_id" in record.__dict__
        assert record.__dict__["file_id"] == expected_file_id
```

---

### Step 4: Fix Model Policy Compliance (NON-BLOCKING - 15 minutes)

**Test**: `test_python_sources_do_not_reference_deprecated_models`

**Search for deprecated references**:
```bash
cd /Users/krisstudio/Developer/Projects/autoD

# Search for deprecated models
grep -r "gpt-4o-mini" src/ --include="*.py"
grep -r "gpt-4\.1" src/ --include="*.py"
grep -r "claude-3\." src/ --include="*.py"
```

**Likely False Positives**:
- Comments explaining deprecated models
- Documentation strings
- Test fixture data

**Real Issues to Fix**:
- Model name constants
- Default values in config
- API call parameters

**Verification**:
```bash
pytest tests/test_model_policy.py::test_python_sources_do_not_reference_deprecated_models -v
```

---

## Post-Fix Validation

### Full Test Suite
```bash
cd /Users/krisstudio/Developer/Projects/autoD
source .venv/bin/activate

# Run complete test suite
pytest tests/ -v --cov=src --cov-report=term-missing --cov-report=json

# Expected results after fixes:
# - Total: 563 tests
# - Passed: 554+ (98%+)
# - Failed: <10 (only logging tests if skipped)
# - Coverage: 65.86%+ (maintained or improved)
```

### Critical Path Validation
```bash
# Verify all critical systems still passing
pytest tests/critical_paths/ -v

# Expected: All 47 tests passing
# - Circuit breaker: 16/16 ✅
# - Database errors: 15/15 ✅
# - Processor errors: 16/16 ✅ (after Step 1 fix)
```

### Integration Test Validation
```bash
# Verify error recovery working
pytest tests/integration/test_error_recovery.py -v

# Expected: All 14 tests passing (after Step 2 fix)
```

---

## Production Deployment Checklist

### Pre-Deployment
- [ ] Step 1 Complete: processor.py schema bug fixed
- [ ] Step 2 Complete: Retry/error recovery tests passing
- [ ] Full test suite passing (≥98%)
- [ ] Coverage maintained at ≥65%
- [ ] No regressions in critical paths
- [ ] Code review completed
- [ ] CHANGELOG.md updated with fixes

### Deployment
- [ ] Deploy to staging environment
- [ ] Run smoke tests with real PDFs
- [ ] Monitor error rates for 24 hours
- [ ] Check circuit breaker metrics
- [ ] Verify retry logic with induced failures
- [ ] Validate cost tracking accuracy

### Post-Deployment
- [ ] Monitor production metrics for 1 week
- [ ] Track processor success rate
- [ ] Monitor retry behavior
- [ ] Verify vector store integration
- [ ] Check embedding cache performance

### Optional (Wave 3)
- [ ] Step 3: Update logging test assertions
- [ ] Step 4: Fix model policy compliance
- [ ] Increase coverage for api_stage.py (54% → 70%)
- [ ] Increase coverage for dedupe.py (34% → 60%)
- [ ] Add tests for embedding_cache.py
- [ ] Add tests for search.py

---

## Risk Assessment

### High Risk (Must Fix Before Production)
1. **Processor Schema Bug** - Breaks processor in non-default mode
   - Affected users: Anyone using `skip_duplicates=False`
   - Failure mode: TypeError, complete processing failure
   - Mitigation: Fix before production (Step 1)

2. **Retry Logic Issues** - May not retry on certain errors
   - Affected users: All users during API outages
   - Failure mode: Failed processing instead of retry
   - Mitigation: Investigate and fix (Step 2)

### Low Risk (Can Fix Post-Production)
3. **Logging Test Assertions** - Test infrastructure only
   - Affected users: Developers only
   - Failure mode: False test failures
   - Mitigation: No production impact

4. **Model Policy Compliance** - Code hygiene
   - Affected users: None (policy enforcement)
   - Failure mode: Deprecated model references in code
   - Mitigation: No runtime impact

---

## Success Criteria

### Minimum (Production Deployment)
- ✅ 98%+ test pass rate (554+/563 tests)
- ✅ All critical path tests passing (47/47)
- ✅ Coverage ≥65%
- ✅ No regressions
- ✅ Processor schema bug fixed (Step 1)
- ✅ Retry logic validated (Step 2)

### Optimal (Ideal State)
- ✅ 100% test pass rate (563/563 tests)
- ✅ Coverage ≥70%
- ✅ All logging tests updated (Step 3)
- ✅ Model policy compliant (Step 4)
- ✅ Coverage >60% for all modules

---

## Timeline Estimates

| Task | Effort | Priority | Can Parallelize? |
|------|--------|----------|------------------|
| Step 1: Fix processor.py | 15 min | HIGH | No - blocks other tests |
| Step 2: Fix retry logic | 1-2 hrs | MEDIUM | No - blocks deployment |
| Step 3: Update logging tests | 30 min | LOW | Yes - independent |
| Step 4: Fix model policy | 15 min | LOW | Yes - independent |
| **Total Serial Path** | **2-2.5 hrs** | | |
| **Total Parallel Path** | **1.75-2.25 hrs** | | If Steps 3+4 parallel |

**Recommended Approach**:
1. Fix Step 1 (15 min) → Run tests → Verify 5 failures resolved
2. Fix Step 2 (1-2 hrs) → Run tests → Verify 4 failures resolved
3. (Optional) Steps 3+4 in parallel after production deployment

---

## Contact & Escalation

**Questions?**
- Test failures: Refer to `/Users/krisstudio/Developer/Projects/autoD/docs/integration_test_report_wave2.md`
- Coverage details: Check `coverage.json` and `test_results.log`
- Raw test output: See `test_results.log`

**Need Help?**
- Processor schema: Review `src/models.py` and `src/processor.py`
- Retry logic: Review `src/retry_logic.py` and OpenAI SDK docs
- Logging tests: Review `src/logging_config.py` and pytest caplog docs

**Escalation Path**:
1. Review full test report: `docs/integration_test_report_wave2.md`
2. Check test artifacts: `test_results.log`, `coverage.json`
3. Re-run failing tests with `-vv -s` for detailed output
4. Contact test-automator agent with specific test names

---

**Report Generated**: 2025-10-16
**Branch**: integration/wave1-config
**Commit**: 07d756a
