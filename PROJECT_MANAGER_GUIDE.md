# Project Manager Coordination Guide

**Role**: Coordinate 4 parallel Claude Code sessions working in git worktrees
**Reference**: `docs/PARALLEL_EXECUTION_STRATEGY.md`
**Created**: 2025-10-16

---

## Overview

You are managing 4 parallel Claude Code sessions, each working in a separate git worktree on independent components. Your job is to:
1. **Monitor progress** across all 4 workstreams
2. **Coordinate integration** at Day 3, 5, 7 checkpoints
3. **Resolve conflicts** when worktrees modify the same files
4. **Ensure quality** by verifying quality gates before merging

---

## Terminal Setup (Recommended)

### iTerm2 Configuration (macOS)

**Terminal Tabs**:
- **Tab 1** (THIS TAB): Project Manager - `autoD/` (main directory)
- **Tab 2**: Workstream 1 - `../autoD-database-pipeline`
- **Tab 3**: Workstream 2 - `../autoD-retry-error-handling`
- **Tab 4**: Workstream 3 - `../autoD-token-tracking`
- **Tab 5**: Workstream 4 - `../autoD-testing`

**iTerm2 Notifications**:
1. iTerm2 > Preferences > Profiles > Terminal > Notifications
2. Enable "Notify on next mark"
3. This will alert you when Claude needs attention in any tab

**Tab Labels** (for clarity):
```bash
# In each terminal tab, run:
# Tab 1
echo -e "\033]0;PM - autoD\007"

# Tab 2
echo -e "\033]0;WS1 - Database+Pipeline\007"

# Tab 3
echo -e "\033]0;WS2 - Retry+Errors\007"

# Tab 4
echo -e "\033]0;WS3 - Token Tracking\007"

# Tab 5
echo -e "\033]0;WS4 - Testing\007"
```

---

## Day 0: Launch Parallel Sessions

### Step 1: Verify Worktrees (✅ DONE)

```bash
# In Tab 1 (Project Manager - autoD/)
git worktree list

# Expected output:
# /path/to/autoD                           [main]
# /path/to/autoD-database-pipeline         [workstream/database-pipeline]
# /path/to/autoD-retry-error-handling      [workstream/retry-error-handling]
# /path/to/autoD-token-tracking            [workstream/token-tracking]
# /path/to/autoD-testing                   [workstream/testing]
```

✅ **Status**: All 4 worktrees created successfully.

### Step 2: Start Claude Sessions in Each Worktree

**Tab 2** (Workstream 1 - Database + Pipeline):
```bash
cd ../autoD-database-pipeline
claude
# When Claude starts, paste the prompt from STARTUP.md
# Or simply say: "Read STARTUP.md and begin the workstream"
```

**Tab 3** (Workstream 2 - Retry Logic + Error Handling):
```bash
cd ../autoD-retry-error-handling
claude
# When Claude starts: "Read STARTUP.md and begin the workstream"
```

**Tab 4** (Workstream 3 - Token Tracking + Cost Monitoring):
```bash
cd ../autoD-token-tracking
claude
# When Claude starts: "Read STARTUP.md and begin the workstream"
```

**Tab 5** (Workstream 4 - Test Infrastructure):
```bash
cd ../autoD-testing
claude
# When Claude starts: "Read STARTUP.md and begin the workstream"
```

### Step 3: Confirm All Sessions Started

**Tab 1** (Project Manager):
```bash
# Verify each Claude session is running and reading docs
# Cycle through tabs and check that each Claude is:
# 1. Reading the STARTUP.md instructions
# 2. Reading the documentation files
# 3. Creating an implementation plan
```

**Initial Status Message to All Workstreams**:
> "All 4 worktrees created successfully. You can start work. Remember:
> - Workstream 1 + 4 will merge on Day 3
> - Workstream 2 will merge on Day 5
> - Workstream 3 will merge on Day 7
> - Use /clear frequently to keep context focused
> - Be specific in your instructions to Claude
> - Update your progress.md file hourly
> - Post completion notifications to the project manager tab when done"

---

## Daily Monitoring (Days 1-2)

### Hourly Progress Checks

**Tab 1** (Project Manager):
```bash
# Check progress across all worktrees
echo "=== WORKSTREAM STATUS ==="
for worktree in database-pipeline retry-error-handling token-tracking testing; do
    echo ""
    echo "=== $worktree ==="
    if [ -f ../autoD-$worktree/progress.md ]; then
        cat ../autoD-$worktree/progress.md | grep -E "(Status|Progress|ETA|Blockers)" | head -5
    else
        echo "⚠️  No progress.md file yet"
    fi
done
```

