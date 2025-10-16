# Phase 1: Configuration Module Documentation

## Overview

Phase 1 implements a production-grade configuration management system using Pydantic V2. The module provides:

- **Type-safe configuration** with validation
- **Fail-fast validation** for missing/invalid environment variables
- **Immutable configuration** (frozen after load)
- **Singleton pattern** for global config access
- **Environment-specific properties** (dev/staging/prod)
- **Approved model validation** (only Frontier models)

## Module Location

```
src/config.py
```

## Key Features

### 1. Environment Variable Validation

All configuration is loaded from environment variables with strict validation:

```python
from src.config import get_config

# Will raise ValidationError if OPENAI_API_KEY is missing
config = get_config()
```

**Required Variables:**
- `OPENAI_API_KEY` (minimum 20 characters)

**Optional Variables with Defaults:**
- `OPENAI_MODEL=gpt-5-mini`
- `API_TIMEOUT_SECONDS=300`
- `MAX_RETRIES=5`
- `BATCH_SIZE=10`
- `ENVIRONMENT=development`
- ... (see `.env.example` for complete list)

### 2. Type Safety

All settings are strongly typed with Pydantic V2:

```python
config.api_timeout_seconds  # int (validated: 30-600)
config.max_retries          # int (validated: 1-10)
config.log_file             # Path object
config.environment          # Literal["development", "staging", "production"]
```

### 3. Model Validation

Only approved Frontier models are allowed per CLAUDE.md:

**Allowed Models:**
- `gpt-5-mini` (default, cost-efficient)
- `gpt-5` (best for coding/agentic tasks)
- `gpt-5-nano` (fastest)
- `gpt-5-pro` (smartest, most precise)
- `gpt-4.1` (smartest non-reasoning)

**Explicitly Forbidden:**
- `gpt-4o` ❌ (per project requirements)
- `gpt-3.5-turbo` ❌
- Any Chat Completions models ❌

```python
# This will raise ValidationError
os.environ["OPENAI_MODEL"] = "gpt-4o"
config = get_config()  # ❌ Raises: "Model 'gpt-4o' not allowed..."
```

### 4. Immutability

Configuration is frozen after instantiation:

```python
config = get_config()

# This will raise ValidationError
config.openai_model = "gpt-5"  # ❌ Cannot modify frozen config
```

### 5. Singleton Pattern

`get_config()` returns the same instance across the application:

```python
config1 = get_config()
config2 = get_config()

assert config1 is config2  # ✓ Same object in memory
```

### 6. Environment-Specific Properties

Convenient properties for environment checks:

```python
config = get_config()

if config.is_production:
    # Production-only logic
    enable_monitoring()

if config.is_development:
    # Dev-only features
    enable_debug_logging()
```

### 7. Safe Repr

The `__repr__` method redacts sensitive data for safe logging:

```python
config = get_config()
logger.info(f"Config loaded: {config}")
# Output: Config(api_key=sk-test...1234, model=gpt-5-mini, ...)
```

## Usage Examples

### Basic Usage

```python
from src.config import get_config

# Load configuration
config = get_config()

# Access settings
print(f"Using model: {config.openai_model}")
print(f"API timeout: {config.api_timeout_seconds}s")
print(f"Max retries: {config.max_retries}")
```

### Environment Detection

```python
from src.config import get_config

config = get_config()

if config.is_production:
    # Use production settings
    log_level = "WARNING"
    enable_monitoring = True
elif config.is_development:
    # Use development settings
    log_level = "DEBUG"
    enable_monitoring = False
```

### Testing with Different Configs

```python
import os
from src.config import get_config, reset_config

# Test with custom settings
os.environ["OPENAI_MODEL"] = "gpt-5"
os.environ["BATCH_SIZE"] = "20"

reset_config()  # Clear cached config
config = get_config()

assert config.openai_model == "gpt-5"
assert config.batch_size == 20
```

### Cost Tracking

```python
from src.config import get_config

config = get_config()

# Calculate costs
input_tokens = 1000000  # 1M tokens
cost = (input_tokens / 1_000_000) * config.prompt_token_price_per_million
print(f"Cost for 1M input tokens: ${cost:.2f}")

# Check if cost exceeds alert threshold
if cost > config.cost_alert_threshold_1:
    send_cost_alert(cost)
```

## Configuration Reference

### API Configuration

| Variable | Type | Default | Range | Description |
|----------|------|---------|-------|-------------|
| `OPENAI_API_KEY` | str | *required* | ≥20 chars | OpenAI API key |
| `OPENAI_MODEL` | str | `gpt-5-mini` | See above | Model to use |
| `API_TIMEOUT_SECONDS` | int | `300` | 30-600 | API timeout |
| `MAX_RETRIES` | int | `5` | 1-10 | Retry attempts |
| `RATE_LIMIT_RPM` | int | `60` | 1-500 | Requests per minute |

### Processing Configuration

