"""Hallucination detection and prevention system.

Implements multiple strategies to detect and prevent AI hallucinations
in regulatory compliance contexts where accuracy is critical.
"""

import re
from typing import Any, Optional

from regulaforge.config.logging import get_logger
from regulaforge.config.settings import settings

logger = get_logger(__name__)


class HallucinationDetector:
    """Multi-strategy hallucination detection for regulatory AI.

    Uses:
    1. Source grounding verification - checks claims against source text
    2. Numerical consistency - verifies numbers, dates, thresholds
    3. Citation validation - verifies cited articles/sections exist
    4. Self-consistency - checks for internal contradictions
    5. Confidence calibration - flags low-confidence assertions
    """

    # Pattern to detect numerical claims
    NUMERIC_PATTERN = re.compile(
        r"\b(\d+[.,]?\d*)\s*(%|percent|years|months|days|EUR|USD|GBP|euro|dollar)\b",
        re.IGNORECASE,
    )

    # Pattern to detect citation claims
    CITATION_PATTERN = re.compile(
        r"(?:Article|Section|Art\.|Sec\.|Regulation|Reg\.)\s*(\d+(?:[\.\-\d]*))",
        re.IGNORECASE,
    )

    # Phrases that indicate low confidence or uncertainty
    LOW_CONFIDENCE_PHRASES = {  # noqa: RUF012
        "may", "might", "could", "possibly", "perhaps",
        "it is unclear", "it is uncertain",
        "we cannot determine", "insufficient information",
    }

    # Phrases that might indicate hallucination
    HALLUCINATION_INDICATORS = {  # noqa: RUF012
        "according to our knowledge",
        "it is well known that",
        "as we all know",
        "commonly understood",
        "as a matter of fact",
        "studies show",
        "research indicates",
    }

    def __init__(self, source_text: Optional[str] = None) -> None:
        self._source_text = source_text
        self._source_citations: set[str] = set()
        self._source_numbers: list[tuple[str, str]] = []

        if source_text:
            self._extract_source_references()

    def _extract_source_references(self) -> None:
        """Extract all references from the source text for grounding."""
        if not self._source_text:
            return

        # Extract citations
        for match in self.CITATION_PATTERN.finditer(self._source_text):
            self._source_citations.add(match.group(0).strip())

        # Extract numeric claims
        for match in self.NUMERIC_PATTERN.finditer(self._source_text):
            self._source_numbers.append((match.group(1), match.group(2)))

        logger.debug(
            "Extracted %d citations and %d numeric references from source",
            len(self._source_citations),
            len(self._source_numbers),
        )

    async def analyze_response(
        self, response_text: str, ai_confidence: Optional[float] = None
    ) -> dict[str, Any]:
        """Analyze an AI response for potential hallucinations.

        Args:
            response_text: The AI-generated text to analyze.
            ai_confidence: Optional confidence score from the AI.

        Returns:
            Analysis result with hallucination risk assessment.
        """
        issues: list[dict[str, Any]] = []
        risk_score = 0.0

        # Check 1: Citation grounding
        citation_issues = self._check_citation_grounding(response_text)
        issues.extend(citation_issues)
        risk_score += len(citation_issues) * 0.2

        # Check 2: Numerical consistency
        numeric_issues = self._check_numerical_consistency(response_text)
        issues.extend(numeric_issues)
        risk_score += len(numeric_issues) * 0.3

        # Check 3: Hallucination indicator phrases
        indicator_issues = self._check_hallucination_indicators(response_text)
        issues.extend(indicator_issues)
        risk_score += len(indicator_issues) * 0.25

        # Check 4: Internal consistency
        consistency_issues = self._check_internal_consistency(response_text)
        issues.extend(consistency_issues)
        risk_score += len(consistency_issues) * 0.2

        # Check 5: Confidence assessment
        if ai_confidence is not None and ai_confidence < settings.ai.confidence_threshold:
            issues.append({
                "type": "low_confidence",
                "severity": "warning",
                "detail": f"AI confidence ({ai_confidence:.2f}) below threshold ({settings.ai.confidence_threshold})",
            })
            risk_score += 0.15

        # Determine overall verdict
        verdict = self._determine_verdict(risk_score, len(issues))

        result = {
            "risk_score": min(risk_score, 1.0),
            "verdict": verdict,
            "issues_found": len(issues),
            "issues": issues,
            "requires_review": verdict in ("high", "critical"),
            "confidence_threshold": settings.ai.confidence_threshold,
        }

        if issues:
            logger.warning(
                "Hallucination detection found %d issues (risk=%.2f, verdict=%s)",
                len(issues), risk_score, verdict,
            )

        return result

    def _check_citation_grounding(self, text: str) -> list[dict[str, Any]]:
        """Check if citations in the response exist in the source."""
        issues = []
        if not self._source_citations:
            return issues

        response_citations = {
            m.group(0).strip() for m in self.CITATION_PATTERN.finditer(text)
        }

        for citation in response_citations:
            # Check if the citation number appears in source
            citation_num = re.search(r"\d+", citation)
            if citation_num:
                num = citation_num.group()
                if not any(num in src_cit for src_cit in self._source_citations):
                    issues.append({
                        "type": "ungrounded_citation",
                        "severity": "high",
                        "detail": f"Citation '{citation}' not found in source text",
                        "citation": citation,
                    })

        return issues

    def _check_numerical_consistency(self, text: str) -> list[dict[str, Any]]:
        """Check if numerical claims match source data."""
        issues = []
        if not self._source_numbers:
            return issues

        response_numbers = self.NUMERIC_PATTERN.findall(text)

        for num, unit in response_numbers:
            # Check if this number appears in source
            matched = any(
                src_num == num and src_unit.lower() == unit.lower()
                for src_num, src_unit in self._source_numbers
            )
            if not matched:
                issues.append({
                    "type": "unverified_number",
                    "severity": "medium",
                    "detail": f"Numerical claim '{num} {unit}' not verified in source",
                    "value": f"{num} {unit}",
                })

        return issues

    def _check_hallucination_indicators(self, text: str) -> list[dict[str, Any]]:
        """Check for phrases that might indicate hallucination."""
        issues = []
        text_lower = text.lower()

        for phrase in self.HALLUCINATION_INDICATORS:
            if phrase in text_lower:
                issues.append({
                    "type": "hallucination_indicator",
                    "severity": "medium",
                    "detail": f"Phrase '{phrase}' may indicate unsupported claims",
                    "phrase": phrase,
                })

        return issues

    def _check_internal_consistency(self, text: str) -> list[dict[str, Any]]:
        """Check for internal contradictions in the response."""
        issues = []

        # Check for contradictory statements
        contradiction_patterns = [
            (r"fully compliant", r"non.compliant"),
            (r"all requirements.*met", r"gaps?.*(?:identified|found)"),
            (r"no (?:issues|problems)", r"however.*(?:issues|problems)"),
        ]

        for pos_pattern, neg_pattern in contradiction_patterns:
            has_pos = bool(re.search(pos_pattern, text, re.IGNORECASE))
            has_neg = bool(re.search(neg_pattern, text, re.IGNORECASE))

            if has_pos and has_neg:
                issues.append({
                    "type": "contradiction",
                    "severity": "high",
                    "detail": f"Contradictory statements: '{pos_pattern}' vs '{neg_pattern}'",
                })

        return issues

    def _determine_verdict(self, risk_score: float, issue_count: int) -> str:
        """Determine overall hallucination risk verdict."""
        if risk_score >= 0.8 or issue_count >= 5:
            return "critical"
        elif risk_score >= 0.5 or issue_count >= 3:
            return "high"
        elif risk_score >= 0.3 or issue_count >= 2:
            return "medium"
        elif risk_score >= 0.1:
            return "low"
        return "negligible"
