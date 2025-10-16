"""
Unit tests for src/cost_calculator.py

Tests cover:
- Price tier definitions and accuracy
- Cost calculations with and without caching
- Model-to-pricing mapping
- CostTracker cumulative tracking
- Pre-flight cost estimation
- Edge cases and error handling

Target: 90%+ coverage
"""

import pytest
from src.cost_calculator import (
    GPT5_PRICING,
    GPT4O_PRICING,
    GPT4_PRICING,
    get_pricing_for_model,
    calculate_cost,
    format_cost_summary,
    CostTracker,
    estimate_cost_from_tokens,
)


class TestPricingTier:
    """Tests for PricingTier dataclass."""

    def test_gpt5_pricing_constants(self):
        """GPT-5 pricing matches expected values."""
        assert GPT5_PRICING.input_per_1k == 0.010
        assert GPT5_PRICING.output_per_1k == 0.030
        assert GPT5_PRICING.cached_per_1k == 0.001

    def test_gpt4o_pricing_constants(self):
        """GPT-4o pricing matches expected values."""
        assert GPT4O_PRICING.input_per_1k == 0.0025
        assert GPT4O_PRICING.output_per_1k == 0.010
        assert GPT4O_PRICING.cached_per_1k == 0.00025

    def test_gpt4_pricing_constants(self):
        """GPT-4 pricing matches expected values."""
        assert GPT4_PRICING.input_per_1k == 0.030
        assert GPT4_PRICING.output_per_1k == 0.060
        assert GPT4_PRICING.cached_per_1k == 0.003

    def test_pricing_tier_immutable(self):
        """PricingTier instances are immutable (frozen dataclass)."""
        with pytest.raises(AttributeError):
            GPT5_PRICING.input_per_1k = 0.020  # type: ignore

    def test_pricing_tier_str_representation(self):
        """PricingTier has readable string representation."""
        s = str(GPT5_PRICING)
        assert "Input: $0.010/1K" in s
        assert "Output: $0.030/1K" in s
        assert "Cached: $0.0010/1K" in s


class TestGetPricingForModel:
    """Tests for get_pricing_for_model() function."""

    def test_exact_match_gpt5(self):
        """Exact model name match returns correct pricing."""
        assert get_pricing_for_model("gpt-5") == GPT5_PRICING

    def test_exact_match_gpt4o(self):
        """Exact match for GPT-4o."""
        assert get_pricing_for_model("gpt-4o") == GPT4O_PRICING

    def test_exact_match_gpt4(self):
        """Exact match for GPT-4."""
        assert get_pricing_for_model("gpt-4") == GPT4_PRICING

    def test_pattern_match_gpt5_mini(self):
        """Pattern matching works for GPT-5 variants."""
        assert get_pricing_for_model("gpt-5-mini") == GPT5_PRICING
        assert get_pricing_for_model("gpt-5-nano") == GPT5_PRICING

    def test_pattern_match_gpt4o_mini(self):
        """Pattern matching works for GPT-4o variants."""
        assert get_pricing_for_model("gpt-4o-mini") == GPT4O_PRICING

    def test_pattern_match_gpt4_turbo(self):
        """Pattern matching works for GPT-4 variants."""
        assert get_pricing_for_model("gpt-4-turbo") == GPT4_PRICING

    def test_unknown_model_defaults_to_gpt5(self):
        """Unknown models default to GPT-5 pricing with warning."""
        pricing = get_pricing_for_model("gpt-unknown-model")
        assert pricing == GPT5_PRICING

    def test_case_insensitive_matching(self):
        """Model name matching is case-insensitive."""
        assert get_pricing_for_model("GPT-5") == GPT5_PRICING
        assert get_pricing_for_model("Gpt-4O-Mini") == GPT4O_PRICING


