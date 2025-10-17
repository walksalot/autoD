"""
Unit tests for token_counter module (tiktoken token counting and cost calculation).

Tests cover:
- Encoding selection for different models
- Token estimation for text
- Prompt token estimation (system/developer/user roles)
- Cost calculation with caching
- Cost report formatting
- Alert threshold checking
"""

import pytest
from unittest.mock import patch, Mock

from src.token_counter import (
    get_encoding_for_model,
    estimate_tokens,
    estimate_prompt_tokens,
    calculate_cost,
    format_cost_report,
    check_cost_alerts,
)


class TestGetEncodingForModel:
    """Test suite for model-to-encoding mapping."""

    def test_gpt5_uses_o200k_base(self):
        """GPT-5 models should use o200k_base encoding."""
        encoding = get_encoding_for_model("gpt-5")
        assert encoding.name == "o200k_base"

    def test_gpt5_mini_uses_o200k_base(self):
        """GPT-5-mini should use o200k_base encoding."""
        encoding = get_encoding_for_model("gpt-5-mini")
        assert encoding.name == "o200k_base"

    def test_older_models_use_cl100k_base(self):
        """Non-GPT-5 models should use cl100k_base encoding."""
        encoding = get_encoding_for_model("gpt-4")
        assert encoding.name == "cl100k_base"

    def test_unknown_model_fallback(self):
        """Unknown models should fall back to cl100k_base."""
        encoding = get_encoding_for_model("unknown-model")
        assert encoding.name == "cl100k_base"


class TestEstimateTokens:
    """Test suite for basic token counting."""

    def test_empty_string(self):
        """Empty string should have 0 tokens."""
        tokens = estimate_tokens("", "gpt-5-mini")
        assert tokens == 0

    def test_simple_text(self):
        """Simple text should count correctly."""
        tokens = estimate_tokens("Hello, world!", "gpt-5-mini")
        assert tokens > 0
        assert isinstance(tokens, int)

    def test_long_text(self):
        """Long text should have more tokens."""
        short_text = "Hi"
        long_text = "This is a much longer piece of text with many more words."

        short_tokens = estimate_tokens(short_text, "gpt-5-mini")
        long_tokens = estimate_tokens(long_text, "gpt-5-mini")

        assert long_tokens > short_tokens

    def test_different_encodings_different_counts(self):
        """Different models (encodings) may produce different token counts."""
        text = "Hello, world!"

        gpt5_tokens = estimate_tokens(text, "gpt-5")
        gpt4_tokens = estimate_tokens(text, "gpt-4")

        # Both should be positive integers (may or may not be equal)
        assert gpt5_tokens > 0
        assert gpt4_tokens > 0

    def test_special_characters(self):
        """Special characters should be counted."""
        text_with_special = "Hello! 🌍 @#$%"
        tokens = estimate_tokens(text_with_special, "gpt-5-mini")
        assert tokens > 0

    def test_unicode_text(self):
        """Unicode text (emojis, non-ASCII) should be handled."""
        unicode_text = "こんにちは 世界 🎉"
        tokens = estimate_tokens(unicode_text, "gpt-5-mini")
        assert tokens > 0


class TestEstimatePromptTokens:
    """Test suite for multi-role prompt token estimation."""

    def test_all_prompts_counted(self):
        """Should count tokens for all three roles."""
        result = estimate_prompt_tokens(
            system_prompt="System: Extract metadata.",
            developer_prompt="Developer: Use JSON format.",
            user_prompt="User: Process this file.",
            model="gpt-5-mini",
        )

        assert "system_tokens" in result
        assert "developer_tokens" in result
        assert "user_tokens" in result
        assert "total_tokens" in result

        assert result["system_tokens"] > 0
        assert result["developer_tokens"] > 0
        assert result["user_tokens"] > 0

    def test_total_includes_overhead(self):
        """Total should include per-message overhead (~30 tokens)."""
        result = estimate_prompt_tokens(
            system_prompt="A",
            developer_prompt="B",
            user_prompt="C",
            model="gpt-5-mini",
        )

        # Total should be sum of individual + overhead (30)
        individual_sum = (
            result["system_tokens"] + result["developer_tokens"] + result["user_tokens"]
        )
        assert result["total_tokens"] >= individual_sum
        assert result["total_tokens"] - individual_sum >= 30  # Overhead

    def test_empty_prompts(self):
        """Empty prompts should still have overhead."""
        result = estimate_prompt_tokens(
            system_prompt="",
            developer_prompt="",
            user_prompt="",
            model="gpt-5-mini",
        )

        assert result["system_tokens"] == 0
        assert result["developer_tokens"] == 0
        assert result["user_tokens"] == 0
        assert result["total_tokens"] == 30  # Just overhead

    def test_long_prompts(self):
        """Long prompts should have higher token counts."""
        long_system = "This is a very long system prompt. " * 50
        long_developer = "This is a very long developer prompt. " * 50
        long_user = "This is a very long user prompt. " * 50

        result = estimate_prompt_tokens(
            system_prompt=long_system,
            developer_prompt=long_developer,
            user_prompt=long_user,
            model="gpt-5-mini",
        )

        assert result["total_tokens"] > 500  # Should be substantial


