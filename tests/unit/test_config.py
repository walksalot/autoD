"""
Unit tests for configuration module.

Tests cover:
- Environment variable validation
- Type safety and constraints
- Immutability (frozen config)
- Singleton pattern
- Model validation (only approved Frontier models)
- Environment-specific properties
"""

import os
import pytest
from pydantic import ValidationError
from pathlib import Path

from src.config import Config, get_config, reset_config


@pytest.fixture(autouse=True)
def reset_env():
    """Reset environment and config before each test."""
    # Clear any existing config
    reset_config()

    # Save original env vars
    original_env = os.environ.copy()

    # Clear relevant env vars
    keys_to_clear = [
        "OPENAI_API_KEY",
        "OPENAI_MODEL",
        "ENVIRONMENT",
        "API_TIMEOUT_SECONDS",
        "MAX_RETRIES",
    ]
    for key in keys_to_clear:
        os.environ.pop(key, None)

    yield

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)
    reset_config()


class TestConfigValidation:
    """Test configuration validation rules."""

    def test_missing_api_key_raises_error(self, monkeypatch):
        """Test that missing API key raises ValidationError."""
        # Ensure API key is completely unset (including from shell environment)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("openai_api_key", raising=False)

        # Also prevent loading from ~/.OPENAI_API_KEY file
        # Mock both exists() and read_text() to prevent file loading
        def mock_exists(self):
            return False

        monkeypatch.setattr(Path, "exists", mock_exists)

        with pytest.raises(ValidationError) as exc_info:
            Config()

        assert "openai_api_key" in str(exc_info.value)
        assert "Field required" in str(exc_info.value)

    def test_api_key_min_length_validation(self):
        """Test that API key must be at least 20 characters."""
        os.environ["OPENAI_API_KEY"] = "sk-short"

        with pytest.raises(ValidationError) as exc_info:
            Config()

        assert "at least 20 characters" in str(exc_info.value)

    def test_valid_config_loads(self):
        """Test that valid configuration loads successfully."""
        os.environ["OPENAI_API_KEY"] = "sk-test-1234567890abcdef1234567890"

        config = Config()

        assert config.openai_api_key == "sk-test-1234567890abcdef1234567890"
        assert config.openai_model == "gpt-5-mini"
        assert config.environment == "development"
        assert config.api_timeout_seconds == 300
        assert config.max_retries == 5

    def test_custom_values_override_defaults(self):
        """Test that custom environment values override defaults."""
        os.environ.update(
            {
                "OPENAI_API_KEY": "sk-test-1234567890abcdef1234567890",
                "OPENAI_MODEL": "gpt-5",
                "API_TIMEOUT_SECONDS": "450",
                "MAX_RETRIES": "8",
                "BATCH_SIZE": "20",
            }
        )

        config = Config()

        assert config.openai_model == "gpt-5"
        assert config.api_timeout_seconds == 450
        assert config.max_retries == 8
        assert config.batch_size == 20


class TestModelValidation:
    """Test OpenAI model validation rules."""

    def test_approved_frontier_models_allowed(self):
        """Test that all approved Frontier models are accepted."""
        os.environ["OPENAI_API_KEY"] = "sk-test-1234567890abcdef1234567890"

        approved_models = [
            "gpt-5-mini",
            "gpt-5",
            "gpt-5-nano",
            "gpt-5-pro",
            "gpt-4.1",
        ]

        for model in approved_models:
            os.environ["OPENAI_MODEL"] = model
            reset_config()

            config = Config()
            assert config.openai_model == model

    def test_gpt4o_rejected(self):
        """Test that gpt-4o is explicitly rejected per CLAUDE.md."""
        os.environ.update(
            {
                "OPENAI_API_KEY": "sk-test-1234567890abcdef1234567890",
                "OPENAI_MODEL": "gpt-4o",
            }
        )

        with pytest.raises(ValidationError) as exc_info:
            Config()

        error_msg = str(exc_info.value)
        assert "gpt-4o" in error_msg
        assert "not allowed" in error_msg

    def test_chat_completion_models_rejected(self):
        """Test that non-Frontier models are rejected."""
        os.environ["OPENAI_API_KEY"] = "sk-test-1234567890abcdef1234567890"

        invalid_models = ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo"]

        for model in invalid_models:
            os.environ["OPENAI_MODEL"] = model
            reset_config()

            with pytest.raises(ValidationError):
                Config()


