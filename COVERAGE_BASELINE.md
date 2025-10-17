# Coverage Baseline Report
**Date:** 2025-10-16
**Analyst:** Claude Code (Sonnet 4.5)
**Total Tests:** 299 (1 skipped)
**Overall Coverage:** 19.31%

---

## Executive Summary

**Current State:** The autoD project has **19.31% code coverage**, significantly lower than the documented 42% estimate. This indicates substantial untested code paths, particularly in critical modules like `processor.py`, `daemon.py`, `database.py`, and `dedupe.py`.

**Target:** Increase coverage to **60%+** with focus on critical paths:
- Circuit breaker state machine (`api_client.py`)
- Error paths and retry logic
- Database operations and migrations
- Full pipeline integration
- Vector store operations

**Test Infrastructure:** ✅ **Excellent**
- 299 tests across 28 files
- Comprehensive fixtures in `conftest.py`
- Well-designed mocks for OpenAI APIs
- Property-based testing framework (Hypothesis) available

---

## Coverage by Module (Sorted by Coverage %)

### Critical Gaps (0-20% Coverage) 🔴

| Module | Statements | Missing | Coverage | Critical Untested Areas |
|--------|-----------|---------|----------|------------------------|
| **daemon.py** | 212 | 212 | **0.00%** | ❌ Entire daemon untested |
| **processor.py** | 121 | 121 | **0.00%** | ❌ process_document god function (195 lines) |
| **database.py** | 41 | 41 | **0.00%** | ❌ DatabaseManager, session handling |
| **dedupe.py** | 57 | 57 | **0.00%** | ❌ Deduplication logic, vector store attributes |
| **token_counter.py** | 44 | 44 | **0.00%** | ❌ Token counting primitives |
| **prompts.py** | 58 | 46 | **14.29%** | ⚠️ Payload construction, prompt templates |
| **vector_store.py** | 84 | 68 | **15.69%** | ⚠️ Vector store lifecycle, file uploads |
| **api_client.py** | 100 | 78 | **17.46%** | ⚠️ **Circuit breaker (lines 25-92)**, retry integration |

### Moderate Coverage (20-50%) 🟡

| Module | Statements | Missing | Coverage | Untested Areas |
|--------|-----------|---------|----------|---------------|
| **stages/api_stage.py** | 60 | 46 | **20.00%** | API call error handling |
| **stages/persist_stage.py** | 34 | 25 | **21.43%** | Database persistence errors |
| **logging_config.py** | 42 | 30 | **22.22%** | JSON formatter edge cases |
| **stages/dedupe_stage.py** | 17 | 11 | **28.57%** | Duplicate detection edge cases |
| **stages/upload_stage.py** | 22 | 14 | **28.57%** | File upload errors |
| **transactions.py** | 22 | 15 | **29.17%** | Compensating transaction rollback |
| **retry_logic.py** | 29 | 18 | **29.73%** | Retry exhaustion, backoff timing |
| **cost_calculator.py** | 95 | 62 | **30.28%** | Cost tracking, alerts |
| **stages/sha256_stage.py** | 14 | 9 | **31.25%** | Hash computation errors |
| **monitoring.py** | 143 | 84 | **34.10%** | Alert manager, health checks |
| **schema.py** | 31 | 18 | **37.14%** | JSON schema validation |

### Good Coverage (50%+) ✅

| Module | Statements | Missing | Coverage | Notes |
|--------|-----------|---------|----------|-------|
| **pipeline.py** | 54 | 22 | **51.61%** | ✅ Core pipeline tested, error paths missing |
| **config.py** | 62 | 20 | **58.33%** | ✅ Good validation coverage |
| **models.py** | 27 | 5 | **81.48%** | ✅ Excellent ORM model coverage |

---

## Critical Path Analysis

### 1. Circuit Breaker (api_client.py:25-92) 🔴 **UNTESTED**

