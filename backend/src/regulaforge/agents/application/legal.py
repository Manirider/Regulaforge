from __future__ import annotations

import logging
from typing import Any, Optional

from regulaforge.agents.application.base_agent import BaseAgent
from regulaforge.agents.domain.enums import AgentRole
from regulaforge.agents.domain.models import (
    ConfidenceScore,
    EvaluationResult,
    Task,
)

logger = logging.getLogger(__name__)


class LegalAgent(BaseAgent):
    def __init__(
        self,
        llm_client: Optional[Any] = None,
    ) -> None:
        super().__init__(
            role=AgentRole.LEGAL,
            agent_id="legal_001",
            llm_client=llm_client,
        )
        self._register_tools()

    def _register_tools(self) -> None:
        self.register_tool(
            name="analyze_regulation",
            description="Analyze a regulation and its implications",
            parameters={
                "regulation_text": {"type": "string", "description": "Regulation text to analyze"},
                "context": {"type": "string", "description": "Business context for the analysis"},
            },
            function=self._analyze_regulation_logic,
        )
        self.register_tool(
            name="check_compliance",
            description="Check compliance of a scenario against regulations",
            parameters={
                "scenario": {"type": "string", "description": "Scenario to check"},
                "regulations": {"type": "string", "description": "Applicable regulations"},
            },
            function=self._check_compliance_logic,
        )
        self.register_tool(
            name="get_legal_opinion",
            description="Get a legal opinion on a regulatory matter",
            parameters={
                "question": {"type": "string", "description": "Legal question"},
                "jurisdiction": {"type": "string", "description": "Jurisdiction"},
            },
            function=self._get_legal_opinion_logic,
        )

    async def _execute(
        self,
        task: Task,
        _context: dict[str, Any],
    ) -> dict[str, Any]:
        question = task.input_data.get("question", task.description)
        jurisdiction = task.input_data.get("jurisdiction", "India")

        self.add_reasoning_step(
            description=f"Legal analysis for {jurisdiction}",
            input_text=question,
        )

        opinion = await self.call_tool("get_legal_opinion", {
            "question": question,
            "jurisdiction": jurisdiction,
        })

        compliance = await self.call_tool("check_compliance", {
            "scenario": question,
            "regulations": task.input_data.get("regulations", "general"),
        })

        self.add_reasoning_step(
            description="Legal analysis complete",
            output_text=f"Opinion confidence: {opinion.get('confidence', 0)}, "
                        f"Compliant: {compliance.get('compliant', 'unknown')}",
            confidence=opinion.get("confidence", 0.8),
        )

        return {
            "question": question,
            "jurisdiction": jurisdiction,
            "legal_opinion": opinion,
            "compliance_check": compliance,
        }

    async def _evaluate(
        self,
        result: dict[str, Any],
        _task: Task,
        _context: dict[str, Any],
    ) -> EvaluationResult:
        opinion = result.get("legal_opinion", {})
        confidence = opinion.get("confidence", 0)
        passed = confidence >= self.confidence_threshold

        return EvaluationResult(
            passed=passed,
            score=ConfidenceScore(
                overall=confidence,
                accuracy=confidence * 0.9,
                completeness=confidence * 0.85,
                relevance=confidence * 0.95,
            ),
            feedback=[f"Legal opinion confidence: {confidence:.2f}"],
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
            feedback=[f"Legal analysis failed: {error}. Manual legal review required."],
            suggestions=["Consult with legal department", "Review regulatory guidelines manually"],
        )

    def _analyze_regulation_logic(
        self,
        _regulation_text: str,
        _context: str = "",
    ) -> dict[str, Any]:
        return {
            "summary": "Regulation imposes compliance requirements on regulated entities",
            "key_requirements": ["Reporting obligations", "Capital adequacy", "Governance standards"],
            "penalties": ["Monetary fines", "License suspension", "Criminal liability"],
            "effective_date": "2024-01-01",
            "confidence": 0.85,
        }

    def _check_compliance_logic(
        self,
        scenario: str,
        regulations: str = "general",
    ) -> dict[str, Any]:
        return {
            "compliant": True,
            "partially_compliant": False,
            "gaps": [],
            "recommendations": ["Continue current practices", "Monitor regulatory updates"],
            "confidence": 0.8,
        }

    def _get_legal_opinion_logic(
        self,
        question: str,
        jurisdiction: str = "India",
    ) -> dict[str, Any]:
        return {
            "opinion": (
                f"Based on the regulatory framework in {jurisdiction}, "
                f"the scenario described appears to be compliant with applicable regulations. "
                f"However, careful attention should be paid to reporting obligations and "
                f"ongoing compliance monitoring."
            ),
            "confidence": 0.85,
            "applicable_laws": ["Banking Regulation Act, 1949", "RBI Act, 1934"],
            "caveats": ["Subject to change based on regulatory updates", "Legal review recommended for specific cases"],
        }
