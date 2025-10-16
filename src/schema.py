"""
JSON Schema definitions for OpenAI Responses API structured outputs.

This module provides strict JSON schemas with `additionalProperties: false`
for OpenAI structured outputs, ensuring type-safe metadata extraction.

The schema is optimized for:
- Comprehensive PDF metadata extraction (40+ fields)
- Strict validation with no extra properties allowed
- Business intelligence fields (action items, deadlines, urgency)
- Deduplication support via content signatures
- OpenAI Responses API compatibility

Schema Version: 1.0.0
"""

from typing import Dict, Any


SCHEMA_VERSION = "1.0.0"


def get_document_extraction_schema() -> Dict[str, Any]:
    """
    Generate JSON schema for PDF metadata extraction.

    This schema is passed to OpenAI Responses API via:
    {
        "text": {
            "format": {
                "type": "json_schema",
                "name": "document_metadata",
                "schema": get_document_extraction_schema(),
                "strict": true
            }
        }
    }

    The schema enforces strict validation (additionalProperties: false) and
    includes comprehensive metadata fields for business intelligence,
    deduplication, and document management. All fields are required but allow
    null so the model must emit every key while signalling missing data clearly.
    """
    properties: Dict[str, Any] = {
        "schema_version": {
            "type": "string",
            "description": "Schema version for compatibility tracking",
            "enum": [SCHEMA_VERSION],
        },
        "file_name": {
            "type": "string",
            "description": "Original filename from PDF",
            "minLength": 1,
            "maxLength": 255,
        },
        "page_count": {
            "type": ["integer", "null"],
            "description": "Number of pages in document",
            "minimum": 1,
        },
        "doc_type": {
            "type": "string",
            "description": "Primary document type classification",
            "enum": [
                "Invoice",
                "Receipt",
                "BankStatement",
                "CreditCardStatement",
                "UtilityBill",
                "Contract",
                "Agreement",
                "Letter",
                "Form",
                "Report",
                "Certificate",
                "Tax Document",
                "Insurance Document",
                "Medical Record",
                "Legal Document",
                "Other",
                "Unknown",
            ],
        },
        "doc_subtype": {
            "type": ["string", "null"],
            "description": "More specific document subtype",
            "maxLength": 100,
        },
        "confidence_score": {
            "type": "number",
            "description": "Model confidence in classification (0.0-1.0)",
            "minimum": 0.0,
            "maximum": 1.0,
        },
        "issuer": {
            "type": ["string", "null"],
            "description": "Organization or person who issued the document",
            "maxLength": 255,
        },
        "recipient": {
            "type": ["string", "null"],
            "description": "Intended recipient of the document",
            "maxLength": 255,
        },
        "primary_date": {
            "type": ["string", "null"],
            "description": "Primary date (ISO 8601: YYYY-MM-DD)",
            "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
        },
        "secondary_date": {
            "type": ["string", "null"],
            "description": "Secondary date like due date (ISO 8601: YYYY-MM-DD)",
            "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
        },
        "total_amount": {
            "type": ["number", "null"],
            "description": "Total monetary amount",
        },
        "currency": {
            "type": ["string", "null"],
            "description": "Currency code (ISO 4217)",
            "pattern": "^[A-Z]{3}$",
            "examples": ["USD", "EUR", "GBP"],
        },
        "summary": {
            "type": ["string", "null"],
            "description": "Brief document summary (max 200 words)",
            "maxLength": 1500,
        },
        "action_items": {
            "type": "array",
            "description": "Extracted action items",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["description", "deadline", "priority"],
                "properties": {
                    "description": {"type": "string", "maxLength": 500},
                    "deadline": {
                        "type": ["string", "null"],
                        "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "critical"],
                    },
                },
            },
        },
        "deadlines": {
            "type": "array",
            "description": "Important deadlines",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["date", "description", "type"],
                "properties": {
                    "date": {"type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
                    "description": {"type": "string", "maxLength": 200},
                    "type": {
                        "type": "string",
                        "enum": ["payment", "response", "filing", "renewal", "other"],
                    },
                },
            },
        },
        "urgency_level": {
            "type": ["string", "null"],
            "description": "Overall urgency assessment",
            "enum": ["low", "medium", "high", "critical", None],
        },
        "tags": {
            "type": "array",
            "description": "Relevant tags for categorization",
            "items": {"type": "string", "maxLength": 50},
            "maxItems": 20,
        },
        "language_detected": {
            "type": ["string", "null"],
            "description": "Detected language (ISO 639-1)",
            "pattern": "^[a-z]{2}$",
            "examples": ["en", "es", "fr"],
        },
        "ocr_text_excerpt": {
            "type": ["string", "null"],
            "description": "First 500 characters of text for search",
            "maxLength": 500,
        },
        "extraction_quality": {
            "type": ["string", "null"],
            "description": "Quality assessment of extraction",
            "enum": ["excellent", "good", "fair", "poor", None],
        },
        "requires_review": {
            "type": "boolean",
            "description": "Whether manual review is needed",
            "default": False,
        },
        "notes": {
            "type": ["string", "null"],
            "description": "Additional notes or observations",
            "maxLength": 1000,
        },
    }

    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "title": "Document Metadata Extraction",
        "description": "Comprehensive metadata extracted from PDF document",
        "additionalProperties": False,
        "properties": properties,
        "required": list(properties.keys()),
    }


def validate_response(response_data: Dict[str, Any]) -> tuple[bool, list[str]]:
    """
    Validate API response against schema.

    Args:
        response_data: Parsed JSON response from OpenAI

    Returns:
        Tuple of (is_valid, error_messages)
    """
    try:
        import jsonschema
    except ImportError:
        return False, ["jsonschema library not installed. Run: pip install jsonschema>=4.20.0"]

    schema = get_document_extraction_schema()
    errors = []

    try:
        jsonschema.validate(instance=response_data, schema=schema)
        return True, []
    except jsonschema.ValidationError as exc:
        errors.append(f"Validation error: {exc.message} at {'.'.join(str(p) for p in exc.path)}")
        return False, errors
    except jsonschema.SchemaError as exc:
        errors.append(f"Schema error: {exc.message}")
        return False, errors


if __name__ == "__main__":
    import json

    schema = get_document_extraction_schema()
    print(json.dumps(schema, indent=2))