class TestCalculateCost:
    """Test suite for cost calculation with caching."""

    @patch("src.token_counter.get_config")
    def test_basic_cost_calculation_no_cache(self, mock_config):
        """Calculate cost without caching."""
        # Mock config
        config_mock = Mock()
        config_mock.prompt_token_price_per_million = 0.15  # $0.15 / 1M
        config_mock.completion_token_price_per_million = 0.60  # $0.60 / 1M
        config_mock.cached_token_price_per_million = 0.075  # $0.075 / 1M
        mock_config.return_value = config_mock

        result = calculate_cost(
            prompt_tokens=1000,
            completion_tokens=500,
            cached_tokens=0,
            model="gpt-5-mini",
        )

        # Input cost: 1000 / 1_000_000 * 0.15 = 0.00015
        # Output cost: 500 / 1_000_000 * 0.60 = 0.0003
        # Cache cost: 0
        assert result["input_cost"] == pytest.approx(0.00015)
        assert result["output_cost"] == pytest.approx(0.0003)
        assert result["cache_cost"] == 0.0
        assert result["total_cost"] == pytest.approx(0.00045)

    @patch("src.token_counter.get_config")
    def test_cost_with_caching(self, mock_config):
        """Calculate cost with prompt caching."""
        config_mock = Mock()
        config_mock.prompt_token_price_per_million = 0.15
        config_mock.completion_token_price_per_million = 0.60
        config_mock.cached_token_price_per_million = 0.075
        mock_config.return_value = config_mock

        result = calculate_cost(
            prompt_tokens=1000,
            completion_tokens=500,
            cached_tokens=600,  # 60% cached
            model="gpt-5-mini",
        )

        # Uncached: 400 tokens * 0.15 = 0.00006
        # Cached: 600 tokens * 0.075 = 0.000045
        # Output: 500 * 0.60 = 0.0003
        assert result["input_cost"] == pytest.approx(0.00006)
        assert result["cache_cost"] == pytest.approx(0.000045)
        assert result["output_cost"] == pytest.approx(0.0003)
        assert result["total_cost"] < 0.0005  # Should be cheaper than no-cache

    @patch("src.token_counter.get_config")
    def test_zero_tokens(self, mock_config):
        """Zero tokens should have zero cost."""
        config_mock = Mock()
        config_mock.prompt_token_price_per_million = 0.15
        config_mock.completion_token_price_per_million = 0.60
        config_mock.cached_token_price_per_million = 0.075
        mock_config.return_value = config_mock

        result = calculate_cost(
            prompt_tokens=0,
            completion_tokens=0,
            cached_tokens=0,
        )

        assert result["input_cost"] == 0.0
        assert result["output_cost"] == 0.0
        assert result["cache_cost"] == 0.0
        assert result["total_cost"] == 0.0

    @patch("src.token_counter.get_config")
    def test_tokens_metadata_included(self, mock_config):
        """Result should include token metadata."""
        config_mock = Mock()
        config_mock.prompt_token_price_per_million = 0.15
        config_mock.completion_token_price_per_million = 0.60
        config_mock.cached_token_price_per_million = 0.075
        mock_config.return_value = config_mock

        result = calculate_cost(
            prompt_tokens=1000,
            completion_tokens=500,
            cached_tokens=300,
        )

        assert "tokens" in result
        assert result["tokens"]["prompt_tokens"] == 1000
        assert result["tokens"]["completion_tokens"] == 500
        assert result["tokens"]["cached_tokens"] == 300
        assert result["tokens"]["total_tokens"] == 1500


