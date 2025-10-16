# Workstream 3: Token Tracking + Cost Monitoring

**Worktree**: autoD-token-tracking
**Branch**: workstream/token-tracking
**Duration**: 4-6 hours (Day 0-7)
**Dependencies**: Minimal (config patterns only - can run parallel with all)

---

## Initial Prompt for Claude Session

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

---

## Progress Tracking

Create `progress.md` in this worktree:

```markdown
# Workstream 3: Token Tracking + Cost Monitoring

**Status**: 🟢 On Track
**Progress**: X/7 tasks complete (X%)
**ETA**: Day 7 (on schedule)

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

1. **Pass Data into Claude**: If you have sample PDFs with known token counts, create `sample_pdf_token_counts.csv` and tell Claude to validate against it

2. **Be Specific**: "Use o200k_base encoding for GPT-5. Verify against OpenAI's reported token counts within 5%."

3. **Test Early**: Create unit tests that validate token counting accuracy before building cost calculations

---

## Integration Handoff (Day 7)

**What gets merged**: Token tracking and cost calculation utilities that can be called from pipeline stages.

**Merge into**: `integration/week1-foundation` (final merge before deploying to main).
