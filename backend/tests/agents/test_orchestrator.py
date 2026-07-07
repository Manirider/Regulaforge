import asyncio

from regulaforge.agents.application.orchestrator import AgentOrchestrator
from regulaforge.agents.domain.enums import AgentRole, RoutingDecision, TaskPriority, TaskStatus
from regulaforge.agents.domain.models import Task


class TestAgentOrchestrator:
    def test_orchestrator_initialization(self):
        orch = AgentOrchestrator()
        assert orch.supervisor is not None
        assert orch.monitoring is not None
        assert orch.knowledge_graph is not None
        assert orch.risk_prediction is not None
        assert orch.clause_drafting is not None
        assert orch.legal is not None
        assert orch.audit is not None
        assert orch.notification is not None
        assert orch.human_approval is not None

    def test_all_agents_registered(self):
        orch = AgentOrchestrator()
        assert len(orch._agents) == 9

    def test_get_agent(self):
        orch = AgentOrchestrator()
        agent = orch.get_agent(AgentRole.LEGAL)
        assert agent.role == AgentRole.LEGAL

    def test_get_agent_supervisor(self):
        orch = AgentOrchestrator()
        agent = orch.get_agent(AgentRole.SUPERVISOR)
        assert agent.role == AgentRole.SUPERVISOR

    def test_run_workflow_completes(self):
        orch = AgentOrchestrator()
        task = Task(title="Legal question", description="Is this regulation applicable?", tags=["legal"])

        async def run():
            state = await orch.run_workflow(task)
            return state

        state = asyncio.run(run())
        assert "task" in state
        assert state["task"].status in (TaskStatus.COMPLETED, TaskStatus.FAILED)

    def test_workflow_stores_agent_results(self):
        orch = AgentOrchestrator()
        task = Task(title="Test", description="Compliance check for RBI guidelines")

        async def run():
            return await orch.run_workflow(task)

        state = asyncio.run(run())
        assert "agent_results" in state
        assert "supervisor" in state["agent_results"]

    def test_workflow_has_routing_decision(self):
        orch = AgentOrchestrator()
        task = Task(title="Risk assessment", description="Assess risk for new regulation", tags=["risk"])

        async def run():
            return await orch.run_workflow(task)

        state = asyncio.run(run())
        assert state.get("routing_decision") is not None

    def test_resolve_human_approval(self):
        orch = AgentOrchestrator()
        orch.human_approval._pending_approvals["req_test"] = {
            "status": "pending", "task_id": "t1",
        }
        result = orch.resolve_human_approval("req_test", "approved", "OK")
        assert result["decision"] == "approved"

    def test_reset_all(self):
        orch = AgentOrchestrator()
        orch.supervisor.add_reasoning_step("Some step")
        orch.reset_all()
        assert len(orch.supervisor.state.reasoning_trace) == 0

    def test_workflow_error_handling(self):
        orch = AgentOrchestrator()
        task = Task(title="", description="")

        async def run():
            return await orch.run_workflow(task)

        state = asyncio.run(run())
        assert "errors" in state
        assert "agent_results" in state
