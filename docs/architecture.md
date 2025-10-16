# Architecture Documentation — autoD

**Status:** 🚧 Under Construction
**Last Updated:** 2025-10-16T00:00:00Z
**Current Implementation Phase:** Phase 0 (Infrastructure Foundation)

---

## Overview

autoD (Automated Document Processing) is a production-grade PDF metadata extraction system built on OpenAI's Responses API. The system processes PDF documents, extracts structured metadata, stores results in a database, and maintains a vector store for cross-document context.

**Design Philosophy:**
- Build for actual needs, not hypothetical scale
- Iterative delivery with working software weekly
- Testable, observable, resilient
- Cross-database compatibility (SQLite → PostgreSQL migration path)

**Current Implementation Status:** Pre-Phase 0 (planning complete, implementation pending)

---

## System Architecture

*This section will be populated as implementation progresses through 10 phases.*

### Architectural Approach

The system follows a **4-week iterative phasing strategy** (see ADR 0001) with working software delivered weekly:

- **Week 1:** Core Pipeline (Foundation) — Database, deduplication, basic API integration
- **Week 2:** Resilience (Error Handling) — Retry logic, transactions, structured logging
- **Week 3:** Observability (Understanding) — Token tracking, cost monitoring, testing
- **Week 4:** Production (Deployment) — Vector stores, migrations, PostgreSQL path

---

## Planned Architecture Components

### 1. Configuration Layer

**File:** `/Users/krisstudio/Developer/Projects/autoD/src/config.py`
**Status:** ⏳ Phase 1 (Not yet implemented)
**Technology:** Pydantic Settings V2

**Purpose:**
- Type-safe environment variable management
- Environment-based configuration overrides
- Validation of required settings (API keys, database URLs)

**Key Settings:**
- OpenAI API key and model selection
- Database connection strings
- Vector store configuration
- Cost tracking parameters
- Retry/timeout configuration

---

### 2. Database Layer

**Files:**
- `/Users/krisstudio/Developer/Projects/autoD/src/models.py` — SQLAlchemy models
- `/Users/krisstudio/Developer/Projects/autoD/src/database.py` — Database initialization

**Status:** ⏳ Phase 2 (Not yet implemented)
**Technology:** SQLAlchemy 2.0 with generic JSON type

**Architecture Decision:**
- Generic `JSON` type (not `JSONB`) for cross-database compatibility
- Supports SQLite (development) and PostgreSQL (production)
- Migration path via Alembic

**Document Model (40+ fields planned):**
- File identity: `sha256_hex`, `original_filename`
- Timestamps: `created_at`, `processed_at`
- OpenAI references: `source_file_id`, `vector_store_file_id`
- Metadata: `metadata_json` (full API response)
- Status tracking: `status`, `error_message`

**Key Features:**
- SHA-256 deduplication via unique constraint
- Status-based processing flow
- Full API response preservation (nothing lost)
- Extensible via migrations

---

### 3. Schema Layer

**File:** `/Users/krisstudio/Developer/Projects/autoD/src/schema.py`
**Status:** ⏳ Phase 3 (Not yet implemented)
**Technology:** Pydantic V2 + OpenAI Structured Outputs

**Purpose:**
- Strict JSON schema with `additionalProperties: false`
- Schema versioning for evolution
- Type-safe metadata extraction

**Planned Fields:**
- Document type classification
- Temporal data (dates, deadlines)
- Entity extraction (organizations, people, amounts)
- Document relationships
- Confidence scores

---

### 4. Prompt Layer

**File:** `/Users/krisstudio/Developer/Projects/autoD/src/prompts.py`
**Status:** ⏳ Phase 4 (Not yet implemented)
**Technology:** OpenAI Responses API (NOT Chat Completions)

**Architecture:**
- Three-role prompt structure (system, user, assistant examples)
- Prompt caching for cost optimization (>90% cache hit target)
- Model-specific prompt optimization (GPT-5 prompt engineering)

**Critical Constraint:**
- MUST use Responses API endpoint
- NEVER use Chat Completions endpoint
- See `/Users/krisstudio/Developer/Projects/autoD/docs/responses_api_endpoint.md`

---

### 5. Deduplication Layer

