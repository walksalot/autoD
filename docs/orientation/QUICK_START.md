# Quick Start Guide — autoD Production System

**Target Audience:** Developers onboarding to the autoD project
**Prerequisites:** Python 3.11+, git, OpenAI API key
**Repository:** /Users/krisstudio/Developer/Projects/autoD

---

## 5-Minute Setup

### 1. Clone and Setup Environment

```bash
cd /Users/krisstudio/Developer/Projects/autoD

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt  # For development
```

### 2. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your API keys
# REQUIRED:
export OPENAI_API_KEY="sk-..."

# OPTIONAL (defaults shown):
export OPENAI_MODEL="gpt-5-mini"
export DATABASE_URL="sqlite:///paper_autopilot.db"
export VECTOR_STORE_NAME="paper-autopilot-docs"
```

### 3. Initialize Database

```bash
# Create database tables
alembic upgrade head

# Verify setup
python -c "from src.config import get_config; print(get_config())"
# Should print: Config(api_key=sk-***..., model=gpt-5-mini, ...)
```

### 4. Run Your First PDF

```bash
# Place a PDF in inbox/
cp sample.pdf inbox/

# Process it
python process_inbox.py

# Check results
sqlite3 paper_autopilot.db "SELECT id, original_filename, status FROM documents;"
```

**Expected Output:**
```
1|sample.pdf|completed
```

---

## Common Development Tasks

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html
open htmlcov/index.html  # View coverage report

# Run specific test file
pytest tests/test_pipeline.py -v

# Run only unit tests
pytest tests/unit/ -v

# Run only integration tests
pytest tests/integration/ -v

# Run tests in parallel
pytest -n auto
```

### Code Quality Checks

```bash
# Format code with black
black src/ tests/

# Check formatting (without modifying)
black src/ tests/ --check

# Type checking with mypy
mypy src/

# Linting with flake8
flake8 src/ tests/
```

### Working with Database

```bash
# Create migration after model changes
alembic revision --autogenerate -m "Add urgency_score field"

# Apply migrations
alembic upgrade head

# Rollback one version
alembic downgrade -1

# View migration history
alembic history

# Check current version
alembic current
```

### Debugging API Calls

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG

# Run processor with verbose output
python process_inbox.py --verbose

# View structured logs
cat logs/paper_autopilot.log | jq '.'

# Filter logs by status
cat logs/paper_autopilot.log | jq 'select(.status == "failed")'

# Calculate total cost
cat logs/paper_autopilot.log | jq 'select(.cost_usd) | .cost_usd' | awk '{sum+=$1} END {print sum}'
```

### Token Counting

```bash
# Count tokens for a file
python -c "
from token_counter import TokenCounter
counter = TokenCounter()
result = counter.count_tokens('gpt-5-mini', [
    {'role': 'user', 'content': 'Extract metadata'}
], estimate_cost=True)
print(f'Tokens: {result.total_tokens}, Cost: ${result.cost.total_usd:.6f}')
"

# Validate against actual API usage
python examples/token_counting_integration.py
```

---

## Project Structure Overview

```
autoD/
├── src/                    # Application code
│   ├── config.py          # Configuration (Pydantic V2)
│   ├── models.py          # Database models (SQLAlchemy)
│   ├── pipeline.py        # Pipeline pattern infrastructure
│   ├── processor.py       # Main processing logic (9 steps)
│   ├── api_client.py      # OpenAI Responses API client
│   ├── vector_store.py    # Vector store operations
│   ├── dedupe.py          # SHA-256 deduplication
│   ├── schema.py          # JSON schema validation
│   ├── prompts.py         # Prompt templates
│   ├── token_counter.py   # Token/cost tracking
│   ├── logging_config.py  # Structured logging
│   └── stages/            # Pipeline stages
│       ├── sha256_stage.py
│       ├── dedupe_stage.py
│       ├── upload_stage.py
│       ├── api_stage.py
│       └── persist_stage.py
│
├── token_counter/         # Standalone token counting module
│   ├── counter.py         # High-level facade
│   ├── responses_api.py   # Responses API calculator
│   ├── chat_api.py        # Chat API calculator
│   ├── file_estimators.py # PDF token estimation
│   ├── cost.py            # Cost calculation
│   └── validator.py       # Validation framework
│
├── tests/                 # Test suite (244 tests)
│   ├── conftest.py        # Pytest fixtures
│   ├── unit/              # Unit tests
│   ├── integration/       # Integration tests
│   └── mocks/             # Mock implementations
│
├── docs/                  # Documentation
│   ├── orientation/       # Orientation documents
│   │   ├── ORIENTATION-2025-10-16.md
│   │   ├── FILE_INVENTORY.md
│   │   └── QUICK_START.md (this file)
│   ├── CODE_ARCHITECTURE.md
│   ├── IMPLEMENTATION_ROADMAP.md
│   └── RUNBOOK.md
│
└── process_inbox.py       # CLI entry point
```

---

## 9-Step Processing Pipeline

The `src/processor.py` orchestrates these stages:

1. **ComputeSHA256Stage** — Hash file for deduplication
2. **DedupeCheckStage** — Query database for duplicates
3. **UploadToFilesAPIStage** — Upload PDF to OpenAI Files API
4. **CallResponsesAPIStage** — Extract metadata via Responses API
5. **ParseResponseStage** — Parse and validate JSON response
6. **CalculateCostStage** — Track token usage and cost
7. **PersistToDBStage** — Save to database
8. **UploadToVectorStoreStage** — Add to vector store
9. **CleanupStage** — Move file to processed/

**Pipeline Pattern:**
```python
from src.pipeline import Pipeline, ProcessingContext
from src.stages.sha256_stage import ComputeSHA256Stage
from pathlib import Path

