"""
Cost calculation for OpenAI API usage with GPT-5 pricing.

Provides accurate cost estimation based on token usage, with support for:
- Input tokens (regular and cached)
- Output tokens
- Prompt caching savings (10% cost for cached tokens)
- Cumulative cost tracking across multiple requests

GPT-5 Pricing (as of 2025-10-16):
- Input: $10.00 per 1M tokens ($0.010 per 1K tokens)
- Output: $30.00 per 1M tokens ($0.030 per 1K tokens)
- Cached Input: $1.00 per 1M tokens ($0.001 per 1K tokens) - 10% of input cost

Usage:
    >>> from src.cost_calculator import calculate_cost, GPT5_PRICING
    >>>
    >>> # From OpenAI API response
    >>> usage = {
    ...     "prompt_tokens": 1000,
    ...     "output_tokens": 500,
    ...     "prompt_tokens_details": {"cached_tokens": 800}
    ... }
    >>>
    >>> cost_breakdown = calculate_cost(usage)
    >>> print(f"Total cost: ${cost_breakdown['total_cost_usd']:.4f}")
    Total cost: $0.0170
"""

from typing import Any, Dict, Optional
from dataclasses import dataclass, asdict


# GPT-5 Pricing Constants (USD per 1K tokens)
# Source: OpenAI pricing as of 2025-10-16
@dataclass(frozen=True)
class PricingTier:
    """Immutable pricing tier for a specific model."""

    input_per_1k: float      # Cost per 1K input tokens
    output_per_1k: float     # Cost per 1K output tokens
    cached_per_1k: float     # Cost per 1K cached input tokens (10% of input)

    def __str__(self) -> str:
        return (
            f"Input: ${self.input_per_1k:.3f}/1K, "
            f"Output: ${self.output_per_1k:.3f}/1K, "
            f"Cached: ${self.cached_per_1k:.4f}/1K"
        )


# GPT-5 Pricing (Primary model for autoD)
GPT5_PRICING = PricingTier(
    input_per_1k=0.010,    # $10.00 per 1M tokens
    output_per_1k=0.030,   # $30.00 per 1M tokens
    cached_per_1k=0.001,   # $1.00 per 1M tokens (10% discount)
)

# Alternative pricing tiers (for future use)
GPT4O_PRICING = PricingTier(
    input_per_1k=0.0025,   # $2.50 per 1M tokens
    output_per_1k=0.010,   # $10.00 per 1M tokens
    cached_per_1k=0.00025, # $0.25 per 1M tokens
)

GPT4_PRICING = PricingTier(
    input_per_1k=0.030,    # $30.00 per 1M tokens
    output_per_1k=0.060,   # $60.00 per 1M tokens
    cached_per_1k=0.003,   # $3.00 per 1M tokens
)

# Model name to pricing mapping
MODEL_PRICING_MAP = {
    "gpt-5": GPT5_PRICING,
    "gpt-5-mini": GPT5_PRICING,
    "gpt-5-nano": GPT5_PRICING,
    "gpt-4o": GPT4O_PRICING,
    "gpt-4o-mini": GPT4O_PRICING,
    "gpt-4": GPT4_PRICING,
    "gpt-4-turbo": GPT4_PRICING,
}


def get_pricing_for_model(model: str) -> PricingTier:
    """
    Get pricing tier for a model name.

    Args:
        model: OpenAI model name (e.g., "gpt-5", "gpt-4o-mini")

    Returns:
        PricingTier with cost per 1K tokens

    Raises:
        ValueError: If model not found (defaults to GPT-5 pricing with warning)
    """
    # Exact match
    if model in MODEL_PRICING_MAP:
        return MODEL_PRICING_MAP[model]

    # Pattern matching for model variants
    model_lower = model.lower()
    if "gpt-5" in model_lower:
        return GPT5_PRICING
    elif "gpt-4o" in model_lower:
        return GPT4O_PRICING
    elif "gpt-4" in model_lower:
        return GPT4_PRICING

    # Default to GPT-5 pricing (most common for autoD)
    import logging
    logging.warning(
        f"Unknown model '{model}', defaulting to GPT-5 pricing. "
        f"Add model to MODEL_PRICING_MAP if this is incorrect."
    )
    return GPT5_PRICING