**File:** `/Users/krisstudio/Developer/Projects/autoD/src/dedupe.py`
**Status:** ⏳ Phase 5 (Not yet implemented)
**Technology:** SHA-256 file hashing

**Purpose:**
- Prevent duplicate processing
- Fast lookup via indexed `sha256_hex` column
- Binary-identical file detection

**Implementation:**
- Hash computed before API call
- Database query checks for existing hash
- Skip processing if duplicate found

---

### 6. Vector Store Layer

**File:** `/Users/krisstudio/Developer/Projects/autoD/src/vector_store.py`
**Status:** ⏳ Phase 6 (Not yet implemented)
**Technology:** OpenAI File Search + Vector Stores API

**Purpose:**
- Cross-document context for API queries
- Semantic search across all processed documents
- Persistent vector store (survives cache deletion)

**Architecture:**
- One persistent vector store for all documents
- Vector store ID cached to file (`.vector_store_id`)
- File attributes for metadata (up to 16 key-value pairs)
- Graceful degradation if vector upload fails

**Failure Handling:**
- Database is source of truth
- Vector store upload is best-effort
- Status field tracks upload state: `pending_vector_upload`, `completed`, `vector_upload_failed`

---

### 7. API Client Layer

**File:** `/Users/krisstudio/Developer/Projects/autoD/src/api_client.py`
**Status:** ⏳ Phase 7 (Not yet implemented)
**Technology:** OpenAI Python SDK + Tenacity retry logic

**Purpose:**
- Reliable OpenAI API communication
- Comprehensive retry logic for all transient errors
- Response parsing and validation

**Retry Strategy:**
- Exponential backoff (2s, 4s, 8s, 16s, 32s)
- Retry on: Rate limits (429), connection errors, timeouts, 5xx errors
- No retry on: Authentication (401), bad requests (400), not found (404)
- Max 5 attempts before failure

**Critical Fix:**
- Original plan only retried `RateLimitError` and `APIConnectionError`
- New design retries ALL transient errors (timeouts, 500s, 502s, 503s)

---

### 8. Token Tracking Layer

**File:** `/Users/krisstudio/Developer/Projects/autoD/src/token_counter.py`
**Status:** ⏳ Phase 8 (Not yet implemented)
**Technology:** tiktoken (o200k_base encoding for GPT-5)

**Purpose:**
- Accurate cost estimation before API calls
- Cost tracking after API calls
- Budget validation and monitoring

**Metrics Tracked:**
- Prompt tokens (input)
- Cached prompt tokens (prompt caching)
- Output tokens
- Total cost in USD
- Cost per document

**Usage:**
- Pre-flight estimation with `tiktoken.encoding_for_model()`
- Post-call actuals from `response.usage` object
- Structured logging of all metrics

---

### 9. Main Processor (Pipeline Orchestration)

**File:** `/Users/krisstudio/Developer/Projects/autoD/src/processor.py`
**Status:** ⏳ Phase 9 (Not yet implemented)
**Technology:** Pipeline pattern with discrete processing stages

**Architecture:**
- Abstract `ProcessingStage` base class
- Immutable `ProcessingContext` passed through stages
- Clear transaction boundaries
- Observable stage transitions

**Pipeline Stages:**
1. `ComputeSHA256Stage` — Hash computation
2. `DedupeCheckStage` — Duplicate detection
3. `APICallStage` — OpenAI Responses API invocation
4. `MetadataExtractionStage` — Parse and validate response
5. `DatabasePersistStage` — Save to database
6. `VectorStoreUploadStage` — Upload to vector store

**Error Handling:**
- Each stage can succeed or fail independently
- Failures captured in context
- Processing stops at first error
- Audit trail preserved in database

---

### 10. Testing Layer

**Directory:** `/Users/krisstudio/Developer/Projects/autoD/tests/`
**Status:** ⏳ Phase 10 (Not yet implemented)
**Technology:** pytest + coverage.py

**Coverage Target:** >90%

**Test Categories:**
- Unit tests for each pipeline stage
- Integration tests for full pipeline
- Retry logic validation
- Database transaction safety
- Mock API tests (no actual API calls)
- End-to-end tests with sample PDFs

**Fixtures:**
- In-memory SQLite for test isolation
- Sample PDF files
- Mock OpenAI client
- Test configuration

---

