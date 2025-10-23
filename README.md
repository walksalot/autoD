# Paper Autopilot - Automatic Document Processing

[![CI](https://github.com/krisstudio/autoD/actions/workflows/ci.yml/badge.svg)](https://github.com/krisstudio/autoD/actions/workflows/ci.yml)
[![Pre-commit](https://github.com/krisstudio/autoD/actions/workflows/pre-commit.yml/badge.svg)](https://github.com/krisstudio/autoD/actions/workflows/pre-commit.yml)
[![codecov](https://codecov.io/gh/krisstudio/autoD/branch/main/graph/badge.svg)](https://codecov.io/gh/krisstudio/autoD)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![MyPy: strict](https://img.shields.io/badge/mypy-strict-blue.svg)](https://mypy.readthedocs.io/en/stable/)

**Automatic PDF processing from your ScanSnap scanner using OpenAI Responses API**

Paper Autopilot continuously monitors your scanner's inbox folder and automatically processes PDFs as they arrive. No manual intervention needed - just scan your documents and let the autopilot handle the rest.

## What's New (Wave 2 - October 2025)

**Type Safety:**
- 100% type annotation coverage with MyPy strict mode
- Zero `Any` type leakage from external libraries
- Pre-commit hooks enforce type safety

**Performance:**
- Production-ready embedding cache with <0.1ms latency
- 70%+ cache hit rate with temporal locality
- >1M lookups/sec throughput
- SHA-256 cache keys with LRU eviction

**Quality:**
- 41 new cache tests (unit + integration + performance)
- Property-based testing with Hypothesis framework
- 3 new ADRs documenting technical decisions

See [CHANGELOG.md](CHANGELOG.md) for full details.

## What It Does

1. **Watches** your scanner's inbox folder (`/Users/krisstudio/Paper/InboxA`)
2. **Detects** new PDFs instantly using filesystem events
3. **Validates** PDF integrity and waits for scanner to finish writing
4. **Processes** documents using OpenAI Responses API for metadata extraction
5. **Stores** results in SQLite database with full audit trail
6. **Uploads** to OpenAI vector store for semantic search
7. **Moves** processed PDFs to organized folders

## Quick Start

### 1. Install Dependencies

```bash
# Create and activate virtual environment
python3 -m venv .venv && source .venv/bin/activate

# Install required packages
pip install -r requirements.txt
```

### 2. Configure API Key

The daemon will automatically load your OpenAI API key from `~/.OPENAI_API_KEY`:

```bash
# Save your API key to the file
echo "sk-your-actual-key-here" > ~/.OPENAI_API_KEY
chmod 600 ~/.OPENAI_API_KEY
```

Or set it as an environment variable:

```bash
export OPENAI_API_KEY=sk-your-actual-key-here
```

### 3. Run the Daemon

```bash
# Start the automatic processing daemon
python3 run_daemon.py
```

The daemon will:
- Create necessary directories if they don't exist
- Start watching `/Users/krisstudio/Paper/InboxA` for new PDFs
- Process documents automatically as they arrive
- Log all activities to `logs/paper_autopilot.log`

### 4. Configure Your Scanner

Set your ScanSnap scanner to save PDFs to:
```
/Users/krisstudio/Paper/InboxA
```

See `docs/scansnap-ix1600-setup.md` for detailed scanner configuration.

## Automatic Startup (macOS)

To have Paper Autopilot start automatically on login:

```bash
# Copy LaunchAgent plist
cp com.paperautopilot.daemon.plist ~/Library/LaunchAgents/

# Load and start the daemon
launchctl load ~/Library/LaunchAgents/com.paperautopilot.daemon.plist

# Verify it's running
launchctl list | grep paperautopilot
```

The daemon will now start automatically every time you log in to your Mac.

## Repository Structure

```
.
├── run_daemon.py          # Entry point for automatic daemon
├── src/
│   ├── daemon.py          # File watching and automatic processing
│   ├── processor.py       # Document processing pipeline
│   ├── config.py          # Configuration management (Pydantic V2)
│   ├── cache.py           # LRU embedding cache (NEW)
│   ├── database.py        # SQLite database operations
│   ├── api_client.py      # OpenAI Responses API client
│   └── vector_store.py    # Vector store management
├── docs/
│   ├── DAEMON_MODE.md     # Detailed daemon setup guide
│   ├── RUNBOOK.md         # Production operations guide
│   ├── DEVELOPMENT_MODEL.md  # Parallel execution guide (NEW)
│   └── scansnap-ix1600-setup.md  # Scanner configuration
└── com.paperautopilot.daemon.plist  # macOS LaunchAgent config
```

## Configuration

All settings can be configured via environment variables:

```bash
# Required
OPENAI_API_KEY=sk-...              # OpenAI API key

# Paths (defaults shown)
PAPER_AUTOPILOT_INBOX_PATH=/Users/krisstudio/Paper/InboxA
PAPER_AUTOPILOT_DB_URL=sqlite:///paper_autopilot.db

# Processing
OPENAI_MODEL=gpt-5-mini           # gpt-5-mini, gpt-5-nano, gpt-5, gpt-5-pro, gpt-4.1
API_TIMEOUT_SECONDS=300           # API call timeout (30-600s)
MAX_RETRIES=5                     # Retry attempts (1-10)

# Logging
LOG_LEVEL=INFO                    # DEBUG, INFO, WARNING, ERROR
LOG_FORMAT=json                   # json or text
```

See `docs/DAEMON_MODE.md` for complete configuration reference.

## Monitoring

View daemon logs in real-time:

```bash
# Application logs (structured JSON)
tail -f logs/paper_autopilot.log | jq .

# Daemon stdout
tail -f logs/daemon_stdout.log

# Daemon errors
tail -f logs/daemon_stderr.log
```

Check daemon status:

```bash
# macOS LaunchAgent
launchctl list | grep paperautopilot

# View recent activity
grep "Processing complete" logs/paper_autopilot.log | tail -10
```

## Folder Organization

```
/Users/krisstudio/Paper/
├── InboxA/          # Scanner drops PDFs here
├── Processed/       # Successfully processed PDFs
└── Failed/          # PDFs that failed processing
```

The daemon automatically moves PDFs to the appropriate folder after processing.

## Supported Models

Paper Autopilot uses only OpenAI Frontier models per project requirements:

- `gpt-5-mini` (default) - Fast, cost-efficient
- `gpt-5-nano` - Fastest, most cost-efficient
- `gpt-5` - Best for coding and agentic tasks
- `gpt-5-pro` - Smarter and more precise
- `gpt-4.1` - Smartest non-reasoning model

**Important**: Never use `gpt-4o` or chat completions models. Paper Autopilot uses only the Responses API endpoint (`/v1/responses`), never chat completions.

## Documentation

- **[Daemon Mode Guide](docs/DAEMON_MODE.md)** - Complete daemon setup and troubleshooting
- **[Production Runbook](docs/RUNBOOK.md)** - Operations guide for production deployments
- **[Development Model](docs/DEVELOPMENT_MODEL.md)** - Parallel execution with git worktrees (NEW)
- **[Scanner Setup](docs/scansnap-ix1600-setup.md)** - ScanSnap iX1600 configuration
- **[Code Architecture](docs/CODE_ARCHITECTURE.md)** - System architecture and design
- **[Processor Guide](docs/PROCESSOR_GUIDE.md)** - Document processing pipeline details

## Contributing

Review `AGENTS.md` for project conventions, testing expectations, and security practices. Key points:

- Follow PEP 8, run `black` before commits
- Use `pytest` for automated testing
- Never commit sample PDFs or raw API responses
- Keep model selections aligned with Frontier models only
- Run policy checks before PRs:
  ```bash
  python scripts/check_model_policy.py --diff
  pytest tests/test_model_policy.py
  ```

## Architecture

Paper Autopilot implements a production-grade document processing pipeline:

1. **File Watching**: Real-time detection with filesystem events (watchdog library)
2. **File Stabilization**: Handles scanner's phased writes (waits for OCR completion)
3. **Deduplication**: SHA-256 hash-based duplicate detection
4. **Processing Pipeline**: Responses API → Schema Validation → Database Storage
5. **Vector Search**: Automatic upload to OpenAI vector store with LRU embedding cache
6. **Audit Trail**: Complete processing history with costs and timing
7. **Error Handling**: Automatic retries with exponential backoff
8. **Type Safety**: MyPy strict mode with 100% annotation coverage
9. **Performance**: <0.1ms cache latency, 70%+ hit rate, >1M ops/sec throughput

## License

See LICENSE file for details.

---

**Maintained By**: Platform Engineering Team
**Version**: 1.0.0
