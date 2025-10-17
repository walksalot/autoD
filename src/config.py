"""
Configuration management using Pydantic V2.
Validates environment variables and provides type-safe access to settings.

This module implements a production-grade configuration system with:
- Environment variable validation (fail-fast on missing required vars)
- Type safety with Pydantic V2 models
- Immutable configuration (frozen after load)
- Support for dev/staging/prod environments
- Singleton pattern for global config access

Usage:
    from src.config import get_config

    config = get_config()
    print(config.openai_model)  # gpt-5-mini
    print(config.api_timeout_seconds)  # 300
"""

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
from typing import Literal, Optional


class Config(BaseSettings):
    """
    Application configuration loaded from environment variables.

    All settings are validated on instantiation. Missing required variables
    will raise clear error messages. Use .env file or export variables.

    Attributes:
        openai_api_key: OpenAI API key (required)
        openai_model: Model to use (default: gpt-5-mini)
        paper_autopilot_db_url: Database connection URL
        api_timeout_seconds: Timeout for API calls (30-600s)
        max_retries: Maximum retry attempts (1-10)
        rate_limit_rpm: Rate limit in requests per minute
        batch_size: Number of PDFs to process in parallel
        environment: Deployment environment (dev/staging/prod)

    Example:
        >>> import os
        >>> os.environ["OPENAI_API_KEY"] = "sk-test-key"
        >>> config = Config()
        >>> config.openai_model
        'gpt-5-mini'
        >>> config.is_production
        False
    """

    # === OpenAI API Configuration ===
    openai_api_key: str = Field(
        ...,  # Required field
        description="OpenAI API key for Responses API access",
        min_length=20,
    )

    openai_model: str = Field(
        default="gpt-5-mini",
        description="OpenAI model to use (gpt-5-mini, gpt-5, gpt-5-nano, gpt-5-pro, gpt-4.1)",
    )

    @field_validator("openai_model")
    @classmethod
    def validate_model(cls, v: str) -> str:
        """
        Validate that only approved Frontier models are used.

        Per CLAUDE.md and OPERATING_RULES.md, only these models are allowed:
        - gpt-5 (best for coding and agentic tasks)
        - gpt-5-mini (faster, cost-efficient)
        - gpt-5-nano (fastest, most cost-efficient)
        - gpt-5-pro (smarter and more precise)
        - gpt-4.1 (smartest non-reasoning model)

        Raises:
            ValueError: If model is not in the approved list
        """
        allowed_models = {
            "gpt-5-mini",
            "gpt-5",
            "gpt-5-nano",
            "gpt-5-pro",
            "gpt-4.1",
        }
        if v not in allowed_models:
            raise ValueError(
                f"Model '{v}' not allowed. Must be one of: {', '.join(sorted(allowed_models))}. "
                "NEVER use gpt-4o or chat completions models per project requirements."
            )
        return v

    @model_validator(mode="before")
    @classmethod
    def load_openai_key_from_file(cls, values: dict):
        """
        Automatically load OPENAI_API_KEY from ~/.OPENAI_API_KEY when not set.

        This keeps tests/dev environments working without forcing contributors to
        export the variable manually, while still requiring a non-empty key.
        """
        key = values.get("openai_api_key")
        if key:
            return values

        key_path = Path.home() / ".OPENAI_API_KEY"
        if key_path.exists():
            file_key = key_path.read_text(encoding="utf-8").strip()
            if file_key:
                values["openai_api_key"] = file_key
        return values

    # === Database Configuration ===
    paper_autopilot_db_url: str = Field(
        default="sqlite:///paper_autopilot.db",
        description="Database connection URL",
    )

    # === API Configuration ===
    api_timeout_seconds: int = Field(
        default=300,
        description="Timeout for Responses API calls (seconds)",
        ge=30,
        le=600,
    )

    max_retries: int = Field(
        default=5,
        description="Maximum retry attempts for API calls",
        ge=1,
        le=10,
    )

    rate_limit_rpm: int = Field(
        default=60,
        description="Rate limit in requests per minute",
        ge=1,
        le=500,
    )

    max_output_tokens: int = Field(
        default=60000,
        description="Maximum output tokens for Responses API",
        ge=1000,
        le=100000,
    )

    # === Cost Configuration (for gpt-5-mini default pricing) ===
    prompt_token_price_per_million: float = Field(
        default=0.15,
        description="Price per 1M input tokens in USD (gpt-5-mini: $0.15)",
        ge=0.0,
    )

    completion_token_price_per_million: float = Field(
        default=0.60,
        description="Price per 1M output tokens in USD (gpt-5-mini: $0.60)",
        ge=0.0,
    )

    cached_token_price_per_million: float = Field(
        default=0.075,
        description="Price per 1M cached tokens in USD (50% discount)",
        ge=0.0,
    )

    cost_alert_threshold_1: float = Field(
        default=10.0,
        description="First cost alert threshold in USD (info level)",
        ge=0.0,
    )

    cost_alert_threshold_2: float = Field(
        default=50.0,
        description="Second cost alert threshold in USD (warning level)",
        ge=0.0,
    )

    cost_alert_threshold_3: float = Field(
        default=100.0,
        description="Third cost alert threshold in USD (critical level)",
        ge=0.0,
    )

    # === Processing Configuration ===
    batch_size: int = Field(
        default=10,
        description="Number of PDFs to process in parallel",
        ge=1,
        le=100,
    )

    max_workers: int = Field(
        default=3,
        description="Thread pool size for parallel processing",
        ge=1,
        le=20,
    )

    processing_timeout_per_doc: int = Field(
        default=60,
        description="Timeout per document (seconds)",
        ge=10,
        le=600,
    )

    # === Logging Configuration ===
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO",
        description="Logging level",
    )

    log_format: Literal["json", "text"] = Field(
        default="json",
        description="Log output format",
    )

    log_file: Path = Field(
        default=Path("logs/paper_autopilot.log"),
        description="Log file path",
    )

    log_max_bytes: int = Field(
        default=10485760,  # 10MB
        description="Maximum log file size before rotation",
        ge=1048576,  # 1MB minimum
    )

    log_backup_count: int = Field(
        default=5,
        description="Number of backup log files to keep",
        ge=1,
        le=50,
    )

    # === Vector Store Configuration ===
    vector_store_name: str = Field(
        default="paper_autopilot_docs",
        description="OpenAI vector store name",
    )

    vector_store_cache_file: Path = Field(
        default=Path(".paper_autopilot_vs_id"),
        description="Cache file for vector store ID",
    )

    vector_store_upload_timeout: int = Field(
        default=300,
        description="Timeout for file upload processing (seconds)",
        ge=60,
        le=600,
    )

    vector_store_max_concurrent_uploads: int = Field(
        default=5,
        description="Maximum concurrent file uploads to vector store",
        ge=1,
        le=20,
    )

    # === Embedding Configuration ===
    embedding_model: str = Field(
        default="text-embedding-3-small",
        description="OpenAI embedding model (text-embedding-3-small, text-embedding-3-large)",
    )

    @field_validator("embedding_model")
    @classmethod
    def validate_embedding_model(cls, v: str) -> str:
        """Validate embedding model is supported."""
        allowed = {
            "text-embedding-3-small",
            "text-embedding-3-large",
            "text-embedding-ada-002",
        }
        if v not in allowed:
            raise ValueError(
                f"Embedding model '{v}' not supported. "
                f"Must be one of: {', '.join(sorted(allowed))}"
            )
        return v

    embedding_dimension: int = Field(
        default=1536,
        description="Embedding vector dimension (512, 1536, or 3072 for text-embedding-3)",
        ge=512,
        le=3072,
    )

    embedding_batch_size: int = Field(
        default=100,
        description="Batch size for embedding generation (max 100 per OpenAI API)",
        ge=1,
        le=100,
    )

    # === Semantic Search Configuration ===
    search_default_top_k: int = Field(
        default=5,
        description="Default number of results for semantic search",
        ge=1,
        le=50,
    )

    search_max_top_k: int = Field(
        default=20,
        description="Maximum allowed top_k for search queries",
        ge=1,
        le=100,
    )

    search_relevance_threshold: float = Field(
        default=0.7,
        description="Minimum cosine similarity score for search results",
        ge=0.0,
        le=1.0,
    )

    # === Vector Cache Configuration ===
    vector_cache_enabled: bool = Field(
        default=True,
        description="Enable embedding vector caching in database",
    )

    vector_cache_ttl_days: int = Field(
        default=7,
        description="Time-to-live for cached embeddings (days)",
        ge=1,
        le=365,
    )

    vector_cache_max_size_mb: int = Field(
        default=1024,
        description="Maximum cache size in megabytes",
        ge=100,
        le=10240,
    )

    vector_cache_hit_rate_target: float = Field(
        default=0.8,
        description="Target cache hit rate (0.8 = 80%)",
        ge=0.5,
        le=1.0,
    )

    # === File Management ===
    processed_retention_days: int = Field(
        default=30,
        description="Days to retain processed PDFs",
        ge=1,
        le=365,
    )

    failed_retry_attempts: int = Field(
        default=3,
        description="Retry attempts for failed documents",
        ge=1,
        le=10,
    )

    # === Environment ===
    environment: Literal["development", "staging", "production"] = Field(
        default="development",
        description="Deployment environment",
    )

    paper_autopilot_version: str = Field(
        default="1.0.0",
        description="Paper Autopilot version",
    )

    # === Pydantic Configuration ===
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,  # Allow OPENAI_API_KEY or openai_api_key
        frozen=True,  # Immutable after instantiation
        extra="ignore",  # Ignore unknown env vars
    )

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == "development"

    @property
    def is_staging(self) -> bool:
        """Check if running in staging environment."""
        return self.environment == "staging"

    def __repr__(self) -> str:
        """
        Safe repr that redacts sensitive fields.

        Returns:
            String representation with API key redacted
        """
        # Redact API key
        key_preview = (
            f"{self.openai_api_key[:7]}...{self.openai_api_key[-4:]}"
            if len(self.openai_api_key) > 20
            else "***"
        )

        # Redact database password if present
        db_url = self.paper_autopilot_db_url
        if "postgresql" in db_url or "mysql" in db_url:
            # Hide password in connection string
            db_url = "***"

        return (
            f"Config("
            f"api_key={key_preview}, "
            f"model={self.openai_model}, "
            f"environment={self.environment}, "
            f"db_url={db_url}, "
            f"timeout={self.api_timeout_seconds}s"
            f")"
        )


