# OpenAI Responses PDF Sandbox

This sandbox showcases how to submit PDFs to the OpenAI Responses API using the `/v1/responses` endpoint with `input_file` parts. The goal is to iterate quickly on metadata extraction prompts before folding changes into larger pipelines.

## Repository Layout

```
.
├── AGENTS.md          # Contributor guide and repo conventions
├── docs/              # Research notes and API experiments
├── inbox/             # Drop PDFs here (ignored by git)
└── process_inbox.py   # Script that submits PDFs to the Responses API
```

## Getting Started

1. Create and activate a virtual environment:
   ```bash
   python3 -m venv .venv && source .venv/bin/activate
   ```
2. Install dependencies:
   ```bash
   python -m pip install -U requests
   ```
3. Export your API key (requires access to a vision-capable model such as `gpt-5`):
   ```bash
   export OPENAI_API_KEY=sk-...
   ```
4. Place PDFs in `inbox/` and run the processor:
   ```bash
   python process_inbox.py
   ```

For each PDF, the script base64-encodes the file, assembles a metadata prompt, and prints the JSON response returned by the model. Add temporary logging inside `process_inbox.py` when troubleshooting; remove it before committing.

## Contributing

Review `AGENTS.md` for project conventions, testing expectations, and security practices. In short, follow PEP 8, run `black process_inbox.py` before review, use `pytest` for any automated coverage, and never commit sample PDFs or raw API responses. Share sanitized excerpts only when needed to illustrate behavior. Keep model selections aligned with `docs/model_policy.md`—do not downgrade from GPT-5 variants without approval.

### Implementation Plan Reference

The end-to-end architecture, retry strategy, vector-store setup, and database plan are detailed in `docs/initial_implementation_plan.md`. Read it before building new features so prompt structure, structured outputs, and cost tracking stay aligned with the intended workflow.

### Policy Checks

Before opening a pull request, run:

```bash
python scripts/check_model_policy.py --diff
pytest tests/test_model_policy.py
```

Both commands will fail loudly if deprecated model identifiers surface.
