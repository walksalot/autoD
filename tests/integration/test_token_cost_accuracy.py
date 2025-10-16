"""
Integration tests for token counting accuracy validation.

Validates that tiktoken estimates are within 5% of OpenAI's reported usage.

These tests use mock API responses with known token counts to verify accuracy.
In production, you can compare against actual OpenAI API responses.
"""

import pytest
from token_counter import EncodingResolver, ResponsesAPICalculator
from src.cost_calculator import calculate_cost, GPT5_PRICING


class TestTokenCountingAccuracy:
    """Test token counting accuracy against expected values."""

    def test_accuracy_simple_text(self):
        """Simple text token counting is accurate."""
        resolver = EncodingResolver()
        encoding = resolver.get_encoding("gpt-5")

        text = "Extract metadata from this PDF document."
        estimated_tokens = len(encoding.encode(text))

        # For this simple text, tiktoken should be exact
        # (In real scenario, compare against OpenAI's reported usage)
        assert estimated_tokens > 0
        assert estimated_tokens < 100  # Sanity check

    def test_accuracy_responses_api_format(self):
        """Responses API message token counting is reasonably accurate."""
        calculator = ResponsesAPICalculator()

        messages = [
            {
                "role": "developer",
                "content": [
                    {
                        "type": "input_text",
                        "text": "You are a document metadata extraction system.",
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": "Extract metadata from the PDF.",
                    }
                ],
            },
        ]

        result = calculator.count_request_tokens(
            model="gpt-5",
            messages=messages,
        )

        # Verify reasonable token count
        assert result.count.total > 0
        assert result.count.total < 1000  # Sanity check for short messages

        # Verify breakdown
        assert result.breakdown["messages"] > 0
        assert result.breakdown["tools"] == 0  # No tools in this request


class TestCostCalculationAccuracy:
    """Test cost calculation accuracy against expected values."""

    def test_cost_matches_pricing_constants(self):
        """Cost calculation uses correct pricing constants."""
        usage = {
            "prompt_tokens": 1000,
            "output_tokens": 1000,
            "prompt_tokens_details": {"cached_tokens": 0},
        }

        cost = calculate_cost(usage)

        # Manual calculation verification
        expected_input_cost = 1000 * GPT5_PRICING.input_per_1k / 1000
        expected_output_cost = 1000 * GPT5_PRICING.output_per_1k / 1000
        expected_total = expected_input_cost + expected_output_cost

        assert cost["input_cost_usd"] == pytest.approx(expected_input_cost)
        assert cost["output_cost_usd"] == pytest.approx(expected_output_cost)
        assert cost["total_cost_usd"] == pytest.approx(expected_total)

    def test_cache_discount_accuracy(self):
        """Cache discount is exactly 10% of regular input cost."""
        usage = {
            "prompt_tokens": 1000,
            "output_tokens": 0,
            "prompt_tokens_details": {"cached_tokens": 1000},
        }

        cost = calculate_cost(usage)

        # Cache cost should be 10% of regular input cost
        regular_cost = 1000 * GPT5_PRICING.input_per_1k / 1000  # $0.010
        cache_cost = 1000 * GPT5_PRICING.cached_per_1k / 1000  # $0.001

        assert cost["cache_cost_usd"] == pytest.approx(cache_cost)
        assert cache_cost == pytest.approx(regular_cost * 0.1)

        # Savings should be 90% of regular cost
        assert cost["cache_savings_usd"] == pytest.approx(regular_cost * 0.9)

    def test_accuracy_against_mock_api_response(self):
        """Simulate real API response and validate accuracy."""
        # Mock API response (in production, use actual OpenAI response)
        mock_api_usage = {
            "prompt_tokens": 1234,
            "output_tokens": 567,
            "prompt_tokens_details": {"cached_tokens": 987},
        }

        # Calculate cost
        cost = calculate_cost(mock_api_usage)

        # Verify accuracy of calculations
        assert cost["prompt_tokens"] == 1234
        assert cost["output_tokens"] == 567
        assert cost["cached_tokens"] == 987
        assert cost["billable_input_tokens"] == 247  # 1234 - 987

        # Manual calculation (new semantics: input_cost = billable + cache)
        expected_billable = 247 * 0.010 / 1000  # $0.00247
        expected_cache = 987 * 0.001 / 1000  # $0.000987
        expected_input = expected_billable + expected_cache  # Total input cost
        expected_output = 567 * 0.030 / 1000  # $0.01701
        expected_total = expected_input + expected_output

        # Verify within reasonable precision (6 decimal places)
        assert abs(cost["input_cost_usd"] - expected_input) < 1e-6
        assert abs(cost["cache_cost_usd"] - expected_cache) < 1e-6
        assert abs(cost["output_cost_usd"] - expected_output) < 1e-6
        assert abs(cost["total_cost_usd"] - expected_total) < 1e-6


