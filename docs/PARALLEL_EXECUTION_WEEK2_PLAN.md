# Parallel Execution Plan: 7 Concurrent Workstreams

**Date:** October 16, 2025
**Duration:** 7 days
**Approach:** Git worktrees + 7 specialized Claude agents
**Status:** ✅ Day 0 Complete (Worktrees created)

---

## Executive Summary

Execute Week 2 development (3 workstreams) + Technical Debt cleanup (4 workstreams) simultaneously using git worktrees and specialized Claude Code agents.

**What's Done:**
- ✅ 7 git worktrees created
- ✅ All branches ready for parallel development

**What's Next:**
- Launch 4 Claude sessions on Day 1 (TD2, TD4, WS1, WS3)
- Launch 2 more on Day 2 after TD2 merges (TD1, WS2)
- Launch 1 more on Day 4 (TD3)
- Merge progressively in 5 waves

---

## The 7 Workstreams

| ID | Name | Agent | Duration | Start Day | Dependencies |
|----|------|-------|----------|-----------|--------------|
| **TD2** | Config Management | `python-pro` | 1-2 days | Day 1 | None (CRITICAL PATH) |
| **TD1** | Error Handling | `python-pro` | 2 days | Day 2 | TD2 |
| **TD3** | API Client Refactor | `backend-architect` | 2 days | Day 4 | TD1, TD2 |
| **TD4** | Test Coverage | `test-automator` | Ongoing | Day 1 | None (continuous) |
| **WS1** | Vector Store | `python-pro` | 4 days | Day 1 | TD2 (soft) |
| **WS2** | Batch Processing | `backend-architect` | 4 days | Day 2 | TD2, TD3 |
| **WS3** | Production Hardening | `deployment-engineer` | 5 days | Day 1 | TD2 (soft) |

---

## Day-by-Day Timeline

### Day 0: ✅ COMPLETE
```bash
# All worktrees created:
git worktree list
# Shows 8 directories (main + 7 workstreams)
```

### Day 1: Launch 4 Sessions

**Start These in Separate Terminal Tabs:**

1. **TD2 Config Management** (🔴 CRITICAL - START FIRST)
```bash
cd /Users/krisstudio/Developer/Projects/autoD-config-management
claude
# Copy-paste prompt from section below
```

2. **TD4 Test Coverage**
```bash
cd /Users/krisstudio/Developer/Projects/autoD-test-coverage
claude
# Copy-paste prompt from section below
```

3. **WS1 Vector Store**
```bash
cd /Users/krisstudio/Developer/Projects/autoD-vector-store
claude
# Copy-paste prompt from section below
```

4. **WS3 Production Hardening**
```bash
cd /Users/krisstudio/Developer/Projects/autoD-production-hardening
claude
# Copy-paste prompt from section below
```

### Day 2: MERGE Wave 1, Launch 2 More

**Morning - Merge TD2:**
```bash
cd /Users/krisstudio/Developer/Projects/autoD
git checkout -b integration/wave1-config
git merge workstream/config-management --no-ff

# Quality Gates:
pytest tests/unit/test_config.py -v
mypy src/config.py
python -c "from src.config import Config; Config()"
```

**Afternoon - Launch 2 More:**
```bash
# TD1 Error Handling
cd /Users/krisstudio/Developer/Projects/autoD-error-handling
claude

# WS2 Batch Processing
cd /Users/krisstudio/Developer/Projects/autoD-batch-processing
claude
```

### Day 3: MERGE Wave 2
```bash
cd /Users/krisstudio/Developer/Projects/autoD
git checkout integration/wave1-config
git merge workstream/error-handling --no-ff
git merge workstream/test-coverage --no-ff
```

### Day 4: Launch TD3
```bash
cd /Users/krisstudio/Developer/Projects/autoD-api-client
claude
```

### Day 5: MERGE Wave 3
```bash
git merge workstream/vector-store --no-ff
git merge workstream/api-client-refactor --no-ff
```

