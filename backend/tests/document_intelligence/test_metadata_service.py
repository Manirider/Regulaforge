from __future__ import annotations

import pytest
from regulaforge.document_intelligence.application.metadata_service import MetadataService
from regulaforge.document_intelligence.application.models import SemanticMetadata


class TestMetadataService:
    @pytest.fixture
    def metadata_service(self) -> MetadataService:
        return MetadataService()

    @pytest.mark.asyncio
    async def test_generate_empty_text(self, metadata_service) -> None:
        meta = await metadata_service.generate("")
        assert meta.title is None
        assert meta.page_count == 0
        assert meta.word_count == 0

    @pytest.mark.asyncio
    async def test_generate_title(self, metadata_service, sample_text) -> None:
        meta = await metadata_service.generate(sample_text)
        assert meta.title is not None
        assert "MASTER DIRECTION" in meta.title

    @pytest.mark.asyncio
    async def test_generate_word_count(self, metadata_service, sample_text) -> None:
        meta = await metadata_service.generate(sample_text)
        assert meta.word_count > 50

    @pytest.mark.asyncio
    async def test_generate_keywords(self, metadata_service, sample_text) -> None:
        meta = await metadata_service.generate(sample_text)
        assert len(meta.keywords) > 0

    @pytest.mark.asyncio
    async def test_generate_jurisdiction(self, metadata_service, sample_text) -> None:
        meta = await metadata_service.generate(sample_text)
        assert meta.jurisdiction is not None
        assert "India" in meta.jurisdiction

    @pytest.mark.asyncio
    async def test_generate_regulatory_body(self, metadata_service, sample_text) -> None:
        meta = await metadata_service.generate(sample_text)
        assert meta.regulatory_body is not None
        assert "Reserve Bank of India" in meta.regulatory_body

    @pytest.mark.asyncio
    async def test_generate_summary(self, metadata_service, sample_text) -> None:
        meta = await metadata_service.generate(sample_text)
        assert meta.summary is not None
        assert len(meta.summary) > 20

    @pytest.mark.asyncio
    async def test_generate_with_entities(self, metadata_service, sample_text, sample_entities) -> None:
        meta = await metadata_service.generate(sample_text, entities=sample_entities)
        assert len(meta.entities) > 0
