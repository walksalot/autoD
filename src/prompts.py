"""
Prompt construction for Paper Autopilot's Responses API workflow.

This module builds the three-message conversation (system / developer / user)
and attaches the strict JSON schema used for Structured Outputs.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.config import get_config
from src.schema import build_schema_with_constants, get_document_extraction_schema

DEFAULT_SCHEMA_NAME = "paper_autopilot_metadata_v3"

SYSTEM_PROMPT = (
    "You are a meticulous document ingestion assistant. "
    "Follow developer instructions exactly and respond with strictly valid JSON."
)

DEVELOPER_PROMPT = """You are a **File Systems Architect / Archival Specialist** for “Paper Autopilot”.

GOAL
Return a single JSON object that matches the provided JSON schema exactly (the API enforces it). Output JSON only. If uncertain, use null. Do not invent values.

INPUTS YOU MAY SEE
- A scanned/digital PDF (often multi-page, image-only).
- A user message that includes:
  • processed_at (UTC ISO 8601) → echo EXACTLY into `processed_date`.
  • original_file_name → echo EXACTLY into `original_file_name`.
  • Optional hints (base_path, property names, known issuers).
  • source_file_id (OpenAI file id) → echo EXACTLY into `source_file_id`.

PRIMARY TASKS
1) CLASSIFY: set `category` (enum), `subcategory` (enum), and `doc_type` (free text).
2) EXTRACT FIELDS if present (use null if absent): amount_due, due_date, account_number,
   invoice_number, statement_date, period_start_date, period_end_date, balance, currency,
   policy_number, claim_number, loan_number, service_address/property_address, tax_id,
   customer_name, email, phone, meter_readings.
3) TITLES & SUMMARIES:
   - `title`: human-friendly title (not a filename).
   - `brief_description`: 1–2 sentences (~≤ 300 chars).
   - `long_description`: short synopsis (~≤ 1,200 chars).
   - `summary_long`: executive summary (~½ page; ~1,200–2,000 chars).
   - `email_subject`, `email_preview_text` (≤ 160 chars), `email_body_markdown`
     (concise, scannable; include amounts, due dates, and required actions).
4) KEY POINTS & ACTIONS:
   - `key_points`: concise bullets with salient facts/flags (e.g., “past due”, “renew by <date>”).
   - `action_items`: list of actionable tasks; for each include: description, assignee_suggestion,
     due (ISO or human text), priority (high/medium/low/critical), blocking (bool), rationale.
   - `deadline`: operative deadline if any (ISO date if explicit; otherwise clear natural-language).
   - `deadline_source`: one of ["explicit_due_date","implied_in_text","inferred_from_context","none"].
   - `urgency_score`: 0–100 + `urgency_reason`: 1–3 sentences.
5) FILE NAMING & PLACEMENT:
   - `suggested_file_name` (no extension). Sanitize to ASCII; remove slashes/newlines.
     Prefer: `YYYY-MM-DD – {issuer} – {doc_type} – {short_topic}`; ≤ 150 chars.
   - `suggested_relative_path`: compact path such as `Financial & Administrative/Bills/Utilities`
     or `Property & Assets/[Property]/Insurance`.
6) OCR & VISUAL:
   - `ocr_text_excerpt`: up to **40,000 characters**; if longer, end with “ … (truncated)”.
   - `ocr_page_summaries`: for each page: {page, text_excerpt (≤ **8,000 chars**), image_description}.
     Describe layout/logos/stamps even for image-only scans.
7) DEDUPE & CROSS-DOC NORMALIZATION:
   - `content_signature`: first ~512 chars of normalized text (heuristic fingerprint).
   - `cross_doc_matches`: if similar docs are found (via File Search), list matches with score/rationale.
   - `normalization`: canonical issuer name, canonical account label, property identifier, if inferable.
8) TAGS: 5–12 concise tags (issuer, doc_type, lifecycle flags like `due_soon`, domain like `utilities`, property IDs).
9) PII SAFETY: Keep masked values masked (e.g., ****1234).
10) DATES:
    - Prefer ISO `YYYY-MM-DD` for date-only fields.
    - For `processed_date`, echo the provided `processed_at` exactly (ISO date-time allowed).

CATEGORIES (enum)
- category ∈ ["Financial & Administrative","Property & Assets","Personal & Family",
              "Business & Professional","Legal & Government","Household & Lifestyle",
              "Creative & Miscellaneous"]
- subcategory ∈ ["Bills","Invoices","Receipts","Banking","Taxes","Investments",
                 "Loans & Mortgages","Insurance","Legal","Government","Medical","Education",
                 "Property Management","Utilities","Telecom","Subscriptions","Payroll","HR",
                 "Travel","Vehicle","Misc"] (or null when none apply)

