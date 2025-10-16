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

    def test_missing_api_key_raises_error(self):
        """Test that missing API key raises ValidationError."""
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
        os.environ.update({
            "OPENAI_API_KEY": "sk-test-1234567890abcdef1234567890",
            "OPENAI_MODEL": "gpt-5",
            "API_TIMEOUT_SECONDS": "450",
            "MAX_RETRIES": "8",
            "BATCH_SIZE": "20",
        })

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
        os.environ.update({
            "OPENAI_API_KEY": "sk-test-1234567890abcdef1234567890",
            "OPENAI_MODEL": "gpt-4o",
        })

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
        os.environ.update({
            "OPENAI_API_KEY": "sk-test-1234567890abcdef1234567890",
            "ENVIRONMENT": "development",
        })

        config = Config()

        assert config.environment == "development"
        assert config.is_development is True
        assert config.is_staging is False
        assert config.is_production is False

    def test_staging_environment(self):
        """Test staging environment properties."""
        os.environ.update({
            "OPENAI_API_KEY": "sk-test-1234567890abcdef1234567890",
            "ENVIRONMENT": "staging",
        })

        config = Config()

        assert config.environment == "staging"
        assert config.is_development is False
        assert config.is_staging is True
        assert config.is_production is False

    def test_production_environment(self):
        """Test production environment properties."""
        os.environ.update({
            "OPENAI_API_KEY": "sk-test-1234567890abcdef1234567890",
            "ENVIRONMENT": "production",
        })

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
        os.environ.update({
            "OPENAI_API_KEY": "sk-test-1234567890abcdef1234567890",
            "PAPER_AUTOPILOT_DB_URL": "postgresql://user:secret@localhost:5432/db",
        })

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
        os.environ.update({
            "OPENAI_API_KEY": "sk-test-1234567890abcdef1234567890",
            "OPENAI_MODEL": "gpt-5",
        })

        config = Config()
        assert config.openai_model == "gpt-5"

    def test_lowercase_env_vars(self):
        """Test that lowercase env vars work."""
        os.environ.update({
            "openai_api_key": "sk-test-1234567890abcdef1234567890",
            "openai_model": "gpt-5-nano",
        })

        config = Config()
        assert config.openai_model == "gpt-5-nano"

    def test_mixed_case_env_vars(self):
        """Test that mixed case env vars work."""
        os.environ.update({
            "OpenAI_API_Key": "sk-test-1234567890abcdef1234567890",
            "OpenAI_Model": "gpt-5-pro",
        })

        config = Config()
        assert config.openai_model == "gpt-5-pro"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