# Construct pipeline
pipeline = Pipeline([
    ComputeSHA256Stage(),
    # ... more stages
])

# Process a PDF
context = ProcessingContext(pdf_path=Path("inbox/sample.pdf"))
result = pipeline.process(context)

if result.error:
    print(f"Failed: {result.error}")
else:
    print(f"Success: doc_id={result.document_id}")
```

---

## Key Configuration Settings

### Required Environment Variables

| Variable | Example | Purpose |
|----------|---------|---------|
| `OPENAI_API_KEY` | `sk-...` | OpenAI API authentication |

### Optional Environment Variables (with defaults)

| Variable | Default | Purpose |
|----------|---------|---------|
| `OPENAI_MODEL` | `gpt-5-mini` | Model to use (gpt-5, gpt-5-mini, gpt-5-nano, gpt-5-pro, gpt-4.1) |
| `DATABASE_URL` | `sqlite:///paper_autopilot.db` | Database connection URL |
| `VECTOR_STORE_NAME` | `paper-autopilot-docs` | Name for vector store |
| `API_TIMEOUT_SECONDS` | `300` | Timeout for API calls (5 minutes) |
| `MAX_RETRIES` | `5` | Maximum retry attempts |
| `RATE_LIMIT_RPM` | `60` | Rate limit in requests per minute |
| `BATCH_SIZE` | `10` | Number of PDFs to process in parallel |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |

### Model Policy Enforcement

**CRITICAL:** Only these models are allowed:
- `gpt-5` — Best for coding and agentic tasks
- `gpt-5-mini` — Faster, cost-efficient (recommended)
- `gpt-5-nano` — Fastest, most cost-efficient
- `gpt-5-pro` — Smarter and more precise
- `gpt-4.1` — Smartest non-reasoning model

**NEVER use:** `gpt-4o`, `gpt-4o-mini`, or any chat completions models

The config validation will raise an error if an invalid model is specified.

---

## Testing Strategy

### Test Categories

1. **Unit Tests** (166 tests) — Test individual functions/classes
2. **Integration Tests** (68 tests) — Test component interactions
3. **Infrastructure Tests** (10 tests) — Test setup and configuration

### Coverage Targets

- **Overall:** 42% (current)
- **Critical Modules:** 80%+ (pipeline, processor, api_client)
- **Config/Models:** 90%+ (config, models, schema)

### Running Specific Test Suites

```bash
# Config validation tests (24 tests)
pytest tests/unit/test_config.py -v

# Pipeline tests (all stages)
pytest tests/test_pipeline.py tests/test_dedupe_stage.py -v

# Token counting tests (78 tests)
pytest tests/unit/test_cost.py tests/unit/test_file_estimators.py \
       tests/integration/test_counter.py tests/integration/test_validator.py -v

# API client tests (with retry logic)
pytest tests/integration/test_responses_api.py -v

# End-to-end processor tests (10 tests)
pytest tests/integration/test_processor.py -v
```

---

## Debugging Common Issues

### Issue: "OPENAI_API_KEY not set"

```bash
# Solution: Export API key
export OPENAI_API_KEY="sk-..."

# Or add to .env file
echo 'OPENAI_API_KEY=sk-...' >> .env
```

### Issue: "Model 'gpt-4o' not allowed"

