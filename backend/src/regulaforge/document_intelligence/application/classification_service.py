from __future__ import annotations

import logging
from typing import Optional

from regulaforge.document_intelligence.application.enums import ClassificationLabel
from regulaforge.document_intelligence.application.models import (
    ClassificationResult,
    ConfidenceScore,
    SemanticMetadata,
)

logger = logging.getLogger(__name__)


class ClassificationService:
    KEYWORD_MAP: dict[str, ClassificationLabel] = {  # noqa: RUF012
        "circular": ClassificationLabel.CIRCULAR,
        "master direction": ClassificationLabel.MASTER_DIRECTION,
        "notification": ClassificationLabel.NOTIFICATION,
        "guideline": ClassificationLabel.GUIDELINE,
        "guidelines": ClassificationLabel.GUIDELINE,
        "press release": ClassificationLabel.PRESS_RELEASE,
        "pressrelease": ClassificationLabel.PRESS_RELEASE,
        "annual report": ClassificationLabel.REPORT,
        "report": ClassificationLabel.REPORT,
        "amendment": ClassificationLabel.AMENDMENT,
        "amend": ClassificationLabel.AMENDMENT,
        "act": ClassificationLabel.LEGISLATION,
        "legislation": ClassificationLabel.LEGISLATION,
        "policy": ClassificationLabel.POLICY,
        "standard": ClassificationLabel.STANDARD,
        "contract": ClassificationLabel.CONTRACT,
        "form": ClassificationLabel.FORM,
    }

    def __init__(self, model_path: Optional[str] = None) -> None:
        self._model_path = model_path

    async def classify(
        self,
        text: str,
        metadata: Optional[SemanticMetadata] = None,
    ) -> ClassificationResult:
        title = (metadata.title or "") if metadata else ""
        first_500 = text[:500].lower()
        title_lower = title.lower()
        full_text_lower = text.lower()

        scores: dict[str, float] = {}
        for keyword, label in self.KEYWORD_MAP.items():
            score = 0.0
            if keyword in title_lower:
                score += 0.4
            if keyword in first_500:
                score += 0.3
            count = full_text_lower.count(keyword)
            score += min(count * 0.05, 0.3)

            if score > 0:
                scores[label.value] = scores.get(label.value, 0.0) + score

        if not scores:
            scores[ClassificationLabel.OTHER.value] = 0.5
            scores[ClassificationLabel.CIRCULAR.value] = 0.3
            scores[ClassificationLabel.GUIDELINE.value] = 0.2

        total = sum(scores.values())
        probabilities = {k: v / total for k, v in scores.items()} if total > 0 else {ClassificationLabel.OTHER.value: 1.0}  # noqa: E501

        best_label_str = max(probabilities, key=lambda k: probabilities.get(k, 0.0))
        best_confidence = probabilities[best_label_str]
        best_label = ClassificationLabel(best_label_str)

        return ClassificationResult(
            label=best_label,
            confidence=ConfidenceScore(
                value=best_confidence,
                model="keyword_classifier",
                metadata={"num_candidates": len(probabilities)},
            ),
            probabilities=probabilities,
            metadata={"title": title, "method": "keyword_weighted"},
        )
