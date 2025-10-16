# Token Counting API Reference

## TokenCounter

High-level facade for token counting and cost estimation.

### Methods

#### `__init__(encoding_resolver=None, cost_calculator=None)`

Initialize the token counter.

**Parameters:**
- `encoding_resolver` (Optional[EncodingResolver]): Custom encoding resolver
- `cost_calculator` (Optional[CostCalculator]): Custom cost calculator

#### `count_tokens(model, messages, tools=None, functions=None, estimate_files=False, estimate_cost=False, api_format=None)`

Count tokens for a request with automatic API format detection.

**Parameters:**
- `model` (str): Model name (e.g., "gpt-5", "gpt-4o")
- `messages` (List[Dict]): List of message dictionaries
- `tools` (Optional[List[Dict]]): Tool definitions
- `functions` (Optional[List[Dict]]): Function definitions (legacy)
- `estimate_files` (bool): Whether to estimate file tokens
- `estimate_cost` (bool): Whether to calculate cost
- `api_format` (Optional[str]): Force specific format ("responses" or "chat")

**Returns:** `TokenResult`

#### `estimate_cost(model, input_tokens, output_tokens=0, cached_tokens=0)`

Estimate cost for token usage.

**Parameters:**
- `model` (str): Model name
- `input_tokens` (int): Number of input tokens
- `output_tokens` (int): Estimated output tokens
- `cached_tokens` (int): Number of cached tokens

**Returns:** `CostEstimate`

#### `count_and_estimate(model, messages, estimated_output_tokens=0, tools=None, estimate_files=False)`

Count tokens and estimate total cost including output.

**Parameters:**
- `model` (str): Model name
- `messages` (List[Dict]): List of message dictionaries
- `estimated_output_tokens` (int): Expected response length
- `tools` (Optional[List[Dict]]): Tool definitions
- `estimate_files` (bool): Whether to estimate file tokens

**Returns:** `TokenResult` with cost estimate including output

#### `get_model_pricing(model)`

Get pricing information for a model.

**Parameters:**
- `model` (str): Model name

**Returns:** `Dict[str, float]` with input_per_million, output_per_million, cached_input_per_million

#### `get_encoding_name(model)`

Get encoding name for a model.

**Parameters:**
- `model` (str): Model name

**Returns:** `str` - Encoding name (e.g., "o200k_base")

---

## TokenValidator

Validates token counts against actual API usage.

### Methods

#### `__init__(counter=None)`

Initialize the validator.

**Parameters:**
- `counter` (Optional[TokenCounter]): TokenCounter instance

#### `validate_from_response(model, messages, response, tools=None, functions=None)`

Validate token count against actual API response.

**Parameters:**
- `model` (str): Model name used in request
- `messages` (List[Dict]): Messages sent to API
- `response` (Any): Response object from OpenAI API
- `tools` (Optional[List[Dict]]): Tool definitions
- `functions` (Optional[List[Dict]]): Function definitions

**Returns:** `ValidationResult`

#### `validate_from_usage_dict(model, messages, usage, tools=None)`

Validate against usage dictionary directly.

**Parameters:**
- `model` (str): Model name
- `messages` (List[Dict]): Messages sent to API
- `usage` (Dict[str, int]): Usage dictionary
- `tools` (Optional[List[Dict]]): Tool definitions

**Returns:** `ValidationResult`

#### `check_accuracy(validation, tolerance_pct=10.0)`

Check if validation result is within acceptable tolerance.

**Parameters:**
- `validation` (ValidationResult): Validation result to check
- `tolerance_pct` (float): Acceptable error percentage

**Returns:** `bool`

#### `batch_validate(validations)`

Analyze multiple validation results.

**Parameters:**
- `validations` (List[ValidationResult]): List of validation results

**Returns:** `Dict[str, Any]` with aggregate statistics

---

## Data Models

### TokenResult

Complete token counting result with breakdown.

**Fields:**
- `model` (str): Model name used for counting
- `encoding` (str): Encoding name (e.g., "o200k_base")
- `count` (TokenCount): Token counts
- `breakdown` (Dict[str, int]): Component breakdown
- `file_estimate` (Optional[TokenEstimate]): File token estimate if files present
- `cost` (Optional[CostEstimate]): Cost estimate if requested
- `metadata` (Dict): Additional metadata

### TokenCount

Token count breakdown.

**Fields:**
- `total` (int): Total tokens
- `billable` (int): Billable tokens (excluding cached)
- `cached` (int): Cached tokens

### CostEstimate

Cost estimate in USD.

**Fields:**
- `input_usd` (float): Input token cost
- `output_usd` (float): Output token cost
- `cached_input_usd` (float): Cached input token cost
- `total_usd` (float): Total cost

### TokenEstimate

Token estimate with confidence range.

**Fields:**
- `min_tokens` (int): Minimum estimated tokens
- `max_tokens` (int): Maximum estimated tokens
- `confidence` (Literal["high", "medium", "low"]): Confidence level
- `basis` (str): Explanation of how estimate was calculated

**Properties:**
- `midpoint` (int): Midpoint of estimate range

### ValidationResult

Result of token count validation.

**Fields:**
- `model` (str): Model name
- `estimated` (int): Estimated token count
- `actual` (int): Actual token count from API
- `delta` (int): Difference (estimated - actual)
- `delta_pct` (float): Percentage difference
- `cached_tokens` (int): Number of cached tokens
- `file_path` (Optional[str]): File path if applicable
- `timestamp` (str): ISO timestamp

**Properties:**
- `within_tolerance` (bool): True if delta is within ±10%

---

## Configuration

### Pricing Configuration (`config/pricing.yaml`)

Model-specific pricing in USD per million tokens:

```yaml
models:
  gpt-5:
    input_per_million: 2.50
    output_per_million: 10.00
    cached_input_per_million: 1.25
```

### Overhead Configuration (`config/message_overhead.yaml`)

Model-specific overhead parameters:

```yaml
defaults:
  tokens_per_message: 3
  tokens_per_name: 1
  reply_priming: 3
```

---

## Advanced Usage

### Custom Encoding Resolver

```python
from token_counter import EncodingResolver, TokenCounter

resolver = EncodingResolver()
counter = TokenCounter(encoding_resolver=resolver)
```

### Custom Cost Calculator

```python
from token_counter import CostCalculator, TokenCounter

cost_calc = CostCalculator(pricing_config_path="custom_pricing.yaml")
counter = TokenCounter(cost_calculator=cost_calc)
```

### Direct Calculator Access

```python
from token_counter import ResponsesAPICalculator

calculator = ResponsesAPICalculator()
result = calculator.count_request_tokens(
    model="gpt-5",
    messages=messages,
    estimate_files=True,
    calculate_cost=True
)
```

---

## Error Handling

### ConfigurationError

Raised when configuration files are missing or invalid.

```python
from token_counter.exceptions import ConfigurationError

try:
    counter = TokenCounter()
except ConfigurationError as e:
    print(f"Configuration error: {e}")
```

### InvalidMessageFormatError

Raised when message format is invalid.

```python
from token_counter.exceptions import InvalidMessageFormatError

try:
    result = counter.count_tokens("gpt-5", invalid_messages)
except InvalidMessageFormatError as e:
    print(f"Invalid message format: {e}")
```

---

For more examples, see [quickstart.md](quickstart.md) and [examples/token_counting_integration.py](../../examples/token_counting_integration.py).
