from __future__ import annotations

import logging
import re
from typing import Any, Optional

from regulaforge.graphrag.domain.models import (
    Citation,
    GroundednessReport,
    GroundednessScore,
    RetrievedContext,
    SourceAttribution,
)

logger = logging.getLogger(__name__)


class GroundednessChecker:
    def __init__(
        self,
        llm_client: Optional[Any] = None,
    ) -> None:
        self.llm_client = llm_client

    async def check(
        self,
        response: str,
        context: RetrievedContext,
    ) -> GroundednessReport:
        claims = self._extract_claims(response)
        context_text = "\n".join(r.result.text for r in context.results)

        source_attributions: list[SourceAttribution] = []
        total_precision = 0.0
        ungrounded: list[str] = []
        missing: list[str] = []

        for claim in claims:
            attribution = await self._verify_claim(claim, context_text, context.citations)
            source_attributions.append(attribution)
            if attribution.is_grounded:
                total_precision += attribution.confidence
            else:
                ungrounded.append(claim)

        total_claims = len(claims)
        if total_claims > 0:
            precision = total_precision / total_claims
            recall = len([c for c in source_attributions if c.is_grounded]) / total_claims
        else:
            precision = 1.0
            recall = 1.0

        score = GroundednessScore(
            overall=(precision + recall) / 2,
            precision=precision,
            recall=recall,
            faithfulness=precision,
            citation_accuracy=self._check_citation_accuracy(response, context),
        )

        logger.info(
            "Groundedness: overall=%.3f, precision=%.3f, recall=%.3f, claims=%d",
            score.overall,
            score.precision,
            score.recall,
            total_claims,
        )

        return GroundednessReport(
            response=response,
            claims=source_attributions,
            score=score,
            ungrounded_claims=ungrounded,
            missing_citations=missing,
        )

    def _extract_claims(self, response: str) -> list[str]:
        sentences = re.split(r"(?<=[.!?])\s+", response)
        return [s.strip() for s in sentences if len(s.strip()) > 20]

    async def _verify_claim(
        self,
        claim: str,
        context_text: str,
        citations: list[Citation],
    ) -> SourceAttribution:
        if self.llm_client:
            return await self._verify_with_llm(claim, context_text, citations)

        return self._verify_rule_based(claim, context_text, citations)

    async def _verify_with_llm(
        self,
        claim: str,
        context_text: str,
        citations: list[Citation],
    ) -> SourceAttribution:
        if self.llm_client is not None:
            try:
                import json

                response = await self.llm_client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are a fact-checker. Determine if the given claim is supported by the context. "
                                "Return JSON: {\"grounded\": bool, \"confidence\": float, \"supporting_text\": str|null}"  # noqa: E501
                            ),
                        },
                        {
                            "role": "user",
                            "content": f"Context:\n{context_text[:4000]}\n\nClaim: {claim}\n\nIs this claim grounded in the context?",  # noqa: E501
                        },
                    ],
                    response_format={"type": "json_object"},
                    max_tokens=256,
                )
                result = json.loads(response.choices[0].message.content or "{}")
                return SourceAttribution(
                    claim=claim,
                    citations=citations[:3],
                    confidence=result.get("confidence", 0.5),
                    is_grounded=result.get("grounded", False),
                    supporting_text=result.get("supporting_text"),
                )
            except Exception as exc:
                logger.warning("LLM verification failed: %s", exc)

        return self._verify_rule_based(claim, context_text, citations)

    def _verify_rule_based(
        self,
        claim: str,
        context_text: str,
        citations: list[Citation],
    ) -> SourceAttribution:
        claim_lower = claim.lower()
        context_lower = context_text.lower()

        key_terms = [w for w in claim_lower.split() if len(w) > 4]
        matches = sum(1 for t in key_terms if t in context_lower)
        confidence = matches / len(key_terms) if key_terms else 0.0

        is_grounded = confidence > 0.3
        supporting = None
        if is_grounded:
            supporting = self._find_supporting_text(claim_lower, context_text)

        return SourceAttribution(
            claim=claim,
            citations=citations[:2] if is_grounded else [],
            confidence=confidence,
            is_grounded=is_grounded,
            supporting_text=supporting,
        )

    def _find_supporting_text(
        self, claim_lower: str, context_text: str
    ) -> Optional[str]:
        key_terms = [w for w in claim_lower.split() if len(w) > 4]
        for paragraph in context_text.split("\n"):
            para_lower = paragraph.lower()
            match_count = sum(1 for t in key_terms if t in para_lower)
            if match_count >= len(key_terms) * 0.5:
                return paragraph[:500]
        return None

    def _check_citation_accuracy(
        self, response: str, context: RetrievedContext
    ) -> float:
        citation_refs = re.findall(r"\[(\d+)\]", response)
        if not citation_refs:
            return 0.0

        max_ref = max(int(r) for r in citation_refs)
        if max_ref <= len(context.citations):
            return 1.0
        return len([r for r in citation_refs if int(r) <= len(context.citations)]) / len(citation_refs)