### Day 6: MERGE Wave 4
```bash
git merge workstream/batch-processing --no-ff
```

### Day 7: MERGE Wave 5 + Deploy
```bash
git merge workstream/production-hardening --no-ff

# Final validation
pytest tests/ --cov=src --cov-report=term

# Merge to main
git checkout main
git merge integration/wave1-config --no-ff
git tag week2-complete
```

---

## Claude Session Prompts (Copy-Paste These)

### 🔴 TD2: Configuration Management (START FIRST - DAY 1)

```
ultrathink: You are implementing Configuration Management standardization for autoD.

CONTEXT - READ THESE FIRST:
- docs/TECHNICAL_DEBT_ANALYSIS.md (Section 1.5)
- src/config.py (current implementation)
- .env.example (21 environment variables)

GOAL: Centralize all 21 environment variables into a unified Config class using Pydantic V2.

DELIVERABLES:
1. Refactor src/config.py with single Config class (all 21 vars)
2. Update all code references (processor.py, api_client.py, etc.)
3. Add Pydantic validation (required/optional, ranges, formats)
4. Write tests for config validation

SUCCESS CRITERIA:
✅ All 21 variables documented and centralized
✅ Type-safe config access throughout codebase
✅ Tests pass: pytest tests/unit/test_config.py -v

IMPORTANT:
- This BLOCKS other workstreams - complete in 1-2 days
- Use Pydantic V2 BaseSettings (not V1)
- Focus on consolidation, not new features

Ready? Read the docs and create your plan. DO NOT CODE YET.
```

---

### TD4: Test Coverage Expansion (START DAY 1)

```
You are implementing Test Coverage Expansion for autoD.

CONTEXT - READ THESE FIRST:
- docs/TECHNICAL_DEBT_ANALYSIS.md (Section 1.3)
- tests/ directory (existing suite)
- conftest.py (fixtures)

GOAL: Increase test coverage from 42% to 60%+ with focus on critical paths.

DELIVERABLES:

Day 1-2: Infrastructure
- Set up pytest-cov
- Baseline coverage report
- Identify gaps (error paths, retry logic, circuit breaker)

Day 3-4: Critical Path Tests
- Error injection tests
- Retry behavior validation
- Circuit breaker state machine tests
- Database migration tests

Day 5-6: Integration Tests
- Full pipeline E2E tests
- Vector store integration
- Batch processing scenarios

Day 7: Property-Based Tests
- Hypothesis for edge cases
- Hash consistency tests
- JSON schema validation

SUCCESS CRITERIA:
✅ 60%+ overall coverage
✅ 80%+ on critical modules (processor, api_client, retry)
✅ Zero flaky tests

IMPORTANT:
- Continuous workstream - validates all other work
- Provide test infrastructure for WS1, WS2, WS3
- Coordinate with other agents for test requirements

Ready? Create your testing strategy.
```

---

### WS1: Vector Store & Semantic Search (START DAY 1)

```
You are implementing Vector Store & Semantic Search for autoD.

CONTEXT - READ THESE FIRST:
- WEEK_2_PLAN.md (Workstream 1)
- docs/CODE_ARCHITECTURE.md
- src/dedupe.py (existing vector store usage)

GOAL: Build OpenAI vector store integration with semantic search over 4 days.

DELIVERABLES:

Day 1: Vector Store Foundation
- VectorStoreManager class (create/retrieve stores)
- File upload with retry logic
- Configuration (embedding model, dimensions)
- Tests (90%+ coverage)

Day 2: Document Embedding Generation
- Extract text from processed documents
- Generate embeddings via OpenAI API
- Cache embeddings in database
- Track embedding costs

Day 3: Semantic Search API
- Query vector store
- Rank results by relevance
- Filter by metadata
- Sub-500ms P95 latency

Day 4: Vector Cache Management
- TTL-based expiration
- Cache size monitoring (<1GB)
- 80%+ cache hit rate

SUCCESS CRITERIA:
✅ 80%+ cache hit rate
✅ Sub-500ms P95 query latency
✅ 90%+ test coverage

DEPENDENCIES:
- WAIT for TD2 (Config) merge on Day 2
- USE TD1 (Error Handling) patterns after Day 3

Ready? Create your 4-day plan.
```

