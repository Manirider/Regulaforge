from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from regulaforge.ingestion.domain.models import RegulatoryDocument

logger = logging.getLogger(__name__)


class MetadataExtractor:
    def extract_from_path(self, file_path: str) -> dict[str, Any]:
        meta: dict[str, Any] = {
            "file_name": Path(file_path).name,
            "file_extension": Path(file_path).suffix,
            "file_size_bytes": os.path.getsize(file_path),
            "modified_at": datetime.fromtimestamp(os.path.getmtime(file_path)).isoformat(),
        }
        if file_path.lower().endswith(".pdf"):
            pdf_meta = self._extract_pdf_metadata(file_path)
            meta.update(pdf_meta)
        return meta

    def _extract_pdf_metadata(self, file_path: str) -> dict[str, Any]:
        meta: dict[str, Any] = {}
        try:
            import PyPDF2
            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                info = reader.metadata
                if info:
                    for key in info:
                        clean_key = key.strip("/") if isinstance(key, str) else key
                        meta[str(clean_key)] = str(info[key])
                meta["num_pages"] = len(reader.pages)
                meta["pdf_version"] = reader.pdf_header if hasattr(reader, "pdf_header") else None
        except ImportError:
            logger.debug("PyPDF2 not available, skipping PDF metadata extraction")
        except Exception as exc:
            logger.warning("Failed to extract PDF metadata from %s: %s", file_path, exc)
        return meta

    def build_document_metadata(
        self,
        doc: RegulatoryDocument,
        file_path: str,
        text: str | None = None,
    ) -> dict[str, Any]:
        meta = self.extract_from_path(file_path)
        meta["source_type"] = doc.source_type.value
        meta["external_id"] = doc.external_id
        meta["title"] = doc.title
        meta["category"] = doc.category.value
        meta["published_date"] = doc.published_date.isoformat()
        if doc.effective_date:
            meta["effective_date"] = doc.effective_date.isoformat()
        if text:
            meta["text_length"] = len(text)
            meta["word_count"] = len(text.split())
        meta["document_url"] = doc.url
        return meta

    def save_metadata(self, meta: dict[str, Any], target_path: Path) -> None:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
        logger.debug("Metadata saved to %s", target_path)

    def load_metadata(self, meta_path: Path) -> dict[str, Any] | None:
        if not meta_path.exists():
            return None
        return json.loads(meta_path.read_text(encoding="utf-8"))
