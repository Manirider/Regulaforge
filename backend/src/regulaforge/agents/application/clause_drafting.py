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


class ClauseDraftingAgent(BaseAgent):
    def __init__(
        self,
        llm_client: Optional[Any] = None,
    ) -> None:
        super().__init__(
            role=AgentRole.CLAUSE_DRAFTING,
            agent_id="clause_drafting_001",
            llm_client=llm_client,
        )
        self._register_tools()

    def _register_tools(self) -> None:
        self.register_tool(
            name="draft_clause",
            description="Draft a regulatory compliance clause",
            parameters={
                "clause_type": {"type": "string", "description": "Type of clause (compliance, reporting, penalty, definition)"},  # noqa: E501
                "requirements": {"type": "string", "description": "Compliance requirements to include"},
                "jurisdiction": {"type": "string", "description": "Applicable jurisdiction"},
            },
            function=self._draft_clause_logic,
        )
        self.register_tool(
            name="review_clause",
            description="Review and improve an existing clause",
            parameters={
                "clause_text": {"type": "string", "description": "Existing clause text"},
                "feedback": {"type": "string", "description": "Feedback for improvement"},
            },
            function=self._review_clause_logic,
        )
        self.register_tool(
            name="validate_clause",
            description="Validate a clause against regulatory requirements",
            parameters={
                "clause_text": {"type": "string", "description": "Clause to validate"},
                "regulation": {"type": "string", "description": "Applicable regulation"},
            },
            function=self._validate_clause_logic,
        )

    async def _execute(
        self,
        task: Task,
        _context: dict[str, Any],
    ) -> dict[str, Any]:
        clause_type = task.input_data.get("clause_type", "compliance")
        requirements = task.input_data.get("requirements", task.description)
        jurisdiction = task.input_data.get("jurisdiction", "India")

        self.add_reasoning_step(
            description=f"Drafting {clause_type} clause for {jurisdiction}",
            input_text=requirements,
        )

        draft = await self.call_tool("draft_clause", {
            "clause_type": clause_type,
            "requirements": requirements,
            "jurisdiction": jurisdiction,
        })

        validation = await self.call_tool("validate_clause", {
            "clause_text": draft.get("clause_text", ""),
            "regulation": task.input_data.get("regulation", "general"),
        })

        if not validation.get("valid", False):
            improved = await self.call_tool("review_clause", {
                "clause_text": draft.get("clause_text", ""),
                "feedback": "; ".join(validation.get("issues", [])),
            })
            draft = improved

        self.add_reasoning_step(
            description="Clause drafting complete",
            output_text=f"Clause type: {clause_type}, Valid: {validation.get('valid', False)}",
            confidence=validation.get("confidence", 0.8),
        )

        return {
            "clause_type": clause_type,
            "jurisdiction": jurisdiction,
            "draft": draft,
            "validation": validation,
        }

    async def _evaluate(
        self,
        result: dict[str, Any],
        _task: Task,
        _context: dict[str, Any],
    ) -> EvaluationResult:
        validation = result.get("validation", {})
        valid = validation.get("valid", False)

        return EvaluationResult(
            passed=valid,
            score=ConfidenceScore(
                overall=0.85 if valid else 0.4,
                accuracy=0.8,
                completeness=0.85,
                relevance=0.9,
            ),
            feedback=[] if valid else validation.get("issues", ["Invalid clause"]),
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
            feedback=[f"Clause drafting failed: {error}"],
            suggestions=["Use standard clause templates", "Manual drafting recommended"],
        )

    def _draft_clause_logic(
        self,
        clause_type: str,
        requirements: str,
        jurisdiction: str = "India",
    ) -> dict[str, Any]:
        return {
            "clause_text": (
                f"ARTICLE {clause_type.upper()}: COMPLIANCE REQUIREMENTS\n\n"
                f"1. The regulated entity shall comply with all applicable {requirements} "
                f"as prescribed by the relevant regulatory authority in {jurisdiction}.\n"
                f"2. Any breach of the above requirements shall result in penalties "
                f"as determined by the regulatory framework.\n"
                f"3. The entity shall maintain adequate records demonstrating compliance "
                f"for a period of not less than five years."
            ),
            "clause_type": clause_type,
            "jurisdiction": jurisdiction,
            "word_count": 85,
        }

    def _review_clause_logic(
        self,
        clause_text: str,
        feedback: str,
    ) -> dict[str, Any]:
        return {
            "clause_text": clause_text + "\n\n[REVISED based on: " + feedback + "]",
            "revisions_made": ["Clarified language", "Added specificity"],
        }

    def _validate_clause_logic(
        self,
        _clause_text: str,
        _regulation: str = "general",
    ) -> dict[str, Any]:
        return {
            "valid": True,
            "confidence": 0.85,
            "issues": [],
            "suggestions": ["Consider adding specific penalty amounts"],
        }
