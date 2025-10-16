# ADR 0001: Iterative Phasing Over Parallel Development

**Status**: ✅ Accepted

**Date**: 2025-10-16

**Deciders**: Architecture Sage Agent, Repository Owner

**Technical Story**: [CHANGES_FROM_ORIGINAL_PLAN.md](../CHANGES_FROM_ORIGINAL_PLAN.md)

---

## Context and Problem Statement

The original implementation plan proposed building all production features in parallel across 8 phases:

1. Database layer with SQLAlchemy
2. Vector store integration
3. Structured outputs + strict schemas
4. Deduplication logic
5. Retry/backoff mechanisms
6. Logging + observability
7. Configuration management
8. Integration testing

This "build everything at once" approach carries significant risks:
- No working software until Week 8
- Late validation of core assumptions
- Difficult to debug when integration fails
- High rework risk if architecture is flawed
- No incremental value delivery

**Question**: Should we continue with the 8-phase parallel approach, or switch to an iterative strategy that delivers working software weekly?

---

## Decision Drivers

### Technical Factors
- **Architectural unknowns**: Database type incompatibility (JSONB vs JSON), transaction boundary issues, incomplete retry logic
- **Testing difficulty**: Monolithic 200-line functions are hard to unit test
- **Integration risk**: Big bang integration at Week 8 has high failure risk
- **Debugging complexity**: When everything is built together, isolating failures is difficult

### Business Factors
- **Time to value**: No working software until all phases complete
- **Risk profile**: All investment upfront with no validation
- **Flexibility**: Hard to pivot if requirements change
- **Learning opportunities**: No feedback loop until the end

### Team Factors
- **Cognitive load**: Managing 8 parallel work streams simultaneously
- **Validation opportunities**: No checkpoints to validate assumptions
- **Motivation**: Long periods without shippable results

---

## Decision Outcome

**Chosen option**: **4-Week Iterative Phasing** with working software delivered every week.

### Rationale

1. **Early Validation**: Week 1 validates core pipeline (DB, SHA-256, API) before investing in advanced features
2. **Risk Reduction**: Each week builds on validated foundation, reducing rework risk
3. **Testability**: Pipeline pattern with discrete stages enables unit testing
4. **Incremental Value**: Each week delivers shippable software that solves real problems
5. **Architectural Safety**: Fixes 5 critical flaws identified during review (see Consequences)

### Implementation Strategy

**Week 1**: Core Pipeline (Foundation)
- Database with generic JSON type (not JSONB)
- SHA-256 deduplication
- Basic Responses API integration
- **Deliverable**: 100 PDFs in database, zero duplicates

**Week 2**: Resilience (Error Handling)
- Comprehensive retry logic (all transient errors)
- Compensating transaction pattern
- Structured JSON logging
- **Deliverable**: 95%+ success rate with graceful failure handling

**Week 3**: Observability (Understanding)
- Token tracking with tiktoken
- Cost estimation and monitoring
- Unit tests with pytest
- **Deliverable**: Cost dashboard, 60%+ test coverage

**Week 4**: Production (Deployment)
- Vector store integration
- Alembic database migrations
- PostgreSQL migration path
- **Deliverable**: 1000 PDFs processed in production

---

## Consequences

### Positive Consequences

1. **Working Software Every Week**
   - Week 1: Can process PDFs to database
   - Week 2: Can survive API failures
   - Week 3: Can track costs and performance
   - Week 4: Can deploy to production

2. **Lower Risk Profile**
   - Assumptions validated early (Week 1)
   - Problems discovered incrementally
   - Easy to course-correct
   - Reduced rework cost

3. **Better Testing**
   - Pipeline stages are independently testable
   - Unit tests written alongside implementation
   - Integration testing happens continuously
   - 60%+ coverage by Week 3

4. **Simplified Debugging**
   - Clear stage boundaries
   - Isolated failure points
   - Structured logs show stage transitions
   - Easier to reproduce issues

5. **Architectural Fixes Included**
   - **Fix #1**: Generic `JSON` type works on SQLite + PostgreSQL
   - **Fix #2**: Pipeline pattern replaces monolithic function
   - **Fix #3**: Compensating transactions prevent data loss
   - **Fix #4**: Comprehensive retry handles all transient errors
   - **Fix #5**: Build for actual scale (10 PDFs/day), not hypothetical (1M PDFs)

### Negative Consequences

1. **Slightly Longer Calendar Time**
   - Original: 8 weeks with all features
   - New: 4 weeks to production, then evolve based on needs
   - **Mitigation**: Working software delivered weekly, not waiting until Week 8

2. **Requires Discipline**
   - Must resist temptation to build premature optimizations
   - Need to stick to "build only what's needed now"
   - **Mitigation**: Clear "What NOT to Build" section in roadmap

