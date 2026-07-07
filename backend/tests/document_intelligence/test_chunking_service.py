from __future__ import annotations

import pytest
from regulaforge.document_intelligence.application.chunking_service import ChunkingService


class TestChunkingService:
    @pytest.fixture
    def chunker(self) -> ChunkingService:
        return ChunkingService()

    @pytest.mark.asyncio
    async def test_chunk_empty_text_empty_elements(self, chunker) -> None:
        chunks = await chunker.chunk("")
        assert chunks == []

    @pytest.mark.asyncio
    async def test_chunk_simple_text(self, chunker, sample_text) -> None:
        chunks = await chunker.chunk(sample_text)
        assert len(chunks) > 0
        for c in chunks:
            assert c.text.strip()

    @pytest.mark.asyncio
    async def test_chunk_no_overlap(self, chunker, sample_text) -> None:
        chunks = await chunker.chunk(sample_text)
        seen = set()
        for c in chunks:
            start_key = (c.page, c.start_char)
            assert start_key not in seen
            seen.add(start_key)

    @pytest.mark.asyncio
    async def test_chunk_with_elements(self, chunker, sample_text, sample_elements) -> None:
        chunks = await chunker.chunk(sample_text, sample_elements)
        assert len(chunks) > 0
        for c in chunks:
            assert c.tokens > 0

    @pytest.mark.asyncio
    async def test_chunk_indexes_are_sequential(self, chunker, sample_text) -> None:
        chunks = await chunker.chunk(sample_text)
        for i, c in enumerate(chunks):
            assert c.chunk_index == i

    @pytest.mark.asyncio
    async def test_chunk_with_entities(self, chunker, sample_text, sample_entities) -> None:
        chunks = await chunker.chunk(sample_text, entities=sample_entities)
        assert len(chunks) > 0
        has_entity_metadata = any("entities" in c.metadata for c in chunks)
        assert has_entity_metadata
