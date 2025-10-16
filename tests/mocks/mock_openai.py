"""Mock implementation of OpenAI Responses API for testing.

This module provides a complete mock of the OpenAI Responses API that:
- Returns realistic response objects with usage statistics
- Supports different document types (Invoice, Receipt, etc.)
- Allows configurable token counts for cost testing
- Can simulate various error conditions

Example usage:
    from tests.mocks.mock_openai import MockResponsesClient, create_mock_response

    # Create mock client
    client = MockResponsesClient(default_doc_type="invoice")

    # Use in tests
    response = client.responses.create(model="gpt-5", input=[...])
    assert response.usage.prompt_tokens > 0
"""

import json
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass
from pathlib import Path


@dataclass
class UsageStats:
    """Simulates OpenAI API usage statistics.

    Matches the structure returned by the actual OpenAI API.
    """
    prompt_tokens: int
    output_tokens: int
    total_tokens: int
    prompt_tokens_details: Dict[str, int]

    def __dict__(self) -> Dict[str, Any]:
        """Convert to dictionary for compatibility with API response parsing."""
        return {
            "prompt_tokens": self.prompt_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "prompt_tokens_details": self.prompt_tokens_details
        }


@dataclass
class ContentItem:
    """Simulates a content item with text attribute for API compatibility."""
    type: str
    text: str


@dataclass
class ResponseOutput:
    """Simulates OpenAI Responses API output structure."""
    role: str
    content: List[ContentItem]


@dataclass
class MockResponse:
    """Simulates complete OpenAI Responses API response.

    This matches the actual API response structure so that code
    parsing the response works identically with mock and real API.
    """
    usage: UsageStats
    output: List[ResponseOutput]
    model: str
    id: str = "mock-response-id"
    created: int = 1234567890

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": self.id,
            "model": self.model,
            "created": self.created,
            "usage": self.usage.__dict__(),
            "output": [
                {
                    "role": out.role,
                    "content": [
                        {"type": item.type, "text": item.text}
                        for item in out.content
                    ]
                }
                for out in self.output
            ]
        }

    def model_dump(self) -> Dict[str, Any]:
        """Pydantic-compatible serialization method.

        CallResponsesAPIStage calls response.model_dump() to serialize
        the response to JSON. This method provides compatibility with
        Pydantic models used by the real OpenAI SDK.
        """
        return self.to_dict()


def load_metadata_fixture(doc_type: str) -> Dict[str, Any]:
    """Load metadata fixture from JSON file.

    Args:
        doc_type: Document type (invoice, receipt, utility_bill, bank_statement, unknown)

    Returns:
        Dictionary containing metadata structure
    """
    # Construct path relative to this file
    fixtures_dir = Path(__file__).parent.parent / "fixtures" / "metadata"
    fixture_path = fixtures_dir / f"{doc_type}.json"

    if not fixture_path.exists():
        raise FileNotFoundError(f"Fixture not found: {fixture_path}")

    with open(fixture_path, "r") as f:
        return json.load(f)


def create_mock_response(
    doc_type: str = "invoice",
    *,
    prompt_tokens: int = 1000,
    output_tokens: int = 200,
    cached_tokens: int = 0,
    model: str = "gpt-5"
) -> MockResponse:
    """Create a realistic mock response for testing.

    Args:
        doc_type: Type of document (invoice, receipt, utility_bill, bank_statement, unknown)
        prompt_tokens: Number of input tokens (default: 1000)
        output_tokens: Number of output tokens (default: 200)
        cached_tokens: Number of cached prompt tokens (default: 0)
        model: Model name (default: gpt-5)

    Returns:
        MockResponse object matching OpenAI API structure

    Example:
        >>> response = create_mock_response("invoice", prompt_tokens=500, output_tokens=100)
        >>> assert response.usage.prompt_tokens == 500
        >>> assert response.usage.output_tokens == 100
        >>> # Extract metadata
        >>> metadata_text = response.output[0].content[0]["text"]
        >>> metadata = json.loads(metadata_text)
        >>> assert metadata["doc_type"] == "Invoice"
    """
    # Load the fixture for this document type
    metadata = load_metadata_fixture(doc_type)

    # Create usage statistics
    usage = UsageStats(
        prompt_tokens=prompt_tokens,
        output_tokens=output_tokens,
        total_tokens=prompt_tokens + output_tokens,
        prompt_tokens_details={"cached_tokens": cached_tokens}
    )

    # Create output with JSON-formatted metadata
    output = [
        ResponseOutput(
            role="assistant",
            content=[
                ContentItem(
                    type="output_text",
                    text=json.dumps(metadata, indent=2)
                )
            ]
        )
    ]

    return MockResponse(
        usage=usage,
        output=output,
        model=model
    )


