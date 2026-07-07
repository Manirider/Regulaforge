"""Confidence scoring system for AI-generated compliance outputs.

Provides calibrated confidence scores based on evidence quality,
source grounding, and prediction consistency.
"""

from typing import Any, Optional


class ConfidenceScorer:
    """Calibrated confidence scoring for AI compliance assessments.

    Factors considered:
    - Evidence quality and completeness
    - Source grounding strength
    - Prediction consistency across multiple analyses
    - Ambiguity in regulatory text
    - Historical accuracy for similar assessments
    """

    # Weights for different confidence factors
    WEIGHT_EVIDENCE_QUALITY = 0.35
    WEIGHT_SOURCE_GROUNDING = 0.30
    WEIGHT_CONSISTENCY = 0.20
    WEIGHT_AMBIGUITY = 0.15

    def __init__(self) -> None:
        self._historical_accuracy: dict[str, float] = {}

    def calculate(
        self,
        evidence_quality: float,
        source_grounding: float,
        prediction_consistency: float = 1.0,
        text_ambiguity: float = 0.0,
        historical_accuracy: Optional[float] = None,
    ) -> dict[str, Any]:
        """Calculate overall confidence score.

        Args:
            evidence_quality: Quality of available evidence (0.0-1.0).
            source_grounding: How well-grounded in source text (0.0-1.0).
            prediction_consistency: Consistency across analyses (0.0-1.0).
            text_ambiguity: Ambiguity level in regulatory text (0.0-1.0).
            historical_accuracy: Historical accuracy for similar tasks.

        Returns:
            Confidence assessment with score and breakdown.
        """
        # Validate inputs
        self._validate_score("evidence_quality", evidence_quality)
        self._validate_score("source_grounding", source_grounding)
        self._validate_score("prediction_consistency", prediction_consistency)
        self._validate_score("text_ambiguity", text_ambiguity)

        # Weighted calculation
        weighted_score = (
            evidence_quality * self.WEIGHT_EVIDENCE_QUALITY
            + source_grounding * self.WEIGHT_SOURCE_GROUNDING
            + prediction_consistency * self.WEIGHT_CONSISTENCY
            - text_ambiguity * self.WEIGHT_AMBIGUITY
        )

        # Apply historical accuracy adjustment
        if historical_accuracy is not None:
            self._validate_score("historical_accuracy", historical_accuracy)
            weighted_score = weighted_score * 0.7 + historical_accuracy * 0.3

        # Clamp to [0, 1]
        final_score = max(0.0, min(1.0, weighted_score))

        # Determine confidence level
        level = self._get_confidence_level(final_score)

        return {
            "score": round(final_score, 4),
            "level": level,
            "components": {
                "evidence_quality": evidence_quality,
                "source_grounding": source_grounding,
                "prediction_consistency": prediction_consistency,
                "text_ambiguity": text_ambiguity,
                "historical_accuracy": historical_accuracy,
            },
            "weights": {
                "evidence_quality": self.WEIGHT_EVIDENCE_QUALITY,
                "source_grounding": self.WEIGHT_SOURCE_GROUNDING,
                "prediction_consistency": self.WEIGHT_CONSISTENCY,
                "text_ambiguity": self.WEIGHT_AMBIGUITY,
            },
        }

    @staticmethod
    def _validate_score(name: str, value: float) -> None:
        """Validate a score is in range."""
        if not 0.0 <= value <= 1.0:
            raise ValueError(f"{name} must be between 0.0 and 1.0, got {value}")

    @staticmethod
    def _get_confidence_level(score: float) -> str:
        """Map numerical score to confidence level."""
        if score >= 0.9:
            return "very_high"
        elif score >= 0.75:
            return "high"
        elif score >= 0.5:
            return "medium"
        elif score >= 0.25:
            return "low"
        return "very_low"

    def assess_evidence_quality(self, evidence: list[dict[str, Any]]) -> float:
        """Assess the quality of available evidence.

        Args:
            evidence: List of evidence artifacts.

        Returns:
            Quality score between 0.0 and 1.0.
        """
        if not evidence:
            return 0.0

        scores = []
        for item in evidence:
            ev_score = 0.0

            # Verified evidence scores higher
            if item.get("is_verified"):
                ev_score += 0.4

            # Official documents score higher
            doc_type = item.get("type", "")
            if doc_type in ("certificate", "audit_trail", "official_document"):
                ev_score += 0.3
            elif doc_type in ("report", "policy", "procedure"):
                ev_score += 0.2

            # Recency matters
            if item.get("date"):
                ev_score += 0.2

            # Source credibility
            if item.get("source") in ("regulatory_body", "external_auditor", "certified_professional"):
                ev_score += 0.1

            scores.append(min(ev_score, 1.0))

        return sum(scores) / len(scores)

    def assess_source_grounding(
        self, source_citations: list[str], response_citations: list[str]
    ) -> float:
        """Assess how well the response is grounded in source text.

        Args:
            source_citations: Citations present in the source text.
            response_citations: Citations used in the AI response.

        Returns:
            Grounding score between 0.0 and 1.0.
        """
        if not response_citations:
            return 0.5  # No citations = neutral

        if not source_citations:
            return 0.3  # No source citations available

        grounded = sum(
            1 for rc in response_citations
            if any(rc in sc or sc in rc for sc in source_citations)
        )
        return grounded / len(response_citations) if response_citations else 0.5

    def update_historical_accuracy(
        self, task_type: str, was_accurate: bool
    ) -> None:
        """Update historical accuracy for a task type.

        Args:
            task_type: The type of AI task.
            was_accurate: Whether the prediction was accurate.
        """
        key = task_type
        if key not in self._historical_accuracy:
            self._historical_accuracy[key] = 0.5  # Start at neutral

        # Exponential moving average
        alpha = 0.3
        current = self._historical_accuracy[key]
        self._historical_accuracy[key] = current * (1 - alpha) + (1.0 if was_accurate else 0.0) * alpha

    def get_historical_accuracy(self, task_type: str) -> Optional[float]:
        """Get historical accuracy for a task type."""
        return self._historical_accuracy.get(task_type)
