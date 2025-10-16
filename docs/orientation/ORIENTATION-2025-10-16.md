# Repository Orientation — autoD

**Generated:** 2025-10-16
**Repository:** /Users/krisstudio/Developer/Projects/autoD
**Size:** 384K | **Files:** 11 | **Git Status:** Not a git repository

---

## Overview

**autoD** (Automated Document Processing) is a minimal Python sandbox for prototyping PDF metadata extraction using OpenAI's Responses API. This is **not** a production system—it's a focused testbed for iterating on prompts and API patterns before integrating into the larger "Paper Autopilot" pipeline.

**Purpose:**
- Rapid experimentation with OpenAI's `/v1/responses` endpoint
- PDF-to-JSON metadata extraction (document classification, field extraction, OCR)
- Validation of Responses API patterns with file inputs and structured outputs
- Proof-of-concept for future Paper Autopilot features

**Key Constraint:** This project uses the **Responses API** (`/v1/responses`), **NOT** the Chat Completions API. All API integrations must follow Responses API conventions.

---

## Tech Stack

### Language & Runtime
- **Python 3.9+** (PEP 8 compliant, type-hinted)
- **Dependencies:** `requests` (only runtime dependency)
- **Formatting:** `black` (code formatter)
- **Testing:** `pytest` (recommended, not yet implemented)

### External APIs
- **OpenAI Responses API** (`https://api.openai.com/v1/responses`)
  - Model: `gpt-5` (vision-capable, supports PDF inputs)
  - Timeout: 300 seconds (5 minutes)
  - Response format: Enforced JSON via `text.format.type: json_object`

### File Handling
- **Input Format:** PDFs (Base64-encoded with data URI wrapper)
- **Encoding:** `data:application/pdf;base64,<base64-data>`

---

## Repository Structure

```
/Users/krisstudio/Developer/Projects/autoD/
├── README.md                              # Project overview & quick start
├── CLAUDE.md                              # Claude Code guidance (created)
├── AGENTS.md                              # Repository conventions & guidelines
├── process_inbox.py                       # Main entrypoint (139 lines)
├── inbox/                                 # PDF input directory (git-ignored)
│   └── .gitkeep
└── docs/                                  # Research notes & API documentation
    ├── initial_implementation_plan.md     # Full Paper Autopilot architecture (707 lines)
    ├── responses_api_endpoint.md          # Comprehensive Responses API guide (200KB)
    ├── file_inputs_for_the_responses_api.md
    ├── gpt_5_prompt_engineering.md        # Prompt optimization strategies
    ├── how_to_count_tokens_w_tik_tok_token.md
    ├── scansnap-ix1600.md                 # Hardware integration docs
    ├── scansnap-ix1600-setup.md
    └── orientation/                       # (newly created)
        └── ORIENTATION-2025-10-16.md
```

**Directory Purposes:**
- **`inbox/`**: Drop PDFs here for processing (git-ignored, empty by default)
- **`docs/`**: API research, implementation plans, hardware setup guides
- **Root**: Minimal single-file script + documentation

---

## Entrypoints & Runbook

### Environment Setup
```bash
# 1. Create virtual environment
python3 -m venv .venv && source .venv/bin/activate

# 2. Install dependencies
python -m pip install -U requests

# 3. Set API key (required)
export OPENAI_API_KEY=sk-...
```

### Running the Tool
```bash
# Process all PDFs in inbox/
python process_inbox.py

# Expected behavior:
# - Discovers all .pdf files in inbox/
# - Base64-encodes each PDF
# - Sends to OpenAI Responses API with metadata extraction prompt
# - Prints JSON response for each document
# - Continues on HTTP errors (logs and moves to next file)
```

### Development Commands
```bash
# Format code (required before commits)
black process_inbox.py

# Run tests (when implemented)
pytest

# Verify Python version
python --version  # Should be 3.9+
```

---

## Code Architecture

### Functional Pipeline (`process_inbox.py`)

The script follows a **stateless functional decomposition** pattern with 6 core functions:

1. **`iter_pdfs(inbox: Path) → Iterable[Path]`**
   Discovers all `.pdf` files in the inbox directory (sorted).

2. **`encode_pdf(pdf_path: Path) → str`**
   Base64-encodes the PDF and wraps with data URI (`data:application/pdf;base64,...`).

3. **`call_responses_api(api_key: str, pdf_path: Path, encoded_pdf: str) → dict`**
   Constructs and sends the Responses API request:
   ```python
   POST https://api.openai.com/v1/responses
   {
       "model": "gpt-5",
       "input": [{
           "role": "user",
           "content": [
               {"type": "input_text", "text": "<PROMPT>"},
               {"type": "input_file", "filename": "...", "file_data": "data:application/pdf;base64,..."}
           ]
       }],
       "text": {"format": {"type": "json_object"}}
   }
   ```