class TestCalculateCost:
    """Tests for calculate_cost() function."""

    def test_basic_cost_no_caching(self):
        """Basic cost calculation without caching."""
        usage = {
            "prompt_tokens": 1000,
            "output_tokens": 500,
            "prompt_tokens_details": {"cached_tokens": 0},
        }

        cost = calculate_cost(usage)

        # Token counts
        assert cost["prompt_tokens"] == 1000
        assert cost["output_tokens"] == 500
        assert cost["cached_tokens"] == 0
        assert cost["billable_input_tokens"] == 1000
        assert cost["total_tokens"] == 1500

        # Costs (GPT-5 pricing)
        assert cost["input_cost_usd"] == pytest.approx(0.010)  # 1000 * 0.010 / 1000
        assert cost["output_cost_usd"] == pytest.approx(0.015)  # 500 * 0.030 / 1000
        assert cost["cache_cost_usd"] == pytest.approx(0.0)
        assert cost["cache_savings_usd"] == pytest.approx(0.0)
        assert cost["total_cost_usd"] == pytest.approx(0.025)

    def test_cost_with_caching(self):
        """Cost calculation with cached tokens."""
        usage = {
            "prompt_tokens": 1000,
            "output_tokens": 500,
            "prompt_tokens_details": {"cached_tokens": 800},
        }

        cost = calculate_cost(usage)

        # Token counts
        assert cost["prompt_tokens"] == 1000
        assert cost["output_tokens"] == 500
        assert cost["cached_tokens"] == 800
        assert cost["billable_input_tokens"] == 200  # 1000 - 800
        assert cost["total_tokens"] == 1500

        # Costs (new semantics: input_cost = billable_input + cache)
        assert cost["input_cost_usd"] == pytest.approx(
            0.0028
        )  # (200 * 0.010 + 800 * 0.001) / 1000
        assert cost["output_cost_usd"] == pytest.approx(0.015)  # 500 * 0.030 / 1000
        assert cost["cache_cost_usd"] == pytest.approx(0.0008)  # 800 * 0.001 / 1000

        # Cache savings = (800 * 0.010 / 1000) - (800 * 0.001 / 1000) = 0.008 - 0.0008 = 0.0072
        assert cost["cache_savings_usd"] == pytest.approx(0.0072)

        # Total = input_cost + output_cost = 0.0028 + 0.015 = 0.0178
        assert cost["total_cost_usd"] == pytest.approx(0.0178)

    def test_cost_with_full_caching(self):
        """All prompt tokens cached (100% cache hit)."""
        usage = {
            "prompt_tokens": 1000,
            "output_tokens": 500,
            "prompt_tokens_details": {"cached_tokens": 1000},
        }

        cost = calculate_cost(usage)

        assert cost["billable_input_tokens"] == 0
        assert cost["cached_tokens"] == 1000
        # New semantics: input_cost includes cache_cost even when billable is 0
        assert cost["input_cost_usd"] == pytest.approx(
            0.001
        )  # 1000 * 0.001 / 1000 (all cached)
        assert cost["cache_cost_usd"] == pytest.approx(0.001)
        assert cost["cache_savings_usd"] == pytest.approx(
            0.009
        )  # 1000 * (0.010 - 0.001) / 1000

    def test_cost_zero_tokens(self):
        """Handle zero token counts gracefully."""
        usage = {
            "prompt_tokens": 0,
            "output_tokens": 0,
            "prompt_tokens_details": {"cached_tokens": 0},
        }

        cost = calculate_cost(usage)

        assert cost["total_tokens"] == 0
        assert cost["total_cost_usd"] == pytest.approx(0.0)

    def test_cost_missing_prompt_details(self):
        """Missing prompt_tokens_details defaults to 0 cached tokens."""
        usage = {
            "prompt_tokens": 1000,
            "output_tokens": 500,
        }

        cost = calculate_cost(usage)

        assert cost["cached_tokens"] == 0
        assert cost["billable_input_tokens"] == 1000

    def test_cost_with_model_parameter(self):
        """Model parameter overrides default pricing."""
        usage = {
            "prompt_tokens": 1000,
            "output_tokens": 500,
            "prompt_tokens_details": {"cached_tokens": 0},
        }

        # Use GPT-4o pricing
        cost = calculate_cost(usage, model="gpt-4o-mini")

        # Should use GPT-4o pricing: 0.0025/1K input, 0.010/1K output
        assert cost["input_cost_usd"] == pytest.approx(0.0025)  # 1000 * 0.0025 / 1000
        assert cost["output_cost_usd"] == pytest.approx(0.005)  # 500 * 0.010 / 1000
        assert cost["total_cost_usd"] == pytest.approx(0.0075)

    def test_cost_with_pricing_parameter(self):
        """Pricing parameter directly specifies pricing tier."""
        usage = {
            "prompt_tokens": 1000,
            "output_tokens": 500,
            "prompt_tokens_details": {"cached_tokens": 0},
        }

        cost = calculate_cost(usage, pricing=GPT4_PRICING)

        # Should use GPT-4 pricing: 0.030/1K input, 0.060/1K output
        assert cost["input_cost_usd"] == pytest.approx(0.030)
        assert cost["output_cost_usd"] == pytest.approx(0.030)  # 500 * 0.060 / 1000
        assert cost["total_cost_usd"] == pytest.approx(0.060)

    def test_cost_rounding_precision(self):
        """Costs are rounded to 6 decimal places."""
        usage = {
            "prompt_tokens": 123,
            "output_tokens": 456,
            "prompt_tokens_details": {"cached_tokens": 0},
        }

        cost = calculate_cost(usage)

        # All cost values should have at most 6 decimal places
        assert len(str(cost["input_cost_usd"]).split(".")[-1]) <= 6
        assert len(str(cost["output_cost_usd"]).split(".")[-1]) <= 6
        assert len(str(cost["total_cost_usd"]).split(".")[-1]) <= 6