class TestFormatCostReport:
    """Test suite for cost report formatting."""

    def test_basic_formatting(self):
        """Should format cost data as readable report."""
        cost_data = {
            "input_cost": 0.00015,
            "output_cost": 0.0003,
            "cache_cost": 0.0,
            "total_cost": 0.00045,
            "tokens": {
                "prompt_tokens": 1000,
                "completion_tokens": 500,
                "cached_tokens": 0,
                "total_tokens": 1500,
            },
        }

        report = format_cost_report(cost_data)

        assert "=== Cost Report ===" in report
        assert "1,000" in report  # Formatted with commas
        assert "500" in report
        assert "1,500" in report
        assert "$0.0004" in report  # Costs formatted

    @patch("src.token_counter.get_config")
    def test_includes_cache_savings(self, mock_config):
        """Report should show cache savings when applicable."""
        config_mock = Mock()
        config_mock.prompt_token_price_per_million = 0.15
        mock_config.return_value = config_mock

        cost_data = {
            "input_cost": 0.00006,
            "output_cost": 0.0003,
            "cache_cost": 0.000045,
            "total_cost": 0.000405,
            "tokens": {
                "prompt_tokens": 1000,
                "completion_tokens": 500,
                "cached_tokens": 600,
                "total_tokens": 1500,
            },
        }

        report = format_cost_report(cost_data)

        assert "Cache savings:" in report
        assert "%" in report  # Percentage shown

    def test_no_cache_no_savings_line(self):
        """Report should not show savings line if no caching."""
        cost_data = {
            "input_cost": 0.00015,
            "output_cost": 0.0003,
            "cache_cost": 0.0,
            "total_cost": 0.00045,
            "tokens": {
                "prompt_tokens": 1000,
                "completion_tokens": 500,
                "cached_tokens": 0,
                "total_tokens": 1500,
            },
        }

        report = format_cost_report(cost_data)

        assert "Cache savings:" not in report


class TestCheckCostAlerts:
    """Test suite for cost alert threshold checking."""

    @patch("src.token_counter.get_config")
    def test_no_alert_below_thresholds(self, mock_config):
        """Costs below all thresholds should return None."""
        config_mock = Mock()
        config_mock.cost_alert_threshold_1 = 10.0
        config_mock.cost_alert_threshold_2 = 50.0
        config_mock.cost_alert_threshold_3 = 100.0
        mock_config.return_value = config_mock

        alert = check_cost_alerts(5.0)
        assert alert is None

    @patch("src.token_counter.get_config")
    def test_info_alert_threshold_1(self, mock_config):
        """Cost exceeding threshold 1 should return info alert."""
        config_mock = Mock()
        config_mock.cost_alert_threshold_1 = 10.0
        config_mock.cost_alert_threshold_2 = 50.0
        config_mock.cost_alert_threshold_3 = 100.0
        mock_config.return_value = config_mock

        alert = check_cost_alerts(15.0)
        assert alert is not None
        assert "ℹ️ INFO" in alert
        assert "$15.00" in alert

    @patch("src.token_counter.get_config")
    def test_warning_alert_threshold_2(self, mock_config):
        """Cost exceeding threshold 2 should return warning alert."""
        config_mock = Mock()
        config_mock.cost_alert_threshold_1 = 10.0
        config_mock.cost_alert_threshold_2 = 50.0
        config_mock.cost_alert_threshold_3 = 100.0
        mock_config.return_value = config_mock

        alert = check_cost_alerts(60.0)
        assert alert is not None
        assert "⚠️ WARNING" in alert
        assert "$60.00" in alert

    @patch("src.token_counter.get_config")
    def test_critical_alert_threshold_3(self, mock_config):
        """Cost exceeding threshold 3 should return critical alert."""
        config_mock = Mock()
        config_mock.cost_alert_threshold_1 = 10.0
        config_mock.cost_alert_threshold_2 = 50.0
        config_mock.cost_alert_threshold_3 = 100.0
        mock_config.return_value = config_mock

        alert = check_cost_alerts(120.0)
        assert alert is not None
        assert "🚨 CRITICAL" in alert
        assert "$120.00" in alert

    @patch("src.token_counter.get_config")
    def test_exact_threshold_triggers_alert(self, mock_config):
        """Cost exactly at threshold should trigger alert."""
        config_mock = Mock()
        config_mock.cost_alert_threshold_1 = 10.0
        config_mock.cost_alert_threshold_2 = 50.0
        config_mock.cost_alert_threshold_3 = 100.0
        mock_config.return_value = config_mock

        alert = check_cost_alerts(10.0)  # Exactly at threshold
        assert alert is not None

    @patch("src.token_counter.get_config")
    def test_highest_threshold_takes_precedence(self, mock_config):
        """If multiple thresholds exceeded, highest should be returned."""
        config_mock = Mock()
        config_mock.cost_alert_threshold_1 = 10.0
        config_mock.cost_alert_threshold_2 = 50.0
        config_mock.cost_alert_threshold_3 = 100.0
        mock_config.return_value = config_mock

        # Cost exceeds all three thresholds
        alert = check_cost_alerts(150.0)
        assert "🚨 CRITICAL" in alert  # Should be critical, not warning or info
