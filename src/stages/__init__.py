"""
Processing stages for PDF pipeline.

This package contains discrete processing stages that are composed
into a pipeline. Each stage performs a single operation:

- sha256_stage: Compute SHA-256 hash of PDF file
- dedupe_stage: Check database for duplicate documents
- upload_stage: Upload PDF to OpenAI Files API
- api_stage: Call OpenAI Responses API for metadata extraction
- persist_stage: Save document record to database

Usage:
    from src.stages.sha256_stage import ComputeSHA256Stage
    from src.stages.dedupe_stage import DedupeCheckStage
    from src.stages.upload_stage import UploadToFilesAPIStage
    from src.stages.api_stage import CallResponsesAPIStage
    from src.stages.persist_stage import PersistToDBStage

    # Compose into pipeline
    from src.pipeline import Pipeline

    pipeline = Pipeline([
        ComputeSHA256Stage(),
        DedupeCheckStage(session),
        UploadToFilesAPIStage(client),
        CallResponsesAPIStage(client),
        PersistToDBStage(session),
    ])
"""

from typing import Any

__all__ = [
    "ComputeSHA256Stage",
    "DedupeCheckStage",
    "UploadToFilesAPIStage",
    "CallResponsesAPIStage",
    "PersistToDBStage",
]


# Lazy imports to avoid circular dependencies
def __getattr__(name: str) -> Any:
    if name == "ComputeSHA256Stage":
        from src.stages.sha256_stage import ComputeSHA256Stage

        return ComputeSHA256Stage
    elif name == "DedupeCheckStage":
        from src.stages.dedupe_stage import DedupeCheckStage

        return DedupeCheckStage
    elif name == "UploadToFilesAPIStage":
        from src.stages.upload_stage import UploadToFilesAPIStage

        return UploadToFilesAPIStage
    elif name == "CallResponsesAPIStage":
        from src.stages.api_stage import CallResponsesAPIStage

        return CallResponsesAPIStage
    elif name == "PersistToDBStage":
        from src.stages.persist_stage import PersistToDBStage

        return PersistToDBStage
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
