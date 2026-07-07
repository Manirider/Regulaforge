from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional

from fastapi import APIRouter, Form, HTTPException

from regulaforge.agents.application.orchestrator import AgentOrchestrator
from regulaforge.agents.domain.enums import AgentRole, RoutingDecision, TaskPriority
from regulaforge.agents.domain.models import Task
from regulaforge.agents.langgraph import LangGraphOrchestrator

logger = logging.getLogger(__name__)


_orchestrator: Optional[AgentOrchestrator] = None
_langgraph_orchestrator: Optional[LangGraphOrchestrator] = None


def get_orchestrator() -> AgentOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = AgentOrchestrator()
    return _orchestrator


def get_langgraph_orchestrator() -> LangGraphOrchestrator:
    global _langgraph_orchestrator
    if _langgraph_orchestrator is None:
        _langgraph_orchestrator = LangGraphOrchestrator()
        _langgraph_orchestrator.compile()
    return _langgraph_orchestrator


def _build_task(
    title: str,
    description: str,
    priority: int,
    tags: str,
    input_data: str,
) -> Task:
    if not title or not title.strip():
        raise HTTPException(status_code=422, detail="title is required")
    if not description or not description.strip():
        raise HTTPException(status_code=422, detail="description is required")

    try:
        priority_enum = TaskPriority(priority)
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid priority '{priority}'. Must be 1 (LOW), 2 (MEDIUM), 3 (HIGH), or 4 (CRITICAL)",
        )

    parsed_tags: list[str] = []
    if tags:
        parsed_tags = [t.strip() for t in tags.split(",") if t.strip()]

    parsed_input: dict[str, Any] = {}
    if input_data:
        try:
            parsed_input = json.loads(input_data)
        except json.JSONDecodeError:
            raise HTTPException(status_code=422, detail="input_data must be valid JSON")

    return Task(
        title=title.strip(),
        description=description.strip(),
        priority=priority_enum,
        tags=parsed_tags,
        input_data=parsed_input,
    )


def _build_workflow_response(
    state: dict[str, Any],
    task: Task,
    start_time: float,
) -> dict[str, Any]:
    errors = state.get("errors", [])
    routing = state.get("routing_decision")
    return {
        "status": "completed" if not errors else "failed",
        "task_id": task.id,
        "routing": routing.value if isinstance(routing, RoutingDecision) else None,
        "agent_results": state.get("agent_results", {}),
        "errors": errors,
        "elapsed_seconds": round(time.time() - start_time, 2),
    }


