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
            "title": {
                "anyOf": [{"type": "string", "maxLength": 512}, {"type": "null"}]
            },
            "brief_description": {
                "anyOf": [{"type": "string", "maxLength": 512}, {"type": "null"}]
            },
            "long_description": {
                "anyOf": [{"type": "string", "maxLength": 2048}, {"type": "null"}]
            },
            "summary": {
                "anyOf": [{"type": "string", "maxLength": 1500}, {"type": "null"}]
            },
            "summary_long": {
                "anyOf": [{"type": "string", "maxLength": 4096}, {"type": "null"}]
            },
            "email_subject": {
                "anyOf": [{"type": "string", "maxLength": 512}, {"type": "null"}]
            },
            "email_preview_text": {
                "anyOf": [{"type": "string", "maxLength": 160}, {"type": "null"}]
            },
            "email_body_markdown": {
                "anyOf": [{"type": "string", "maxLength": 10000}, {"type": "null"}]
            },
            # Classification
            "category": {
                "type": "string",
                "enum": _CATEGORIES,
            },
            "subcategory": {
                "anyOf": [{"type": "string", "enum": _SUBCATEGORIES}, {"type": "null"}]
            },
            "doc_type": {
                "anyOf": [{"type": "string", "maxLength": 256}, {"type": "null"}]
            },
            "confidence_score": {
                "anyOf": [
                    {"type": "number", "minimum": 0.0, "maximum": 1.0},
                    {"type": "null"},
                ]
            },
            # Parties & dates
            "issuer": {
                "anyOf": [{"type": "string", "maxLength": 512}, {"type": "null"}]
            },
            "primary_date": {
                "anyOf": [
                    {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
                    {"type": "null"},
                ]
            },
            "period_start_date": {
                "anyOf": [
                    {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
                    {"type": "null"},
                ]
            },
            "period_end_date": {
                "anyOf": [
                    {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
                    {"type": "null"},
                ]
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
                            "anyOf": [
                                {"type": "string", "maxLength": 256},
                                {"type": "null"},
                            ]
                        },
                        "due": {
                            "anyOf": [
                                {"type": "string", "maxLength": 128},
                                {"type": "null"},
                            ]
                        },
                        "priority": {
                            "anyOf": [
                                {
                                    "type": "string",
                                    "enum": ["low", "medium", "high", "critical"],
                                },
                                {"type": "null"},
                            ]
                        },
                        "blocking": {"anyOf": [{"type": "boolean"}, {"type": "null"}]},
                        "rationale": {
                            "anyOf": [
                                {"type": "string", "maxLength": 1024},
                                {"type": "null"},
                            ]
                        },
                    },
                    "required": [
                        "description",
                        "assignee_suggestion",
                        "due",
                        "priority",
                        "blocking",
                        "rationale",
                    ],
                },
            },
            "deadline": {
                "anyOf": [{"type": "string", "maxLength": 128}, {"type": "null"}]
            },
            "deadline_source": {
                "anyOf": [
                    {
                        "type": "string",
                        "enum": [
                            "explicit_due_date",
                            "implied_in_text",
                            "inferred_from_context",
                            "none",
                        ],
                    },
                    {"type": "null"},
                ]
            },
            "urgency_score": {
                "anyOf": [
                    {"type": "integer", "minimum": 0, "maximum": 100},
                    {"type": "null"},
                ]
            },
            "urgency_reason": {
                "anyOf": [{"type": "string", "maxLength": 1024}, {"type": "null"}]
            },
            # Extracted fields
            "extracted_fields": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "amount_due": {"anyOf": [{"type": "number"}, {"type": "null"}]},
                    "due_date": {
                        "anyOf": [
                            {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
                            {"type": "null"},
                        ]
                    },
                    "account_number": {
                        "anyOf": [
                            {"type": "string", "maxLength": 256},
                            {"type": "null"},
                        ]
                    },
                    "invoice_number": {
                        "anyOf": [
                            {"type": "string", "maxLength": 256},
                            {"type": "null"},
                        ]
                    },
                    "statement_date": {
                        "anyOf": [
                            {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
                            {"type": "null"},
                        ]
                    },
                    "period_start_date": {
                        "anyOf": [
                            {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
                            {"type": "null"},
                        ]
                    },
                    "period_end_date": {
                        "anyOf": [
                            {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
                            {"type": "null"},
                        ]
                    },
                    "balance": {"anyOf": [{"type": "number"}, {"type": "null"}]},
                    "currency": {
                        "anyOf": [{"type": "string", "maxLength": 3}, {"type": "null"}]
                    },
                    "policy_number": {
                        "anyOf": [
                            {"type": "string", "maxLength": 256},
                            {"type": "null"},
                        ]
                    },
                    "claim_number": {
                        "anyOf": [
                            {"type": "string", "maxLength": 256},
                            {"type": "null"},
                        ]
                    },
                    "loan_number": {
                        "anyOf": [
                            {"type": "string", "maxLength": 256},
                            {"type": "null"},
                        ]
                    },
                    "service_address": {
                        "anyOf": [
                            {"type": "string", "maxLength": 512},
                            {"type": "null"},
                        ]
                    },
                    "property_address": {
                        "anyOf": [
                            {"type": "string", "maxLength": 512},
                            {"type": "null"},
                        ]
                    },
                    "tax_id": {
                        "anyOf": [{"type": "string", "maxLength": 64}, {"type": "null"}]
                    },
                    "customer_name": {
                        "anyOf": [
                            {"type": "string", "maxLength": 256},
                            {"type": "null"},
                        ]
                    },
                    "email": {
                        "anyOf": [
                            {"type": "string", "maxLength": 256},
                            {"type": "null"},
                        ]
                    },
                    "phone": {
                        "anyOf": [{"type": "string", "maxLength": 64}, {"type": "null"}]
                    },
                    "meter_readings": {
                        "anyOf": [
                            {"type": "string", "maxLength": 512},
                            {"type": "null"},
                        ]
                    },
                },
                "required": [
                    "amount_due",
                    "due_date",
                    "account_number",
                    "invoice_number",
                    "statement_date",
                    "period_start_date",
                    "period_end_date",
                    "balance",
                    "currency",
                    "policy_number",
                    "claim_number",
                    "loan_number",
                    "service_address",
                    "property_address",
                    "tax_id",
                    "customer_name",
                    "email",
                    "phone",
                    "meter_readings",
                ],
            },
            # Filing + organization
            "suggested_file_name": {
                "type": "string",
                "description": "Recommended filename (without extension).",
                "minLength": 1,
                "maxLength": 150,
            },
            "suggested_relative_path": {
                "anyOf": [
                    {
                        "type": "string",
                        "maxLength": 1024,
                        "description": "Recommended relative path for archival.",
                    },
                    {"type": "null"},
                ]
            },
            "tags": {
                "type": "array",
                "items": {"type": "string", "maxLength": 64},
            },
            "language": {
                "anyOf": [
                    {
                        "type": "string",
                        "pattern": "^[a-z]{2}$",
                        "description": "ISO 639-1 language code.",
                    },
                    {"type": "null"},
                ]
            },
            "page_count": {
                "anyOf": [{"type": "integer", "minimum": 1}, {"type": "null"}]
            },
            # OCR & visual
            "ocr_text_excerpt": {
                "anyOf": [{"type": "string", "maxLength": 40000}, {"type": "null"}]
            },
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
            "content_signature": {
                "anyOf": [{"type": "string", "maxLength": 8192}, {"type": "null"}]
            },
            "cross_doc_matches": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "vector_store_id": {
                            "anyOf": [
                                {"type": "string", "maxLength": 64},
                                {"type": "null"},
                            ]
                        },
                        "file_id": {
                            "anyOf": [
                                {"type": "string", "maxLength": 64},
                                {"type": "null"},
                            ]
                        },
                        "filename": {
                            "anyOf": [
                                {"type": "string", "maxLength": 255},
                                {"type": "null"},
                            ]
                        },
                        "score": {
                            "anyOf": [
                                {"type": "number", "minimum": 0.0, "maximum": 1.0},
                                {"type": "null"},
                            ]
                        },
                        "rationale": {
                            "anyOf": [
                                {"type": "string", "maxLength": 1024},
                                {"type": "null"},
                            ]
                        },
                    },
                    "required": [
                        "vector_store_id",
                        "file_id",
                        "filename",
                        "score",
                        "rationale",
                    ],
                },
            },
            "normalization": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "canonical_issuer": {
                        "anyOf": [
                            {"type": "string", "maxLength": 256},
                            {"type": "null"},
                        ]
                    },
                    "canonical_account_label": {
                        "anyOf": [
                            {"type": "string", "maxLength": 256},
                            {"type": "null"},
                        ]
                    },
                    "property_identifier": {
                        "anyOf": [
                            {"type": "string", "maxLength": 256},
                            {"type": "null"},
                        ]
                    },
                },
                "required": [
                    "canonical_issuer",
                    "canonical_account_label",
                    "property_identifier",
                ],
            },
            # Diagnostics
            "errors": {"type": "array", "items": {"type": "string", "maxLength": 512}},
        },
        "required": [
            "action_items",
            "brief_description",
            "category",
            "confidence_score",
            "content_signature",
            "cross_doc_matches",
            "deadline",
            "deadline_source",
            "doc_type",
            "email_body_markdown",
            "email_preview_text",
            "email_subject",
            "errors",
            "extracted_fields",
            "issuer",
            "key_points",
            "language",
            "long_description",
            "normalization",
            "ocr_page_summaries",
            "ocr_text_excerpt",
            "original_file_name",
            "page_count",
            "period_end_date",
            "period_start_date",
            "primary_date",
            "processed_date",
            "schema_version",
            "source_file_id",
            "subcategory",
            "suggested_file_name",
            "suggested_relative_path",
            "summary",
            "summary_long",
            "tags",
            "title",
            "urgency_reason",
            "urgency_score",
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
