from __future__ import annotations

from pathlib import Path

import pytest

from config.models import (
    APPROVED_MODEL_IDS,
    DEPRECATED_MODEL_IDS,
    PRIMARY_MODEL,
    ModelPolicyError,
    ensure_model_allowed,
)


def test_primary_model_is_current():
    assert PRIMARY_MODEL == "gpt-5"
    assert "gpt-5" in APPROVED_MODEL_IDS
    assert "gpt-5-mini" in APPROVED_MODEL_IDS
    assert "claude-4.5-sonnet" in APPROVED_MODEL_IDS


@pytest.mark.parametrize("model_id", DEPRECATED_MODEL_IDS)
def test_deprecated_models_raise(model_id: str):
    with pytest.raises(ModelPolicyError):
        ensure_model_allowed(model_id)


def test_python_sources_do_not_reference_deprecated_models():
    repo_root = Path(__file__).resolve().parents[1]
    banned = set(DEPRECATED_MODEL_IDS)
    allowed = {
        Path("config/models.py"),  # central allow/deny list
        Path("src/config.py"),     # config module validates and rejects deprecated models
        Path("src/token_counter.py"),  # token counter needs to support all models for accurate counting
    }
    # Token counter module needs to support all models for accurate counting
    allowed_prefixes = (
        Path("token_counter"),
        Path("tests/unit/test_encoding.py"),
        Path("tests/unit/test_primitives.py"),
        Path("tests/unit/test_config.py"),  # Config tests may reference models in test data
        Path("tests/unit/test_cost_calculator.py"),  # Cost calculator tests need all models for pricing tests
        Path("tests/integration"),
        Path("examples"),  # Example code may reference models for demonstration
    )

    for path in repo_root.rglob("*.py"):
        rel_path = path.relative_to(repo_root)
        if rel_path in allowed:
            continue

        # Skip virtual environments and build artifacts
        if any(part in {".venv", "venv", "env", ".tox", "build", "dist", ".eggs"}
               for part in rel_path.parts):
            continue

        # Skip token_counter module and its tests - they need to support all models
        if any(rel_path.is_relative_to(prefix) for prefix in allowed_prefixes):
            continue

        text = path.read_text(encoding="utf-8")
        for model in banned:
            assert model not in text, f"{model} found in {rel_path}"