4. **`extract_output_text(response_json: dict) → str`**
   Parses the model's response to extract the metadata JSON string.

5. **`main() → None`**
   Orchestrates the pipeline:
   - Load API key from environment
   - Iterate PDFs in `inbox/`
   - For each: encode → call API → extract → print
   - Error handling: per-file try/catch (HTTP errors logged, processing continues)

### Request Structure Details

**Endpoint:** `https://api.openai.com/v1/responses`
**Model:** `gpt-5` (hardcoded constant at line 33)
**Timeout:** 300 seconds (line 90)
**Response Format:** Enforced JSON object (lines 83-87)

**Current Metadata Extraction Schema:**
- `file_name` (string)
- `doc_type` (enum: UtilityBill, BankStatement, Invoice, Receipt, Unknown)
- `issuer` (organization/person)
- `primary_date` (ISO YYYY-MM-DD or null)
- `total_amount` (numeric or null)
- `summary` (≤40 words)

---

## APIs & Routes

**No traditional REST/GraphQL API endpoints.** This is a command-line utility that acts as a **client** to the OpenAI Responses API.

**External API Integration:**
- **OpenAI Responses API** (POST `/v1/responses`)
  - Authentication: Bearer token via `OPENAI_API_KEY` environment variable
  - Content-Type: `application/json`
  - Request payload: See architecture section above
  - Response: JSON with `output` array containing model's structured response

---

## Data Models & Storage

**No database or persistent storage.** This is a stateless processing script.

**Data Flow:**
1. **Input:** PDF files in `inbox/` directory (filesystem)
2. **Processing:** In-memory (Base64 encoding, HTTP requests)
3. **Output:** JSON printed to stdout (ephemeral)

**Future Evolution (from `docs/initial_implementation_plan.md`):**
The full Paper Autopilot system will include:
- **SQLAlchemy** ORM with PostgreSQL/SQLite
- **Vector Stores** for cross-document context and deduplication
- **SHA-256** file hashing for dedupe
- Comprehensive schema with 40+ fields (action items, deadlines, urgency, OCR excerpts)

---

## Configuration & Secrets

### Required Environment Variables
- **`OPENAI_API_KEY`** (required) — OpenAI API key for Responses API access
  - Format: `sk-...`
  - Set via: `export OPENAI_API_KEY=sk-...` or git-ignored `.env` file

### Hardcoded Configuration
All configuration is currently **hardcoded in `process_inbox.py`**:
- `API_URL = "https://api.openai.com/v1/responses"` (line 32)
- `MODEL = "gpt-5"` (line 33)
- `PROMPT_TEMPLATE` (lines 35-44) — Metadata extraction instructions

### Security Notes
- **Never commit** PDFs from `inbox/` (directory is git-ignored)
- **Never commit** raw API responses containing sensitive data
- **Sanitize and redact** response excerpts before sharing
- **Rotate API keys** immediately if exposed in logs

---

## Tests & Quality

### Current State
**No automated tests implemented.** Testing is manual via:
1. Place test PDF in `inbox/`
2. Run `python process_inbox.py`
3. Verify JSON output

### Recommended Testing Strategy (from AGENTS.md)
- **Framework:** `pytest`
- **Structure:** `tests/test_<scenario>.py` with functions named `test_<behavior>`
- **Mocking:** Use `responses` or `pytest-httpx` for network I/O
- **Coverage Areas:**
  - Empty inbox handling
  - Malformed PDF handling
  - HTTP error scenarios (4xx, 5xx)
  - Response parsing edge cases
  - Missing environment variables

### Code Quality Tools
- **Formatter:** `black process_inbox.py` (required before commits)
- **Style Guide:** PEP 8 compliance
- **Type Checking:** Full type hints present (no mypy config yet)

---

## Repository Map (Top Directories by Purpose)

| Path | Purpose | File Count | Key Files |
|------|---------|------------|-----------|
| `/` | Root | 4 | `process_inbox.py`, `README.md`, `CLAUDE.md`, `AGENTS.md` |
| `inbox/` | PDF intake folder (git-ignored) | 1 | `.gitkeep` (directory marker only) |
| `docs/` | Research & API documentation | 7 | `initial_implementation_plan.md` (707 lines), `responses_api_endpoint.md` (200KB) |
| `docs/orientation/` | Orientation reports | 1 | `ORIENTATION-2025-10-16.md` (this file) |

