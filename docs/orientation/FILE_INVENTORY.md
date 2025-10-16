# File Inventory — autoD Production System

**Generated:** 2025-10-16
**Repository:** /Users/krisstudio/Developer/Projects/autoD
**Total Files:** 108 tracked files
**Total Size:** 63M
**Total LOC (Python):** ~12,826 lines (excluding venv)

---

## Source Code (`src/`) — 4,290 LOC

### Core Application Files

| File | LOC | Purpose |
|------|-----|---------|
| `src/prompts.py` | 548 | Three-role prompt architecture (system/developer/user) optimized for 85% caching |
| `src/config.py` | 465 | Pydantic V2 settings with 21 validated environment variables, model policy enforcement |
| `src/processor.py` | 403 | Main 9-step processing pipeline orchestrator |
| `src/api_client.py` | 377 | Responses API client with circuit breaker and exponential backoff (4s-60s, 5 retries) |
| `src/vector_store.py` | 358 | Vector store operations with persistent ID caching and attribute management |
| `src/dedupe.py` | 336 | SHA-256 file hashing and duplicate detection |
| `src/token_counter.py` | 269 | Token counting and cost calculation using tiktoken (o200k_base encoding) |
| `src/schema.py` | 250 | JSON schema with 22 required fields for OpenAI strict mode |
| `src/pipeline.py` | 250 | Pipeline pattern infrastructure (ProcessingContext, ProcessingStage ABC) |
| `src/models.py` | — | SQLAlchemy Document model with 40+ fields |
| `src/database.py` | — | DatabaseManager with session management |
| `src/logging_config.py` | — | Structured JSON logging with rotation |

**Total src/ (main):** ~3,256 LOC

### Processing Stages (`src/stages/`)

| File | LOC | Purpose |
|------|-----|---------|
| `stages/sha256_stage.py` | — | Compute SHA-256 hash for deduplication |
| `stages/dedupe_stage.py` | — | Query database for duplicate documents |
| `stages/upload_stage.py` | — | Upload PDF to OpenAI Files API |
| `stages/api_stage.py` | — | Call Responses API for metadata extraction |
| `stages/persist_stage.py` | — | Save document to database |

**Total stages/:** ~1,034 LOC (estimated)

---

## Token Counter Module (`token_counter/`) — 2,632 LOC

**Purpose:** Standalone post-launch enhancement for pre-request cost estimation and validation.

| File | LOC | Purpose |
|------|-----|---------|
| `token_counter/responses_api.py` | 332 | Responses API token calculator |
| `token_counter/chat_api.py` | 322 | Chat Completions API token calculator |
| `token_counter/counter.py` | 310 | High-level facade API with auto-detection |
| `token_counter/validator.py` | 269 | Validation against actual API usage |
| `token_counter/file_estimators.py` | 264 | PDF token estimation (85-1,100 tokens/page) |
| `token_counter/cost.py` | 259 | Cost calculation with model pricing |
| `token_counter/primitives.py` | 251 | Low-level token counting primitives |
| `token_counter/encoding.py` | — | Model-to-encoding resolution (o200k_base, cl100k_base) |
| `token_counter/models.py` | — | Pydantic data models for token counting |
| `token_counter/exceptions.py` | — | Error definitions |

**Total token_counter/:** ~2,632 LOC

---

## Test Suite (`tests/`) — 4,904 LOC

### Test Infrastructure

| File | LOC | Purpose |
|------|-----|---------|
| `tests/conftest.py` | 525 | Pytest fixtures: in-memory DB, mock OpenAI client, sample PDFs |
| `tests/test_infrastructure.py` | 436 | Infrastructure validation tests |

### Unit Tests