class TestImmutability:
    """Test configuration immutability (frozen after load)."""

    def test_config_is_frozen(self):
        """Test that config cannot be modified after instantiation."""
        os.environ["OPENAI_API_KEY"] = "sk-test-1234567890abcdef1234567890"

        config = Config()

        with pytest.raises(ValidationError):
            config.openai_model = "gpt-5"

        with pytest.raises(ValidationError):
            config.api_timeout_seconds = 600

    def test_original_values_preserved(self):
        """Test that original values remain unchanged."""
        os.environ["OPENAI_API_KEY"] = "sk-test-1234567890abcdef1234567890"

        config = Config()
        original_model = config.openai_model

        try:
            config.openai_model = "gpt-5"
        except ValidationError:
            pass

        assert config.openai_model == original_model


class TestSingletonPattern:
    """Test singleton pattern implementation."""

    def test_get_config_returns_singleton(self):
        """Test that get_config() returns the same instance."""
        os.environ["OPENAI_API_KEY"] = "sk-test-1234567890abcdef1234567890"

        config1 = get_config()
        config2 = get_config()

        assert config1 is config2
        assert id(config1) == id(config2)

    def test_reset_config_creates_new_instance(self):
        """Test that reset_config() allows loading new config."""
        os.environ["OPENAI_API_KEY"] = "sk-test-1234567890abcdef1234567890"

        config1 = get_config()
        config1_id = id(config1)

        reset_config()
        os.environ["OPENAI_MODEL"] = "gpt-5"

        config2 = get_config()
        config2_id = id(config2)

        assert config1_id != config2_id
        assert config2.openai_model == "gpt-5"


class TestNumericConstraints:
    """Test numeric field constraints."""

    def test_timeout_constraints(self):
        """Test API timeout must be between 30 and 600."""
        os.environ["OPENAI_API_KEY"] = "sk-test-1234567890abcdef1234567890"

        # Too low
        os.environ["API_TIMEOUT_SECONDS"] = "20"
        with pytest.raises(ValidationError):
            Config()

        # Too high
        os.environ["API_TIMEOUT_SECONDS"] = "700"
        reset_config()
        with pytest.raises(ValidationError):
            Config()

        # Valid
        os.environ["API_TIMEOUT_SECONDS"] = "300"
        reset_config()
        config = Config()
        assert config.api_timeout_seconds == 300

    def test_retry_constraints(self):
        """Test max retries must be between 1 and 10."""
        os.environ["OPENAI_API_KEY"] = "sk-test-1234567890abcdef1234567890"

        # Too low
        os.environ["MAX_RETRIES"] = "0"
        with pytest.raises(ValidationError):
            Config()

        # Too high
        os.environ["MAX_RETRIES"] = "15"
        reset_config()
        with pytest.raises(ValidationError):
            Config()

        # Valid
        os.environ["MAX_RETRIES"] = "5"
        reset_config()
        config = Config()
        assert config.max_retries == 5

    def test_batch_size_constraints(self):
        """Test batch size must be between 1 and 100."""
        os.environ["OPENAI_API_KEY"] = "sk-test-1234567890abcdef1234567890"

        # Too high
        os.environ["BATCH_SIZE"] = "150"
        with pytest.raises(ValidationError):
            Config()

        # Valid
        os.environ["BATCH_SIZE"] = "50"
        reset_config()
        config = Config()
        assert config.batch_size == 50