## Technology Stack

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| **Language** | Python | 3.11+ | Modern async/await support |
| **Database** | SQLAlchemy | 2.0 | ORM with future-proof API |
| **DB (Dev)** | SQLite | - | Local development, no Docker |
| **DB (Prod)** | PostgreSQL | 14+ | Production scalability |
| **API** | OpenAI Responses API | - | Structured metadata extraction |
| **Vector Store** | OpenAI File Search | - | Cross-document context |
| **Validation** | Pydantic | V2 | Type-safe config + schemas |
| **Retry** | Tenacity | - | Exponential backoff |
| **Tokens** | tiktoken | - | o200k_base encoding (GPT-5) |
| **Migrations** | Alembic | - | Schema evolution |
| **Testing** | pytest | - | Unit + integration tests |
| **Coverage** | coverage.py | - | Code coverage analysis |
| **Logging** | Python logging | - | Structured JSON logs |

---

## Data Flow

```
┌─────────────┐
│ inbox/*.pdf │ PDF files arrive
└──────┬──────┘
       │
       ▼
┌──────────────────┐
│ ComputeSHA256    │ Hash file
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ DedupeCheck      │ Query database by hash
└────────┬─────────┘
         │
         ├─ Duplicate? ──▶ Skip processing
         │
         ▼ New file
┌──────────────────┐
│ Upload to OpenAI │ Files API
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Call Responses   │ Extract metadata (with retry)
│ API              │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Persist to DB    │ Save Document record
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Upload to Vector │ Best-effort (graceful failure)
│ Store            │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Structured Logs  │ JSON logs with metrics
└──────────────────┘
```

---

## Key Architectural Decisions

### ADR 0001: Iterative Phasing Over Parallel Development
**Status:** ✅ Accepted
**Date:** 2025-10-16
**File:** `/Users/krisstudio/Developer/Projects/autoD/docs/adr/0001-iterative-phasing-over-parallel-development.md`

**Decision:** Adopt 4-week iterative phasing with working software delivered weekly, replacing original 8-phase parallel approach.

**Rationale:**
- Early validation of core assumptions
- Reduced integration risk
- Better testability via pipeline pattern
- Continuous delivery of value

**Architectural Fixes Included:**
1. Generic JSON type (cross-database compatibility)
2. Pipeline pattern (testability)
3. Compensating transactions (data safety)
4. Comprehensive retry logic (resilience)
5. Build-for-actual-scale (pragmatism)

---

### Future ADRs (Planned)

**ADR 0002:** PostgreSQL vs SQLite for production
**ADR 0003:** Vector store implementation strategy
**ADR 0004:** Structured output schema design
**ADR 0005:** Prompt caching optimization approach

---

## Observability

### Structured Logging

**Format:** JSON logs for queryable analysis

**Fields Tracked:**
- `timestamp` (ISO 8601 UTC)
- `level` (INFO, WARNING, ERROR)
- `message` (human-readable description)
- `logger` (module name)
- `pdf_path` (file being processed)
- `sha256_hex` (file hash)
- `doc_id` (database ID)
- `stage` (pipeline stage name)
- `duration_ms` (processing time)
- `cost_usd` (API cost)
- `prompt_tokens`, `output_tokens` (token counts)
- `status` (processing status)

**Log Analysis Examples:**
```bash
# Total cost
cat autod.log | jq -s 'map(select(.cost_usd)) | map(.cost_usd) | add'

# Average processing time
cat autod.log | jq -s 'map(select(.duration_ms)) | add / length'

# Error analysis
cat autod.log | jq 'select(.level == "ERROR")'
```

---

## Security Considerations

**API Key Management:**
- API keys stored in `.env` file (git-ignored)
- Loaded via Pydantic Settings
- Never logged or committed to version control

**Database Security:**
- No sensitive data in metadata (only document metadata)
- Local SQLite for development
- Production PostgreSQL with connection encryption

**File Handling:**
- PDFs processed in `inbox/` directory (git-ignored)
- No permanent storage of raw PDFs
- Deduplication prevents reprocessing

---

## Scalability Considerations

**Current Design:**
- **Target:** 10 PDFs/day (~300/month)
- **Storage:** SQLite sufficient for development
- **API Limits:** Within OpenAI rate limits
- **Cost:** <$100/month for 300 PDFs

