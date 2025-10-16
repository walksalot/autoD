"""Error simulation utilities for testing retry logic and error handling.

This module provides functions to simulate various OpenAI API errors
for testing purposes. These errors can be injected into mock API responses
to verify that retry logic and error handling work correctly.

Example usage:
    from tests.mocks.error_simulator import simulate_rate_limit, ErrorAfterNCalls

    # Simulate a rate limit error
    with pytest.raises(RateLimitError):
        simulate_rate_limit()

    # Fail first 2 calls, then succeed
    counter = ErrorAfterNCalls(2, lambda: simulate_rate_limit())
    counter()  # Raises RateLimitError
    counter()  # Raises RateLimitError
    counter()  # Returns None (success)
"""

from typing import Optional, Callable


# Mock OpenAI error classes for testing
# These simulate the actual OpenAI SDK exception types
class RateLimitError(Exception):
    """Simulates openai.RateLimitError (HTTP 429)."""

    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(message)
        self.status_code = 429


class APIConnectionError(Exception):
    """Simulates openai.APIConnectionError (network connectivity issues)."""

    def __init__(self, message: str = "Connection error"):
        super().__init__(message)


class Timeout(Exception):
    """Simulates openai.Timeout (request timed out)."""

    def __init__(self, message: str = "Request timed out"):
        super().__init__(message)


class APIError(Exception):
    """Simulates openai.APIError with configurable status code."""

    def __init__(self, message: str = "API error", status_code: int = 500):
        super().__init__(message)
        self.status_code = status_code


class AuthenticationError(Exception):
    """Simulates openai.AuthenticationError (HTTP 401)."""

    def __init__(self, message: str = "Invalid API key"):
        super().__init__(message)
        self.status_code = 401


class BadRequestError(Exception):
    """Simulates openai.BadRequestError (HTTP 400)."""

    def __init__(self, message: str = "Bad request"):
        super().__init__(message)
        self.status_code = 400


# Error simulation functions


def simulate_rate_limit(
    message: str = "Rate limit exceeded, please retry after 60 seconds",
) -> None:
    """Raise a RateLimitError to simulate hitting OpenAI rate limits.

    Args:
        message: Custom error message

    Raises:
        RateLimitError: Always raises

    Example:
        >>> with pytest.raises(RateLimitError):
        ...     simulate_rate_limit()
    """
    raise RateLimitError(message)


def simulate_timeout(message: str = "Request timed out after 300 seconds") -> None:
    """Raise a Timeout error to simulate request timeouts.

    Args:
        message: Custom error message

    Raises:
        Timeout: Always raises

    Example:
        >>> with pytest.raises(Timeout):
        ...     simulate_timeout()
    """
    raise Timeout(message)


def simulate_connection_error(message: str = "Connection refused by server") -> None:
    """Raise an APIConnectionError to simulate network connectivity issues.

    Args:
        message: Custom error message

    Raises:
        APIConnectionError: Always raises

    Example:
        >>> with pytest.raises(APIConnectionError):
        ...     simulate_connection_error()
    """
    raise APIConnectionError(message)


def simulate_api_error(status_code: int = 500, message: Optional[str] = None) -> None:
    """Raise an APIError with a specific HTTP status code.

    Use this to simulate server-side errors (5xx) or client errors (4xx).

    Args:
        status_code: HTTP status code (e.g., 500, 502, 503, 400, 404)
        message: Custom error message. If None, generates default message.

    Raises:
        APIError: Always raises with specified status code

    Example:
        >>> # Simulate 503 Service Unavailable
        >>> with pytest.raises(APIError) as exc_info:
        ...     simulate_api_error(503)
        >>> assert exc_info.value.status_code == 503

        >>> # Simulate 500 Internal Server Error
        >>> with pytest.raises(APIError):
        ...     simulate_api_error(500, "Internal server error")
    """
    if message is None:
        message = f"API error (HTTP {status_code})"

    raise APIError(message, status_code=status_code)


def simulate_auth_error(message: str = "Invalid API key provided") -> None:
    """Raise an AuthenticationError to simulate invalid credentials.

    Args:
        message: Custom error message

    Raises:
        AuthenticationError: Always raises

    Example:
        >>> with pytest.raises(AuthenticationError):
        ...     simulate_auth_error()
    """
    raise AuthenticationError(message)


def simulate_bad_request(message: str = "Invalid request parameters") -> None:
    """Raise a BadRequestError to simulate malformed requests.

    Args:
        message: Custom error message

    Raises:
        BadRequestError: Always raises

    Example:
        >>> with pytest.raises(BadRequestError):
        ...     simulate_bad_request()
    """
    raise BadRequestError(message)


class ErrorAfterNCalls:
    """Helper to simulate errors that occur after N successful calls.

    Useful for testing retry logic that needs to fail a specific number
    of times before succeeding.

    Example:
        >>> counter = ErrorAfterNCalls(2, lambda: simulate_rate_limit())
        >>> counter()  # Raises RateLimitError (call 1)
        >>> counter()  # Raises RateLimitError (call 2)
        >>> counter()  # Returns None (call 3, success)
        >>> counter()  # Returns None (call 4, success)
    """

    def __init__(self, fail_count: int, error_fn: Callable[[], None]):
        """Initialize error counter.

        Args:
            fail_count: Number of times to raise error before succeeding
            error_fn: Function that raises the desired error
        """
        self.fail_count = fail_count
        self.error_fn = error_fn
        self.call_count = 0

    def __call__(self) -> None:
        """Invoke the error simulator.

        Raises the specified error for the first N calls,
        then succeeds silently.
        """
        self.call_count += 1
        if self.call_count <= self.fail_count:
            self.error_fn()
        # Otherwise, succeed silently


class RandomErrorSimulator:
    """Simulate errors with a specified probability.

    Useful for stress testing error handling with non-deterministic failures.

    Example:
        >>> import random
        >>> random.seed(42)  # For deterministic tests
        >>> sim = RandomErrorSimulator(0.3, lambda: simulate_rate_limit())
        >>> # About 30% of calls will raise RateLimitError
        >>> for _ in range(100):
        ...     try:
        ...         sim()
        ...     except RateLimitError:
        ...         pass  # Expected
    """

    def __init__(
        self,
        error_probability: float,
        error_fn: Callable[[], None],
        seed: Optional[int] = None,
    ):
        """Initialize random error simulator.

        Args:
            error_probability: Probability of error (0.0 to 1.0)
            error_fn: Function that raises the desired error
            seed: Optional random seed for deterministic testing
        """
        import random

        self.error_probability = error_probability
        self.error_fn = error_fn
        self.random = random.Random(seed)

    def __call__(self) -> None:
        """Invoke the error simulator with probability.

        Raises error with the specified probability.
        """
        if self.random.random() < self.error_probability:
            self.error_fn()
        # Otherwise, succeed silently