class TestEnvironmentProperties:
    """Test environment-specific properties."""

    def test_development_environment(self):
        """Test development environment properties."""
        os.environ.update(
            {
                "OPENAI_API_KEY": "sk-test-1234567890abcdef1234567890",
                "ENVIRONMENT": "development",
            }
        )

        config = Config()

        assert config.environment == "development"
        assert config.is_development is True
        assert config.is_staging is False
        assert config.is_production is False

    def test_staging_environment(self):
        """Test staging environment properties."""
        os.environ.update(
            {
                "OPENAI_API_KEY": "sk-test-1234567890abcdef1234567890",
                "ENVIRONMENT": "staging",
            }
        )

        config = Config()

        assert config.environment == "staging"
        assert config.is_development is False
        assert config.is_staging is True
        assert config.is_production is False

    def test_production_environment(self):
        """Test production environment properties."""
        os.environ.update(
            {
                "OPENAI_API_KEY": "sk-test-1234567890abcdef1234567890",
                "ENVIRONMENT": "production",
            }
        )

        config = Config()

        assert config.environment == "production"
        assert config.is_development is False
        assert config.is_staging is False
        assert config.is_production is True


class TestPathFields:
    """Test path field handling."""

    def test_log_file_path_is_path_object(self):
        """Test that log_file is a Path object."""
        os.environ["OPENAI_API_KEY"] = "sk-test-1234567890abcdef1234567890"

        config = Config()

        assert isinstance(config.log_file, Path)
        assert config.log_file == Path("logs/paper_autopilot.log")

    def test_vector_store_cache_file_is_path(self):
        """Test that vector_store_cache_file is a Path object."""
        os.environ["OPENAI_API_KEY"] = "sk-test-1234567890abcdef1234567890"

        config = Config()

        assert isinstance(config.vector_store_cache_file, Path)
        assert config.vector_store_cache_file == Path(".paper_autopilot_vs_id")


class TestSafeRepr:
    """Test safe __repr__ that redacts sensitive data."""

    def test_repr_redacts_api_key(self):
        """Test that __repr__ redacts the API key."""
        os.environ["OPENAI_API_KEY"] = "sk-test-1234567890abcdef1234567890"

        config = Config()
        repr_str = repr(config)

        # Should not contain full API key
        assert "sk-test-1234567890abcdef1234567890" not in repr_str
        # Should contain model and environment
        assert "gpt-5-mini" in repr_str
        assert "development" in repr_str

    def test_repr_redacts_database_password(self):
        """Test that __repr__ redacts database passwords."""
        os.environ.update(
            {
                "OPENAI_API_KEY": "sk-test-1234567890abcdef1234567890",
                "PAPER_AUTOPILOT_DB_URL": "postgresql://user:secret@localhost:5432/db",
            }
        )

        config = Config()
        repr_str = repr(config)

        # Should not contain the password
        assert "secret" not in repr_str
        # Should show *** for non-sqlite databases
        assert "db_url=***" in repr_str


class TestCaseInsensitiveEnvVars:
    """Test case-insensitive environment variable loading."""

    def test_uppercase_env_vars(self):
        """Test that UPPERCASE env vars work."""
        os.environ.update(
            {
                "OPENAI_API_KEY": "sk-test-1234567890abcdef1234567890",
                "OPENAI_MODEL": "gpt-5",
            }
        )

        config = Config()
        assert config.openai_model == "gpt-5"

    def test_lowercase_env_vars(self):
        """Test that lowercase env vars work."""
        os.environ.update(
            {
                "openai_api_key": "sk-test-1234567890abcdef1234567890",
                "openai_model": "gpt-5-nano",
            }
        )

        config = Config()
        assert config.openai_model == "gpt-5-nano"

    def test_mixed_case_env_vars(self):
        """Test that mixed case env vars work."""
        os.environ.update(
            {
                "OpenAI_API_Key": "sk-test-1234567890abcdef1234567890",
                "OpenAI_Model": "gpt-5-pro",
            }
        )

        config = Config()
        assert config.openai_model == "gpt-5-pro"


