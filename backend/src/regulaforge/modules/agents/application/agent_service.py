from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Optional

from regulaforge.common.exceptions import NotFoundError, ValidationError
from regulaforge.modules.agents.domain.models import Agent, AgentExecution, AgentStatus
from regulaforge.modules.agents.domain.repository import AgentExecutionRepository, AgentRepository

logger = logging.getLogger(__name__)


class AgentService:
    def __init__(
        self,
        agent_repo: AgentRepository,
        execution_repo: AgentExecutionRepository,
    ) -> None:
        self._agent_repo = agent_repo
        self._execution_repo = execution_repo

    async def get_agent(self, agent_id: str) -> Agent:
        agent = await self._agent_repo.find_by_id(agent_id)
        if not agent:
            raise NotFoundError(f"Agent {agent_id} not found")
        return agent

    async def list_agents(
        self, skip: int = 0, limit: int = 100, tenant_id: Optional[str] = None,
    ) -> tuple[list[Agent], int]:
        agents = await self._agent_repo.find_all(skip, limit, tenant_id)
        total = await self._agent_repo.count(tenant_id)
        return agents, total

    async def create_agent(self, agent: Agent) -> Agent:
        return await self._agent_repo.save(agent)

    async def update_agent(self, agent_id: str, updates: dict[str, Any]) -> Agent:
        agent = await self.get_agent(agent_id)
        for key, value in updates.items():
            if hasattr(agent, key) and key not in ("id", "created_at"):
                setattr(agent, key, value)
        agent.updated_at = datetime.utcnow()
        return await self._agent_repo.save(agent)

    async def delete_agent(self, agent_id: str) -> None:
        agent = await self.get_agent(agent_id)
        await self._agent_repo.delete(agent_id)

    async def execute_agent(
        self, agent_id: str, task: str, input_data: dict[str, Any], triggered_by: str = "",
    ) -> AgentExecution:
        agent = await self.get_agent(agent_id)
        if agent.status == AgentStatus.DISABLED:
            raise ValidationError(f"Agent {agent_id} is disabled")

        execution = AgentExecution(
            agent_id=agent_id,
            task=task,
            input_data=input_data,
            triggered_by=triggered_by,
        )
        execution = await self._execution_repo.save(execution)

        agent.status = AgentStatus.RUNNING
        await self._agent_repo.save(agent)

        start_time = time.monotonic()
        try:
            result = await self._run_agent_logic(agent, execution)
            execution.output_data = result
            execution.status = AgentStatus.SUCCESS
            agent.status = AgentStatus.IDLE
        except Exception as exc:
            execution.status = AgentStatus.FAILED
            execution.error_message = str(exc)
            agent.status = AgentStatus.FAILED if agent.status != AgentStatus.DISABLED else agent.status

        execution.duration_ms = int((time.monotonic() - start_time) * 1000)
        execution.completed_at = datetime.utcnow()
        await self._agent_repo.save(agent)
        return await self._execution_repo.save(execution)

    async def get_execution(self, execution_id: str) -> AgentExecution:
        execution = await self._execution_repo.find_by_id(execution_id)
        if not execution:
            raise NotFoundError(f"Execution {execution_id} not found")
        return execution

    async def list_executions(
        self, agent_id: str, skip: int = 0, limit: int = 100,
    ) -> list[AgentExecution]:
        return await self._execution_repo.find_by_agent(agent_id, skip, limit)

    async def _run_agent_logic(
        self, agent: Agent, execution: AgentExecution,
    ) -> dict[str, Any]:
        logger.info("Running agent %s with task: %s", agent.id, execution.task)
        return {
            "result": f"Agent '{agent.name}' processed task: {execution.task}",
            "status": "completed",
        }