def create_agents_router() -> APIRouter:
    router = APIRouter(prefix="/agents", tags=["agents"])

    @router.post("/workflow/langgraph")
    async def run_langgraph_workflow(
        title: str = Form(...),
        description: str = Form(...),
        priority: int = Form(TaskPriority.MEDIUM.value),
        tags: str = Form(""),
        input_data: str = Form("{}"),
        thread_id: str = Form("default"),
    ) -> dict[str, Any]:
        orch = get_langgraph_orchestrator()
        task = _build_task(title, description, priority, tags, input_data)
        start = time.time()

        state = await orch.run(task, thread_id=thread_id)

        return _build_workflow_response(state, task, start)

    @router.post("/workflow/langgraph/resume")
    async def resume_langgraph_workflow(
        thread_id: str = Form(...),
        approved: bool = Form(...),
        notes: str = Form(""),
    ) -> dict[str, Any]:
        if not thread_id or not thread_id.strip():
            raise HTTPException(status_code=422, detail="thread_id is required")

        orch = get_langgraph_orchestrator()
        decision = {"approved": approved, "notes": notes}
        result = orch.resolve_human_approval(thread_id, decision)
        return {"status": "resolved", "result": str(result)}

    @router.post("/workflow")
    async def run_workflow(
        title: str = Form(...),
        description: str = Form(...),
        priority: int = Form(TaskPriority.MEDIUM.value),
        tags: str = Form(""),
        input_data: str = Form("{}"),
    ) -> dict[str, Any]:
        orch = get_orchestrator()
        task = _build_task(title, description, priority, tags, input_data)
        start = time.time()

        state = await orch.run_workflow(task)

        return _build_workflow_response(state, task, start)

    @router.post("/workflow/direct")
    async def run_direct_agent(
        agent_role: str = Form(...),
        title: str = Form(...),
        description: str = Form(...),
        input_data: str = Form("{}"),
    ) -> dict[str, Any]:
        if not agent_role or not agent_role.strip():
            raise HTTPException(status_code=422, detail="agent_role is required")
        if not title or not title.strip():
            raise HTTPException(status_code=422, detail="title is required")
        if not description or not description.strip():
            raise HTTPException(status_code=422, detail="description is required")

        orch = get_orchestrator()
        try:
            role = AgentRole(agent_role.strip())
        except ValueError:
            valid = [r.value for r in AgentRole]
            raise HTTPException(
                status_code=400,
                detail=f"Invalid agent role '{agent_role}'. Valid: {valid}",
            )

        agent = orch.get_agent(role)
        parsed_input: dict[str, Any] = {}
        if input_data:
            try:
                parsed_input = json.loads(input_data)
            except json.JSONDecodeError:
                raise HTTPException(status_code=422, detail="input_data must be valid JSON")

        task = Task(
            title=title.strip(),
            description=description.strip(),
            input_data=parsed_input,
        )
        agent_state = await agent.run(task)

        return {
            "task_id": task.id,
            "status": agent_state.status.value,
            "evaluation": {
                "passed": agent_state.evaluation.passed if agent_state.evaluation else False,
                "confidence": {
                    "overall": agent_state.confidence.overall,
                } if agent_state.confidence else {},
                "feedback": agent_state.evaluation.feedback if agent_state.evaluation else [],
            },
            "reasoning_trace": [
                {"step": s.step_number, "description": s.description, "output": s.output}
                for s in agent_state.reasoning_trace
            ],
            "tool_calls": [
                {"tool": tc.tool_name, "result": tc.result, "error": tc.error}
                for tc in agent_state.tool_calls
            ],
            "fallback_used": agent_state.fallback_used,
        }

    @router.post("/approve")
    async def approve(
        request_id: str = Form(...),
        decision: str = Form(...),
        notes: Optional[str] = Form(None),
    ) -> dict[str, Any]:
        if not request_id or not request_id.strip():
            raise HTTPException(status_code=422, detail="request_id is required")
        if not decision or not decision.strip():
            raise HTTPException(status_code=422, detail="decision is required")

        orch = get_orchestrator()
        result = orch.resolve_human_approval(request_id.strip(), decision.strip(), notes)
        return {"status": "resolved", "result": result}

    @router.get("/agents")
    async def list_agents() -> dict[str, Any]:
        orch = get_orchestrator()
        agents = {}
        for role in AgentRole:
            agent = orch.get_agent(role)
            agents[role.value] = {
                "agent_id": agent.agent_id,
                "status": agent.state.status.value,
                "task_count": len(agent.state.memory.task_history),
                "reasoning_steps": len(agent.state.reasoning_trace),
                "tool_calls": len(agent.state.tool_calls),
            }
        return {"agents": agents}

    @router.post("/reset")
    async def reset_agents() -> dict[str, Any]:
        orch = get_orchestrator()
        orch.reset_all()
        return {"status": "success", "message": "All agents reset"}

    @router.get("/task/{task_id}")
    async def get_task_status(task_id: str) -> dict[str, Any]:
        if not task_id or not task_id.strip():
            raise HTTPException(status_code=422, detail="task_id is required")
        return {
            "task_id": task_id.strip(),
            "message": "Task status lookup available via workflow result",
        }

    @router.get("/langgraph/health")
    async def langgraph_health() -> dict[str, Any]:
        try:
            orch = get_langgraph_orchestrator()
            agent_count = len(orch._agents)
            return {
                "status": "healthy",
                "agents": agent_count,
                "compiled": orch._compiled is not None,
            }
        except Exception as exc:
            logger.error("LangGraph health check failed: %s", exc)
            return {
                "status": "unhealthy",
                "error": str(exc),
            }

    return router
