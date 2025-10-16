# Workstream 1: Database + Pipeline Foundation

**Worktree**: autoD-database-pipeline
**Branch**: workstream/database-pipeline
**Duration**: 8-12 hours (Day 0-3)
**Dependencies**: None (can start immediately)

---

## Initial Prompt for Claude Session

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

---

## Progress Tracking

Update `progress.md` in this worktree hourly:

```markdown
# Workstream 1: Database + Pipeline

**Status**: 🟢 On Track / 🟡 At Risk / 🔴 Blocked
**Progress**: X/10 tasks complete (X%)
**ETA**: Day 3 (on schedule)

## Completed
- ✅ Task 1
- ✅ Task 2

## In Progress
- 🔄 Task 3

## Pending
- ⏳ Task 4
- ⏳ Task 5

## Blockers
- None

## Next Steps
1. Step 1
2. Step 2
```

---

## Best Practices

1. **Be Specific**: Instead of "add deduplication", say "Implement DedupeCheckStage that queries Document table using session.query(Document).filter_by(sha256_hex=ctx.sha256_hex).first()..."

2. **Use /clear Frequently**: Between major components (after models, after pipeline pattern, after each stage)

3. **Course Correct Early**: If Claude starts implementing retry logic or token tracking, interrupt (Escape) and redirect

4. **Create Checklists**: Use `implementation_checklist.md` to track systematic progress

---

## Integration Handoff (Day 3)

**What gets merged**: Complete pipeline implementation that can process PDFs but may fail on API errors (retry logic added in Workstream 2).

**Merge with**: Workstream 4 (testing infrastructure) to create `integration/week1-foundation` branch.
