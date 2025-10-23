# ADR-024: Workstream Deferral (TD3 + WS2) for Wave 1 Integration

**Status:** Accepted
**Date:** 2025-10-23
**Deciders:** Technical Leadership
**Related ADRs:** ADR-023 (Technical Debt Reduction), ADR-001 (Iterative Phasing)

---

## Context

During Wave 1 parallel execution integration, the team identified two workstreams that, while valuable, could be deferred without blocking core functionality:

### TD3: MyPy Strict Mode + Type Coverage
**Scope:** 8-12 hours
- Enable `strict = true` in mypy configuration
- Fix 49 existing type annotation gaps
- Add type stubs for third-party libraries without annotations
- Achieve 100% type coverage across src/ modules

**Current State:**
- Wave 1 quality gates show 49 mypy warnings
- All warnings are non-critical (missing type hints, untyped function signatures)
- No runtime impact - purely static analysis improvements
- Core functionality fully validated through 100% integration test pass rate (73/73)

**Value Proposition:**
- Enhanced IDE autocomplete and error detection
- Earlier bug detection during development
- Improved code maintainability
- Better onboarding experience for new developers

### WS2: Embedding Cache Optimization
**Scope:** 8-10 hours
- Implement SHA-256 hash-based cache key generation for embeddings
- Add cache hit/miss metrics and observability
- Create cache invalidation strategy for schema changes
- Add cache size management (LRU eviction, configurable limits)
- Comprehensive cache integration testing

**Current State:**
- Basic embedding cache implemented in WS1 (merged to integration)
- Functional but lacks optimization features
- No performance degradation without optimizations
- Current cache hit rate unknown (no metrics)

**Value Proposition:**
- 20-40% reduction in OpenAI API calls for repeated documents
- Estimated $50-100/month cost savings at production scale
- Improved pipeline throughput (reduced API latency)
- Better cost predictability

### Integration Timeline Constraints

**Wave 1 Priority:** Establish parallel execution infrastructure
- TD1 (Error Handling): CompensatingTransaction pattern ✅
- TD2 (Config Management): Pydantic V2 validation ✅
- TD4 (Test Coverage): E2E + property-based tests ✅
- WS1 (Vector Store): Core semantic search capability ✅
- WS3 (Production Hardening): Comprehensive error recovery ✅

**Deferral Rationale:**
1. **No blocking dependencies**: TD3/WS2 are independent enhancements
2. **Wave 1 scope management**: 5 workstreams already integrated (37 hours baseline)
3. **Quality gate success**: 93% unit test pass, 100% integration tests, 62% coverage
4. **Risk mitigation**: Avoid scope creep during critical infrastructure merge
5. **Technical debt policy**: Documented deferral better than rushed implementation

**Cost-Benefit Analysis:**

| Workstream | Implementation | Value | Risk of Deferral | Priority |
|------------|---------------|-------|------------------|----------|
| TD3 (mypy) | 8-12 hours | Medium (Developer Experience) | Low (no runtime impact) | Wave 2 |
| WS2 (cache optimization) | 8-10 hours | Medium (Cost savings) | Low (basic cache functional) | Wave 2 |
| Wave 1 Core | 37 hours | High (Infrastructure) | High (blocks parallel dev) | ✅ Complete |

**Total Deferred Work:** 16-22 hours (~3 days of focused development)

---

## Decision

**Defer TD3 (MyPy Strict Mode) and WS2 (Embedding Cache Optimization) to Wave 2** while maintaining comprehensive documentation of:
1. Current state and gaps
2. Implementation scope and estimates
3. Value proposition and ROI
4. Success criteria and testing requirements
5. Integration strategy for Wave 2

**Wave 2 Timing:** Post-Wave 1 merge to main + documentation completion
**Estimated Start:** 2025-10-24 (after Wave 1 retrospective)
**Estimated Completion:** 2025-10-25 (16-22 hours over 2-3 days)

