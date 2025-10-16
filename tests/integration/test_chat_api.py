"""Integration tests for ChatAPICalculator.

These tests verify the end-to-end behavior of the Chat Completions API calculator,
ensuring proper integration of encoding resolution, overhead configuration,
and token counting primitives.
"""

import pytest

from token_counter import ChatAPICalculator
from token_counter.exceptions import InvalidMessageFormatError


class TestChatAPICalculatorBasics:
    """Basic integration tests for ChatAPICalculator."""

    @pytest.fixture
    def calculator(self):
        """Provide a calculator instance."""
        return ChatAPICalculator()

    def test_simple_user_message(self, calculator):
        """Test counting tokens in a simple user message."""
        messages = [{"role": "user", "content": "Hello world"}]

        result = calculator.count_request_tokens(
            model="gpt-4",
            messages=messages,
        )

        assert result.model == "gpt-4"
        assert result.encoding == "cl100k_base"
        assert result.count.total > 5  # Message content + overhead
        assert result.breakdown["messages"] > 0
        assert result.breakdown["tools"] == 0
        assert result.breakdown["functions"] == 0

    def test_multi_message_conversation(self, calculator):
        """Test counting tokens in a multi-turn conversation."""
        messages = [
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
            {"role": "user", "content": "How are you?"},
        ]

        result = calculator.count_request_tokens(
            model="gpt-4",
            messages=messages,
        )

        assert result.count.total > 20  # Multiple messages with overhead
        assert result.breakdown["messages"] > 0

    def test_message_with_name_field(self, calculator):
        """Test that name field adds extra tokens."""
        messages_without_name = [{"role": "user", "content": "Hello"}]
        messages_with_name = [{"role": "user", "name": "Alice", "content": "Hello"}]

        result_without = calculator.count_request_tokens(
            model="gpt-4",
            messages=messages_without_name,
        )

        result_with = calculator.count_request_tokens(
            model="gpt-4",
            messages=messages_with_name,
        )

        # With name should have more tokens
        assert result_with.count.total > result_without.count.total


class TestChatAPICalculatorTools:
    """Test tool definition token counting."""

    @pytest.fixture
    def calculator(self):
        """Provide a calculator instance."""
        return ChatAPICalculator()

    def test_request_with_single_tool(self, calculator):
        """Test counting tokens with a tool definition."""
        messages = [{"role": "user", "content": "What's the weather?"}]

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get current weather",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {
                                "type": "string",
                                "description": "City name",
                            }
                        },
                    },
                },
            }
        ]

        result = calculator.count_request_tokens(
            model="gpt-4",
            messages=messages,
            tools=tools,
        )

        assert result.breakdown["tools"] > 10  # Tool definitions add overhead
        assert result.count.total > result.breakdown["messages"]

    def test_request_with_multiple_tools(self, calculator):
        """Test counting tokens with multiple tool definitions."""
        messages = [{"role": "user", "content": "Help me"}]

        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get weather",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_time",
                    "description": "Get current time",
                    "parameters": {"type": "object", "properties": {}},
                },
            },
        ]

        result = calculator.count_request_tokens(
            model="gpt-4",
            messages=messages,
            tools=tools,
        )

        assert result.breakdown["tools"] > 20  # Multiple tools
        assert result.count.total > 30


class TestChatAPICalculatorFunctions:
    """Test legacy function calling token counting."""

    @pytest.fixture
    def calculator(self):
        """Provide a calculator instance."""
        return ChatAPICalculator()

    def test_request_with_single_function(self, calculator):
        """Test counting tokens with a function definition (legacy)."""
        messages = [{"role": "user", "content": "What's the weather?"}]

        functions = [
            {
                "name": "get_weather",
                "description": "Get current weather",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "City name",
                        }
                    },
                },
            }
        ]

        result = calculator.count_request_tokens(
            model="gpt-4",
            messages=messages,
            functions=functions,
        )

        assert result.breakdown["functions"] > 10  # Function definitions add overhead
        assert result.count.total > result.breakdown["messages"]

    def test_request_with_multiple_functions(self, calculator):
        """Test counting tokens with multiple function definitions."""
        messages = [{"role": "user", "content": "Help me"}]

        functions = [
            {
                "name": "get_weather",
                "description": "Get weather",
                "parameters": {"type": "object", "properties": {}},
            },
            {
                "name": "get_time",
                "description": "Get current time",
                "parameters": {"type": "object", "properties": {}},
            },
        ]

        result = calculator.count_request_tokens(
            model="gpt-4",
            messages=messages,
            functions=functions,
        )

        assert result.breakdown["functions"] > 20  # Multiple functions


class TestChatAPICalculatorModels:
    """Test different model behaviors."""

    @pytest.fixture
    def calculator(self):
        """Provide a calculator instance."""
        return ChatAPICalculator()

    def test_gpt4_model(self, calculator):
        """Test with GPT-4 model."""
        messages = [{"role": "user", "content": "Hello"}]

        result = calculator.count_request_tokens(
            model="gpt-4",
            messages=messages,
        )

        assert result.model == "gpt-4"
        assert result.encoding == "cl100k_base"

    def test_gpt4o_model(self, calculator):
        """Test with GPT-4o model."""
        messages = [{"role": "user", "content": "Hello"}]

        result = calculator.count_request_tokens(
            model="gpt-4o",
            messages=messages,
        )

        assert result.model == "gpt-4o"
        assert result.encoding == "o200k_base"

    def test_gpt35_turbo_model(self, calculator):
        """Test with GPT-3.5-turbo model."""
        messages = [{"role": "user", "content": "Hello"}]

        result = calculator.count_request_tokens(
            model="gpt-3.5-turbo",
            messages=messages,
        )

        assert result.model == "gpt-3.5-turbo"
        assert result.encoding == "cl100k_base"

    def test_model_variant_pattern_matching(self, calculator):
        """Test that model variants are correctly matched."""
        messages = [{"role": "user", "content": "Hello"}]

        # GPT-4 variant
        result_gpt4 = calculator.count_request_tokens(
            model="gpt-4-1106-preview",
            messages=messages,
        )
        assert result_gpt4.encoding == "cl100k_base"

        # GPT-4o variant
        result_gpt4o = calculator.count_request_tokens(
            model="gpt-4o-mini",
            messages=messages,
        )
        assert result_gpt4o.encoding == "o200k_base"


