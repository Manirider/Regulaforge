from __future__ import annotations

import logging

from regulaforge.document_intelligence.domain.models import (
    ConfidenceScore,
    TableCell,
    TableElement,
)

logger = logging.getLogger(__name__)


class CamelotTableExtractor:
    async def extract(self, pdf_path: str) -> list[TableElement]:
        tables: list[TableElement] = []
        try:
            import camelot
            parsed = camelot.read_pdf(pdf_path, pages="all", flavor="lattice")
            for _i, table in enumerate(parsed):
                rows: list[list[TableCell]] = []
                headers: list[str] = []
                df = table.df
                for ri in range(len(df)):
                    row_cells = []
                    for ci in range(len(df.columns)):
                        cell = TableCell(
                            text=str(df.iloc[ri, ci]),
                            row=ri,
                            col=ci,
                            is_header=ri == 0,
                        )
                        row_cells.append(cell)
                    if ri == 0:
                        headers = [str(df.iloc[ri, ci]) for ci in range(len(df.columns))]
                    rows.append(row_cells)

                tables.append(
                    TableElement(
                        id=__import__("uuid").uuid4(),
                        page=table.page,
                        headers=headers,
                        rows=rows if len(rows) > 1 else rows,
                        confidence=ConfidenceScore(value=table.parsing_report.get("accuracy", 0) / 100.0 if hasattr(table, "parsing_report") else 0.85, model="camelot"),  # noqa: E501
                    )
                )
            logger.info("Camelot: %d tables from %s", len(tables), pdf_path)
        except ImportError:
            logger.debug("camelot-py not available")
        except Exception as exc:
            logger.warning("Camelot extraction failed: %s", exc)
        return tables