---

### WS3: Production Hardening (START DAY 1)

```
You are implementing Production Hardening for autoD.

CONTEXT - READ THESE FIRST:
- WEEK_2_PLAN.md (Workstream 3)
- docs/DEPLOYMENT_VALIDATION.md
- docker-compose.yml

GOAL: Build operational excellence with monitoring and alerting over 5 days.

DELIVERABLES:

Day 3: Health Check Endpoints
- Liveness, readiness, startup probes
- Database, OpenAI API, vector store checks
- Sub-100ms responses

Day 4: Metrics Dashboard
- Request counts, latencies, error rates
- Cost tracking per operation
- Prometheus format export

Day 5: Alert Routing
- Email, Slack, PagerDuty integration
- High error rate (>5%) alerts
- Slow response time (>2s P95) alerts

Day 6: Deployment Runbook
- Operations guide (RUNBOOK.md)
- Monitoring setup (MONITORING.md)
- Troubleshooting guide

Day 7: Load Testing
- Sustained load (1 hour)
- Spike test
- Soak test (24 hours)

SUCCESS CRITERIA:
✅ Handles 100 req/min sustained
✅ Sub-2s P95 processing latency
✅ Complete runbook validated

Ready? Create your 5-day plan.
```

---

### TD1: Error Handling Standardization (START DAY 2)

```
ultrathink: You are implementing Error Handling Standardization for autoD.

CONTEXT - READ THESE FIRST:
- docs/TECHNICAL_DEBT_ANALYSIS.md (Section 1.2)
- src/retry.py (current retry logic)
- src/api_client.py (circuit breaker)

GOAL: Consolidate 6 error handling patterns into unified approach.

DELIVERABLES:

1. Standard retry logic (src/retry.py):
   - is_retryable_api_error() predicate
   - @retry decorator with tenacity
   - Exponential backoff: 2-60 seconds, max 5 attempts
   - Handles: RateLimitError, APIConnectionError, Timeout, APIError (5xx)

2. Compensating transactions (src/transactions.py):
   - CompensatingTransaction context manager
   - Rollback handlers for Files API uploads
   - Audit trail for partial failures

3. Update all API calls:
   - Apply @retry decorator consistently
   - Wrap multi-step operations in CompensatingTransaction

SUCCESS CRITERIA:
✅ All API calls use consistent retry logic
✅ Partial failures trigger compensating actions
✅ 90%+ coverage on new modules

DEPENDENCIES:
- REQUIRES TD2 (Config) merged
- Provides patterns for WS1, WS2, WS3

Ready? Create your plan.
```

---

### WS2: Batch Processing Pipeline (START DAY 2)

```
You are implementing Batch Processing Pipeline for autoD.

CONTEXT - READ THESE FIRST:
- WEEK_2_PLAN.md (Workstream 2)
- src/processor.py (current single-doc processing)

GOAL: Build high-volume batch processing with parallel execution over 4 days.

DELIVERABLES:

Day 2: Batch Upload Foundation
- BatchProcessor class (accept list of file paths)
- Batch validation before processing
- Batch tracking record
- Config: batch size 10-100, worker pool size

Day 3: Parallel Processing
- ThreadPoolExecutor for I/O-bound work
- Progress tracking (real-time ETA)
- Resource throttling
- 3-5x speedup vs sequential

Day 4: Batch Error Handling
- Partial batch failures
- Failed document retry
- Checkpoint progress for resumption

Day 5: Batch Integration
- E2E test: 100+ documents
- Performance benchmarking
- Documentation (BATCH_PROCESSING.md)

SUCCESS CRITERIA:
✅ Processes 100+ documents successfully
✅ 3-5x speedup vs sequential
✅ Graceful handling of partial failures

DEPENDENCIES:
- REQUIRES TD2 (Config) merged
- REQUIRES TD3 (API Client) merged on Day 5
- USE TD1 (Error Handling) patterns

Ready? Create your 4-day plan.
```

