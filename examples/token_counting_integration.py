#!/usr/bin/env python3
"""
Token Counting Integration Example

This example demonstrates how to use the token counting system
for pre-request token estimation and cost calculation.

Run this example:
    python examples/token_counting_integration.py
"""

from token_counter import TokenCounter


def example_basic_counting():
    """Example 1: Basic token counting."""
    print("=" * 60)
    print("Example 1: Basic Token Counting")
    print("=" * 60)

    counter = TokenCounter()

    # Simple message
    messages = [
        {"role": "user", "content": "Hello, how are you today?"}
    ]

    result = counter.count_tokens("gpt-5", messages)

    print(f"Model: {result.model}")
    print(f"Encoding: {result.encoding}")
    print(f"Total tokens: {result.count.total}")
    print(f"Breakdown: {result.breakdown}")
    print()


def example_with_cost_estimation():
    """Example 2: Token counting with cost estimation."""
    print("=" * 60)
    print("Example 2: Token Counting with Cost Estimation")
    print("=" * 60)

    counter = TokenCounter()

    messages = [
        {"role": "system", "content": "You are a helpful AI assistant"},
        {"role": "user", "content": "Write a short poem about Python programming"}
    ]

    # Count tokens and estimate cost
    result = counter.count_tokens("gpt-5", messages, estimate_cost=True)

    print(f"Total tokens: {result.count.total}")
    print(f"Estimated input cost: ${result.cost.input_usd:.6f}")
    print(f"Total cost: ${result.cost.total_usd:.6f}")
    print()


def example_with_tools():
    """Example 3: Token counting with tool definitions."""
    print("=" * 60)
    print("Example 3: Token Counting with Tools")
    print("=" * 60)

    counter = TokenCounter()

    messages = [
        {"role": "user", "content": "What's the weather in San Francisco?"}
    ]

    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get current weather for a location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "City name"
                        },
                        "units": {
                            "type": "string",
                            "enum": ["celsius", "fahrenheit"]
                        }
                    },
                    "required": ["location"]
                }
            }
        }
    ]

    result = counter.count_tokens("gpt-5", messages, tools=tools, estimate_cost=True)

    print(f"Message tokens: {result.breakdown['messages']}")
    print(f"Tool tokens: {result.breakdown['tools']}")
    print(f"Total tokens: {result.count.total}")
    print(f"Estimated cost: ${result.cost.total_usd:.6f}")
    print()


def example_cost_comparison():
    """Example 4: Cost comparison across models."""
    print("=" * 60)
    print("Example 4: Cost Comparison Across Models")
    print("=" * 60)

    counter = TokenCounter()

    messages = [
        {"role": "user", "content": "Explain quantum computing in simple terms"}
    ]

    models = ["gpt-5", "gpt-5-mini", "gpt-4o", "gpt-4o-mini"]

    print(f"{'Model':<15} {'Tokens':<10} {'Cost (Input)':<15}")
    print("-" * 45)

    for model in models:
        result = counter.count_tokens(model, messages, estimate_cost=True)
        print(f"{model:<15} {result.count.total:<10} ${result.cost.input_usd:<14.6f}")

    print()


def example_output_estimation():
    """Example 5: Total cost estimation including output."""
    print("=" * 60)
    print("Example 5: Total Cost Estimation (Input + Output)")
    print("=" * 60)

    counter = TokenCounter()

    messages = [
        {"role": "user", "content": "Write a 500-word essay about climate change"}
    ]

    # Count input and estimate total cost including expected output
    result = counter.count_and_estimate(
        model="gpt-5",
        messages=messages,
        estimated_output_tokens=600  # Estimated essay length
    )

    print(f"Input tokens: {result.count.total}")
    print(f"Estimated output tokens: 600")
    print(f"Input cost: ${result.cost.input_usd:.6f}")
    print(f"Output cost: ${result.cost.output_usd:.6f}")
    print(f"Total estimated cost: ${result.cost.total_usd:.6f}")
    print()


def example_pricing_lookup():
    """Example 6: Looking up model pricing."""
    print("=" * 60)
    print("Example 6: Model Pricing Lookup")
    print("=" * 60)

    counter = TokenCounter()

    models = ["gpt-5", "gpt-5-mini", "gpt-5-pro", "claude-4.5-sonnet"]

    for model in models:
        pricing = counter.get_model_pricing(model)
        print(f"\n{model}:")
        print(f"  Input:  ${pricing['input_per_million']:.2f} / 1M tokens")
        print(f"  Output: ${pricing['output_per_million']:.2f} / 1M tokens")
        print(f"  Cached: ${pricing['cached_input_per_million']:.2f} / 1M tokens")

    print()


def example_file_estimation():
    """Example 7: Token estimation with file inputs."""
    print("=" * 60)
    print("Example 7: File Token Estimation (PDF)")
    print("=" * 60)

    counter = TokenCounter()

    # Example with a PDF file
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "input_text", "text": "Please analyze this document"},
                {
                    "type": "input_file",
                    "filename": "report.pdf",
                    # In real usage, you'd have actual base64-encoded PDF data here
                    "file_data": "data:application/pdf;base64,JVBERi0xLjQK..."
                }
            ]
        }
    ]

    result = counter.count_tokens("gpt-5", messages, estimate_files=True, estimate_cost=True)

    print(f"Message tokens: {result.breakdown['messages']}")
    print(f"File tokens (estimated): {result.breakdown['files']}")
    print(f"Total tokens: {result.count.total}")
    print(f"File estimate: {result.file_estimate}")
    print(f"Total cost: ${result.cost.total_usd:.6f}")
    print()


def example_api_format_detection():
    """Example 8: Automatic API format detection."""
    print("=" * 60)
    print("Example 8: Automatic API Format Detection")
    print("=" * 60)

    counter = TokenCounter()

    # Responses API format
    responses_messages = [
        {
            "role": "user",
            "content": [
                {"type": "input_text", "text": "Hello"}
            ]
        }
    ]

    # Chat API format
    chat_messages = [
        {"role": "user", "content": "Hello"}
    ]

    result1 = counter.count_tokens("gpt-5", responses_messages)
    result2 = counter.count_tokens("gpt-4", chat_messages)

    print(f"Responses API message: {result1.count.total} tokens")
    print(f"Chat API message: {result2.count.total} tokens")
    print("\nBoth were automatically detected and processed correctly!")
    print()


def main():
    """Run all examples."""
    examples = [
        example_basic_counting,
        example_with_cost_estimation,
        example_with_tools,
        example_cost_comparison,
        example_output_estimation,
        example_pricing_lookup,
        example_file_estimation,
        example_api_format_detection,
    ]

    print("\n" + "=" * 60)
    print("Token Counting System - Integration Examples")
    print("=" * 60 + "\n")

    for example in examples:
        try:
            example()
        except Exception as e:
            print(f"Error in {example.__name__}: {e}\n")

    print("=" * 60)
    print("Examples complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
