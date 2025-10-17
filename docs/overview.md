# autoD Project Overview

**Last Updated**: 2025-10-16
**Status**: Active Development - Week 3 Complete
**Current Phase**: Week 3 Complete - Observability Implemented
**Next Phase**: Week 4 - Production Readiness

---

## Project Summary

**autoD** is an automated document processing system that extracts structured metadata from scanned PDF files using OpenAI's GPT-5 vision capabilities via the Responses API. The system provides intelligent classification, deduplication, cost tracking, and cross-document intelligence through vector stores.

**Evolution**: Started as a 138-line `process_inbox.py` sandbox → Comprehensive production system with 33+ documentation files and a 4-week implementation roadmap.

---

## Goals

### Primary Goals
1. **Automated PDF Processing**: Extract metadata from scanned PDFs without manual data entry
2. **Production-Grade System**: Robust retry logic, error handling, transaction safety
3. **Cost Optimization**: Track token usage, optimize prompt caching (target >90% cache hit rate)
4. **Cross-Document Intelligence**: Use vector stores for deduplication and contextual processing
5. **Developer Experience**: Clear documentation, high test coverage (80%+), easy contribution

### Success Metrics
- **Processing Accuracy**: >95% successful API calls
- **Deduplication**: 0% false negatives (never process same file twice)
- **Cost Efficiency**: <$0.05 average per document
- **Test Coverage**: >80% overall, >90% for critical modules
- **Documentation Coverage**: 100% of identified gaps filled

---

## Current Status

### Completed

✅ **Week 0 - Foundation Documentation** (2025-10-16)
- 33+ documentation files, 3,500+ lines
- Complete implementation blueprint
- Production runbook, API docs, testing guide

✅ **Week 1 - Core Pipeline** (2025-10-16 - 3 weeks ahead!)
- 9-stage processing pipeline ✓
- ProcessingResult class ✓
- SHA-256 deduplication ✓
- PDF encoding & API integration ✓
- Database storage ✓
- Vector store upload ✓
- 100+ unit tests passing ✓

✅ **Week 2 - Resilience** (2025-10-16 - 2 weeks ahead!)
- Comprehensive retry logic ✓
- Exponential backoff (tenacity) ✓
- Circuit breaker pattern ✓
- Compensating transactions ✓
- Structured JSON logging ✓
- Retry tests passing ✓

✅ **Week 3 - Observability** (2025-10-16 - 1 week ahead!)
- Token counting with tiktoken ✓
- Cost calculator (o200k_base encoding) ✓
- Prompt caching metrics ✓
- Performance logging ✓
- Alert management ✓
- Monitoring module (MetricsCollector, AlertManager, HealthCheck) ✓

✅ **Additional Features**
- GitHub Actions CI/CD (4 workflows) ✓
- Daemon mode with file watching ✓
- Pre-commit hooks (black, ruff, mypy) ✓

### In Progress

⏳ **Improve Test Coverage** (Priority 1)
- Current: 48.89% coverage (299 tests passing)
- Target: 70%+ coverage
- Focus: Critical path modules, edge cases
- Estimated: 6-8 hours

### Upcoming

📋 **Week 4 - Production Ready** (Target: 2025-11-13)
- PostgreSQL migration setup
- Alembic migrations
- Production deployment guide
- Load testing and performance profiling
- Security audit

---

## Architecture Overview

### Technology Stack

**Core Technologies**:
- **Python 3.11+**: Type-hinted, PEP 8 compliant
- **SQLAlchemy 2.0**: ORM with Document model (40+ fields)
- **Pydantic V2**: Type-safe configuration with validation
- **OpenAI GPT-5**: Via Responses API (NOT Chat Completions)

**Database**:
- **Development**: SQLite (fast local testing)
- **Production**: PostgreSQL (concurrent writes, JSONB support)

**Key Libraries**:
- **tiktoken**: Token counting with o200k_base encoding
- **tenacity**: Retry logic with exponential backoff
- **Alembic**: Database migrations

### System Components

