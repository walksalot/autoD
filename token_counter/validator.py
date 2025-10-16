"""Token count validation against actual API usage.

This module provides tools to validate estimated token counts against
actual usage reported by the OpenAI API, helping verify accuracy and
identify edge cases.

Example usage:
    from token_counter import TokenCounter, TokenValidator
    from openai import OpenAI

    counter = TokenCounter()
    validator = TokenValidator(counter)

    # Make API request and validate
    messages = [{"role": "user", "content": "Hello!"}]

    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4",
        messages=messages
    )

    validation = validator.validate_from_response(
        model="gpt-4",
        messages=messages,
        response=response
    )

    print(f"Estimated: {validation.estimated}")
    print(f"Actual: {validation.actual}")
    print(f"Delta: {validation.delta} ({validation.delta_pct:.1f}%)")
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from .counter import TokenCounter
from .models import ValidationResult


class TokenValidator:
    """Validates token counts against actual API usage.

    Provides tools to compare estimated token counts with actual
    usage reported by OpenAI API responses, helping identify
    accuracy issues and edge cases.
    """

    def __init__(self, counter: TokenCounter | None = None):
        """Initialize the validator.

        Args:
            counter: Optional TokenCounter instance. If None, creates new one.
        """
        self.counter = counter or TokenCounter()

    def validate_from_response(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        response: Any,
        tools: List[Dict[str, Any]] | None = None,
        functions: List[Dict[str, Any]] | None = None,
    ) -> ValidationResult:
        """Validate token count against actual API response.

        Args:
            model: Model name used in request
            messages: Messages sent to API
            response: Response object from OpenAI API
            tools: Tool definitions if used
            functions: Function definitions if used (legacy)

        Returns:
            ValidationResult with comparison details

        Example:
            >>> validator = TokenValidator()
            >>> validation = validator.validate_from_response(
            ...     model="gpt-4",
            ...     messages=messages,
            ...     response=response
            ... )
            >>> print(f"Accuracy: {validation.delta_pct:.1f}%")
        """
        # Estimate tokens
        result = self.counter.count_tokens(
            model=model,
            messages=messages,
            tools=tools,
            functions=functions,
        )

        # Extract actual usage from response
        actual = self._extract_actual_usage(response)

        # Calculate delta
        estimated = result.count.total
        delta = estimated - actual["prompt_tokens"]
        delta_pct = (
            (delta / actual["prompt_tokens"] * 100)
            if actual["prompt_tokens"] > 0
            else 0
        )

        return ValidationResult(
            model=model,
            estimated=estimated,
            actual=actual["prompt_tokens"],
            delta=delta,
            delta_pct=delta_pct,
            cached_tokens=actual.get("cached_tokens", 0),
            timestamp=datetime.now().isoformat(),
        )

    def validate_from_usage_dict(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        usage: Dict[str, int],
        tools: List[Dict[str, Any]] | None = None,
    ) -> ValidationResult:
        """Validate against usage dictionary directly.

        Useful when you already have the usage stats but not the full response.

        Args:
            model: Model name
            messages: Messages sent to API
            usage: Usage dictionary with prompt_tokens, completion_tokens, etc.
            tools: Tool definitions if used

        Returns:
            ValidationResult with comparison details
        """
        # Estimate tokens
        result = self.counter.count_tokens(
            model=model,
            messages=messages,
            tools=tools,
        )

        estimated = result.count.total
        actual = usage.get("prompt_tokens", 0)
        delta = estimated - actual
        delta_pct = (delta / actual * 100) if actual > 0 else 0

        return ValidationResult(
            model=model,
            estimated=estimated,
            actual=actual,
            delta=delta,
            delta_pct=delta_pct,
            cached_tokens=usage.get("cached_tokens", 0),
            timestamp=datetime.now().isoformat(),
        )

    def check_accuracy(
        self,
        validation: ValidationResult,
        tolerance_pct: float = 10.0,
    ) -> bool:
        """Check if validation result is within acceptable tolerance.

        Args:
            validation: ValidationResult to check
            tolerance_pct: Acceptable error percentage (default: 10%)

        Returns:
            True if within tolerance, False otherwise

        Example:
            >>> validation = validator.validate_from_response(...)
            >>> is_accurate = validator.check_accuracy(validation, tolerance_pct=5.0)
        """
        return abs(validation.delta_pct) <= tolerance_pct

    def _extract_actual_usage(self, response: Any) -> Dict[str, int]:
        """Extract usage statistics from API response.

        Handles both Chat Completions and Responses API formats.

        Args:
            response: Response object from OpenAI API

        Returns:
            Dictionary with prompt_tokens, completion_tokens, etc.
        """
        # Try to get usage object
        usage = getattr(response, "usage", None)

        if usage is None:
            # Fallback: try dictionary access
            if isinstance(response, dict):
                usage = response.get("usage")
                if usage is None:
                    raise ValueError(
                        "Could not extract usage from response. "
                        "Response must have a 'usage' attribute or key."
                    )
            else:
                raise ValueError(
                    "Could not extract usage from response. "
                    "Response must have a 'usage' attribute or key."
                )

        # Extract tokens
        if hasattr(usage, "prompt_tokens"):
            # Object with attributes
            return {
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": getattr(usage, "completion_tokens", 0),
                "total_tokens": getattr(usage, "total_tokens", 0),
                "cached_tokens": (
                    getattr(usage, "prompt_tokens_details", {}).get("cached_tokens", 0)
                    if hasattr(usage, "prompt_tokens_details")
                    else 0
                ),
            }
        else:
            # Dictionary
            return {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
                "cached_tokens": usage.get("prompt_tokens_details", {}).get(
                    "cached_tokens", 0
                ),
            }

    def batch_validate(
        self,
        validations: List[ValidationResult],
    ) -> Dict[str, Any]:
        """Analyze multiple validation results.

        Provides aggregate statistics across multiple validations.

        Args:
            validations: List of ValidationResult objects

        Returns:
            Dictionary with aggregate statistics

        Example:
            >>> results = []
            >>> for model, messages, response in test_cases:
            ...     result = validator.validate_from_response(model, messages, response)
            ...     results.append(result)
            >>> stats = validator.batch_validate(results)
            >>> print(f"Average error: {stats['avg_delta_pct']:.1f}%")
        """
        if not validations:
            return {
                "count": 0,
                "avg_delta": 0,
                "avg_delta_pct": 0,
                "max_delta_pct": 0,
                "min_delta_pct": 0,
                "within_10pct": 0,
            }

        deltas = [v.delta for v in validations]
        delta_pcts = [v.delta_pct for v in validations]
        within_10pct = sum(1 for v in validations if abs(v.delta_pct) <= 10.0)

        return {
            "count": len(validations),
            "avg_delta": sum(deltas) / len(deltas),
            "avg_delta_pct": sum(delta_pcts) / len(delta_pcts),
            "max_delta_pct": max(delta_pcts),
            "min_delta_pct": min(delta_pcts),
            "within_10pct": within_10pct,
            "within_10pct_pct": (within_10pct / len(validations)) * 100,
        }
