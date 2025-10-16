# Workstream 2: Retry Logic + Error Handling

**Worktree**: autoD-retry-error-handling
**Branch**: workstream/retry-error-handling
**Duration**: 6-8 hours (Day 0-5)
**Dependencies**: Minimal (config patterns only - can run parallel with Workstream 1)

---

## Initial Prompt for Claude Session

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

---

## Progress Tracking

Create `progress.md` in this worktree:

```markdown
# Workstream 2: Retry Logic + Error Handling

**Status**: 🟢 On Track
**Progress**: X/8 tasks complete (X%)
**ETA**: Day 5 (on schedule)

## Completed
- ✅ Task 1

## In Progress
- 🔄 Task 2

## Pending
- ⏳ Task 3

## Blockers
- None
```

---

## Best Practices

1. **Use Checklists**: Create `retry_implementation_checklist.md` to systematically track error types and test cases

2. **Give Claude Images**: If you have retry flow diagrams, drag them into the session

3. **Course Correct**: If Claude tries to implement database models, interrupt and redirect

---

## Integration Handoff (Day 5)

**What gets merged**: Retry decorators and transaction patterns that Workstream 1's pipeline stages can use.

**Merge into**: `integration/week1-foundation` branch (after Workstream 1 + 4 are merged).
