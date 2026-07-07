"""Pre-defined workflow definitions for the Multi-Agent AI System.

These workflows chain together multiple agent executions with
input/output data passing, timeouts, and retry policies for
common compliance automation scenarios.
"""

from typing import Any

from regulaforge.agents.domain.models import AgentType, WorkflowDefinition, WorkflowStep


def _step(
    order: int,
    agent_type: AgentType,
    task_type: str,
    input_mapping: dict[str, str] | None = None,
    output_mapping: dict[str, str] | None = None,
    timeout_seconds: int = 300,
    retry_count: int = 3,
    on_failure: str = "abort",
) -> WorkflowStep:
    """Create a workflow step with sensible defaults.

    Args:
        order: Step execution order (0-indexed).
        agent_type: The agent type to execute this step.
        task_type: The type of task to run.
        input_mapping: Maps step input keys from accumulated data keys.
        output_mapping: Maps result keys to accumulated data keys.
        timeout_seconds: Maximum step execution time.
        retry_count: Number of retries on failure.
        on_failure: Failure behavior ('abort', 'skip', or 'retry').

    Returns:
        A configured WorkflowStep instance.
    """
    return WorkflowStep(
        order=order,
        agent_type=agent_type,
        task_type=task_type,
        input_mapping=input_mapping or {},
        output_mapping=output_mapping or {},
        timeout_seconds=timeout_seconds,
        retry_count=retry_count,
        on_failure=on_failure,
    )


# ---------------------------------------------------------------------------
# FULL_COMPLIANCE_ASSESSMENT
# Documents -> Compliance Check -> Risk Scoring -> Report
# ---------------------------------------------------------------------------

FULL_COMPLIANCE_ASSESSMENT = WorkflowDefinition(
    name="full_compliance_assessment",
    description=(
        "End-to-end compliance assessment: processes documents, evaluates "
        "compliance against regulations, assesses risk levels, and generates "
        "a comprehensive compliance report."
    ),
    steps=[
        _step(
            order=0,
            agent_type=AgentType.DOCUMENT_INTELLIGENCE,
            task_type="process_document",
            input_mapping={"file_path": "file_path", "content": "document_content"},
            output_mapping={"entities": "extracted_entities", "obligations": "extracted_obligations"},
            timeout_seconds=600,
            retry_count=2,
        ),
        _step(
            order=1,
            agent_type=AgentType.COMPLIANCE_ASSESSOR,
            task_type="assess_compliance",
            input_mapping={
                "entity_id": "entity_id",
                "entity_name": "entity_name",
                "entity_type": "entity_type",
                "evidence_documents": "extracted_entities",
                "regulation_ids": "regulation_ids",
            },
            output_mapping={"findings": "compliance_findings", "compliance_score": "compliance_score"},
            timeout_seconds=600,
            retry_count=2,
        ),
        _step(
            order=2,
            agent_type=AgentType.RISK_ASSESSOR,
            task_type="assess_risk",
            input_mapping={
                "entity_id": "entity_id",
                "entity_type": "entity_type",
                "findings": "compliance_findings",
            },
            output_mapping={"risk_score": "risk_score", "risk_level": "risk_level"},
            timeout_seconds=300,
            retry_count=2,
        ),
        _step(
            order=3,
            agent_type=AgentType.REPORT_GENERATOR,
            task_type="generate_report",
            input_mapping={
                "report_type": "report_type",
                "entity_name": "entity_name",
                "findings": "compliance_findings",
                "risk_data": "risk_score",
                "assessment_data": "compliance_score",
            },
            output_mapping={"report_id": "report_id"},
            timeout_seconds=300,
            retry_count=1,
        ),
    ],
    timeout_seconds=3600,
    retry_policy={"max_retries": 3, "backoff_factor": 2.0},
)


# ---------------------------------------------------------------------------
# REGULATION_IMPACT_ANALYSIS
# New Regulation -> Graph Impact -> Compliance Check -> Report
# ---------------------------------------------------------------------------

