#!/usr/bin/env python3
"""
Token Counting and Cost Calculation Demo

Demonstrates the complete workflow for:
1. Counting tokens in API requests using tiktoken
2. Calculating costs based on GPT-5 pricing
3. Tracking cumulative costs across multiple requests
4. Logging token/cost metrics in structured JSON format

Usage:
    python examples/token_cost_demo.py
"""

import sys
from pathlib import Path

# Add src/ to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from token_counter import EncodingResolver, ResponsesAPICalculator
from src.cost_calculator import (
    calculate_cost,
    format_cost_summary,
    CostTracker,
    estimate_cost_from_tokens,
)
from src.logging_config import setup_logging


def demo_basic_token_counting():
    """Demo 1: Basic token counting with tiktoken."""
    print("=" * 70)
    print("DEMO 1: Basic Token Counting")
    print("=" * 70)

    resolver = EncodingResolver()
    encoding = resolver.get_encoding("gpt-5")

    text = "Extract metadata from this PDF document including document type, issuer, primary date, and total amount."
    tokens = encoding.encode(text)
    token_count = len(tokens)

    print(f"Text: {text}")
    print(f"Token count: {token_count}")
    print("Encoding: o200k_base (GPT-5)")
    print()


def demo_cost_calculation_simple():
    """Demo 2: Simple cost calculation from token counts."""
    print("=" * 70)
    print("DEMO 2: Simple Cost Calculation")
    print("=" * 70)

    # Simulate API response usage
    usage = {
        "prompt_tokens": 1000,
        "output_tokens": 500,
        "prompt_tokens_details": {"cached_tokens": 0},
    }

    cost = calculate_cost(usage)

    print(f"Prompt tokens: {cost['prompt_tokens']:,}")
    print(f"Output tokens: {cost['output_tokens']:,}")
    print(f"Total tokens: {cost['total_tokens']:,}")
    print()
    print(f"Input cost: ${cost['input_cost_usd']:.6f}")
    print(f"Output cost: ${cost['output_cost_usd']:.6f}")
    print(f"Total cost: ${cost['total_cost_usd']:.6f}")
    print()
    print(f"Summary: {format_cost_summary(cost)}")
    print()


def demo_cost_with_caching():
    """Demo 3: Cost calculation with prompt caching."""
    print("=" * 70)
    print("DEMO 3: Cost Calculation with Prompt Caching")
    print("=" * 70)

    # Simulate API response with cached tokens
    # Developer prompt is reused across PDFs → 80% cache hit
    usage = {
        "prompt_tokens": 1000,
        "output_tokens": 500,
        "prompt_tokens_details": {"cached_tokens": 800},
    }

    cost = calculate_cost(usage)

    print(f"Prompt tokens: {cost['prompt_tokens']:,}")
    print(f"  - Billable (new): {cost['billable_input_tokens']:,}")
    print(f"  - Cached (reused): {cost['cached_tokens']:,}")
    print(f"Output tokens: {cost['output_tokens']:,}")
    print()
    print(f"Input cost (billable): ${cost['input_cost_usd']:.6f}")
    print(f"Cache cost (discounted): ${cost['cache_cost_usd']:.6f}")
    print(f"Output cost: ${cost['output_cost_usd']:.6f}")
    print(f"Total cost: ${cost['total_cost_usd']:.6f}")
    print()
    print(
        f"Cache savings: ${cost['cache_savings_usd']:.6f} ({cost['cached_tokens'] / cost['prompt_tokens']:.1%})"
    )
    print()
    print(f"Summary: {format_cost_summary(cost)}")
    print()


def demo_responses_api_calculator():
    """Demo 4: Using ResponsesAPICalculator for message token counting."""
    print("=" * 70)
    print("DEMO 4: Responses API Token Counting")
    print("=" * 70)

    calculator = ResponsesAPICalculator()

    messages = [
        {
            "role": "developer",
            "content": [
                {
                    "type": "input_text",
                    "text": "You are a document metadata extraction system. Extract: doc_type, issuer, primary_date, total_amount.",
                }
            ],
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "input_text",
                    "text": "Extract metadata from the PDF.",
                },
                {
                    "type": "input_file",
                    "filename": "utility_bill.pdf",
                    "file_data": "data:application/pdf;base64,JVBERi0...",
                },
            ],
        },
    ]

    result = calculator.count_request_tokens(
        model="gpt-5",
        messages=messages,
        tools=None,
        estimate_files=False,  # Would need actual file estimator
    )

    print(f"Model: {result.model}")
    print(f"Encoding: {result.encoding}")
    print(f"Total tokens: {result.count.total}")
    print()
    print("Breakdown:")
    for component, tokens in result.breakdown.items():
        print(f"  - {component}: {tokens} tokens")
    print()