OUTPUT
Return ONLY the JSON object that matches the schema. No markdown, no extra commentary."""


def build_user_prompt(
    *,
    processed_at: str,
    original_file_name: str,
    source_file_id: Optional[str] = None,
    page_count: Optional[int] = None,
    vector_context: Optional[str] = None,
    similar_documents_found: bool = False,
    extra_context: Optional[str] = None,
) -> str:
    """
    Build the per-document user prompt.
    """
    lines: List[str] = [
        "Context for this file:",
        f"- processed_at (UTC ISO 8601): {processed_at}",
        f"- original_file_name: {original_file_name}",
    ]

    if source_file_id:
        lines.append(f"- source_file_id: {source_file_id}")
    if page_count is not None:
        lines.append(f"- page_count: {page_count}")

    lines.extend(
        [
            "",
            "Instructions:",
            "- Set `processed_date` to processed_at exactly.",
            "- Set `original_file_name` exactly.",
            "- Set `source_file_id` exactly (if provided).",
            "- Use the attached PDF only; do not fabricate values.",
            "- Return only JSON per the schema.",
        ]
    )

    if extra_context:
        lines.extend(["", extra_context.strip()])

    if vector_context:
        lines.append("")
        header = (
            "Related documents context (consistent naming, recurring vendors, etc.):"
            if similar_documents_found
            else "Historical context:"
        )
        lines.append(header)
        lines.append(vector_context.strip())

    return "\n".join(lines)


def build_responses_api_payload(
    *,
    filename: str,
    file_id: Optional[str] = None,
    pdf_base64: Optional[str] = None,
    processed_at: Optional[str] = None,
    original_file_name: Optional[str] = None,
    source_file_id: Optional[str] = None,
    vector_store_ids: Optional[List[str]] = None,
    vector_context: Optional[str] = None,
    similar_documents_found: bool = False,
    page_count: Optional[int] = None,
    schema: Optional[Dict[str, Any]] = None,
    schema_name: str = DEFAULT_SCHEMA_NAME,
    reasoning_effort: Optional[str] = None,
    verbosity: Optional[str] = None,
    extra_user_context: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build the payload for OpenAI Responses API.

    Args:
        filename: Human-readable filename (used for logging).
        file_id: OpenAI Files API identifier (preferred).
        pdf_base64: Base64 data URI fallback (legacy).
        processed_at: ISO timestamp for processed_date (auto-generated if None).
        original_file_name: Optional override of the filename echoed to the model.
        source_file_id: Optional override; defaults to file_id when available.
        vector_store_ids: List of vector store IDs to attach for File Search.
        vector_context: Optional textual context from prior documents.
        similar_documents_found: Whether vector_context represents close matches.
        page_count: Document page count (if known).
        schema: Optional pre-built schema to reuse.
        schema_name: Name passed to structured output format.
        reasoning_effort / verbosity: Passed through when supported.
        extra_user_context: Additional instructions appended to the user prompt.
    """
    if not file_id and not pdf_base64:
        raise ValueError("Either file_id or pdf_base64 must be provided.")
    if file_id and pdf_base64:
        raise ValueError("Provide only one of file_id or pdf_base64.")

    processed_at = processed_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    original_file_name = original_file_name or filename
    source_file_id = source_file_id or file_id

    schema_base = schema or get_document_extraction_schema()
    if source_file_id:
        schema_to_use = build_schema_with_constants(
            processed_date=processed_at,
            original_file_name=original_file_name,
            source_file_id=source_file_id,
            base_schema=schema_base,
        )
    else:
        # If we cannot set const values (e.g., legacy flow), still copy to avoid mutation.
        schema_to_use = deepcopy(schema_base)

    user_prompt = build_user_prompt(
        processed_at=processed_at,
        original_file_name=original_file_name,
        source_file_id=source_file_id,
        page_count=page_count,
        vector_context=vector_context,
        similar_documents_found=similar_documents_found,
        extra_context=extra_user_context,
    )

    user_content: List[Dict[str, Any]] = [
        {"type": "input_text", "text": user_prompt},
    ]

    if file_id:
        file_part: Dict[str, Any] = {"type": "input_file", "file_id": file_id}
        if filename:
            file_part["filename"] = filename
    else:
        # Ensure the data URI prefix exists
        encoded = pdf_base64 or ""
        if not encoded.startswith("data:"):
            encoded = f"data:application/pdf;base64,{encoded}"
        file_part = {"type": "input_file", "filename": filename, "file_data": encoded}

    user_content.append(file_part)

    config = get_config()
    payload: Dict[str, Any] = {
        "model": config.openai_model,
        "input": [
            {"role": "system", "content": [{"type": "input_text", "text": SYSTEM_PROMPT}]},
            {"role": "developer", "content": [{"type": "input_text", "text": DEVELOPER_PROMPT}]},
            {"role": "user", "content": user_content},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "schema": schema_to_use,
                    "strict": True,
                },
            }
        },
    }

    if vector_store_ids:
        payload["tools"] = [{"type": "file_search"}]
        payload["attachments"] = [{"vector_store_id": vs_id} for vs_id in vector_store_ids]

    if reasoning_effort:
        payload["reasoning_effort"] = reasoning_effort
    if verbosity:
        payload["verbosity"] = verbosity

    return payload


__all__ = [
    "SYSTEM_PROMPT",
    "DEVELOPER_PROMPT",
    "build_user_prompt",
    "build_responses_api_payload",
    "DEFAULT_SCHEMA_NAME",
]
