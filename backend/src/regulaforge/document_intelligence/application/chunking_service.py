from __future__ import annotations

import logging
import re
from typing import Optional
from uuid import uuid4

from regulaforge.document_intelligence.application.enums import ElementType
from regulaforge.document_intelligence.application.models import (
    ConfidenceScore,
    DocumentElement,
    ExtractedEntity,
    TextChunk,
)

logger = logging.getLogger(__name__)


class ChunkingService:
    def __init__(
        self,
        max_chunk_size: int = 1024,
        min_chunk_size: int = 128,
        overlap: int = 64,
    ) -> None:
        self._max_chunk_size = max_chunk_size
        self._min_chunk_size = min_chunk_size
        self._overlap = overlap

    async def chunk(
        self,
        text: str,
        elements: Optional[list[DocumentElement]] = None,
        entities: Optional[list[ExtractedEntity]] = None,
    ) -> list[TextChunk]:
        chunks: list[TextChunk] = []

        chunks = self._element_based_chunking(elements, text) if elements else self._semantic_chunking(text)

        chunks = self._merge_small_chunks(chunks)
        return self._enrich_chunks(chunks, text, entities)

    def _element_based_chunking(
        self,
        elements: list[DocumentElement],
        _full_text: str,
    ) -> list[TextChunk]:
        chunks: list[TextChunk] = []
        current_text: list[str] = []
        current_elements: list[str] = []
        char_offset = 0

        for elem in elements:
            if elem.element_type in (ElementType.HEADER, ElementType.FOOTER, ElementType.PAGE_NUMBER):
                continue
            text_len = len(elem.text) + 1
            candidate = " ".join([*current_text, elem.text]) if current_text else elem.text

            if len(candidate) > self._max_chunk_size and current_text:
                chunk_text = " ".join(current_text)
                chunks.append(
                    TextChunk(
                        id=uuid4(),
                        text=chunk_text,
                        page=elem.page,
                        chunk_index=len(chunks),
                        start_char=char_offset - len(chunk_text),
                        end_char=char_offset,
                        tokens=len(chunk_text.split()),
                        confidence=ConfidenceScore(value=0.9, model="element_chunker"),
                    )
                )
                current_text = [elem.text]
                current_elements = [str(elem.id)]
            else:
                current_text.append(elem.text)
                current_elements.append(str(elem.id))
            char_offset += text_len

        if current_text:
            chunk_text = " ".join(current_text)
            chunks.append(
                TextChunk(
                    id=uuid4(),
                    text=chunk_text,
                    page=elements[-1].page if elements else 0,
                    chunk_index=len(chunks),
                    start_char=char_offset - len(chunk_text),
                    end_char=char_offset,
                    tokens=len(chunk_text.split()),
                    confidence=ConfidenceScore(value=0.9, model="element_chunker"),
                )
            )

        return chunks

    def _semantic_chunking(self, text: str) -> list[TextChunk]:
        chunks: list[TextChunk] = []
        sections = re.split(r"\n(?=(?:Section|Article|Clause|CHAPTER|PART|Schedule)\s+\d+)", text, flags=re.IGNORECASE)

        char_offset = 0
        for _i, section in enumerate(sections):
            section = section.strip()
            if not section:
                continue

            if len(section) <= self._max_chunk_size:
                chunks.append(
                    TextChunk(
                        id=uuid4(),
                        text=section,
                        page=0,
                        chunk_index=len(chunks),
                        start_char=char_offset,
                        end_char=char_offset + len(section),
                        section_title=self._extract_section_title(section),
                        tokens=len(section.split()),
                        confidence=ConfidenceScore(value=0.85, model="semantic_chunker"),
                    )
                )
                char_offset += len(section) + 1
            else:
                paragraphs = section.split("\n\n")
                for para in paragraphs:
                    para = para.strip()
                    if not para:
                        continue
                    if len(para) > self._max_chunk_size:
                        sub_chunks = self._split_large_chunk(para, char_offset, len(chunks))
                        chunks.extend(sub_chunks)
                        char_offset += len(para) + 2
                    else:
                        chunks.append(
                            TextChunk(
                                id=uuid4(),
                                text=para,
                                page=0,
                                chunk_index=len(chunks),
                                start_char=char_offset,
                                end_char=char_offset + len(para),
                                section_title=self._extract_section_title(section),
                                tokens=len(para.split()),
                                confidence=ConfidenceScore(value=0.8, model="semantic_chunker"),
                            )
                        )
                        char_offset += len(para) + 2

        return chunks

    def _split_large_chunk(self, text: str, base_offset: int, base_index: int) -> list[TextChunk]:
        chunks: list[TextChunk] = []
        sentences = re.split(r"(?<=[.!?])\s+", text)
        current = ""
        offset = base_offset

        for sentence in sentences:
            if len(current) + len(sentence) > self._max_chunk_size and current:
                chunks.append(
                    TextChunk(
                        id=uuid4(),
                        text=current.strip(),
                        page=0,
                        chunk_index=base_index + len(chunks),
                        start_char=offset,
                        end_char=offset + len(current),
                        tokens=len(current.split()),
                        confidence=ConfidenceScore(value=0.75, model="sentence_splitter"),
                    )
                )
                offset += len(current)
                current = sentence
            else:
                current += " " + sentence if current else sentence

        if current.strip():
            chunks.append(
                TextChunk(
                    id=uuid4(),
                    text=current.strip(),
                    page=0,
                    chunk_index=base_index + len(chunks),
                    start_char=offset,
                    end_char=offset + len(current),
                    tokens=len(current.split()),
                    confidence=ConfidenceScore(value=0.75, model="sentence_splitter"),
                )
            )
        return chunks

    def _merge_small_chunks(self, chunks: list[TextChunk]) -> list[TextChunk]:
        if not chunks:
            return chunks
        merged: list[TextChunk] = []
        carry = chunks[0]

        for i in range(1, len(chunks)):
            if len(carry.text) + len(chunks[i].text) <= self._max_chunk_size:
                carry = TextChunk(
                    id=carry.id if False else uuid4(),
                    text=carry.text + "\n\n" + chunks[i].text,
                    page=carry.page,
                    chunk_index=len(merged),
                    start_char=carry.start_char,
                    end_char=chunks[i].end_char,
                    tokens=len((carry.text + " " + chunks[i].text).split()),
                    confidence=ConfidenceScore(
                        value=min(carry.confidence.value, chunks[i].confidence.value),
                        model="merged",
                    ),
                )
            else:
                merged.append(carry)
                carry = chunks[i]

        merged.append(carry)
        for j, c in enumerate(merged):
            c.chunk_index = j
        return merged

    def _enrich_chunks(
        self,
        chunks: list[TextChunk],
        _full_text: str,
        entities: Optional[list[ExtractedEntity]],
    ) -> list[TextChunk]:
        if not entities:
            return chunks
        entity_map: dict[str, list[str]] = {}
        for ent in entities:
            entity_map.setdefault(ent.entity_type.value, []).append(ent.text)

        for chunk in chunks:
            chunk.metadata["entities"] = {}
            for etype, etexts in entity_map.items():
                found = [t for t in etexts if t.lower() in chunk.text.lower()]
                if found:
                    chunk.metadata["entities"][etype] = list(set(found))
        return chunks

    def _extract_section_title(self, text: str) -> Optional[str]:
        match = re.match(r"(Section|Article|Clause|CHAPTER|PART|Schedule)\s+\d+[.\d]*\s*-?\s*([A-Z][A-Za-z0-9\s]+)", text)  # noqa: E501
        if match:
            return match.group(0).strip()
        return None
