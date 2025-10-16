"""
OpenAI Responses API client with retry logic and circuit breaker.
Implements exponential backoff and error handling for production use.
"""

from typing import Dict, Any, Optional
import time
import json
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
from openai import OpenAI, RateLimitError, APIConnectionError, APITimeoutError
import logging
import requests

from src.config import get_config


logger = logging.getLogger("paper_autopilot")


class CircuitBreaker:
    """
    Circuit breaker pattern to prevent cascade failures.

    States:
    - CLOSED: Normal operation
    - OPEN: Too many failures, reject requests immediately
    - HALF_OPEN: Testing if service recovered
    """

    def __init__(self, failure_threshold: int = 10, timeout: int = 60):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            timeout: Seconds to wait before entering half-open state
        """
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = "CLOSED"

    def call(self, func, *args, **kwargs):
        """
        Execute function through circuit breaker.

        Args:
            func: Function to execute
            *args, **kwargs: Arguments to pass to function

        Returns:
            Function result

        Raises:
            Exception: If circuit is OPEN or function fails
        """
        if self.state == "OPEN":
            if time.time() - self.last_failure_time >= self.timeout:
                self.state = "HALF_OPEN"
                logger.info("Circuit breaker entering HALF_OPEN state")
            else:
                raise Exception(f"Circuit breaker OPEN (failures: {self.failure_count})")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e

    def _on_success(self):
        """Reset circuit breaker on successful call."""
        if self.state == "HALF_OPEN":
            self.state = "CLOSED"
            logger.info("Circuit breaker CLOSED (service recovered)")

        self.failure_count = 0

    def _on_failure(self):
        """Record failure and potentially open circuit."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            logger.warning(f"Circuit breaker OPEN after {self.failure_count} failures")


