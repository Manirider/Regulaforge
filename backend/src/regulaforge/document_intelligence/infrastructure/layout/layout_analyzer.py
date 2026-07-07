from __future__ import annotations

import logging
import re
from uuid import uuid4

from regulaforge.document_intelligence.application.enums import ElementType
from regulaforge.document_intelligence.application.models import (
    BoundingBox,
    ConfidenceScore,
    DocumentElement,
)

logger = logging.getLogger(__name__)


class LayoutAnalyzer:
    async def analyze(
        self,
        source_path: str,
        text: str,
    ) -> list[DocumentElement]:
        elements: list[DocumentElement] = []

        rule_elements = self._rule_based_analysis(text)
        elements.extend(rule_elements)

        if source_path.lower().endswith(".pdf"):
            pdf_elements = await self._extract_pdf_elements(source_path)
            elements.extend(pdf_elements)

        docling_elements = await self._analyze_with_docling(source_path)
        elements.extend(docling_elements)

        layoutlm_elements = await self._analyze_with_layoutlm(source_path)
        elements.extend(layoutlm_elements)

        elements = self._deduplicate_and_merge(elements)
        logger.info("Layout analysis: %d elements from %s", len(elements), source_path)
        return elements

    def _rule_based_analysis(self, text: str) -> list[DocumentElement]:
        elements: list[DocumentElement] = []
        lines = text.split("\n")
        char_offset = 0

        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped:
                char_offset += len(line) + 1
                continue

            elem_type = ElementType.PARAGRAPH
            confidence = 0.7

            if stripped.isupper() and len(stripped) > 5 and len(stripped) < 200:
                elem_type = ElementType.SECTION_HEADING if len(stripped) < 100 else ElementType.TITLE
                confidence = 0.75
            elif re.match(r"^(SECTION|ARTICLE|CLAUSE|CHAPTER|PART|SCHEDULE|ANNEXURE)\s", stripped, re.IGNORECASE):
                elem_type = ElementType.SECTION_HEADING
                confidence = 0.9
            elif re.match(r"^\d+[.\d]*\s", stripped):
                may_be_clause = re.match(r"^\d+[.\d]*\s+[A-Z]", stripped)
                if may_be_clause and len(stripped) < 150:
                    elem_type = ElementType.SECTION_HEADING
                    confidence = 0.7
            elif len(stripped) < 80 and re.match(r"^(Page|-\s*\d+\s*-)", stripped, re.IGNORECASE):
                elem_type = ElementType.PAGE_NUMBER
                confidence = 0.9
            elif re.match(r"^(Copyright|©|All rights reserved|Confidential)", stripped, re.IGNORECASE):
                elem_type = ElementType.FOOTER
                confidence = 0.85
            elif re.match(r"^[A-Z][A-Za-z\s]+:$", stripped) and len(stripped) < 100:
                elem_type = ElementType.SECTION_HEADING if len(stripped) < 80 else ElementType.PARAGRAPH
                confidence = 0.65

            element = DocumentElement(
                id=uuid4(),
                element_type=elem_type,
                text=stripped[:2000],
                page=0,
                bbox=None,
                confidence=ConfidenceScore(value=confidence, model="rule_based"),
                metadata={"line": i, "char_offset": char_offset},
            )
            elements.append(element)
            char_offset += len(line) + 1

        return elements

    async def _extract_pdf_elements(self, path: str) -> list[DocumentElement]:
        elements: list[DocumentElement] = []
        try:
            import fitz
            doc = fitz.open(path)
            for page_num in range(len(doc)):
                page = doc[page_num]
                blocks = page.get_text("dict")["blocks"]
                for block in blocks:
                    if block["type"] == 0:
                        for line in block.get("lines", []):
                            for span in line.get("spans", []):
                                text = span.get("text", "").strip()
                                if not text:
                                    continue
                                bbox = span.get("bbox", None)
                                elem_type = self._classify_span(span)
                                element = DocumentElement(
                                    id=uuid4(),
                                    element_type=elem_type,
                                    text=text[:2000],
                                    page=page_num,
                                    bbox=BoundingBox(
                                        page=page_num,
                                        left=bbox[0] if bbox else 0,
                                        top=bbox[1] if bbox else 0,
                                        width=(bbox[2] - bbox[0]) if bbox else 0,
                                        height=(bbox[3] - bbox[1]) if bbox else 0,
                                    ) if bbox else None,
                                    confidence=ConfidenceScore(
                                        value=min(0.9, span.get("size", 12) / 24 + 0.5),
                                        model="pymupdf_layout",
                                        metadata={"font": span.get("font", ""), "size": span.get("size", 0), "flags": span.get("flags", 0)},  # noqa: E501
                                    ),
                                )
                                elements.append(element)
            doc.close()
            logger.info("PyMuPDF layout: %d elements from %d pages", len(elements), len(doc))
        except ImportError:
            logger.debug("PyMuPDF not available for layout analysis")
        except Exception as exc:
            logger.warning("PyMuPDF layout analysis failed: %s", exc)
        return elements

    def _classify_span(self, span: dict) -> ElementType:  # type: ignore[type-arg]
        font = span.get("font", "").lower()
        size = span.get("size", 12)
        flags = span.get("flags", 0)
        text = span.get("text", "").strip()

        is_bold = bool(flags & 2) if hasattr(flags, "__int__") else False
        bool(flags & 1)
        is_mono = "courier" in font or "mono" in font

        if is_bold and size > 14:
            return ElementType.TITLE
        if is_bold and size > 11:
            return ElementType.SECTION_HEADING
        if size < 8:
            return ElementType.FOOTNOTE
        if is_mono and re.match(r"^\d", text):
            return ElementType.PAGE_NUMBER
        if re.match(r"^(Copyright|©|All rights|Confidential)", text, re.IGNORECASE):
            return ElementType.FOOTER
        return ElementType.PARAGRAPH

    async def _analyze_with_docling(self, path: str) -> list[DocumentElement]:
        elements: list[DocumentElement] = []
        try:
            from docling.document_converter import DocumentConverter
            converter = DocumentConverter()
            result = converter.convert(path)
            docling_doc = result.document

            for item, _level in docling_doc.iterate_items():
                try:
                    text = item.text if hasattr(item, "text") else str(item)
                    label = item.label.value if hasattr(item, "label") and hasattr(item.label, "value") else str(getattr(item, "label", "other"))  # noqa: E501
                    page = item.prov[0].page if hasattr(item, "prov") and item.prov else 0
                    bbox_data = item.prov[0].bbox if hasattr(item, "prov") and item.prov else None

                    elem_type = self._docling_label_to_type(label)
                    elements.append(
                        DocumentElement(
                            id=uuid4(),
                            element_type=elem_type,
                            text=str(text)[:2000],
                            page=page,
                            bbox=BoundingBox(
                                page=page,
                                left=bbox_data.l if bbox_data else 0,
                                top=bbox_data.t if bbox_data else 0,
                                width=(bbox_data.r - bbox_data.l) if bbox_data else 0,
                                height=(bbox_data.b - bbox_data.t) if bbox_data else 0,
                            ) if bbox_data else None,
                            confidence=ConfidenceScore(value=0.9, model="docling"),
                        )
                    )
                except Exception:
                    continue
            logger.info("Docling: %d elements from %s", len(elements), path)
        except ImportError:
            logger.debug("Docling not available")
        except Exception as exc:
            logger.warning("Docling analysis failed: %s", exc)
        return elements

    def _docling_label_to_type(self, label: str) -> ElementType:
        mapping = {
            "title": ElementType.TITLE,
            "heading": ElementType.SECTION_HEADING,
            "paragraph": ElementType.PARAGRAPH,
            "table": ElementType.TABLE,
            "figure": ElementType.FIGURE,
            "list": ElementType.LIST,
            "header": ElementType.HEADER,
            "footer": ElementType.FOOTER,
            "caption": ElementType.CAPTION,
            "footnote": ElementType.FOOTNOTE,
            "form": ElementType.FORM,
            "page_number": ElementType.PAGE_NUMBER,
        }
        return mapping.get(label.lower(), ElementType.OTHER)

    async def _analyze_with_layoutlm(self, path: str) -> list[DocumentElement]:
        elements: list[DocumentElement] = []
        try:
            import fitz
            import torch
            from PIL import Image
            from transformers import LayoutLMv3ForTokenClassification, LayoutLMv3Processor

            processor = LayoutLMv3Processor.from_pretrained("microsoft/layoutlmv3-base", apply_ocr=False)
            model = LayoutLMv3ForTokenClassification.from_pretrained("microsoft/layoutlmv3-base")

            doc = fitz.open(path)
            for page_num in range(min(len(doc), 5)):
                page = doc[page_num]
                pix = page.get_pixmap(dpi=150)
                img_path = f"/tmp/_layoutlm_page_{page_num}.png"
                pix.save(img_path)
                image = Image.open(img_path).convert("RGB")

                words = []
                boxes = []
                blocks = page.get_text("dict")["blocks"]
                for block in blocks:
                    if block["type"] == 0:
                        for line in block.get("lines", []):
                            for span in line.get("spans", []):
                                text = span.get("text", "").strip()
                                if text and len(text) > 1:
                                    bbox = span.get("bbox", [0, 0, 0, 0])
                                    words.append(text)
                                    boxes.append([int(b) for b in bbox])

                if not words:
                    continue

                encoding = processor(
                    image,
                    text=words,
                    boxes=boxes,
                    return_tensors="pt",
                    truncation=True,
                    max_length=512,
                )

                with torch.no_grad():
                    outputs = model(**encoding)
                    predictions = outputs.logits.argmax(-1).squeeze().tolist()

                if isinstance(predictions, int):
                    predictions = [predictions]

                current_words: list[str] = []
                for _wi, (word, pred) in enumerate(zip(words, predictions[:len(words)], strict=False)):
                    if pred != 0:
                        current_words.append(word)
                    else:
                        if current_words:
                            elem = DocumentElement(
                                id=uuid4(),
                                element_type=ElementType.OTHER,
                                text=" ".join(current_words)[:2000],
                                page=page_num,
                                confidence=ConfidenceScore(value=0.65, model="layoutlmv3"),
                            )
                            elements.append(elem)
                            current_words = []
                if current_words:
                    elements.append(
                        DocumentElement(
                            id=uuid4(),
                            element_type=ElementType.OTHER,
                            text=" ".join(current_words)[:2000],
                            page=page_num,
                            confidence=ConfidenceScore(value=0.65, model="layoutlmv3"),
                        )
                    )

            doc.close()
            logger.info("LayoutLMv3: %d elements from %s", len(elements), path)
        except ImportError:
            logger.debug("LayoutLMv3/transformers not available")
        except Exception as exc:
            logger.warning("LayoutLMv3 analysis failed: %s", exc)
        return elements

    def _deduplicate_and_merge(self, elements: list[DocumentElement]) -> list[DocumentElement]:
        if not elements:
            return elements
        seen_texts: set[tuple[str, int, str]] = set()
        deduplicated: list[DocumentElement] = []
        for elem in elements:
            key = (elem.text[:100].lower(), elem.page, elem.element_type.value)
            if key not in seen_texts:
                seen_texts.add(key)
                deduplicated.append(elem)
        return deduplicated
