import asyncio

from regulaforge.agents.application.supervisor import SupervisorAgent
from regulaforge.agents.domain.enums import (
    AgentRole,
    AgentStatus,
    RoutingDecision,
    TaskPriority,
    TaskStatus,
)
from regulaforge.agents.domain.models import Task


class TestSupervisorAgent:
    def test_agent_role(self):
        agent = SupervisorAgent()
        assert agent.role == AgentRole.SUPERVISOR
        assert agent.agent_id == "supervisor_001"

    def test_registered_tools(self):
        agent = SupervisorAgent()
        assert "route_task" in agent.tools
        assert "decompose_task" in agent.tools
        assert "escalate_task" in agent.tools

    def test_route_task_logic(self):
        agent = SupervisorAgent()
        result = agent._route_task_logic("Risk assessment needed", "risk")
        assert result == "risk_prediction"

    def test_route_task_logic_default(self):
        agent = SupervisorAgent()
        result = agent._route_task_logic("Unknown task", "unknown")
        assert result == "legal"

    def test_decompose_task_logic(self):
        agent = SupervisorAgent()
        result = agent._decompose_task_logic("task_1", "Complex analysis")
        assert len(result) == 3

    def test_escalate_task_logic(self):
        agent = SupervisorAgent()
        result = agent._escalate_task_logic("task_1", "Needs human review")
        assert result["escalated"] is True

    def test_run_routes_to_legal(self):
        agent = SupervisorAgent()
        task = Task(title="Legal question", description="Is this compliant?", tags=["legal"])

        async def run():
            state = await agent.run(task)
            return state

        state = asyncio.run(run())
        assert state.status == AgentStatus.COMPLETED
        assert state.routing_decision is not None

    def test_reasoning_trace_populated(self):
        agent = SupervisorAgent()
        task = Task(title="Test", description="Test task")

        async def run():
            return await agent.run(task)

        state = asyncio.run(run())
        assert len(state.reasoning_trace) >= 2

    def test_evaluation_passes(self):
        agent = SupervisorAgent()
        task = Task(title="Test", description="Test")

        async def run():
            return await agent.run(task)

        state = asyncio.run(run())
        assert state.evaluation.passed is True
        assert state.evaluation.score.overall > 0.9
