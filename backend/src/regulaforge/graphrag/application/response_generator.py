from __future__ import annotations

import logging
import re
from typing import Any, Optional

from regulaforge.graphrag.domain.models import (
    Citation,
    RetrievedContext,
    SourceAttribution,
)

logger = logging.getLogger(__name__)


class ResponseGenerator:
    def __init__(
        self,
        llm_client: Optional[Any] = None,
        model_name: str = "gpt-4o",
        max_tokens: int = 2048,
        temperature: float = 0.3,
    ) -> None:
        self.llm_client = llm_client
        self.model_name = model_name
        self.max_tokens = max_tokens
        self.temperature = temperature

    async def generate(
        self,
        query: str,
        context: RetrievedContext,
        system_prompt: Optional[str] = None,
    ) -> str:
        if self.llm_client:
            return await self._generate_with_llm(query, context, system_prompt)
        return self._generate_rule_based(query, context)

    async def _generate_with_llm(
        self,
        query: str,
        context: RetrievedContext,
        system_prompt: Optional[str] = None,
    ) -> str:
        context_text = self._format_context(context)
        citations_text = self._format_citations(context.citations)

        default_system = (
            "You are a regulatory compliance expert. Answer questions based on the provided context. "
            "Cite sources using [1], [2] etc. If the context does not contain enough information, "
            "say so. Be precise, cite specific clause numbers and regulation references."
        )

        messages = [
            {
                "role": "system",
                "content": system_prompt or default_system,
            },
            {
                "role": "user",
                "content": f"Context:\n{context_text}\n\n"
                f"Sources:\n{citations_text}\n\n"
                f"Question: {query}\n\n"
                f"Provide a detailed answer with inline citations.",
            },
        ]

        if self.llm_client is not None:
            try:
                response = await self.llm_client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                )
                return response.choices[0].message.content or ""
            except Exception as exc:
                logger.error("LLM generation failed: %s", exc)

        return self._generate_rule_based(query, context)

    def _generate_rule_based(
        self,
        query: str,
        context: RetrievedContext,
    ) -> str:
        parts: list[str] = []
        parts.append(f"Query: {query}\n")

        seen_sources: set[str] = set()
        for i, rr in enumerate(context.results[:5], 1):
            source = rr.result.source or "Unknown"
            text = rr.result.text[:500] if rr.result.text else "N/A"
            parts.append(f"[{i}] Source: {source}")
            parts.append(f"    {text}")
            seen_sources.add(source)

        if context.citations:
            parts.append("\nReferences:")
            for i, c in enumerate(context.citations, 1):
                parts.append(f"  [{i}] {c.document_title} (ID: {c.document_id})")

        return "\n\n".join(parts)

    def _format_context(self, context: RetrievedContext) -> str:
        lines = []
        for i, rr in enumerate(context.results, 1):
            header = rr.result.heading or f"Chunk {rr.result.chunk_id}"
            lines.append(f"[{i}] {header}")
            lines.append(f"    Source: {rr.result.source}")
            lines.append(f"    Relevance: {rr.rerank_score:.3f}")
            if rr.result.page_number:
                lines.append(f"    Page: {rr.result.page_number}")
            lines.append(f"    Text: {rr.result.text[:800]}")
            lines.append("")
        return "\n".join(lines)

    def _format_citations(self, citations: list[Citation]) -> str:
        lines = []
        for i, c in enumerate(citations, 1):
            pages = f", pp. {', '.join(str(p) for p in c.page_numbers)}" if c.page_numbers else ""
            lines.append(
                f"[{i}] {c.document_title}{pages}"
            )
            if c.url:
                lines.append(f"    URL: {c.url}")
            if c.excerpt:
                lines.append(f"    Excerpt: {c.excerpt[:200]}")
        return "\n".join(lines)

    def extract_claims(self, response: str) -> list[SourceAttribution]:
        claims: list[SourceAttribution] = []
        re.findall(r"\[(\d+)\]", response)

        # Split into sentences as claims
        sentences = re.split(r"(?<=[.!?])\s+", response)
        for sent in sentences:
            sent = sent.strip()
            if not sent:
                continue
            refs_in_sent = re.findall(r"\[(\d+)\]", sent)
            if refs_in_sent:
                claim_citations: list[Citation] = []
                for _ref in refs_in_sent:
                    pass
                claims.append(
                    SourceAttribution(
                        claim=sent,
                        citations=claim_citations,
                        confidence=0.9 if refs_in_sent else 0.5,
                        is_grounded=bool(refs_in_sent),
                    )
                )
        return claims
