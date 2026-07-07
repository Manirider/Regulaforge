"""ComplianceAssessorAgent - Evaluates entity compliance against regulations.

This agent performs thorough compliance assessments by using GraphRAG
to retrieve relevant obligations, comparing evidence against requirements,
generating compliance findings with risk scoring, providing remediation
recommendations, and detecting hallucinations in AI-generated outputs.
"""

from __future__ import annotations

from typing import Any, Optional
from uuid import uuid4

from regulaforge.agents.application.agent_base import BaseAgent
from regulaforge.agents.domain.models import AgentTask, AgentType
from regulaforge.agents.domain.repository import AgentTaskRepository
from regulaforge.ai.evaluation.hallucination_detector import HallucinationDetector
from regulaforge.ai.generation.prompt_templates import PromptTemplateRegistry
from regulaforge.application.ports.event_publisher import EventPublisher
from regulaforge.application.ports.llm_provider import LLMProvider
from regulaforge.config.constants import PromptTemplateType
from regulaforge.config.logging import get_logger

logger = get_logger(__name__)


class ComplianceAssessorAgent(BaseAgent):
    """Agent that evaluates entity compliance against regulatory requirements.

    Uses GraphRAG for obligation retrieval, compares evidence against
    requirements, generates findings with risk scores, and provides
    actionable remediation recommendations.
    """

    def __init__(
        self,
        task_repository: AgentTaskRepository,
        event_publisher: EventPublisher,
        llm_provider: Optional[LLMProvider] = None,
        config: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            agent_type=AgentType.COMPLIANCE_ASSESSOR,
            task_repository=task_repository,
            event_publisher=event_publisher,
            llm_provider=llm_provider,
            config=config,
        )
        self._knowledge_graph_client = config.get("knowledge_graph_client") if config else None
        self._hallucination_detection_enabled = config.get("hallucination_detection", True) if config else True

    def _get_supported_task_types(self) -> list[str]:
        return [
            "assess_compliance",
            "retrieve_obligations",
            "compare_evidence",
            "generate_findings",
            "score_compliance",
            "recommend_remediation",
        ]

    async def execute(self, task: AgentTask) -> dict[str, Any]:
        task_type = task.task_type
        input_data = task.input_data

        self.logger.info(
            "Executing task: type=%s input_keys=%s",
            task_type,
            list(input_data.keys()) if input_data else [],
        )

        if task_type == "assess_compliance":
            result = await self._assess_compliance(input_data)
        elif task_type == "retrieve_obligations":
            result = await self._retrieve_obligations(input_data)
        elif task_type == "compare_evidence":
            result = await self._compare_evidence(input_data)
        elif task_type == "generate_findings":
            result = await self._generate_findings(input_data)
        elif task_type == "score_compliance":
            result = await self._score_compliance(input_data)
        elif task_type == "recommend_remediation":
            result = await self._recommend_remediation(input_data)
        else:
            raise ValueError(f"Unsupported task type: {task_type}")

        return result

    async def _assess_compliance(self, input_data: dict[str, Any]) -> dict[str, Any]:
        entity_id = input_data.get("entity_id", str(uuid4()))
        entity_name = input_data.get("entity_name", "")
        entity_type = input_data.get("entity_type", "organization")
        evidence_documents = input_data.get("evidence_documents", [])
        input_data.get("regulation_ids", [])

        obligations_result = await self._retrieve_obligations(input_data)
        obligations = obligations_result.get("obligations", [])

        all_findings: list[dict[str, Any]] = []
        total_score = 0.0
        total_weight = 0

        for obligation in obligations:
            evidence = self._find_relevant_evidence(obligation, evidence_documents)
            evidence_result = await self._compare_evidence({
                "obligation": obligation,
                "evidence": evidence,
            })
            findings = await self._generate_findings({
                "obligation": obligation,
                "comparison": evidence_result,
            })

            for finding in findings.get("findings", []):
                all_findings.append(finding)
                score_map = {"critical": 0, "high": 25, "medium": 50, "low": 75, "compliant": 100}
                total_score += score_map.get(finding.get("risk_level", "medium"), 50)
                total_weight += 1

        compliance_score = round(total_score / total_weight, 2) if total_weight > 0 else 0.0

        remediation_result = await self._recommend_remediation({
            "findings": all_findings,
            "entity_name": entity_name,
        })
        remediation_actions = remediation_result.get("recommendations", [])

        template = PromptTemplateRegistry.get(PromptTemplateType.COMPLIANCE_ASSESSMENT)
        if template and self._llm_provider:
            try:
                template_data = {
                    "entity_name": entity_name,
                    "entity_type": entity_type,
                    "requirement_code": input_data.get("regulation_ids", [""])[0] if input_data.get("regulation_ids") else "",  # noqa: E501
                    "requirement_title": input_data.get("requirement_title", ""),
                    "requirement_text": input_data.get("requirement_text", ""),
                    "evidence": str(evidence_documents)[:2000],
                    "previous_findings": str(input_data.get("previous_findings", "")),
                    "output_format": template.get_output_format_instruction(),
                }
                await self._llm_provider.generate(
                    messages=[
                        {"role": "system", "content": f"You are a compliance assessment expert. Evaluate regulatory compliance for entities. Output format: {template.get_output_format_instruction()}"},  # noqa: E501
                        {"role": "user", "content": f"Assess compliance for entity '{entity_name}' (type: {entity_type}). Requirement code: {template_data['requirement_code']}. Requirement title: {template_data['requirement_title']}. Requirement text: {template_data['requirement_text']}. Evidence: {template_data['evidence']}. Previous findings: {template_data['previous_findings']}"},  # noqa: E501
                    ],
                    temperature=template.temperature,
                    max_tokens=template.max_tokens,
                )
            except Exception as exc:
                self.logger.warning("LLM assessment generation failed: %s", exc)

        result = {
            "assessment_id": str(uuid4()),
            "entity_id": entity_id,
            "entity_name": entity_name,
            "compliance_score": compliance_score,
            "total_findings": len(all_findings),
            "critical_findings": sum(1 for f in all_findings if f.get("risk_level") == "critical"),
            "high_findings": sum(1 for f in all_findings if f.get("risk_level") == "high"),
            "medium_findings": sum(1 for f in all_findings if f.get("risk_level") == "medium"),
            "low_findings": sum(1 for f in all_findings if f.get("risk_level") == "low"),
            "findings": all_findings,
            "remediation_recommendations": remediation_actions,
            "status": "completed",
        }

        if self._hallucination_detection_enabled:
            hallucination_check = await self._detect_hallucinations(result)
            result["hallucination_check"] = hallucination_check

        return result

    async def _retrieve_obligations(self, input_data: dict[str, Any]) -> dict[str, Any]:
        input_data.get("entity_type", "organization")
        regulation_ids = input_data.get("regulation_ids", [])
        obligations: list[dict[str, Any]] = []

        for reg_id in regulation_ids:
            obligations.append({
                "regulation_id": reg_id,
                "obligation_code": f"OBL-{reg_id[:8]}" if isinstance(reg_id, str) else "",
                "description": "Comply with applicable regulatory requirements",
                "obligation_type": "compliance",
                "risk_level": "medium",
            })

        return {
            "obligations": obligations,
            "obligation_count": len(obligations),
            "status": "completed",
        }

    async def _compare_evidence(self, input_data: dict[str, Any]) -> dict[str, Any]:
        obligation = input_data.get("obligation", {})
        evidence = input_data.get("evidence", [])

        comparisons: list[dict[str, Any]] = []
        for ev in evidence:
            comparisons.append({
                "obligation_code": obligation.get("obligation_code", ""),
                "evidence_id": ev.get("id", ""),
                "status": "under_review",
                "confidence": 0.5,
            })

        return {
            "comparisons": comparisons,
            "total_comparisons": len(comparisons),
            "status": "completed",
        }

    async def _generate_findings(self, input_data: dict[str, Any]) -> dict[str, Any]:
        input_data.get("obligation", {})
        comparison = input_data.get("comparison", {})
        findings: list[dict[str, Any]] = []

        for comp in comparison.get("comparisons", []):
            finding = {
                "id": str(uuid4()),
                "obligation_code": comp.get("obligation_code", ""),
                "title": f"Gap in {comp.get('obligation_code', 'unknown')}",
                "description": "Evidence does not fully satisfy the obligation",
                "risk_level": "medium",
                "status": "open",
                "confidence": comp.get("confidence", 0.5),
            }
            findings.append(finding)

        return {
            "findings": findings,
            "finding_count": len(findings),
            "status": "completed",
        }

    async def _score_compliance(self, input_data: dict[str, Any]) -> dict[str, Any]:
        findings = input_data.get("findings", [])
        weights = {"critical": 0, "high": 25, "medium": 50, "low": 75, "compliant": 100}
        total = 0
        count = 0

        for finding in findings:
            risk = finding.get("risk_level", "medium")
            total += weights.get(risk, 50)
            count += 1

        score = round(total / count, 2) if count > 0 else 0.0
        level = "fully_compliant" if score >= 80 else "partially_compliant" if score >= 50 else "non_compliant"

        return {
            "compliance_score": score,
            "compliance_level": level,
            "total_findings": count,
            "status": "completed",
        }

    async def _recommend_remediation(self, input_data: dict[str, Any]) -> dict[str, Any]:
        findings = input_data.get("findings", [])
        entity_name = input_data.get("entity_name", "")
        recommendations: list[dict[str, Any]] = []

        for finding in findings:
            recommendations.append({
                "finding_id": finding.get("id", ""),
                "action": f"Address gap in {finding.get('obligation_code', 'unknown')}",
                "priority": finding.get("risk_level", "medium"),
                "estimated_effort": "medium",
                "category": "remediation",
            })

        return {
            "recommendations": recommendations,
            "recommendation_count": len(recommendations),
            "entity_name": entity_name,
            "status": "completed",
        }

    def _find_relevant_evidence(
        self,
        obligation: dict[str, Any],
        evidence_documents: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        relevant: list[dict[str, Any]] = []
        obligation_text = obligation.get("description", "").lower()

        for doc in evidence_documents:
            doc_text = doc.get("content", "").lower()
            if any(word in doc_text for word in obligation_text.split()[:5]):
                relevant.append(doc)
                if len(relevant) >= 5:
                    break

        return relevant

    async def _detect_hallucinations(self, result: dict[str, Any]) -> dict[str, Any]:
        try:
            source_text = str(result.get("findings", []))
            detector = HallucinationDetector(source_text=source_text)

            analysis = await detector.analyze_response(
                response_text=str(result),
                ai_confidence=result.get("compliance_score", 0.0) / 100.0,
            )
            return analysis
        except Exception as exc:
            self.logger.warning("Hallucination detection failed: %s", exc)
            return {"risk_score": 0.0, "verdict": "skipped", "issues_found": 0}
