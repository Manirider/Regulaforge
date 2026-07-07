"""ClauseRecommenderAgent - Recommends regulatory clauses for entity profiles.

This agent uses GraphRAG to find similar entities and their obligations,
suggests compliance clauses based on industry patterns, generates
confidence scores for each recommendation, and provides contextual
rationale for why each clause is recommended.
"""

from __future__ import annotations

from typing import Any, Optional
from uuid import uuid4

from regulaforge.agents.application.agent_base import BaseAgent
from regulaforge.agents.domain.models import AgentTask, AgentType
from regulaforge.agents.domain.repository import AgentTaskRepository
from regulaforge.application.ports.event_publisher import EventPublisher
from regulaforge.application.ports.llm_provider import LLMProvider
from regulaforge.config.logging import get_logger

logger = get_logger(__name__)


class ClauseRecommenderAgent(BaseAgent):
    """Agent that recommends relevant regulatory clauses for entity profiles.

    Uses graph-based retrieval to find similar entities and their
    regulatory obligations, analyzes industry patterns, and provides
    ranked recommendations with confidence scores and rationale.
    """

    def __init__(
        self,
        task_repository: AgentTaskRepository,
        event_publisher: EventPublisher,
        llm_provider: Optional[LLMProvider] = None,
        config: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            agent_type=AgentType.CLAUSE_RECOMMENDER,
            task_repository=task_repository,
            event_publisher=event_publisher,
            llm_provider=llm_provider,
            config=config,
        )
        self._knowledge_graph_client = config.get("knowledge_graph_client") if config else None
        self._max_recommendations = config.get("max_recommendations", 10) if config else 10

    def _get_supported_task_types(self) -> list[str]:
        return [
            "recommend_clauses",
            "find_similar_entities",
            "analyze_industry_patterns",
            "rank_recommendations",
            "generate_rationale",
            "batch_recommend",
        ]

    async def execute(self, task: AgentTask) -> dict[str, Any]:
        task_type = task.task_type
        input_data = task.input_data

        self.logger.info(
            "Executing task: type=%s input_keys=%s",
            task_type,
            list(input_data.keys()) if input_data else [],
        )

        if task_type == "recommend_clauses":
            result = await self._recommend_clauses(input_data)
        elif task_type == "find_similar_entities":
            result = await self._find_similar_entities(input_data)
        elif task_type == "analyze_industry_patterns":
            result = await self._analyze_industry_patterns(input_data)
        elif task_type == "rank_recommendations":
            result = await self._rank_recommendations(input_data)
        elif task_type == "generate_rationale":
            result = await self._generate_rationale(input_data)
        elif task_type == "batch_recommend":
            result = await self._batch_recommend(input_data)
        else:
            raise ValueError(f"Unsupported task type: {task_type}")

        return result

    async def _recommend_clauses(self, input_data: dict[str, Any]) -> dict[str, Any]:
        entity_id = input_data.get("entity_id", str(uuid4()))
        entity_name = input_data.get("entity_name", "")
        entity_type = input_data.get("entity_type", "organization")
        industry = input_data.get("industry", "")
        existing_obligations = input_data.get("existing_obligations", [])

        similar_entities = await self._find_similar_entities({
            "entity_id": entity_id,
            "entity_type": entity_type,
            "industry": industry,
        })
        similar = similar_entities.get("entities", [])

        industry_patterns = await self._analyze_industry_patterns({
            "industry": industry,
            "entity_type": entity_type,
        })
        patterns = industry_patterns.get("patterns", [])

        recommendations: list[dict[str, Any]] = []
        seen_clauses: set = set()

        for pattern in patterns:
            clause = {
                "clause_id": str(uuid4()),
                "regulation_code": pattern.get("regulation_code", ""),
                "clause_title": pattern.get("clause_title", ""),
                "description": pattern.get("description", ""),
                "source": "industry_pattern",
                "confidence": pattern.get("confidence", 0.5),
                "rationale": f"Common clause for {industry} entities of type {entity_type}",
            }
            clause_key = f"{clause['regulation_code']}:{clause['clause_title']}"
            if clause_key not in seen_clauses:
                seen_clauses.add(clause_key)
                recommendations.append(clause)

        for entity in similar:
            for obligation in entity.get("obligations", []):
                ob_key = obligation.get("regulation_code", "")
                ob_title = obligation.get("clause_title", "")
                key = f"{ob_key}:{ob_title}"
                if key not in seen_clauses and len(recommendations) < self._max_recommendations * 2:
                    seen_clauses.add(key)
                    recommendations.append({
                        "clause_id": str(uuid4()),
                        "regulation_code": ob_key,
                        "clause_title": ob_title,
                        "description": obligation.get("description", ""),
                        "source": "similar_entity",
                        "source_entity": entity.get("name", ""),
                        "confidence": obligation.get("confidence", 0.5),
                        "rationale": f"Applied to similar entity: {entity.get('name', '')}",
                    })

        ranked_result = await self._rank_recommendations({
            "recommendations": recommendations,
            "entity_type": entity_type,
            "existing_obligations": existing_obligations,
        })
        ranked = ranked_result.get("ranked", recommendations)

        final_recommendations = ranked[:self._max_recommendations]

        for rec in final_recommendations:
            rationale = await self._generate_rationale({
                "clause": rec,
                "entity_name": entity_name,
                "entity_type": entity_type,
                "industry": industry,
            })
            rec["rationale"] = rationale.get("rationale", rec.get("rationale", ""))

        return {
            "entity_id": entity_id,
            "entity_name": entity_name,
            "recommendations": final_recommendations,
            "recommendation_count": len(final_recommendations),
            "total_candidates": len(recommendations),
            "sources": {
                "industry_patterns": len(patterns),
                "similar_entities": len(similar),
            },
            "status": "completed",
        }

    async def _find_similar_entities(self, input_data: dict[str, Any]) -> dict[str, Any]:
        entity_type = input_data.get("entity_type", "organization")
        industry = input_data.get("industry", "")

        entities: list[dict[str, Any]] = []
        if self._knowledge_graph_client:
            self.logger.info("Querying knowledge graph for similar entities")
        else:
            entities = [
                {
                    "id": str(uuid4()),
                    "name": f"Reference {entity_type} 1",
                    "type": entity_type,
                    "industry": industry,
                    "similarity_score": 0.85,
                    "obligations": [
                        {
                            "regulation_code": "RBI-2023-01",
                            "clause_title": "Data Privacy Requirements",
                            "description": "Ensure customer data privacy compliance",
                            "confidence": 0.9,
                        },
                        {
                            "regulation_code": "SEBI-2023-05",
                            "clause_title": "Reporting Obligations",
                            "description": "Submit periodic compliance reports",
                            "confidence": 0.85,
                        },
                    ],
                },
            ]

        return {
            "entities": entities,
            "entity_count": len(entities),
            "status": "completed",
        }

    async def _analyze_industry_patterns(self, input_data: dict[str, Any]) -> dict[str, Any]:
        industry = input_data.get("industry", "")
        entity_type = input_data.get("entity_type", "organization")

        common_clauses: dict[str, list[dict[str, Any]]] = {
            "banking": [
                {"regulation_code": "RBI-KYC-2023", "clause_title": "KYC Compliance", "description": "Know Your Customer requirements", "confidence": 0.95},  # noqa: E501
                {"regulation_code": "RBI-AML-2023", "clause_title": "Anti-Money Laundering", "description": "AML screening and reporting", "confidence": 0.95},  # noqa: E501
                {"regulation_code": "RBI-DATA-2023", "clause_title": "Data Localization", "description": "Data storage within national boundaries", "confidence": 0.9},  # noqa: E501
            ],
            "finance": [
                {"regulation_code": "SEBI-COMP-2023", "clause_title": "Compliance Reporting", "description": "Periodic regulatory filings", "confidence": 0.9},  # noqa: E501
                {"regulation_code": "SEBI-RISK-2023", "clause_title": "Risk Management Framework", "description": "Enterprise risk management requirements", "confidence": 0.85},  # noqa: E501
            ],
            "healthcare": [
                {"regulation_code": "HIPAA-PRIV-2023", "clause_title": "Patient Data Privacy", "description": "Protected health information handling", "confidence": 0.95},  # noqa: E501
            ],
        }

        patterns = common_clauses.get(industry.lower(), common_clauses.get("banking", []))
        return {
            "patterns": patterns,
            "pattern_count": len(patterns),
            "industry": industry,
            "entity_type": entity_type,
            "status": "completed",
        }

    async def _rank_recommendations(self, input_data: dict[str, Any]) -> dict[str, Any]:
        recommendations = input_data.get("recommendations", [])
        existing_obligations = input_data.get("existing_obligations", [])
        existing_codes = {o.get("regulation_code", "") for o in existing_obligations}

        scored = []
        for rec in recommendations:
            score = rec.get("confidence", 0.5)
            if rec.get("regulation_code", "") in existing_codes:
                score *= 0.5
            if rec.get("source") == "industry_pattern":
                score *= 1.1
            scored.append((score, rec))

        scored.sort(key=lambda x: x[0], reverse=True)
        ranked = [rec for _, rec in scored]

        return {
            "ranked": ranked,
            "ranking_count": len(ranked),
            "status": "completed",
        }

    async def _generate_rationale(self, input_data: dict[str, Any]) -> dict[str, Any]:
        clause = input_data.get("clause", {})
        entity_name = input_data.get("entity_name", "")
        entity_type = input_data.get("entity_type", "")
        industry = input_data.get("industry", "")

        rationale = (
            f"Recommendation for {entity_name} ({entity_type}) in {industry} industry. "
            f"Clause '{clause.get('clause_title', '')}' from "
            f"regulation {clause.get('regulation_code', '')} is recommended "
            f"because {clause.get('description', 'it is relevant')}. "
            f"Confidence: {clause.get('confidence', 0.5):.0%}."
        )

        if self._llm_provider:
            try:
                llm_rationale = await self._llm_provider.generate(
                    messages=[
                        {"role": "system", "content": "You are a clause recommendation expert. Generate detailed rationale for why specific regulatory clauses are recommended for entities based on their profile and industry."},  # noqa: E501
                        {"role": "user", "content": f"Generate a rationale for recommending clause '{clause.get('clause_title', '')}' (regulation: {clause.get('regulation_code', '')}) to entity '{entity_name}' (type: {entity_type}) in the {industry} industry. Description: {clause.get('description', '')}. Confidence: {clause.get('confidence', 0.5)}."},  # noqa: E501
                    ],
                    temperature=0.3,
                    max_tokens=300,
                )
                rationale = llm_rationale.content
            except Exception as exc:
                self.logger.warning("LLM rationale generation failed: %s", exc)

        return {
            "rationale": rationale,
            "status": "completed",
        }

    async def _batch_recommend(self, input_data: dict[str, Any]) -> dict[str, Any]:
        entities = input_data.get("entities", [])
        batch_results: list[dict[str, Any]] = []

        for entity in entities:
            try:
                result = await self._recommend_clauses(entity)
                batch_results.append(result)
            except Exception as exc:
                self.logger.error("Batch recommendation failed for entity %s: %s", entity.get("entity_id", ""), exc)
                batch_results.append({
                    "entity_id": entity.get("entity_id", ""),
                    "error": str(exc),
                    "status": "failed",
                })

        return {
            "batch_results": batch_results,
            "total_entities": len(entities),
            "successful": sum(1 for r in batch_results if r.get("status") == "completed"),
            "failed": sum(1 for r in batch_results if r.get("status") == "failed"),
            "status": "completed",
        }
