"""
Central definition of model identifiers approved for Paper Autopilot agents.

Keeping model IDs in one place makes it harder for contributors or external
agents to accidentally downgrade us to legacy models like GPT-4. Any change
here should be coordinated with the platform team.
"""

from __future__ import annotations

from typing import Iterable

# Increment when the policy changes so orchestration layers can confirm agents
# are reading the latest guidance.
MODEL_POLICY_VERSION = "2024-09-23"

# Primary/secondary multimodal models we rely on today.
PRIMARY_MODEL = "gpt-5"
FALLBACK_MODELS = ("gpt-5-mini",)

# Allow-list of all model identifiers agents may use without escalation.
APPROVED_MODEL_IDS = (PRIMARY_MODEL, *FALLBACK_MODELS, "claude-4.5-sonnet")

# Deprecated/blocked identifiers that should never surface in code.
DEPRECATED_MODEL_IDS = (
    "gpt-4",
    "gpt-4.1",
    "gpt-4.1-mini",
    "gpt-3.5-turbo",
    "claude-3.5-sonnet",
    "claude-3-opus",
)


class ModelPolicyError(RuntimeError):
    """Raised when an attempt is made to use a non-approved model."""


def is_model_allowed(model_id: str) -> bool:
    """Return True if the provided model ID conforms to the allow-list."""
    return model_id in APPROVED_MODEL_IDS


def ensure_model_allowed(model_id: str, *, source: str | None = None) -> None:
    """
    Raise ModelPolicyError if a disallowed model is supplied.

    Parameters
    ----------
    model_id:
        The model identifier being requested.
    source:
        Optional context (module/function) to include in the error message.
    """
    if model_id in APPROVED_MODEL_IDS:
        return

    context = f" in {source}" if source else ""
    if model_id in DEPRECATED_MODEL_IDS:
        raise ModelPolicyError(
            f"Model policy violation{context}: '{model_id}' is deprecated. "
            "Consult docs/model_policy.md before changing models."
        )

    raise ModelPolicyError(
        f"Model policy violation{context}: '{model_id}' is not in the approved allow-list "
        f"{APPROVED_MODEL_IDS}. Update docs/model_policy.md and this file if you intend to "
        "onboard a new model."
    )


def assert_only_allowed_models(models: Iterable[str]) -> None:
    """
    Convenience helper for tests/scripts to ensure every model in a collection
    is approved.
    """
    for model in models:
        ensure_model_allowed(model)
