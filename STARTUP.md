# Workstream 4: Test Infrastructure

**Worktree**: autoD-testing
**Branch**: workstream/testing
**Duration**: 6-8 hours (Day 0-7)
**Dependencies**: None (fully parallel - can run alongside all others)

---

## Initial Prompt for Claude Session

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

---

## Progress Tracking

Create `progress.md` in this worktree:

```markdown
# Workstream 4: Test Infrastructure

**Status**: 🟢 On Track
**Progress**: X/8 tasks complete (X%)
**ETA**: Day 3 (on schedule)

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

1. **Write Tests, Commit; Code, Iterate, Commit** (TDD):
   - Write test infrastructure first
   - Run tests to confirm they work
   - Commit the test infrastructure
   - Use these fixtures in other workstreams

2. **Visual Targets**: If you have screenshots of ideal test output, drag them into Claude session

3. **Be Specific**: "Create mock_openai.py that returns a Responses API response with file_name, doc_type, issuer, primary_date, total_amount, and summary fields matching the schema in docs/CODE_ARCHITECTURE.md section 3."

---

## Integration Handoff (Day 3)

**What gets merged**: Complete test infrastructure that Workstream 1, 2, 3 can use immediately.

**Merge with**: Workstream 1 (database + pipeline) to create `integration/week1-foundation` branch.

**Why Together**: Testing infrastructure provides immediate validation for pipeline implementation, creating a testable foundation.
