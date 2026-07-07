"""Tests for semantic chunking engines."""

from __future__ import annotations

import pytest

from regulaforge.document_intelligence.chunking.semantic_chunker import (
    ChunkOverlapMode,
    SemanticChunker,
    SentenceWindowChunker,
)


@pytest.mark.asyncio
async def test_sentence_window_available():
    c = SentenceWindowChunker()
    assert await c.is_available()


@pytest.mark.asyncio
async def test_sentence_window_empty():
    c = SentenceWindowChunker()
    result = await c.chunk("")
    assert result.num_chunks == 0


@pytest.mark.asyncio
async def test_sentence_window_single_sentence():
    c = SentenceWindowChunker()
    result = await c.chunk("This is a single sentence.")
    assert result.num_chunks == 1
    assert result.chunks[0].text == "This is a single sentence."


@pytest.mark.asyncio
async def test_sentence_window_multiple_chunks():
    c = SentenceWindowChunker(chunk_size=2, overlap=0)
    text = "First sentence here. Second sentence here. Third sentence here. Fourth sentence here."
    result = await c.chunk(text)
    assert result.num_chunks == 2
    assert "First" in result.chunks[0].text
    assert "Third" in result.chunks[1].text


@pytest.mark.asyncio
async def test_sentence_window_with_overlap():
    c = SentenceWindowChunker(chunk_size=2, overlap=1)
    text = "Sent A. Sent B. Sent C. Sent D."
    result = await c.chunk(text)
    assert result.num_chunks >= 2
    assert result.chunks[0].metadata.get("sentence_start") == 0
    if result.num_chunks > 1:
        assert result.chunks[1].metadata.get("sentence_start") == 1


@pytest.mark.asyncio
async def test_sentence_window_page_number():
    c = SentenceWindowChunker()
    text = "Page one content. More page one content."
    result = await c.chunk(text, page_number=1)
    assert result.chunks[0].page_number == 1


@pytest.mark.asyncio
async def test_chunk_overlap_mode_values():
    assert ChunkOverlapMode.NONE.value == "none"
    assert ChunkOverlapMode.SENTENCE.value == "sentence"
    assert ChunkOverlapMode.CHUNK.value == "chunk"


@pytest.mark.asyncio
async def test_semantic_chunker_abstract():
    with pytest.raises(TypeError):
        SemanticChunker()  # type: ignore[abstract]


@pytest.mark.asyncio
async def test_sentence_window_step_at_least_one():
    c = SentenceWindowChunker(chunk_size=5, overlap=10)  # overlap >= chunk_size
    text = "A. B. C. D. E. F. G."
    result = await c.chunk(text)
    assert result.num_chunks > 0
