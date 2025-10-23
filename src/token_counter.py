"""
Token counting and cost estimation using tiktoken.
Provides preflight cost estimates and actual usage tracking.
"""

import tiktoken
from typing import Dict, Any, Optional

from src.config import get_config


def get_encoding_for_model(model: str) -> tiktoken.Encoding:
    """
    Get tiktoken encoding for a model.

    Args:
        model: Model name (e.g., "gpt-5-mini", "gpt-5")

    Returns:
        tiktoken.Encoding instance

    Note:
        GPT-5 series uses o200k_base encoding
    """
    # GPT-5 models use o200k_base encoding
    if model.startswith("gpt-5"):
        return tiktoken.get_encoding("o200k_base")
    else:
        # Fallback to cl100k_base for older models
        return tiktoken.get_encoding("cl100k_base")


def estimate_tokens(text: str, model: str = "gpt-5-mini") -> int:
    """
    Estimate token count for text.

    Args:
        text: Input text
        model: Model name for encoding selection

    Returns:
        Estimated token count

    Example:
        >>> estimate_tokens("Hello, world!", "gpt-5-mini")
        4
    """
    encoding = get_encoding_for_model(model)
    tokens = encoding.encode(text)
    return len(tokens)


def estimate_prompt_tokens(
    system_prompt: str,
    developer_prompt: str,
    user_prompt: str,
    model: str = "gpt-5-mini",
) -> Dict[str, int]:
    """
    Estimate tokens for three-role prompt.

    Args:
        system_prompt: System message text
        developer_prompt: Developer message text
        user_prompt: User message text
        model: Model name

    Returns:
        Dict with system_tokens, developer_tokens, user_tokens, total_tokens
    """
    encoding = get_encoding_for_model(model)

    system_tokens = len(encoding.encode(system_prompt))
    developer_tokens = len(encoding.encode(developer_prompt))
    user_tokens = len(encoding.encode(user_prompt))

    # Add overhead for message formatting (~10 tokens per message)
    overhead = 30

    return {
        "system_tokens": system_tokens,
        "developer_tokens": developer_tokens,
        "user_tokens": user_tokens,
        "total_tokens": system_tokens + developer_tokens + user_tokens + overhead,
    }


