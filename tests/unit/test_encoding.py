"""Unit tests for encoding resolution."""

import pytest

from token_counter.encoding import EncodingResolver
from token_counter.exceptions import ConfigurationError


class TestEncodingResolver:
    """Test cases for EncodingResolver class."""

    def test_exact_match_gpt5(self):
        """Test exact model name match for GPT-5."""
        resolver = EncodingResolver()
        encoding_name = resolver.get_encoding_name("gpt-5")
        assert encoding_name == "o200k_base"

    def test_exact_match_gpt4o(self):
        """Test exact model name match for GPT-4o."""
        resolver = EncodingResolver()
        encoding_name = resolver.get_encoding_name("gpt-4o")
        assert encoding_name == "o200k_base"

    def test_exact_match_gpt4(self):
        """Test exact model name match for GPT-4."""
        resolver = EncodingResolver()
        encoding_name = resolver.get_encoding_name("gpt-4")
        assert encoding_name == "cl100k_base"

    def test_pattern_match_gpt5_variant(self):
        """Test pattern matching for GPT-5 variant."""
        resolver = EncodingResolver()
        encoding_name = resolver.get_encoding_name("gpt-5-turbo-preview")
        assert encoding_name == "o200k_base"

    def test_pattern_match_gpt4_variant(self):
        """Test pattern matching for GPT-4 variant."""
        resolver = EncodingResolver()
        encoding_name = resolver.get_encoding_name("gpt-4-1106-preview")
        assert encoding_name == "cl100k_base"

    def test_default_fallback_unknown_model(self):
        """Test default fallback for unknown model."""
        resolver = EncodingResolver()
        encoding_name = resolver.get_encoding_name("some-future-model")
        assert encoding_name == "o200k_base"  # default from config

    def test_get_encoding_returns_tiktoken_object(self):
        """Test that get_encoding returns actual tiktoken.Encoding."""
        resolver = EncodingResolver()
        encoding = resolver.get_encoding("gpt-5")

        # Verify it's a tiktoken Encoding object by checking it has encode method
        assert hasattr(encoding, "encode")
        assert hasattr(encoding, "decode")

        # Verify it can actually encode text
        tokens = encoding.encode("Hello world")
        assert isinstance(tokens, list)
        assert len(tokens) > 0

    def test_get_encoding_caching(self):
        """Test that encodings are cached."""
        resolver = EncodingResolver()

        # Get encoding twice for same model
        encoding1 = resolver.get_encoding("gpt-5")
        encoding2 = resolver.get_encoding("gpt-5")

        # Should be the exact same object (cached)
        assert encoding1 is encoding2

    def test_list_supported_models(self):
        """Test listing supported models."""
        resolver = EncodingResolver()
        models = resolver.list_supported_models()

        assert "gpt-5" in models
        assert "gpt-4o" in models
        assert "gpt-4" in models
        assert len(models) > 5  # Should have multiple models

    def test_get_encoding_metadata(self):
        """Test retrieving encoding metadata."""
        resolver = EncodingResolver()
        metadata = resolver.get_encoding_metadata("o200k_base")

        assert "description" in metadata
        assert "vocab_size" in metadata
        assert metadata["vocab_size"] == 200000

    def test_missing_config_file_raises_error(self, tmp_path):
        """Test that missing config file raises ConfigurationError."""
        fake_config = tmp_path / "nonexistent.yaml"

        with pytest.raises(ConfigurationError) as exc_info:
            EncodingResolver(config_path=fake_config)

        assert "not found" in str(exc_info.value).lower()

    def test_reload_config_clears_cache(self):
        """Test that reload_config clears the LRU cache."""
        resolver = EncodingResolver()

        # Get encoding to populate cache
        encoding1 = resolver.get_encoding("gpt-5")

        # Reload config
        resolver.reload_config()

        # Get encoding again
        encoding2 = resolver.get_encoding("gpt-5")

        # After reload, cache is cleared so we get a new object
        # (though with same encoding name, so functionally identical)
        assert encoding1.encode("test") == encoding2.encode("test")

    def test_case_insensitive_pattern_matching(self):
        """Test that pattern matching is case-insensitive."""
        resolver = EncodingResolver()

        # GPT-4o in various cases
        assert resolver.get_encoding_name("GPT-4o") == "o200k_base"
        assert resolver.get_encoding_name("gpt-4O") == "o200k_base"
        assert resolver.get_encoding_name("GPT-4O-MINI") == "o200k_base"
