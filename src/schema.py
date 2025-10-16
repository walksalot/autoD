"""
Structured output schema for Paper Autopilot.

This module defines the JSON Schema used with OpenAI Responses API
structured outputs.  The schema captures classification, extraction,
actionability, OCR excerpts, and dedupe fingerprints so downstream
systems can rely on a consistent contract.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, Optional

try:
    import jsonschema  # type: ignore
except (
    ImportError
):  # pragma: no cover - jsonschema is an optional dependency at runtime
    jsonschema = None

SCHEMA_VERSION = "1.0.0"

_CATEGORIES = [
    "Financial & Administrative",
    "Property & Assets",
    "Personal & Family",
    "Business & Professional",
    "Legal & Government",
    "Household & Lifestyle",
    "Creative & Miscellaneous",
]

_SUBCATEGORIES = [
    "Bills",
    "Invoices",
    "Receipts",
    "Banking",
    "Taxes",
    "Investments",
    "Loans & Mortgages",
    "Insurance",
    "Legal",
    "Government",
    "Medical",
    "Education",
    "Property Management",
    "Utilities",
    "Telecom",
    "Subscriptions",
    "Payroll",
    "HR",
    "Travel",
    "Vehicle",
    "Misc",
]


def _base_schema() -> Dict[str, Any]:
    """Return the base schema (without per-file const overrides)."""
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "title": "Paper Autopilot Document Metadata",
        "description": "Structured metadata extracted from a PDF document.",
        "additionalProperties": False,
        "properties": {
            "schema_version": {
                "type": "string",
                "description": "Schema version for compatibility tracking.",
                "enum": [SCHEMA_VERSION],
            },
            "processed_date": {
                "type": "string",
                "description": "When this document was processed (ISO 8601).",
                "minLength": 1,
            },
            "original_file_name": {
                "type": "string",
                "description": "Original filename provided by the user.",
                "minLength": 1,
                "maxLength": 255,
            },
            "source_file_id": {
                "type": "string",
                "description": "OpenAI Files API identifier for the processed file.",
                "minLength": 1,
            },
            # Titles & summaries
            "title": {"type": ["string", "null"], "maxLength": 512},
            "brief_description": {"type": ["string", "null"], "maxLength": 512},
            "long_description": {"type": ["string", "null"], "maxLength": 2048},
            "summary": {"type": ["string", "null"], "maxLength": 1500},
            "summary_long": {"type": ["string", "null"], "maxLength": 4096},
            "email_subject": {"type": ["string", "null"], "maxLength": 512},
            "email_preview_text": {"type": ["string", "null"], "maxLength": 160},
            "email_body_markdown": {"type": ["string", "null"], "maxLength": 10000},
            # Classification
            "category": {
                "type": "string",
                "enum": _CATEGORIES,
            },
            "subcategory": {
                "type": ["string", "null"],
                "enum": _SUBCATEGORIES + [None],
            },
            "doc_type": {
                "type": ["string", "null"],
                "maxLength": 256,
            },
            "confidence_score": {
                "type": ["number", "null"],
                "minimum": 0.0,
                "maximum": 1.0,
            },
            # Parties & dates
            "issuer": {"type": ["string", "null"], "maxLength": 512},
            "primary_date": {
                "type": ["string", "null"],
                "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
            },
            "period_start_date": {
                "type": ["string", "null"],
                "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
            },
            "period_end_date": {
                "type": ["string", "null"],
                "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
            },
            # Actionability
            "key_points": {
                "type": "array",
                "items": {"type": "string", "maxLength": 512},
            },
            "action_items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "description": {"type": "string", "maxLength": 512},
                        "assignee_suggestion": {
                            "type": ["string", "null"],
                            "maxLength": 256,
                        },
                        "due": {"type": ["string", "null"], "maxLength": 128},
                        "priority": {
                            "type": ["string", "null"],
                            "enum": ["low", "medium", "high", "critical", None],
                        },
                        "blocking": {"type": ["boolean", "null"]},
                        "rationale": {"type": ["string", "null"], "maxLength": 1024},
                    },
                    "required": ["description"],
                },
            },
            "deadline": {"type": ["string", "null"], "maxLength": 128},
            "deadline_source": {
                "type": ["string", "null"],
                "enum": [
                    "explicit_due_date",
                    "implied_in_text",
                    "inferred_from_context",
                    "none",
                    None,
                ],
            },
            "urgency_score": {
                "type": ["integer", "null"],
                "minimum": 0,
                "maximum": 100,
            },
            "urgency_reason": {"type": ["string", "null"], "maxLength": 1024},
            # Extracted fields
            "extracted_fields": {
                "type": "object",
                "additionalProperties": True,
                "properties": {
                    "amount_due": {"type": ["number", "null"]},
                    "due_date": {
                        "type": ["string", "null"],
                        "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
                    },
                    "account_number": {"type": ["string", "null"], "maxLength": 256},
                    "invoice_number": {"type": ["string", "null"], "maxLength": 256},
                    "statement_date": {
                        "type": ["string", "null"],
                        "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
                    },
                    "period_start_date": {
                        "type": ["string", "null"],
                        "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
                    },
                    "period_end_date": {
                        "type": ["string", "null"],
                        "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
                    },
                    "balance": {"type": ["number", "null"]},
                    "currency": {"type": ["string", "null"], "maxLength": 3},
                    "policy_number": {"type": ["string", "null"], "maxLength": 256},
                    "claim_number": {"type": ["string", "null"], "maxLength": 256},
                    "loan_number": {"type": ["string", "null"], "maxLength": 256},
                    "service_address": {"type": ["string", "null"], "maxLength": 512},
                    "property_address": {"type": ["string", "null"], "maxLength": 512},
                    "tax_id": {"type": ["string", "null"], "maxLength": 64},
                    "customer_name": {"type": ["string", "null"], "maxLength": 256},
                    "email": {"type": ["string", "null"], "maxLength": 256},
                    "phone": {"type": ["string", "null"], "maxLength": 64},
                    "meter_readings": {"type": ["string", "null"], "maxLength": 512},
                },
            },
            # Filing + organization
            "suggested_file_name": {
                "type": "string",
                "description": "Recommended filename (without extension).",
                "minLength": 1,
                "maxLength": 150,
            },
            "suggested_relative_path": {
                "type": ["string", "null"],
                "description": "Recommended relative path for archival.",
                "maxLength": 1024,
            },
            "tags": {
                "type": "array",
                "items": {"type": "string", "maxLength": 64},
            },
            "language": {
                "type": ["string", "null"],
                "description": "ISO 639-1 language code.",
                "pattern": "^[a-z]{2}$",
            },
            "page_count": {
                "type": ["integer", "null"],
                "minimum": 1,
            },
            # OCR & visual
            "ocr_text_excerpt": {"type": ["string", "null"], "maxLength": 40000},
            "ocr_page_summaries": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "page": {"type": "integer", "minimum": 1},
                        "text_excerpt": {"type": "string", "maxLength": 8000},
                        "image_description": {"type": "string", "maxLength": 2000},
                    },
                    "required": ["page", "text_excerpt", "image_description"],
                },
            },
            # Dedupe / normalization
            "content_signature": {"type": ["string", "null"], "maxLength": 8192},
            "cross_doc_matches": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "vector_store_id": {
                            "type": ["string", "null"],
                            "maxLength": 64,
                        },
                        "file_id": {"type": ["string", "null"], "maxLength": 64},
                        "filename": {"type": ["string", "null"], "maxLength": 255},
                        "score": {
                            "type": ["number", "null"],
                            "minimum": 0.0,
                            "maximum": 1.0,
                        },
                        "rationale": {"type": ["string", "null"], "maxLength": 1024},
                    },
                    "required": ["score"],
                },
            },
            "normalization": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "canonical_issuer": {"type": ["string", "null"], "maxLength": 256},
                    "canonical_account_label": {
                        "type": ["string", "null"],
                        "maxLength": 256,
                    },
                    "property_identifier": {
                        "type": ["string", "null"],
                        "maxLength": 256,
                    },
                },
            },
            # Diagnostics
            "errors": {"type": "array", "items": {"type": "string", "maxLength": 512}},
        },
        "required": [
            "schema_version",
            "processed_date",
            "original_file_name",
            "source_file_id",
            "category",
            "doc_type",
            "summary",
            "suggested_file_name",
        ],
    }


def get_document_extraction_schema() -> Dict[str, Any]:
    """
    Return a deep copy of the base schema.

    The caller may mutate the returned dict (e.g., to add const constraints).
    """
    return deepcopy(_base_schema())


def build_schema_with_constants(
    *,
    processed_date: str,
    original_file_name: str,
    source_file_id: str,
    base_schema: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Return a schema with per-file constants baked in.

    Args:
        processed_date: ISO timestamp string for processed_date.
        original_file_name: Original filename string.
        source_file_id: Files API ID to embed.
        base_schema: Optional schema to clone (defaults to base schema).
    """
    schema = (
        deepcopy(base_schema)
        if base_schema is not None
        else get_document_extraction_schema()
    )
    overrides = {
        "processed_date": processed_date,
        "original_file_name": original_file_name,
        "source_file_id": source_file_id,
    }
    for key, value in overrides.items():
        schema["properties"][key]["const"] = value
    return schema


def validate_response(response_data: Dict[str, Any]) -> tuple[bool, list[str]]:
    """
    Validate a JSON response against the base schema.

    Returns:
        (is_valid, errors)
    """
    if jsonschema is None:
        return False, [
            "jsonschema library not installed. Run: pip install jsonschema>=4.20.0"
        ]

    schema = get_document_extraction_schema()
    try:
        jsonschema.validate(instance=response_data, schema=schema)
        return True, []
    except jsonschema.ValidationError as exc:  # type: ignore[attr-defined]
        path = ".".join(str(part) for part in exc.path)
        return False, [f"Validation error at {path or '<root>'}: {exc.message}"]
    except jsonschema.SchemaError as exc:  # type: ignore[attr-defined]
        return False, [f"Schema error: {exc.message}"]


__all__ = [
    "SCHEMA_VERSION",
    "get_document_extraction_schema",
    "build_schema_with_constants",
    "validate_response",
]