class TestChatAPICalculatorValidation:
    """Test input validation."""

    @pytest.fixture
    def calculator(self):
        """Provide a calculator instance."""
        return ChatAPICalculator()

    def test_invalid_message_format_not_list(self, calculator):
        """Test that non-list messages raise error."""
        with pytest.raises(InvalidMessageFormatError, match="must be a list"):
            calculator.count_message_tokens(
                model="gpt-4",
                messages="not a list",  # type: ignore
            )

    def test_invalid_message_missing_role(self, calculator):
        """Test that messages without role raise error."""
        messages = [{"content": "Hello"}]  # Missing 'role'

        with pytest.raises(InvalidMessageFormatError, match="missing.*role"):
            calculator.count_message_tokens(
                model="gpt-4",
                messages=messages,
            )

    def test_invalid_message_missing_content(self, calculator):
        """Test that user messages without content raise error."""
        messages = [{"role": "user"}]  # Missing 'content'

        with pytest.raises(InvalidMessageFormatError, match="missing.*content"):
            calculator.count_message_tokens(
                model="gpt-4",
                messages=messages,
            )

    def test_invalid_role(self, calculator):
        """Test that invalid roles raise error."""
        messages = [{"role": "invalid_role", "content": "Hello"}]

        with pytest.raises(InvalidMessageFormatError, match="invalid role"):
            calculator.count_message_tokens(
                model="gpt-4",
                messages=messages,
            )

    def test_tool_role_without_content_allowed(self, calculator):
        """Test that tool/function roles can omit content."""
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "tool", "tool_call_id": "123"},  # No content required
        ]

        # Should not raise error
        result = calculator.count_message_tokens(
            model="gpt-4",
            messages=messages,
        )

        assert result > 0


class TestChatAPICalculatorBreakdown:
    """Test token breakdown functionality."""

    @pytest.fixture
    def calculator(self):
        """Provide a calculator instance."""
        return ChatAPICalculator()

    def test_breakdown_includes_all_components(self, calculator):
        """Test that breakdown includes messages, tools, and functions."""
        messages = [{"role": "user", "content": "Hello"}]
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "test",
                    "description": "Test",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]

        result = calculator.count_request_tokens(
            model="gpt-4",
            messages=messages,
            tools=tools,
        )

        assert "messages" in result.breakdown
        assert "tools" in result.breakdown
        assert "functions" in result.breakdown
        assert result.breakdown["messages"] > 0
        assert result.breakdown["tools"] > 0

    def test_breakdown_sum_equals_total(self, calculator):
        """Test that breakdown components sum to total."""
        messages = [{"role": "user", "content": "Hello"}]
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "test",
                    "description": "Test",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]

        result = calculator.count_request_tokens(
            model="gpt-4",
            messages=messages,
            tools=tools,
        )

        breakdown_total = sum(result.breakdown.values())
        assert breakdown_total == result.count.total

    def test_tools_and_functions_both_present(self, calculator):
        """Test using both tools and functions (edge case)."""
        messages = [{"role": "user", "content": "Hello"}]
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "tool_func",
                    "description": "Tool",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]
        functions = [
            {
                "name": "legacy_func",
                "description": "Function",
                "parameters": {"type": "object", "properties": {}},
            }
        ]

        result = calculator.count_request_tokens(
            model="gpt-4",
            messages=messages,
            tools=tools,
            functions=functions,
        )

        # Both should be counted
        assert result.breakdown["tools"] > 0
        assert result.breakdown["functions"] > 0
        breakdown_total = sum(result.breakdown.values())
        assert breakdown_total == result.count.total


class TestChatAPICalculatorOverhead:
    """Test overhead calculation differences between models."""

    @pytest.fixture
    def calculator(self):
        """Provide a calculator instance."""
        return ChatAPICalculator()

    def test_gpt4_vs_gpt4o_tool_overhead_difference(self, calculator):
        """Test that GPT-4 and GPT-4o have different tool overhead."""
        messages = [{"role": "user", "content": "Test"}]
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "test",
                    "description": "Test",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]

        result_gpt4 = calculator.count_request_tokens(
            model="gpt-4",
            messages=messages,
            tools=tools,
        )

        result_gpt4o = calculator.count_request_tokens(
            model="gpt-4o",
            messages=messages,
            tools=tools,
        )

        # GPT-4 has higher tool overhead (10 init vs 7 init)
        assert result_gpt4.breakdown["tools"] > result_gpt4o.breakdown["tools"]

    def test_gpt35_turbo_name_overhead(self, calculator):
        """Test that GPT-3.5-turbo has different name field behavior."""
        messages_with_name = [{"role": "user", "name": "Alice", "content": "Hello"}]

        result = calculator.count_request_tokens(
            model="gpt-3.5-turbo",
            messages=messages_with_name,
        )

        # Should handle GPT-3.5-turbo's -1 token for name field
        assert result.count.total > 0
