from __future__ import annotations

from typing import Optional

from regulaforge.modules.agents.domain.models import Agent, AgentExecution


class AgentRepository:
    async def find_by_id(self, agent_id: str) -> Optional[Agent]:
        raise NotImplementedError

    async def find_by_type(self, agent_type: str) -> list[Agent]:
        raise NotImplementedError

    async def find_all(self, skip: int = 0, limit: int = 100, tenant_id: Optional[str] = None) -> list[Agent]:
        raise NotImplementedError

    async def count(self, tenant_id: Optional[str] = None) -> int:
        raise NotImplementedError

    async def save(self, agent: Agent) -> Agent:
        raise NotImplementedError

    async def delete(self, agent_id: str) -> None:
        raise NotImplementedError


class AgentExecutionRepository:
    async def find_by_id(self, execution_id: str) -> Optional[AgentExecution]:
        raise NotImplementedError

    async def find_by_agent(self, agent_id: str, skip: int = 0, limit: int = 100) -> list[AgentExecution]:
        raise NotImplementedError

    async def save(self, execution: AgentExecution) -> AgentExecution:
        raise NotImplementedError