class TestCostConfiguration:
    """Test cost and pricing configuration fields."""

    def test_pricing_fields_have_defaults(self):
        """Test that pricing fields load with correct defaults."""
        os.environ["OPENAI_API_KEY"] = "sk-test-1234567890abcdef1234567890"

        config = Config()

        assert config.prompt_token_price_per_million == 0.15
        assert config.completion_token_price_per_million == 0.60
        assert config.cached_token_price_per_million == 0.075

    def test_cost_alert_thresholds_have_defaults(self):
        """Test that cost alert thresholds load with correct defaults."""
        os.environ["OPENAI_API_KEY"] = "sk-test-1234567890abcdef1234567890"

        config = Config()

        assert config.cost_alert_threshold_1 == 10.00
        assert config.cost_alert_threshold_2 == 50.00
        assert config.cost_alert_threshold_3 == 100.00

    def test_custom_pricing_overrides_defaults(self):
        """Test that custom pricing values override defaults."""
        os.environ.update(
            {
                "OPENAI_API_KEY": "sk-test-1234567890abcdef1234567890",
                "PROMPT_TOKEN_PRICE_PER_MILLION": "0.20",
                "COMPLETION_TOKEN_PRICE_PER_MILLION": "0.80",
                "CACHED_TOKEN_PRICE_PER_MILLION": "0.10",
            }
        )

        config = Config()

        assert config.prompt_token_price_per_million == 0.20
        assert config.completion_token_price_per_million == 0.80
        assert config.cached_token_price_per_million == 0.10

    def test_custom_cost_thresholds_override_defaults(self):
        """Test that custom cost thresholds override defaults."""
        os.environ.update(
            {
                "OPENAI_API_KEY": "sk-test-1234567890abcdef1234567890",
                "COST_ALERT_THRESHOLD_1": "5.00",
                "COST_ALERT_THRESHOLD_2": "25.00",
                "COST_ALERT_THRESHOLD_3": "75.00",
            }
        )

        config = Config()

        assert config.cost_alert_threshold_1 == 5.00
        assert config.cost_alert_threshold_2 == 25.00
        assert config.cost_alert_threshold_3 == 75.00

    def test_cost_thresholds_must_be_ascending(self):
        """Test that cost alert thresholds must be in ascending order."""
        os.environ.update(
            {
                "OPENAI_API_KEY": "sk-test-1234567890abcdef1234567890",
                "COST_ALERT_THRESHOLD_1": "50.00",
                "COST_ALERT_THRESHOLD_2": "30.00",  # Invalid: not ascending
                "COST_ALERT_THRESHOLD_3": "100.00",
            }
        )

        with pytest.raises(ValidationError) as exc_info:
            Config()

        error_msg = str(exc_info.value)
        assert "ascending order" in error_msg
        assert "threshold_1" in error_msg
        assert "threshold_2" in error_msg

    def test_equal_cost_thresholds_rejected(self):
        """Test that equal cost thresholds are rejected."""
        os.environ.update(
            {
                "OPENAI_API_KEY": "sk-test-1234567890abcdef1234567890",
                "COST_ALERT_THRESHOLD_1": "25.00",
                "COST_ALERT_THRESHOLD_2": "25.00",  # Equal to threshold_1
                "COST_ALERT_THRESHOLD_3": "75.00",
            }
        )

        with pytest.raises(ValidationError) as exc_info:
            Config()

        error_msg = str(exc_info.value)
        assert "ascending order" in error_msg

    def test_negative_pricing_rejected(self):
        """Test that negative pricing values are rejected."""
        os.environ.update(
            {
                "OPENAI_API_KEY": "sk-test-1234567890abcdef1234567890",
                "PROMPT_TOKEN_PRICE_PER_MILLION": "-0.15",
            }
        )

        with pytest.raises(ValidationError) as exc_info:
            Config()

        error_msg = str(exc_info.value)
        assert "greater than or equal to 0" in error_msg.lower()

    def test_negative_cost_threshold_rejected(self):
        """Test that negative cost thresholds are rejected."""
        os.environ.update(
            {
                "OPENAI_API_KEY": "sk-test-1234567890abcdef1234567890",
                "COST_ALERT_THRESHOLD_1": "-10.00",
            }
        )

        with pytest.raises(ValidationError) as exc_info:
            Config()

        error_msg = str(exc_info.value)
        assert "greater than or equal to 0" in error_msg.lower()

    def test_zero_pricing_allowed(self):
        """Test that zero pricing is allowed (for free tiers or testing)."""
        os.environ.update(
            {
                "OPENAI_API_KEY": "sk-test-1234567890abcdef1234567890",
                "PROMPT_TOKEN_PRICE_PER_MILLION": "0.0",
                "COMPLETION_TOKEN_PRICE_PER_MILLION": "0.0",
                "CACHED_TOKEN_PRICE_PER_MILLION": "0.0",
            }
        )

        config = Config()

        assert config.prompt_token_price_per_million == 0.0
        assert config.completion_token_price_per_million == 0.0
        assert config.cached_token_price_per_million == 0.0

    def test_all_21_environment_variables_present(self):
        """Test that all 21 environment variables from .env.example are supported."""
        os.environ.update(
            {
                # 1. OPENAI_API_KEY
                "OPENAI_API_KEY": "sk-test-1234567890abcdef1234567890",
                # 2. OPENAI_MODEL
                "OPENAI_MODEL": "gpt-5-mini",
                # 3. PAPER_AUTOPILOT_DB_URL
                "PAPER_AUTOPILOT_DB_URL": "sqlite:///test.db",
                # 4. API_TIMEOUT_SECONDS
                "API_TIMEOUT_SECONDS": "300",
                # 5. MAX_RETRIES
                "MAX_RETRIES": "5",
                # 6. RATE_LIMIT_RPM
                "RATE_LIMIT_RPM": "60",
                # 7. PROMPT_TOKEN_PRICE_PER_MILLION
                "PROMPT_TOKEN_PRICE_PER_MILLION": "0.15",
                # 8. COMPLETION_TOKEN_PRICE_PER_MILLION
                "COMPLETION_TOKEN_PRICE_PER_MILLION": "0.60",
                # 9. CACHED_TOKEN_PRICE_PER_MILLION
                "CACHED_TOKEN_PRICE_PER_MILLION": "0.075",
                # 10. COST_ALERT_THRESHOLD_1
                "COST_ALERT_THRESHOLD_1": "10.00",
                # 11. COST_ALERT_THRESHOLD_2
                "COST_ALERT_THRESHOLD_2": "50.00",
                # 12. COST_ALERT_THRESHOLD_3
                "COST_ALERT_THRESHOLD_3": "100.00",
                # 13. BATCH_SIZE
                "BATCH_SIZE": "10",
                # 14. MAX_WORKERS
                "MAX_WORKERS": "3",
                # 15. PROCESSING_TIMEOUT_PER_DOC
                "PROCESSING_TIMEOUT_PER_DOC": "60",
                # 16. LOG_LEVEL
                "LOG_LEVEL": "INFO",
                # 17. LOG_FORMAT
                "LOG_FORMAT": "json",
                # 18. LOG_FILE
                "LOG_FILE": "logs/test.log",
                # 19. LOG_MAX_BYTES
                "LOG_MAX_BYTES": "10485760",
                # 20. LOG_BACKUP_COUNT
                "LOG_BACKUP_COUNT": "5",
                # 21. VECTOR_STORE_NAME
                "VECTOR_STORE_NAME": "test_vector_store",
            }
        )

        config = Config()

        # Verify all 21 variables are accessible
        assert config.openai_api_key == "sk-test-1234567890abcdef1234567890"
        assert config.openai_model == "gpt-5-mini"
        assert config.paper_autopilot_db_url == "sqlite:///test.db"
        assert config.api_timeout_seconds == 300
        assert config.max_retries == 5
        assert config.rate_limit_rpm == 60
        assert config.prompt_token_price_per_million == 0.15
        assert config.completion_token_price_per_million == 0.60
        assert config.cached_token_price_per_million == 0.075
        assert config.cost_alert_threshold_1 == 10.00
        assert config.cost_alert_threshold_2 == 50.00
        assert config.cost_alert_threshold_3 == 100.00
        assert config.batch_size == 10
        assert config.max_workers == 3
        assert config.processing_timeout_per_doc == 60
        assert config.log_level == "INFO"
        assert config.log_format == "json"
        assert str(config.log_file) == "logs/test.log"
        assert config.log_max_bytes == 10485760
        assert config.log_backup_count == 5
        assert config.vector_store_name == "test_vector_store"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