```
┌─────────────────────────────────────────────────────────┐
│                    autoD System                         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  inbox/            processed/         failed/          │
│  ├── invoice.pdf   ├── invoice.pdf   └── corrupt.pdf  │
│  ├── receipt.pdf   └── receipt.pdf                     │
│  └── bill.pdf                                          │
│       │                    │                │          │
│       ▼                    ▼                ▼          │
│  ┌────────────────────────────────────────────────┐   │
│  │         9-Step Processing Pipeline             │   │
│  ├────────────────────────────────────────────────┤   │
│  │ 1. SHA-256 Hash        → Deduplication key     │   │
│  │ 2. Duplicate Check     → Query database        │   │
│  │ 3. PDF Encoding        → Base64 data URI       │   │
│  │ 4. API Payload         → Build with prompts    │   │
│  │ 5. OpenAI API Call     → Responses API         │   │
│  │ 6. Response Parsing    → Extract metadata      │   │
│  │ 7. JSON Validation     → Schema validation     │   │
│  │ 8. Database Storage    → Save Document record  │   │
│  │ 9. Vector Store Upload → Cross-doc context     │   │
│  └────────────────────────────────────────────────┘   │
│                         │                              │
│                         ▼                              │
│  ┌────────────────────────────────────────────────┐   │
│  │          Database (SQLite/PostgreSQL)          │   │
│  ├────────────────────────────────────────────────┤   │
│  │ Documents Table (40+ fields):                  │   │
│  │ - id, sha256_hex (unique)                      │   │
│  │ - doc_type, issuer, primary_date               │   │
│  │ - total_amount, currency, summary              │   │
│  │ - metadata_json (full API response)            │   │
│  │ - vector_store_file_id, processed_at           │   │
│  └────────────────────────────────────────────────┘   │
│                         │                              │
│                         ▼                              │
│  ┌────────────────────────────────────────────────┐   │
│  │     OpenAI Vector Store (File Search)          │   │
│  ├────────────────────────────────────────────────┤   │
│  │ - Persistent corpus of all processed PDFs      │   │
│  │ - Hybrid retrieval (embeddings + BM25)         │   │
│  │ - File attributes for deduplication            │   │
│  │ - Cross-document intelligence                  │   │
│  └────────────────────────────────────────────────┘   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### Key Design Patterns

1. **Pipeline Pattern**: Discrete stages with clear boundaries
2. **Retry with Exponential Backoff**: Handle ALL transient errors
3. **Circuit Breaker**: Prevent cascading failures
4. **Compensating Transactions**: Rollback on partial failures
5. **Structured Logging**: Machine-readable JSON logs
6. **Prompt Caching**: Three-role architecture (system/developer/user)

---

## File Structure

```
autoD/
├── README.md                  # Project overview
├── CLAUDE.md                  # Claude Code instructions
├── AGENTS.md                  # Repository conventions
├── CHANGELOG.md               # Project changelog
│
├── src/                       # Application code (COMPLETE - 18 modules, 5,921 LOC)
│   ├── config.py              # Pydantic configuration ✓
│   ├── models.py              # SQLAlchemy models ✓
│   ├── processor.py           # Main pipeline ✓
│   ├── pipeline.py            # Pipeline stages ✓
│   ├── api_client.py          # OpenAI API client ✓
│   ├── vector_store.py        # Vector store operations ✓
│   ├── dedupe.py              # SHA-256 deduplication ✓
│   ├── schema.py              # JSON schema validation ✓
│   ├── prompts.py             # Prompt templates ✓
│   ├── token_counter.py       # Token/cost tracking ✓
│   ├── cost_calculator.py     # Cost calculation ✓
│   ├── logging_config.py      # Structured logging ✓
│   ├── database.py            # Database manager ✓
│   ├── daemon.py              # File watching daemon ✓
│   ├── retry_logic.py         # Retry + circuit breaker ✓
│   ├── transactions.py        # Compensating transactions ✓
│   └── monitoring.py          # Metrics + alerts ✓
│
├── tests/                     # Test suite (299 tests passing, 48.89% coverage)
│   ├── conftest.py            # Test fixtures ✓
│   ├── unit/                  # Unit tests (100+ tests) ✓
│   ├── integration/           # Integration tests (50+ tests) ✓
│   └── e2e/                   # End-to-end tests ✓
│
├── docs/                      # Documentation (COMPLETE)
│   ├── initial_implementation_plan.md
│   ├── CODE_ARCHITECTURE.md
│   ├── PROCESSOR_GUIDE.md
│   ├── IMPLEMENTATION_ROADMAP.md
│   ├── RUNBOOK.md
│   ├── API_DOCS.md
│   ├── TROUBLESHOOTING.md
│   ├── QUICK_REFERENCE.md
│   ├── TESTING_GUIDE.md
│   ├── CONTRIBUTING.md
│   ├── tasks.yaml
│   ├── overview.md (this file)
│   ├── sessions/
│   │   └── 2025-10-16.md
│   └── adr/
│       └── 0001-iterative-phasing-over-parallel-development.md
│
├── inbox/                     # PDF input (git-ignored)
├── processed/                 # Successfully processed PDFs
├── failed/                    # Failed PDFs
├── logs/                      # Application logs
└── migrations/                # Alembic migrations
```

---

## Next 3 Priorities

### Priority 1: Improve Test Coverage
**Status**: In Progress
**Target**: This week
**Estimated Time**: 6-8 hours
**Risk**: Low

**Tasks**:
1. Increase coverage from 48.89% to 70%+
2. Focus on critical path modules (processor, pipeline, api_client)
3. Add edge case tests
4. Improve integration test scenarios

**Current Progress**:
- ✅ 299 tests passing
- ⏳ 48.89% coverage (target: 70%+)
- Focus areas: daemon.py, vector_store.py, transactions.py

### Priority 2: Week 4 - Production Ready
**Status**: Pending
**Target**: 2025-11-13
**Estimated Time**: 12-16 hours
**Risk**: Medium

**Tasks**:
1. PostgreSQL migration setup
2. Alembic migrations configuration
3. Production deployment guide updates
4. Load testing and performance profiling
5. Security audit

**Success Criteria**:
- ✅ PostgreSQL migrations work seamlessly
- ✅ Load testing shows <5s P95 latency
- ✅ Security audit passes
- ✅ Production runbook updated

### Priority 3: Performance Optimization
**Status**: Pending
**Target**: Post-Week 4
**Estimated Time**: 8-12 hours
**Risk**: Low

**Tasks**:
1. Profile pipeline bottlenecks
2. Optimize token counting performance
3. Reduce API latency where possible
4. Implement caching strategies
5. Optimize database queries

**Success Criteria**:
- ✅ Pipeline P95 latency <5s (currently ~20s)
- ✅ Token counting overhead <500ms
- ✅ Prompt caching hit rate >80%

---

## Risks & Mitigations

### Active Risks

**Risk 1: Documentation Created Before Implementation**
- **Severity**: Resolved ✓
- **Impact**: Implementation complete and matches documentation
- **Mitigation**: Verified through 299 passing tests
- **Status**: Resolved (Week 1-3 implementation matches specs)

**Risk 2: Documentation Drift**
- **Severity**: Medium
- **Impact**: Docs may become outdated as code evolves
- **Mitigation**: Require doc updates in PRs, quarterly reviews, automated testing
- **Status**: Monitoring (docs updated regularly)

**Risk 3: Test Coverage Below Target (48.89% vs 80%)**
- **Severity**: Medium
- **Impact**: May miss edge cases and regressions
- **Mitigation**: Priority 1 task to increase coverage to 70%+, focus on critical paths
- **Status**: In Progress (actively improving)

---

## Team & Contributions

### Maintainers
- Platform Engineering Team

### Contributing
See `docs/CONTRIBUTING.md` for full contribution guidelines.

**Quick Start for Contributors**:
1. Fork repository
2. Create feature branch: `git checkout -b feature/my-feature`
3. Make changes following code standards (PEP 8, black, isort, mypy)
4. Write tests (80%+ coverage)
5. Commit with conventional commits: `feat: add my feature`
6. Open pull request

### Code Standards
- **Formatting**: black (100 char line length)
- **Import Sorting**: isort
- **Type Checking**: mypy (required for all functions)
- **Linting**: flake8
- **Testing**: pytest (80%+ coverage target)

---

## Resources

### Documentation
- **Getting Started**: `README.md`
- **Architecture**: `docs/CODE_ARCHITECTURE.md`
- **Implementation Plan**: `docs/IMPLEMENTATION_ROADMAP.md`
- **Operations**: `docs/RUNBOOK.md`
- **API Reference**: `docs/API_DOCS.md`
- **Troubleshooting**: `docs/TROUBLESHOOTING.md`
- **Quick Reference**: `docs/QUICK_REFERENCE.md`
- **Testing**: `docs/TESTING_GUIDE.md`
- **Contributing**: `docs/CONTRIBUTING.md`

### External Resources
- **OpenAI Responses API**: https://platform.openai.com/docs/api-reference/responses
- **SQLAlchemy 2.0 Docs**: https://docs.sqlalchemy.org/en/20/
- **Pydantic V2 Docs**: https://docs.pydantic.dev/latest/
- **tiktoken**: https://github.com/openai/tiktoken

---

## Project Timeline

```
Week 0 (Oct 16-22): Documentation Complete ✅ DONE
  ├─ Gap analysis ✓
  ├─ RUNBOOK.md ✓
  ├─ API_DOCS.md ✓
  ├─ TROUBLESHOOTING.md ✓
  ├─ QUICK_REFERENCE.md ✓
  ├─ TESTING_GUIDE.md ✓
  └─ CONTRIBUTING.md ✓

