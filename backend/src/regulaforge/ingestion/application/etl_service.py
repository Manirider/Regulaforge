from __future__ import annotations

import logging
from pathlib import Path
from uuid import UUID

from regulaforge.ingestion.application.fingerprint_service import (
    DeduplicationService,
    FingerprintCalculator,
)
from regulaforge.ingestion.domain.models import (
    CrawlJob,
    DocumentStatus,
    RegulatoryDocument,
)
from regulaforge.ingestion.domain.repository import (
    CrawlJobRepository,
    DocumentRepository,
    FingerprintRepository,
)

logger = logging.getLogger(__name__)


class ETLService:
    def __init__(
        self,
        doc_repo: DocumentRepository,
        fp_repo: FingerprintRepository,
        job_repo: CrawlJobRepository,
        fingerprint_calculator: FingerprintCalculator,
        dedup_service: DeduplicationService,
    ) -> None:
        self._doc_repo = doc_repo
        self._fp_repo = fp_repo
        self._job_repo = job_repo
        self._fp = fingerprint_calculator
        self._dedup = dedup_service

    async def extract(
        self,
        _doc: RegulatoryDocument,
        raw_pdf_path: str,
    ) -> bytes:
        with open(raw_pdf_path, "rb") as f:
            return f.read()

    async def transform(
        self,
        pdf_bytes: bytes,
        doc: RegulatoryDocument,
    ) -> str | None:
        try:
            import io

            import PyPDF2
        except ImportError:
            logger.warning("PyPDF2 not available, skipping text extraction")
            return None
        try:
            reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
            pages = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)
            return "\n".join(pages)
        except Exception as exc:
            logger.error("Failed to extract text from %s: %s", doc.external_id, exc)
            return None

    async def load(
        self,
        doc: RegulatoryDocument,
        text: str | None,
        job: CrawlJob,
        text_dir: Path,
    ) -> None:
        if text:
            content_hash = self._fp.compute_content_hash(text)
            existing_with_same_hash = await self._doc_repo.get_by_content_hash(content_hash)
            duplicate_doc_id: UUID | None = None

            for ed in existing_with_same_hash:
                if ed.source_type == doc.source_type:
                    duplicate_doc_id = ed.id
                    break

            if duplicate_doc_id is not None and duplicate_doc_id != doc.id:
                doc.mark_duplicate(duplicate_doc_id)
                job.documents_duplicate += 1
                logger.info("Duplicate doc %s (id: %s) based on content hash", doc.external_id, doc.id)
            else:
                fp = self._fp.create_fingerprint(doc, text)
                await self._fp_repo.save(fp)
                doc.mark_processed(content_hash, {"extracted_text_length": len(text)})

                text_path = text_dir / f"{doc.id}.txt"
                text_path.write_text(text, encoding="utf-8")
        else:
            doc.mark_processed("", {"extracted_text_length": 0})

        await self._doc_repo.save(doc)

    async def etl_pipeline(
        self,
        doc: RegulatoryDocument,
        _raw_dir: Path,
        text_dir: Path,
        job: CrawlJob,
    ) -> None:
        try:
            raw_path = Path(str(doc.download_path)) if doc.download_path else None
            if not raw_path or not raw_path.exists():
                doc.mark_failed()
                await self._doc_repo.save(doc)
                return

            pdf_bytes = await self.extract(doc, str(raw_path))
            text = await self.transform(pdf_bytes, doc)
            await self.load(doc, text, job, text_dir)

        except Exception:
            logger.exception("ETL failed for doc %s", doc.external_id)
            doc.mark_failed()
            await self._doc_repo.save(doc)
            job.documents_failed += 1
            raise

    async def run_batch_etl(
        self,
        docs: list[RegulatoryDocument],
        job: CrawlJob,
        raw_dir: Path,
        text_dir: Path,
    ) -> None:
        for doc in docs:
            if doc.status == DocumentStatus.DOWNLOADED:
                await self.etl_pipeline(doc, raw_dir, text_dir, job)
