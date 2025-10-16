# Repository Guidelines

## Project Structure & Module Organization
`process_inbox.py` is the sandbox entry point; it walks `inbox/`, base64-encodes PDFs, and calls `POST /v1/responses` with strict structured outputs. Keep transient files in `inbox/` (git-ignored) and remove them after inspection so sensitive data never leaks into git. Log research, prompt revisions, and API learnings in `docs/`—always reread `docs/initial_implementation_plan.md` before altering flows. Model configuration lives in `config/models.py`; review `docs/model_policy.md` before touching those constants. When you add helpers, colocate them with the script and mirror the structure under `tests/` to keep fixtures discoverable.

## Build, Test, and Development Commands
Create a clean virtualenv with `python3 -m venv .venv && source .venv/bin/activate`. Install dependencies using `python -m pip install -U requests`; extend this command when you introduce new packages. Run the ingestion loop via `python process_inbox.py`; it will process every PDF in `inbox/` and print the model payload for review. Run `python scripts/check_model_policy.py --diff` alongside `pytest` before pushing to block accidental downgrades.

## Coding Style & Naming Conventions
Target Python 3.9+, four-space indentation, and full PEP 8 compliance. Use descriptive `lower_snake_case` verbs for functions (e.g., `encode_pdf`, `build_payload`) and keep module constants at the top. Preserve type hints, docstrings, and schema comments so downstream consumers know what the Responses API expects. Format changed Python modules with `black process_inbox.py` prior to review and keep the developer prompt text stable to maximize prompt caching. Never inline model names—import from `config.models` so the allow list stays authoritative.

## Testing Guidelines
Adopt `pytest`; place suites in `tests/test_<feature>.py` with functions named `test_<behavior>`. Mock HTTP calls with `responses` or `pytest-httpx` to avoid real API usage and capture edge cases such as empty inboxes, malformed PDFs, and HTTP failures. Run `pytest` locally before requesting review and add fixtures mirroring the runtime structure.

## Commit & Pull Request Guidelines
Write imperative, scoped commit subjects (e.g., `feat: add structured output schema`). In PRs summarize behavior changes, list verification commands (`python process_inbox.py`, `pytest`), and note any sample PDFs exercised. Flag any proposed model changes explicitly and cite `docs/model_policy.md`. Attach sanitized excerpts or screenshots only when necessary, ensuring issuers, totals, and credentials are redacted.

## Security & Configuration Tips
Load `OPENAI_API_KEY` from your shell or an ignored `.env`; rotate immediately if exposed. Never commit contents of `inbox/` or raw response JSON—share scrubbed snippets instead. Track token usage fields (`usage.prompt_tokens`, `usage.output_tokens`, `usage.prompt_tokens_details.cached_tokens`) when iterating so cost reporting stays aligned with the architecture plan.
