from __future__ import annotations

import logging
from typing import Optional

from regulaforge.document_intelligence.domain.models import (
    ClassificationLabel,
    ClassificationResult,
    ConfidenceScore,
)

logger = logging.getLogger(__name__)


class TransformersClassifierAdapter:
    def __init__(
        self,
        model_name: str = "nlpaueb/legal-bert-base-uncased",
        labels: Optional[list[str]] = None,
        device: str = "cpu",
    ) -> None:
        self._model_name = model_name
        self._labels = labels or [l.value for _l in ClassificationLabel]  # noqa: F821
        self._device = device
        self._pipeline = None

    async def load(self) -> None:
        try:
            from transformers import pipeline
            self._pipeline = pipeline(
                "text-classification",
                model=self._model_name,
                device=self._device,
                return_all_scores=True,
            )
            logger.info("Classifier model loaded: %s", self._model_name)
        except ImportError:
            logger.warning("Transformers not available for classification")
        except Exception as exc:
            logger.warning("Failed to load classifier: %s", exc)

    async def classify(self, text: str) -> Optional[ClassificationResult]:
        if self._pipeline is None:
            await self.load()
        if self._pipeline is None:
            return None

        try:
            truncated = text[:512]
            results = self._pipeline(truncated)
            if not results:
                return None

            probs: dict[str, float] = {}
            for r in results[0]:
                label = r.get("label", "OTHER").lower()
                score = r.get("score", 0.0)
                try:
                    mapped = self._map_label(label)
                    probs[mapped.value] = max(probs.get(mapped.value, 0.0), score)
                except ValueError:
                    probs[label] = score

            if not probs:
                return None

            best_label_str = max(probs, key=probs.get)
            best_confidence = probs[best_label_str]
            total = sum(probs.values())
            probabilities = {k: v / total for k, v in probs.items()} if total > 0 else probs

            return ClassificationResult(
                label=ClassificationLabel(best_label_str),
                confidence=ConfidenceScore(
                    value=best_confidence,
                    model=self._model_name,
                ),
                probabilities=probabilities,
                metadata={"model": self._model_name},
            )
        except Exception as exc:
            logger.warning("Classification failed: %s", exc)
            return None

    def _map_label(self, label: str) -> ClassificationLabel:
        mapping = {
            "CIRCULAR": ClassificationLabel.CIRCULAR,
            "MASTER_DIRECTION": ClassificationLabel.MASTER_DIRECTION,
            "NOTIFICATION": ClassificationLabel.NOTIFICATION,
            "GUIDELINE": ClassificationLabel.GUIDELINE,
            "PRESS_RELEASE": ClassificationLabel.PRESS_RELEASE,
            "REPORT": ClassificationLabel.REPORT,
            "AMENDMENT": ClassificationLabel.AMENDMENT,
            "LEGISLATION": ClassificationLabel.LEGISLATION,
            "POLICY": ClassificationLabel.POLICY,
            "STANDARD": ClassificationLabel.STANDARD,
            "CONTRACT": ClassificationLabel.CONTRACT,
            "FORM": ClassificationLabel.FORM,
        }
        ul = label.upper().replace(" ", "_")
        return mapping.get(ul, ClassificationLabel.OTHER)