| Variable | Type | Default | Range | Description |
|----------|------|---------|-------|-------------|
| `BATCH_SIZE` | int | `10` | 1-100 | Parallel PDFs |
| `MAX_WORKERS` | int | `3` | 1-20 | Thread pool size |
| `PROCESSING_TIMEOUT_PER_DOC` | int | `60` | 10-600 | Timeout per doc |

### Cost Configuration

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `PROMPT_TOKEN_PRICE_PER_MILLION` | float | `0.15` | Input token cost |
| `COMPLETION_TOKEN_PRICE_PER_MILLION` | float | `0.60` | Output token cost |
| `CACHED_TOKEN_PRICE_PER_MILLION` | float | `0.075` | Cached token cost |
| `COST_ALERT_THRESHOLD_1` | float | `10.0` | First alert ($) |
| `COST_ALERT_THRESHOLD_2` | float | `50.0` | Second alert ($) |
| `COST_ALERT_THRESHOLD_3` | float | `100.0` | Third alert ($) |

### Logging Configuration

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `LOG_LEVEL` | str | `INFO` | DEBUG/INFO/WARNING/ERROR |
| `LOG_FORMAT` | str | `json` | json or text |
| `LOG_FILE` | Path | `logs/paper_autopilot.log` | Log file path |
| `LOG_MAX_BYTES` | int | `10485760` | Max size (10MB) |
| `LOG_BACKUP_COUNT` | int | `5` | Backup files |

### Environment

| Variable | Type | Default | Options |
|----------|------|---------|---------|
| `ENVIRONMENT` | str | `development` | development/staging/production |

## Validation Gates

All validation gates passed successfully:

1. ✅ **Missing API key raises error** - ValidationError with clear message
2. ✅ **Config loads with valid API key** - All settings accessible
3. ✅ **Invalid model rejected** - gpt-4o and others rejected
4. ✅ **Config is immutable** - Cannot modify after instantiation
5. ✅ **Singleton pattern works** - Same instance returned

## Testing

Run the comprehensive test suite:

```bash
# Run all config tests
python3 -m pytest tests/unit/test_config.py -v

# Run specific test class
python3 -m pytest tests/unit/test_config.py::TestModelValidation -v

# Run built-in validation
python3 src/config.py
```

**Test Coverage:**
- 24 unit tests
- 100% coverage of config module
- All validation rules tested
- Model policy enforcement tested
- Immutability and singleton pattern verified

## Integration

The config module integrates with:

- **Logging** (`src/logging_config.py`): Uses config for log level, format, and file paths
- **Database** (Phase 2): Will use `paper_autopilot_db_url`
- **API Client** (Phase 5): Will use `openai_api_key`, `openai_model`, timeout settings
- **Cost Tracking** (Phase 8): Will use token pricing configuration

## Error Handling

The module provides clear error messages for common issues:

### Missing API Key

```
ValidationError: 1 validation error for Config
openai_api_key
  Field required [type=missing]
```

### Invalid Model

```
ValidationError: 1 validation error for Config
openai_model
  Value error, Model 'gpt-4o' not allowed. Must be one of: gpt-4.1, gpt-5,
  gpt-5-mini, gpt-5-nano, gpt-5-pro. NEVER use gpt-4o or chat completions
  models per project requirements.
```

### Out of Range Value

```
ValidationError: 1 validation error for Config
api_timeout_seconds
  Input should be less than or equal to 600 [type=less_than_equal]
```

## Best Practices

1. **Load config once** at application startup
2. **Use singleton pattern** via `get_config()`
3. **Don't modify config** after loading (it's frozen)
4. **Use environment variables** for configuration
5. **Use `.env` file** for local development
6. **Test with `reset_config()`** when changing env vars in tests
7. **Log config safely** using `repr(config)` to redact secrets

## Next Phases

Phase 1 configuration module enables:

- ✅ **Phase 2: Database Models** - Use `paper_autopilot_db_url`
- ✅ **Phase 3: JSON Schema** - No dependencies
- ✅ **Phase 4: Prompts** - No dependencies
- ✅ **Phase 5: API Client** - Use model, key, timeout settings
- ✅ **Phase 8: Cost Tracking** - Use token pricing configuration

## Files Created

- `/Users/krisstudio/Developer/Projects/autoD/src/config.py` (465 lines)
- `/Users/krisstudio/Developer/Projects/autoD/tests/unit/test_config.py` (24 tests)
- `/Users/krisstudio/Developer/Projects/autoD/examples/config_usage.py` (demonstration)
- `/Users/krisstudio/Developer/Projects/autoD/docs/phase1_config_documentation.md` (this file)

## Version

- **Phase:** 1
- **Module:** Configuration Management
- **Status:** ✅ Complete
- **Tests:** 24/24 passed
- **Validation Gates:** 5/5 passed
- **Python Version:** 3.9.6+
- **Pydantic Version:** 2.11.5
