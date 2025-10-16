"""High-level facade API for token counting.

This module provides a simplified, user-friendly interface for token counting
that abstracts away the complexities of different API formats, encodings,
and cost calculations.

Example usage:
    from token_counter import TokenCounter

    counter = TokenCounter()

    # Simple token counting
    messages = [
        {"role": "user", "content": "Hello!"}
    ]
    result = counter.count_tokens("gpt-5", messages)
    print(f"Tokens: {result.count.total}")

    # With cost estimation
    result = counter.count_tokens("gpt-5", messages, estimate_cost=True)
    print(f"Cost: ${result.cost.total_usd:.6f}")

    # File estimation
    messages_with_pdf = [
        {
            "role": "user",
            "content": [
                {"type": "input_text", "text": "Analyze this PDF"},
                {"type": "input_file", "filename": "doc.pdf", "file_data": "..."}
            ]
        }
    ]
    result = counter.count_tokens("gpt-5", messages_with_pdf, estimate_files=True)
"""

from __future__ import annotations

from typing import Any, Dict, List

from .chat_api import ChatAPICalculator
from .cost import CostCalculator
from .encoding import EncodingResolver
from .models import CostEstimate, TokenResult
from .responses_api import ResponsesAPICalculator


class TokenCounter:
    """Simplified facade for token counting and cost estimation.

    This class provides a high-level API that automatically handles:
    - API format detection (Responses API vs Chat Completions)
    - Encoding resolution
    - File token estimation
    - Cost calculation

    All complexity is hidden behind simple, intuitive methods.
    """

    def __init__(
        self,
        encoding_resolver: EncodingResolver | None = None,
        cost_calculator: CostCalculator | None = None,
    ):
        """Initialize the token counter.

        Args:
            encoding_resolver: Optional custom EncodingResolver
            cost_calculator: Optional custom CostCalculator
        """
        self.encoding_resolver = encoding_resolver or EncodingResolver()
        self.cost_calculator = cost_calculator or CostCalculator()

        # Initialize both calculators
        self.responses_calculator = ResponsesAPICalculator(
            encoding_resolver=self.encoding_resolver,
            cost_calculator=self.cost_calculator,
        )
        self.chat_calculator = ChatAPICalculator(
            encoding_resolver=self.encoding_resolver,
            cost_calculator=self.cost_calculator,
        )

    def count_tokens(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        tools: List[Dict[str, Any]] | None = None,
        functions: List[Dict[str, Any]] | None = None,
        estimate_files: bool = False,
        estimate_cost: bool = False,
        api_format: str | None = None,
    ) -> TokenResult:
        """Count tokens for a request.

        Automatically detects API format if not specified.

        Args:
            model: Model name (e.g., "gpt-5", "gpt-4o")
            messages: List of message dictionaries
            tools: Optional tool definitions
            functions: Optional function definitions (legacy Chat API)
            estimate_files: Whether to estimate file tokens
            estimate_cost: Whether to calculate cost
            api_format: Force specific format ("responses" or "chat")
                If None, auto-detects based on message structure

        Returns:
            TokenResult with counts, estimates, and optionally cost

        Example:
            >>> counter = TokenCounter()
            >>> messages = [{"role": "user", "content": "Hello"}]
            >>> result = counter.count_tokens("gpt-5", messages)
            >>> print(result.count.total)
            5
        """
        # Auto-detect API format if not specified
        if api_format is None:
            api_format = self._detect_api_format(messages)

        # Route to appropriate calculator
        if api_format == "responses":
            return self.responses_calculator.count_request_tokens(
                model=model,
                messages=messages,
                tools=tools,
                estimate_files=estimate_files,
                calculate_cost=estimate_cost,
            )
        else:  # chat
            return self.chat_calculator.count_request_tokens(
                model=model,
                messages=messages,
                tools=tools,
                functions=functions,
                calculate_cost=estimate_cost,
            )

    def estimate_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int = 0,
        cached_tokens: int = 0,
    ) -> CostEstimate:
        """Estimate cost for token usage.

        Useful for pre-request cost estimation when you know
        approximate token counts.

        Args:
            model: Model name
            input_tokens: Number of input tokens
            output_tokens: Estimated output tokens (default: 0)
            cached_tokens: Number of cached tokens (default: 0)

        Returns:
            CostEstimate with detailed cost breakdown

        Example:
            >>> counter = TokenCounter()
            >>> cost = counter.estimate_cost(
            ...     model="gpt-5",
            ...     input_tokens=1000,
            ...     output_tokens=500
            ... )
            >>> print(f"${cost.total_usd:.4f}")
            $0.0075
        """
        return self.cost_calculator.calculate_cost(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=cached_tokens,
        )

    def count_and_estimate(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        estimated_output_tokens: int = 0,
        tools: List[Dict[str, Any]] | None = None,
        estimate_files: bool = False,
    ) -> TokenResult:
        """Count tokens and estimate total cost including output.

        Convenience method that combines token counting with
        cost estimation for both input and expected output.

        Args:
            model: Model name
            messages: List of message dictionaries
            estimated_output_tokens: Expected response length
            tools: Optional tool definitions
            estimate_files: Whether to estimate file tokens

        Returns:
            TokenResult with cost estimate including output

        Example:
            >>> counter = TokenCounter()
            >>> messages = [{"role": "user", "content": "Write an essay"}]
            >>> result = counter.count_and_estimate(
            ...     model="gpt-5",
            ...     messages=messages,
            ...     estimated_output_tokens=1000
            ... )
            >>> print(f"Estimated cost: {result.cost}")
        """
        # Count input tokens
        result = self.count_tokens(
            model=model,
            messages=messages,
            tools=tools,
            estimate_files=estimate_files,
            estimate_cost=False,  # We'll calculate cost separately
        )

        # Calculate cost including estimated output
        cost = self.cost_calculator.calculate_cost(
            model=model,
            input_tokens=result.count.billable,
            output_tokens=estimated_output_tokens,
            cached_tokens=result.count.cached,
        )

        # Update result with cost
        result.cost = cost

        return result

    def get_model_pricing(self, model: str) -> Dict[str, float]:
        """Get pricing information for a model.

        Args:
            model: Model name

        Returns:
            Dictionary with input_per_million, output_per_million,
            and cached_input_per_million pricing

        Example:
            >>> counter = TokenCounter()
            >>> pricing = counter.get_model_pricing("gpt-5")
            >>> print(f"Input: ${pricing['input_per_million']}/M tokens")
            Input: $2.50/M tokens
        """
        return self.cost_calculator.get_model_pricing(model)

    def get_encoding_name(self, model: str) -> str:
        """Get encoding name for a model.

        Args:
            model: Model name

        Returns:
            Encoding name (e.g., "o200k_base", "cl100k_base")

        Example:
            >>> counter = TokenCounter()
            >>> encoding = counter.get_encoding_name("gpt-5")
            >>> print(encoding)
            o200k_base
        """
        return self.encoding_resolver.get_encoding_name(model)

    def _detect_api_format(self, messages: List[Dict[str, Any]]) -> str:
        """Auto-detect API format from message structure.

        Responses API messages use content arrays with types:
        - input_text
        - input_file

        Chat API messages use simple string content or arrays with:
        - text
        - image_url

        Args:
            messages: List of message dictionaries

        Returns:
            "responses" or "chat"
        """
        if not messages:
            return "responses"  # Default

        # Check first message with content
        for msg in messages:
            content = msg.get("content")

            # String content can be either format
            if isinstance(content, str):
                continue

            # Check array content types
            if isinstance(content, list) and content:
                first_item = content[0]
                if isinstance(first_item, dict):
                    item_type = first_item.get("type", "")

                    # Responses API types
                    if item_type in ["input_text", "input_file"]:
                        return "responses"

                    # Chat API types
                    if item_type in ["text", "image_url"]:
                        return "chat"

        # Default to Responses API for gpt-5 and newer models
        return "responses"
