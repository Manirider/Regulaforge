"""LLM provider port interface.

Abstracts interactions with Large Language Models, enabling
swappable backends (OpenAI, Anthropic, Azure OpenAI, local models)
without affecting the application logic.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class LLMResponse:
    """Standardized response from an LLM call."""

    content: str
    model: str
    usage: dict[str, int] = field(default_factory=lambda: {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
    })
    finish_reason: str = "stop"
    latency_ms: float = 0.0
    raw_response: Optional[dict[str, Any]] = None


@dataclass
class LLMMessage:
    """A message in a conversation with an LLM."""

    role: str  # "system", "user", "assistant"
    content: str
    name: Optional[str] = None


class LLMProvider(ABC):
    """Port interface for LLM interactions.

    All AI features use this interface, enabling
    provider-agnostic prompt execution.
    """

    @abstractmethod
    async def generate(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        stop_sequences: Optional[list[str]] = None,
        response_format: Optional[dict[str, Any]] = None,
    ) -> LLMResponse:
        """Generate a response from the LLM.

        Args:
            messages: Conversation messages.
            temperature: Sampling temperature (0.0-2.0).
            max_tokens: Maximum tokens to generate.
            stop_sequences: Sequences that stop generation.
            response_format: Structured output format (e.g., JSON).

        Returns:
            LLMResponse containing the generated content.

        Raises:
            LLMProviderError: If the LLM call fails.
        """
        ...

    @abstractmethod
    async def generate_structured(
        self,
        messages: list[LLMMessage],
        output_schema: dict[str, Any],
        temperature: float = 0.1,
    ) -> dict[str, Any]:
        """Generate a structured (JSON) response from the LLM.

        Args:
            messages: Conversation messages.
            output_schema: JSON schema for the expected output.
            temperature: Sampling temperature.

        Returns:
            Parsed structured output as a dictionary.

        Raises:
            LLMProviderError: If generation or parsing fails.
        """
        ...

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Generate an embedding vector for the given text.

        Args:
            text: Text to embed.

        Returns:
            List of floats representing the embedding vector.

        Raises:
            LLMProviderError: If embedding fails.
        """
        ...

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts.

        Args:
            texts: List of texts to embed.

        Returns:
            List of embedding vectors.

        Raises:
            LLMProviderError: If batch embedding fails.
        """
        ...


from regulaforge.common.exceptions import LLMProviderError  # noqa: F401 - re-exported for backward compatibility
