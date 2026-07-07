from __future__ import annotations

import logging
import re
from typing import Optional
from uuid import uuid4

from regulaforge.document_intelligence.application.enums import ElementType
from regulaforge.document_intelligence.application.models import (
    ConfidenceScore,
    DocumentElement,
    TableCell,
    TableElement,
)

logger = logging.getLogger(__name__)


class TableExtractionService:
    def __init__(self, method: str = "hybrid") -> None:
        self._method = method

    async def extract(
        self,
        source_path: str,
        elements: Optional[list[DocumentElement]] = None,
    ) -> list[TableElement]:
        tables: list[TableElement] = []

        if elements:
            table_elements = [e for e in elements if e.element_type == ElementType.TABLE]
            for te in table_elements:
                table = await self._parse_table_element(te)
                if table:
                    tables.append(table)

        text_tables = await self._extract_text_tables(source_path)
        tables.extend(text_tables)

        logger.info("Table extraction: %d tables found", len(tables))
        return tables

    async def _parse_table_element(self, element: DocumentElement) -> Optional[TableElement]:
        if not element.text.strip():
            return None
        lines = element.text.strip().split("\n")
        if len(lines) < 2:
            return None

        headers: list[str] = []
        rows: list[list[TableCell]] = []

        for i, line in enumerate(lines):
            cells = [c.strip() for c in re.split(r"\s{2,}|\t|\|", line) if c.strip()]
            if not cells:
                continue
            if i == 0:
                headers = cells
            row_cells = [
                TableCell(text=cell, row=i - 1, col=j, is_header=i == 0)
                for j, cell in enumerate(cells)
            ]
            rows.append(row_cells)

        return TableElement(
            id=uuid4(),
            page=element.page,
            headers=headers,
            rows=rows,
            bbox=element.bbox,
            confidence=ConfidenceScore(value=0.7, model="text_parser"),
            metadata={"source_element": str(element.id), "num_lines": len(lines)},
        )

    async def _extract_text_tables(self, source_path: str) -> list[TableElement]:
        import os
        tables: list[TableElement] = []
        ext = os.path.splitext(source_path)[1].lower()

        if ext == ".pdf":
            try:
                import pdfplumber
                with pdfplumber.open(source_path) as pdf:
                    for page_num, page in enumerate(pdf.pages):
                        pdf_tables = page.extract_tables()
                        for pdf_table in pdf_tables:
                            if not pdf_table or len(pdf_table) < 2:
                                continue
                            headers = [str(c or "") for c in pdf_table[0]]
                            rows: list[list[TableCell]] = []
                            for ri, row in enumerate(pdf_table[1:]):
                                row_cells = [
                                    TableCell(text=str(c or ""), row=ri, col=ci)
                                    for ci, c in enumerate(row)
                                ]
                                rows.append(row_cells)
                            tables.append(
                                TableElement(
                                    id=uuid4(),
                                    page=page_num,
                                    headers=headers,
                                    rows=rows,
                                    confidence=ConfidenceScore(value=0.85, model="pdfplumber"),
                                )
                            )
            except ImportError:
                logger.debug("pdfplumber not available for table extraction")
            except Exception as exc:
                logger.warning("pdfplumber table extraction failed: %s", exc)

        return tables
