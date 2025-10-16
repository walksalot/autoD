"""
Comprehensive retry logic for OpenAI API calls with exponential backoff.

Handles ALL transient errors including rate limits, timeouts, connection errors,
and server-side errors (5xx). Non-retryable errors (4xx client errors) fail fast.

Usage:
    from openai import OpenAI
    from src.retry_logic import call_openai_with_retry

    client = OpenAI(api_key="sk-...")

    try:
        response = call_openai_with_retry(
            client,
            model="gpt-5",
            input=[{"role": "user", "content": [...]}],
            text={"format": {"type": "json_object"}}
        )
        print("Success!")
    except Exception as e:
        print(f"Failed after 5 retries: {e}")
"""

from tenacity import (
    retry as _tenacity_retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception,
    before_sleep_log,
)
from openai import RateLimitError, APIConnectionError, APIError, Timeout
import logging

logger = logging.getLogger(__name__)


def is_retryable_api_error(exception: BaseException) -> bool:
    """
    Determine if an OpenAI API error should be retried.

    Retryable errors (transient):
    - RateLimitError (429): Rate limit exceeded
    - APIConnectionError: Network connectivity issues
    - Timeout: Request timed out
    - APIError with 5xx status: Server-side errors (500, 502, 503, 504)

    Non-retryable errors (permanent):
    - AuthenticationError (401): Invalid API key
    - PermissionDeniedError (403): Insufficient permissions
    - BadRequestError (400): Malformed request
    - NotFoundError (404): Resource doesn't exist
    - APIError with 4xx status: Client errors

    Args:
        exception: The exception to check

    Returns:
        True if error should be retried, False otherwise

    Examples:
        >>> is_retryable_api_error(RateLimitError("rate limit"))
        True
        >>> is_retryable_api_error(APIConnectionError("connection failed"))
        True
        >>> is_retryable_api_error(Timeout("request timeout"))
        True
        >>> error = APIError("server error")
        >>> error.status_code = 500
        >>> is_retryable_api_error(error)
        True
        >>> error.status_code = 400
        >>> is_retryable_api_error(error)
        False
    """
    # Always retry rate limits, connection errors, timeouts
    if isinstance(exception, (RateLimitError, APIConnectionError, Timeout)):
        logger.info(f"Retryable error: {type(exception).__name__}")
        return True

    # Retry server errors (5xx), but not client errors (4xx)
    if isinstance(exception, APIError):
        if hasattr(exception, "status_code"):
            status_code = exception.status_code
            is_server_error = status_code >= 500
            logger.info(f"API error {status_code}: retryable={is_server_error}")
            return is_server_error
        # Unknown API error - don't retry
        return False

    # Inspect message for transient cues (rate limit, timeout, overloaded)
    message = str(exception).lower()
    transient_markers = [
        "rate limit",
        "retry later",
        "timed out",
        "timeout",
        "temporarily unavailable",
        "server overloaded",
        "service unavailable",
        "503",
        "504",
    ]
    if any(marker in message for marker in transient_markers):
        logger.info("Retryable error inferred from message: %s", message)
        return True

    # Don't retry unknown exceptions otherwise
    return False


def retry(*, max_attempts: int = 5, initial_wait: float = 2.0, max_wait: float = 60.0):
    """
    Decorator that retries a function when `is_retryable_api_error` returns True.

    Args:
        max_attempts: Maximum attempts before giving up.
        initial_wait: Base multiplier for exponential backoff (seconds).
        max_wait: Maximum wait between retries.
    """

    def decorator(func):
        return _tenacity_retry(
            retry=retry_if_exception(is_retryable_api_error),
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=initial_wait, max=max_wait),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        )(func)

    return decorator


@retry()
def call_openai_with_retry(client, **kwargs):
    """
    Call OpenAI Responses API with exponential backoff retry.

    Retry schedule:
    - Attempt 1: immediate
    - Attempt 2: wait 2s
    - Attempt 3: wait 4s
    - Attempt 4: wait 8s
    - Attempt 5: wait 16s (then give up)

    Max total wait: ~30 seconds across all retries

    Args:
        client: OpenAI client instance
        **kwargs: Arguments to pass to client.responses.create()

    Returns:
        API response object

    Raises:
        Exception: After 5 failed attempts, re-raises the last exception

    Examples:
        >>> from openai import OpenAI
        >>> client = OpenAI(api_key="sk-...")
        >>> response = call_openai_with_retry(
        ...     client,
        ...     model="gpt-5",
        ...     input=[{
        ...         "role": "user",
        ...         "content": [
        ...             {"type": "input_text", "text": "Extract metadata"},
        ...             {"type": "input_file", "filename": "doc.pdf", "file_data": "data:..."}
        ...         ]
        ...     }],
        ...     text={"format": {"type": "json_object"}}
        ... )
    """
    logger.info("Calling OpenAI Responses API")
    return client.responses.create(**kwargs)