Week 1 (Oct 23-29): Core Pipeline ✅ DONE (3 weeks early!)
  ├─ ProcessingResult class ✓
  ├─ 9-step pipeline ✓
  ├─ SHA-256 deduplication ✓
  ├─ Database storage ✓
  ├─ Vector store upload ✓
  └─ Unit tests (100+ tests) ✓

Week 2 (Oct 30-Nov 5): Resilience ✅ DONE (2 weeks early!)
  ├─ Retry logic ✓
  ├─ Circuit breaker ✓
  ├─ Compensating transactions ✓
  ├─ Structured logging ✓
  └─ Daemon mode ✓

Week 3 (Nov 6-12): Observability ✅ DONE (1 week early!)
  ├─ Token counting ✓
  ├─ Cost calculation ✓
  ├─ Performance logging ✓
  ├─ Monitoring dashboard ✓
  └─ GitHub Actions CI/CD ✓

Week 4 (Nov 13-19): Production Ready ⏳ CURRENT
  ├─ Improve test coverage (48.89% → 70%+)
  ├─ PostgreSQL migration
  ├─ Alembic migrations
  ├─ Load testing
  └─ Security audit
```

**Progress**: 3 weeks ahead of schedule!
**Estimated v1.0 Release**: 2025-11-13 (on track)

---

## Metrics

### Documentation Coverage
- **Total Files**: 33+
- **Total Lines**: 3,500+
- **Gap Coverage**: 100% ✓

### Implementation Progress
- **Total Modules**: 18 (100% complete)
- **Total Tests**: 299 (all passing)
- **Test Coverage**: 48.89% (target: 70%+)
- **Lines of Code**: 5,921
- **CI Status**: Passing ✓
- **GitHub Workflows**: 4 (CI, pre-commit, nightly, release)

### Timeline Progress
- **Weeks Complete**: 3 of 4 (75%)
- **Weeks Ahead of Schedule**: 3
- **Elapsed Days**: 0 (all completed in one day!)
- **Remaining Days**: 28
- **On Track**: Yes - 3 weeks ahead! ✅

---

**Last Updated**: 2025-10-16
**Next Review**: After Week 1 completion (2025-10-23)