class ResponsesAPIClient:
    """
    OpenAI Responses API client with production-grade error handling.

    Features:
    - Exponential backoff retry logic
    - Circuit breaker pattern
    - Rate limiting
    - Comprehensive error handling
    """

    def __init__(self, client: Optional[OpenAI] = None):
        """
        Initialize API client.

        Args:
            client: OpenAI client (creates new if None)
        """
        config = get_config()
        self.client = client or OpenAI(
            api_key=config.openai_api_key,
            timeout=config.api_timeout_seconds,
        )
        self.config = config
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=10,
            timeout=60,
        )
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {config.openai_api_key}",
                "Content-Type": "application/json",
            }
        )
        self._api_url = "https://api.openai.com/v1/responses"

    @retry(
        wait=wait_exponential(multiplier=1, min=4, max=60),
        stop=stop_after_attempt(5),
        retry=retry_if_exception_type((
            RateLimitError,
            APIConnectionError,
            APITimeoutError,
        )),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def _call_responses_api_with_retry(
        self,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Call Responses API with automatic retry.

        Retries on:
        - RateLimitError (5xx, rate limits)
        - APIConnectionError (network issues)
        - APITimeoutError (timeout)

        Does NOT retry on:
        - AuthenticationError (invalid API key)
        - InvalidRequestError (bad request)

        Args:
            payload: Complete API request payload

        Returns:
            API response as dict

        Raises:
            Exception: If all retries exhausted or non-retryable error
        """
        logger.info(f"Calling Responses API (model: {payload.get('model')})")

        try:
            response = self.client.post(
                "/v1/responses",
                cast_to=dict,
                body=payload,
            )
            logger.info(f"API call successful (OpenAI SDK)")
            return response
        except APIConnectionError as err:
            logger.warning(
                "OpenAI SDK connection error, retrying with requests session: %s",
                err,
            )
            return self._post_with_requests(payload)

    def _post_with_requests(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fallback HTTP POST using requests.Session.

        This avoids known chunked-transfer issues with httpx/LibreSSL on macOS.
        """
        try:
            response = self._session.post(
                self._api_url,
                json=payload,
                timeout=self.config.api_timeout_seconds,
            )
        except requests.RequestException as exc:
            raise APIConnectionError(message=str(exc)) from exc

        if 500 <= response.status_code < 600:
            raise APIConnectionError(
                message=f"Server error {response.status_code}: {response.text}"
            )

        if response.status_code >= 400:
            try:
                error_payload = response.json()
            except json.JSONDecodeError:
                error_payload = {"error": {"message": response.text}}
            message = error_payload.get("error", {}).get("message", response.text)
            raise ValueError(f"OpenAI API error {response.status_code}: {message}")

        logger.info("API call successful (requests fallback)")
        return response.json()

    def create_response(
        self,
        payload: Dict[str, Any],
        use_circuit_breaker: bool = True,
    ) -> Dict[str, Any]:
        """
        Create a response using OpenAI Responses API.

        Args:
            payload: Complete API request payload
            use_circuit_breaker: Whether to use circuit breaker

        Returns:
            API response dict

        Raises:
            Exception: If request fails after retries
        """
        if use_circuit_breaker:
            return self.circuit_breaker.call(
                self._call_responses_api_with_retry,
                payload
            )
        else:
            return self._call_responses_api_with_retry(payload)

    def extract_output_text(self, response: Dict[str, Any]) -> str:
        """
        Extract output text from Responses API response.

        Args:
            response: API response dict

        Returns:
            Extracted text content

        Raises:
            KeyError: If response structure is invalid
        """
        # Response structure: response["output"][0]["content"][0]["text"]
        output_items = response.get("output", [])
        if not output_items:
            raise ValueError("No output in response")

        for item in output_items:
            if item.get("type") != "message":
                continue
            content_parts = item.get("content", [])
            for part in content_parts:
                if part.get("type") in {"output_text", "text"}:
                    return part.get("text", "")
                if part.get("type") == "output_json_schema":
                    return part.get("json_schema", "")

        raise ValueError("No content in output")

    def extract_usage(self, response: Dict[str, Any]) -> Dict[str, int]:
        """
        Extract token usage from response.

        Args:
            response: API response dict

        Returns:
            Dict with prompt_tokens, completion_tokens, cached_tokens
        """
        usage = response.get("usage", {})

        prompt_tokens = usage.get("prompt_tokens", usage.get("input_tokens", 0))
        completion_tokens = usage.get("completion_tokens", usage.get("output_tokens", 0))

        # Extract cached tokens from prompt/input token details
        prompt_tokens_details = usage.get(
            "prompt_tokens_details", usage.get("input_tokens_details", {})
        )
        cached_tokens = prompt_tokens_details.get("cached_tokens", 0)

        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cached_tokens": cached_tokens,
        }


# Example usage
if __name__ == "__main__":
    import base64
    import json

    from src.prompts import build_responses_api_payload

    print("=== API Client Test ===")

    # Initialize client
    client = ResponsesAPIClient()
    print(f"✅ Client initialized")
    print(f"   Timeout: {client.config.api_timeout_seconds}s")
    print(f"   Max retries: {client.config.max_retries}")

    # Test 1: Circuit breaker
    print("\nTest 1: Circuit breaker")
    cb = CircuitBreaker(failure_threshold=3, timeout=5)
    print(f"✅ Initial state: {cb.state}")

    # Simulate failures
    for i in range(3):
        try:
            cb.call(lambda: 1 / 0)  # Raises ZeroDivisionError
        except:
            print(f"   Failure {i + 1} recorded")

    print(f"✅ State after 3 failures: {cb.state}")

    if cb.state == "OPEN":
        print("✅ Circuit breaker opened correctly")
    else:
        print("❌ Circuit breaker should be OPEN")

    # Test 2: Payload building
    print("\nTest 2: Build test payload")
    test_pdf_content = b"%PDF-1.4\nTest content"
    test_pdf_base64 = f"data:application/pdf;base64,{base64.b64encode(test_pdf_content).decode()}"

    payload = build_responses_api_payload(
        filename="test.pdf",
        pdf_base64=test_pdf_base64,
        processed_at="2025-01-01T00:00:00Z",
        original_file_name="test.pdf",
        source_file_id="file-test-id",
    )

    print(f"✅ Payload built")
    print(f"   Model: {payload['model']}")
    print(f"   Roles: {[msg['role'] for msg in payload['input']]}")
    print(f"   Has schema: {'text' in payload and 'format' in payload['text']}")

    # Test 3: Extract output (mock response)
    print("\nTest 3: Extract output from mock response")
    mock_response = {
        "output": [{
            "content": [{
                "text": '{"schema_version": "1.0.0", "doc_type": "Invoice"}'
            }]
        }],
        "usage": {
            "prompt_tokens": 2000,
            "completion_tokens": 500,
            "prompt_tokens_details": {
                "cached_tokens": 1800
            }
        }
    }

    text = client.extract_output_text(mock_response)
    print(f"✅ Extracted text: {text[:50]}...")

    usage = client.extract_usage(mock_response)
    print(f"✅ Usage: {usage}")

    if usage["cached_tokens"] == 1800:
        print("✅ Cached tokens extracted correctly")

    print("\n=== All Tests Complete ===")
    print("Note: Actual API calls skipped (require valid API key and credits)")
