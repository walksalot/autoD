# Parallel Execution Strategy: Git Worktrees + Multi-Claude Delegation

**Status**: ✅ Active
**Created**: 2025-10-16
**Updated**: 2025-10-16
**Reference**: [Claude Code Best Practices - Git Worktrees](https://www.anthropic.com/research/claude-code-best-practices#git-worktrees)

---

## Executive Summary

This document defines the parallel execution strategy for implementing Week 1 of the 4-week iterative plan using **Git worktrees** and **multiple Claude Code sessions** working concurrently. Instead of sequential implementation, we enable 3-4 Claude instances to work simultaneously on independent components, coordinated through integration checkpoints.

### Why Git Worktrees?

**Git worktrees enable you to run multiple Claude sessions simultaneously on different parts of your project, each focused on its own independent task.** ([Source](https://www.anthropic.com/research/claude-code-best-practices#git-worktrees))

**Benefits**:
1. **Faster Delivery**: Week 1 components completed in ~7 days instead of sequential approach
2. **Isolation**: Each worktree provides clean development environment without conflicts
3. **Reversibility**: Easy to abandon a worktree if approach fails
4. **Early Integration**: Problems discovered incrementally at Days 3, 5, 7
5. **Resource Efficiency**: Shared git history, separate working directories

---

## Architecture Overview

### Worktree Structure

```
autoD/ (main development directory - "project manager" terminal)
├── .git/ (shared git repository)
├── process_inbox.py (current 138-line sandbox)
├── docs/
└── README.md

../autoD-database-pipeline/ (Worktree 1 - Terminal Tab 1)
├── .git → points to autoD/.git (shared history)
├── src/models.py (NEW)
├── src/pipeline.py (NEW)
├── src/stages/ (NEW)
└── tests/test_models.py, tests/test_pipeline.py

../autoD-retry-error-handling/ (Worktree 2 - Terminal Tab 2)
├── .git → points to autoD/.git (shared history)
├── src/retry.py (NEW)
├── src/transactions.py (NEW)
└── tests/test_retry.py, tests/test_transactions.py

../autoD-token-tracking/ (Worktree 3 - Terminal Tab 3)
├── .git → points to autoD/.git (shared history)
├── src/token_counter.py (NEW)
├── src/cost_calculator.py (NEW)
└── tests/test_token_counter.py, tests/test_cost_calculator.py

../autoD-testing/ (Worktree 4 - Terminal Tab 4)
├── .git → points to autoD/.git (shared history)
├── tests/conftest.py (NEW)
├── tests/fixtures/ (NEW)
└── tests/mocks/ (NEW)
```

### Terminal Setup

**Best Practice**: Maintain one terminal tab per worktree + one for project management

**Recommended iTerm2 Setup** (macOS):
- **Tab 1**: Project manager (autoD/) - coordination and integration
- **Tab 2**: Workstream 1 (database-pipeline) - Claude session 1
- **Tab 3**: Workstream 2 (retry-error-handling) - Claude session 2
- **Tab 4**: Workstream 3 (token-tracking) - Claude session 3
- **Tab 5**: Workstream 4 (testing) - Claude session 4

**iTerm2 Notifications**: Enable notifications for when Claude needs attention:
- iTerm2 > Preferences > Profiles > Terminal > Notifications > "Notify on next mark"

---

## Four Parallel Workstreams

### Workstream 1: Database + Pipeline Foundation

**Worktree Path**: `../autoD-database-pipeline`
**Branch**: `workstream/database-pipeline`
**Duration**: 8-12 hours (Day 0-3)
**Dependencies**: None (can start immediately)
**Terminal Tab**: #2

#### Claude Session Instructions

**Setup Commands**:
```bash
# From autoD/
git worktree add ../autoD-database-pipeline -b workstream/database-pipeline
cd ../autoD-database-pipeline
claude
```

**Initial Prompt** (use "ultrathink" for complex planning):
```
ultrathink: You are implementing the Database + Pipeline Foundation for the autoD project.

CONTEXT - READ THESE FIRST:
- docs/CODE_ARCHITECTURE.md (sections 3-4: Database Models, Pipeline Pattern)
- docs/IMPLEMENTATION_ROADMAP.md (Week 1: Core Pipeline section)
- AGENTS.md (repository conventions)

WORKFLOW (follow "Explore, Plan, Code, Commit" pattern):
1. EXPLORE: Read the files above to understand architecture
2. PLAN: Create a detailed implementation plan. DO NOT CODE YET. Show me the plan first.
3. CODE: After I approve the plan, implement it incrementally
4. COMMIT: Create commits with descriptive messages as you complete major components

DELIVERABLES:
1. SQLAlchemy Document model with generic JSON type (NOT JSONB)
2. Pipeline pattern infrastructure (ProcessingContext, ProcessingStage ABC, Pipeline orchestrator)
3. Five pipeline stages:
   - ComputeSHA256Stage: File hashing (hashlib.sha256)
   - DedupeCheckStage: Database deduplication query
   - UploadToFilesAPIStage: Upload PDF to OpenAI Files API
   - CallResponsesAPIStage: Extract metadata via Responses API
   - PersistToDBStage: Save to database
4. Unit tests with 80%+ coverage

SUCCESS CRITERIA:
✅ Document table created with Alembic migration
✅ Pipeline processes 1 PDF end-to-end without errors
✅ SHA-256 deduplication prevents duplicates (test with identical PDFs)
✅ All 5 stages execute in correct order
✅ Unit tests pass: pytest tests/ -v
✅ Type checking passes: mypy src/

IMPORTANT:
- Use docs/CODE_ARCHITECTURE.md as your implementation guide (copy patterns exactly)
- NEVER use JSONB type - use generic JSON type for SQLite compatibility
- Follow PEP 8 and black formatting
- DO NOT implement retry logic (that's Workstream 2)
- DO NOT implement token tracking (that's Workstream 3)

INTEGRATION CHECKPOINT: Day 3
You'll merge with Workstream 4 (testing infrastructure) to create the foundation branch.

Ready to begin? Start by reading the docs and creating your plan.
```

#### Best Practices for This Workstream

**Be Specific**: Instead of "add deduplication", say:
> "Implement DedupeCheckStage that queries the Document table using session.query(Document).filter_by(sha256_hex=ctx.sha256_hex).first(). If a record exists, set ctx.is_duplicate=True and ctx.existing_doc_id to the ID. If not, set ctx.is_duplicate=False. Include a unit test that processes the same PDF twice and verifies only one record exists."

**Use /clear Frequently**: Between major components (after models, after pipeline pattern, after each stage), run /clear to keep context focused.

**Course Correct Early**: If Claude starts implementing retry logic or token tracking, interrupt (Escape) and redirect:
> "Stop - retry logic belongs in Workstream 2. Focus only on the pipeline pattern for now."

#### Progress Tracking

Create `progress.md` in the worktree:
```markdown
# Workstream 1: Database + Pipeline

**Status**: 🟢 On Track
**Progress**: 5/10 tasks complete (50%)
**ETA**: Day 3 (on schedule)

## Completed
- ✅ Read docs/CODE_ARCHITECTURE.md sections 3-4
- ✅ Read docs/IMPLEMENTATION_ROADMAP.md Week 1
- ✅ Created implementation plan (approved)
- ✅ Implemented SQLAlchemy Document model
- ✅ Created Alembic migration for Document table

## In Progress
- 🔄 Implementing Pipeline pattern (70% done)

## Pending
- ⏳ ComputeSHA256Stage
- ⏳ DedupeCheckStage
- ⏳ UploadToFilesAPIStage
- ⏳ CallResponsesAPIStage

## Blockers
- None

## Next Steps
1. Finish Pipeline pattern
2. Run tests to verify Document model works
3. Implement SHA-256 stage
```

Update this file hourly and post updates to project manager terminal.

---

### Workstream 2: Retry Logic + Error Handling

**Worktree Path**: `../autoD-retry-error-handling`
**Branch**: `workstream/retry-error-handling`
**Duration**: 6-8 hours (Day 0-5)
**Dependencies**: Minimal (config patterns only - can run parallel with Workstream 1)
**Terminal Tab**: #3

#### Claude Session Instructions

**Setup Commands**:
```bash
# From autoD/
git worktree add ../autoD-retry-error-handling -b workstream/retry-error-handling
cd ../autoD-retry-error-handling
claude
```

**Initial Prompt**:
```
ultrathink: You are implementing Retry Logic + Error Handling for the autoD project.

CONTEXT - READ THESE FIRST:
- docs/CODE_ARCHITECTURE.md (sections 5-7: Retry Logic, Transaction Safety, Structured Logging)
- docs/IMPLEMENTATION_ROADMAP.md (Week 2: Resilience section)
- docs/CHANGES_FROM_ORIGINAL_PLAN.md (Critical Flaw #4: Incomplete Retry Logic)

WORKFLOW (follow "Explore, Plan, Code, Commit" pattern):
1. EXPLORE: Read the files above, especially the "before/after" examples
2. PLAN: Create implementation plan. DO NOT CODE YET.
3. CODE: After approval, implement incrementally
4. COMMIT: Commit after each major component

DELIVERABLES:
1. Comprehensive retry logic (src/retry.py):
   - is_retryable_api_error() predicate function
   - Handles ALL transient errors: timeouts, 5xx, rate limits, connection errors
   - @retry decorator using tenacity library
   - Exponential backoff: 2-60 seconds, max 5 attempts

2. Compensating transaction pattern (src/transactions.py):
   - CompensatingTransaction context manager
   - Rollback handlers for Files API uploads
   - Database transaction safety
   - Audit trail for partial failures

3. Structured JSON logging (src/logging_config.py):
   - JSONFormatter for machine-readable logs
   - Stage transition logging
   - Error logging with stack traces
   - Performance metrics logging

4. Unit tests with 70%+ coverage

SUCCESS CRITERIA:
✅ Retry logic handles all transient API errors (test with mock failures)
✅ Compensating transactions prevent data loss on partial failures
✅ Structured logs capture all stage transitions (verify JSON format)
✅ 95%+ success rate under simulated API failures
✅ pytest tests/ -v passes
✅ mypy src/ passes

IMPORTANT:
- Follow docs/CODE_ARCHITECTURE.md examples EXACTLY (especially retry predicate)
- Include ALL error types: RateLimitError, APIConnectionError, Timeout, APIError (5xx)
- DO NOT assume async - use synchronous code for now
- DO NOT implement database models (that's Workstream 1)
- DO NOT implement token tracking (that's Workstream 3)

INTEGRATION CHECKPOINT: Day 5
You'll merge into the foundation branch (after Workstream 1 + 4 merge on Day 3).

Ready? Start by reading the docs and creating your plan.
```

#### Best Practices

**Give Claude Images**: If you have diagrams of the retry flow or transaction pattern, drag them into the Claude session.

**Use Checklists**: For the retry logic, create a checklist in the worktree:
```markdown
# Retry Logic Implementation Checklist

## Error Types to Handle
- [ ] RateLimitError - rate limit exceeded
- [ ] APIConnectionError - network connectivity issues
- [ ] Timeout - request timeout
- [ ] APIError with status_code >= 500 (5xx errors)

## Test Cases
- [ ] Simulated 429 (rate limit) → retries 5 times
- [ ] Simulated 500 (internal server error) → retries 5 times
- [ ] Simulated timeout → retries 5 times
- [ ] Simulated connection error → retries 5 times
- [ ] Non-retryable error (400, 401, 404) → fails immediately

## Validation
- [ ] Exponential backoff uses 2-60 second range
- [ ] Maximum 5 retry attempts
- [ ] Logs show retry attempts with timestamps
```

Tell Claude to work through this checklist systematically, checking off items as it completes them.

---

### Workstream 3: Token Tracking + Cost Monitoring

**Worktree Path**: `../autoD-token-tracking`
**Branch**: `workstream/token-tracking`
**Duration**: 4-6 hours (Day 0-7)
**Dependencies**: Minimal (config patterns only - can run parallel with all)
**Terminal Tab**: #4

#### Claude Session Instructions

**Setup Commands**:
```bash
# From autoD/
git worktree add ../autoD-token-tracking -b workstream/token-tracking
cd ../autoD-token-tracking
claude
```

**Initial Prompt**:
```
You are implementing Token Tracking + Cost Monitoring for the autoD project.

CONTEXT - READ THESE FIRST:
- docs/CODE_ARCHITECTURE.md (section 8: Token Tracking)
- docs/IMPLEMENTATION_ROADMAP.md (Week 3: Observability section)
- docs/how_to_count_tokens_w_tik_tok_token.md (tiktoken guide)

WORKFLOW:
1. READ: Read the files above
2. PLAN: Create implementation plan (be specific about tiktoken encoding choice)
3. CODE: Implement incrementally
4. TEST: Verify accuracy with sample PDFs

DELIVERABLES:
1. Token counting with tiktoken (src/token_counter.py):
   - count_tokens() using o200k_base encoding (GPT-5)
   - Developer prompt token counting (track cached tokens separately)
   - PDF content estimation
   - Structured output overhead calculation

2. Cost calculation (src/cost_calculator.py):
   - GPT-5 pricing constants: $10 per 1M input, $30 per 1M output
   - Prompt caching discount: 10% cost for cached tokens
   - Per-PDF cost tracking
   - Cumulative cost reporting functions

3. Logging integration (src/token_logging.py):
   - Add token metrics to structured logs (prompt_tokens, output_tokens, cached_tokens)
   - Add cost metrics (input_cost_usd, output_cost_usd, total_cost_usd)
   - Add performance metrics (duration_ms, throughput_pdfs_per_hour)

4. Unit tests with 90%+ coverage

SUCCESS CRITERIA:
✅ Token counts accurate within 5% of OpenAI's reported usage
✅ Cost calculations correct for GPT-5 pricing model
✅ Caching savings calculated correctly (10% of cached tokens)
✅ Logs include all token/cost metrics in JSON format
✅ pytest tests/ -v passes with 90%+ coverage
✅ mypy src/ passes

IMPORTANT:
- Use o200k_base encoding (NOT cl100k_base - that's for GPT-4)
- Verify pricing constants match current OpenAI pricing
- DO NOT implement database models (Workstream 1)
- DO NOT implement retry logic (Workstream 2)
- DO NOT implement pipeline orchestration (Workstream 1)

INTEGRATION CHECKPOINT: Day 7
Final merge before deploying Week 1 to main branch.

Ready? Read the docs and show me your plan.
```

#### Best Practices

**Pass Data into Claude**: If you have sample PDFs with known token counts, pass them in:
```bash
# In the worktree terminal
cat <<EOF > sample_pdf_token_counts.csv
pdf_filename,expected_tokens,source
sample_invoice.pdf,1523,openai_playground
sample_receipt.pdf,892,openai_playground
EOF
```

Then tell Claude:
> "Use sample_pdf_token_counts.csv to validate your token counting accuracy. Your count_tokens() function should match these values within 5%."

---

### Workstream 4: Test Infrastructure

**Worktree Path**: `../autoD-testing`
**Branch**: `workstream/testing`
**Duration**: 6-8 hours (Day 0-7)
**Dependencies**: None (fully parallel - can run alongside all others)
**Terminal Tab**: #5

#### Claude Session Instructions

**Setup Commands**:
```bash
# From autoD/
git worktree add ../autoD-testing -b workstream/testing
cd ../autoD-testing
claude
```

**Initial Prompt**:
```
You are implementing Test Infrastructure for the autoD project.

CONTEXT - READ THESE FIRST:
- docs/CODE_ARCHITECTURE.md (section 10: Testing Patterns)
- docs/IMPLEMENTATION_ROADMAP.md (Week 1-3: Testing sections)

WORKFLOW (follow "Write Tests, Commit; Code, Iterate, Commit" - TDD):
1. READ: Understand testing patterns from CODE_ARCHITECTURE.md
2. PLAN: Design test infrastructure (fixtures, mocks, utilities)
3. CODE: Build test infrastructure incrementally
4. VALIDATE: Run tests to ensure infrastructure works

DELIVERABLES:
1. pytest configuration (tests/conftest.py):
   - Database fixtures (in-memory SQLite for fast tests)
   - Mock OpenAI client (returns realistic responses without API calls)
   - Sample PDF fixtures (invoice, receipt, multi-page document)
   - Test environment setup/teardown

2. Mock patterns (tests/mocks/):
   - mock_openai.py: Mock Responses API with realistic metadata
   - mock_files_api.py: Mock Files API for upload/download
   - mock_vector_store.py: Mock vector store operations
   - Error simulation utilities (RateLimitError, Timeout, APIError)

3. Test fixtures (tests/fixtures/):
   - Generate sample PDFs programmatically (don't commit actual PDFs to git)
   - Expected metadata JSON for each sample PDF
   - SHA-256 hash values for deduplication tests
   - API response templates

4. Test utilities (tests/utils.py):
   - create_test_pdf() - Generate PDFs on-demand
   - assert_document_equal() - Compare database records
   - capture_logs() - Log assertion helper
   - simulate_api_error() - Error injection for retry testing

SUCCESS CRITERIA:
✅ pytest runs with all fixtures working (pytest tests/ -v)
✅ Mock OpenAI client returns realistic structured output
✅ Test PDFs generate correct SHA-256 hashes
✅ Database fixtures support parallel test execution (pytest -n auto)
✅ Test utilities simplify test authoring
✅ All fixtures documented with examples

IMPORTANT:
- DO NOT create mock implementations of business logic (that's tested, not mocked)
- DO create mock implementations of external APIs (OpenAI, vector stores)
- Follow pytest best practices (use fixtures, not setUp/tearDown)
- Ensure tests are deterministic (no random data without seed)

INTEGRATION CHECKPOINT: Day 3
Merge with Workstream 1 to enable testing pipeline implementation immediately.

Ready? Read the docs and create your plan.
```

#### Best Practices

**Write Tests, Commit; Code, Iterate, Commit** (TDD):
1. Have Claude write test infrastructure first
2. Run tests to confirm they work (even if they're testing mocks)
3. Commit the test infrastructure
4. Use these fixtures in Workstream 1, 2, 3 as they integrate

**Visual Targets**: If you have screenshots of test output or coverage reports you want to match, drag them into Claude:
> "Here's a screenshot of our ideal test output format. Make the test utilities produce output that looks like this."

---

## Project Manager Coordination

### Role and Responsibilities

The **project manager** runs in the main `autoD/` directory (Terminal Tab #1) and is responsible for:

1. **Creating Worktrees** - Initialize all 4 worktrees on Day 0
2. **Monitoring Progress** - Check `progress.md` files hourly
3. **Coordinating Integration** - Manage merges on Day 3, 5, 7
4. **Resolving Conflicts** - Handle merge conflicts between worktrees
5. **Quality Assurance** - Verify quality gates before merging
6. **Communication** - Keep all workstreams informed

### Daily Standup Protocol

**Day 0: Kickoff**
```bash
# Terminal Tab #1 (project manager in autoD/)
# Create all worktrees
git worktree add ../autoD-database-pipeline -b workstream/database-pipeline
git worktree add ../autoD-retry-error-handling -b workstream/retry-error-handling
git worktree add ../autoD-token-tracking -b workstream/token-tracking
git worktree add ../autoD-testing -b workstream/testing

# Verify worktrees
git worktree list

# Expected output:
# /path/to/autoD                           abc1234 [main]
# /path/to/autoD-database-pipeline         def5678 [workstream/database-pipeline]
# /path/to/autoD-retry-error-handling      ghi9012 [workstream/retry-error-handling]
# /path/to/autoD-token-tracking            jkl3456 [workstream/token-tracking]
# /path/to/autoD-testing                   mno7890 [workstream/testing]
```

**Communicate to all workstreams**:
> "All 4 worktrees created successfully. You can start work. Remember:
> - Workstream 1 + 4 will merge on Day 3
> - Workstream 2 will merge on Day 5
> - Workstream 3 will merge on Day 7
> - Use /clear frequently to keep context focused
> - Be specific in your instructions to Claude
> - Post updates to your progress.md hourly"

**Day 1-2: Monitor Progress**

Check each worktree's progress:
```bash
# Terminal Tab #1 (project manager)
cat ../autoD-database-pipeline/progress.md
cat ../autoD-retry-error-handling/progress.md
cat ../autoD-token-tracking/progress.md
cat ../autoD-testing/progress.md
```

Identify blockers and adjust timeline if needed.

**Day 3: Foundation Integration**

**Merge**: `workstream/database-pipeline` + `workstream/testing` → `integration/week1-foundation`

```bash
# Terminal Tab #1 (project manager in autoD/)
git checkout -b integration/week1-foundation

# Merge Workstream 4 (testing) first - provides fixtures for pipeline
git merge workstream/testing --no-ff -m "Merge Workstream 4: Test Infrastructure"

# Run tests to ensure fixtures work
pytest tests/ -v

# Merge Workstream 1 (database + pipeline)
git merge workstream/database-pipeline --no-ff -m "Merge Workstream 1: Database + Pipeline"

# Resolve conflicts if any (likely in tests/conftest.py)
# Keep both test fixtures and pipeline tests

# Quality Gate
pytest tests/ -v --cov=src --cov-report=term
# Expected: 60%+ coverage, all tests pass

# Integration Test
python -m src.pipeline  # Process 1 PDF end-to-end
# Expected: PDF processed, record in database, no duplicates

# Tag milestone
git tag week1-day3-foundation-integrated
```

**Communicate success**:
> "🎉 Day 3 Integration Complete!
> ✅ Workstream 1 (Database + Pipeline) + Workstream 4 (Testing) merged successfully
> ✅ 65% test coverage
> ✅ Pipeline processes 1 PDF end-to-end
> ✅ SHA-256 deduplication working
>
> Workstream 2 and 3: You can now merge the foundation branch into your worktrees to get the latest code:
> ```
> cd ../autoD-retry-error-handling
> git merge integration/week1-foundation
> ```
>
> Next checkpoint: Day 5 (Workstream 2 merge)"

**Day 5: Retry Logic Integration**

**Merge**: `workstream/retry-error-handling` → `integration/week1-foundation`

```bash
# Terminal Tab #1 (project manager in autoD/)
git checkout integration/week1-foundation

# Merge Workstream 2 (retry logic + error handling)
git merge workstream/retry-error-handling --no-ff -m "Merge Workstream 2: Retry Logic + Error Handling"

# Resolve conflicts (likely in src/pipeline.py if retry decorators added)
# Keep retry decorators, ensure backward compatibility

# Quality Gate
pytest tests/ -v --cov=src --cov-report=term
# Expected: 70%+ coverage, all tests pass including retry tests

# Integration Test: Simulate API failures
python -m tests.test_retry  # Test retry logic with mock failures
# Expected: 95%+ success rate, 5 retry attempts on transient errors

# Tag milestone
git tag week1-day5-retry-integrated
```

**Day 7: Final Integration**

**Merge**: `workstream/token-tracking` → `integration/week1-foundation` → `main`

```bash
# Terminal Tab #1 (project manager in autoD/)
git checkout integration/week1-foundation

# Merge Workstream 3 (token tracking)
git merge workstream/token-tracking --no-ff -m "Merge Workstream 3: Token Tracking + Cost Monitoring"

# Resolve conflicts (likely in src/logging_config.py)
# Combine logging fields

# Quality Gate
pytest tests/ -v --cov=src --cov-report=term
# Expected: 75%+ coverage, all tests pass

# Integration Test: Process 100 PDFs
python process_inbox.py  # Process 100 test PDFs
# Expected:
# - 100 PDFs in database
# - Zero duplicates (test with 10 duplicate PDFs)
# - Token counts accurate within 5%
# - Cost calculations correct
# - Structured logs show all metrics

# Tag Week 1 completion
git tag week1-complete

# Merge to main
git checkout main
git merge integration/week1-foundation --no-ff -m "Week 1 Complete: Core Pipeline + Retry + Token Tracking"
git push origin main --tags
```

**Celebrate**:
> "🎉🎉🎉 Week 1 Complete!
> ✅ All 4 workstreams integrated successfully
> ✅ 76% test coverage
> ✅ 100 PDFs processed, zero duplicates
> ✅ 95%+ API success rate with retry logic
> ✅ Token tracking and cost monitoring working
> ✅ Structured logs capturing all metrics
>
> Total time: 7 days (with 4 parallel Claude sessions)
> vs. Estimated sequential time: 5 days (but with 1 agent only)
>
> Benefit: Multiple agents learning and validating in parallel, earlier integration feedback
>
> Ready for Week 2!"

---

## Integration Checkpoints

### Day 3: Foundation Integration

**What Gets Merged**:
- Workstream 1: Database models, pipeline pattern, 5 pipeline stages
- Workstream 4: Test fixtures, mock patterns, test utilities

**Why Together**: Testing infrastructure provides immediate validation for pipeline implementation. This creates a testable foundation.

**Quality Gates**:
- ✅ All unit tests pass (`pytest tests/ -v`)
- ✅ Test coverage 60%+ (`pytest --cov=src --cov-report=term`)
- ✅ Pipeline processes 1 PDF successfully
- ✅ SHA-256 deduplication works (test with duplicate PDF)
- ✅ Type checking passes (`mypy src/`)
- ✅ Linting passes (`black src/ tests/ --check`)

**Rollback Procedure**:
```bash
# If integration fails quality gates
git reset --hard HEAD~1  # Undo merge
# Fix issues in worktrees
# Retry merge
```

### Day 5: Retry Logic Integration

**What Gets Merged**:
- Workstream 2: Retry logic, compensating transactions, structured logging

**Why Now**: Foundation is solid (Day 3 validated), now add resilience layer.

**Quality Gates**:
- ✅ All unit tests pass (including retry tests)
- ✅ Test coverage 70%+
- ✅ Pipeline survives simulated API failures (95%+ success rate)
- ✅ Retry logic triggers 5 attempts on transient errors
- ✅ Compensating transactions prevent data loss
- ✅ Structured logs show retry attempts

**Rollback Procedure**: Same as Day 3

### Day 7: Final Integration

**What Gets Merged**:
- Workstream 3: Token tracking, cost calculation, logging integration

**Why Last**: This is "observability layer" - doesn't affect core functionality, safe to add last.

**Quality Gates**:
- ✅ All unit tests pass (including token tracking tests)
- ✅ Test coverage 75%+
- ✅ 100 PDFs processed successfully
- ✅ Token counts accurate within 5% of OpenAI's reported usage
- ✅ Cost calculations correct
- ✅ Logs include token/cost metrics

**Final Validation**:
```bash
# Process real PDFs (not test data)
python process_inbox.py

# Check results
sqlite3 database.db "SELECT COUNT(*), SUM(metadata_json->>'total_cost_usd') FROM documents;"
# Expected: 100 PDFs, total cost < $50

# Check logs
grep "total_cost_usd" logs/app.log | jq '.total_cost_usd' | awk '{sum+=$1} END {print sum}'
# Expected: Matches database sum
```

**Merge to Main**: After all quality gates pass, merge to main and tag `week1-complete`.

---

## Conflict Resolution Strategy

### Common Conflict Scenarios

**Scenario 1: Both Workstream 1 and 2 modify `src/pipeline.py`**

**Workstream 1 Version**:
```python
class Pipeline:
    def process(self, context: ProcessingContext) -> ProcessingContext:
        for stage in self.stages:
            context = stage.execute(context)
        return context
```

**Workstream 2 Version**:
```python
class Pipeline:
    @retry(retry=retry_if_exception(is_retryable_api_error))
    def process(self, context: ProcessingContext) -> ProcessingContext:
        for stage in self.stages:
            context = stage.execute(context)
        return context
```

**Resolution**: Keep Workstream 2's version (adds retry decorator without breaking Workstream 1's logic).

**Scenario 2: Workstream 2 and 3 both modify `src/logging_config.py`**

**Workstream 2 Version** (adds stage transition logging):
```python
def format(self, record):
    log_obj = {
        "timestamp": datetime.utcnow().isoformat(),
        "level": record.levelname,
        "message": record.getMessage(),
        "stage": getattr(record, 'stage', None),
    }
    return json.dumps(log_obj)
```

**Workstream 3 Version** (adds token/cost metrics):
```python
def format(self, record):
    log_obj = {
        "timestamp": datetime.utcnow().isoformat(),
        "level": record.levelname,
        "message": record.getMessage(),
        "prompt_tokens": getattr(record, 'prompt_tokens', None),
        "output_tokens": getattr(record, 'output_tokens', None),
        "cost_usd": getattr(record, 'cost_usd', None),
    }
    return json.dumps(log_obj)
```

**Resolution**: Combine both (keep all fields):
```python
def format(self, record):
    log_obj = {
        "timestamp": datetime.utcnow().isoformat(),
        "level": record.levelname,
        "message": record.getMessage(),
        "stage": getattr(record, 'stage', None),  # From Workstream 2
        "prompt_tokens": getattr(record, 'prompt_tokens', None),  # From Workstream 3
        "output_tokens": getattr(record, 'output_tokens', None),
        "cost_usd": getattr(record, 'cost_usd', None),
    }
    return json.dumps(log_obj)
```

### Conflict Resolution Protocol

1. **Detect**: Git identifies merge conflicts during `git merge`
2. **Analyze**: Project manager reviews both versions
3. **Consult**: If unclear, ask workstream owners (in their terminal tabs)
4. **Decide**: Choose one version, or combine both, or write new version
5. **Test**: Run tests to ensure conflict resolution didn't break anything
6. **Document**: If significant, create ADR documenting the decision
7. **Communicate**: Notify affected workstreams of the resolution

### Rollback Strategy

If any integration fails quality gates:

**Step 1**: Undo merge
```bash
git reset --hard HEAD~1
```

**Step 2**: Notify workstream owner
```bash
# In workstream terminal tab
echo "Integration failed quality gate: retry tests failing. Please fix and re-merge."
```

**Step 3**: Fix in worktree
```bash
# Workstream owner fixes issue in their worktree
cd ../autoD-retry-error-handling
# Fix bug
pytest tests/  # Verify fix
git commit -am "fix: Retry logic edge case"
```

**Step 4**: Retry integration
```bash
# Project manager retries merge
cd autoD/
git checkout integration/week1-foundation
git merge workstream/retry-error-handling
pytest tests/  # NOW PASSES ✅
```

---

## Best Practices (from Claude Code Guide)

### 1. Be Specific in Instructions

**Poor**: "add tests for foo.py"
**Good**: "write a new test case for foo.py, covering the edge case where the user is logged out. avoid mocks. test the actual database query."

**Poor**: "why does the pipeline fail?"
**Good**: "run the pipeline with a sample PDF and capture logs. examine logs to identify which stage failed and why. check if it's a transient error (retry should fix) or a bug (needs code fix)."

**Poor**: "add token tracking"
**Good**: "implement count_tokens() in src/token_counter.py using tiktoken with o200k_base encoding. The function should accept a string and return the integer token count. Include a unit test that verifies accuracy within 5% using sample_pdf_token_counts.csv."

### 2. Use /clear Frequently

During long sessions, Claude's context window can fill with irrelevant content. Use `/clear` between major tasks:

- After completing database models, before starting pipeline pattern
- After completing each pipeline stage
- Before starting integration testing
- After resolving merge conflicts

### 3. Course Correct Early and Often

**Tools for Course Correction**:

1. **Ask for a Plan**: "Create a plan for implementing retry logic. DO NOT CODE YET."
2. **Press Escape**: Interrupt Claude mid-tool-call to redirect
3. **Double-tap Escape**: Jump back in history, edit previous prompt
4. **Ask to Undo**: "Undo the last file edit and take a different approach"

**Example**:
```
Claude: *starts implementing retry logic in Workstream 1*
You: [Press Escape] "Stop - retry logic belongs in Workstream 2. Focus on the pipeline pattern only."
```

### 4. Use Checklists for Complex Workflows

Create Markdown checklists in worktrees for systematic work:

**Example**: `../autoD-database-pipeline/implementation_checklist.md`
```markdown
# Database + Pipeline Implementation Checklist

## Database Models
- [ ] Document table with all 15 fields
- [ ] SHA-256 unique index
- [ ] Generic JSON type (not JSONB)
- [ ] Alembic migration created
- [ ] Migration tested (upgrade + downgrade)

## Pipeline Pattern
- [ ] ProcessingContext dataclass with all fields
- [ ] ProcessingStage ABC with execute() method
- [ ] Pipeline orchestrator
- [ ] Error handling in pipeline loop

## Pipeline Stages
- [ ] ComputeSHA256Stage implemented
- [ ] DedupeCheckStage implemented
- [ ] UploadToFilesAPIStage implemented
- [ ] CallResponsesAPIStage implemented
- [ ] PersistToDBStage implemented

## Testing
- [ ] Unit tests for Document model
- [ ] Unit tests for each pipeline stage
- [ ] Integration test for full pipeline
- [ ] Coverage 80%+

## Quality Gates
- [ ] pytest tests/ -v passes
- [ ] mypy src/ passes
- [ ] black src/ tests/ --check passes
```

Tell Claude: "Work through this checklist systematically. Check off each item as you complete it. Update the checklist file after each task."

### 5. Give Claude URLs and Images

**URLs**: Paste doc links for Claude to read:
```
Read https://platform.openai.com/docs/api-reference/files and implement UploadToFilesAPIStage following the exact API structure shown.
```

**Images**: Drag screenshots or diagrams:
```
Here's a diagram of the pipeline flow. Implement the Pipeline class to match this architecture exactly.
[drag diagram.png]
```

### 6. Use Auto-Accept Mode Carefully

**Shift+Tab**: Toggle auto-accept mode (Claude works autonomously without asking for permission)

**When to Use**:
- Fixing lint errors (low risk)
- Running tests (read-only)
- Implementing well-specified tasks

**When NOT to Use**:
- Making architectural decisions
- Modifying shared code (e.g., pipeline pattern used by other workstreams)
- First-time implementations

---

## Risk Management

### Identified Risks

**Risk 1**: Merge conflicts too complex to resolve
**Mitigation**: Clear file ownership, daily coordination
**Contingency**: Sequential fallback (merge one workstream at a time)

**Risk 2**: One workstream blocks on dependency
**Mitigation**: Minimal inter-workstream dependencies
**Contingency**: Provide stub implementations until real code ready

**Risk 3**: Quality gate failures delay integration
**Mitigation**: Sub-agents run tests locally before declaring complete
**Contingency**: Extend timeline by 1-2 days for fixes

**Risk 4**: Git worktree confusion (Claude modifies wrong directory)
**Mitigation**: Clear directory naming, terminal tab labels
**Contingency**: Revert incorrect changes, re-do work in correct worktree

**Risk 5**: Integration branch becomes unstable
**Mitigation**: Only merge after quality gates pass
**Contingency**: Reset integration branch, start over with sequential merges

### Risk Monitoring

**Daily Risk Assessment**:
```bash
# Project manager checks each worktree
for worktree in database-pipeline retry-error-handling token-tracking testing; do
    echo "=== $worktree ==="
    cat ../autoD-$worktree/progress.md | grep -E "(Status|Blockers)"
done
```

Identify:
- 🔴 Blocked workstreams (need help)
- 🟡 At-risk workstreams (behind schedule)
- 🟢 On-track workstreams (proceeding normally)

**Escalation Path**:
1. Workstream identifies blocker → Notify project manager
2. Project manager assesses impact → Adjust plan or get help
3. Major risk (>2 days delay) → Escalate to user for decision

---

## Success Metrics

### Week 1 Completion Criteria

**Functional**:
- ✅ Pipeline processes 100 PDFs successfully
- ✅ Zero duplicate records in database
- ✅ 95%+ API success rate with retry logic
- ✅ Token counts accurate within 5%
- ✅ Cost tracking working correctly

**Quality**:
- ✅ 75%+ test coverage
- ✅ All tests pass
- ✅ Type checking passes
- ✅ Linting passes
- ✅ Structured logs capture all metrics

**Process**:
- ✅ All 4 workstreams merged cleanly
- ✅ < 5 merge conflicts total
- ✅ < 2 rollbacks required
- ✅ Integration checkpoints met on schedule

### Performance Metrics

**Development Time**: ~7 days (4 parallel Claude sessions)
vs. Sequential: ~5 days (1 agent only)

**Benefit**: Multiple perspectives, early integration feedback, distributed learning

**Agent Utilization**: 4 Claudes working simultaneously (4x parallelism)

**Integration Success**: 3 integration checkpoints (Day 3, 5, 7)

---

## Cleanup and Next Steps

### Cleanup After Week 1

**Remove Worktrees** (keep branches for reference):
```bash
# After successfully merging to main
git worktree remove ../autoD-database-pipeline
git worktree remove ../autoD-retry-error-handling
git worktree remove ../autoD-token-tracking
git worktree remove ../autoD-testing

# Verify removal
git worktree list
# Should show only main directory

# Keep branches for reference (don't delete)
git branch
# workstream/database-pipeline
# workstream/retry-error-handling
# workstream/token-tracking
# workstream/testing
```

**Why Keep Branches**: Historical record of parallel development, useful for post-mortem analysis.

### Week 2 Parallel Strategy

Apply same pattern to Week 2 components:

**Workstream 5**: Vector Store Integration
**Workstream 6**: Alembic Migrations
**Workstream 7**: PostgreSQL Migration
**Workstream 8**: Performance Optimization

**Setup**:
```bash
git worktree add ../autoD-vector-store -b workstream/vector-store
git worktree add ../autoD-alembic -b workstream/alembic
git worktree add ../autoD-postgres -b workstream/postgres-migration
git worktree add ../autoD-performance -b workstream/performance
```

---

## Tools and Commands Reference

### Git Worktree Commands

```bash
# Create worktree with new branch
git worktree add <path> -b <branch-name>

# Example
git worktree add ../autoD-database-pipeline -b workstream/database-pipeline

# List all worktrees
git worktree list

# Remove worktree (keeps branch)
git worktree remove <path>

# Prune deleted worktrees from metadata
git worktree prune

# Move worktree to new location
git worktree move <old-path> <new-path>
```

### Integration Commands

```bash
# Create integration branch
git checkout -b integration/week1-foundation

# Merge with no fast-forward (preserves history)
git merge workstream/database-pipeline --no-ff -m "Merge Workstream 1: Database + Pipeline"

# Check for conflicts
git status

# Abort merge (if conflicts too complex)
git merge --abort

# Continue after resolving conflicts
git merge --continue

# Tag milestone
git tag week1-day3-foundation-integrated
git push origin week1-day3-foundation-integrated
```

### Testing Commands

```bash
# Run all tests with verbose output
pytest tests/ -v

# Run with coverage report
pytest --cov=src --cov-report=term

# Run specific test file
pytest tests/test_pipeline.py -v

# Run tests in parallel (requires pytest-xdist)
pytest -n auto

# Run with markers
pytest -m "not slow"
```

### Quality Check Commands

```bash
# Type checking
mypy src/

# Linting
black src/ tests/ --check

# Format code
black src/ tests/

# Run all quality checks
pytest tests/ -v && mypy src/ && black src/ tests/ --check
```

---

## Pull Request Workflow for Integration Checkpoints

### When to Use Pull Requests

**Workstream Branches** (direct commits, no PRs):
```bash
# Inside workstream worktree - commit directly
cd ~/Developer/Projects/autoD-retry-error-handling
git add . && git commit -m "feat: add exponential backoff logic"
git push origin workstream/retry-error-handling
```

**Integration Checkpoints** (required PRs):
```bash
# Day 3, 5, 7: Create PR for integration → main
cd ~/Developer/Projects/autoD  # Main worktree
git checkout integration/week1-foundation
git push origin integration/week1-foundation

# Open PR using template (auto-populates checklist)
gh pr create --base main --fill
```

### PR Template Features

The `.github/pull_request_template.md` auto-populates:
- ✅ Workstream checklist (which workstreams are being merged)
- ✅ Quality gates (tests, coverage, Docker, integration tests)
- ✅ Risk assessment section
- ✅ Rollback plan template
- ✅ Manual validation checklist

**One-command PR creation:**
```bash
gh pr create --fill  # Uses template, auto-fills from commits
```

### Automated Quality Gates (GitHub Actions)

The `integration-pr.yml` workflow runs automatically on PRs to `integration/*` or `main`:

**Validation Steps:**
1. Full test suite with coverage (≥75% for Week 1 modules)
2. Pre-commit hooks (Black, Ruff, Mypy)
3. Docker build validation
4. Docker Compose multi-container validation (app + PostgreSQL)
5. Integration smoke tests
6. Secrets scanning (detects committed API keys)

**PR Comment:**
GitHub Actions posts detailed results as a PR comment:
```
## Integration Checkpoint Validation Results

**Overall Status:** ✅ ALL QUALITY GATES PASSED

### Quality Gates

| Check | Status |
|-------|--------|
| Full Test Suite | ✅ PASS |
| Week 1 Coverage (≥75%) | ✅ PASS (76%) |
| Pre-commit Hooks | ✅ PASS |
| Docker Build | ✅ PASS |
| Docker Compose Validation | ✅ PASS |
| Integration Smoke Tests | ✅ PASS |
| Secrets Check | ✅ PASS |

### Next Steps

✅ All quality gates passed. This PR is ready to merge.
```

### Integration Workflow with PRs

**Day 3: Foundation Integration PR**
```bash
# Terminal Tab #1 (project manager in autoD/)
git checkout -b integration/week1-foundation

# Merge workstreams locally first
git merge workstream/testing --no-ff -m "Merge Workstream 4: Test Infrastructure"
git merge workstream/database-pipeline --no-ff -m "Merge Workstream 1: Database + Pipeline"

# Run local quality gates
pytest tests/ -v --cov=src --cov-report=term
# Expected: 60%+ coverage, all tests pass

# Push integration branch
git push origin integration/week1-foundation

# Create PR with template
gh pr create --base main --fill --title "Week 1 Day 3: Foundation (Testing + Database)"

# GitHub Actions runs automatically:
# - Full test suite
# - Docker build
# - Integration validation
# - Posts results as PR comment

# After PR approval + CI green → Merge via GitHub UI or:
gh pr merge --squash --delete-branch
```

**Day 5: Retry Logic Integration PR**
```bash
# Terminal Tab #1 (project manager in autoD/)
git checkout integration/week1-foundation

# Merge retry logic
git merge workstream/retry-error-handling --no-ff -m "Merge Workstream 2: Retry Logic + Error Handling"

# Run local quality gates
pytest tests/ -v --cov=src --cov-report=term
# Expected: 70%+ coverage, all tests pass

# Push and create PR
git push origin integration/week1-foundation
gh pr create --base main --fill --title "Week 1 Day 5: Add Retry Logic + Error Handling"

# CI validates → Merge after approval
```

**Day 7: Final Integration PR**
```bash
# Terminal Tab #1 (project manager in autoD/)
git checkout integration/week1-foundation

# Merge token tracking (final workstream)
git merge workstream/token-tracking --no-ff -m "Merge Workstream 3: Token Tracking + Cost Monitoring"

# Run local quality gates
pytest tests/ -v --cov=src --cov-report=term
# Expected: 75%+ coverage, all tests pass

# Integration test: Process 100 PDFs
python process_inbox.py

# Push and create final PR
git push origin integration/week1-foundation
gh pr create --base main --fill --title "Week 1 Complete: Core Pipeline + Retry + Token Tracking"

# CI validates → Merge to main after approval
gh pr merge --squash --delete-branch

# Tag release
git checkout main
git pull
git tag week1-complete
git push origin week1-complete
```

### Why This PR Strategy Works

**Fast Iteration** (workstreams):
- No PR overhead within workstreams
- 5-6 agents work independently
- Direct commits to workstream branches

**Quality Gates** (integration):
- Automated CI/CD validation at critical merge points
- Prevents bad merges before they hit main
- Clear documentation of what each integration includes

**Clean History** (main):
- Main branch only has integration merges
- Easy to understand project evolution
- Easy to roll back (revert single integration PR)

**Safety** (rollback):
- If integration PR fails CI → fix in workstream, retry
- If integrated PR causes production issues → revert PR, redeploy

### PR Commands Reference

```bash
# Create PR using template (auto-populates checklist)
gh pr create --fill

# Create PR with specific base and title
gh pr create --base main --head integration/week1-foundation \
  --title "Week 1 Day 3: Foundation" --fill

# List PRs
gh pr list

# View PR status
gh pr status

# View CI checks
gh pr checks

# Merge PR (squash merge recommended for clean history)
gh pr merge --squash --delete-branch

# Merge PR (no-fast-forward to preserve integration history)
gh pr merge --merge --delete-branch
```

---

## References

- **Claude Code Best Practices**: https://www.anthropic.com/research/claude-code-best-practices
- **Git Worktrees Section**: https://www.anthropic.com/research/claude-code-best-practices#git-worktrees
- **Implementation Plan**: `docs/IMPLEMENTATION_ROADMAP.md`
- **Code Patterns**: `docs/CODE_ARCHITECTURE.md`
- **Original vs Revised**: `docs/CHANGES_FROM_ORIGINAL_PLAN.md`
- **ADR 0001**: `docs/adr/0001-iterative-phasing-over-parallel-development.md`
- **PR Template**: `.github/pull_request_template.md`
- **Integration PR Workflow**: `.github/workflows/integration-pr.yml`
- **Workflows Documentation**: `.github/workflows/README.md`

---

## Changelog

| Date | Change | Author |
|------|--------|--------|
| 2025-10-16 | Created parallel execution strategy with 4 git worktrees | Project Manager |
| 2025-10-16 | Incorporated Claude Code best practices (git worktrees, /clear, specific instructions) | Project Manager |
| 2025-10-16 | Defined integration checkpoints (Day 3, 5, 7) | Project Manager |

---

**Status**: ✅ Ready for Execution

**Next Actions**:
1. ✅ Create this strategy document
2. ⏳ Set up 4 git worktrees
3. ⏳ Launch Claude in each worktree terminal tab
4. ⏳ Monitor progress and coordinate integration

*End of Parallel Execution Strategy*
