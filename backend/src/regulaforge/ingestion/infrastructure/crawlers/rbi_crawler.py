from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import aiohttp
from bs4 import BeautifulSoup

from regulaforge.ingestion.domain.models import (
    CrawlSourceConfig,
    DocumentCategory,
    RegulatoryDocument,
)
from regulaforge.ingestion.infrastructure.crawlers.base_crawler import (
    BaseCrawler,
    DiscoveredDocument,
    RetryExhausted,
)

logger = __import__("logging").getLogger(__name__)

RBI_BASE = "https://www.rbi.org.in"
RBI_CIRCULARS_URL = "https://www.rbi.org.in/Scripts/BS_CircularIndexDisplay.aspx"


class RBICrawler(BaseCrawler):

    async def discover_documents(
        self,
        config: CrawlSourceConfig,
        _since: datetime | None = None,
    ) -> list[DiscoveredDocument]:
        documents: list[DiscoveredDocument] = []
        seen_ids: set = set()

        async with aiohttp.ClientSession() as session:
            try:
                resp = await self._fetch_with_retry(session, RBI_CIRCULARS_URL, config)
                html = await resp.text()
                soup = BeautifulSoup(html, "html.parser")
                table = soup.find("table", {"class": "table table-striped"})
                if not table:
                    table = soup.find("table")
                rows = table.find_all("tr") if table else []

                for row in rows[1:]:
                    cols = row.find_all("td")
                    if len(cols) < 2:
                        continue
                    link_tag = row.find("a")
                    if not link_tag or not link_tag.get("href"):
                        continue
                    href = link_tag["href"]
                    title = link_tag.get_text(strip=True)
                    if not title:
                        continue

                    external_id_match = re.search(r"Id=([^&\s]+)", href)
                    external_id = external_id_match.group(1) if external_id_match else hashlib.md5(title.encode()).hexdigest()[:12]  # noqa: E501
                    if external_id in seen_ids:
                        continue
                    seen_ids.add(external_id)

                    full_url = urljoin(RBI_BASE, href)
                    date_text = cols[0].get_text(strip=True) if len(cols) > 0 else ""
                    published_date = self._parse_date(date_text, ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%B %d, %Y"]) or datetime.now(timezone.utc)  # noqa: E501

                    category = self._categorize(title)

                    doc = DiscoveredDocument(
                        external_id=external_id,
                        title=title,
                        url=full_url,
                        category=category,
                        published_date=published_date,
                    )
                    documents.append(doc)

            except RetryExhausted as exc:
                logger.error("RBI discovery failed: %s", exc)
                raise

        logger.info("RBI discovery found %d documents", len(documents))
        return documents

    async def download_document(
        self,
        doc: RegulatoryDocument,
        config: CrawlSourceConfig,
        download_dir: Path,
    ) -> tuple[Path, int, str]:
        pdf_url = doc.url
        file_name = f"{doc.external_id}.pdf"
        target_path = download_dir / file_name

        async with aiohttp.ClientSession() as session:
            try:
                file_size, sha256 = await self._download_file_with_retry(session, pdf_url, target_path, config)
                return target_path, file_size, sha256
            except RetryExhausted:
                raise

    def _categorize(self, title: str) -> DocumentCategory:
        t = title.lower()
        if "amendment" in t or "amend" in t:
            return DocumentCategory.AMENDMENT
        if "master direction" in t:
            return DocumentCategory.MASTER_DIRECTION
        if "circular" in t:
            return DocumentCategory.CIRCULAR
        if "notification" in t:
            return DocumentCategory.NOTIFICATION
        if "guideline" in t or "guidance" in t:
            return DocumentCategory.GUIDELINE
        if "press release" in t:
            return DocumentCategory.PRESS_RELEASE
        if "report" in t:
            return DocumentCategory.REPORT
        return DocumentCategory.OTHER


