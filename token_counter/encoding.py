"""Encoding resolution for tiktoken models."""

from __future__ import annotations

import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import tiktoken
import yaml

from .exceptions import ConfigurationError, EncodingNotFoundError

logger = logging.getLogger(__name__)

# Default config path relative to this file
DEFAULT_CONFIG_PATH = Path(__file__).parent.parent / "config" / "model_encodings.yaml"


class EncodingResolver:
    """
    Resolves tiktoken encodings for OpenAI models using config-driven fallback chain.

    Resolution strategy:
    1. Try exact model name match from config
    2. Try regex pattern match from config
    3. Use default encoding from config
    4. Raise EncodingNotFoundError if all fail

    Example:
        >>> resolver = EncodingResolver()
        >>> encoding = resolver.get_encoding("gpt-5")
        >>> tokens = encoding.encode("Hello world")
    """

    def __init__(self, config_path: str | Path | None = None):
        """
        Initialize encoding resolver.

        Args:
            config_path: Path to model_encodings.yaml config file.
                        If None, uses default location in config/
        """
        self.config_path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
        self._config: dict[str, Any] | None = None
        self._load_config()

    def _load_config(self) -> None:
        """Load configuration from YAML file."""
        if not self.config_path.exists():
            raise ConfigurationError(
                f"Model encodings config not found at {self.config_path}"
            )

        try:
            with open(self.config_path, "r") as f:
                self._config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigurationError(
                f"Invalid YAML in {self.config_path}: {e}"
            ) from e

        # Validate required sections
        required = ["exact_matches", "pattern_matches", "default_encoding"]
        missing = [k for k in required if k not in self._config]
        if missing:
            raise ConfigurationError(
                f"Missing required config sections: {', '.join(missing)}"
            )

        logger.info(
            f"Loaded encoding config v{self._config.get('version', '?')} "
            f"from {self.config_path}"
        )

    def get_encoding_name(self, model: str) -> str:
        """
        Resolve encoding name for a model using fallback chain.

        Args:
            model: OpenAI model name (e.g., "gpt-5", "gpt-4o-mini")

        Returns:
            Encoding name (e.g., "o200k_base", "cl100k_base")

        Raises:
            EncodingNotFoundError: If encoding cannot be determined
        """
        attempted = []

        # Step 1: Try exact match
        exact_matches = self._config.get("exact_matches", {})
        if model in exact_matches:
            encoding_name = exact_matches[model]
            logger.debug(f"Resolved {model} to {encoding_name} via exact match")
            return encoding_name
        attempted.append("exact_match")

        # Step 2: Try pattern matches
        pattern_matches = self._config.get("pattern_matches", [])
        for entry in pattern_matches:
            pattern = entry.get("pattern")
            encoding_name = entry.get("encoding")
            if not pattern or not encoding_name:
                continue

            if re.search(pattern, model, re.IGNORECASE):
                logger.debug(
                    f"Resolved {model} to {encoding_name} via pattern '{pattern}'"
                )
                return encoding_name
        attempted.append("pattern_match")

        # Step 3: Use default encoding
        default = self._config.get("default_encoding")
        if default:
            logger.warning(
                f"No match for model '{model}', using default encoding '{default}'"
            )
            return default

        # Step 4: All failed
        raise EncodingNotFoundError(model, attempted_fallbacks=attempted)

    @lru_cache(maxsize=32)
    def get_encoding(self, model: str) -> tiktoken.Encoding:
        """
        Get tiktoken Encoding object for a model.

        This method is cached to avoid re-loading encodings for the same model.

        Args:
            model: OpenAI model name

        Returns:
            tiktoken.Encoding object

        Raises:
            EncodingNotFoundError: If encoding cannot be determined
        """
        encoding_name = self.get_encoding_name(model)

        try:
            encoding = tiktoken.get_encoding(encoding_name)
            logger.debug(f"Loaded tiktoken encoding '{encoding_name}' for {model}")
            return encoding
        except Exception as e:
            # tiktoken.get_encoding can raise various exceptions
            raise EncodingNotFoundError(
                model, attempted_fallbacks=[encoding_name]
            ) from e

    def get_encoding_metadata(self, encoding_name: str) -> dict[str, Any]:
        """
        Get metadata about an encoding from config.

        Args:
            encoding_name: Name of encoding (e.g., "o200k_base")

        Returns:
            Dictionary with metadata (description, vocab_size, etc.)
        """
        metadata = self._config.get("encoding_metadata", {}).get(encoding_name, {})
        return metadata

    def list_supported_models(self) -> list[str]:
        """
        List all explicitly supported model names from config.

        Returns:
            List of model names with exact match entries
        """
        return list(self._config.get("exact_matches", {}).keys())

    def reload_config(self) -> None:
        """Reload configuration from file (for hot-reload support)."""
        self._load_config()
        # Clear LRU cache to force re-resolution
        self.get_encoding.cache_clear()
        logger.info("Encoding config reloaded and cache cleared")
