from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from regulaforge.graphrag.domain.enums import (
    EntityCategory,
    GraphRelationshipType,
)
from regulaforge.graphrag.domain.models import (
    ChunkNode,
    DocumentNode,
    EntityNode,
    RelationshipEdge,
    TemporalEvent,
)

logger = logging.getLogger(__name__)

ENTITY_PATTERNS: dict[EntityCategory, list[str]] = {
    EntityCategory.REGULATION: [
        r"(?:Regulation|Directive|Rule|Guideline)\s+(?:No\.\s*)?(\d+[./]\d+)",
        r"(?:Securities and Exchange Board of India|RBI|IRDAI|SEBI)\s+\((?:\w+\s+)*?(?:Regulations|Rules|Guidelines)\s+\d+",  # noqa: E501
    ],
    EntityCategory.STATUTE: [
        r"(?:Act|Ordinance|Code|Law)\s+(?:No\.\s*)?(\d+\s+of\s+\d{4})",
        r"(?:Companies Act|Income Tax Act|GST Act|Banking Regulation Act)[,\s]+(\d{4})",
    ],
    EntityCategory.ORGANIZATION: [
        r"(?:Reserve Bank of India|Securities and Exchange Board of India|IRDAI|SEBI|RBI|Ministry of Finance|Government of India)",  # noqa: E501
    ],
    EntityCategory.JURISDICTION: [
        r"(?:Supreme Court|High Court|Tribunal|Appellate Authority|Competition Commission)",
    ],
    EntityCategory.AMOUNT: [
        r"(?:Rs\.?|₹|INR)\s*[0-9,]+(?:\s*(?:crore|lakh|crore|trillion|billion|million))?(?:\s*(?:rupees|))?",
        r"(?:penalty|fine|fee|charge)\s+(?:of\s+)?(?:Rs\.?|₹|INR)\s*[0-9,]+",
    ],
    EntityCategory.PENALTY: [
        r"(?:penalty|fine|sanction|punishment)[^.]*(?:Rs\.?|₹|INR)\s*[0-9,]+",
        r"(?:imprisonment|incarceration)\s+(?:for\s+)?(?:a\s+period\s+of\s+)?\d+\s+years?",
    ],
    EntityCategory.COMPLIANCE_REQUIREMENT: [
        r"(?:shall|must|required to|obligated to|mandatory to|comply with)[^.]*\.",
        r"(?:furnish|submit|file|disclose|report)[^.]*(?:to|with|before)[^.]*\.",
    ],
    EntityCategory.REPORTING_DEADLINE: [
        r"(?:within|before|by|no later than|not later than)\s+\d+\s+(?:days|weeks|months|years)",
        r"(?:due date|deadline|period of)\s+(?:for|of)?\s*(?:filing|submission|compliance|reporting)",
    ],
    EntityCategory.DEFINITION: [
        r"(?:means|defined as|refers to|shall include|shall mean)[^.]*\.",
    ],
    EntityCategory.CITATION: [
        r"(?:\(\d{4}\)\s+\d+\s+SCC\s+\d+|AIR\s+\d{4}\s+\w+\s+\d+|\(\d{4}\)\s+\d+\s+SCR\s+\d+)",
        r"(?:Section|Article|Clause|Rule|Regulation)\s+\d+[.\d]*(?:\([a-z]\))*",
    ],
    EntityCategory.DATE: [
        r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b",
        r"\b(\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})\b",
    ],
    EntityCategory.PERSON: [
        r"(?:Shri|Mr\.|Ms\.|Dr\.|Justice)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*",
    ],
}