**Documentation Requirements:**
1. Create `DEFERRED_WORK.md` with detailed implementation plans
2. Add TD3/WS2 tasks to `docs/tasks.yaml`
3. Update `CHANGELOG.md` with deferral decision
4. Include deferral rationale in Wave 1 session notes

---

## Consequences

### Positive

**Scope Management:**
- Wave 1 integration completed on time (37 hours baseline estimate)
- Clean merge to main without rushed implementation
- Quality gates validated with realistic expectations (93% unit, 100% integration)
- Documentation reflects actual state (no aspirational claims)

**Risk Reduction:**
- Avoided integration conflicts from simultaneous type system changes
- Prevented scope creep during critical infrastructure merge
- Clear backlog for Wave 2 with implementation plans ready

**Team Velocity:**
- Focused effort on high-value infrastructure (CompensatingTransaction, Pydantic V2)
- Reduced cognitive load during integration
- Faster wave completion enables earlier Wave 2 start

### Negative

**Short-Term Trade-offs:**
- 49 mypy warnings visible in CI output (non-blocking)
- No cache optimization metrics (unknown hit rate)
- Potential missed cost savings (~$50-100/month) during deferral period
- Developer IDE experience not optimal (missing type hints)

**Technical Debt:**
- Type coverage remains ~60% instead of target 100%
- Cache implementation functional but not optimized
- Two workstreams in backlog requiring eventual completion

### Neutral

**Process Impact:**
- Demonstrates prioritization discipline (scope > features)
- Establishes precedent for deferral documentation standards
- Validates wave-based integration model (ADR-001)
- Aligns with ADR-023 technical debt policy (15-20% sprint capacity)

---

## Implementation Plan (Wave 2)

### TD3: MyPy Strict Mode (8-12 hours)

**Phase 1: Configuration (2 hours)**
```toml
# pyproject.toml
[tool.mypy]
strict = true
python_version = "3.9"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
```

**Phase 2: Fix Core Modules (4-6 hours)**
Priority order:
1. `src/config.py` - Configuration management
2. `src/transactions.py` - Error handling
3. `src/dedupe.py` - Hash and vector store utilities
4. `src/processor.py` - Main pipeline orchestration
5. `src/pipeline.py` - Pipeline framework
6. `src/stages/*.py` - All pipeline stages

**Phase 3: Add Type Stubs (2-3 hours)**
- `requests` library (no official stubs)
- Internal type definitions (TypedDict for API responses)
- Protocol definitions for stage interfaces

**Phase 4: CI Integration (1 hour)**
- Update pre-commit hook to enforce strict mode
- Add mypy to GitHub Actions with fail-on-error

**Success Criteria:**
- `mypy src/ --strict` exits with 0 warnings
- All functions have complete type signatures
- IDE autocomplete fully functional
- Pre-commit hook blocks untyped code

### WS2: Embedding Cache Optimization (8-10 hours)

**Phase 1: Cache Key Strategy (2 hours)**
```python
def generate_cache_key(doc: Document, model: str) -> str:
    """Generate stable cache key from document hash + model version."""
    key_material = f"{doc.sha256_hex}:{model}:v1"
    return hashlib.sha256(key_material.encode()).hexdigest()[:16]
```

**Phase 2: Cache Metrics (3 hours)**
- Add `CacheMetrics` dataclass (hits, misses, evictions, size_bytes)
- Instrument cache operations with logging
- Expose metrics via `/metrics` endpoint (future observability)
- Create Grafana dashboard spec

**Phase 3: Cache Management (2-3 hours)**
- Implement LRU eviction policy (max 1000 entries or 100MB)
- Add cache invalidation for schema version changes
- Create cache warming strategy for common document types
- Add admin CLI for cache inspection/clearing

**Phase 4: Testing (2-3 hours)**
- Unit tests for cache key generation (determinism, collision resistance)
- Integration tests for cache hit/miss scenarios
- Performance benchmarks (cache overhead <5ms per lookup)
- Stress tests for cache eviction under load

