from __future__ import annotations

import asyncio
import logging

from regulaforge.document_intelligence.application.models import ConfidenceScore

logger = logging.getLogger(__name__)


class OCRService:
    def __init__(
        self,
        tesseract_cmd: str = "tesseract",
        langs: str = "eng",
        psm: int = 3,
        timeout: int = 120,
    ) -> None:
        self._tesseract_cmd = tesseract_cmd
        self._langs = langs
        self._psm = psm
        self._timeout = timeout

    async def process(self, images: list[str]) -> str:
        texts: list[str] = []
        for img_path in images:
            try:
                text = await self._ocr_image(img_path)
                texts.append(text)
            except Exception as exc:
                logger.warning("OCR failed for %s: %s", img_path, exc)
        return "\n\n".join(texts)

    async def process_single(self, image_path: str) -> tuple[str, ConfidenceScore]:
        text = await self._ocr_image(image_path)
        conf = ConfidenceScore(
            value=0.8 if text.strip() else 0.0,
            model="tesseract",
            metadata={"psm": self._psm, "lang": self._langs},
        )
        return text, conf

    async def _ocr_image(self, image_path: str) -> str:
        try:
            import pytesseract
            from PIL import Image
            img = Image.open(image_path)
            text: str = await asyncio.to_thread(
                pytesseract.image_to_string,
                img,
                lang=self._langs,
                config=f"--psm {self._psm} --oem 3",
            )
            return text.strip()
        except ImportError:
            logger.warning("pytesseract not installed, OCR unavailable")
            return ""
        except Exception as exc:
            logger.exception("Tesseract OCR failed: %s", exc)
            return ""

    async def is_scanned(self, pdf_path: str) -> bool:
        try:
            import fitz
            doc = fitz.open(pdf_path)
            if len(doc) == 0:
                return False
            page = doc[0]
            text = page.get_text().strip()
            doc.close()
            return len(text) < 50
        except ImportError:
            logger.warning("PyMuPDF not installed, assuming scanned")
            return True
        except Exception:
            return True