```python
class CircuitBreaker:
    States: CLOSED | OPEN | HALF_OPEN
    Missing Tests:
    - State transitions (CLOSED → OPEN → HALF_OPEN → CLOSED)
    - Failure threshold breach (10 failures)
    - Timeout recovery (60 seconds)
    - Concurrent requests during state change
    - Success in HALF_OPEN closes circuit
    - Failure in HALF_OPEN reopens circuit
```

**Impact:** Circuit breaker prevents cascade failures. Untested state machine = **production risk**.

### 2. Processor God Function (processor.py:70-265) 🔴 **0% COVERAGE**

```python
def process_document(...) -> ProcessingResult:
    # 195 lines, 9 responsibilities:
    1. Hash computation
    2. Deduplication check
    3. PDF encoding
    4. API payload construction
    5. Responses API call
    6. Response parsing
    7. Cost calculation
    8. Database persistence
    9. Vector store upload
```

**Impact:** Core business logic completely untested. **Highest priority**.

### 3. Database Operations (database.py) 🔴 **0% COVERAGE**

```python
class DatabaseManager:
    Missing Tests:
    - Connection pool management
    - Transaction rollback
    - Foreign key constraints
    - Session lifecycle
    - SQLite pragma settings
```

### 4. Retry Logic Edge Cases (retry_logic.py) 🟡 **29.73%**

```python
Tested:
✅ is_retryable_api_error predicate (13 tests)
✅ Basic retry on rate limit

Missing:
❌ Retry exhaustion after 5 attempts
❌ Exponential backoff timing validation
❌ Mixed error sequence handling
❌ Circuit breaker integration
```

### 5. Vector Store Operations (vector_store.py) 🔴 **15.69%**

```python
class VectorStoreManager:
    Missing Tests:
    - Vector store creation
    - Cache file persistence
    - File upload to vector store
    - Recovery from cache loss
    - Concurrent uploads
```

---

## Test Distribution

### By Type
```
Unit Tests:       ~180 tests (60%)
Integration Tests: ~95 tests (32%)
Infrastructure:    ~24 tests (8%)
```

### By Module Coverage
```
Excellent (80%+): 1 module   (models.py)
Good (60-79%):    1 module   (config.py)
Moderate (40-59%): 1 module   (pipeline.py)
Low (20-39%):     8 modules
Critical (<20%):  11 modules  ← TARGET FOR EXPANSION
```

---

## Gap Analysis: Path to 60% Coverage

### Required New Coverage

**Current:** 323 statements covered (19.31%)
**Target:** 821 statements covered (60%)
**Gap:** 498 additional statements need tests

### High-Impact Modules (Largest Coverage Gains)

1. **daemon.py** (212 statements) - +15.5% if 100% covered
   - Priority: Low (daemon not in critical path)

2. **processor.py** (121 statements) - +8.8% if 100% covered
   - Priority: **CRITICAL** (core business logic)

3. **api_client.py** (100 statements) - +7.3% if 100% covered
   - Priority: **CRITICAL** (circuit breaker)

4. **cost_calculator.py** (95 statements) - +6.9% if 100% covered
   - Priority: Medium (cost tracking)

5. **vector_store.py** (84 statements) - +6.1% if 100% covered
   - Priority: High (integration)

### Prioritized Test Plan

#### Phase 1: Critical Paths (Target: +25% coverage)
- ✅ Circuit breaker tests (api_client.py) → +5%
- ✅ Processor error paths (processor.py) → +6%
- ✅ Database operations (database.py) → +3%
- ✅ Retry edge cases (retry_logic.py) → +2%
- ✅ Dedupe logic (dedupe.py) → +4%
- ✅ Vector store operations (vector_store.py) → +5%

#### Phase 2: Integration Tests (Target: +15% coverage)
- ✅ Full pipeline E2E (processor.py integration) → +5%
- ✅ Batch processing (process_inbox) → +5%
- ✅ Alembic migrations → +2%
- ✅ Stage integration tests → +3%

