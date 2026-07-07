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

IRDAI_BASE = "https://www.irdai.gov.in"
IRDAI_LIST_URL = "https://www.irdai.gov.in/ADMINCMS/cms/WhatNews_Lists.aspx"


class IRDAICrawler(BaseCrawler):

    async def discover_documents(
        self,
        config: CrawlSourceConfig,
        _since: datetime | None = None,
    ) -> list[DiscoveredDocument]:
        documents: list[DiscoveredDocument] = []
        seen_ids: set = set()

        async with aiohttp.ClientSession() as session:
            try:
                resp = await self._fetch_with_retry(session, IRDAI_LIST_URL, config)
                html = await resp.text()
                soup = BeautifulSoup(html, "html.parser")

                items = soup.select("table tr, .list-item, .news-item, .circular-item")
                if not items:
                    items = soup.find_all("div", {"class": re.compile(r"item|news|list")})

                if not items:
                    links = soup.find_all("a", href=re.compile(r"\.pdf|AdminCMS|cms", re.I))
                    for link in links:
                        href = link.get("href", "")
                        title = link.get_text(strip=True) or Path(href).stem.replace("_", " ")
                        full_url = urljoin(IRDAI_BASE, href)
                        external_id = hashlib.md5(href.encode()).hexdigest()[:12]
                        if external_id in seen_ids:
                            continue
                        seen_ids.add(external_id)
                        doc = DiscoveredDocument(
                            external_id=external_id,
                            title=title,
                            url=full_url,
                            category=DocumentCategory.CIRCULAR,
                            published_date=datetime.now(timezone.utc),
                        )
                        documents.append(doc)
                    return documents

                for item in items:
                    link = item.find("a") if hasattr(item, "find") else None
                    href = link.get("href") if link else None
                    if not href:
                        continue
                    title = link.get_text(strip=True) if link else ""
                    if not title:
                        continue

                    full_url = urljoin(IRDAI_BASE, href)
                    external_id = hashlib.md5(href.encode()).hexdigest()[:12]
                    if external_id in seen_ids:
                        continue
                    seen_ids.add(external_id)

                    date_text = ""
                    spans = item.find_all("span") if hasattr(item, "find_all") else []
                    for sp in spans:
                        txt = sp.get_text(strip=True)
                        if re.search(r"\d{2}[/-]\d{2}[/-]\d{4}", txt):
                            date_text = txt
                            break
                    if not date_text:
                        match = re.search(r"(\d{2}[/-]\d{2}[/-]\d{4})", item.get_text())
                        date_text = match.group(1) if match else ""

                    published_date = self._parse_date(date_text, ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"]) or datetime.now(timezone.utc)  # noqa: E501
                    category = self._categorize(title)

                    discovered = DiscoveredDocument(
                        external_id=external_id,
                        title=title,
                        url=full_url,
                        category=category,
                        published_date=published_date,
                    )
                    documents.append(discovered)

            except RetryExhausted as exc:
                logger.error("IRDAI discovery failed: %s", exc)
                raise

        logger.info("IRDAI discovery found %d documents", len(documents))
        return documents

    async def download_document(
        self,
        doc: RegulatoryDocument,
        config: CrawlSourceConfig,
        download_dir: Path,
    ) -> tuple[Path, int, str]:
        file_name = f"{doc.external_id}.pdf"
        target_path = download_dir / file_name

        async with aiohttp.ClientSession() as session:
            try:
                file_size, sha256 = await self._download_file_with_retry(session, doc.url, target_path, config)
                return target_path, file_size, sha256
            except RetryExhausted:
                raise

    def _categorize(self, title: str) -> DocumentCategory:
        t = title.lower()
        if "circular" in t:
            return DocumentCategory.CIRCULAR
        if "guideline" in t:
            return DocumentCategory.GUIDELINE
        if "notification" in t:
            return DocumentCategory.NOTIFICATION
        if "press release" in t:
            return DocumentCategory.PRESS_RELEASE
        if "report" in t:
            return DocumentCategory.REPORT
        if "amendment" in t or "amend" in t:
            return DocumentCategory.AMENDMENT
        return DocumentCategory.OTHER
