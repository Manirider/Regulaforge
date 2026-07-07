"""OpenAI LLM provider implementation.

Implements the LLMProvider port interface using OpenAI's API.
Supports GPT-4, GPT-4 Turbo, and text-embedding-3 models.
"""

import time
from typing import Any, Optional

from openai import AsyncOpenAI

from regulaforge.application.ports.llm_provider import (
    LLMMessage,
    LLMProvider,
    LLMProviderError,
    LLMResponse,
)
from regulaforge.config.logging import get_logger
from regulaforge.config.settings import settings

logger = get_logger(__name__)


class OpenAIProvider(LLMProvider):
    """OpenAI-based LLM provider for RegulaForge AI features.

    Provides text generation, structured output, and embeddings
    using OpenAI's API with proper error handling, retries,
    and token management.
    """

    def __init__(self) -> None:
        self._client: Optional[AsyncOpenAI] = None
        self._model = settings.ai.llm_model
        self._embedding_model = settings.ai.embedding_model
        self._max_retries = 3
        self._initialized = False

    async def _ensure_client(self) -> AsyncOpenAI:
        """Lazy-initialize the OpenAI client."""
        if not self._initialized:
            self._client = AsyncOpenAI(
                api_key=settings.security.secret_key,  # Will use OPENAI_API_KEY env var
                max_retries=self._max_retries,
            )
            self._initialized = True
            logger.info(
                "OpenAI provider initialized: model=%s, embedding=%s",
                self._model, self._embedding_model,
            )
        return self._client  # type: ignore

    async def generate(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        stop_sequences: Optional[list[str]] = None,
        response_format: Optional[dict[str, Any]] = None,
    ) -> LLMResponse:
        """Generate a response from OpenAI."""
        client = await self._ensure_client()
        start_time = time.monotonic()

        api_messages = [{"role": m.role, "content": m.content} for m in messages]

        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": api_messages,
            "temperature": temperature,
            "max_tokens": max_tokens or settings.ai.llm_max_tokens,
        }

        if stop_sequences:
            kwargs["stop"] = stop_sequences

        if response_format:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            response = await client.chat.completions.create(**kwargs)
            choice = response.choices[0]

            latency_ms = (time.monotonic() - start_time) * 1000

            result = LLMResponse(
                content=choice.message.content or "",
                model=response.model,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                    "total_tokens": response.usage.total_tokens if response.usage else 0,
                },
                finish_reason=choice.finish_reason or "stop",
                latency_ms=round(latency_ms, 2),
                raw_response=response.model_dump() if hasattr(response, "model_dump") else None,
            )

            logger.debug(
                "OpenAI generation: model=%s, tokens=%d, latency=%.1fms",
                response.model,
                result.usage["total_tokens"],
                latency_ms,
            )

            return result

        except Exception as e:
            logger.error("OpenAI generation failed: %s", e, exc_info=True)
            raise LLMProviderError(
                message=str(e),
                provider="openai",
                status_code=getattr(e, "status_code", None),
            )

    async def generate_structured(
        self,
        messages: list[LLMMessage],
        output_schema: dict[str, Any],
        temperature: float = 0.1,
    ) -> dict[str, Any]:
        """Generate structured JSON output from OpenAI."""
        import json

        # Add JSON schema instruction to system message
        schema_instruction = (
            "\n\nYou must respond with valid JSON conforming to this schema:\n"
            f"{json.dumps(output_schema, indent=2)}"
        )

        enhanced_messages = []
        for msg in messages:
            if msg.role == "system":
                enhanced_messages.append(LLMMessage(
                    role="system",
                    content=msg.content + schema_instruction,
                ))
            else:
                enhanced_messages.append(msg)

        response = await self.generate(
            messages=enhanced_messages,
            temperature=temperature,
            response_format={"type": "json_object"},
        )

        try:
            parsed = json.loads(response.content)
            return parsed
        except json.JSONDecodeError as e:
            logger.error("Failed to parse structured output: %s", e)
            raise LLMProviderError(
                message=f"Failed to parse structured JSON output: {e}",
                provider="openai",
            )

    async def embed(self, text: str) -> list[float]:
        """Generate an embedding vector."""
        client = await self._ensure_client()

        try:
            response = await client.embeddings.create(
                model=self._embedding_model,
                input=text,
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error("OpenAI embedding failed: %s", e, exc_info=True)
            raise LLMProviderError(
                message=str(e),
                provider="openai",
                status_code=getattr(e, "status_code", None),
            )

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts."""
        client = await self._ensure_client()

        try:
            response = await client.embeddings.create(
                model=self._embedding_model,
                input=texts,
            )
            # Sort by index to maintain order
            sorted_data = sorted(response.data, key=lambda x: x.index)
            return [item.embedding for item in sorted_data]
        except Exception as e:
            logger.error("OpenAI batch embedding failed: %s", e, exc_info=True)
            raise LLMProviderError(
                message=str(e),
                provider="openai",
                status_code=getattr(e, "status_code", None),
            )
