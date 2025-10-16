"""Low-level token counting primitives.

These are pure functions that operate on strings and use tiktoken encodings directly.
They form the foundation for higher-level token counting logic.
"""

from __future__ import annotations

import tiktoken


def count_string_tokens(text: str, encoding: tiktoken.Encoding) -> int:
    """
    Count tokens in a text string using a tiktoken encoding.

    Args:
        text: Input text
        encoding: tiktoken.Encoding object

    Returns:
        Number of tokens

    Example:
        >>> encoding = tiktoken.get_encoding("o200k_base")
        >>> count_string_tokens("Hello world", encoding)
        2
    """
    if not text:
        return 0
    return len(encoding.encode(text))


def count_message_tokens_chat_api(
    messages: list[dict],
    encoding: tiktoken.Encoding,
    tokens_per_message: int = 3,
    tokens_per_name: int = 1,
) -> int:
    """
    Count tokens for messages in Chat Completions API format.

    Based on OpenAI's token counting guide for chat models.
    Applies overhead for message formatting.

    Args:
        messages: List of message dicts with 'role' and 'content'
        encoding: tiktoken.Encoding object
        tokens_per_message: Overhead tokens per message (default: 3)
        tokens_per_name: Additional tokens if 'name' field present (default: 1)

    Returns:
        Total token count including overhead

    Example:
        >>> messages = [
        ...     {"role": "system", "content": "You are helpful"},
        ...     {"role": "user", "content": "Hello"}
        ... ]
        >>> encoding = tiktoken.get_encoding("o200k_base")
        >>> count_message_tokens_chat_api(messages, encoding)
        14  # includes message overhead
    """
    num_tokens = 0

    for message in messages:
        num_tokens += tokens_per_message

        for key, value in message.items():
            # Count tokens in the value (must be string)
            if isinstance(value, str):
                num_tokens += count_string_tokens(value, encoding)

            # Add extra token if 'name' field is present
            if key == "name":
                num_tokens += tokens_per_name

    # Every reply is primed with <|start|>assistant<|message|>
    num_tokens += 3

    return num_tokens


def count_message_tokens_responses_api(
    messages: list[dict],
    encoding: tiktoken.Encoding,
    tokens_per_message: int = 3,
    tokens_per_name: int = 1,
) -> int:
    """
    Count tokens for messages in Responses API format.

    Responses API supports different role types:
    - system
    - developer
    - user
    - assistant (for multi-turn)

    Message content can be:
    - Simple string
    - List of content parts (text, input_file, etc.)

    Args:
        messages: List of message dicts with 'role' and 'content'
        encoding: tiktoken.Encoding object
        tokens_per_message: Overhead tokens per message (default: 3)
        tokens_per_name: Additional tokens if 'name' field present (default: 1)

    Returns:
        Total token count including overhead (excluding file tokens)

    Note:
        File inputs (input_file type) are NOT counted here.
        Use file estimators separately for file token costs.
    """
    num_tokens = 0

    for message in messages:
        num_tokens += tokens_per_message

        content = message.get("content", "")

        # Handle string content
        if isinstance(content, str):
            num_tokens += count_string_tokens(content, encoding)

        # Handle list of content parts (Responses API format)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict):
                    # Text parts: input_text or output_text
                    if part.get("type") in ("input_text", "output_text"):
                        text = part.get("text", "")
                        num_tokens += count_string_tokens(text, encoding)

                    # File parts: input_file (skip - counted separately)
                    # We don't count file tokens here because they need
                    # special estimation logic (pages × tokens/page)

        # Add extra token if 'name' field is present
        if "name" in message:
            num_tokens += tokens_per_name

    # Every reply is primed with assistant start tokens
    num_tokens += 3

    return num_tokens


def count_tool_definition_tokens(
    tools: list[dict],
    encoding: tiktoken.Encoding,
    model_family: str = "gpt-4o",
) -> int:
    """
    Count tokens consumed by tool/function definitions.

    Tool definitions add overhead beyond the message tokens.
    The calculation varies by model family.

    Args:
        tools: List of tool definition dicts
        encoding: tiktoken.Encoding object
        model_family: Model family ("gpt-4o", "gpt-4", "gpt-3.5")

    Returns:
        Token count for tool definitions

    Note:
        This is a conservative estimate based on OpenAI's guidance.
        Actual token usage may vary slightly.
    """
    if not tools:
        return 0

    # Model-specific overhead constants
    # Based on tiktoken documentation
    if model_family in ("gpt-4o", "gpt-4o-mini"):
        func_init = 7
        prop_init = 3
        prop_key = 3
        enum_init = -3
        enum_item = 3
        func_end = 12
    elif model_family in ("gpt-4", "gpt-3.5-turbo", "gpt-3.5"):
        func_init = 10
        prop_init = 3
        prop_key = 3
        enum_init = -3
        enum_item = 3
        func_end = 12
    else:
        # Conservative fallback
        func_init = 10
        prop_init = 3
        prop_key = 3
        enum_init = -3
        enum_item = 3
        func_end = 12

    func_token_count = 0

    for tool in tools:
        func_token_count += func_init

        # Extract function definition
        function = tool.get("function", {})
        if not function:
            continue

        f_name = function.get("name", "")
        f_desc = function.get("description", "")

        # Remove trailing period if present (per OpenAI guidance)
        if f_desc.endswith("."):
            f_desc = f_desc[:-1]

        # Count name and description tokens
        line = f"{f_name}:{f_desc}"
        func_token_count += count_string_tokens(line, encoding)

        # Count parameter tokens
        parameters = function.get("parameters", {})
        properties = parameters.get("properties", {})

        if properties:
            func_token_count += prop_init

            for key, prop_def in properties.items():
                func_token_count += prop_key

                p_name = key
                p_type = prop_def.get("type", "")
                p_desc = prop_def.get("description", "")

                # Handle enum values
                if "enum" in prop_def:
                    func_token_count += enum_init
                    for item in prop_def["enum"]:
                        func_token_count += enum_item
                        func_token_count += count_string_tokens(str(item), encoding)

                # Remove trailing period
                if p_desc.endswith("."):
                    p_desc = p_desc[:-1]

                # Count property tokens
                line = f"{p_name}:{p_type}:{p_desc}"
                func_token_count += count_string_tokens(line, encoding)

    func_token_count += func_end
    return func_token_count
