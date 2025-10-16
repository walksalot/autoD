"""Integration tests for ResponsesAPICalculator.

These tests verify the end-to-end behavior of the Responses API calculator,
ensuring proper integration of encoding resolution, overhead configuration,
and token counting primitives.
"""

import pytest

from token_counter import ResponsesAPICalculator
from token_counter.exceptions import InvalidMessageFormatError


class TestResponsesAPICalculatorBasics:
    """Basic integration tests for ResponsesAPICalculator."""

    @pytest.fixture
    def calculator(self):
        """Provide a calculator instance."""
        return ResponsesAPICalculator()

    def test_simple_user_message(self, calculator):
        """Test counting tokens in a simple user message."""
        messages = [{"role": "user", "content": "Hello world"}]

        result = calculator.count_request_tokens(
            model="gpt-5",
            messages=messages,
        )

        assert result.model == "gpt-5"
        assert result.encoding == "o200k_base"
        assert result.count.total > 5  # Message content + overhead
        assert result.breakdown["messages"] > 0
        assert result.breakdown["tools"] == 0
        assert result.breakdown["files"] == 0

    def test_multi_message_conversation(self, calculator):
        """Test counting tokens in a multi-turn conversation."""
        messages = [
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
            {"role": "user", "content": "How are you?"},
        ]

        result = calculator.count_request_tokens(
            model="gpt-5",
            messages=messages,
        )

        assert result.count.total > 20  # Multiple messages with overhead
        assert result.breakdown["messages"] > 0

    def test_developer_role_responses_api_specific(self, calculator):
        """Test that developer role (Responses API specific) works."""
        messages = [
            {"role": "system", "content": "System prompt"},
            {"role": "developer", "content": "Developer instructions"},
            {"role": "user", "content": "User query"},
        ]

        result = calculator.count_request_tokens(
            model="gpt-5",
            messages=messages,
        )

        assert result.count.total > 10
        assert result.breakdown["messages"] > 0

    def test_message_with_name_field(self, calculator):
        """Test that name field adds extra tokens."""
        messages_without_name = [{"role": "user", "content": "Hello"}]
        messages_with_name = [
            {"role": "user", "name": "Alice", "content": "Hello"}
        ]

        result_without = calculator.count_request_tokens(
            model="gpt-5",
            messages=messages_without_name,
        )

        result_with = calculator.count_request_tokens(
            model="gpt-5",
            messages=messages_with_name,
        )

        # With name should have more tokens
        assert result_with.count.total > result_without.count.total


class TestResponsesAPICalculatorContentTypes:
    """Test handling of different content types."""

    @pytest.fixture
    def calculator(self):
        """Provide a calculator instance."""
        return ResponsesAPICalculator()

    def test_string_content(self, calculator):
        """Test with simple string content."""
        messages = [{"role": "user", "content": "Hello world"}]

        result = calculator.count_request_tokens(
            model="gpt-5",
            messages=messages,
        )

        assert result.count.total > 0

    def test_list_content_with_input_text(self, calculator):
        """Test with list content containing input_text."""
        messages = [
            {
                "role": "user",
                "content": [{"type": "input_text", "text": "Hello world"}],
            }
        ]

        result = calculator.count_request_tokens(
            model="gpt-5",
            messages=messages,
        )

        assert result.count.total > 0

    def test_list_content_with_input_file(self, calculator):
        """Test that input_file types are detected for estimation."""
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "Process this PDF"},
                    {
                        "type": "input_file",
                        "filename": "test.pdf",
                        "file_data": "data:application/pdf;base64,JVBERi0x...",
                    },
                ],
            }
        ]

        # Without file estimation
        result_no_estimate = calculator.count_request_tokens(
            model="gpt-5",
            messages=messages,
            estimate_files=False,
        )

        # With file estimation
        result_with_estimate = calculator.count_request_tokens(
            model="gpt-5",
            messages=messages,
            estimate_files=True,
        )

        # With estimation should include file tokens (placeholder)
        assert result_with_estimate.count.total >= result_no_estimate.count.total
        assert result_with_estimate.file_estimate is not None
        assert result_with_estimate.breakdown["files"] > 0


