"""Grounding — links GraphRAG responses to source KG nodes with attribution and confidence.

Provides source attribution, citation generation, and confidence scoring
to ensure every GraphRAG response is traceable to its source knowledge graph nodes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from regulaforge.config.logging import get_logger

from .reranker import RankedDocument

logger = get_logger(__name__)


@dataclass
class SourceAttribution:
    """Attribution of a response fact to a knowledge graph source node."""

    node_id: str
    node_type: str
    title: str
    score: float
    evidence_text: str
    regulation_code: str = ""
    jurisdiction: str = ""
    source_url: str = ""


@dataclass
class Citation:
    """A formatted citation referencing a knowledge graph source."""

    citation_id: int
    node_id: str
    title: str
    node_type: str
    relevance_score: float
    evidence_snippet: str
    formatted: str = ""


@dataclass
class ConfidenceScore:
    """Confidence assessment for a GraphRAG response."""

    overall: float
    retrieval_quality: float
    relevance: float
    source_authority: float
    completeness: float
    explanation: str = ""


@dataclass
class GroundedResponse:
    """A fully grounded GraphRAG response with attribution and confidence."""

    query: str
    answer: str
    citations: list[Citation] = field(default_factory=list)
    source_attributions: list[SourceAttribution] = field(default_factory=list)
    confidence: Optional[ConfidenceScore] = None
    latency_ms: float = 0.0
    model_used: str = ""
    timestamp: str = ""


class GroundingService:
    """Links retrieved documents to their KG sources and generates attribution metadata.

    Provides citation formatting, confidence scoring, and provenance tracking
    for every GraphRAG response.
    """

    def __init__(self, kg_service: Any = None) -> None:
        self._kg_service = kg_service

    async def build_attributions(
        self,
        documents: list[RankedDocument],
        *,
        include_kg_metadata: bool = True,
    ) -> list[SourceAttribution]:
        """Build source attributions from ranked documents.

        Enriches each document with metadata from the knowledge graph
        (regulation code, jurisdiction, source URL) when available.
        """
        attributions: list[SourceAttribution] = []
        for doc in documents:
            metadata = doc.document.metadata
            extra: dict[str, Any] = {}
            if include_kg_metadata and self._kg_service and doc.document.node_id:
                try:
                    node_id = UUID(doc.document.node_id)
                    node = await self._kg_service.get_node_by_id(node_id)
                    if node:
                        extra = {
                            "regulation_code": node.properties.get("code", ""),
                            "jurisdiction": node.properties.get("jurisdiction", ""),
                            "source_url": node.properties.get("source_url", ""),
                            "issuing_body": node.properties.get("issuing_body", ""),
                        }
                except Exception as e:
                    logger.debug("Failed to enrich attribution for %s: %s", doc.document.node_id, str(e))

            attribution = SourceAttribution(
                node_id=doc.document.node_id,
                node_type=doc.document.node_type,
                title=doc.document.title,
                score=doc.rerank_score,
                evidence_text=doc.document.text[:500],
                regulation_code=extra.get("regulation_code", metadata.get("regulation_code", "")),
                jurisdiction=extra.get("jurisdiction", metadata.get("jurisdiction", "")),
                source_url=extra.get("source_url", metadata.get("source_url", "")),
            )
            attributions.append(attribution)
        return attributions

    def build_citations(
        self,
        attributions: list[SourceAttribution],
        *,
        max_citations: int = 10,
        format_style: str = "markdown",
    ) -> list[Citation]:
        """Generate formatted citations from source attributions.

        Args:
            attributions: Source attributions to cite.
            max_citations: Maximum citations to include.
            format_style: 'markdown', 'text', or 'json'.

        Returns:
            List of Citation objects with pre-formatted text.
        """
        citations: list[Citation] = []
        for i, attr in enumerate(attributions[:max_citations]):
            snippet = attr.evidence_text[:200].strip()
            if format_style == "markdown":
                formatted = (
                    f"**[{i + 1}] {attr.title}** "
                    f"(*{attr.node_type}*" +
                    (f", {attr.jurisdiction}" if attr.jurisdiction else "") +
                    ")  \n"
                    f"> {snippet}  \n"
                    f"`ID: {attr.node_id}` " +
                    (f"| Score: {attr.score:.3f}" if attr.score else "")
                )
            elif format_style == "text":
                formatted = (
                    f"[{i + 1}] {attr.title} ({attr.node_type})"
                    f"{f', {attr.jurisdiction}' if attr.jurisdiction else ''}: "
                    f"{snippet[:100]}..."
                )
            else:
                formatted = ""

            citation = Citation(
                citation_id=i + 1,
                node_id=attr.node_id,
                title=attr.title,
                node_type=attr.node_type,
                relevance_score=attr.score,
                evidence_snippet=snippet,
                formatted=formatted,
            )
            citations.append(citation)
        return citations

    def compute_confidence(
        self,
        attributions: list[SourceAttribution],
        reranked_docs: list[RankedDocument],
    ) -> ConfidenceScore:
        """Compute a confidence score for the response based on retrieval quality.

        Factors:
        - retrieval_quality: Average score and number of relevant documents.
        - relevance: Semantic closeness of results to the query.
        - source_authority: Quality of sources (jurisdiction, node type).
        - completeness: Coverage of the information need.
        """
        if not attributions:
            return ConfidenceScore(
                overall=0.0,
                retrieval_quality=0.0,
                relevance=0.0,
                source_authority=0.0,
                completeness=0.0,
                explanation="No source attributions available",
            )

        scores = [a.score for a in attributions]
        avg_score = sum(scores) / len(scores) if scores else 0.0
        max_score = max(scores) if scores else 0.0
        score_variance = sum((s - avg_score) ** 2 for s in scores) / len(scores) if scores else 0.0

        retrieval_quality = min(1.0, avg_score * 1.5)
        relevance = min(1.0, max_score * 1.2)
        high_value_types = {"REGULATION", "CLAUSE", "OBLIGATION"}
        authority_count = sum(
            1 for a in attributions if a.node_type in high_value_types
        )
        source_authority = min(1.0, authority_count / max(len(attributions), 1) * 1.2)
        completeness = min(1.0, 1.0 - (score_variance * 2))

        overall = (
            retrieval_quality * 0.35
            + relevance * 0.30
            + source_authority * 0.20
            + completeness * 0.15
        )
        overall = max(0.0, min(1.0, overall))

        explanation_parts = []
        if retrieval_quality > 0.7:
            explanation_parts.append("high retrieval quality")
        elif retrieval_quality > 0.4:
            explanation_parts.append("moderate retrieval quality")
        else:
            explanation_parts.append("low retrieval quality")
        if source_authority > 0.7:
            explanation_parts.append("authoritative sources")
        if completeness > 0.7:
            explanation_parts.append("good coverage")

        return ConfidenceScore(
            overall=round(overall, 3),
            retrieval_quality=round(retrieval_quality, 3),
            relevance=round(relevance, 3),
            source_authority=round(source_authority, 3),
            completeness=round(completeness, 3),
            explanation=", ".join(explanation_parts) if explanation_parts else "insufficient data",
        )

    def format_answer_with_citations(
        self,
        answer: str,
        citations: list[Citation],
    ) -> str:
        """Append formatted citations to an answer text."""
        if not citations:
            return answer
        citation_lines = "\n\n---\n**Sources:**\n"
        for c in citations:
            citation_lines += c.formatted + "\n\n"
        return answer + citation_lines
