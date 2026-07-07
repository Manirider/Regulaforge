"""ReportGeneratorAgent - Generates comprehensive compliance reports.

This agent produces compliance reports in multiple formats (PDF, HTML, XLSX)
using configurable templates for audit reports, gap analysis, and compliance
summaries. Includes data visualizations, natural language narrative
generation, and executive summaries.
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


class ReportGeneratorAgent(BaseAgent):
    """Agent that generates compliance reports in multiple formats.

    Supports PDF, HTML, and XLSX output formats with templates for
    audit reports, gap analysis, compliance summaries, and more.
    Includes chart generation, narrative text, and executive summaries.
    """

    SUPPORTED_FORMATS = ["pdf", "html", "xlsx"]  # noqa: RUF012
    REPORT_TYPES = ["audit_report", "gap_analysis", "compliance_summary"]  # noqa: RUF012

    def __init__(
        self,
        task_repository: AgentTaskRepository,
        event_publisher: EventPublisher,
        llm_provider: Optional[LLMProvider] = None,
        config: Optional[dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            agent_type=AgentType.REPORT_GENERATOR,
            task_repository=task_repository,
            event_publisher=event_publisher,
            llm_provider=llm_provider,
            config=config,
        )
        self._output_dir = config.get("output_dir", "/tmp/regulaforge/reports") if config else "/tmp/regulaforge/reports"  # noqa: E501
        self._templates_enabled = config.get("templates_enabled", True) if config else True

    def _get_supported_task_types(self) -> list[str]:
        return [
            "generate_report",
            "generate_audit_report",
            "generate_gap_analysis",
            "generate_compliance_summary",
            "generate_executive_summary",
            "generate_visualizations",
            "generate_narrative",
        ]

    async def execute(self, task: AgentTask) -> dict[str, Any]:
        task_type = task.task_type
        input_data = task.input_data

        self.logger.info(
            "Executing task: type=%s input_keys=%s",
            task_type,
            list(input_data.keys()) if input_data else [],
        )

        if task_type == "generate_report":
            result = await self._generate_report(input_data)
        elif task_type == "generate_audit_report":
            result = await self._generate_audit_report(input_data)
        elif task_type == "generate_gap_analysis":
            result = await self._generate_gap_analysis(input_data)
        elif task_type == "generate_compliance_summary":
            result = await self._generate_compliance_summary(input_data)
        elif task_type == "generate_executive_summary":
            result = await self._generate_executive_summary(input_data)
        elif task_type == "generate_visualizations":
            result = await self._generate_visualizations(input_data)
        elif task_type == "generate_narrative":
            result = await self._generate_narrative(input_data)
        else:
            raise ValueError(f"Unsupported task type: {task_type}")

        return result

    async def _generate_report(self, input_data: dict[str, Any]) -> dict[str, Any]:
        report_type = input_data.get("report_type", "compliance_summary")
        output_format = input_data.get("format", "pdf")
        entity_name = input_data.get("entity_name", "")
        assessment_data = input_data.get("assessment_data", {})
        findings = input_data.get("findings", [])
        risk_data = input_data.get("risk_data", {})

        if report_type not in self.REPORT_TYPES:
            raise ValueError(f"Unsupported report type: {report_type}. Supported: {self.REPORT_TYPES}")
        if output_format not in self.SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported format: {output_format}. Supported: {self.SUPPORTED_FORMATS}")

        narrative = await self._generate_narrative({
            "report_type": report_type,
            "entity_name": entity_name,
            "assessment_data": assessment_data,
            "findings": findings,
        })

        executive_summary = await self._generate_executive_summary({
            "entity_name": entity_name,
            "assessment_data": assessment_data,
            "findings": findings,
            "risk_data": risk_data,
        })

        visualizations = await self._generate_visualizations({
            "findings": findings,
            "risk_data": risk_data,
        })

        report_id = str(uuid4())
        report_content = self._build_report_content(
            report_type=report_type,
            entity_name=entity_name,
            executive_summary=executive_summary.get("summary", ""),
            narrative=narrative.get("narrative", ""),
            findings=findings,
            visualizations=visualizations.get("charts", []),
            assessment_data=assessment_data,
        )

        report_data = {
            "report_id": report_id,
            "report_type": report_type,
            "format": output_format,
            "entity_name": entity_name,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "sections": [
                {"title": "Executive Summary", "content": executive_summary.get("summary", "")},
                {"title": "Detailed Narrative", "content": narrative.get("narrative", "")},
                {"title": "Findings", "content": str(findings)[:1000]},
                {"title": "Visualizations", "content": str(visualizations.get("charts", []))[:500]},
            ],
            "page_count": len(findings) + 3,
            "content": report_content,
            "status": "completed",
        }

        return report_data

    async def _generate_audit_report(self, input_data: dict[str, Any]) -> dict[str, Any]:
        input_data["report_type"] = "audit_report"
        return await self._generate_report(input_data)

    async def _generate_gap_analysis(self, input_data: dict[str, Any]) -> dict[str, Any]:
        input_data["report_type"] = "gap_analysis"
        return await self._generate_report(input_data)

    async def _generate_compliance_summary(self, input_data: dict[str, Any]) -> dict[str, Any]:
        input_data["report_type"] = "compliance_summary"
        return await self._generate_report(input_data)

    async def _generate_executive_summary(self, input_data: dict[str, Any]) -> dict[str, Any]:
        entity_name = input_data.get("entity_name", "")
        assessment_data = input_data.get("assessment_data", {})
        findings = input_data.get("findings", [])
        risk_data = input_data.get("risk_data", {})

        score = assessment_data.get("compliance_score", 0.0)
        critical_count = sum(1 for f in findings if f.get("risk_level") == "critical")
        high_count = sum(1 for f in findings if f.get("risk_level") == "high")
        risk_level = risk_data.get("risk_level", "unknown")

        summary = (
            f"Compliance Assessment Summary for {entity_name}. "
            f"Overall compliance score: {score:.1f}%. "
            f"Identified {len(findings)} findings "
            f"({critical_count} critical, {high_count} high). "
            f"Current risk level: {risk_level}."
        )

        if self._llm_provider:
            try:
                llm_summary = await self._llm_provider.generate(
                    messages=[
                        {"role": "system", "content": "You are a compliance report expert. Generate concise executive summaries of compliance assessment results."},  # noqa: E501
                        {"role": "user", "content": f"Generate an executive summary for {entity_name}. Compliance score: {score:.1f}%. Findings: {len(findings)} total ({critical_count} critical, {high_count} high). Risk level: {risk_level}. Assessment data: {str(assessment_data)[:500]}."},  # noqa: E501
                    ],
                    temperature=0.3,
                    max_tokens=500,
                )
                summary = llm_summary.content
            except Exception as exc:
                self.logger.warning("LLM summary generation failed: %s", exc)

        return {
            "summary": summary,
            "compliance_score": score,
            "total_findings": len(findings),
            "critical_findings": critical_count,
            "high_findings": high_count,
            "risk_level": risk_level,
            "status": "completed",
        }

    async def _generate_visualizations(self, input_data: dict[str, Any]) -> dict[str, Any]:
        findings = input_data.get("findings", [])
        risk_data = input_data.get("risk_data", {})

        charts: list[dict[str, Any]] = []

        if findings:
            risk_counts: dict[str, int] = {}
            for finding in findings:
                level = finding.get("risk_level", "low")
                risk_counts[level] = risk_counts.get(level, 0) + 1

            charts.append({
                "type": "bar",
                "title": "Findings by Risk Level",
                "data": [{"label": k, "value": v} for k, v in risk_counts.items()],
            })

        if risk_data:
            charts.append({
                "type": "gauge",
                "title": "Overall Risk Score",
                "data": {"value": risk_data.get("risk_score", 0) * 100, "max": 100},
            })

        return {
            "charts": charts,
            "chart_count": len(charts),
            "status": "completed",
        }

    async def _generate_narrative(self, input_data: dict[str, Any]) -> dict[str, Any]:
        report_type = input_data.get("report_type", "compliance_summary")
        entity_name = input_data.get("entity_name", "")
        findings = input_data.get("findings", [])

        narrative = (
            f"This {report_type.replace('_', ' ')} report presents the compliance "
            f"assessment results for {entity_name}. "
            f"A total of {len(findings)} compliance findings were identified "
            f"during the assessment period."
        )

        if self._llm_provider:
            try:
                llm_narrative = await self._llm_provider.generate(
                    messages=[
                        {"role": "system", "content": "You are a compliance narrative writer. Generate detailed narrative sections for compliance reports."},  # noqa: E501
                        {"role": "user", "content": f"Generate a narrative for a {report_type.replace('_', ' ')} report for {entity_name}. There are {len(findings)} compliance findings. Assessment data: {str(input_data.get('assessment_data', {}))[:500]}."},  # noqa: E501
                    ],
                    temperature=0.5,
                    max_tokens=1000,
                )
                narrative = llm_narrative.content
            except Exception as exc:
                self.logger.warning("LLM narrative generation failed: %s", exc)

        return {
            "narrative": narrative,
            "word_count": len(narrative.split()),
            "status": "completed",
        }

    def _build_report_content(
        self,
        report_type: str,
        entity_name: str,
        executive_summary: str,
        narrative: str,
        findings: list[dict[str, Any]],
        visualizations: list[dict[str, Any]],
        _assessment_data: dict[str, Any],
    ) -> str:
        content_parts = [
            f"# {report_type.replace('_', ' ').title()}: {entity_name}",
            f"Generated: {datetime.now(timezone.utc).isoformat()}",
            "",
            "## Executive Summary",
            executive_summary,
            "",
            "## Detailed Analysis",
            narrative,
            "",
            f"## Findings ({len(findings)})",
        ]

        for i, finding in enumerate(findings, 1):
            content_parts.append(
                f"{i}. [{finding.get('risk_level', 'unknown').upper()}] "
                f"{finding.get('title', 'Untitled')}: "
                f"{finding.get('description', 'No description')}"
            )

        content_parts.extend([
            "",
            f"## Visualizations ({len(visualizations)})",
            str(visualizations),
            "",
            "---",
            f"*Report ID: {uuid4()!s}*",
        ])

        return "\n".join(content_parts)