REGULATION_IMPACT_ANALYSIS = WorkflowDefinition(
    name="regulation_impact_analysis",
    description=(
        "Analyzes the impact of new or amended regulations: monitors "
        "regulatory updates, explores the knowledge graph for affected "
        "entities, assesses compliance impact, and generates an impact report."
    ),
    steps=[
        _step(
            order=0,
            agent_type=AgentType.REGULATION_MONITOR,
            task_type="poll_regulations",
            input_mapping={"source": "regulatory_source"},
            output_mapping={"new_regulations": "regulation_updates"},
            timeout_seconds=300,
            retry_count=2,
        ),
        _step(
            order=1,
            agent_type=AgentType.GRAPH_EXPLORER,
            task_type="explore_impact",
            input_mapping={"regulations": "regulation_updates"},
            output_mapping={"affected_entities": "impacted_entities"},
            timeout_seconds=300,
            retry_count=2,
        ),
        _step(
            order=2,
            agent_type=AgentType.COMPLIANCE_ASSESSOR,
            task_type="assess_compliance",
            input_mapping={
                "entity_id": "entity_id",
                "entity_name": "entity_name",
                "entity_type": "entity_type",
                "regulation_ids": "regulation_updates",
            },
            output_mapping={"findings": "impact_findings"},
            timeout_seconds=600,
            retry_count=2,
        ),
        _step(
            order=3,
            agent_type=AgentType.REPORT_GENERATOR,
            task_type="generate_report",
            input_mapping={
                "report_type": "impact_analysis",
                "entity_name": "entity_name",
                "findings": "impact_findings",
                "assessment_data": "regulation_updates",
            },
            output_mapping={"report_id": "impact_report_id"},
            timeout_seconds=300,
            retry_count=1,
        ),
    ],
    timeout_seconds=3600,
    retry_policy={"max_retries": 3, "backoff_factor": 2.0},
)


# ---------------------------------------------------------------------------
# CONTINUOUS_MONITORING_CYCLE
# Monitor -> Assess -> Risk -> Report (looping cycle)
# ---------------------------------------------------------------------------

CONTINUOUS_MONITORING_CYCLE = WorkflowDefinition(
    name="continuous_monitoring_cycle",
    description=(
        "Continuous compliance monitoring cycle: polls for regulatory changes, "
        "assesses impact on entities, evaluates risk, and generates periodic "
        "monitoring reports. Designed for scheduled recurring execution."
    ),
    steps=[
        _step(
            order=0,
            agent_type=AgentType.REGULATION_MONITOR,
            task_type="monitor_regulatory_feeds",
            input_mapping={"sources": "monitoring_sources"},
            output_mapping={"results": "monitoring_results"},
            timeout_seconds=300,
            retry_count=2,
        ),
        _step(
            order=1,
            agent_type=AgentType.COMPLIANCE_ASSESSOR,
            task_type="assess_compliance",
            input_mapping={
                "entity_id": "entity_id",
                "entity_name": "entity_name",
                "entity_type": "entity_type",
                "evidence_documents": "monitoring_results",
                "regulation_ids": "regulation_ids",
            },
            output_mapping={"findings": "monitoring_findings"},
            timeout_seconds=600,
            retry_count=2,
        ),
        _step(
            order=2,
            agent_type=AgentType.RISK_ASSESSOR,
            task_type="assess_risk",
            input_mapping={
                "entity_id": "entity_id",
                "findings": "monitoring_findings",
                "regulatory_changes": "monitoring_results",
            },
            output_mapping={"risk_score": "monitoring_risk", "risk_level": "monitoring_risk_level"},
            timeout_seconds=300,
            retry_count=2,
        ),
        _step(
            order=3,
            agent_type=AgentType.REPORT_GENERATOR,
            task_type="generate_compliance_summary",
            input_mapping={
                "entity_name": "entity_name",
                "findings": "monitoring_findings",
                "risk_data": "monitoring_risk",
            },
            output_mapping={"report_id": "monitoring_report_id"},
            timeout_seconds=300,
            retry_count=1,
        ),
    ],
    timeout_seconds=3600,
    retry_policy={"max_retries": 3, "backoff_factor": 2.0},
)


# ---------------------------------------------------------------------------
# AUDIT_PREPARATION
# Document Intel -> Compliance Assessment -> Report
# ---------------------------------------------------------------------------

AUDIT_PREPARATION = WorkflowDefinition(
    name="audit_preparation",
    description=(
        "Prepares for regulatory audits by processing evidence documents, "
        "assessing compliance against applicable regulations, and generating "
        "a comprehensive audit readiness report."
    ),
    steps=[
        _step(
            order=0,
            agent_type=AgentType.DOCUMENT_INTELLIGENCE,
            task_type="process_document",
            input_mapping={
                "file_path": "file_path",
                "content": "document_content",
                "document_id": "document_id",
            },
            output_mapping={"entities": "audit_entities", "obligations": "audit_obligations"},
            timeout_seconds=600,
            retry_count=2,
        ),
        _step(
            order=1,
            agent_type=AgentType.COMPLIANCE_ASSESSOR,
            task_type="assess_compliance",
            input_mapping={
                "entity_id": "entity_id",
                "entity_name": "entity_name",
                "entity_type": "entity_type",
                "evidence_documents": "audit_entities",
                "regulation_ids": "regulation_ids",
            },
            output_mapping={"findings": "audit_findings", "compliance_score": "audit_score"},
            timeout_seconds=600,
            retry_count=2,
        ),
        _step(
            order=2,
            agent_type=AgentType.REPORT_GENERATOR,
            task_type="generate_audit_report",
            input_mapping={
                "entity_name": "entity_name",
                "findings": "audit_findings",
                "assessment_data": "audit_score",
            },
            output_mapping={"report_id": "audit_report_id"},
            timeout_seconds=300,
            retry_count=1,
        ),
    ],
    timeout_seconds=3600,
    retry_policy={"max_retries": 3, "backoff_factor": 2.0},
)


