# Token Counting Quickstart Guide

## Overview

The token counting system provides accurate token estimation and cost calculation for OpenAI API requests. It supports:

- **Accurate token counting** using tiktoken encodings
- **Cost estimation** based on current model pricing
- **File token estimation** for PDFs and other file inputs
- **Automatic API format detection** (Responses API vs Chat Completions)
- **Validation** against actual API usage

## Installation

The token counting module is included in the project. Required dependencies:

```bash
pip install tiktoken>=0.8.0 pyyaml>=6.0 pydantic>=2.10.4 PyPDF2>=3.0.1
```

## Basic Usage

### Simple Token Counting

```python
from token_counter import TokenCounter

counter = TokenCounter()

messages = [
    {"role": "user", "content": "Hello, how are you?"}
]

result = counter.count_tokens("gpt-5", messages)

print(f"Total tokens: {result.count.total}")
# Output: Total tokens: 8
```

### With Cost Estimation

```python
result = counter.count_tokens("gpt-5", messages, estimate_cost=True)

print(f"Tokens: {result.count.total}")
print(f"Cost: ${result.cost.total_usd:.6f}")
# Output:
# Tokens: 8
# Cost: $0.000020
```

### With Tool Definitions

```python
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get weather for a location",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string"}
                }
            }
        }
    }
]

result = counter.count_tokens("gpt-5", messages, tools=tools)

print(f"Message tokens: {result.breakdown['messages']}")
print(f"Tool tokens: {result.breakdown['tools']}")
print(f"Total: {result.count.total}")
```

## Estimating Response Costs

### Pre-Request Cost Estimation

```python
# Estimate cost for known token counts
cost = counter.estimate_cost(
    model="gpt-5",
    input_tokens=1000,
    output_tokens=500
)

print(f"Estimated total: ${cost.total_usd:.4f}")
# Output: Estimated total: $0.0075
```

### Including Expected Output

```python
# Count input and estimate total with expected output
result = counter.count_and_estimate(
    model="gpt-5",
    messages=messages,
    estimated_output_tokens=1000
)

print(f"Input cost: ${result.cost.input_usd:.6f}")
print(f"Output cost: ${result.cost.output_usd:.6f}")
print(f"Total: ${result.cost.total_usd:.6f}")
```

## File Token Estimation

### PDF Files

```python
messages = [
    {
        "role": "user",
        "content": [
            {"type": "input_text", "text": "Analyze this PDF"},
            {
                "type": "input_file",
                "filename": "document.pdf",
                "file_data": "data:application/pdf;base64,..."
            }
        ]
    }
]

result = counter.count_tokens("gpt-5", messages, estimate_files=True)

print(f"File estimate: {result.file_estimate}")
print(f"Confidence: {result.file_estimate.confidence}")
# Output:
# File estimate: 850-11000 tokens (high confidence)
# Confidence: high
```

## Cost Comparison

### Across Models

```python
models = ["gpt-5", "gpt-5-mini", "gpt-4o", "gpt-4o-mini"]

for model in models:
    result = counter.count_tokens(model, messages, estimate_cost=True)
    print(f"{model}: ${result.cost.input_usd:.6f}")

# Output:
# gpt-5: $0.000020
# gpt-5-mini: $0.000003
# gpt-4o: $0.000020
# gpt-4o-mini: $0.000001
```

## Validation

### Validate Against Actual API Usage

```python
from token_counter import TokenValidator
from openai import OpenAI

validator = TokenValidator()
client = OpenAI()

# Make actual API request
response = client.chat.completions.create(
    model="gpt-4",
    messages=messages
)

# Validate our estimate
validation = validator.validate_from_response(
    model="gpt-4",
    messages=messages,
    response=response
)

print(f"Estimated: {validation.estimated}")
print(f"Actual: {validation.actual}")
print(f"Delta: {validation.delta} ({validation.delta_pct:.1f}%)")
```

## Advanced Features

### Lookup Model Pricing

```python
pricing = counter.get_model_pricing("gpt-5")

print(f"Input: ${pricing['input_per_million']}/M tokens")
print(f"Output: ${pricing['output_per_million']}/M tokens")
# Output:
# Input: $2.50/M tokens
# Output: $10.00/M tokens
```

### Get Encoding Information

```python
encoding_name = counter.get_encoding_name("gpt-5")
print(f"Encoding: {encoding_name}")
# Output: Encoding: o200k_base
```

## Best Practices

1. **Always estimate cost before large batches** - Use `estimate_cost()` to predict costs
2. **Validate accuracy periodically** - Use `TokenValidator` to verify estimates
3. **Use file estimation for PDFs** - Set `estimate_files=True` when including files
4. **Consider output tokens** - Use `count_and_estimate()` for total cost prediction
5. **Cache your counter instance** - Reuse the same `TokenCounter` for better performance

## Common Patterns

### Pre-Request Cost Check

```python
def make_request_if_affordable(messages, max_cost_usd=0.01):
    counter = TokenCounter()

    result = counter.count_and_estimate(
        model="gpt-5",
        messages=messages,
        estimated_output_tokens=1000,  # Conservative estimate
    )

    if result.cost.total_usd <= max_cost_usd:
        # Make actual API request
        pass
    else:
        print(f"Cost ${result.cost.total_usd:.4f} exceeds budget")
```

### Batch Processing Budget

```python
def process_batch(documents, budget_usd=1.00):
    counter = TokenCounter()
    total_cost = 0
    processed = 0

    for doc in documents:
        messages = [{"role": "user", "content": doc}]
        result = counter.count_tokens("gpt-5", messages, estimate_cost=True)

        if total_cost + result.cost.input_usd <= budget_usd:
            # Process document
            total_cost += result.cost.input_usd
            processed += 1
        else:
            break

    print(f"Processed {processed} documents for ${total_cost:.4f}")
```

## Next Steps

- See [API Reference](api_reference.md) for complete API documentation
- Check [examples/token_counting_integration.py](../../examples/token_counting_integration.py) for more examples
- Review [config/pricing.yaml](../../config/pricing.yaml) for current pricing data
