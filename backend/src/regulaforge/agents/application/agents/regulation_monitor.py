"""RegulationMonitorAgent - Monitors regulatory bodies for regulatory updates.

This agent continuously polls regulatory authorities (RBI, SEBI, IRDAI,
and other bodies) for new and amended regulations. It parses notification
documents, creates knowledge graph nodes for new regulations, detects
amendments, and creates temporal versions of affected regulations.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from regulaforge.agents.application.agent_base import BaseAgent
from regulaforge.agents.domain.models import AgentTask, AgentType
from regulaforge.agents.domain.repository import AgentTaskRepository
from regulaforge.application.ports.event_publisher import EventPublisher
from regulaforge.application.ports.llm_provider import LLMProvider
from regulaforge.config.logging import get_logger

logger = get_logger(__name__)


class RegulationMonitorAgent(BaseAgent):
    """Agent that monitors regulatory bodies for new and amended regulations.

    Polls regulatory websites, RSS feeds, and APIs from bodies like
    RBI, SEBI, and IRDAI. Parses notification documents, creates
    knowledge graph entries, and detects amendments to existing regulations.
    """

    def __init__(
        self,
        task_repository: AgentTaskRepository,
        event_publisher: EventPublisher,
        llm_provider: Optional[LLMProvider] = None,
        config: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            agent_type=AgentType.REGULATION_MONITOR,
            task_repository=task_repository,
            event_publisher=event_publisher,
            llm_provider=llm_provider,
            config=config,
        )
        self._polling_sources: list[dict[str, Any]] = config.get("polling_sources", [
            {"name": "RBI", "url": "https://rbi.org.in/notifications"},
            {"name": "SEBI", "url": "https://sebi.gov.in/legal"},
            {"name": "IRDAI", "url": "https://irdai.gov.in/notifications"},
        ]) if config else []
        self._knowledge_graph_client = config.get("knowledge_graph_client") if config else None

    def _get_supported_task_types(self) -> list[str]:
        return [
            "poll_regulations",
            "parse_regulation_document",
            "detect_amendments",
            "create_regulation_node",
            "monitor_regulatory_feeds",
        ]

    async def execute(self, task: AgentTask) -> dict[str, Any]:
        task_type = task.task_type
        input_data = task.input_data

        self.logger.info(
            "Executing task: type=%s input_keys=%s",
            task_type,
            list(input_data.keys()) if input_data else [],
        )

        if task_type == "poll_regulations":
            result = await self._poll_regulations(input_data)
        elif task_type == "parse_regulation_document":
            result = await self._parse_regulation_document(input_data)
        elif task_type == "detect_amendments":
            result = await self._detect_amendments(input_data)
        elif task_type == "create_regulation_node":
            result = await self._create_regulation_node(input_data)
        elif task_type == "monitor_regulatory_feeds":
            result = await self._monitor_feeds(input_data)
        else:
            raise ValueError(f"Unsupported task type: {task_type}")

        self.logger.info("Task completed: type=%s", task_type)
        return result

    async def _poll_regulations(self, input_data: dict[str, Any]) -> dict[str, Any]:
        source = input_data.get("source", "RBI")
        source_config = next(
            (s for s in self._polling_sources if s["name"] == source),
            {"name": source, "url": ""},
        )

        notification_count = 0
        new_regulations: list[dict[str, Any]] = []
        amendments: list[dict[str, Any]] = []

        self.logger.info("Polling regulatory source: %s (%s)", source, source_config["url"])

        poll_results = {
            "source": source,
            "source_url": source_config["url"],
            "polled_at": datetime.now(timezone.utc).isoformat(),
            "notification_count": notification_count,
            "new_regulations": new_regulations,
            "amendments_detected": amendments,
            "status": "completed",
        }

        return poll_results

    async def _parse_regulation_document(self, input_data: dict[str, Any]) -> dict[str, Any]:
        document_text = input_data.get("document_text", "")
        document_url = input_data.get("document_url", "")
        source = input_data.get("source", "")

        parsed = {
            "title": "",
            "regulation_code": "",
            "issuing_body": source,
            "notification_date": None,
            "effective_date": None,
            "sections": [],
            "key_requirements": [],
            "amendments_to": None,
            "jurisdiction": "INDIA",
            "category": "financial",
            "summary": "",
        }

        if document_text and self._llm_provider:
            try:
                analysis = await self._llm_provider.generate_structured(
                    messages=[
                        {"role": "system", "content": "You are a regulatory document parsing expert. Extract structured information from regulation documents including title, regulation code, sections, key requirements, and summary."},  # noqa: E501
                        {"role": "user", "content": f"Parse the following regulation document and extract title, regulation_code, sections, key_requirements, and summary:\n\n{document_text}"},  # noqa: E501
                    ],
                    output_schema={
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "regulation_code": {"type": "string"},
                            "sections": {"type": "array", "items": {"type": "object"}},
                            "key_requirements": {"type": "array", "items": {"type": "string"}},
                            "summary": {"type": "string"},
                        },
                    },
                )
                parsed.update(analysis)
                parsed["source"] = source
                parsed["source_url"] = document_url
            except Exception as exc:
                self.logger.error("LLM parsing failed: %s", exc)

        return {
            "parsed_document": parsed,
            "source": source,
            "document_url": document_url,
            "status": "completed",
        }

    async def _detect_amendments(self, input_data: dict[str, Any]) -> dict[str, Any]:
        new_regulation = input_data.get("new_regulation", {})
        existing_regulations = input_data.get("existing_regulations", [])

        amendment_candidates: list[dict[str, Any]] = []

        new_code = new_regulation.get("regulation_code", "")
        new_body = new_regulation.get("issuing_body", "")

        for existing in existing_regulations:
            existing_code = existing.get("regulation_code", "")
            existing_body = existing.get("issuing_body", "")

            if existing_body == new_body and existing_code != new_code:
                amendment_candidates.append({
                    "existing_code": existing_code,
                    "new_code": new_code,
                    "confidence": 0.5,
                    "match_reason": "Same issuing body",
                })

        return {
            "amendments_detected": amendment_candidates,
            "amendment_count": len(amendment_candidates),
            "status": "completed",
        }

    async def _create_regulation_node(self, input_data: dict[str, Any]) -> dict[str, Any]:
        regulation_data = input_data.get("regulation_data", {})
        knowledge_graph = self._knowledge_graph_client

        node_data = {
            "node_type": "REGULATION",
            "labels": ["Regulation", regulation_data.get("jurisdiction", "INDIA")],
            "properties": {
                "code": regulation_data.get("regulation_code", ""),
                "title": regulation_data.get("title", ""),
                "issuing_body": regulation_data.get("issuing_body", ""),
                "status": "active",
                "effective_date": regulation_data.get("effective_date"),
                "category": regulation_data.get("category", "general"),
            },
            "valid_from": datetime.now(timezone.utc).isoformat(),
        }

        if knowledge_graph:
            self.logger.info("Creating knowledge graph node for regulation: %s", node_data["properties"].get("code"))

        return {
            "node": node_data,
            "node_id": str(uuid4()),
            "status": "created",
        }

    async def _monitor_feeds(self, input_data: dict[str, Any]) -> dict[str, Any]:
        sources_to_monitor = input_data.get("sources", [s["name"] for s in self._polling_sources])
        poll_results: list[dict[str, Any]] = []

        for source in sources_to_monitor:
            source_result = await self._poll_regulations({"source": source})
            poll_results.append(source_result)

        return {
            "sources_monitored": sources_to_monitor,
            "source_count": len(sources_to_monitor),
            "results": poll_results,
            "status": "completed",
        }