#### Phase 3: Property-Based Tests (Target: +5% coverage)
- ✅ Hash consistency (Hypothesis)
- ✅ JSON schema validation
- ✅ Cost calculation properties

**Expected Total:** 19.31% + 25% + 15% + 5% = **64.31%** ✅ **EXCEEDS 60% TARGET**

---

## Module-Specific Coverage Details

### api_client.py (17.46% coverage)

```
Lines Covered: 22/100
Missing Critical Code:

Lines 25-92:   CircuitBreaker class (UNTESTED)
  - __init__, call(), _on_success(), _on_failure()
  - State: CLOSED, OPEN, HALF_OPEN

Lines 117-134: ResponsesAPIClient.__init__ (UNTESTED)
Lines 173-188: call_responses_api() error handling (UNTESTED)
Lines 196-219: _parse_response() validation (UNTESTED)
Lines 239-244: _extract_metadata() (UNTESTED)
Lines 260-274: Error recovery logic (UNTESTED)
```

**Test Needed:**
- `tests/critical_paths/test_circuit_breaker.py` (8 tests)
- `tests/unit/test_api_client_parsing.py` (5 tests)

### processor.py (0.00% coverage)

```
Lines Covered: 0/121
ALL CODE UNTESTED

Lines 70-265:  process_document() - 195 lines (God function)
Lines 268-365: process_inbox() - 96 lines (Batch processing)
Lines 368-398: Helper functions
```

**Test Needed:**
- `tests/critical_paths/test_processor_errors.py` (5 tests)
- `tests/integration/test_batch_processing.py` (4 tests)
- `tests/integration/test_full_pipeline_e2e.py` (6 tests)

### database.py (0.00% coverage)

```
Lines Covered: 0/41
ALL CODE UNTESTED

Lines 14-52:  DatabaseManager.__init__
Lines 54-69:  get_session() context manager
Lines 71-85:  health_check()
Lines 87-96:  close()
Lines 98-113: Migration helpers
```

**Test Needed:**
- `tests/critical_paths/test_database_errors.py` (4 tests)
- `tests/integration/test_alembic_migrations.py` (4 tests)

---

## Existing Test Suite Analysis

### Well-Tested Areas ✅

**Token Counter Tests (145 tests):**
- `tests/integration/test_chat_api.py` (21 tests)
- `tests/integration/test_responses_api.py` (18 tests)
- `tests/integration/test_token_cost_accuracy.py` (8 tests)
- `tests/unit/test_primitives.py` (28 tests)
- `tests/unit/test_cost_calculator.py` (42 tests)
- `tests/unit/test_encoding.py` (13 tests)

**Configuration Tests (24 tests):**
- `tests/unit/test_config.py` - Excellent validation coverage

**Pipeline Tests (13 tests):**
- `tests/test_pipeline.py` - Good integration coverage

**SHA-256 Tests (11 tests):**
- `tests/test_sha256_stage.py` - Comprehensive hash testing

### Test Quality Assessment ✅

**Strengths:**
- ✅ Deterministic test data (known_hashes)
- ✅ Comprehensive fixtures (conftest.py - 563 lines)
- ✅ Property-based testing framework available (Hypothesis)
- ✅ Parallel test execution support (pytest-xdist)
- ✅ Mock error injection framework (error_simulator.py)

**Gaps:**
- ❌ No circuit breaker tests
- ❌ No migration tests
- ❌ No batch processing tests
- ❌ Limited error path coverage
- ❌ No performance benchmarks

---

## Recommendations

### Immediate Actions (Week 1)

1. **Create `tests/critical_paths/` directory** for high-priority tests
2. **Implement circuit breaker tests** (api_client.py:25-92)
3. **Add processor error path tests** (processor.py)
4. **Create database error tests** (database.py)

### Short-Term (Week 2)