# Singleton instance (lazy loaded)
_config: Optional[Config] = None


def get_config() -> Config:
    """
    Get the global configuration instance.

    Configuration is loaded once and cached. Subsequent calls return
    the same instance (singleton pattern).

    Returns:
        Validated and frozen Config instance

    Raises:
        ValidationError: If required environment variables are missing
                        or validation fails

    Example:
        >>> from src.config import get_config
        >>> config = get_config()
        >>> print(config.openai_model)
        gpt-5-mini
    """
    global _config
    if _config is None:
        _config = Config()  # type: ignore[call-arg]
    return _config


def reset_config() -> None:
    """
    Reset the global configuration instance.

    Useful for testing with different configurations or when
    environment variables change during runtime.

    Example:
        >>> import os
        >>> from src.config import reset_config, get_config
        >>> os.environ["OPENAI_MODEL"] = "gpt-5"
        >>> reset_config()
        >>> config = get_config()
        >>> print(config.openai_model)
        gpt-5
    """
    global _config
    _config = None


# Example usage and testing
if __name__ == "__main__":
    import os
    import sys

    print("=" * 70)
    print("Phase 1: Configuration Module Validation")
    print("=" * 70)

    test_results = {
        "missing_api_key_raises_error": False,
        "config_loads": False,
        "invalid_model_rejected": False,
        "config_is_immutable": False,
        "singleton_pattern_works": False,
    }

    # Test 1: Missing API key should raise error
    print("\n[Test 1] Missing API key validation...")
    print("-" * 70)
    # Ensure API key is not set
    if "OPENAI_API_KEY" in os.environ:
        del os.environ["OPENAI_API_KEY"]

    try:
        config = Config()  # type: ignore[call-arg]
        print("❌ FAIL: Should have raised ValidationError")
        print("   Issue: Config loaded without required OPENAI_API_KEY")
    except Exception as e:
        print(f"✅ PASS: Raised {type(e).__name__}")
        print(f"   Error message: {str(e)[:100]}...")
        test_results["missing_api_key_raises_error"] = True

    # Test 2: With valid API key
    print("\n[Test 2] Valid configuration loading...")
    print("-" * 70)
    os.environ["OPENAI_API_KEY"] = "sk-test-key-1234567890abcdef1234567890"
    reset_config()

    try:
        config = Config()  # type: ignore[call-arg]
        print("✅ PASS: Config loaded successfully")
        print(f"   Model: {config.openai_model}")
        print(f"   Environment: {config.environment}")
        print(f"   Timeout: {config.api_timeout_seconds}s")
        print(f"   Batch Size: {config.batch_size}")
        print(f"   Max Retries: {config.max_retries}")
        print(f"   Log Level: {config.log_level}")
        print(f"   Is Production: {config.is_production}")
        print(f"   Is Development: {config.is_development}")
        print(f"   Repr: {config}")
        test_results["config_loads"] = True
    except Exception as e:
        print(f"❌ FAIL: {type(e).__name__}: {e}")

    # Test 3: Invalid model (gpt-4o should be rejected)
    print("\n[Test 3] Invalid model rejection...")
    print("-" * 70)
    os.environ["OPENAI_MODEL"] = "gpt-4o"  # Not allowed per CLAUDE.md
    reset_config()

    try:
        config = Config()  # type: ignore[call-arg]
        print("❌ FAIL: Should have rejected gpt-4o")
        print("   Issue: gpt-4o is explicitly forbidden per project requirements")
    except Exception as e:
        print("✅ PASS: Rejected invalid model")
        print(f"   Error type: {type(e).__name__}")
        print(f"   Error message: {str(e)[:150]}...")
        test_results["invalid_model_rejected"] = True

    # Test 4: Immutability (config should be frozen)
    print("\n[Test 4] Configuration immutability...")
    print("-" * 70)
    os.environ["OPENAI_MODEL"] = "gpt-5-mini"  # Valid model
    reset_config()
    config = Config()  # type: ignore[call-arg]

    try:
        config.openai_model = "gpt-4o"  # Try to modify
        print("❌ FAIL: Config should be frozen")
        print("   Issue: Config was modified after instantiation")
    except Exception as e:
        print("✅ PASS: Config is immutable")
        print(f"   Error type: {type(e).__name__}")
        print("   Cannot modify frozen config")
        test_results["config_is_immutable"] = True

    # Test 5: Singleton pattern
    print("\n[Test 5] Singleton pattern validation...")
    print("-" * 70)
    reset_config()
    config1 = get_config()
    config2 = get_config()

    if config1 is config2:
        print("✅ PASS: get_config() returns same instance")
        print(f"   config1 id: {id(config1)}")
        print(f"   config2 id: {id(config2)}")
        print("   Both references point to identical object")
        test_results["singleton_pattern_works"] = True
    else:
        print("❌ FAIL: get_config() should return singleton")
        print(f"   config1 id: {id(config1)}")
        print(f"   config2 id: {id(config2)}")

    # Test 6: Environment-specific properties
    print("\n[Test 6] Environment-specific properties...")
    print("-" * 70)
    for env in ["development", "staging", "production"]:
        os.environ["ENVIRONMENT"] = env
        reset_config()
        config = get_config()
        print(
            f"   {env}: is_production={config.is_production}, "
            f"is_staging={config.is_staging}, is_development={config.is_development}"
        )

    # Test 7: Numeric constraints
    print("\n[Test 7] Numeric constraints validation...")
    print("-" * 70)
    os.environ["API_TIMEOUT_SECONDS"] = "1000"  # Too high (max 600)
    reset_config()

    try:
        config = Config()  # type: ignore[call-arg]
        print("❌ FAIL: Should reject timeout > 600")
    except Exception as e:
        print("✅ PASS: Rejected invalid timeout")
        print(f"   Error: {str(e)[:100]}...")

    # Final Summary
    print("\n" + "=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)

    passed = sum(test_results.values())
    total = len(test_results)

    for test_name, result in test_results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")

    print("-" * 70)
    print(f"Results: {passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All validation gates passed!")
        print("Phase 1 configuration module is ready for production use.")
        sys.exit(0)
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        print("Please review failures above.")
        sys.exit(1)