# ---------------------------------------------------------------------------
# GAP_ANALYSIS
# Compliance Assessment -> Risk Scoring -> Clause Recommendations -> Report
# ---------------------------------------------------------------------------

GAP_ANALYSIS = WorkflowDefinition(
    name="gap_analysis",
    description=(
        "Identifies and analyzes compliance gaps: assesses current compliance "
        "posture, evaluates risk levels, recommends regulatory clauses to "
        "address gaps, and generates a detailed gap analysis report."
    ),
    steps=[
        _step(
            order=0,
            agent_type=AgentType.COMPLIANCE_ASSESSOR,
            task_type="assess_compliance",
            input_mapping={
                "entity_id": "entity_id",
                "entity_name": "entity_name",
                "entity_type": "entity_type",
                "evidence_documents": "evidence_documents",
                "regulation_ids": "regulation_ids",
            },
            output_mapping={"findings": "gap_findings", "compliance_score": "gap_score"},
            timeout_seconds=600,
            retry_count=2,
        ),
        _step(
            order=1,
            agent_type=AgentType.RISK_ASSESSOR,
            task_type="assess_risk",
            input_mapping={
                "entity_id": "entity_id",
                "entity_type": "entity_type",
                "findings": "gap_findings",
            },
            output_mapping={
                "risk_score": "gap_risk_score",
                "risk_level": "gap_risk_level",
                "risk_factors": "gap_risk_factors",
            },
            timeout_seconds=300,
            retry_count=2,
        ),
        _step(
            order=2,
            agent_type=AgentType.CLAUSE_RECOMMENDER,
            task_type="recommend_clauses",
            input_mapping={
                "entity_id": "entity_id",
                "entity_name": "entity_name",
                "entity_type": "entity_type",
                "industry": "industry",
                "existing_obligations": "gap_findings",
            },
            output_mapping={"recommendations": "clause_recommendations"},
            timeout_seconds=300,
            retry_count=2,
        ),
        _step(
            order=3,
            agent_type=AgentType.REPORT_GENERATOR,
            task_type="generate_gap_analysis",
            input_mapping={
                "entity_name": "entity_name",
                "findings": "gap_findings",
                "risk_data": "gap_risk_score",
                "assessment_data": "gap_score",
            },
            output_mapping={"report_id": "gap_report_id"},
            timeout_seconds=300,
            retry_count=1,
        ),
    ],
    timeout_seconds=3600,
    retry_policy={"max_retries": 3, "backoff_factor": 2.0},
)


# ---------------------------------------------------------------------------
# Workflow Registry
# ---------------------------------------------------------------------------

WORKFLOW_REGISTRY: dict[str, WorkflowDefinition] = {
    "full_compliance_assessment": FULL_COMPLIANCE_ASSESSMENT,
    "regulation_impact_analysis": REGULATION_IMPACT_ANALYSIS,
    "continuous_monitoring_cycle": CONTINUOUS_MONITORING_CYCLE,
    "audit_preparation": AUDIT_PREPARATION,
    "gap_analysis": GAP_ANALYSIS,
}


def get_workflow(name: str) -> WorkflowDefinition | None:
    """Get a workflow definition by name.

    Args:
        name: The workflow name (key in WORKFLOW_REGISTRY).

    Returns:
        The matching WorkflowDefinition, or None if not found.
    """
    return WORKFLOW_REGISTRY.get(name)


def list_workflows() -> list[dict[str, Any]]:
    """List all registered workflow definitions.

    Returns:
        A list of workflow summary dictionaries.
    """
    return [
        {
            "name": wf.name,
            "description": wf.description,
            "step_count": len(wf.steps),
            "timeout_seconds": wf.timeout_seconds,
            "steps": [
                {
                    "order": s.order,
                    "agent_type": s.agent_type.value,
                    "task_type": s.task_type,
                }
                for s in wf.steps
            ],
        }
        for wf in WORKFLOW_REGISTRY.values()
    ]