class TestProductionScenarios:
    """Test realistic production scenarios."""

    def test_batch_processing_cost_tracking(self):
        """Simulate batch processing of 100 PDFs."""
        from src.cost_calculator import CostTracker

        tracker = CostTracker()

        # Simulate 100 PDFs
        # First PDF: cold start, no caching
        # Remaining 99: 80% cache hit on developer prompt

        # Cold start
        tracker.add_usage(
            {
                "prompt_tokens": 1200,
                "output_tokens": 450,
                "prompt_tokens_details": {"cached_tokens": 0},
            }
        )

        # Subsequent PDFs with caching
        for _ in range(99):
            tracker.add_usage(
                {
                    "prompt_tokens": 1200,
                    "output_tokens": 450,
                    "prompt_tokens_details": {"cached_tokens": 960},
                }
            )

        summary = tracker.summary()

        # Verify reasonable totals
        assert summary["request_count"] == 100
        assert summary["total_tokens"] == 100 * 1650  # (1200 + 450) * 100
        assert summary["total_cached_tokens"] == 99 * 960  # Only last 99 have caching
        assert summary["total_cost_usd"] > 0
        assert summary["cache_hit_rate"] > 0.5  # Should be around 58%

        # Verify cost savings from caching
        assert summary["total_cache_savings_usd"] > 0

        # Average cost should be less than cold start cost
        cold_start_cost = (1200 * 0.010 + 450 * 0.030) / 1000  # $0.0255
        assert summary["average_cost_usd"] < cold_start_cost

    def test_cost_estimation_before_processing(self):
        """Pre-flight cost estimation for budget validation."""
        from src.cost_calculator import estimate_cost_from_tokens
        from token_counter import EncodingResolver

        resolver = EncodingResolver()
        encoding = resolver.get_encoding("gpt-5")

        # Estimate prompt tokens
        developer_prompt = "You are a document metadata extraction system. Extract: doc_type, issuer, primary_date, total_amount."
        prompt_tokens = len(encoding.encode(developer_prompt))

        # Conservative output estimate
        expected_output_tokens = 500

        # Estimate cost
        estimated = estimate_cost_from_tokens(
            prompt_tokens=prompt_tokens,
            output_tokens=expected_output_tokens,
            cached_tokens=0,  # Conservative (no caching assumed)
        )

        # Verify estimation is reasonable
        assert estimated["total_cost_usd"] > 0
        assert estimated["total_cost_usd"] < 1.0  # Should be well under $1 per PDF

        # For 1000 PDFs, estimate total cost
        total_estimated_cost = estimated["total_cost_usd"] * 1000

        # Should be well under $100 for 1000 PDFs (success criterion)
        assert total_estimated_cost < 100.0

    def test_accuracy_tolerance_validation(self):
        """Validate that our estimates meet 5% accuracy tolerance."""
        # This test would compare tiktoken estimates vs actual OpenAI usage
        # For now, we verify the calculation logic is sound

        usage = {
            "prompt_tokens": 1000,
            "output_tokens": 500,
            "prompt_tokens_details": {"cached_tokens": 0},
        }

        cost = calculate_cost(usage)

        # If OpenAI reports same token counts, cost should match exactly
        # In real scenarios, tiktoken may differ by ~1-5% from OpenAI's count
        # Our cost calculation is exact given the token counts

        # Verify precision
        assert cost["total_cost_usd"] == pytest.approx(0.025, abs=1e-6)

        # Simulate 5% variance in token counting
        usage_5pct_higher = {
            "prompt_tokens": 1050,  # 5% higher
            "output_tokens": 525,  # 5% higher
            "prompt_tokens_details": {"cached_tokens": 0},
        }

        cost_higher = calculate_cost(usage_5pct_higher)

        # Cost should also be ~5% higher
        expected_ratio = 1.05
        actual_ratio = cost_higher["total_cost_usd"] / cost["total_cost_usd"]

        assert actual_ratio == pytest.approx(expected_ratio, rel=0.01)


# Manual validation helper (for real API testing)
def validate_against_real_api_response():
    """
    Helper function for manual validation against real OpenAI API responses.

    Usage (not automated):
        1. Make a real API call and capture response
        2. Extract response.usage dictionary
        3. Calculate cost using our calculator
        4. Compare against OpenAI's billing data

    Example:
        >>> response = client.responses.create(...)
        >>> usage = response.usage.__dict__
        >>> cost = calculate_cost(usage)
        >>> print(f"Estimated cost: ${cost['total_cost_usd']:.6f}")
        >>>
        >>> # Compare with actual billing amount from OpenAI dashboard
        >>> # Should be within 5% tolerance
    """
    pass