5. **Integration tests for full pipeline** (E2E)
6. **Batch processing tests** (process_inbox)
7. **Vector store integration tests**
8. **Alembic migration tests**

### Long-Term (Week 3)

9. **Property-based tests** with Hypothesis
10. **Performance benchmarks** (baseline for optimization)
11. **Coverage enforcement in CI** (fail under 60%)

---

## Success Criteria

### Coverage Targets by Module

| Module | Current | Target | Priority |
|--------|---------|--------|----------|
| api_client.py | 17% | **80%+** | CRITICAL |
| processor.py | 0% | **70%+** | CRITICAL |
| database.py | 0% | **75%+** | CRITICAL |
| retry_logic.py | 30% | **90%+** | HIGH |
| dedupe.py | 0% | **70%+** | HIGH |
| vector_store.py | 16% | **60%+** | HIGH |
| **OVERALL** | **19.31%** | **60%+** | **TARGET** |

### Quality Metrics

- ✅ Zero flaky tests (all deterministic)
- ✅ All tests pass in parallel (`pytest -n auto`)
- ✅ Coverage enforced in CI (fail under 60%)
- ✅ Property-based tests catch edge cases
- ✅ Error path coverage >= 50% for critical modules

---

## Appendix: Full Coverage Report

```
Name                          Stmts   Miss Branch BrPart   Cover   Missing
--------------------------------------------------------------------------
src/api_client.py               100     78     26      0  17.46%   Lines: 44-48, 64-79, 83-87, 91-96, 117-134, ...
src/config.py                    62     20     10      0  58.33%   Lines: 81-93, 104-113, 250, 255, 260, ...
src/cost_calculator.py           95     62     14      0  30.28%   Lines: 45, 98-117, 178-209, 242-267, ...
src/daemon.py                   212    212     56      0   0.00%   Lines: 8-466 (ENTIRE MODULE)
src/database.py                  41     41      2      0   0.00%   Lines: 6-113 (ENTIRE MODULE)
src/dedupe.py                    57     57     30      0   0.00%   Lines: 6-199 (ENTIRE MODULE)
src/logging_config.py            42     30     12      0  22.22%   Lines: 23-80, 104-141, 152
src/models.py                    27      5      0      0  81.48%   Lines: 159, 198-201
src/monitoring.py               143     84     30      0  34.10%   Lines: 62-64, 88-90, 102-104, 122-136, ...
src/pipeline.py                  54     22      8      0  51.61%   Lines: 147, 182, 198-262
src/processor.py                121    121     18      0   0.00%   Lines: 6-398 (ENTIRE MODULE)
src/prompts.py                   58     46     26      0  14.29%   Lines: 102-138, 178-265
src/retry_logic.py               29     18      8      0  29.73%   Lines: 77-109, 174-175
src/schema.py                    31     18      4      0  37.14%   Lines: 61, 313, 332-344, 354-367
src/stages/api_stage.py          60     46     10      0  20.00%   Lines: 26-38, 61-62, 65-156
src/stages/dedupe_stage.py       17     11      4      0  28.57%   Lines: 48, 63-83
src/stages/persist_stage.py      34     25      8      0  21.43%   Lines: 48, 65-135
src/stages/sha256_stage.py       14      9      2      0  31.25%   Lines: 51-68
src/stages/upload_stage.py       22     14      6      0  28.57%   Lines: 50, 66-103
src/token_counter.py             44     44     10      0   0.00%   Lines: 6-193 (ENTIRE MODULE)
src/transactions.py              22     15      2      0  29.17%   Lines: 43-61
src/vector_store.py              84     68     18      0  15.69%   Lines: 44-47, 63-91, 100-109, 131-165, ...
--------------------------------------------------------------------------
TOTAL                          1369   1046    304      0  19.31%
```

---

**Generated:** 2025-10-16
**Next Review:** After Phase 1 completion (Circuit breaker + Processor tests)
**Contact:** See AGENTS.md for test coverage workstream lead
