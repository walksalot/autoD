#!/usr/bin/env python3
"""
Simple demo app that sends PDFs from ./inbox to the OpenAI Responses API.

For each PDF in test_approach/inbox, the script:
 1. Base64-encodes the file
 2. Calls POST /v1/responses with an instruction prompt asking for metadata
 3. Prints the model's JSON summary to stdout

Usage:
    export OPENAI_API_KEY=sk-...
    python test_approach/process_inbox.py

Dependencies:
    - requests (pip install requests)

This utility is intentionally lightweight and standalone; it is not wired
into the primary Paper Autopilot pipeline.
"""

from __future__ import annotations

import base64
import json
import os
from itertools import chain
from pathlib import Path
from typing import Iterator

import requests

from config.models import (
    MODEL_POLICY_VERSION,
    PRIMARY_MODEL,
    ensure_model_allowed,
    ModelPolicyError,
)


API_URL = "https://api.openai.com/v1/responses"
MODEL_ENV_VAR = "PAPER_AUTOPILOT_MODEL"

_model_override = os.getenv(MODEL_ENV_VAR)
MODEL = _model_override or PRIMARY_MODEL

try:
    ensure_model_allowed(MODEL, source="process_inbox.py")
except ModelPolicyError as err:
    raise SystemExit(str(err)) from err

if _model_override:
    print(
        f"Using model override from ${MODEL_ENV_VAR}={MODEL} "
        f"(policy version {MODEL_POLICY_VERSION})."
    )
else:
    print(f"Using default model {MODEL} (policy version {MODEL_POLICY_VERSION}).")

REQUEST_TIMEOUT = 300

PROMPT_TEMPLATE = """You are a document intake assistant. A PDF is attached.
Please analyze it and return concise JSON metadata with the following keys:
- "file_name": string (original filename)
- "doc_type": short guess such as UtilityBill, BankStatement, Invoice, Receipt, or Unknown
- "issuer": organization or person who produced the document
- "primary_date": ISO date string (YYYY-MM-DD) if one is clearly stated, else null
- "total_amount": numeric amount if a single total is clearly indicated, else null
- "summary": short (≤40 words) synopsis of the document's purpose

Use null for any field you cannot infer confidently. Respond with JSON only."""


def iter_pdfs(inbox: Path) -> Iterator[Path]:
    if not inbox.exists():
        return iter(())
    pdfs = sorted(
        p for p in inbox.iterdir() if p.suffix.lower() == ".pdf" and p.is_file()
    )
    return iter(pdfs)


def encode_pdf(pdf_path: Path) -> str:
    data = pdf_path.read_bytes()
    encoded = base64.b64encode(data).decode("utf-8")
    return f"data:application/pdf;base64,{encoded}"


def call_responses_api(
    session: requests.Session, pdf_path: Path, encoded_pdf: str
) -> dict:
    payload = {
        "model": MODEL,
        "input": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": PROMPT_TEMPLATE,
                    },
                    {
                        "type": "input_file",
                        "filename": pdf_path.name,
                        "file_data": encoded_pdf,
                    },
                ],
            }
        ],
        "text": {"format": {"type": "json_object"}},
    }

    response = session.post(API_URL, json=payload, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.json()


def extract_output_text(response_json: dict) -> str:
    # Prefer output_text if provided, otherwise manually grab the message content.
    if "output_text" in response_json and response_json["output_text"]:
        return response_json["output_text"]

    for item in response_json.get("output", []):
        if item.get("type") == "message":
            for part in item.get("content", []):
                if part.get("type") in ("output_text", "text"):
                    return part.get("text", "")
    return ""


def main() -> None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("Missing OPENAI_API_KEY environment variable.")

    inbox = Path(__file__).resolve().parent / "inbox"
    pdf_iter = iter_pdfs(inbox)
    try:
        first_pdf = next(pdf_iter)
    except StopIteration:
        print(f"No PDF files found in {inbox}. Drop test PDFs there and rerun.")
        return

    with requests.Session() as session:
        session.headers.update({"Authorization": f"Bearer {api_key}"})
        for pdf_path in chain((first_pdf,), pdf_iter):
            print(f"Processing {pdf_path.name} ...")
            encoded_pdf = encode_pdf(pdf_path)
            try:
                response_json = call_responses_api(session, pdf_path, encoded_pdf)
                output_text = extract_output_text(response_json)
                if output_text:
                    print(output_text)
                else:
                    print(json.dumps(response_json, indent=2))
            except requests.HTTPError as err:
                print(
                    f"HTTP error for {pdf_path.name}: {err.response.status_code} {err.response.text}"
                )
            except Exception as exc:  # pragma: no cover
                print(f"Failed to process {pdf_path.name}: {exc}")
            print("-" * 60)


if __name__ == "__main__":
    main()