class TestFormatCostSummary:
    """Tests for format_cost_summary() function."""

    def test_format_basic_summary(self):
        """Format summary without caching."""
        cost = {
            "prompt_tokens": 1000,
            "output_tokens": 500,
            "cached_tokens": 0,
            "billable_input_tokens": 1000,
            "total_tokens": 1500,
            "input_cost_usd": 0.010,
            "output_cost_usd": 0.015,
            "cache_cost_usd": 0.0,
            "cache_savings_usd": 0.0,
            "total_cost_usd": 0.025,
            "pricing_tier": str(GPT5_PRICING),
        }

        summary = format_cost_summary(cost)

        assert "Total: $0.0250" in summary
        assert "Input: 1,000 tokens" in summary
        assert "Output: 500 tokens" in summary
        assert "Cached" not in summary  # No caching

    def test_format_summary_with_caching(self):
        """Format summary with cached tokens."""
        cost = {
            "prompt_tokens": 1000,
            "output_tokens": 500,
            "cached_tokens": 800,
            "billable_input_tokens": 200,
            "total_tokens": 1500,
            "input_cost_usd": 0.002,
            "output_cost_usd": 0.015,
            "cache_cost_usd": 0.0008,
            "cache_savings_usd": 0.0072,
            "total_cost_usd": 0.0178,
            "pricing_tier": str(GPT5_PRICING),
        }

        summary = format_cost_summary(cost)

        assert "Total: $0.0178" in summary
        assert "Input: 200 tokens" in summary
        assert "Cached: 800 tokens" in summary
        assert "saved $0.0072" in summary


class TestCostTracker:
    """Tests for CostTracker class."""

    def test_tracker_initialization(self):
        """CostTracker initializes correctly."""
        tracker = CostTracker()

        assert tracker.total_cost == 0.0
        assert tracker.total_tokens == 0
        assert tracker.request_count == 0
        assert tracker.pricing == GPT5_PRICING

    def test_tracker_add_single_usage(self):
        """Add single usage record."""
        tracker = CostTracker()

        usage = {
            "prompt_tokens": 1000,
            "output_tokens": 500,
            "prompt_tokens_details": {"cached_tokens": 0},
        }

        cost = tracker.add_usage(usage)

        assert tracker.request_count == 1
        assert tracker.total_cost == pytest.approx(0.025)
        assert tracker.total_tokens == 1500
        assert cost["total_cost_usd"] == pytest.approx(0.025)

    def test_tracker_add_multiple_usages(self):
        """Add multiple usage records."""
        tracker = CostTracker()

        for _ in range(10):
            usage = {
                "prompt_tokens": 1000,
                "output_tokens": 500,
                "prompt_tokens_details": {"cached_tokens": 0},
            }
            tracker.add_usage(usage)

        assert tracker.request_count == 10
        assert tracker.total_cost == pytest.approx(0.25)  # 10 * 0.025
        assert tracker.total_tokens == 15000  # 10 * 1500
        assert tracker.average_cost == pytest.approx(0.025)

    def test_tracker_with_caching(self):
        """Track caching statistics."""
        tracker = CostTracker()

        # First request: no caching
        tracker.add_usage(
            {
                "prompt_tokens": 1000,
                "output_tokens": 500,
                "prompt_tokens_details": {"cached_tokens": 0},
            }
        )

        # Subsequent requests: 80% cache hit
        for _ in range(9):
            tracker.add_usage(
                {
                    "prompt_tokens": 1000,
                    "output_tokens": 500,
                    "prompt_tokens_details": {"cached_tokens": 800},
                }
            )

        assert tracker.request_count == 10
        assert tracker.total_cached_tokens == 7200  # 9 * 800
        assert tracker.total_cache_savings > 0

    def test_tracker_with_metadata(self):
        """Store metadata with usage records."""
        tracker = CostTracker()

        tracker.add_usage(
            usage={"prompt_tokens": 1000, "output_tokens": 500},
            metadata={"pdf_path": "/path/to/file.pdf", "doc_id": 42},
        )

        assert len(tracker.requests) == 1
        assert tracker.requests[0]["metadata"]["pdf_path"] == "/path/to/file.pdf"
        assert tracker.requests[0]["metadata"]["doc_id"] == 42

    def test_tracker_summary(self):
        """Summary statistics are correct."""
        tracker = CostTracker()

        for i in range(5):
            tracker.add_usage(
                {
                    "prompt_tokens": 1000,
                    "output_tokens": 500,
                    "prompt_tokens_details": {"cached_tokens": 800 if i > 0 else 0},
                }
            )

        summary = tracker.summary()

        assert summary["request_count"] == 5
        assert summary["total_cost_usd"] > 0
        assert summary["average_cost_usd"] > 0
        assert summary["total_tokens"] == 7500
        assert summary["total_cached_tokens"] == 3200
        assert summary["cache_hit_rate"] > 0

    def test_tracker_summary_text(self):
        """Summary text is formatted correctly."""
        tracker = CostTracker()

        tracker.add_usage(
            {
                "prompt_tokens": 1000,
                "output_tokens": 500,
                "prompt_tokens_details": {"cached_tokens": 0},
            }
        )

        text = tracker.summary_text()

        assert "1 requests" in text
        assert "Total:" in text
        assert "Avg:" in text
        assert "Tokens:" in text

    def test_tracker_with_different_models(self):
        """Tracker handles different model pricing."""
        tracker = CostTracker()

        tracker.add_usage(
            usage={"prompt_tokens": 1000, "output_tokens": 500}, model="gpt-5"
        )

        tracker.add_usage(
            usage={"prompt_tokens": 1000, "output_tokens": 500}, model="gpt-4o-mini"
        )

        # Costs should differ due to different pricing
        assert (
            tracker.requests[0]["total_cost_usd"]
            != tracker.requests[1]["total_cost_usd"]
        )

    def test_tracker_empty_average(self):
        """Average cost is 0 when no requests."""
        tracker = CostTracker()
        assert tracker.average_cost == 0.0


