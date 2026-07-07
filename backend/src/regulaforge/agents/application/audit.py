from __future__ import annotations

import logging
import time
from typing import Any, Optional

from regulaforge.agents.application.base_agent import BaseAgent
from regulaforge.agents.domain.enums import AgentRole
from regulaforge.agents.domain.models import (
    ConfidenceScore,
    EvaluationResult,
    Task,
)

logger = logging.getLogger(__name__)


class AuditAgent(BaseAgent):
    def __init__(
        self,
        llm_client: Optional[Any] = None,
    ) -> None:
        super().__init__(
            role=AgentRole.AUDIT,
            agent_id="audit_001",
            llm_client=llm_client,
        )
        self._register_tools()

    def _register_tools(self) -> None:
        self.register_tool(
            name="conduct_audit",
            description="Conduct a compliance audit on a given area",
            parameters={
                "audit_area": {"type": "string", "description": "Area to audit"},
                "scope": {"type": "string", "description": "Audit scope"},
                "criteria": {"type": "string", "description": "Audit criteria and standards"},
            },
            function=self._conduct_audit_logic,
        )
        self.register_tool(
            name="generate_findings",
            description="Generate audit findings from audit data",
            parameters={
                "audit_data": {"type": "string", "description": "Raw audit data"},
                "threshold": {"type": "number", "description": "Materiality threshold"},
            },
            function=self._generate_findings_logic,
        )
        self.register_tool(
            name="recommend_actions",
            description="Recommend corrective actions for audit findings",
            parameters={
                "findings": {"type": "string", "description": "List of audit findings"},
                "priority": {"type": "string", "description": "Priority level"},
            },
            function=self._recommend_actions_logic,
        )

    async def _execute(
        self,
        task: Task,
        _context: dict[str, Any],
    ) -> dict[str, Any]:
        audit_area = task.input_data.get("audit_area", "compliance")
        scope = task.input_data.get("scope", "full")
        criteria = task.input_data.get("criteria", "regulatory_standards")

        self.add_reasoning_step(
            description=f"Conducting {audit_area} audit (scope: {scope})",
            input_text=task.description,
        )

        audit_result = await self.call_tool("conduct_audit", {
            "audit_area": audit_area,
            "scope": scope,
            "criteria": criteria,
        })

        findings = await self.call_tool("generate_findings", {
            "audit_data": str(audit_result),
            "threshold": task.input_data.get("threshold", 0.5),
        })

        if findings.get("critical_count", 0) > 0:
            recommendations = await self.call_tool("recommend_actions", {
                "findings": str(findings),
                "priority": "high",
            })
        else:
            recommendations = {"message": "No critical findings", "actions": []}

        self.add_reasoning_step(
            description="Audit complete",
            output_text=f"Findings: {findings.get('total', 0)} total, "
                        f"{findings.get('critical_count', 0)} critical",
            confidence=audit_result.get("confidence", 0.85),
        )

        return {
            "audit_area": audit_area,
            "audit_result": audit_result,
            "findings": findings,
            "recommendations": recommendations,
        }

    async def _evaluate(
        self,
        result: dict[str, Any],
        _task: Task,
        _context: dict[str, Any],
    ) -> EvaluationResult:
        findings = result.get("findings", {})
        critical = findings.get("critical_count", 0)

        return EvaluationResult(
            passed=critical == 0,
            score=ConfidenceScore(
                overall=0.9,
                accuracy=0.85,
                completeness=0.9,
                relevance=0.95,
            ),
            feedback=[f"Found {critical} critical findings"] if critical else ["No critical issues found"],
        )

    async def _fallback(
        self,
        _task: Task,
        _context: dict[str, Any],
        error: str,
    ) -> EvaluationResult:
        return EvaluationResult(
            passed=False,
            score=ConfidenceScore(overall=0.2),
            feedback=[f"Audit failed: {error}"],
            suggestions=["Perform manual audit", "Check system logs for errors"],
        )

    def _conduct_audit_logic(
        self,
        audit_area: str,
        scope: str = "full",
        _criteria: str = "regulatory_standards",
    ) -> dict[str, Any]:
        return {
            "audit_area": audit_area,
            "scope": scope,
            "status": "completed",
            "items_reviewed": 50,
            "confidence": 0.9,
            "timestamp": time.time(),
        }

    def _generate_findings_logic(
        self,
        _audit_data: str,
        _threshold: float = 0.5,
    ) -> dict[str, Any]:
        return {
            "total": 3,
            "critical_count": 0,
            "major_count": 1,
            "minor_count": 2,
            "findings": [
                {"severity": "major", "description": "Documentation gap in reporting process", "area": "reporting"},
                {"severity": "minor", "description": "Missing signature on compliance form", "area": "documentation"},
                {"severity": "minor", "description": "Delayed filing by 2 days", "area": "timeliness"},
            ],
        }

    def _recommend_actions_logic(
        self,
        _findings: str,
        priority: str = "medium",
    ) -> dict[str, Any]:
        return {
            "actions": [
                {"action": "Update reporting process documentation", "deadline": "30 days", "owner": "compliance_team"},
                {"action": "Implement digital signature workflow", "deadline": "60 days", "owner": "IT_team"},
                {"action": "Set up automated filing reminders", "deadline": "15 days", "owner": "operations_team"},
            ],
            "priority": priority,
            "tracking_required": True,
        }