def demo_cost_tracker():
    """Demo 5: Tracking cumulative costs across multiple PDFs."""
    print("=" * 70)
    print("DEMO 5: Cost Tracker (Multiple PDFs)")
    print("=" * 70)

    tracker = CostTracker()

    # Simulate processing 10 PDFs
    pdf_files = [f"invoice_{i:03d}.pdf" for i in range(1, 11)]

    print("Processing 10 PDFs with prompt caching enabled...")
    print()

    for i, pdf_path in enumerate(pdf_files, start=1):
        # First PDF: no caching (cold start)
        # Subsequent PDFs: 80% cache hit on developer prompt
        if i == 1:
            usage = {
                "prompt_tokens": 1200,
                "output_tokens": 450,
                "prompt_tokens_details": {"cached_tokens": 0},
            }
        else:
            usage = {
                "prompt_tokens": 1200,
                "output_tokens": 450,
                "prompt_tokens_details": {"cached_tokens": 960},  # 80% cached
            }

        cost = tracker.add_usage(usage, metadata={"pdf_path": pdf_path, "doc_id": i})

        # Log progress for first 3 PDFs
        if i <= 3:
            print(f"PDF {i}: {pdf_path}")
            print(f"  Cost: ${cost['total_cost_usd']:.6f}")
            if cost["cached_tokens"] > 0:
                print(
                    f"  Cached: {cost['cached_tokens']} tokens (saved ${cost['cache_savings_usd']:.6f})"
                )
            print()

    # Show summary
    print("..." if len(pdf_files) > 3 else "")
    print()
    print("Summary:")
    print(tracker.summary_text())
    print()

    summary = tracker.summary()
    print(f"Total cost: ${summary['total_cost_usd']:.4f}")
    print(f"Average per PDF: ${summary['average_cost_usd']:.4f}")
    print(f"Cache hit rate: {summary['cache_hit_rate']:.1%}")
    print(f"Total savings from caching: ${summary['total_cache_savings_usd']:.4f}")
    print()


def demo_structured_logging():
    """Demo 6: Structured logging with token/cost metrics."""
    print("=" * 70)
    print("DEMO 6: Structured Logging Integration")
    print("=" * 70)

    # Set up structured logger
    logger = setup_logging(
        log_level="INFO", log_format="json", log_file="logs/demo.log"
    )

    # Simulate processing a PDF
    usage = {
        "prompt_tokens": 1200,
        "output_tokens": 450,
        "prompt_tokens_details": {"cached_tokens": 960},
    }

    cost = calculate_cost(usage)

    # Log with token/cost metrics in extra fields
    logger.info(
        "PDF processing completed",
        extra={
            "pdf_path": "inbox/utility_bill_2024_10.pdf",
            "doc_id": 42,
            "sha256_hex": "abc123...",
            "status": "completed",
            "duration_ms": 2345,
            **cost,  # Unpack all cost metrics into log
        },
    )

    print("Logged metrics to logs/demo.log with JSON formatting")
    print()
    print("Log entry includes:")
    print("  - All token counts (prompt, output, cached, billable)")
    print("  - Cost breakdown (input, output, cache, savings, total)")
    print("  - Processing context (pdf_path, doc_id, status, duration)")
    print()
    print("Query with jq:")
    print("  cat logs/demo.log | jq '.total_cost_usd'")
    print("  cat logs/demo.log | jq 'select(.status == \"completed\")'")
    print()


def demo_pre_flight_estimation():
    """Demo 7: Pre-flight cost estimation before API call."""
    print("=" * 70)
    print("DEMO 7: Pre-Flight Cost Estimation")
    print("=" * 70)

    resolver = EncodingResolver()
    encoding = resolver.get_encoding("gpt-5")

    # Count tokens in prompt
    prompt = (
        "Extract metadata: doc_type, issuer, primary_date, total_amount from the PDF."
    )
    prompt_tokens = len(encoding.encode(prompt))

    # Estimate output tokens (conservative guess)
    expected_output_tokens = 500

    # Estimate cost before making API call
    estimated_cost = estimate_cost_from_tokens(
        prompt_tokens=prompt_tokens,
        output_tokens=expected_output_tokens,
        cached_tokens=0,  # First request, no caching
    )

    print(f"Prompt: {prompt}")
    print(f"Estimated prompt tokens: {prompt_tokens}")
    print(f"Expected output tokens: {expected_output_tokens}")
    print()
    print(f"Estimated cost: ${estimated_cost['total_cost_usd']:.6f}")
    print()
    print("This helps validate budget before processing large batches!")
    print()


def main():
    """Run all demos."""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 10 + "Token Counting & Cost Calculation Demo" + " " * 19 + "║")
    print("║" + " " * 15 + "autoD → Paper Autopilot" + " " * 29 + "║")
    print("╚" + "=" * 68 + "╝")
    print()

    demo_basic_token_counting()
    demo_cost_calculation_simple()
    demo_cost_with_caching()
    demo_responses_api_calculator()
    demo_cost_tracker()
    demo_structured_logging()
    demo_pre_flight_estimation()

    print("=" * 70)
    print("All demos completed!")
    print("=" * 70)
    print()
    print("Next steps:")
    print("  1. Run unit tests: pytest tests/ -v --cov=src")
    print("  2. Process real PDFs: python process_inbox.py")
    print("  3. Analyze costs: cat logs/paper_autopilot.log | jq '.total_cost_usd'")
    print()


if __name__ == "__main__":
    main()
