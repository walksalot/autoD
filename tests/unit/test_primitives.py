"""Unit tests for token counting primitives."""

import pytest
import tiktoken

from token_counter.primitives import (
    count_string_tokens,
    count_message_tokens_chat_api,
    count_message_tokens_responses_api,
    count_tool_definition_tokens,
)


@pytest.fixture
def o200k_encoding():
    """Fixture providing o200k_base encoding (GPT-5, GPT-4o)."""
    return tiktoken.get_encoding("o200k_base")


@pytest.fixture
def cl100k_encoding():
    """Fixture providing cl100k_base encoding (GPT-4, GPT-3.5)."""
    return tiktoken.get_encoding("cl100k_base")


class TestCountStringTokens:
    """Test cases for count_string_tokens function."""

    def test_simple_string(self, o200k_encoding):
        """Test counting tokens in a simple string."""
        text = "Hello world"
        count = count_string_tokens(text, o200k_encoding)
        assert count > 0
        assert count <= 3  # Should be 2 tokens typically

    def test_empty_string(self, o200k_encoding):
        """Test that empty string returns 0 tokens."""
        count = count_string_tokens("", o200k_encoding)
        assert count == 0

    def test_unicode_string(self, o200k_encoding):
        """Test counting tokens in Unicode text."""
        text = "こんにちは世界"  # "Hello world" in Japanese
        count = count_string_tokens(text, o200k_encoding)
        assert count > 0

    def test_long_string(self, o200k_encoding):
        """Test counting tokens in a long string."""
        text = "This is a much longer string that contains many words " * 10
        count = count_string_tokens(text, o200k_encoding)
        assert count > 50  # Should have many tokens

    def test_encoding_consistency(self, o200k_encoding):
        """Test that same text always produces same token count."""
        text = "Consistent test string"
        count1 = count_string_tokens(text, o200k_encoding)
        count2 = count_string_tokens(text, o200k_encoding)
        assert count1 == count2


class TestCountMessageTokensChatAPI:
    """Test cases for count_message_tokens_chat_api function."""

    def test_single_message(self, o200k_encoding):
        """Test counting tokens for a single message."""
        messages = [{"role": "user", "content": "Hello"}]
        count = count_message_tokens_chat_api(messages, o200k_encoding)

        # Should include: message overhead (3) + content tokens + reply priming (3)
        assert count > 5

    def test_multiple_messages(self, o200k_encoding):
        """Test counting tokens for multiple messages."""
        messages = [
            {"role": "system", "content": "You are helpful"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
        count = count_message_tokens_chat_api(messages, o200k_encoding)

        # Each message adds overhead
        assert count > 15

    def test_message_with_name_field(self, o200k_encoding):
        """Test that 'name' field adds extra tokens."""
        messages_without_name = [{"role": "user", "content": "Hello"}]
        messages_with_name = [{"role": "user", "name": "Alice", "content": "Hello"}]

        count_without = count_message_tokens_chat_api(
            messages_without_name, o200k_encoding
        )
        count_with = count_message_tokens_chat_api(messages_with_name, o200k_encoding)

        # With name should have more tokens
        assert count_with > count_without

    def test_empty_messages_list(self, o200k_encoding):
        """Test counting tokens for empty messages list."""
        messages = []
        count = count_message_tokens_chat_api(messages, o200k_encoding)

        # Should still have reply priming tokens
        assert count == 3

    def test_custom_overhead(self, o200k_encoding):
        """Test with custom overhead parameters."""
        messages = [{"role": "user", "content": "Test"}]

        # Default overhead
        count_default = count_message_tokens_chat_api(messages, o200k_encoding)

        # Custom overhead
        count_custom = count_message_tokens_chat_api(
            messages, o200k_encoding, tokens_per_message=5, tokens_per_name=2
        )

        # Custom should be different
        assert count_custom != count_default


class TestCountMessageTokensResponsesAPI:
    """Test cases for count_message_tokens_responses_api function."""

    def test_string_content(self, o200k_encoding):
        """Test with simple string content."""
        messages = [{"role": "user", "content": "Hello world"}]
        count = count_message_tokens_responses_api(messages, o200k_encoding)
        assert count > 5

    def test_list_content_with_input_text(self, o200k_encoding):
        """Test with list content containing input_text."""
        messages = [
            {
                "role": "user",
                "content": [{"type": "input_text", "text": "Hello world"}],
            }
        ]
        count = count_message_tokens_responses_api(messages, o200k_encoding)
        assert count > 5

    def test_list_content_with_input_file(self, o200k_encoding):
        """Test that input_file types are skipped."""
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "Process this PDF"},
                    {
                        "type": "input_file",
                        "file_data": "base64data...",
                        "filename": "test.pdf",
                    },
                ],
            }
        ]
        count = count_message_tokens_responses_api(messages, o200k_encoding)

        # Should only count the text, not the file
        assert count > 5
        assert count < 20  # Shouldn't include file tokens

    def test_developer_role(self, o200k_encoding):
        """Test with developer role (Responses API specific)."""
        messages = [
            {"role": "system", "content": "System prompt"},
            {"role": "developer", "content": "Developer instructions"},
            {"role": "user", "content": "User query"},
        ]
        count = count_message_tokens_responses_api(messages, o200k_encoding)
        assert count > 10


class TestCountToolDefinitionTokens:
    """Test cases for count_tool_definition_tokens function."""

    def test_no_tools(self, o200k_encoding):
        """Test that no tools returns 0 tokens."""
        count = count_tool_definition_tokens([], o200k_encoding)
        assert count == 0

    def test_single_tool(self, o200k_encoding):
        """Test counting tokens for a single tool definition."""
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get the current weather",
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
        count = count_tool_definition_tokens(tools, o200k_encoding)
        assert count > 10  # Should have significant overhead

    def test_tool_with_enum(self, o200k_encoding):
        """Test tool with enum property."""
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "convert_temp",
                    "description": "Convert temperature",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "unit": {
                                "type": "string",
                                "description": "Temperature unit",
                                "enum": ["celsius", "fahrenheit"],
                            }
                        },
                    },
                },
            }
        ]
        count = count_tool_definition_tokens(tools, o200k_encoding)
        assert count > 15

    def test_model_family_overhead_differences(self, o200k_encoding):
        """Test that different model families have different overhead."""
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "test",
                    "description": "Test function",
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]

        count_gpt4o = count_tool_definition_tokens(
            tools, o200k_encoding, model_family="gpt-4o"
        )
        count_gpt4 = count_tool_definition_tokens(
            tools, o200k_encoding, model_family="gpt-4"
        )

        # Different model families should have different overhead
        assert count_gpt4o != count_gpt4

    def test_trailing_period_removal(self, o200k_encoding):
        """Test that trailing periods are removed from descriptions."""
        tools_with_period = [
            {
                "type": "function",
                "function": {
                    "name": "test",
                    "description": "This is a test.",  # Has period
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]

        tools_without_period = [
            {
                "type": "function",
                "function": {
                    "name": "test",
                    "description": "This is a test",  # No period
                    "parameters": {"type": "object", "properties": {}},
                },
            }
        ]

        count_with = count_tool_definition_tokens(tools_with_period, o200k_encoding)
        count_without = count_tool_definition_tokens(
            tools_without_period, o200k_encoding
        )

        # Should be the same (period removed)
        assert count_with == count_without
