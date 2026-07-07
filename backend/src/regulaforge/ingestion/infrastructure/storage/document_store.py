from __future__ import annotations

import logging
import shutil
from pathlib import Path

from regulaforge.ingestion.domain.models import CrawlSourceType

logger = logging.getLogger(__name__)


class DocumentStore:
    def __init__(self, base_dir: Path) -> None:
        self._base_dir = base_dir
        self._raw_dir = base_dir / "raw"
        self._text_dir = base_dir / "text"
        self._meta_dir = base_dir / "metadata"
        self._version_dir = base_dir / "versions"
        self._raw_dir.mkdir(parents=True, exist_ok=True)
        self._text_dir.mkdir(parents=True, exist_ok=True)
        self._meta_dir.mkdir(parents=True, exist_ok=True)
        self._version_dir.mkdir(parents=True, exist_ok=True)

    @property
    def raw_dir(self) -> Path:
        return self._raw_dir

    @property
    def text_dir(self) -> Path:
        return self._text_dir

    def source_raw_dir(self, source: CrawlSourceType) -> Path:
        p = self._raw_dir / source.value
        p.mkdir(parents=True, exist_ok=True)
        return p

    def source_text_dir(self, source: CrawlSourceType) -> Path:
        p = self._text_dir / source.value
        p.mkdir(parents=True, exist_ok=True)
        return p

    def source_meta_dir(self, source: CrawlSourceType) -> Path:
        p = self._meta_dir / source.value
        p.mkdir(parents=True, exist_ok=True)
        return p

    def source_version_dir(self, source: CrawlSourceType) -> Path:
        p = self._version_dir / source.value
        p.mkdir(parents=True, exist_ok=True)
        return p

    def store_raw_pdf(self, source: CrawlSourceType, doc_id: str, content: bytes) -> Path:
        target = self.source_raw_dir(source) / f"{doc_id}.pdf"
        target.write_bytes(content)
        logger.debug("Stored raw PDF: %s", target)
        return target

    def store_text(self, source: CrawlSourceType, doc_id: str, text: str) -> Path:
        target = self.source_text_dir(source) / f"{doc_id}.txt"
        target.write_text(text, encoding="utf-8")
        return target

    def store_metadata(self, source: CrawlSourceType, doc_id: str, meta: dict) -> Path:
        import json
        target = self.source_meta_dir(source) / f"{doc_id}.json"
        target.write_text(json.dumps(meta, indent=2, default=str), encoding="utf-8")
        return target

    def store_version(self, source: CrawlSourceType, doc_id: str, version: int, content: bytes) -> Path:
        ver_dir = self.source_version_dir(source) / doc_id
        ver_dir.mkdir(parents=True, exist_ok=True)
        target = ver_dir / f"v{version}.pdf"
        target.write_bytes(content)
        return target

    def get_raw_path(self, source: CrawlSourceType, doc_id: str) -> Path | None:
        p = self.source_raw_dir(source) / f"{doc_id}.pdf"
        return p if p.exists() else None

    def get_text_path(self, source: CrawlSourceType, doc_id: str) -> Path | None:
        p = self.source_text_dir(source) / f"{doc_id}.txt"
        return p if p.exists() else None

    def get_metadata_path(self, source: CrawlSourceType, doc_id: str) -> Path | None:
        p = self.source_meta_dir(source) / f"{doc_id}.json"
        return p if p.exists() else None

    def list_raw(self, source: CrawlSourceType) -> list[Path]:
        return list(self.source_raw_dir(source).glob("*.pdf"))

    def archive_old_version(self, source: CrawlSourceType, doc_id: str, version: int) -> None:
        raw = self.get_raw_path(source, doc_id)
        if raw and raw.exists():
            ver_dir = self.source_version_dir(source) / doc_id
            ver_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(raw), str(ver_dir / f"v{version}.pdf"))
            logger.info("Archived version %d for doc %s", version, doc_id)

    def total_size_bytes(self) -> int:
        total = 0
        for p in self._raw_dir.rglob("*"):
            if p.is_file():
                total += p.stat().st_size
        return total

    def file_count(self) -> int:
        return sum(1 for _ in self._raw_dir.rglob("*") if _.is_file())
