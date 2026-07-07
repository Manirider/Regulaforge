from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from regulaforge.graphrag.domain.enums import TemporalRelation
from regulaforge.graphrag.domain.models import TemporalEvent, TemporalQuery

logger = logging.getLogger(__name__)


class TemporalGraphService:
    def __init__(self, neo4j_client: Any) -> None:
        self.neo4j = neo4j_client

    async def query_temporal(
        self,
        query: TemporalQuery,
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = await self.neo4j.temporal_graph_query(query)
        logger.info(
            "Temporal query: %s-%s, results=%d",
            query.start_date,
            query.end_date,
            len(results),
        )
        return results

    async def get_timeline(
        self,
        entity_name: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> list[dict[str, Any]]:
        tq = TemporalQuery(
            start_date=start_date,
            end_date=end_date,
            entity_names=[entity_name],
            relation=TemporalRelation.DURING,
        )
        results = await self.neo4j.temporal_graph_query(tq)
        return list(results)

    async def find_temporal_relationships(
        self,
        source_entity: str,
        target_entity: str,
    ) -> list[dict[str, Any]]:
        async with self.neo4j._session() as session:
            result = await session.run(
                """
                MATCH (a:Entity {name: $source})-[r]-(te:TemporalEvent)-[r2]-(b:Entity {name: $target})
                RETURN te, type(r) as rel1, type(r2) as rel2
                ORDER BY te.date
                """,
                source=source_entity,
                target=target_entity,
            )
            return [dict(record) async for record in result]

    async def get_events_in_range(
        self,
        start: datetime,
        end: datetime,
        event_types: Optional[list[str]] = None,
    ) -> list[TemporalEvent]:
        tq = TemporalQuery(
            start_date=start,
            end_date=end,
            event_types=event_types,
        )
        results = await self.neo4j.temporal_graph_query(tq)
        events = []
        for r in results:
            te = r.get("te")
            if te:
                events.append(
                    TemporalEvent(
                        id=te.get("id", ""),
                        name=te.get("name", ""),
                        date=datetime.fromisoformat(te.get("date")) if isinstance(te.get("date"), str) else datetime.utcnow(),  # noqa: E501
                        end_date=datetime.fromisoformat(te.get("end_date")) if isinstance(te.get("end_date"), str) and te.get("end_date") else None,  # noqa: E501
                        description=te.get("description"),
                        event_type=te.get("event_type"),
                    )
                )
        return events
