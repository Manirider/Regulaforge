from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status, Response

from regulaforge.common.exceptions import NotFoundError, ValidationError
from regulaforge.common.utils import create_response
from regulaforge.modules.agents.application.agent_service import AgentService
from regulaforge.modules.agents.domain.models import Agent

logger = logging.getLogger(__name__)


def create_agents_router(
    agent_service: Optional[AgentService] = None,
    dependencies: Optional[list[Any]] = None,
) -> APIRouter:
    router = APIRouter(
        prefix="/agents",
        tags=["Agents"],
        dependencies=dependencies or [],
    )

    @router.get("")
    async def list_agents(
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=1000),
        tenant_id: Optional[str] = None,
    ) -> dict[str, Any]:
        agents, total = await agent_service.list_agents(skip, limit, tenant_id)
        return create_response(data={
            "items": [{
                "id": a.id,
                "name": a.name,
                "agent_type": a.agent_type,
                "status": a.status.value,
                "capabilities": a.capabilities,
            } for a in agents],
            "total": total,
        })

    @router.post("", status_code=status.HTTP_201_CREATED)
    async def create_agent(body: Agent) -> dict[str, Any]:
        agent = await agent_service.create_agent(body)
        return create_response(data={"id": agent.id, "name": agent.name})

    @router.get("/{agent_id}")
    async def get_agent(agent_id: str) -> dict[str, Any]:
        try:
            agent = await agent_service.get_agent(agent_id)
            return create_response(data={
                "id": agent.id,
                "name": agent.name,
                "description": agent.description,
                "agent_type": agent.agent_type,
                "status": agent.status.value,
                "capabilities": agent.capabilities,
                "configuration": {
                    "model": agent.configuration.model,
                    "max_iterations": agent.configuration.max_iterations,
                    "timeout_seconds": agent.configuration.timeout_seconds,
                    "allow_delegation": agent.configuration.allow_delegation,
                },
                "created_at": agent.created_at.isoformat(),
            })
        except NotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    @router.put("/{agent_id}")
    async def update_agent(agent_id: str, body: dict[str, Any]) -> dict[str, Any]:
        try:
            agent = await agent_service.update_agent(agent_id, body)
            return create_response(data={"id": agent.id})
        except NotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    @router.delete("/{agent_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
    async def delete_agent(agent_id: str) -> Response:
        try:
            await agent_service.delete_agent(agent_id)
            return Response(status_code=status.HTTP_204_NO_CONTENT)
        except NotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    @router.post("/{agent_id}/execute")
    async def execute_agent(
        agent_id: str,
        task: str,
        input_data: dict[str, Any] = {},
        triggered_by: str = "",
    ) -> dict[str, Any]:
        try:
            execution = await agent_service.execute_agent(agent_id, task, input_data, triggered_by)
            return create_response(data={
                "execution_id": execution.id,
                "status": execution.status.value,
                "output": execution.output_data,
                "duration_ms": execution.duration_ms,
            })
        except (NotFoundError, ValidationError) as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND if isinstance(exc, NotFoundError) else status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            )

    @router.get("/{agent_id}/executions")
    async def list_executions(
        agent_id: str,
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=1000),
    ) -> dict[str, Any]:
        executions = await agent_service.list_executions(agent_id, skip, limit)
        return create_response(data=[{
            "id": e.id,
            "task": e.task,
            "status": e.status.value,
            "duration_ms": e.duration_ms,
            "error_message": e.error_message,
            "started_at": e.started_at.isoformat(),
            "completed_at": e.completed_at.isoformat() if e.completed_at else None,
        } for e in executions])

    return router