```python
# Error: ValidationError: Model 'gpt-4o' not allowed
# Solution: Use approved Frontier model
export OPENAI_MODEL="gpt-5-mini"
```

### Issue: Database migration conflicts

```bash
# Solution: Rollback and reapply
alembic downgrade -1
alembic upgrade head

# Or create new migration
alembic revision --autogenerate -m "Fix migration conflict"
```

### Issue: Tests failing with import errors

```bash
# Solution: Ensure PYTHONPATH includes src/
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Or use pytest with sys.path fix
python -m pytest tests/
```

### Issue: Vector store upload failures

```bash
# Check vector store ID cache
cat .vector_store_id

# Delete cache to recreate
rm .vector_store_id

# Run processor again
python process_inbox.py
```

---

## Git Workflow

### Branch Strategy

- **`main`** — Production-ready code
- **`integration/week1-foundation`** — Current development branch
- **`workstream/*`** — Feature branches (multi-agent parallel development)

### Common Git Commands

```bash
# Check current branch
git branch

# View git worktrees (if using parallel development)
git worktree list

# Create feature branch
git checkout -b feature/my-feature

# Commit changes
git add .
git commit -m "feat: Add my feature"

# Push to remote
git push origin feature/my-feature

# Merge to main (after PR approval)
git checkout main
git merge feature/my-feature --no-ff
```

---

## Performance Benchmarks

### Expected Performance

| Metric | Target | Current |
|--------|--------|---------|
| Processing Time (per PDF) | <20s | ~9.38s |
| Deduplication Check | <100ms | <50ms |
| API Call (with retry) | <15s | ~8.5s |
| Token Counting | <10ms | ~5ms |
| Database Write | <50ms | ~20ms |

### Optimization Tips

1. **Enable Prompt Caching** — Keep system/developer prompts identical (85% cost reduction)
2. **Use gpt-5-mini** — 10x cheaper than gpt-5, similar quality for extraction
3. **Batch Processing** — Process multiple PDFs in parallel (set `BATCH_SIZE=10`)
4. **Vector Store Dedup** — Pre-check vector store attributes before API call

---

## Cost Monitoring

### Tracking Costs

```bash
# View logs with cost data
cat logs/paper_autopilot.log | jq 'select(.cost_usd)'

# Calculate total cost
cat logs/paper_autopilot.log | jq -s 'map(select(.cost_usd)) | map(.cost_usd) | add'

# Cost per PDF
sqlite3 paper_autopilot.db \
  "SELECT AVG(json_extract(metadata_json, '$.estimated_cost_usd')) FROM documents WHERE status='completed';"
```

### Expected Costs (gpt-5-mini)

- **Input:** $0.15 per 1M tokens
- **Cached Input:** $0.075 per 1M tokens (50% discount)
- **Output:** $0.60 per 1M tokens

**Typical PDF Processing:**
- Prompt: ~2,200 tokens (85% cached after first run)
- Output: ~500 tokens
- **First PDF:** ~$0.0005 (uncached)
- **Subsequent PDFs:** ~$0.0001 (cached)

---

## Next Steps

After completing this quick start:

1. **Read Orientation Document** — `/docs/orientation/ORIENTATION-2025-10-16.md` (comprehensive architecture overview)
2. **Review Code Architecture** — `/docs/CODE_ARCHITECTURE.md` (implementation patterns)
3. **Study Test Suite** — `/tests/README.md` (testing patterns and examples)
4. **Explore Token Counting** — `/docs/token_counting/quickstart.md` (cost estimation guide)
5. **Deploy to Production** — `/docs/RUNBOOK.md` (deployment and operations guide)

---

## Helpful Resources

### Documentation

- **Architecture:** `/docs/CODE_ARCHITECTURE.md`
- **API Reference:** `/docs/API_DOCS.md`
- **Troubleshooting:** `/docs/TROUBLESHOOTING.md`
- **Operations:** `/docs/RUNBOOK.md`
- **Contributing:** `/docs/CONTRIBUTING.md`

### External Resources

- **OpenAI Responses API:** https://platform.openai.com/docs/api-reference/responses
- **SQLAlchemy 2.0 Docs:** https://docs.sqlalchemy.org/en/20/
- **Pydantic V2 Docs:** https://docs.pydantic.dev/latest/
- **tiktoken:** https://github.com/openai/tiktoken

---

## Getting Help

- **Issues:** Open a GitHub issue
- **Questions:** Ask in team chat or via email
- **Bugs:** Include logs from `logs/paper_autopilot.log`

---

**Last Updated:** 2025-10-16
**Status:** Production Ready ✅
**Version:** 1.0.0