**Success Criteria:**
- Cache hit rate ≥60% for repeated document processing
- Cache lookup latency <5ms P95
- No more than 100MB memory footprint
- Graceful degradation on cache failures
- Comprehensive observability (metrics + logs)

---

## Validation Criteria

**TD3 Completion Checklist:**
- [ ] `mypy src/ --strict` passes with 0 errors
- [ ] All 49 existing warnings resolved
- [ ] Type stubs added for third-party libraries
- [ ] Pre-commit hook enforces strict mode
- [ ] CI pipeline fails on new type violations
- [ ] Documentation updated with type annotation guidelines

**WS2 Completion Checklist:**
- [ ] Cache key generation tested with Hypothesis (property-based)
- [ ] Cache metrics visible in logs and dashboards
- [ ] LRU eviction tested under memory pressure
- [ ] Cache invalidation strategy documented
- [ ] Performance benchmarks show <5ms overhead
- [ ] Integration tests cover all cache paths (hit/miss/eviction)

---

## Alternatives Considered

### Alternative 1: Include TD3/WS2 in Wave 1
**Rejected** - Scope creep risk:
- Wave 1 already integrates 5 workstreams (37 hours)
- Type system changes could introduce integration conflicts
- Cache optimization not blocking for core functionality
- Violates iterative phasing principle (ADR-001)

**Estimated impact:** +3 days to Wave 1 timeline, increased merge complexity

### Alternative 2: Abandon TD3/WS2 Permanently
**Rejected** - Value loss:
- Type safety improves long-term maintainability
- Cache optimization provides measurable cost savings
- Developer experience impact (IDE autocomplete)
- Technical debt accumulation

**Estimated impact:** $600-1,200/year in increased bug costs + $50-100/month API costs

### Alternative 3: Implement TD3 Only (Defer WS2)
**Rejected** - Inconsistent prioritization:
- Both workstreams have similar scope (8-12 hours)
- Both are enhancements, not core functionality
- Splitting defeats wave-based integration model
- Better to batch related improvements in Wave 2

### Alternative 4: Selected Approach (Document + Defer Both)
**Accepted** - Balanced scope management:
- Clear documentation ensures work not forgotten
- Detailed implementation plans enable fast Wave 2 start
- Demonstrates prioritization discipline
- Aligns with technical debt policy (ADR-023)

---

## Compliance

This decision aligns with established architectural patterns:

**ADR-001 (Iterative Phasing):**
- Validates wave-based integration model
- Demonstrates scope management discipline
- Prioritizes infrastructure over enhancements

**ADR-023 (Technical Debt Reduction):**
- Follows 15-20% sprint capacity guidance
- Documents technical debt transparently
- Establishes clear payback timeline (Wave 2)

**Industry Best Practices:**
- **Agile Scope Management:** Defer non-critical features to maintain velocity
- **Technical Debt Budgeting:** Document all deferred work with implementation plans
- **Definition of Done:** Wave 1 complete when core infrastructure functional, not when all enhancements delivered

---

## References

**Internal Documentation:**
- `/Users/krisstudio/Developer/Projects/autoD/docs/DEFERRED_WORK.md` - Detailed implementation plans
- `/Users/krisstudio/Developer/Projects/autoD/docs/sessions/2025-10-23.md` - Wave 1 integration audit trail
- `/Users/krisstudio/Developer/Projects/autoD/docs/CHANGELOG.md` - Version history

**Related Workstreams:**
- TD3: `git worktree list` - workstream/mypy-strict (if exists)
- WS2: `git worktree list` - workstream/embedding-cache-optimization (if exists)

**Quality Gate Results (Wave 1):**
- MyPy: 49 warnings (non-critical)
- Unit Tests: 469/497 passed (93%, excluding WS1 test issues)
- Integration Tests: 73/73 passed (100%)
- Coverage: 62.04% (exceeds 60% threshold)

---

**Last Updated:** 2025-10-23
**Next Review:** 2025-10-24 (Wave 2 kickoff)
**Owner:** Technical Lead
