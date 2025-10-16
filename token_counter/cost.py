"""Cost calculation for OpenAI API token usage.

This module provides cost estimation based on model-specific pricing data.
Supports both exact model matching and pattern-based fallbacks for new models.

Example usage:
    from token_counter import CostCalculator

    calculator = CostCalculator()

    # Calculate cost for a request
    cost = calculator.calculate_cost(
        model="gpt-5",
        input_tokens=1000,
        output_tokens=500,
        cached_tokens=200
    )

    print(f"Total cost: ${cost.total_usd:.6f}")
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict

import yaml

from .exceptions import ConfigurationError
from .models import CostEstimate


class CostCalculator:
    """Calculator for API token costs.

    Loads pricing data from config/pricing.yaml and provides cost
    estimation for input, output, and cached tokens.

    Pricing resolution:
    1. Exact model match (e.g., "gpt-5")
    2. Pattern match (e.g., "^gpt-5.*")
    3. Default pricing
    """

    def __init__(self, pricing_config_path: str | Path | None = None):
        """Initialize the cost calculator.

        Args:
            pricing_config_path: Optional path to pricing.yaml config.
                If None, uses default path (config/pricing.yaml).
        """
        if pricing_config_path is None:
            config_dir = Path(__file__).parent.parent / "config"
            pricing_config_path = config_dir / "pricing.yaml"

        self.pricing_config = self._load_pricing_config(pricing_config_path)

    def _load_pricing_config(self, config_path: Path | str) -> Dict[str, Any]:
        """Load pricing configuration from YAML file.

        Args:
            config_path: Path to pricing.yaml

        Returns:
            Parsed pricing configuration

        Raises:
            ConfigurationError: If config file not found or invalid
        """
        config_path = Path(config_path)
        if not config_path.exists():
            raise ConfigurationError(f"Pricing config not found at {config_path}")

        with open(config_path) as f:
            config = yaml.safe_load(f)

        if not config or "defaults" not in config:
            raise ConfigurationError(
                "Invalid pricing config: missing 'defaults' section"
            )

        return config

    def get_model_pricing(self, model: str) -> Dict[str, float]:
        """Get pricing for a specific model.

        Resolution order:
        1. Exact match in models section
        2. Pattern match in pattern_matches section
        3. Default pricing

        Args:
            model: Model name (e.g., "gpt-5", "gpt-4o-mini")

        Returns:
            Dictionary with input_per_million, output_per_million, cached_input_per_million
        """
        # Try exact match
        models = self.pricing_config.get("models", {})
        if model in models:
            model_config = models[model]
            return {
                "input_per_million": model_config["input_per_million"],
                "output_per_million": model_config["output_per_million"],
                "cached_input_per_million": model_config.get(
                    "cached_input_per_million",
                    model_config["input_per_million"]
                    * self.pricing_config["defaults"]["cached_discount_factor"],
                ),
            }

        # Try pattern matching
        for pattern_def in self.pricing_config.get("pattern_matches", []):
            pattern = pattern_def["pattern"]
            if re.match(pattern, model, re.IGNORECASE):
                return {
                    "input_per_million": pattern_def["input_per_million"],
                    "output_per_million": pattern_def["output_per_million"],
                    "cached_input_per_million": pattern_def.get(
                        "cached_input_per_million",
                        pattern_def["input_per_million"]
                        * self.pricing_config["defaults"]["cached_discount_factor"],
                    ),
                }

        # Use defaults
        defaults = self.pricing_config["defaults"]
        return {
            "input_per_million": defaults["input_per_million"],
            "output_per_million": defaults["output_per_million"],
            "cached_input_per_million": defaults["cached_input_per_million"],
        }

    def calculate_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cached_tokens: int = 0,
    ) -> CostEstimate:
        """Calculate cost for a request.

        Args:
            model: Model name
            input_tokens: Number of input tokens (excluding cached)
            output_tokens: Number of output tokens
            cached_tokens: Number of cached input tokens

        Returns:
            CostEstimate with detailed cost breakdown

        Example:
            >>> calculator = CostCalculator()
            >>> cost = calculator.calculate_cost(
            ...     model="gpt-5",
            ...     input_tokens=1000,
            ...     output_tokens=500,
            ...     cached_tokens=200
            ... )
            >>> print(f"${cost.total_usd:.6f}")
            $0.007750
        """
        pricing = self.get_model_pricing(model)

        # Calculate costs per token type
        input_cost = (input_tokens / 1_000_000) * pricing["input_per_million"]
        output_cost = (output_tokens / 1_000_000) * pricing["output_per_million"]
        cached_cost = (cached_tokens / 1_000_000) * pricing["cached_input_per_million"]

        total_cost = input_cost + output_cost + cached_cost

        return CostEstimate(
            input_usd=input_cost,
            output_usd=output_cost,
            cached_input_usd=cached_cost,
            total_usd=total_cost,
        )

    def calculate_cost_for_token_count(
        self,
        model: str,
        token_count: TokenCount,
    ) -> CostEstimate:
        """Calculate cost from a TokenCount object.

        Args:
            model: Model name
            token_count: TokenCount with total, billable, and cached

        Returns:
            CostEstimate

        Note:
            This assumes all billable tokens are input tokens.
            For requests with output tokens, use calculate_cost() directly
            with explicit input/output breakdown.
        """

        return self.calculate_cost(
            model=model,
            input_tokens=token_count.billable,
            output_tokens=0,  # Assume input-only for token count
            cached_tokens=token_count.cached,
        )

    def estimate_response_cost(
        self,
        model: str,
        input_tokens: int,
        estimated_output_tokens: int,
        cached_tokens: int = 0,
    ) -> CostEstimate:
        """Estimate total cost including output tokens.

        Useful for pre-request cost estimation when you know approximate
        response length.

        Args:
            model: Model name
            input_tokens: Number of input tokens
            estimated_output_tokens: Estimated output tokens
            cached_tokens: Number of cached tokens

        Returns:
            CostEstimate for complete request+response
        """
        return self.calculate_cost(
            model=model,
            input_tokens=input_tokens,
            output_tokens=estimated_output_tokens,
            cached_tokens=cached_tokens,
        )

    def get_cost_per_token(self, model: str) -> Dict[str, float]:
        """Get cost per individual token for a model.

        Args:
            model: Model name

        Returns:
            Dictionary with input_cost, output_cost, cached_cost (per token)

        Example:
            >>> calculator = CostCalculator()
            >>> costs = calculator.get_cost_per_token("gpt-5")
            >>> print(f"Input: ${costs['input_cost']:.8f} per token")
            Input: $0.00000250 per token
        """
        pricing = self.get_model_pricing(model)

        return {
            "input_cost": pricing["input_per_million"] / 1_000_000,
            "output_cost": pricing["output_per_million"] / 1_000_000,
            "cached_cost": pricing["cached_input_per_million"] / 1_000_000,
        }