| File | LOC | Purpose |
|------|-----|---------|
| `tests/unit/test_config.py` | 405 | Configuration validation (24 tests) |
| `tests/unit/test_primitives.py` | 285 | Token counting primitives tests |
| `tests/unit/test_encoding.py` | — | Encoding resolution tests |
| `tests/unit/test_cost.py` | — | Cost calculation tests (20 tests) |
| `tests/unit/test_file_estimators.py` | — | PDF estimation tests (24 tests) |
| `tests/unit/test_prompts.py` | — | Prompt structure tests |
| `tests/unit/test_schema.py` | — | JSON schema validation tests (23 tests) |
| `tests/unit/test_dedupe.py` | — | Deduplication tests (22 tests) |

### Integration Tests

| File | LOC | Purpose |
|------|-----|---------|
| `tests/integration/test_responses_api.py` | 401 | Responses API integration tests |
| `tests/integration/test_chat_api.py` | 478 | Chat API integration tests |
| `tests/integration/test_counter.py` | — | TokenCounter facade tests (18 tests) |
| `tests/integration/test_validator.py` | — | Validation framework tests (9 tests) |
| `tests/integration/test_processor.py` | — | End-to-end pipeline tests (10 tests) |

### Test Mocks (`tests/mocks/`)

| File | LOC | Purpose |
|------|-----|---------|
| `tests/mocks/mock_openai.py` | 373 | Mock Responses API with realistic responses |
| `tests/mocks/mock_vector_store.py` | 329 | Mock vector store operations |
| `tests/mocks/error_simulator.py` | 260 | Error injection for retry testing |
| `tests/mocks/mock_files_api.py` | 246 | Mock Files API for upload/download |

### Pipeline Tests

| File | LOC | Purpose |
|------|-----|---------|
| `tests/test_pipeline.py` | 379 | Pipeline pattern tests |
| `tests/test_dedupe_stage.py` | 242 | Deduplication stage tests |

**Total tests/:** ~4,904 LOC

---

## Configuration (`config/`)

| File | Purpose |
|------|---------|
| `config/pricing.yaml` | Model-specific pricing (GPT-5: $2.50-$0.15/M input, cached discounts) |
| `config/models.py` | Pydantic models for pricing configuration |

---

## Documentation (`docs/`) — 33+ files

### Core Documentation

| File | Lines | Purpose |
|------|-------|---------|
| `docs/initial_implementation_plan.md` | — | Complete implementation blueprint |
| `docs/CODE_ARCHITECTURE.md` | — | Architecture patterns and examples |
| `docs/IMPLEMENTATION_ROADMAP.md` | — | 4-week implementation plan |
| `docs/DELEGATION_STRATEGY.md` | — | Multi-agent coordination matrix |
| `docs/PARALLEL_EXECUTION_STRATEGY.md` | — | Git worktrees + multi-Claude delegation |
| `docs/CHANGELOG.md` | 411 | Complete project history |
| `docs/progress.md` | 258 | Live implementation dashboard |
| `docs/overview.md` | 417 | Project summary and status |

### Operational Documentation

| File | Purpose |
|------|---------|
| `docs/RUNBOOK.md` | Production operations guide |
| `docs/API_DOCS.md` | Python module API reference |
| `docs/PROCESSOR_GUIDE.md` | Main processor module guide |
| `docs/TROUBLESHOOTING.md` | Consolidated troubleshooting guide |
| `docs/QUICK_REFERENCE.md` | Single-page cheat sheet |
| `docs/TESTING_GUIDE.md` | Comprehensive testing guide |
| `docs/CONTRIBUTING.md` | Contribution workflow |

### API Reference Documentation

| File | Purpose |
|------|---------|
| `docs/file_inputs_for_the_responses_api.md` | PDF handling specifics (Base64, file URLs, token counting) |
| `docs/how_to_count_tokens_w_tik_tok_token.md` | tiktoken usage guide |

### Token Counting Module Documentation

| File | Lines | Purpose |
|------|-------|---------|
| `docs/token_counting/quickstart.md` | — | User guide with common patterns |
| `docs/token_counting/api_reference.md` | — | Complete API documentation |

### Orientation Documents