**File Inventory (11 total):**
```
./AGENTS.md                                      # Repository conventions (2.6 KB)
./CLAUDE.md                                      # Claude Code guidance (6.2 KB)
./README.md                                      # Project overview (1.6 KB)
./process_inbox.py                               # Main script (4.4 KB, 139 lines)
./inbox/.gitkeep                                 # Directory marker
./docs/file_inputs_for_the_responses_api.md      # API docs
./docs/gpt_5_prompt_engineering.md               # Prompt engineering guide
./docs/how_to_count_tokens_w_tik_tok_token.md    # Token counting guide
./docs/initial_implementation_plan.md            # Full architecture (707 lines)
./docs/responses_api_endpoint.md                 # Comprehensive API guide (200 KB)
./docs/scansnap-ix1600-setup.md                  # Hardware setup
./docs/scansnap-ix1600.md                        # Hardware integration
```

---

## Unknowns & Risks

### Architectural Unknowns
1. **Prompt Stability:** Current prompt may need tuning based on real-world PDFs
2. **Token/Cost Tracking:** No usage monitoring implemented (see `docs/initial_implementation_plan.md` for full solution)
3. **Retry Logic:** No retry mechanism for transient API errors (fails fast)
4. **Rate Limiting:** No rate limiting or backoff strategy

### Integration Risks
1. **OpenAI API Changes:** Responses API is newer; schema/behavior may evolve
2. **Model Availability:** `gpt-5` model availability and pricing not confirmed
3. **PDF Size Limits:** No testing of token limits with large/multi-page PDFs
4. **Base64 Overhead:** Large PDFs may hit request size limits

### Data Risks
1. **No Deduplication:** Same PDF processed multiple times if re-added to inbox
2. **No Audit Trail:** Processing history is ephemeral (stdout only)
3. **PII Exposure:** Raw responses may contain sensitive data; no sanitization

### Operational Risks
1. **No Tests:** Manual testing only; regression risk on changes
2. **Single File:** All logic in one 139-line script; difficult to unit test
3. **No Logging:** Relies on print statements; no structured logging
4. **Hard Dependencies:** Global `requests` import fails if not installed

---

## Design Decisions & Context

### Why Responses API (Not Chat Completions)?
From `docs/initial_implementation_plan.md`:
- Responses API supports **PDF file inputs** natively (`input_file` type)
- Supports **structured outputs** with strict JSON schema enforcement
- Enables **prompt caching** for repeated system/developer messages
- Allows **multi-turn conversations** via `previous_response_id`
- **Vector Store integration** for cross-document context

### Why Minimal Dependencies?
From `CLAUDE.md` and `process_inbox.py` docstring:
> "This utility is intentionally lightweight and standalone; it is not wired into the primary Paper Autopilot pipeline."

This is a **sandbox for rapid iteration**, not a production system. Minimal deps = faster setup and fewer breaking changes.

### Why No Database?
Current scope is **prompt validation only**. Full persistence layer documented in `docs/initial_implementation_plan.md` (SQLAlchemy + PostgreSQL + Vector Stores).

---

## Next Steps Before Coding

### 1. **Validate API Access**
- [ ] Confirm `OPENAI_API_KEY` is set and valid
- [ ] Verify `gpt-5` model access (check OpenAI dashboard for model availability)
- [ ] Test with a sample PDF to confirm end-to-end flow

### 2. **Review Implementation Plan**
- [ ] Read `docs/initial_implementation_plan.md` (707 lines) to understand full Paper Autopilot architecture
- [ ] Understand the gap between current sandbox and production system
- [ ] Identify which features are being prototyped vs. deferred

### 3. **Establish Baseline Tests**
- [ ] Create `tests/` directory structure
- [ ] Implement basic smoke test (mock API call, verify JSON parsing)
- [ ] Add test for empty inbox handling
- [ ] Verify black formatting passes

---

## Quick Reference

**Run the tool:**
```bash
cd /Users/krisstudio/Developer/Projects/autoD
source .venv/bin/activate
export OPENAI_API_KEY=sk-...
python process_inbox.py
```

**Modify extraction prompt:**
Edit `PROMPT_TEMPLATE` in `process_inbox.py` (lines 35-44)

**Change model:**
Edit `MODEL` constant in `process_inbox.py` (line 33)

**Add dependency:**
`python -m pip install <package>` (document in AGENTS.md or README.md)

**Format code:**
`black process_inbox.py`

**Key documentation:**
- `README.md` — Project overview
- `CLAUDE.md` — Claude Code operating instructions
- `AGENTS.md` — Repository conventions
- `docs/initial_implementation_plan.md` — Full Paper Autopilot architecture
- `docs/responses_api_endpoint.md` — Comprehensive Responses API guide

---

**End of Orientation Report**
*Generated by Claude Code `/orient` command on 2025-10-16*
