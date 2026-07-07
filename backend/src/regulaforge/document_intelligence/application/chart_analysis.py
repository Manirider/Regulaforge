"""Chart and figure analysis engine for document images."""

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import uuid4

from regulaforge.document_intelligence.application.enums import ElementType
from regulaforge.document_intelligence.application.models import (
    ConfidenceScore,
    DocumentElement,
)

logger = logging.getLogger(__name__)

CHART_KEYWORDS = [
    "figure", "fig.", "chart", "graph", "diagram", "plot",
    "exhibit", "tableau", "illustration",
]


class ChartAnalysisEngine:
    """Analyzes charts and figures in document images.

    Uses image captioning (BLIP-2 / GIT) when available, falling back
    to OCR-based keyword and structural analysis for chart description.
    """

    def __init__(self, model_name: str = "Salesforce/blip-image-captioning-base") -> None:
        self._model_name = model_name
        self._captioner = None

    async def analyze(self, image_path: str, element: DocumentElement | None = None) -> DocumentElement:
        caption, chart_type, confidence = await self._caption_image(image_path)
        return DocumentElement(
            id=str(uuid4()),
            element_type=ElementType.FIGURE,
            text=caption or "",
            page=element.page if element else 0,
            confidence=ConfidenceScore(
                value=confidence,
                model="chart_analysis",
                metadata={
                    "chart_type": chart_type,
                    "image_path": image_path,
                    "has_caption": caption is not None,
                },
            ),
        )

    async def analyze_batch(self, image_paths: list[str]) -> list[DocumentElement]:
        results: list[DocumentElement] = []
        for path in image_paths:
            try:
                elem = await self.analyze(path)
                results.append(elem)
            except Exception as exc:
                logger.warning("Chart analysis failed for %s: %s", path, exc)
        return results

    async def _caption_image(self, image_path: str) -> tuple[str | None, str | None, float]:
        caption, confidence = await self._try_transformers_caption(image_path)
        if caption:
            chart_type = self._classify_chart_type(caption)
            return caption, chart_type, confidence

        caption, confidence = await self._try_ocr_based_analysis(image_path)
        if caption:
            return caption, None, confidence

        return None, None, 0.0

    async def _try_transformers_caption(self, image_path: str) -> tuple[str | None, float]:
        if self._captioner is None:
            self._captioner = self._load_captioner()
        if self._captioner is None:
            return None, 0.0

        try:
            from PIL import Image
            image = Image.open(image_path).convert("RGB")
            result = self._captioner(image)
            caption = result[0]["generated_text"] if isinstance(result, list) else str(result)
            return caption.strip()[:500], 0.85
        except Exception as exc:
            logger.debug("Image captioning failed: %s", exc)
            return None, 0.0

    def _load_captioner(self) -> Any | None:
        try:
            from transformers import pipeline
            pipe = pipeline("image-to-text", model=self._model_name)
            logger.info("Loaded caption model: %s", self._model_name)
            return pipe
        except ImportError:
            logger.debug("Transformers not available for chart captioning")
            return None
        except Exception as exc:
            logger.warning("Failed to load caption model: %s", exc)
            return None

    async def _try_ocr_based_analysis(self, image_path: str) -> tuple[str | None, float]:
        try:
            import pytesseract
            from PIL import Image
            image = Image.open(image_path).convert("RGB")
            ocr_text: str = pytesseract.image_to_string(image).strip().lower()
            if not ocr_text:
                return None, 0.0

            lines = [l.strip() for l in ocr_text.split("\n") if l.strip()]
            title = lines[0] if lines else ""
            matched_keywords = [kw for kw in CHART_KEYWORDS if kw in ocr_text]
            is_chart = bool(matched_keywords) or self._looks_like_chart(lines)

            if is_chart:
                summary = f"Chart/figure with {len(lines)} text elements"
                if title:
                    summary = f"Chart: {title[:200]}"
                confidence = 0.5 + min(len(matched_keywords) * 0.1, 0.3)
                return summary, round(min(confidence, 0.85), 2)

            return None, 0.0
        except ImportError:
            logger.debug("pytesseract not available for chart OCR analysis")
            return None, 0.0
        except Exception as exc:
            logger.debug("OCR chart analysis failed: %s", exc)
            return None, 0.0

    def _looks_like_chart(self, lines: list[str]) -> bool:
        import re
        num_count = sum(1 for l in lines if re.search(r"\d+", l))
        axis_count = sum(1 for l in lines if re.search(r"[xXyY]\s*[-–—:]|\baxis\b", l))
        percent_count = sum(1 for l in lines if "%" in l)
        return (num_count >= 3 and percent_count >= 1) or axis_count >= 2

    def _classify_chart_type(self, caption: str) -> str | None:
        caption_lower = caption.lower()
        if any(w in caption_lower for w in ["bar chart", "bar graph", "barplot"]):
            return "bar"
        if any(w in caption_lower for w in ["line chart", "line graph", "trend"]):
            return "line"
        if any(w in caption_lower for w in ["pie chart", "pie graph"]):
            return "pie"
        if any(w in caption_lower for w in ["scatter", "scatter plot", "scatterplot"]):
            return "scatter"
        if any(w in caption_lower for w in ["table", "grid"]):
            return "table"
        return "chart"