3. **Multiple Refactoring Cycles**
   - Week 1 code may need refinement in Week 2
   - Pipeline stages may need adjustment
   - **Mitigation**: Expected and budgeted for; easier with discrete stages

4. **Less Upfront Planning**
   - Detailed design happens week-by-week
   - Some decisions deferred to later weeks
   - **Mitigation**: Clear roadmap provides direction; flexibility is a feature

---

## Alternatives Considered

### Alternative 1: Keep Original 8-Phase Parallel Plan

**Pros**:
- Comprehensive upfront design
- All features planned from day one
- Clear deliverables for each phase

**Cons**:
- No working software until Week 8
- High integration risk
- Late discovery of architectural flaws (JSONB, transactions, retry logic)
- Monolithic functions hard to test
- No incremental value delivery

**Why rejected**: Too risky. Architectural review identified 5 critical flaws that would cause failures at Week 8 integration. Better to discover and fix these issues incrementally.

---

### Alternative 2: Waterfall (Design → Build → Test → Deploy)

**Pros**:
- Traditional approach with clear gates
- Comprehensive requirements upfront
- Separate design and implementation phases

**Cons**:
- Even longer time to working software
- Higher risk of requirement drift
- Late validation (testing only at end)
- No feedback loop

**Why rejected**: Even worse than parallel phasing. Modern software development favors iterative approaches with continuous validation.

---

### Alternative 3: Pure Agile Sprints (No Long-Term Plan)

**Pros**:
- Maximum flexibility
- Respond to changes immediately
- Focus on immediate needs

**Cons**:
- No strategic direction
- Risk of aimless iteration
- Missing critical features (vector stores, migrations)
- Hard to track progress toward production

**Why rejected**: Too loose. Iterative phasing provides structure (4-week plan) while maintaining flexibility (evolve based on real problems).

---

### Alternative 4: MVP Then Big Bang Expansion

**Pros**:
- Get basic version working quickly
- Validate core assumptions
- Then add all features at once

**Cons**:
- Second big bang still risky
- "MVP" scope often unclear
- Temptation to ship MVP and never improve
- No continuous validation of expansions

**Why rejected**: Iterative phasing gives us benefits of MVP (early validation) plus continuous improvement (weekly deliverables).

---

## Trade-offs

| Aspect | Parallel Phasing | Iterative Phasing | Winner |
|--------|-----------------|-------------------|--------|
| **Time to first working software** | 8 weeks | 1 week | ✅ Iterative |
| **Upfront design effort** | High | Medium | ⚖️ Tie (trade-off) |
| **Integration risk** | High (all at once) | Low (continuous) | ✅ Iterative |
| **Code testability** | Low (monolithic) | High (pipeline stages) | ✅ Iterative |
| **Flexibility to pivot** | Low (all planned) | High (week-by-week) | ✅ Iterative |
| **Architectural validation** | Week 8 (late) | Week 1 (early) | ✅ Iterative |
| **Refactoring effort** | Low (one-time) | Higher (multiple cycles) | ⚠️ Parallel |
| **Planning overhead** | Upfront only | Weekly adjustments | ⚖️ Tie |

**Net Result**: Iterative phasing wins on critical factors (risk, testability, validation) while trading off some refactoring overhead.

---

## Architectural Improvements Included

This decision incorporates fixes for 5 critical architectural flaws:

### 1. Database Type Cross-Compatibility
**Before**: `Column(JSONB)` - PostgreSQL-only
**After**: `Column(JSON)` - Works on SQLite and PostgreSQL
**Impact**: Local development without Docker

### 2. Processing Function Design
**Before**: Monolithic 200-line `process_pdf()` function
**After**: Pipeline with discrete stages (ComputeSHA256Stage, DedupeCheckStage, etc.)
**Impact**: Independently testable, clear transaction boundaries

### 3. Transaction Safety
**Before**: Commit to DB, then upload to vector store (orphans records on failure)
**After**: Compensating transactions or best-effort pattern with status tracking
**Impact**: No data loss on partial failures

### 4. Retry Predicate Completeness
**Before**: Only retries `RateLimitError` and `APIConnectionError`
**After**: Retries all transient errors (timeouts, 500s, 502s, 503s)
**Impact**: Robust error handling in production

### 5. Scaling Strategy
**Before**: Build for hypothetical 1M PDFs when processing 10/day
**After**: Build for actual needs, scale when proven necessary
**Impact**: Faster delivery, lower complexity

---

## Validation Checkpoints

Each week has clear success criteria:

