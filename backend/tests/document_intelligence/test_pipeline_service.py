from __future__ import annotations

from uuid import uuid4

import pytest
from regulaforge.document_intelligence.application.pipeline_service import DocumentIntelligencePipeline
from regulaforge.document_intelligence.application.enums import ProcessingStatus


class TestDocumentIntelligencePipeline:
    @pytest.fixture
    def pipeline(self, sample_pipeline) -> DocumentIntelligencePipeline:
        return sample_pipeline

    @pytest.mark.asyncio
    async def test_process_empty_path(self, pipeline) -> None:
        result = await pipeline.process(source_path="")
        assert result.status == ProcessingStatus.FAILED

    @pytest.mark.asyncio
    async def test_process_nonexistent(self, pipeline) -> None:
        result = await pipeline.process(source_path="/nonexistent/file.pdf")
        assert result.status == ProcessingStatus.FAILED

    @pytest.mark.asyncio
    async def test_process_text_file(self, pipeline, tmp_path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("This is a test document for RBI compliance.", encoding="utf-8")
        result = await pipeline.process(
            source_path=str(f),
            extract_tables=False,
            run_ner=False,
            run_classification=False,
            run_chunking=False,
        )
        assert result.status == ProcessingStatus.COMPLETED
        assert result.source_path == str(f)

    @pytest.mark.asyncio
    async def test_result_to_dict(self, pipeline, tmp_path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("Test document.", encoding="utf-8")
        result = await pipeline.process(
            source_path=str(f),
            extract_tables=False,
            run_ner=False,
            run_classification=False,
            run_chunking=False,
        )
        d = result.to_dict()
        assert "source_path" in d
        assert "status" in d
        assert "entities" in d
        assert "chunks" in d
        assert d["status"] == "completed"

    @pytest.mark.asyncio
    async def test_process_with_ner(self, pipeline, tmp_path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("The Reserve Bank of India issued this circular.", encoding="utf-8")
        result = await pipeline.process(
            source_path=str(f),
            extract_tables=False,
            extract_clauses=False,
            extract_forms=False,
            extract_lists=False,
            run_ner=True,
            run_classification=False,
            run_chunking=False,
            run_relations=False,
        )
        assert result.status == ProcessingStatus.COMPLETED
        assert len(result.entities) > 0

    @pytest.mark.asyncio
    async def test_process_with_classification(self, pipeline, tmp_path) -> None:
        f = tmp_path / "circular.txt"
        f.write_text("CIRCULAR ON KYC\nReserve Bank of India\nThis circular is issued.", encoding="utf-8")
        result = await pipeline.process(
            source_path=str(f),
            extract_tables=False,
            extract_clauses=False,
            extract_forms=False,
            extract_lists=False,
            run_ner=False,
            run_classification=True,
            run_chunking=False,
            run_relations=False,
        )
        assert result.classification is not None

    @pytest.mark.asyncio
    async def test_process_skipped_stages(self, pipeline, tmp_path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("Some text for processing.", encoding="utf-8")
        result = await pipeline.process(
            source_path=str(f),
            extract_tables=False,
            extract_clauses=False,
            extract_forms=False,
            extract_lists=False,
            run_ner=False,
            run_classification=False,
            run_chunking=False,
            run_relations=False,
        )
        assert result.status == ProcessingStatus.COMPLETED
        assert result.entities == []
        assert result.classification is None
        assert result.chunks == []
        assert result.tables == []
