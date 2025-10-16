"""Pydantic data models for token counting."""

from __future__ import annotations

from typing import Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


class TokenCount(BaseModel):
    """Token count breakdown."""

    total: int = Field(ge=0, description="Total tokens")
    billable: int = Field(ge=0, description="Billable tokens (excluding cached)")
    cached: int = Field(ge=0, description="Cached tokens")

    def __str__(self) -> str:
        if self.cached > 0:
            return (
                f"{self.total} tokens ({self.billable} billable, {self.cached} cached)"
            )
        return f"{self.total} tokens"


class TokenEstimate(BaseModel):
    """Token estimate with confidence range."""

    min_tokens: int = Field(ge=0, description="Minimum estimated tokens")
    max_tokens: int = Field(ge=0, description="Maximum estimated tokens")
    confidence: Literal["high", "medium", "low"] = Field(
        description="Confidence level of estimate"
    )
    basis: str = Field(description="Explanation of how estimate was calculated")

    @property
    def midpoint(self) -> int:
        """Return midpoint of estimate range."""
        return (self.min_tokens + self.max_tokens) // 2

    def __str__(self) -> str:
        if self.min_tokens == self.max_tokens:
            return f"{self.min_tokens} tokens ({self.confidence} confidence)"
        return (
            f"{self.min_tokens}-{self.max_tokens} tokens ({self.confidence} confidence)"
        )


class CostEstimate(BaseModel):
    """Cost estimate in USD."""

    input_usd: float = Field(ge=0, description="Input token cost in USD")
    output_usd: float = Field(ge=0, description="Output token cost in USD")
    cached_input_usd: float = Field(ge=0, description="Cached input token cost in USD")
    total_usd: float = Field(ge=0, description="Total cost in USD")

    def __str__(self) -> str:
        return f"${self.total_usd:.6f}"


class TokenResult(BaseModel):
    """Complete token counting result with breakdown.

    This model is returned by API calculators and includes:
    - Model name and encoding used
    - Token count breakdown
    - Optional file token estimate
    - Optional metadata
    """

    model: str = Field(description="Model name used for counting")
    encoding: str = Field(description="Encoding name (e.g., 'o200k_base')")
    count: TokenCount = Field(description="Token counts")
    breakdown: Dict[str, int] = Field(
        default_factory=dict,
        description="Component breakdown (messages, tools, files, etc.)",
    )
    file_estimate: Optional[TokenEstimate] = Field(
        None, description="File token estimate if files present"
    )
    metadata: Dict[str, Union[str, int, float]] = Field(
        default_factory=dict, description="Additional metadata"
    )

    def __str__(self) -> str:
        parts = [f"{self.count}"]
        if self.file_estimate:
            parts.append(f"Files: {self.file_estimate}")
        return " | ".join(parts)


class EncodingMetadata(BaseModel):
    """Metadata about a tiktoken encoding."""

    name: str
    description: str
    vocab_size: int
    models: List[str] = Field(default_factory=list)


class ValidationResult(BaseModel):
    """Result of token count validation against actual API usage."""

    model: str
    estimated: int
    actual: int
    delta: int
    delta_pct: float
    cached_tokens: int
    file_path: Optional[str] = None
    timestamp: str

    @property
    def within_tolerance(self) -> bool:
        """Check if delta is within ±10% tolerance."""
        return abs(self.delta_pct) <= 10.0

    def __str__(self) -> str:
        sign = "+" if self.delta > 0 else ""
        return (
            f"Estimated: {self.estimated}, Actual: {self.actual}, "
            f"Delta: {sign}{self.delta} ({sign}{self.delta_pct:.1f}%)"
        )
