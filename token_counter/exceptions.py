"""Custom exceptions for token counting module."""

from __future__ import annotations


class TokenCountError(Exception):
    """Base exception for token counting errors."""

    pass


class EncodingNotFoundError(TokenCountError):
    """Raised when a model's encoding cannot be determined."""

    def __init__(self, model: str, attempted_fallbacks: list[str] | None = None):
        self.model = model
        self.attempted_fallbacks = attempted_fallbacks or []
        msg = f"Could not determine encoding for model '{model}'"
        if attempted_fallbacks:
            msg += f" (tried: {', '.join(attempted_fallbacks)})"
        super().__init__(msg)


class InvalidMessageFormatError(TokenCountError):
    """Raised when message format is invalid or unsupported."""

    pass


class ConfigurationError(TokenCountError):
    """Raised when configuration files are invalid or missing."""

    pass


class ValidationError(TokenCountError):
    """Raised during token count validation failures."""

    pass