### Risk Identification

**Look for**:
- 🔴 **Blocked** workstreams (Blockers section non-empty)
- 🟡 **At Risk** workstreams (Progress < 50% by Day 2)
- 🟢 **On Track** workstreams (Status: On Track)

**If Blocked**: Switch to that workstream's tab and ask Claude what the blocker is, help resolve it.

**If At Risk**: Adjust integration timeline if needed (e.g., delay Day 3 merge to Day 4).

---

## Day 3: Foundation Integration

### Pre-Integration Checklist

**Tab 1** (Project Manager):
```bash
# Verify Workstream 1 (Database + Pipeline) is complete
cd ../autoD-database-pipeline
git status  # Should show commits on workstream/database-pipeline
pytest tests/ -v  # Should pass
mypy src/  # Should pass

# Verify Workstream 4 (Testing) is complete
cd ../autoD-testing
git status  # Should show commits on workstream/testing
pytest tests/ -v  # Should pass (even if just testing fixtures)
```

### Integration Steps

**Tab 1** (Project Manager in `autoD/` directory):

**Step 1**: Create integration branch
```bash
git checkout -b integration/week1-foundation
```

**Step 2**: Merge Workstream 4 (Testing) first - provides fixtures
```bash
git merge workstream/testing --no-ff -m "Merge Workstream 4: Test Infrastructure

- pytest configuration with database fixtures
- Mock OpenAI client for testing without API calls
- Sample PDF fixtures for testing
- Test utilities for assertions and log capture

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

**Step 3**: Run tests to ensure fixtures work
```bash
pytest tests/ -v
# Expected: Tests pass (even if just testing the fixtures themselves)
```

**Step 4**: Merge Workstream 1 (Database + Pipeline)
```bash
git merge workstream/database-pipeline --no-ff -m "Merge Workstream 1: Database + Pipeline Foundation

- SQLAlchemy Document model with generic JSON type
- Pipeline pattern with ProcessingStage ABC
- Five pipeline stages (SHA-256, dedupe, upload, API call, persist)
- Unit tests with 80%+ coverage

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

**Step 5**: Resolve conflicts (if any)
```bash
# If conflicts occur (likely in tests/conftest.py):
git status  # Shows conflicted files

# Manually resolve conflicts, keeping both test fixtures and pipeline tests
# Edit conflicted files

# After resolving:
git add <conflicted-files>
git merge --continue
```

**Step 6**: Quality Gate Validation
```bash
# Run all tests
pytest tests/ -v --cov=src --cov-report=term

# Expected:
# - All tests pass ✅
# - Coverage 60%+ ✅

# Type checking
mypy src/

# Linting
black src/ tests/ --check

# Integration test - process 1 PDF
python -m src.pipeline  # Or however the pipeline is invoked
# Expected: PDF processed, record in database, no duplicates
```

**Step 7**: Tag milestone
```bash
git tag week1-day3-foundation-integrated
git push origin integration/week1-foundation week1-day3-foundation-integrated
```

**Step 8**: Communicate success to all workstreams
```bash
# Post this message to all workstream tabs
cat <<EOF
🎉 Day 3 Integration Complete!

✅ Workstream 1 (Database + Pipeline) + Workstream 4 (Testing) merged successfully
✅ 65% test coverage
✅ Pipeline processes 1 PDF end-to-end
✅ SHA-256 deduplication working

Workstream 2 and 3: You can now merge the foundation branch into your worktrees to get the latest code:
  cd ../autoD-retry-error-handling (or token-tracking)
  git merge integration/week1-foundation

Next checkpoint: Day 5 (Workstream 2 merge)
EOF
```

---

## Day 5: Retry Logic Integration

### Pre-Integration Checklist

**Tab 1** (Project Manager):
```bash
# Verify Workstream 2 (Retry Logic + Error Handling) is complete
cd ../autoD-retry-error-handling
git status  # Should show commits
pytest tests/ -v  # Should pass
mypy src/  # Should pass
```

### Integration Steps

**Tab 1** (Project Manager in `autoD/` directory):

**Step 1**: Checkout integration branch
```bash
git checkout integration/week1-foundation
```

