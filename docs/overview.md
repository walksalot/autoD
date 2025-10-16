# autoD Project Overview

**Last Updated**: 2025-10-16
**Status**: Documentation Complete, Ready for Implementation
**Current Phase**: Week 0 - Foundation Documentation

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

### Completed (Week 0)

✅ **Foundation Documentation** (2025-10-16)
- 33+ documentation files
- 3,500+ lines of reference material
- Documentation organized by audience:
  - **Operations**: RUNBOOK.md (production operations)
  - **Developers**: API_DOCS.md, TESTING_GUIDE.md, CONTRIBUTING.md
  - **All Users**: QUICK_REFERENCE.md, TROUBLESHOOTING.md

**Key Documents**:
- `docs/initial_implementation_plan.md` - Complete implementation blueprint
- `docs/CODE_ARCHITECTURE.md` - Architecture patterns and examples
- `docs/PROCESSOR_GUIDE.md` - Main processor module guide
- `docs/IMPLEMENTATION_ROADMAP.md` - 4-week implementation plan
- `docs/RUNBOOK.md` - Production operations runbook
- `docs/API_DOCS.md` - Python module API reference
- `docs/TROUBLESHOOTING.md` - Consolidated troubleshooting guide
- `docs/QUICK_REFERENCE.md` - Single-page cheat sheet
- `docs/TESTING_GUIDE.md` - Comprehensive testing guide
- `docs/CONTRIBUTING.md` - Contribution workflow and guidelines

### In Progress

⏳ **Week 1 - Core Pipeline** (Target: 2025-10-23)
- Status: Not started
- Blockers: None
- Next: Implement src/processor.py with 9-step pipeline

### Upcoming

📋 **Week 2 - Resilience** (Target: 2025-10-30)
- Retry logic with exponential backoff
- Circuit breaker pattern
- Compensating transactions
- Structured JSON logging

📋 **Week 3 - Observability** (Target: 2025-11-06)
- Token counting with tiktoken
- Cost calculation and alerts
- Performance logging
- Monitoring dashboard

📋 **Week 4 - Production Ready** (Target: 2025-11-13)
- PostgreSQL migration
- Alembic migrations
- Production deployment guide
- Load testing and security audit

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
├── src/                       # Application code (TO BE IMPLEMENTED)
│   ├── config.py              # Pydantic configuration
│   ├── models.py              # SQLAlchemy models
│   ├── processor.py           # Main pipeline
│   ├── api_client.py          # OpenAI API client
│   ├── vector_store.py        # Vector store operations
│   ├── dedupe.py              # SHA-256 deduplication
│   ├── schema.py              # JSON schema validation
│   ├── prompts.py             # Prompt templates
│   ├── token_counter.py       # Token/cost tracking
│   ├── logging_config.py      # Structured logging
│   └── database.py            # Database manager
│
├── tests/                     # Test suite (TO BE IMPLEMENTED)
│   ├── conftest.py
│   ├── unit/
│   ├── integration/
│   └── e2e/
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

### Priority 1: Implement Core Pipeline
**Status**: Pending
**Target**: Week 1 (2025-10-23)
**Estimated Time**: 8-12 hours
**Risk**: Medium

**Tasks**:
1. Create `src/processor.py` with ProcessingResult class
2. Implement 9-step processing pipeline
3. Write unit tests (target 90%+ coverage)
4. Create integration test for full pipeline

**Success Criteria**:
- ✅ Pipeline processes 1 PDF end-to-end
- ✅ SHA-256 deduplication prevents duplicates
- ✅ All 5 pipeline stages execute in correct order
- ✅ Unit tests pass with 90%+ coverage

### Priority 2: Add Retry Logic
**Status**: Pending (blocked by Priority 1)
**Target**: Week 1-2 (2025-10-30)
**Estimated Time**: 6-8 hours
**Risk**: Low

**Tasks**:
1. Implement comprehensive retry predicate (ALL transient errors)
2. Add exponential backoff with tenacity
3. Implement circuit breaker pattern
4. Write retry logic tests
5. Verify 95%+ success rate under simulated failures

**Success Criteria**:
- ✅ Retry logic handles RateLimitError, APIConnectionError, Timeout, APIError (5xx)
- ✅ Exponential backoff: 2-60 seconds, max 5 attempts
- ✅ 95%+ success rate under simulated failures

### Priority 3: Set Up Testing Infrastructure
**Status**: Pending (no blockers, can run parallel)
**Target**: Week 1 (2025-10-23)
**Estimated Time**: 4-6 hours
**Risk**: Low

**Tasks**:
1. Create `tests/conftest.py` with fixtures
2. Implement mock OpenAI client
3. Create sample PDF generators
4. Set up pytest configuration
5. Configure coverage reporting

**Success Criteria**:
- ✅ pytest runs with all fixtures working
- ✅ Mock OpenAI client returns realistic responses
- ✅ Test PDFs generate correct SHA-256 hashes
- ✅ Coverage reporting configured

---

## Risks & Mitigations

### Active Risks

**Risk 1: Documentation Created Before Implementation**
- **Severity**: High
- **Impact**: Docs may not match final implementation
- **Mitigation**: Documentation serves as specification; implementation should follow docs
- **Status**: Accepted (documentation-driven development)

**Risk 2: Documentation Drift**
- **Severity**: Medium
- **Impact**: Docs may become outdated as code evolves
- **Mitigation**: Require doc updates in PRs, quarterly reviews, automated testing
- **Status**: Monitoring

**Risk 3: Test Coverage Target Ambitious (80%+)**
- **Severity**: Low
- **Impact**: May slow development velocity
- **Mitigation**: Differential coverage by module, focus on critical paths
- **Status**: Monitoring

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
Week 0 (Oct 16-22): Documentation Complete ✅
  ├─ Gap analysis
  ├─ RUNBOOK.md
  ├─ API_DOCS.md
  ├─ TROUBLESHOOTING.md
  ├─ QUICK_REFERENCE.md
  ├─ TESTING_GUIDE.md
  └─ CONTRIBUTING.md

Week 1 (Oct 23-29): Core Pipeline ⏳
  ├─ ProcessingResult class
  ├─ 9-step pipeline
  ├─ SHA-256 deduplication
  ├─ Database storage
  └─ Unit tests (90%+)

Week 2 (Oct 30-Nov 5): Resilience 📋
  ├─ Retry logic
  ├─ Circuit breaker
  ├─ Compensating transactions
  └─ Structured logging

Week 3 (Nov 6-12): Observability 📋
  ├─ Token counting
  ├─ Cost calculation
  ├─ Performance logging
  └─ Monitoring dashboard

Week 4 (Nov 13-19): Production Ready 📋
  ├─ PostgreSQL migration
  ├─ Alembic migrations
  ├─ Load testing
  └─ Security audit
```

**Estimated v1.0 Release**: 2025-11-13

---

## Metrics

### Documentation Coverage
- **Total Files**: 33+
- **Total Lines**: 3,500+
- **Gap Coverage**: 100%

### Implementation Progress
- **Total Modules**: 0 of 12 (0%)
- **Test Coverage**: 0% (target: 80%+)
- **Lines of Code**: 0

### Timeline Progress
- **Elapsed Days**: 0
- **Remaining Days**: 28
- **On Track**: Yes ✅

---

**Last Updated**: 2025-10-16
**Next Review**: After Week 1 completion (2025-10-23)