**Future Scaling (if needed):**
- Migrate to PostgreSQL for production
- Batch processing for high volumes
- Async processing with asyncio
- Queue-based architecture (Celery/Redis)

**Philosophy:**
- Build for actual needs, not hypothetical scale
- Scale when bottlenecks are measured, not assumed
- Current design supports 100x growth before refactoring needed

---

## Migration Strategy

### SQLite → PostgreSQL

**When:** When single-user constraint becomes limiting OR data size exceeds SQLite limits

**How:**
1. Update `DATABASE_URL` in `.env`
2. Run Alembic migrations on PostgreSQL: `alembic upgrade head`
3. Migrate data with pgloader: `pgloader sqlite://autod.db postgresql://...`
4. Verify migration: `psql -c "SELECT COUNT(*) FROM documents;"`

**Compatibility:**
- Generic `JSON` type ensures cross-database compatibility
- SQLAlchemy 2.0 abstracts database differences
- No code changes required (configuration only)

---

## Error Handling Philosophy

**Graceful Degradation:**
- Database is source of truth (always commit)
- Vector store upload is best-effort (don't fail pipeline)
- Status field tracks processing state
- Error messages preserved for debugging

**Retry Strategy:**
- Transient errors retry automatically (5 attempts)
- Permanent errors fail fast (no retry)
- All retries logged with context

**Audit Trail:**
- All documents recorded, even failures
- Error messages truncated to 1000 chars
- Structured logs show full exception trace

---

## Current Implementation Status

### Completed
- ✅ Project initialization
- ✅ Delegation strategy
- ✅ ADR 0001 (architectural decision)
- ✅ CODE_ARCHITECTURE.md (implementation patterns)
- ✅ Continuous documentation workflow

### In Progress
- 🟡 Awaiting Phase 0 assignment (deployment-engineer)

### Pending
- ⏳ Phase 0: Infrastructure (git, requirements, directory structure)
- ⏳ Phase 1: Configuration (Pydantic settings)
- ⏳ Phase 2: Database (SQLAlchemy models)
- ⏳ Phase 3-10: Remaining implementation phases

---

## References

**Planning Documents:**
- [DELEGATION_STRATEGY.md](/Users/krisstudio/Developer/Projects/autoD/docs/DELEGATION_STRATEGY.md) - Agent assignment matrix
- [IMPLEMENTATION_CHANGES.md](/Users/krisstudio/Developer/Projects/autoD/docs/IMPLEMENTATION_CHANGES.md) - Plan deviation tracking
- [CODE_ARCHITECTURE.md](/Users/krisstudio/Developer/Projects/autoD/docs/CODE_ARCHITECTURE.md) - Implementation patterns
- [initial_implementation_plan.md](/Users/krisstudio/Developer/Projects/autoD/docs/initial_implementation_plan.md) - Original 8-phase plan

**Technical References:**
- [responses_api_endpoint.md](/Users/krisstudio/Developer/Projects/autoD/docs/responses_api_endpoint.md) - OpenAI Responses API guide
- [how_to_count_tokens_w_tik_tok_token.md](/Users/krisstudio/Developer/Projects/autoD/docs/how_to_count_tokens_w_tik_tok_token.md) - Token counting guide
- [gpt_5_prompt_engineering.md](/Users/krisstudio/Developer/Projects/autoD/docs/gpt_5_prompt_engineering.md) - Prompt optimization

**External Documentation:**
- [SQLAlchemy 2.0 Docs](https://docs.sqlalchemy.org/en/20/)
- [Pydantic V2 Docs](https://docs.pydantic.dev/latest/)
- [Tenacity Docs](https://tenacity.readthedocs.io/)
- [tiktoken Docs](https://github.com/openai/tiktoken)
- [OpenAI API Reference](https://platform.openai.com/docs/api-reference)

---

## Update History

| Date | Event | Updated By |
|------|-------|------------|
| 2025-10-16 | Initial architecture documentation created | technical-writer |

---

**Maintained By:** technical-writer agent
**Update Trigger:** Phase completions, architectural decisions, implementation changes
**Next Update:** After Phase 0 completion (infrastructure artifacts)
**Status:** 🚧 Living document (updated throughout implementation)