| File | Lines | Purpose |
|------|-------|---------|
| `docs/orientation/ORIENTATION-2025-10-16.md` | 781 | Complete repository orientation (this run) |
| `docs/orientation/FILE_INVENTORY.md` | — | This file |

### Architecture Decision Records (ADRs)

| File | Purpose |
|------|---------|
| `docs/adr/0001-iterative-phasing-over-parallel-development.md` | Strategic architecture decision |

### Session History

| File | Purpose |
|------|---------|
| `docs/sessions/2025-10-16-token-counting.md` | Token counting implementation session |
| `docs/sessions/2025-10-16-snapshot-1.md` | Project initialization snapshot |

---

## Examples (`examples/`)

| File | LOC | Purpose |
|------|-----|---------|
| `examples/token_counting_integration.py` | 270 | 8 working examples of token counting integration |

---

## Entry Points

### Primary Entry Point (Demo)
- **`process_inbox.py`** (~178 LOC) — Refactored CLI with argparse for processing PDFs

### Production Entry Point
- **`src/processor.py`** (403 LOC) — Main pipeline orchestrator

### Test Runner
- **`pytest tests/`** — Run all 244 tests

---

## Database Files

| File | Purpose |
|------|---------|
| `paper_autopilot.db` | SQLite database (git-ignored) |
| `.vector_store_id` | Persistent vector store ID cache (git-ignored) |

---

## Infrastructure Files

| File | Purpose |
|------|---------|
| `.gitignore` | 54 lines preventing sensitive data leaks |
| `requirements.txt` | 9 core dependencies (requests, openai, pydantic, etc.) |
| `requirements-dev.txt` | Development dependencies (pytest, black, mypy, etc.) |
| `Dockerfile` | Production container definition |
| `docker-compose.yml` | Multi-container setup |
| `paper-autopilot.service` | systemd service definition |

---

## Configuration Files (git-ignored)

| File | Purpose |
|------|---------|
| `.env` | Environment variables (API keys, configuration) |
| `logs/` | Application logs directory |
| `inbox/` | PDF input directory |
| `processed/` | Successfully processed PDFs |
| `failed/` | Failed PDFs |

---

## Top 10 Largest Source Files

| Rank | File | LOC | Purpose |
|------|------|-----|---------|
| 1 | `src/prompts.py` | 548 | Prompt architecture |
| 2 | `tests/conftest.py` | 525 | Test fixtures |
| 3 | `tests/integration/test_chat_api.py` | 478 | Chat API integration tests |
| 4 | `src/config.py` | 465 | Configuration management |
| 5 | `tests/test_infrastructure.py` | 436 | Infrastructure tests |
| 6 | `tests/unit/test_config.py` | 405 | Config validation tests |
| 7 | `src/processor.py` | 403 | Main pipeline |
| 8 | `tests/integration/test_responses_api.py` | 401 | Responses API integration tests |
| 9 | `tests/test_pipeline.py` | 379 | Pipeline tests |
| 10 | `src/api_client.py` | 377 | API client |

---

## Code Distribution

```
Total Python LOC: ~12,826 (excluding venv)

├── src/             4,290 LOC (33%) — Application code
├── token_counter/   2,632 LOC (21%) — Token counting module
├── tests/           4,904 LOC (38%) — Test suite
├── examples/          270 LOC (2%)  — Integration examples
└── scripts/           730 LOC (6%)  — Build/deployment scripts
```

---

## Test Coverage Breakdown

**Total Tests:** 244
**Test Coverage:** 42% overall

### Tests by Module
- **Unit Tests:** 166 tests (68%)
- **Integration Tests:** 68 tests (28%)
- **Infrastructure Tests:** 10 tests (4%)

### Tests by Phase
- Phase 1 (Config): 24 tests
- Phase 2 (Database): 46 tests (28 model + 18 database)
- Phase 3 (Schema): 23 tests
- Phase 4 (Prompts): 24 tests
- Phase 5 (Dedupe): 22 tests
- Phase 6 (Vector Store): 15 tests
- Phase 7 (API Client): 20 tests
- Phase 8 (Token Tracking): 18 tests
- Phase 9 (Processor): 10 tests
- Phase 10 (Token Counter Module): 78 tests