class MockResponsesNamespace:
    """Simulates client.responses namespace."""

    def __init__(
        self,
        default_doc_type: str = "invoice",
        error_simulator: Optional[Callable[[], None]] = None,
        custom_response_fn: Optional[Callable[..., MockResponse]] = None
    ):
        """Initialize mock responses namespace.

        Args:
            default_doc_type: Default document type for responses
            error_simulator: Optional function that raises errors for testing
            custom_response_fn: Optional function to generate custom responses
        """
        self.default_doc_type = default_doc_type
        self.error_simulator = error_simulator
        self.custom_response_fn = custom_response_fn
        self.call_count = 0

    def create(self, **kwargs) -> MockResponse:
        """Simulate client.responses.create() API call.

        Args:
            **kwargs: API request parameters (model, input, text, etc.)

        Returns:
            MockResponse object

        Raises:
            Various exceptions if error_simulator is configured

        Example:
            >>> responses = MockResponsesNamespace()
            >>> response = responses.create(model="gpt-5", input=[...])
            >>> assert response.model == "gpt-5"
        """
        self.call_count += 1

        # Simulate error if configured
        if self.error_simulator:
            self.error_simulator()

        # Use custom response function if provided
        if self.custom_response_fn:
            return self.custom_response_fn(**kwargs)

        # Extract model from kwargs
        model = kwargs.get("model", "gpt-5")

        # Extract file information if present for realistic token estimation
        input_data = kwargs.get("input", [])
        has_file = any(
            "content" in msg
            and any(item.get("type") == "input_file" for item in msg.get("content", []))
            for msg in input_data
        )

        # Estimate tokens based on input
        # Typical PDF upload: ~1000-5000 tokens
        # Typical output: ~100-300 tokens
        prompt_tokens = 3000 if has_file else 500
        output_tokens = 200

        # Create default response
        return create_mock_response(
            doc_type=self.default_doc_type,
            prompt_tokens=prompt_tokens,
            output_tokens=output_tokens,
            model=model
        )


class MockResponsesClient:
    """Complete mock of OpenAI client with Responses API.

    This can be used as a drop-in replacement for the real OpenAI client
    in tests.

    Example:
        >>> # Create mock client
        >>> client = MockResponsesClient(default_doc_type="invoice")
        >>>
        >>> # Use exactly like real client
        >>> response = client.responses.create(
        ...     model="gpt-5",
        ...     input=[{
        ...         "role": "user",
        ...         "content": [{"type": "input_text", "text": "Extract metadata"}]
        ...     }]
        ... )
        >>>
        >>> # Response structure matches real API
        >>> assert response.usage.prompt_tokens > 0
        >>> assert response.output[0].role == "assistant"
    """

    def __init__(
        self,
        default_doc_type: str = "invoice",
        error_simulator: Optional[Callable[[], None]] = None,
        custom_response_fn: Optional[Callable[..., MockResponse]] = None
    ):
        """Initialize mock OpenAI client.

        Args:
            default_doc_type: Default document type for responses
            error_simulator: Optional function that raises errors
            custom_response_fn: Optional function for custom responses
        """
        self.responses = MockResponsesNamespace(
            default_doc_type=default_doc_type,
            error_simulator=error_simulator,
            custom_response_fn=custom_response_fn
        )


# Convenience functions for common test scenarios

def create_mock_client_with_doc_type(doc_type: str) -> MockResponsesClient:
    """Create a mock client that always returns a specific document type.

    Args:
        doc_type: Document type (invoice, receipt, utility_bill, bank_statement, unknown)

    Returns:
        Configured MockResponsesClient

    Example:
        >>> client = create_mock_client_with_doc_type("receipt")
        >>> response = client.responses.create(model="gpt-5", input=[...])
        >>> metadata = json.loads(response.output[0].content[0]["text"])
        >>> assert metadata["doc_type"] == "Receipt"
    """
    return MockResponsesClient(default_doc_type=doc_type)


def create_mock_client_with_errors(error_fn: Callable[[], None]) -> MockResponsesClient:
    """Create a mock client that simulates errors.

    Args:
        error_fn: Function that raises the desired error

    Returns:
        Configured MockResponsesClient that will raise errors

    Example:
        >>> from tests.mocks.error_simulator import simulate_rate_limit
        >>> client = create_mock_client_with_errors(simulate_rate_limit)
        >>> with pytest.raises(RateLimitError):
        ...     client.responses.create(model="gpt-5", input=[...])
    """
    return MockResponsesClient(error_simulator=error_fn)


def create_mock_client_with_custom_tokens(
    prompt_tokens: int,
    output_tokens: int,
    cached_tokens: int = 0
) -> MockResponsesClient:
    """Create a mock client with specific token counts for cost testing.

    Args:
        prompt_tokens: Number of prompt tokens
        output_tokens: Number of output tokens
        cached_tokens: Number of cached tokens

    Returns:
        Configured MockResponsesClient

    Example:
        >>> # Test high-cost scenario
        >>> client = create_mock_client_with_custom_tokens(
        ...     prompt_tokens=50000,
        ...     output_tokens=10000
        ... )
        >>> response = client.responses.create(model="gpt-5", input=[...])
        >>> assert response.usage.prompt_tokens == 50000
    """
    def custom_response(**kwargs):
        model = kwargs.get("model", "gpt-5")
        return create_mock_response(
            "invoice",
            prompt_tokens=prompt_tokens,
            output_tokens=output_tokens,
            cached_tokens=cached_tokens,
            model=model
        )

    return MockResponsesClient(custom_response_fn=custom_response)