**Step 2**: Merge Workstream 2
```bash
git merge workstream/retry-error-handling --no-ff -m "Merge Workstream 2: Retry Logic + Error Handling

- Comprehensive retry logic with tenacity (handles all transient errors)
- Compensating transaction pattern for data consistency
- Structured JSON logging for observability
- 70%+ test coverage

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

**Step 3**: Resolve conflicts (if any)
```bash
# Likely conflict: src/pipeline.py if retry decorators applied
# Resolution: Keep retry decorators, ensure backward compatibility

# Likely conflict: src/logging_config.py if logging fields added
# Resolution: Keep all logging fields from both workstreams

git status  # Check for conflicts
# Resolve manually, then:
git add <conflicted-files>
git merge --continue
```

**Step 4**: Quality Gate Validation
```bash
# Run all tests (including new retry tests)
pytest tests/ -v --cov=src --cov-report=term

# Expected:
# - All tests pass ✅
# - Coverage 70%+ ✅

# Integration test: Simulate API failures
python -m tests.test_retry  # Or however retry tests are invoked
# Expected: 95%+ success rate, 5 retry attempts on transient errors

# Type checking
mypy src/

# Linting
black src/ tests/ --check
```

**Step 5**: Tag milestone
```bash
git tag week1-day5-retry-integrated
git push origin integration/week1-foundation week1-day5-retry-integrated
```

**Step 6**: Communicate success
```bash
cat <<EOF
🎉 Day 5 Integration Complete!

✅ Workstream 2 (Retry Logic + Error Handling) merged successfully
✅ 72% test coverage
✅ Retry logic handles all transient errors
✅ 95%+ API success rate under simulated failures
✅ Structured logs show retry attempts

Workstream 3: You can now merge the foundation branch:
  cd ../autoD-token-tracking
  git merge integration/week1-foundation

Final checkpoint: Day 7 (Workstream 3 merge and deploy to main)
EOF
```

---

## Day 7: Final Integration and Deployment

### Pre-Integration Checklist

**Tab 1** (Project Manager):
```bash
# Verify Workstream 3 (Token Tracking) is complete
cd ../autoD-token-tracking
git status  # Should show commits
pytest tests/ -v  # Should pass
mypy src/  # Should pass
```

### Integration Steps

**Step 1**: Merge Workstream 3
```bash
cd ../autoD/  # Project manager directory
git checkout integration/week1-foundation

git merge workstream/token-tracking --no-ff -m "Merge Workstream 3: Token Tracking + Cost Monitoring

- tiktoken integration with o200k_base encoding (GPT-5)
- Cost calculation with GPT-5 pricing
- Token/cost metrics in structured logs
- 90%+ test coverage

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"
```

**Step 2**: Resolve conflicts (if any)
```bash
# Likely conflict: src/logging_config.py if token metrics added
# Resolution: Combine all logging fields

git status
# Resolve, then:
git add <conflicted-files>
git merge --continue
```

**Step 3**: Quality Gate Validation
```bash
# Run all tests
pytest tests/ -v --cov=src --cov-report=term

# Expected:
# - All tests pass ✅
# - Coverage 75%+ ✅

# Type checking
mypy src/

# Linting
black src/ tests/ --check
```

**Step 4**: Final Validation - Process 100 PDFs
```bash
# Create 100 test PDFs (or use existing)
# Process them through the pipeline
python process_inbox.py

# Expected:
# - 100 PDFs in database ✅
# - Zero duplicates (test with 10 duplicate PDFs) ✅
# - Token counts accurate within 5% ✅
# - Cost calculations correct ✅
# - Structured logs show all metrics ✅
```

**Step 5**: Tag Week 1 completion
```bash
git tag week1-complete
```

**Step 6**: Merge to main
```bash
git checkout main
git merge integration/week1-foundation --no-ff -m "Week 1 Complete: Core Pipeline + Retry + Token Tracking

All 4 workstreams integrated successfully:
- Workstream 1: Database + Pipeline (SQLAlchemy, pipeline pattern, 5 stages)
- Workstream 2: Retry Logic + Error Handling (tenacity, compensating transactions, structured logs)
- Workstream 3: Token Tracking + Cost Monitoring (tiktoken, cost calculation)
- Workstream 4: Test Infrastructure (pytest fixtures, mocks, utilities)

Success Metrics:
✅ 76% test coverage
✅ 100 PDFs processed, zero duplicates
✅ 95%+ API success rate with retry logic
✅ Token tracking and cost monitoring working
✅ Structured logs capturing all metrics

Total time: 7 days (4 parallel Claude sessions)

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"

git push origin main --tags
```

**Step 7**: Celebrate!
```bash
cat <<EOF
🎉🎉🎉 Week 1 Complete!