class TestResponsesAPICalculatorTools:
    """Test tool definition token counting."""

    @pytest.fixture
    def calculator(self):
        """Provide a calculator instance."""
        return ResponsesAPICalculator()

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
            model="gpt-5",
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
            model="gpt-5",
            messages=messages,
            tools=tools,
        )

        assert result.breakdown["tools"] > 20  # Multiple tools
        assert result.count.total > 30


class TestResponsesAPICalculatorModels:
    """Test different model behaviors."""

    @pytest.fixture
    def calculator(self):
        """Provide a calculator instance."""
        return ResponsesAPICalculator()

    def test_gpt5_model(self, calculator):
        """Test with GPT-5 model."""
        messages = [{"role": "user", "content": "Hello"}]

        result = calculator.count_request_tokens(
            model="gpt-5",
            messages=messages,
        )

        assert result.model == "gpt-5"
        assert result.encoding == "o200k_base"

    def test_gpt4o_model(self, calculator):
        """Test with GPT-4o model."""
        messages = [{"role": "user", "content": "Hello"}]

        result = calculator.count_request_tokens(
            model="gpt-4o",
            messages=messages,
        )

        assert result.model == "gpt-4o"
        assert result.encoding == "o200k_base"

    def test_gpt4_model(self, calculator):
        """Test with GPT-4 model (different encoding)."""
        messages = [{"role": "user", "content": "Hello"}]

        result = calculator.count_request_tokens(
            model="gpt-4",
            messages=messages,
        )

        assert result.model == "gpt-4"
        assert result.encoding == "cl100k_base"

    def test_model_variant_pattern_matching(self, calculator):
        """Test that model variants are correctly matched."""
        messages = [{"role": "user", "content": "Hello"}]

        # GPT-5 variant
        result_gpt5 = calculator.count_request_tokens(
            model="gpt-5-turbo-preview",
            messages=messages,
        )
        assert result_gpt5.encoding == "o200k_base"

        # GPT-4o variant
        result_gpt4o = calculator.count_request_tokens(
            model="gpt-4o-mini",
            messages=messages,
        )
        assert result_gpt4o.encoding == "o200k_base"


class TestResponsesAPICalculatorValidation:
    """Test input validation."""

    @pytest.fixture
    def calculator(self):
        """Provide a calculator instance."""
        return ResponsesAPICalculator()

    def test_invalid_message_format_not_list(self, calculator):
        """Test that non-list messages raise error."""
        with pytest.raises(InvalidMessageFormatError, match="must be a list"):
            calculator.count_message_tokens(
                model="gpt-5",
                messages="not a list",  # type: ignore
            )

    def test_invalid_message_missing_role(self, calculator):
        """Test that messages without role raise error."""
        messages = [{"content": "Hello"}]  # Missing 'role'

        with pytest.raises(InvalidMessageFormatError, match="missing.*role"):
            calculator.count_message_tokens(
                model="gpt-5",
                messages=messages,
            )

    def test_invalid_message_missing_content(self, calculator):
        """Test that messages without content raise error."""
        messages = [{"role": "user"}]  # Missing 'content'

        with pytest.raises(InvalidMessageFormatError, match="missing.*content"):
            calculator.count_message_tokens(
                model="gpt-5",
                messages=messages,
            )

    def test_invalid_role(self, calculator):
        """Test that invalid roles raise error."""
        messages = [{"role": "invalid_role", "content": "Hello"}]

        with pytest.raises(InvalidMessageFormatError, match="invalid role"):
            calculator.count_message_tokens(
                model="gpt-5",
                messages=messages,
            )


class TestResponsesAPICalculatorBreakdown:
    """Test token breakdown functionality."""

    @pytest.fixture
    def calculator(self):
        """Provide a calculator instance."""
        return ResponsesAPICalculator()

    def test_breakdown_includes_all_components(self, calculator):
        """Test that breakdown includes messages, tools, and files."""
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
            model="gpt-5",
            messages=messages,
            tools=tools,
        )

        assert "messages" in result.breakdown
        assert "tools" in result.breakdown
        assert "files" in result.breakdown
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
            model="gpt-5",
            messages=messages,
            tools=tools,
        )

        breakdown_total = sum(result.breakdown.values())
        assert breakdown_total == result.count.total
