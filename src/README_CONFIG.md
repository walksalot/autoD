# Configuration Module Quick Reference

## Import

```python
from src.config import get_config
```

## Basic Usage

```python
# Load configuration (singleton)
config = get_config()

# Access settings
print(config.openai_model)        # gpt-5-mini
print(config.api_timeout_seconds)  # 300
print(config.max_retries)          # 5
```

## Required Environment Variables

```bash
export OPENAI_API_KEY=sk-your-key-here  # Required, minimum 20 chars
```

## Optional Environment Variables

See `.env.example` for complete list. Key defaults:

```bash
OPENAI_MODEL=gpt-5-mini          # Model to use
API_TIMEOUT_SECONDS=300          # 5 minutes
MAX_RETRIES=5                    # Retry attempts
BATCH_SIZE=10                    # Parallel processing
ENVIRONMENT=development          # dev/staging/production
```

## Approved Models

Only Frontier models are allowed (per CLAUDE.md):

✅ `gpt-5-mini` (default, cost-efficient)
✅ `gpt-5` (best for coding/agentic tasks)
✅ `gpt-5-nano` (fastest)
✅ `gpt-5-pro` (smartest, most precise)
✅ `gpt-4.1` (smartest non-reasoning)

❌ `gpt-4o` **FORBIDDEN** per project requirements
❌ `gpt-3.5-turbo`, `gpt-4`, `gpt-4-turbo`

## Environment Detection

```python
config = get_config()

if config.is_production:
    # Production-only code
    enable_monitoring()

if config.is_development:
    # Dev-only code
    enable_debug_logging()

if config.is_staging:
    # Staging-only code
    enable_beta_features()
```

## Cost Tracking

```python
config = get_config()

# Calculate token costs
input_cost = (input_tokens / 1_000_000) * config.prompt_token_price_per_million
output_cost = (output_tokens / 1_000_000) * config.completion_token_price_per_million
cached_cost = (cached_tokens / 1_000_000) * config.cached_token_price_per_million

total_cost = input_cost + output_cost + cached_cost

# Check alert thresholds
if total_cost > config.cost_alert_threshold_1:
    send_cost_alert(total_cost)
```

## Features

- ✅ **Type-safe**: Pydantic V2 validation
- ✅ **Fail-fast**: Missing variables raise clear errors
- ✅ **Immutable**: Frozen after load (cannot modify)
- ✅ **Singleton**: Same instance across application
- ✅ **Safe logging**: repr() redacts sensitive data
- ✅ **Model validation**: Only approved Frontier models
- ✅ **Environment detection**: dev/staging/prod properties
- ✅ **Case-insensitive**: OPENAI_API_KEY or openai_api_key both work

## Testing

```bash
# Run all config tests
python3 -m pytest tests/unit/test_config.py -v

# Run built-in validation
python3 src/config.py

# Test with different config
export OPENAI_MODEL=gpt-5
python3 -c "from src.config import get_config, reset_config; reset_config(); print(get_config().openai_model)"
```

## Important Notes

1. **Config is frozen** - Cannot modify after loading
2. **Use singleton pattern** - Always use `get_config()`
3. **Model policy enforced** - gpt-4o and Chat Completions blocked
4. **Case-insensitive env vars** - OPENAI_API_KEY or openai_api_key work
5. **Safe for logging** - `repr(config)` redacts secrets

## Common Patterns

### Load at startup

```python
# app.py
from src.config import get_config

config = get_config()  # Load once
```

### Environment-specific behavior

```python
config = get_config()

timeout = 600 if config.is_production else 300
log_level = "WARNING" if config.is_production else "DEBUG"
```

### Reset for testing

```python
import os
from src.config import get_config, reset_config

# Change env vars
os.environ["OPENAI_MODEL"] = "gpt-5"
reset_config()  # Clear cached config

# Load new config
config = get_config()
assert config.openai_model == "gpt-5"
```

## Documentation

- **Full Documentation**: `/Users/krisstudio/Developer/Projects/autoD/docs/phase1_config_documentation.md`
- **Usage Example**: `/Users/krisstudio/Developer/Projects/autoD/examples/config_usage.py`
- **Tests**: `/Users/krisstudio/Developer/Projects/autoD/tests/unit/test_config.py`
- **Handoff Report**: `/Users/krisstudio/Developer/Projects/autoD/docs/phase1_handoff.json`

## Quick Validation

```bash
# Test import
python3 -c "from src.config import get_config; print('✓ Import works')"

# Test with API key
OPENAI_API_KEY=sk-test-1234567890abcdef1234567890 python3 -c "from src.config import get_config; c = get_config(); print(f'✓ Config loaded: {c.openai_model}')"

# Run tests
python3 -m pytest tests/unit/test_config.py -q
```

## Support

For issues or questions about the configuration module:

1. Check `/Users/krisstudio/Developer/Projects/autoD/docs/phase1_config_documentation.md`
2. Review test examples in `/Users/krisstudio/Developer/Projects/autoD/tests/unit/test_config.py`
3. Run example script: `PYTHONPATH=. python3 examples/config_usage.py`
