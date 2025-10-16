#!/usr/bin/env python3
"""
Example usage of the configuration module.

This demonstrates best practices for using the config system:
- Loading configuration
- Accessing settings
- Using environment-specific properties
- Safe repr for logging
"""

import os

# Ensure we have a valid API key for demonstration
if "OPENAI_API_KEY" not in os.environ:
    os.environ["OPENAI_API_KEY"] = "sk-test-1234567890abcdef1234567890"

from src.config import get_config, reset_config


def main():
    """Demonstrate configuration module usage."""

    print("=" * 70)
    print("Configuration Module Usage Example")
    print("=" * 70)

    # Load configuration (singleton pattern)
    print("\n1. Loading configuration...")
    config = get_config()
    print(f"   ✓ Configuration loaded: {type(config).__name__}")

    # Access basic settings
    print("\n2. Basic settings:")
    print(f"   Model: {config.openai_model}")
    print(f"   Timeout: {config.api_timeout_seconds}s")
    print(f"   Max Retries: {config.max_retries}")
    print(f"   Batch Size: {config.batch_size}")
    print(f"   Rate Limit: {config.rate_limit_rpm} RPM")

    # Environment-specific properties
    print("\n3. Environment detection:")
    print(f"   Current Environment: {config.environment}")
    print(f"   Is Development: {config.is_development}")
    print(f"   Is Staging: {config.is_staging}")
    print(f"   Is Production: {config.is_production}")

    # Cost tracking configuration
    print("\n4. Cost tracking settings:")
    print(f"   Input Tokens: ${config.prompt_token_price_per_million}/M")
    print(f"   Output Tokens: ${config.completion_token_price_per_million}/M")
    print(f"   Cached Tokens: ${config.cached_token_price_per_million}/M")
    print(
        f"   Alert Thresholds: ${config.cost_alert_threshold_1}, "
        f"${config.cost_alert_threshold_2}, ${config.cost_alert_threshold_3}"
    )

    # Logging configuration
    print("\n5. Logging configuration:")
    print(f"   Log Level: {config.log_level}")
    print(f"   Log Format: {config.log_format}")
    print(f"   Log File: {config.log_file}")
    print(f"   Max Size: {config.log_max_bytes / 1024 / 1024:.1f}MB")
    print(f"   Backup Count: {config.log_backup_count}")

    # Database and file paths
    print("\n6. Storage configuration:")
    print(f"   Database: {config.paper_autopilot_db_url}")
    print(f"   Vector Store: {config.vector_store_name}")
    print(f"   Cache File: {config.vector_store_cache_file}")
    print(f"   Retention: {config.processed_retention_days} days")

    # Safe repr for logging (redacts sensitive data)
    print("\n7. Safe representation (for logging):")
    print(f"   {repr(config)}")

    # Singleton verification
    print("\n8. Singleton pattern verification:")
    config2 = get_config()
    print(f"   Same instance: {config is config2}")
    print(f"   config1 ID: {id(config)}")
    print(f"   config2 ID: {id(config2)}")

    # Demonstrate immutability
    print("\n9. Immutability demonstration:")
    try:
        config.openai_model = "gpt-4o"
        print("   ✗ Config was modified (shouldn't happen!)")
    except Exception as e:
        print(f"   ✓ Config is immutable: {type(e).__name__}")

    # Environment switching example
    print("\n10. Environment switching:")
    for env in ["development", "staging", "production"]:
        os.environ["ENVIRONMENT"] = env
        reset_config()
        c = get_config()
        print(
            f"   {env:12} -> dev={c.is_development}, "
            f"staging={c.is_staging}, prod={c.is_production}"
        )

    print("\n" + "=" * 70)
    print("Configuration module is ready for use!")
    print("=" * 70)


if __name__ == "__main__":
    main()
