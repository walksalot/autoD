"""Token counting module for OpenAI API requests.

This module provides reliable token counting and cost estimation for OpenAI API calls,
with particular focus on the Responses API and PDF file inputs.

Basic usage:
    >>> from token_counter import EncodingResolver, count_string_tokens
    >>> import tiktoken
    >>>
    >>> resolver = EncodingResolver()
    >>> encoding = resolver.get_encoding("gpt-5")
    >>> tokens = count_string_tokens("Hello world", encoding)

Advanced usage with messages:
    >>> from token_counter import count_message_tokens_responses_api
    >>>
    >>> messages = [
    ...     {"role": "system", "content": "You are helpful"},
    ...     {"role": "user", "content": "Hello"}
    ... ]
    >>> token_count = count_message_tokens_responses_api(messages, encoding)
"""

from .chat_api import ChatAPICalculator
from .encoding import EncodingResolver
from .exceptions import (
    ConfigurationError,
    EncodingNotFoundError,
    InvalidMessageFormatError,
    TokenCountError,
    ValidationError,
)
from .models import (
    CostEstimate,
    EncodingMetadata,
    TokenCount,
    TokenEstimate,
    TokenResult,
    ValidationResult,
)
from .primitives import (
    count_message_tokens_chat_api,
    count_message_tokens_responses_api,
    count_string_tokens,
    count_tool_definition_tokens,
)
from .responses_api import ResponsesAPICalculator

__all__ = [
    # Core functionality
    "EncodingResolver",
    "count_string_tokens",
    "count_message_tokens_chat_api",
    "count_message_tokens_responses_api",
    "count_tool_definition_tokens",
    # Calculators
    "ResponsesAPICalculator",
    "ChatAPICalculator",
    # Data models
    "TokenCount",
    "TokenEstimate",
    "CostEstimate",
    "TokenResult",
    "EncodingMetadata",
    "ValidationResult",
    # Exceptions
    "TokenCountError",
    "EncodingNotFoundError",
    "InvalidMessageFormatError",
    "ConfigurationError",
    "ValidationError",
]

__version__ = "0.1.0"