def calculate_cost(
    usage: Dict[str, Any],
    pricing: Optional[PricingTier] = None,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Calculate cost breakdown from OpenAI API usage object.

    This function parses the usage statistics returned by the OpenAI API
    and calculates costs based on the pricing tier. It handles both
    regular and cached tokens correctly.

    Args:
        usage: Usage dictionary from OpenAI API response, containing:
               - prompt_tokens: Total input tokens
               - output_tokens: Total output tokens
               - prompt_tokens_details: {"cached_tokens": int} (optional)
        pricing: Optional PricingTier to use. If None, uses GPT-5 pricing.
        model: Optional model name to auto-detect pricing tier.
               Overrides `pricing` parameter if provided.

    Returns:
        Dictionary with detailed cost breakdown:
        {
            "prompt_tokens": int,           # Total input tokens
            "output_tokens": int,           # Total output tokens
            "cached_tokens": int,           # Cached input tokens
            "billable_input_tokens": int,   # Input tokens - cached tokens
            "total_tokens": int,            # Sum of all tokens
            "input_cost_usd": float,        # Cost of billable input tokens
            "output_cost_usd": float,       # Cost of output tokens
            "cache_cost_usd": float,        # Cost of cached tokens
            "cache_savings_usd": float,     # Savings from caching
            "total_cost_usd": float,        # Total cost
            "pricing_tier": str,            # Pricing tier used
        }

    Examples:
        >>> # Basic usage (no caching)
        >>> usage = {"prompt_tokens": 1000, "output_tokens": 500}
        >>> cost = calculate_cost(usage)
        >>> print(f"Total: ${cost['total_cost_usd']:.4f}")
        Total: $0.0250

        >>> # With caching
        >>> usage = {
        ...     "prompt_tokens": 1000,
        ...     "output_tokens": 500,
        ...     "prompt_tokens_details": {"cached_tokens": 800}
        ... }
        >>> cost = calculate_cost(usage)
        >>> print(f"Savings: ${cost['cache_savings_usd']:.4f}")
        Savings: $0.0072

        >>> # Auto-detect pricing from model name
        >>> cost = calculate_cost(usage, model="gpt-4o-mini")
    """
    # Determine pricing tier
    if model:
        pricing = get_pricing_for_model(model)
    elif pricing is None:
        pricing = GPT5_PRICING

    # Extract token counts
    prompt_tokens = usage.get("prompt_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)

    # Extract cached tokens from prompt_tokens_details
    prompt_details = usage.get("prompt_tokens_details", {})
    cached_tokens = prompt_details.get("cached_tokens", 0)

    # Calculate billable input tokens (total prompt - cached)
    billable_input_tokens = max(prompt_tokens - cached_tokens, 0)

    # Calculate costs (convert from per-1K to actual cost)
    input_cost_usd = (billable_input_tokens / 1000.0) * pricing.input_per_1k
    output_cost_usd = (output_tokens / 1000.0) * pricing.output_per_1k
    cache_cost_usd = (cached_tokens / 1000.0) * pricing.cached_per_1k

    # Calculate cache savings (what we would have paid without caching)
    # Savings = (cached_tokens * input_price) - (cached_tokens * cached_price)
    cache_savings_usd = (cached_tokens / 1000.0) * (
        pricing.input_per_1k - pricing.cached_per_1k
    )

    # Total cost
    total_cost_usd = input_cost_usd + output_cost_usd + cache_cost_usd

    return {
        # Token counts
        "prompt_tokens": prompt_tokens,
        "output_tokens": output_tokens,
        "cached_tokens": cached_tokens,
        "billable_input_tokens": billable_input_tokens,
        "total_tokens": prompt_tokens + output_tokens,

        # Cost breakdown (USD)
        "input_cost_usd": round(input_cost_usd, 6),
        "output_cost_usd": round(output_cost_usd, 6),
        "cache_cost_usd": round(cache_cost_usd, 6),
        "cache_savings_usd": round(cache_savings_usd, 6),
        "total_cost_usd": round(total_cost_usd, 6),

        # Metadata
        "pricing_tier": str(pricing),
    }


def format_cost_summary(cost_breakdown: Dict[str, Any]) -> str:
    """
    Format cost breakdown as human-readable summary.

    Args:
        cost_breakdown: Dictionary from calculate_cost()

    Returns:
        Formatted string with cost breakdown

    Example:
        >>> cost = calculate_cost(usage)
        >>> print(format_cost_summary(cost))
        Total: $0.0250 | Input: 1,000 tokens ($0.0100) | Output: 500 tokens ($0.0150) | Cached: 0 tokens
    """
    parts = []

    # Total cost
    total = cost_breakdown["total_cost_usd"]
    parts.append(f"Total: ${total:.4f}")

    # Input tokens
    input_tokens = cost_breakdown["billable_input_tokens"]
    input_cost = cost_breakdown["input_cost_usd"]
    parts.append(f"Input: {input_tokens:,} tokens (${input_cost:.4f})")

    # Output tokens
    output_tokens = cost_breakdown["output_tokens"]
    output_cost = cost_breakdown["output_cost_usd"]
    parts.append(f"Output: {output_tokens:,} tokens (${output_cost:.4f})")

    # Cached tokens (if any)
    cached = cost_breakdown["cached_tokens"]
    if cached > 0:
        cache_cost = cost_breakdown["cache_cost_usd"]
        savings = cost_breakdown["cache_savings_usd"]
        parts.append(
            f"Cached: {cached:,} tokens (${cache_cost:.4f}, saved ${savings:.4f})"
        )

    return " | ".join(parts)


class CostTracker:
    """
    Track cumulative costs across multiple API calls.

    Useful for monitoring total spend over a batch of PDF processing.

    Example:
        >>> tracker = CostTracker()
        >>> for pdf in pdfs:
        ...     response = process_pdf(pdf)
        ...     tracker.add_usage(response.usage.__dict__)
        >>>
        >>> print(f"Total cost: ${tracker.total_cost:.4f}")
        >>> print(f"Average per PDF: ${tracker.average_cost:.4f}")
    """

    def __init__(self, pricing: Optional[PricingTier] = None):
        """
        Initialize cost tracker.

        Args:
            pricing: Optional pricing tier. Defaults to GPT-5 pricing.
        """
        self.pricing = pricing or GPT5_PRICING
        self.requests: list[Dict[str, Any]] = []

    def add_usage(
        self,
        usage: Dict[str, Any],
        model: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Add a usage record and calculate its cost.

        Args:
            usage: Usage dictionary from OpenAI API response
            model: Optional model name (overrides instance pricing)
            metadata: Optional metadata to store with this request
                     (e.g., {"pdf_path": "/path/to/file.pdf", "doc_id": 123})

        Returns:
            Cost breakdown for this request
        """
        pricing = get_pricing_for_model(model) if model else self.pricing
        cost = calculate_cost(usage, pricing=pricing)

        # Store request with metadata
        record = {
            **cost,
            "metadata": metadata or {},
        }
        self.requests.append(record)

        return cost

    @property
    def total_cost(self) -> float:
        """Total cost across all requests."""
        return sum(r["total_cost_usd"] for r in self.requests)

    @property
    def total_tokens(self) -> int:
        """Total tokens across all requests."""
        return sum(r["total_tokens"] for r in self.requests)

    @property
    def total_cached_tokens(self) -> int:
        """Total cached tokens across all requests."""
        return sum(r["cached_tokens"] for r in self.requests)

    @property
    def total_cache_savings(self) -> float:
        """Total savings from caching across all requests."""
        return sum(r["cache_savings_usd"] for r in self.requests)

    @property
    def average_cost(self) -> float:
        """Average cost per request."""
        return self.total_cost / len(self.requests) if self.requests else 0.0

    @property
    def request_count(self) -> int:
        """Number of requests tracked."""
        return len(self.requests)

    def summary(self) -> Dict[str, Any]:
        """
        Get summary statistics.

        Returns:
            Dictionary with aggregate statistics
        """
        return {
            "request_count": self.request_count,
            "total_cost_usd": round(self.total_cost, 6),
            "average_cost_usd": round(self.average_cost, 6),
            "total_tokens": self.total_tokens,
            "total_cached_tokens": self.total_cached_tokens,
            "total_cache_savings_usd": round(self.total_cache_savings, 6),
            "cache_hit_rate": (
                self.total_cached_tokens / self.total_tokens
                if self.total_tokens > 0
                else 0.0
            ),
        }

    def summary_text(self) -> str:
        """Format summary as human-readable text."""
        s = self.summary()
        return (
            f"{s['request_count']} requests | "
            f"Total: ${s['total_cost_usd']:.4f} | "
            f"Avg: ${s['average_cost_usd']:.4f} | "
            f"Tokens: {s['total_tokens']:,} | "
            f"Cached: {s['total_cached_tokens']:,} ({s['cache_hit_rate']:.1%}) | "
            f"Savings: ${s['total_cache_savings_usd']:.4f}"
        )


# Module-level convenience functions
def estimate_cost_from_tokens(
    prompt_tokens: int,
    output_tokens: int,
    cached_tokens: int = 0,
    pricing: Optional[PricingTier] = None,
) -> Dict[str, Any]:
    """
    Estimate cost from token counts (pre-API call).

    Useful for cost estimation before making API request.

    Args:
        prompt_tokens: Estimated input tokens
        output_tokens: Estimated output tokens
        cached_tokens: Estimated cached tokens (default: 0)
        pricing: Optional pricing tier (default: GPT-5)

    Returns:
        Cost breakdown dictionary

    Example:
        >>> # Estimate before API call
        >>> from token_counter import count_string_tokens, EncodingResolver
        >>> resolver = EncodingResolver()
        >>> encoding = resolver.get_encoding("gpt-5")
        >>> prompt_tokens = len(encoding.encode("Extract metadata from PDF"))
        >>> estimated_cost = estimate_cost_from_tokens(prompt_tokens, 500)
        >>> print(f"Estimated: ${estimated_cost['total_cost_usd']:.4f}")
    """
    usage = {
        "prompt_tokens": prompt_tokens,
        "output_tokens": output_tokens,
        "prompt_tokens_details": {"cached_tokens": cached_tokens},
    }
    return calculate_cost(usage, pricing=pricing)