---

### TD3: API Client Refactoring (START DAY 4)

```
You are implementing API Client Refactoring for autoD.

CONTEXT - READ THESE FIRST:
- docs/TECHNICAL_DEBT_ANALYSIS.md (Section 1.2)
- src/api_client.py (current implementation)
- src/processor.py (API call patterns)

GOAL: Extract reusable retry logic and create ResponsesAPIClient base class.

DELIVERABLES:

1. ResponsesAPIClient base class:
   - Common retry logic (from TD1)
   - Circuit breaker pattern
   - Request/response logging
   - Cost tracking integration

2. Extract from processor.py:
   - Move API call logic to api_client.py
   - Remove duplication
   - Clean interfaces

3. Tests:
   - Unit tests for base class
   - Integration tests for circuit breaker
   - 85%+ coverage

SUCCESS CRITERIA:
✅ Zero duplication of retry logic
✅ Clean separation of concerns
✅ All API calls use base client

DEPENDENCIES:
- REQUIRES TD1 (Error Handling) merged
- REQUIRES TD2 (Config) merged
- Integrates with WS1 (vector store API calls)

Ready? Create your plan.
```

---

## Quality Gates (Before Each Merge)

### Wave 1 (Day 2): TD2 Config
- [ ] All 21 variables centralized
- [ ] Pydantic validation working
- [ ] pytest tests/unit/test_config.py -v passes
- [ ] mypy src/config.py passes

### Wave 2 (Day 3): TD1 + TD4
- [ ] Retry logic handles all errors (429, 500, timeout)
- [ ] CompensatingTransaction tests pass
- [ ] Coverage baseline: 55%+

### Wave 3 (Day 5): WS1 + TD3
- [ ] Vector search working
- [ ] Sub-500ms P95 latency
- [ ] 80%+ cache hit rate
- [ ] API client refactored

### Wave 4 (Day 6): WS2
- [ ] Batch processes 100+ docs
- [ ] 3x+ speedup
- [ ] Partial failure handling

### Wave 5 (Day 7): WS3 + Final
- [ ] Health checks <100ms
- [ ] Load test: 100 req/min
- [ ] Overall coverage: 60%+
- [ ] All documentation complete

---

## Progress Monitoring

**Check hourly:**
```bash
cd /Users/krisstudio/Developer/Projects/autoD

# TD2 (CRITICAL PATH)
cat ../autoD-config-management/progress.md

# Other workstreams
cat ../autoD-test-coverage/progress.md
cat ../autoD-vector-store/progress.md
cat ../autoD-production-hardening/progress.md
# etc.
```

---

## Success Metrics (By Day 7)

**Functional:**
- ✅ All 7 workstreams merged to main
- ✅ Vector search operational
- ✅ Batch processing handles 100+ docs
- ✅ Production monitoring active

**Quality:**
- ✅ 60%+ test coverage (up from 42%)
- ✅ Zero critical bugs
- ✅ All quality gates passed

**Performance:**
- ✅ Sub-2s P95 document processing
- ✅ Sub-500ms P95 vector search
- ✅ 3x+ batch speedup

---

## Next Steps

**Right Now:**
1. Open 4 terminal tabs
2. cd into each worktree directory
3. Run `claude` in each
4. Copy-paste the prompts above

**Tomorrow (Day 2):**
1. Merge TD2 (Config) in morning
2. Launch TD1 and WS2 in afternoon

**Continue through Day 7**

---

**Status:** Ready to execute 🚀
**Your role:** Project manager coordinating 7 parallel Claude sessions
