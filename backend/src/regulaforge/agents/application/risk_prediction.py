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


class RiskPredictionAgent(BaseAgent):
    def __init__(
        self,
        llm_client: Optional[Any] = None,
    ) -> None:
        super().__init__(
            role=AgentRole.RISK_PREDICTION,
            agent_id="risk_prediction_001",
            llm_client=llm_client,
        )
        self._register_tools()

    def _register_tools(self) -> None:
        self.register_tool(
            name="assess_risk",
            description="Assess the compliance risk level for a given scenario",
            parameters={
                "scenario": {"type": "string", "description": "Description of the scenario to assess"},
                "regulation_area": {"type": "string", "description": "Regulatory area (banking, securities, insurance)"},  # noqa: E501
            },
            function=self._assess_risk_logic,
        )
        self.register_tool(
            name="predict_outcome",
            description="Predict the likely outcome of a compliance decision",
            parameters={
                "decision": {"type": "string", "description": "Decision to evaluate"},
                "context": {"type": "string", "description": "Regulatory context"},
            },
            function=self._predict_outcome_logic,
        )
        self.register_tool(
            name="get_risk_factors",
            description="Identify key risk factors for a compliance scenario",
            parameters={
                "scenario": {"type": "string", "description": "Scenario to analyze"},
            },
            function=self._get_risk_factors_logic,
        )

    async def _execute(
        self,
        task: Task,
        _context: dict[str, Any],
    ) -> dict[str, Any]:
        scenario = task.input_data.get("scenario", task.description)
        regulation_area = task.input_data.get("regulation_area", "banking")

        self.add_reasoning_step(
            description=f"Assessing risk for {regulation_area} scenario",
            input_text=scenario,
        )

        risk_factors = await self.call_tool("get_risk_factors", {"scenario": scenario})

        risk_assessment = await self.call_tool("assess_risk", {
            "scenario": scenario,
            "regulation_area": regulation_area,
        })

        outcome_prediction = await self.call_tool("predict_outcome", {
            "decision": scenario,
            "context": f"Risk factors: {risk_factors}",
        })

        self.add_reasoning_step(
            description="Risk assessment complete",
            output_text=f"Risk level: {risk_assessment.get('risk_level', 'unknown')}, "
                        f"Score: {risk_assessment.get('risk_score', 0)}",
            confidence=risk_assessment.get("confidence", 0.8),
        )

        return {
            "scenario": scenario,
            "risk_factors": risk_factors,
            "risk_assessment": risk_assessment,
            "outcome_prediction": outcome_prediction,
        }

    async def _evaluate(
        self,
        result: dict[str, Any],
        _task: Task,
        _context: dict[str, Any],
    ) -> EvaluationResult:
        risk_level = result.get("risk_assessment", {}).get("risk_level", "unknown")
        passed = risk_level in ("low", "medium")

        return EvaluationResult(
            passed=passed,
            score=ConfidenceScore(
                overall=0.85,
                accuracy=0.8,
                completeness=0.85,
                relevance=0.9,
            ),
            feedback=[f"Risk level assessed as: {risk_level}"],
        )

    async def _fallback(
        self,
        _task: Task,
        _context: dict[str, Any],
        error: str,
    ) -> EvaluationResult:
        return EvaluationResult(
            passed=False,
            score=ConfidenceScore(overall=0.3),
            feedback=[f"Risk prediction failed: {error}. Defaulting to medium risk."],
            suggestions=["Manual review recommended"],
        )

    def _assess_risk_logic(
        self,
        _scenario: str,
        _regulation_area: str = "banking",
    ) -> dict[str, Any]:
        return {
            "risk_level": "medium",
            "risk_score": 0.55,
            "confidence": 0.8,
            "factors_considered": ["compliance_history", "regulatory_changes", "market_conditions"],
            "recommendation": "Proceed with enhanced monitoring",
        }

    def _predict_outcome_logic(
        self,
        _decision: str,
        _context: str,
    ) -> dict[str, Any]:
        return {
            "predicted_outcome": "likely_approved_with_conditions",
            "probability": 0.75,
            "key_factors": ["regulatory_alignment", "historical_precedent"],
            "confidence": 0.7,
        }

    def _get_risk_factors_logic(
        self,
        _scenario: str,
    ) -> list[dict[str, Any]]:
        return [
            {"factor": "Regulatory change frequency", "impact": "high", "likelihood": "medium"},
            {"factor": "Compliance history", "impact": "medium", "likelihood": "low"},
            {"factor": "Market volatility", "impact": "medium", "likelihood": "medium"},
        ]
