# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**autoD** is a lightweight OpenAI Responses API sandbox for PDF metadata extraction. This is NOT integrated into larger pipelines—it's designed for rapid iteration on prompts before productionizing changes elsewhere.

**Critical API Rule**: This project uses the OpenAI **Responses API** (`/v1/responses` endpoint), NOT the Chat Completions API. Always reference `/docs/responses_api_endpoint.md` before making API changes.

**Technology Stack**:
- Python 3.9+ (PEP 8 compliant, formatted with `black`)
- `requests` library (only runtime dependency)
- OpenAI GPT-5 (vision-capable model)
- Base64 encoding for PDF transmission

## Development Commands

### Environment Setup
```bash
# Create and activate virtual environment
python3 -m venv .venv && source .venv/bin/activate

# Install dependencies
python -m pip install -U requests

# Set API key (required)
export OPENAI_API_KEY=sk-...
```

### Running the Tool
```bash
# Process all PDFs in inbox/
python process_inbox.py

# The script will:
# 1. Find all .pdf files in inbox/
# 2. Base64-encode each PDF
# 3. Send to OpenAI Responses API with metadata extraction prompt
# 4. Print JSON response for each document
```

### Code Quality
```bash
# Format code before committing (required)
black process_inbox.py

# Run tests (if implemented)
pytest
```

## Code Architecture

### Functional Pipeline (`process_inbox.py`)
The script follows a functional decomposition pattern with 6 core functions:

1. **`iter_pdfs(inbox: Path)`** → Discovers all PDFs in inbox directory
2. **`encode_pdf(pdf_path: Path)`** → Base64-encodes PDF with data URI wrapper
3. **`call_responses_api(api_key, pdf_path, encoded_pdf)`** → Constructs and sends API request
4. **`extract_output_text(response_json)`** → Parses model response to extract metadata JSON
5. **`main()`** → Orchestrates the pipeline and handles errors per-file

### OpenAI Responses API Request Structure
```python
{
    "model": "gpt-5",
    "input": [
        {
            "role": "user",
            "content": [
                {"type": "input_text", "text": "<PROMPT>"},
                {"type": "input_file", "filename": "...", "file_data": "data:application/pdf;base64,..."}
            ]
        }
    ],
    "text": {"format": {"type": "json_object"}}  # Enforces JSON response
}
```

**Key API Details**:
- Endpoint: `https://api.openai.com/v1/responses`
- Model: `gpt-5` (hardcoded constant)
- Timeout: 300 seconds (5 minutes)
- Response format: Enforced JSON object via `text.format.type`

### Metadata Extraction Schema
The current prompt extracts these fields:
- `file_name` (string)
- `doc_type` (UtilityBill, BankStatement, Invoice, Receipt, Unknown)
- `issuer` (organization/person)
- `primary_date` (ISO YYYY-MM-DD or null)
- `total_amount` (numeric or null)
- `summary` (≤40 words)

## Important Constraints

### Stateless Processing
- Each PDF is processed independently
- No multi-turn conversations or state management
- No use of `previous_response_id` or conversation history

### Security & Data Handling
- **Never commit** sample PDFs or raw API responses with sensitive data
- Delete test PDFs from `inbox/` after validation
- Sanitize and redact response excerpts before sharing
- `inbox/` directory is git-ignored by default
- Rotate API keys immediately if they appear in logs

### API Key Management
```bash
# Export via shell
export OPENAI_API_KEY=sk-...

# Or use git-ignored .env file (load manually in script if needed)
```

## Testing Guidelines

When adding automated tests:
- Use `pytest` framework
- Create tests in `tests/test_<scenario>.py`
- Name test functions `test_<behavior>`
- Mock network I/O with `responses` or `pytest-httpx` for deterministic, offline-friendly tests
- Include edge cases: missing PDFs, malformed metadata, HTTP errors

Example test structure:
```python
# tests/test_pdf_processing.py
def test_encode_pdf_returns_base64_data_uri():
    # Test implementation
    pass

def test_extract_output_text_handles_missing_fields():
    # Test implementation
    pass
```

## Documentation Reference

Key docs in `/docs/`:
- **`responses_api_endpoint.md`** (200KB) – Comprehensive Responses API guide vs Chat Completions
- **`file_inputs_for_the_responses_api.md`** – PDF handling specifics (Base64, file URLs, token counting)
- **`gpt_5_prompt_engineering.md`** – Prompt optimization strategies for GPT-5
- **`scansnap-ix1600*.md`** – Hardware integration docs for document scanning

## Extension Points

### Modifying Extraction Behavior
1. Edit `PROMPT_TEMPLATE` constant in `process_inbox.py` for different schemas
2. Adjust `extract_output_text()` if response structure changes
3. Add new functions for custom transformations or validations

### Future Evolution Paths
- Add retry logic for transient errors (currently fails fast)
- Implement streaming response handling
- Support multi-turn conversations via `previous_response_id`
- Add support for other file types (images, URLs)
- Integrate into larger Paper Autopilot pipeline

## Coding Standards

- **Python version**: 3.9+
- **Style**: PEP 8 compliant, 4-space indentation
- **Formatting**: Run `black process_inbox.py` before committing
- **Function naming**: Descriptive `lower_snake_case` verbs
- **Type hints**: Full type annotations required
- **Docstrings**: Required for request/response schemas
- **Constants**: Module-level constants at top of file
- **Error handling**: Catch HTTP errors per-file, log and continue

## Commit Guidelines

- Use imperative commit subjects: `feat: add retry logic`, `fix: handle missing issuer field`
- Keep changes narrowly scoped
- Include verification commands in PR descriptions
- Attach sanitized screenshots/excerpts when clarifying model behavior
- Remove temporary logging before committing
- Always read /Users/krisstudio/Developer/Projects/autoD/docs/initial_implementation_plan.md carefully before beginning work.
- API Keys are stored in environmental variables. You can find their names, values, etc., by viewing the ~/.zshrc file. You can use those API keys to populate local config / env files, if desired.