---

## Key Metrics

- **Production Code:** 7,192 LOC (src/ + token_counter/ + examples/)
- **Test Code:** 4,904 LOC
- **Test-to-Code Ratio:** 0.68 (68% as much test code as production code)
- **Files per Directory:**
  - `src/`: 20 files
  - `token_counter/`: 11 files
  - `tests/`: 40+ files
  - `docs/`: 33+ files
- **Average File Size:** 118 LOC per file

---

## Dependencies

### Core Runtime Dependencies (9)
1. `requests` — HTTP client
2. `openai` — OpenAI SDK
3. `pydantic` — Configuration validation
4. `pydantic-settings` — Environment-based config
5. `sqlalchemy` — ORM
6. `alembic` — Database migrations
7. `tenacity` — Retry logic
8. `tiktoken` — Token counting
9. `PyPDF2` — PDF parsing

### Development Dependencies (8+)
1. `pytest` — Test framework
2. `pytest-cov` — Coverage reporting
3. `black` — Code formatting
4. `mypy` — Type checking
5. `flake8` — Linting
6. `hypothesis` — Property-based testing
7. `pytest-xdist` — Parallel test execution
8. `pytest-mock` — Mocking framework

---

## Git Statistics

**Current Branch:** `integration/week1-foundation`
**Last Commit:** `54dd9d6 Add ContentItem class for proper API response structure`
**Total Commits:** 15
**Active Branches:** 4 (main, 3 workstream branches)

### Recent Commits (Last 10)
1. `54dd9d6` — Add ContentItem class for proper API response structure
2. `b6c0538` — Add model_dump() method to MockResponse for Pydantic compatibility
3. `dd4b7a2` — Fix mock_openai_client fixture
4. `7501a6b` — Fix test fixture compatibility and model policy validation
5. `ed45b64` — Integrate Workstream 1: Database + Pipeline Foundation
6. `fb97a2e` — feat: Complete Workstream 1
7. `9dbc3f0` — Integrate Workstream 4: Test Infrastructure
8. `049cb7f` — feat: Complete Workstream 4
9. `650352d` — Stashing main branch changes before Week 1 integration
10. `21c0820` — index on main

---

## Repository Size Analysis

**Total Size:** 63M

### Size Breakdown (estimated)
- `.git/`: ~10M (git history)
- `venv/`: ~45M (Python virtual environment)
- `src/` + `token_counter/` + `tests/`: ~3M (source code)
- `docs/`: ~2M (documentation)
- `examples/`: ~500K (example code)
- Other files: ~2.5M

---

## File System Structure Summary

```
autoD/                           # Root directory (63M)
├── src/ (20 files)              # Application code (4,290 LOC)
│   ├── stages/ (6 files)        # Processing stages
│   └── *.py                     # Core modules
├── token_counter/ (11 files)    # Token counting module (2,632 LOC)
├── tests/ (40+ files)           # Test suite (4,904 LOC)
│   ├── unit/                    # Unit tests
│   ├── integration/             # Integration tests
│   └── mocks/                   # Mock implementations
├── docs/ (33+ files)            # Documentation
│   ├── orientation/             # Orientation documents
│   ├── token_counting/          # Token counting docs
│   ├── adr/                     # Architecture decisions
│   └── sessions/                # Session history
├── config/ (2 files)            # Configuration
├── examples/ (1 file)           # Integration examples (270 LOC)
├── migrations/                  # Alembic migrations
├── inbox/                       # PDF input (git-ignored)
├── processed/                   # Processed PDFs (git-ignored)
├── failed/                      # Failed PDFs (git-ignored)
├── logs/                        # Application logs (git-ignored)
└── venv/                        # Python virtual environment (git-ignored)
```

---

**Last Updated:** 2025-10-16
**Status:** Production Ready ✅
**Next Review:** After production deployment

