"""Token calculator for OpenAI Responses API format.

This module provides a high-level calculator for counting tokens in Responses API
requests, which use a different message format than Chat Completions.

Key features:
- Handles Responses API specific roles (system, developer, user, assistant)
- Supports input_text and input_file content types
- Integrates with file estimators for PDF token estimation
- Model-aware overhead calculation
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from .encoding import EncodingResolver
from .exceptions import ConfigurationError, InvalidMessageFormatError
from .models import TokenCount, TokenEstimate, TokenResult
from .primitives import (
    count_message_tokens_responses_api,
    count_tool_definition_tokens,
)


class ResponsesAPICalculator:
    """Calculator for Responses API token counting.

    Example usage:
        calculator = ResponsesAPICalculator()

        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ]

        result = calculator.count_request_tokens(
            model="gpt-5",
            messages=messages
        )

        print(f"Total tokens: {result.count.total}")
    """

    def __init__(
        self,
        encoding_resolver: EncodingResolver | None = None,
        overhead_config_path: str | Path | None = None,
    ):
        """Initialize the calculator.

        Args:
            encoding_resolver: Optional custom EncodingResolver instance
            overhead_config_path: Path to message_overhead.yaml config
        """
        self.encoding_resolver = encoding_resolver or EncodingResolver()

        # Load overhead config
        if overhead_config_path is None:
            config_dir = Path(__file__).parent.parent / "config"
            overhead_config_path = config_dir / "message_overhead.yaml"

        self.overhead_config = self._load_overhead_config(overhead_config_path)

    def _load_overhead_config(self, config_path: Path | str) -> dict[str, Any]:
        """Load overhead configuration from YAML file."""
        config_path = Path(config_path)
        if not config_path.exists():
            raise ConfigurationError(f"Overhead config not found at {config_path}")

        with open(config_path) as f:
            config = yaml.safe_load(f)

        if not config or "defaults" not in config:
            raise ConfigurationError(
                "Invalid overhead config: missing 'defaults' section"
            )

        return config

    def _get_model_family(self, model: str) -> str:
        """Determine model family for overhead lookup.

        Args:
            model: Model name (e.g., "gpt-5", "gpt-4o-mini")

        Returns:
            Model family name (e.g., "gpt-5", "gpt-4o")
        """
        # Check exact match in model_families
        if model in self.overhead_config.get("model_families", {}):
            return model

        # Try pattern matching
        for pattern_def in self.overhead_config.get("pattern_matches", []):
            pattern = pattern_def["pattern"]
            if re.match(pattern, model, re.IGNORECASE):
                return pattern_def["family"]

        # Default to using the encoding family
        encoding_name = self.encoding_resolver.get_encoding_name(model)
        if "o200k" in encoding_name:
            return "gpt-5"  # Modern models
        elif "cl100k" in encoding_name:
            return "gpt-4"  # Legacy GPT-4/3.5

        return "gpt-5"  # Final fallback

    def _get_overhead_params(self, model: str) -> dict[str, Any]:
        """Get overhead parameters for a model.

        Args:
            model: Model name

        Returns:
            Dictionary with tokens_per_message, tokens_per_name, etc.
        """
        family = self._get_model_family(model)
        defaults = self.overhead_config["defaults"]

        # Get family-specific overrides or use defaults
        family_config = self.overhead_config.get("model_families", {}).get(family, {})

        return {
            "tokens_per_message": family_config.get(
                "tokens_per_message", defaults["tokens_per_message"]
            ),
            "tokens_per_name": family_config.get(
                "tokens_per_name", defaults["tokens_per_name"]
            ),
            "reply_priming": family_config.get(
                "reply_priming", defaults["reply_priming"]
            ),
            "tool_overhead": family_config.get("tool_overhead", {}),
        }

    def count_message_tokens(
        self,
        model: str,
        messages: list[dict[str, Any]],
    ) -> int:
        """Count tokens in Responses API messages.

        Args:
            model: Model name (e.g., "gpt-5")
            messages: List of message dictionaries

        Returns:
            Total token count including overhead

        Raises:
            InvalidMessageFormatError: If message format is invalid
        """
        # Validate message format
        self._validate_messages(messages)

        # Get encoding and overhead params
        encoding = self.encoding_resolver.get_encoding(model)
        overhead_params = self._get_overhead_params(model)

        # Count tokens using primitive
        return count_message_tokens_responses_api(
            messages=messages,
            encoding=encoding,
            tokens_per_message=overhead_params["tokens_per_message"],
            tokens_per_name=overhead_params["tokens_per_name"],
        )

    def count_tool_tokens(
        self,
        model: str,
        tools: list[dict[str, Any]],
    ) -> int:
        """Count tokens in tool definitions.

        Args:
            model: Model name
            tools: List of tool definition dictionaries

        Returns:
            Total token count for tool definitions
        """
        if not tools:
            return 0

        # Get encoding and model family
        encoding = self.encoding_resolver.get_encoding(model)
        family = self._get_model_family(model)

        # Count tokens using primitive
        return count_tool_definition_tokens(
            tools=tools,
            encoding=encoding,
            model_family=family,
        )

    def count_request_tokens(
        self,
        model: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        estimate_files: bool = False,
    ) -> TokenResult:
        """Count total tokens for a Responses API request.

        Args:
            model: Model name
            messages: List of message dictionaries
            tools: Optional list of tool definitions
            estimate_files: If True, estimate tokens for input_file content

        Returns:
            TokenResult with detailed breakdown
        """
        # Count message tokens
        message_tokens = self.count_message_tokens(model, messages)

        # Count tool tokens
        tool_tokens = self.count_tool_tokens(model, tools or [])

        # File token estimation (Phase 3 integration point)
        file_tokens = 0
        file_estimate = None
        if estimate_files:
            file_estimate = self._estimate_file_tokens(messages)
            if file_estimate:
                file_tokens = file_estimate.min_tokens  # Conservative estimate

        # Calculate total
        total_tokens = message_tokens + tool_tokens + file_tokens

        # Build result
        count = TokenCount(
            total=total_tokens,
            billable=total_tokens,  # Will be refined with caching in Phase 4
            cached=0,
        )

        return TokenResult(
            model=model,
            encoding=self.encoding_resolver.get_encoding_name(model),
            count=count,
            breakdown={
                "messages": message_tokens,
                "tools": tool_tokens,
                "files": file_tokens,
            },
            file_estimate=file_estimate,
        )

    def _validate_messages(self, messages: list[dict[str, Any]]) -> None:
        """Validate Responses API message format.

        Args:
            messages: List of message dictionaries

        Raises:
            InvalidMessageFormatError: If format is invalid
        """
        if not isinstance(messages, list):
            raise InvalidMessageFormatError("Messages must be a list")

        supported_roles = (
            self.overhead_config.get("api_formats", {})
            .get("responses", {})
            .get("supported_roles", ["system", "developer", "user", "assistant"])
        )

        for i, msg in enumerate(messages):
            if not isinstance(msg, dict):
                raise InvalidMessageFormatError(f"Message {i} must be a dictionary")

            if "role" not in msg:
                raise InvalidMessageFormatError(
                    f"Message {i} missing required 'role' field"
                )

            if msg["role"] not in supported_roles:
                raise InvalidMessageFormatError(
                    f"Message {i} has invalid role '{msg['role']}'. "
                    f"Supported: {supported_roles}"
                )

            if "content" not in msg:
                raise InvalidMessageFormatError(
                    f"Message {i} missing required 'content' field"
                )

    def _estimate_file_tokens(
        self, messages: list[dict[str, Any]]
    ) -> TokenEstimate | None:
        """Estimate tokens from input_file content types.

        This is a placeholder for Phase 3 integration with file estimators.
        Currently returns None.

        Args:
            messages: List of message dictionaries

        Returns:
            TokenEstimate if files found, None otherwise
        """
        # TODO: Integrate with FileTokenEstimator in Phase 3
        # For now, we just detect if files exist
        has_files = False

        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "input_file":
                        has_files = True
                        break

        if not has_files:
            return None

        # Return a conservative estimate placeholder
        return TokenEstimate(
            min_tokens=100,  # Conservative minimum
            max_tokens=10000,  # Conservative maximum
            confidence="low",
            basis="Placeholder estimate - file estimators not yet integrated",
        )