✅ All 4 workstreams integrated successfully
✅ 76% test coverage
✅ 100 PDFs processed, zero duplicates
✅ 95%+ API success rate with retry logic
✅ Token tracking and cost monitoring working
✅ Structured logs capturing all metrics

Total time: 7 days (with 4 parallel Claude sessions)
vs. Estimated sequential time: 5 days (but with 1 agent only)

Benefit: Multiple agents learning and validating in parallel, earlier integration feedback

Ready for Week 2!
EOF
```

---

## Conflict Resolution Playbook

### Common Conflict: `src/pipeline.py`

**Scenario**: Both Workstream 1 and 2 modify `src/pipeline.py`

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

**Resolution**: Keep Workstream 2's version (adds retry decorator without breaking logic).

```bash
# During merge conflict:
git checkout --theirs src/pipeline.py  # Accept Workstream 2's version
git add src/pipeline.py
```

### Common Conflict: `src/logging_config.py`

**Scenario**: Workstream 2 and 3 both add fields to `JSONFormatter`

**Resolution**: Combine all fields from both workstreams.

```python
# Manual edit of src/logging_config.py
def format(self, record):
    log_obj = {
        "timestamp": datetime.utcnow().isoformat(),
        "level": record.levelname,
        "message": record.getMessage(),
        # From Workstream 2
        "stage": getattr(record, 'stage', None),
        "duration_ms": getattr(record, 'duration_ms', None),
        # From Workstream 3
        "prompt_tokens": getattr(record, 'prompt_tokens', None),
        "output_tokens": getattr(record, 'output_tokens', None),
        "cost_usd": getattr(record, 'cost_usd', None),
    }
    return json.dumps(log_obj)
```

```bash
# After manual resolution:
git add src/logging_config.py
git merge --continue
```

---

## Rollback Procedure

If any integration fails quality gates:

**Step 1**: Undo merge
```bash
git reset --hard HEAD~1
```

**Step 2**: Notify workstream owner
```bash
# Switch to the workstream's tab (e.g., Tab 3 for Workstream 2)
# Message in Claude session:
"Integration failed quality gate: retry tests are failing. Please fix the issue in your worktree and notify me when ready to re-merge."
```

**Step 3**: Fix in worktree
```bash
# Workstream owner fixes issue in their worktree
cd ../autoD-retry-error-handling
# Fix bug
pytest tests/  # Verify fix
git commit -am "fix: Retry logic edge case for timeout errors"
```

**Step 4**: Retry integration
```bash
# Back in Tab 1 (Project Manager)
cd autoD/
git checkout integration/week1-foundation
git merge workstream/retry-error-handling
pytest tests/  # NOW PASSES ✅
```

---

## Cleanup After Week 1

**Remove Worktrees** (keep branches for reference):
```bash
# Tab 1 (Project Manager in autoD/)
git worktree remove ../autoD-database-pipeline
git worktree remove ../autoD-retry-error-handling
git worktree remove ../autoD-token-tracking
git worktree remove ../autoD-testing

# Verify removal
git worktree list
# Should show only: /path/to/autoD [main]

# Keep branches for historical reference
git branch
# workstream/database-pipeline
# workstream/retry-error-handling
# workstream/token-tracking
# workstream/testing
```

---

## Week 2 Planning

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

## Quick Reference Commands

**List worktrees**:
```bash
git worktree list
```

**Check progress across all workstreams**:
```bash
for worktree in database-pipeline retry-error-handling token-tracking testing; do
    echo "=== $worktree ==="
    cat ../autoD-$worktree/progress.md | head -10
done
```

**Run tests in integration branch**:
```bash
git checkout integration/week1-foundation
pytest tests/ -v --cov=src --cov-report=term
```

**Tag a milestone**:
```bash
git tag week1-day3-foundation-integrated
git push origin week1-day3-foundation-integrated
```

**Merge to main**:
```bash
git checkout main
git merge integration/week1-foundation --no-ff
git push origin main --tags
```

---

## Success Metrics

Track these throughout the week:

- ✅ All 4 worktrees merged cleanly (< 5 conflicts total)
- ✅ < 2 rollbacks required
- ✅ Integration checkpoints met on schedule (Day 3, 5, 7)
- ✅ 75%+ test coverage
- ✅ 100 PDFs processed successfully
- ✅ Zero duplicate records
- ✅ 95%+ API success rate
- ✅ Token counts accurate within 5%

---

**Good luck coordinating the parallel workstreams! 🚀**