class TestEstimateCostFromTokens:
    """Tests for estimate_cost_from_tokens() function."""

    def test_estimate_basic(self):
        """Estimate cost from token counts."""
        estimated = estimate_cost_from_tokens(
            prompt_tokens=1000,
            output_tokens=500,
            cached_tokens=0,
        )

        assert estimated["prompt_tokens"] == 1000
        assert estimated["output_tokens"] == 500
        assert estimated["total_cost_usd"] == pytest.approx(0.025)

    def test_estimate_with_caching(self):
        """Estimate cost with cached tokens."""
        estimated = estimate_cost_from_tokens(
            prompt_tokens=1000,
            output_tokens=500,
            cached_tokens=800,
        )

        assert estimated["cached_tokens"] == 800
        assert estimated["billable_input_tokens"] == 200
        assert estimated["total_cost_usd"] < 0.025  # Should be cheaper with caching

    def test_estimate_with_custom_pricing(self):
        """Estimate cost with custom pricing tier."""
        estimated = estimate_cost_from_tokens(
            prompt_tokens=1000,
            output_tokens=500,
            pricing=GPT4O_PRICING,
        )

        # GPT-4o is cheaper than GPT-5
        assert estimated["total_cost_usd"] < 0.025


# Integration tests
class TestIntegration:
    """Integration tests combining multiple components."""

    def test_full_workflow_no_caching(self):
        """Complete workflow: usage → cost → tracker → summary."""
        tracker = CostTracker()

        # Simulate 3 API calls
        for i in range(3):
            usage = {
                "prompt_tokens": 1200,
                "output_tokens": 450,
                "prompt_tokens_details": {"cached_tokens": 0},
            }

            cost = calculate_cost(usage)
            tracker.add_usage(usage, metadata={"request": i})

            # Verify individual cost
            assert cost["total_cost_usd"] > 0

        # Verify tracking
        assert tracker.request_count == 3
        assert tracker.total_cost > 0
        assert tracker.average_cost > 0

        # Verify summary
        summary = tracker.summary()
        assert summary["request_count"] == 3
        assert summary["total_tokens"] == 3 * 1650  # 3 * (1200 + 450)

    def test_full_workflow_with_caching(self):
        """Complete workflow with progressive caching."""
        tracker = CostTracker()

        # First request: cold start, no caching
        usage_cold = {
            "prompt_tokens": 1200,
            "output_tokens": 450,
            "prompt_tokens_details": {"cached_tokens": 0},
        }
        cost_cold = tracker.add_usage(usage_cold)

        # Subsequent requests: 80% cache hit
        for _ in range(9):
            usage_cached = {
                "prompt_tokens": 1200,
                "output_tokens": 450,
                "prompt_tokens_details": {"cached_tokens": 960},
            }
            tracker.add_usage(usage_cached)

        # Verify caching statistics
        summary = tracker.summary()
        assert summary["total_cached_tokens"] == 9 * 960
        assert summary["total_cache_savings_usd"] > 0
        assert summary["cache_hit_rate"] > 0.5  # Should be ~72% (8640 / 12000)

        # Cost should decrease significantly with caching
        assert tracker.average_cost < cost_cold["total_cost_usd"]