**Week 1**: 100 PDFs in database, zero duplicates
**Week 2**: 95%+ API success rate with retry logic
**Week 3**: Cost tracking dashboard, 60%+ test coverage
**Week 4**: 1000 PDFs processed, vector stores integrated

**Decision Point**: If any week fails validation, we stop and fix before proceeding. This is a **feature**, not a bug - catch problems early.

---

## What We're NOT Building (Yet)

Deferred optimizations (build when proven necessary):

- ❌ Async processing with asyncio
- ❌ Circuit breaker pattern
- ❌ OpenTelemetry integration
- ❌ Kubernetes deployment
- ❌ GraphQL API
- ❌ 40-field database schema
- ❌ Multi-tenant support
- ❌ Webhook notifications

**Rationale**: These are solutions to problems we don't have yet. Build them when bottlenecks are measured, not assumed.

---

## Implementation Notes

### Pipeline Stage Pattern
```python
class ProcessingStage(ABC):
    """Abstract base for pipeline stages."""

    @abstractmethod
    def execute(self, context: ProcessingContext) -> ProcessingContext:
        """Execute stage logic, return updated context."""
        pass

# Example: Discrete, testable stages
class ComputeSHA256Stage(ProcessingStage):
    def execute(self, ctx):
        ctx.sha256_hex = hashlib.sha256(ctx.pdf_bytes).hexdigest()
        return ctx

class DedupeCheckStage(ProcessingStage):
    def execute(self, ctx):
        existing = session.query(Document).filter_by(sha256_hex=ctx.sha256_hex).first()
        ctx.is_duplicate = existing is not None
        return ctx
```

### Comprehensive Retry Logic
```python
def is_retryable_api_error(exception: Exception) -> bool:
    # Rate limits, connections, timeouts always retry
    if isinstance(exception, (RateLimitError, APIConnectionError, Timeout)):
        return True
    # Server errors (5xx) retry
    if isinstance(exception, APIError):
        return hasattr(exception, 'status_code') and exception.status_code >= 500
    return False

@retry(
    retry=retry_if_exception(is_retryable_api_error),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=60)
)
def call_openai_with_retry(client, **kwargs):
    return client.responses.create(**kwargs)
```

---

## Related Decisions

- **ADR 0002** (future): PostgreSQL vs SQLite for production
- **ADR 0003** (future): Vector store implementation strategy
- **ADR 0004** (future): Structured output schema design

---

## References

- **Original Plan**: `docs/initial_implementation_plan.md` (707 lines)
- **Revised Plan**: `docs/IMPLEMENTATION_ROADMAP.md`
- **Comparison**: `docs/CHANGES_FROM_ORIGINAL_PLAN.md`
- **Code Patterns**: `docs/CODE_ARCHITECTURE.md`
- **Repository Rules**: `AGENTS.md`
- **Architecture Review**: Architecture Sage Agent review (2025-10-16)

---

## Decision Timeline

- **2025-10-16 08:00**: Original 8-phase plan proposed
- **2025-10-16 10:00**: Architecture Sage review identifies 5 critical flaws
- **2025-10-16 11:00**: Revised 4-week iterative plan drafted
- **2025-10-16 11:30**: ADR 0001 created documenting decision
- **Status**: ✅ **APPROVED AND ACTIVE**

---

## Success Metrics (Post-Implementation)

After 4 weeks, we should see:

- ✅ 1000 PDFs processed successfully in production
- ✅ Zero duplicate records (deduplication working)
- ✅ 95%+ API call success rate (retry logic working)
- ✅ < $100 total cost for 1000-PDF corpus
- ✅ 60%+ test coverage with pytest
- ✅ Structured logs showing stage-by-stage progress
- ✅ Vector store integration complete
- ✅ Migration path to PostgreSQL validated

---

## Review Schedule

- **Week 1**: Review database persistence and deduplication
- **Week 2**: Review retry logic and transaction safety
- **Week 3**: Review observability and cost tracking
- **Week 4**: Review production readiness
- **Week 8**: Retrospective on iterative phasing approach (validate this ADR)

If iterative phasing proves ineffective, we can revisit and supersede this ADR. However, based on industry best practices and architectural review, this approach has strong theoretical and empirical support.

---

## Notes

- This ADR represents a **strategic shift** from "build everything" to "build what's needed"
- The shift was driven by concrete architectural flaws, not just philosophy
- All 5 architectural fixes are incorporated into the 4-week plan
- Working software every week provides validation checkpoints
- "What NOT to Build" section prevents premature optimization
- Pipeline pattern enables testing and observability
- Decision is **reversible** but evidence strongly supports this approach

---

**Status**: ✅ Accepted and active

**Next ADR**: 0002 - Database selection for production (PostgreSQL vs SQLite)

*End of ADR 0001*