class GraphConstructor:
    def __init__(
        self,
        neo4j_client: Any,
        chunk_size: int = 512,
        chunk_overlap: int = 64,
    ) -> None:
        self.neo4j = neo4j_client
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    async def build_from_document(
        self,
        document_id: str,
        text: str,
        title: str,
        source: str,
        doc_type: str,
        jurisdiction: Optional[str] = None,
        regulatory_body: Optional[str] = None,
        published_date: Optional[datetime] = None,
        metadata: Optional[dict[str, Any]] = None,
        page_map: Optional[dict[int, str]] = None,
    ) -> dict[str, Any]:
        logger.info("Building graph from document %s: %s", document_id, title)
        doc_node = DocumentNode(
            id=document_id,
            title=title,
            source=source,
            doc_type=doc_type,
            jurisdiction=jurisdiction,
            regulatory_body=regulatory_body,
            published_date=published_date,
            metadata=metadata or {},
        )
        await self.neo4j.create_document_node(doc_node)

        chunks = self._chunk_text(text, document_id, page_map)
        for chunk in chunks:
            await self.neo4j.create_chunk_node(chunk)
            await self.neo4j.link_chunk_to_document(chunk.id, document_id)

        all_entities: dict[str, EntityNode] = {}
        for chunk in chunks:
            entities = self._extract_entities(chunk.text)
            for entity in entities:
                if entity.name not in all_entities:
                    all_entities[entity.name] = entity
                    await self.neo4j.create_entity_node(entity)
                await self.neo4j.link_entity_to_chunk(
                    all_entities[entity.name].id,
                    chunk.id,
                )

        entity_list = list(all_entities.values())
        self._extract_relationships(entity_list, chunks)

        for chunk in chunks:
            events = self._extract_temporal_events(chunk.text, chunk.id, entity_list)
            for event in events:
                await self.neo4j.create_temporal_event(event)

        logger.info(
            "Graph built: doc=%s, chunks=%d, entities=%d",
            document_id,
            len(chunks),
            len(all_entities),
        )
        return {
            "document_id": document_id,
            "chunks": len(chunks),
            "entities": len(all_entities),
        }

    def _chunk_text(
        self,
        text: str,
        document_id: str,
        page_map: Optional[dict[int, str]] = None,
    ) -> list[ChunkNode]:
        paragraphs = re.split(r"\n\s*\n", text)
        chunks: list[ChunkNode] = []
        current_chunk: list[str] = []
        current_size = 0
        chunk_index = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            para_words = len(para.split())
            if current_size + para_words > self.chunk_size and current_chunk:
                chunk_text = " ".join(current_chunk)
                chunk_id = f"{document_id}_chunk_{chunk_index:04d}"
                page_no = self._guess_page(chunk_text, page_map) if page_map else None
                chunks.append(
                    ChunkNode(
                        id=chunk_id,
                        document_id=document_id,
                        text=chunk_text,
                        chunk_index=chunk_index,
                        page_number=page_no,
                        heading=self._extract_heading(chunk_text),
                    )
                )
                overlap_words = current_chunk[-min(
                    len(current_chunk),
                    max(1, self.chunk_overlap),
                ):]
                current_chunk = list(overlap_words)
                current_chunk.append(para)
                current_size = sum(len(p.split()) for p in current_chunk)
                chunk_index += 1
            else:
                current_chunk.append(para)
                current_size += para_words

        if current_chunk:
            chunk_text = " ".join(current_chunk)
            chunk_id = f"{document_id}_chunk_{chunk_index:04d}"
            page_no = self._guess_page(chunk_text, page_map) if page_map else None
            chunks.append(
                ChunkNode(
                    id=chunk_id,
                    document_id=document_id,
                    text=chunk_text,
                    chunk_index=chunk_index,
                    page_number=page_no,
                    heading=self._extract_heading(chunk_text),
                )
            )

        return chunks

    def _extract_heading(self, text: str) -> Optional[str]:
        lines = text.strip().split("\n")
        for line in lines[:5]:
            line = line.strip()
            if line and (line.isupper() or re.match(r"^[A-Z][a-z]+[\s\w]*:", line)):
                return line[:200]
        return None

    def _guess_page(
        self, text: str, page_map: dict[int, str]
    ) -> Optional[int]:
        for page_num, page_text in page_map.items():
            overlap = len(set(text.split()) & set(page_text.split()))
            if overlap > 10:
                return page_num
        return None

    def _extract_entities(self, text: str) -> list[EntityNode]:
        seen: set[str] = set()
        entities: list[EntityNode] = []

        for category, patterns in ENTITY_PATTERNS.items():
            for pattern in patterns:
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    name = match.group(0).strip()
                    if name.lower() in seen:
                        continue
                    seen.add(name.lower())
                    entity = EntityNode(
                        id=str(uuid4()),
                        name=name,
                        category=category,
                        first_seen=datetime.utcnow(),
                        last_seen=datetime.utcnow(),
                    )
                    entities.append(entity)

        return entities

    def _extract_relationships(
        self,
        entities: list[EntityNode],
        chunks: list[ChunkNode],
    ) -> None:
        import itertools

        chunk_texts = {c.id: c.text.lower() for c in chunks}
        entity_texts = {e.name.lower(): e for e in entities}

        seen_pairs: set[tuple[str, ...]] = set()

        for _chunk_id, text in chunk_texts.items():
            chunk_entities = [
                e for e_name, e in entity_texts.items() if e_name in text
            ]
            for e1, e2 in itertools.combinations(chunk_entities, 2):
                pair_key = tuple(sorted([e1.id, e2.id]))
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                rel_type = self._infer_relationship(e1, e2)
                edge = RelationshipEdge(
                    source_id=e1.id,
                    target_id=e2.id,
                    relationship_type=rel_type,
                    weight=0.8,
                    confidence=0.7,
                )
                self._schedule_relationship(edge)

    def _infer_relationship(
        self, e1: EntityNode, e2: EntityNode
    ) -> GraphRelationshipType:
        if e1.category == EntityCategory.REGULATION and e2.category == EntityCategory.ORGANIZATION:
            return GraphRelationshipType.REGULATES
        if e1.category == EntityCategory.ORGANIZATION and e2.category == EntityCategory.REGULATION:
            return GraphRelationshipType.REGULATES
        if e1.category == EntityCategory.STATUTE and e2.category == EntityCategory.JURISDICTION:
            return GraphRelationshipType.REFERENCES
        if e1.category == EntityCategory.JURISDICTION and e2.category == EntityCategory.STATUTE:
            return GraphRelationshipType.REFERENCES
        return GraphRelationshipType.RELATED_TO

    def _schedule_relationship(self, edge: RelationshipEdge) -> None:
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self.neo4j.create_relationship(edge))  # noqa: RUF006
        except RuntimeError:
            pass

    def _extract_temporal_events(
        self,
        text: str,
        chunk_id: str,
        entities: list[EntityNode],
    ) -> list[TemporalEvent]:
        events: list[TemporalEvent] = []
        date_patterns = [
            r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})",
            r"(\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})",
            r"(?:(\d{4})\s*-\s*(\d{4}))",
        ]

        for pattern in date_patterns:
            for match in re.finditer(pattern, text):
                date_str = match.group(0)
                event_id = f"evt_{chunk_id}_{len(events)}"
                event = TemporalEvent(
                    id=event_id,
                    name=f"Event at {date_str}",
                    date=datetime.utcnow(),
                    description=text[match.start():match.end() + 200][:500],
                    entity_ids=[e.id for e in entities if e.name.lower() in text.lower()],
                )
                events.append(event)

        return events
