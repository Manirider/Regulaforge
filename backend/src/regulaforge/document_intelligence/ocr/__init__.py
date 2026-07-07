"""
OCR engine abstractions and implementations.

Provides pluggable OCR backends (Tesseract, PaddleOCR) with a common
``OcrEngine`` interface.  Each engine returns structured results with
per-word bounding boxes and confidence scores.
"""

from regulaforge.document_intelligence.ocr.base import OcrEngine, OcrResult, OcrWord, OcrPageResult
from regulaforge.document_intelligence.ocr.tesseract_engine import TesseractEngine
from regulaforge.document_intelligence.ocr.paddle_engine import PaddleOcrEngine

__all__ = [
    "OcrEngine",
    "OcrResult",
    "OcrWord",
    "OcrPageResult",
    "TesseractEngine",
    "PaddleOcrEngine",
]
