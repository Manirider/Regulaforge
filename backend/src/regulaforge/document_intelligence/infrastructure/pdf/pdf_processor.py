from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


class PDFProcessor:
    async def extract_text(self, path: str) -> tuple[str, list[str]]:
        pages_images: list[str] = []
        extracted_text = ""

        if not os.path.exists(path):
            raise FileNotFoundError(f"PDF not found: {path}")

        extracted_text = await self._extract_with_pymupdf(path)
        if extracted_text.strip():
            return extracted_text, []

        extracted_text = await self._extract_with_pdfplumber(path)
        if extracted_text.strip():
            return extracted_text, []

        pages_images = await self._convert_to_images(path)
        return extracted_text, pages_images

    async def _extract_with_pymupdf(self, path: str) -> str:
        try:
            import fitz
            doc = fitz.open(path)
            texts: list[str] = []
            for page in doc:
                text = page.get_text().strip()
                if text:
                    texts.append(text)
            doc.close()
            result = "\n\n".join(texts)
            if result.strip():
                logger.info("PyMuPDF extracted %d chars from %s", len(result), path)
            return result
        except ImportError:
            logger.debug("PyMuPDF not available")
            return ""
        except Exception as exc:
            logger.warning("PyMuPDF extraction failed: %s", exc)
            return ""

    async def _extract_with_pdfplumber(self, path: str) -> str:
        try:
            import pdfplumber
            texts: list[str] = []
            with pdfplumber.open(path) as pdf:
                for page in pdf.pages:
                    text = page.extract_text() or ""
                    if text.strip():
                        texts.append(text)
            result = "\n\n".join(texts)
            if result.strip():
                logger.info("pdfplumber extracted %d chars from %s", len(result), path)
            return result
        except ImportError:
            logger.debug("pdfplumber not available")
            return ""
        except Exception as exc:
            logger.warning("pdfplumber extraction failed: %s", exc)
            return ""

    async def _convert_to_images(self, path: str) -> list[str]:
        images: list[str] = []
        try:
            import fitz
            doc = fitz.open(path)
            output_dir = os.path.join(os.path.dirname(path), f"_pages_{os.path.basename(path)}")
            os.makedirs(output_dir, exist_ok=True)

            for page_num in range(len(doc)):
                page = doc[page_num]
                pix = page.get_pixmap(dpi=200)
                img_path = os.path.join(output_dir, f"page_{page_num + 1:04d}.png")
                pix.save(img_path)
                images.append(img_path)

            doc.close()
            logger.info("Converted %d pages to images in %s", len(images), output_dir)
        except ImportError:
            logger.warning("PyMuPDF not available for page rasterization")
        except Exception as exc:
            logger.warning("Page-to-image conversion failed: %s", exc)
        return images

    async def get_page_count(self, path: str) -> int:
        try:
            import fitz
            doc = fitz.open(path)
            count = len(doc)
            doc.close()
            return count
        except ImportError:
            return 0
        except Exception:
            return 0

    async def extract_images(self, path: str) -> list[str]:
        return await self._convert_to_images(path)
