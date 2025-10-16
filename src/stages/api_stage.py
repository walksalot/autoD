"""
Responses API stage.

Builds the structured-output payload, optionally enriches the prompt with
vector-store context, calls OpenAI Responses API through the resilient
ResponsesAPIClient wrapper, and stores the parsed metadata + usage stats.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import List, Optional

from src.api_client import ResponsesAPIClient
from src.pipeline import ProcessingContext, ProcessingStage
from src.prompts import build_responses_api_payload
from src.vector_store import VectorStoreManager

logger = logging.getLogger(__name__)


def _format_vector_context(matches: List[dict]) -> Optional[str]:
    """Format vector-search hits into a short prompt-friendly block."""
    if not matches:
        return None

    lines = ["Similar documents previously processed:"]
    for match in matches[:5]:
        filename = (
            match.get("filename") or match.get("original_file_name") or "unknown.pdf"
        )
        score = match.get("score")
        reason = match.get("rationale") or match.get("summary") or ""
        score_text = f"{score:.2f}" if isinstance(score, (int, float)) else "n/a"
        lines.append(f"- {filename} (score {score_text}) {reason}".strip())
    return "\n".join(lines)


class CallResponsesAPIStage(ProcessingStage):
    """
    Call OpenAI Responses API and parse the structured output.

    Inputs (from context):
        pdf_path, file_id, sha256_hex, processed_at, source_file_id

    Outputs:
        context.metadata_json      -> Parsed structured output
        context.api_response       -> Raw API response dictionary
        context.response_usage     -> Token usage dict
        context.vector_store_id    -> Vector store id (if manager provided)
        context.vector_search_results -> Similarity hits (if any)
    """

    def __init__(
        self,
        api_client: ResponsesAPIClient,
        vector_manager: Optional[VectorStoreManager] = None,
    ) -> None:
        self.api_client = api_client
        self.vector_manager = vector_manager

    def execute(self, context: ProcessingContext) -> ProcessingContext:
        if not context.file_id:
            raise ValueError("file_id not set - UploadToFilesAPIStage must run first")

        # Ensure processed_at + source_file_id are populated
        processed_at = context.processed_at or datetime.now(timezone.utc).isoformat(
            timespec="seconds"
        )
        context.processed_at = processed_at
        context.source_file_id = context.source_file_id or context.file_id

        vector_store_ids: Optional[List[str]] = None
        vector_context_text: Optional[str] = None

        if self.vector_manager:
            try:
                vector_store = self.vector_manager.get_or_create_vector_store()
                vector_store_id = getattr(vector_store, "id", vector_store)
                context.vector_store_id = vector_store_id
                vector_store_ids = [vector_store_id] if vector_store_id else None

                if context.sha256_hex:
                    matches = self.vector_manager.search_similar_documents(
                        query=context.sha256_hex,
                        top_k=3,
                    )
                else:
                    matches = []

                context.vector_search_results = matches
                vector_context_text = _format_vector_context(matches)
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.warning(
                    "Vector store enrichment failed: %s",
                    exc,
                    extra={"pdf_path": str(context.pdf_path)},
                )

        payload = build_responses_api_payload(
            filename=context.pdf_path.name,
            file_id=context.file_id,
            processed_at=processed_at,
            original_file_name=context.pdf_path.name,
            source_file_id=context.source_file_id,
            vector_store_ids=vector_store_ids,
            vector_context=vector_context_text,
            similar_documents_found=bool(vector_context_text),
            page_count=context.metrics.get("page_count"),
        )

        logger.info(
            "Calling Responses API",
            extra={
                "pdf_path": str(context.pdf_path),
                "model": payload.get("model"),
                "vector_store_ids": vector_store_ids,
            },
        )

        response_dict = self.api_client.create_response(payload)
        context.api_response = response_dict

        output_text = self.api_client.extract_output_text(response_dict)
        try:
            metadata = json.loads(output_text)
        except json.JSONDecodeError as exc:
            logger.error(
                "Responses API returned invalid JSON: %s",
                exc,
                extra={
                    "pdf_path": str(context.pdf_path),
                    "raw_text": output_text[:200],
                },
            )
            raise

        context.metadata_json = metadata

        usage = self.api_client.extract_usage(response_dict)
        context.response_usage = usage
        context.metrics["usage"] = usage

        logger.info(
            "Responses API call successful",
            extra={
                "pdf_path": str(context.pdf_path),
                "doc_type": metadata.get("doc_type"),
                "tokens_prompt": usage.get("prompt_tokens"),
                "tokens_output": usage.get("completion_tokens"),
            },
        )

        return context