def calculate_cost(
    prompt_tokens: int,
    completion_tokens: int,
    cached_tokens: int = 0,
    model: str = "gpt-5-mini",
) -> Dict[str, Any]:
    """
    Calculate cost for API call.

    Args:
        prompt_tokens: Number of input tokens
        completion_tokens: Number of output tokens
        cached_tokens: Number of cached input tokens (90% discount)
        model: Model name (affects pricing)

    Returns:
        Dict with input_cost, output_cost, cache_cost, total_cost (in USD)

    Note:
        Pricing is configurable via environment variables.
        Default pricing (gpt-5-mini):
        - Input: $0.15 / 1M tokens
        - Output: $0.60 / 1M tokens
        - Cached: $0.075 / 1M tokens (50% discount)
    """
    config = get_config()

    # Uncached input tokens
    uncached_tokens = prompt_tokens - cached_tokens

    # Calculate costs (per 1M tokens, convert to actual)
    input_cost = (uncached_tokens / 1_000_000) * config.prompt_token_price_per_million
    output_cost = (
        completion_tokens / 1_000_000
    ) * config.completion_token_price_per_million
    cache_cost = (cached_tokens / 1_000_000) * config.cached_token_price_per_million

    total_cost = input_cost + output_cost + cache_cost

    return {
        "input_cost": input_cost,
        "output_cost": output_cost,
        "cache_cost": cache_cost,
        "total_cost": total_cost,
        "tokens": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cached_tokens": cached_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


def format_cost_report(cost_data: Dict[str, Any]) -> str:
    """
    Format cost data as human-readable report.

    Args:
        cost_data: Output from calculate_cost()

    Returns:
        Formatted cost report string
    """
    tokens = cost_data["tokens"]

    report = [
        "=== Cost Report ===",
        f"Input tokens: {tokens['prompt_tokens']:,} (${cost_data['input_cost']:.4f})",
        f"Cached tokens: {tokens['cached_tokens']:,} (${cost_data['cache_cost']:.4f})",
        f"Output tokens: {tokens['completion_tokens']:,} (${cost_data['output_cost']:.4f})",
        f"Total tokens: {tokens['total_tokens']:,}",
        f"Total cost: ${cost_data['total_cost']:.4f}",
    ]

    # Calculate cache savings
    if tokens["cached_tokens"] > 0:
        full_cost_without_cache = (
            tokens["prompt_tokens"] / 1_000_000
        ) * get_config().prompt_token_price_per_million + cost_data["output_cost"]
        savings = full_cost_without_cache - cost_data["total_cost"]
        savings_pct = (savings / full_cost_without_cache) * 100
        report.append(f"Cache savings: ${savings:.4f} ({savings_pct:.1f}%)")

    return "\n".join(report)


def check_cost_alerts(total_cost: float) -> Optional[str]:
    """
    Check if cost exceeds alert thresholds.

    Args:
        total_cost: Total cost in USD

    Returns:
        Alert message if threshold exceeded, None otherwise
    """
    config = get_config()

    if total_cost >= config.cost_alert_threshold_3:
        return f"🚨 CRITICAL: Cost ${total_cost:.2f} exceeds threshold ${config.cost_alert_threshold_3:.2f}"
    elif total_cost >= config.cost_alert_threshold_2:
        return f"⚠️ WARNING: Cost ${total_cost:.2f} exceeds threshold ${config.cost_alert_threshold_2:.2f}"
    elif total_cost >= config.cost_alert_threshold_1:
        return f"ℹ️ INFO: Cost ${total_cost:.2f} exceeds threshold ${config.cost_alert_threshold_1:.2f}"

    return None


# Example usage
if __name__ == "__main__":
    from src.prompts import SYSTEM_PROMPT, DEVELOPER_PROMPT, build_user_prompt

    print("=== Token Counter Test ===")

    # Test 1: Basic token counting
    print("\nTest 1: Basic token counting")
    test_text = "Hello, world! How are you today?"
    tokens = estimate_tokens(test_text, "gpt-5-mini")
    print(f"✅ Text: '{test_text}'")
    print(f"✅ Tokens: {tokens}")

    # Test 2: Estimate prompt tokens
    print("\nTest 2: Estimate prompt tokens")
    from datetime import datetime, timezone

    user_prompt = build_user_prompt(
        processed_at=datetime.now(timezone.utc).isoformat(),
        original_file_name="test.pdf",
        page_count=1,
    )

    estimates = estimate_prompt_tokens(
        SYSTEM_PROMPT, DEVELOPER_PROMPT, user_prompt, "gpt-5-mini"
    )

    print(f"✅ System tokens: {estimates['system_tokens']}")
    print(f"✅ Developer tokens: {estimates['developer_tokens']}")
    print(f"✅ User tokens: {estimates['user_tokens']}")
    print(f"✅ Total tokens: {estimates['total_tokens']}")

    # Test 3: Calculate cost (first request, no cache)
    print("\nTest 3: Calculate cost (first request)")
    cost_first = calculate_cost(
        prompt_tokens=estimates["total_tokens"],
        completion_tokens=500,
        cached_tokens=0,
        model="gpt-5-mini",
    )

    print(format_cost_report(cost_first))

    # Test 4: Calculate cost (subsequent request, with cache)
    print("\nTest 4: Calculate cost (with prompt caching)")
    # Assume system + developer prompts are cached (90% of prompt tokens)
    cacheable_tokens = estimates["system_tokens"] + estimates["developer_tokens"]

    cost_cached = calculate_cost(
        prompt_tokens=estimates["total_tokens"],
        completion_tokens=500,
        cached_tokens=cacheable_tokens,
        model="gpt-5-mini",
    )

    print(format_cost_report(cost_cached))

    # Test 5: Cost alerts
    print("\nTest 5: Cost alert thresholds")
    test_costs = [5.0, 15.0, 60.0, 120.0]
    for cost in test_costs:
        alert = check_cost_alerts(cost)
        if alert:
            print(f"${cost}: {alert}")
        else:
            print(f"${cost}: No alert")

    # Test 6: Savings calculation
    print("\nTest 6: Cache savings analysis")
    savings = cost_first["total_cost"] - cost_cached["total_cost"]
    savings_pct = (savings / cost_first["total_cost"]) * 100

    print(f"✅ First request cost: ${cost_first['total_cost']:.4f}")
    print(f"✅ Cached request cost: ${cost_cached['total_cost']:.4f}")
    print(f"✅ Savings: ${savings:.4f} ({savings_pct:.1f}%)")

    print("\n=== All Tests Complete ===")
