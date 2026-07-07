import asyncio

import pytest

from regulaforge.agents.domain.enums import RoutingDecision, TaskPriority
from regulaforge.agents.domain.models import Task
from regulaforge.agents.langgraph import (
    AgentFactory,
    GraphBuilder,
    LangGraphOrchestrator,
    create_initial_state,
)
from regulaforge.agents.langgraph.checkpoint import create_checkpoint_saver
from regulaforge.agents.langgraph.nodes import (
    AgentNodeError,
    finalize_node,
    supervisor_node,
)
from regulaforge.agents.langgraph.routing import route_after_agent, route_after_supervisor
from regulaforge.agents.langgraph.state import AgentWorkflowState


class TestLangGraphState:
    def test_create_initial_state(self):
        task = Task(title="Test", description="Test task")
        state = create_initial_state(task)
        assert state["task"] == task
        assert state["errors"] == []
        assert state["agent_results"] == {}
        assert state["routing_decision"] is None
        assert state["current_agent"] is None
        assert state["elapsed_seconds"] == 0.0
        assert state["start_time"] > 0

    def test_initial_state_all_keys(self):
        task = Task(title="Test", description="Test task")
        state = create_initial_state(task)
        expected_keys = {
            "task", "supervisor_state", "monitoring_state",
            "knowledge_graph_state", "risk_prediction_state",
            "clause_drafting_state", "legal_state", "audit_state",
            "notification_state", "human_approval_state",
            "routing_decision", "current_agent", "errors",
            "start_time", "agent_results", "elapsed_seconds",
        }
        assert set(state.keys()) == expected_keys


class TestLangGraphRouting:
    def test_route_after_supervisor_default(self):
        task = Task(title="Test", description="Test")
        state = create_initial_state(task)
        result = route_after_supervisor(state)
        assert result == "legal"

    def test_route_after_supervisor_complete(self):
        state = create_initial_state(Task(title="Test", description="Test"))
        state["routing_decision"] = RoutingDecision.COMPLETE
        result = route_after_supervisor(state)
        assert result == "finalize"

    def test_route_after_supervisor_all_routes(self):
        route_map = {
            RoutingDecision.ROUTE_TO_MONITORING: "monitoring",
            RoutingDecision.ROUTE_TO_KNOWLEDGE_GRAPH: "knowledge_graph",
            RoutingDecision.ROUTE_TO_RISK_PREDICTION: "risk_prediction",
            RoutingDecision.ROUTE_TO_CLAUSE_DRAFTING: "clause_drafting",
            RoutingDecision.ROUTE_TO_LEGAL: "legal",
            RoutingDecision.ROUTE_TO_AUDIT: "audit",
            RoutingDecision.ROUTE_TO_NOTIFICATION: "notification",
            RoutingDecision.ROUTE_TO_HUMAN_APPROVAL: "human_approval",
            RoutingDecision.COMPLETE: "finalize",
            RoutingDecision.ESCALATE: "escalate",
            RoutingDecision.FAIL: "fail",
        }
        for decision, expected_node in route_map.items():
            state = create_initial_state(Task(title="Test", description="Test"))
            state["routing_decision"] = decision
            result = route_after_supervisor(state)
            assert result == expected_node, f"{decision.value} -> {result}, expected {expected_node}"

    def test_route_after_agent_no_errors(self):
        state = create_initial_state(Task(title="Test", description="Test"))
        result = route_after_agent(state)
        assert result == "finalize"

    def test_route_after_agent_with_errors(self):
        state = create_initial_state(Task(title="Test", description="Test"))
        state["errors"].append("test error")
        result = route_after_agent(state)
        assert result == "notification"

    def test_route_after_supervisor_unknown_decision(self):
        state = create_initial_state(Task(title="Test", description="Test"))
        state["routing_decision"] = "unknown_decision"
        result = route_after_supervisor(state)
        assert result == "legal"


class TestLangGraphCheckpoint:
    def test_create_memory_checkpoint(self):
        saver = create_checkpoint_saver("memory")
        assert saver is not None
        from langgraph.checkpoint.memory import MemorySaver
        assert isinstance(saver, MemorySaver)

    def test_create_unknown_checkpoint_type(self):
        saver = create_checkpoint_saver("unknown_type")
        assert saver is not None
        from langgraph.checkpoint.memory import MemorySaver
        assert isinstance(saver, MemorySaver)

    def test_create_checkpoint_normalizes_case(self):
        saver = create_checkpoint_saver("  MEMORY  ")
        assert saver is not None

    def test_create_sqlite_checkpoint_fallback_on_empty(self):
        saver = create_checkpoint_saver("sqlite", conn_string="")
        assert saver is not None

    def test_create_postgres_checkpoint_fallback_on_empty(self):
        saver = create_checkpoint_saver("postgres", conn_string="")
        assert saver is not None


class TestAgentFactory:
    def test_create_all_agents(self):
        agents = AgentFactory.create_agents()
        assert len(agents) == 9
        assert "supervisor" in agents
        assert "legal" in agents
        assert "audit" in agents
        assert "monitoring" in agents
        assert "knowledge_graph" in agents
        assert "risk_prediction" in agents
        assert "clause_drafting" in agents
        assert "notification" in agents
        assert "human_approval" in agents

    def test_agent_roles_match(self):
        agents = AgentFactory.create_agents()
        assert agents["supervisor"].role.value == "supervisor"
        assert agents["legal"].role.value == "legal"
        assert agents["audit"].role.value == "audit"


class TestGraphBuilder:
    def test_build_graph_structure(self):
        agents = AgentFactory.create_agents()
        builder = GraphBuilder(agents)
        graph = builder.build()
        node_names = list(graph.nodes.keys())
        expected = {
            "supervisor", "monitoring", "knowledge_graph", "risk_prediction",
            "clause_drafting", "legal", "audit", "notification",
            "human_approval", "finalize",
        }
        assert set(node_names) == expected

    def test_build_graph_entry_point(self):
        agents = AgentFactory.create_agents()
        builder = GraphBuilder(agents)
        graph = builder.build()
        assert "supervisor" in graph.nodes


class TestLangGraphOrchestrator:
    def test_orchestrator_initialization(self):
        orch = LangGraphOrchestrator()
        assert len(orch._agents) == 9
        assert "supervisor" in orch._agents
        assert "legal" in orch._agents

    def test_get_agent(self):
        orch = LangGraphOrchestrator()
        agent = orch.get_agent("supervisor")
        assert agent is not None
        assert agent.role.value == "supervisor"

    def test_get_agent_unknown_raises(self):
        orch = LangGraphOrchestrator()
        with pytest.raises(KeyError, match="unknown_agent"):
            orch.get_agent("unknown_agent")

    def test_build_graph(self):
        orch = LangGraphOrchestrator()
        graph = orch.build_graph()
        assert graph is not None
        node_names = list(graph.nodes.keys())
        assert "supervisor" in node_names
        assert "finalize" in node_names

    def test_compile(self):
        orch = LangGraphOrchestrator()
        compiled = orch.compile()
        assert compiled is not None

    def test_build_then_compile(self):
        orch = LangGraphOrchestrator()
        orch.build_graph()
        compiled = orch.compile()
        assert compiled is not None

    def test_reset_all(self):
        orch = LangGraphOrchestrator()
        orch.reset_all()
        for agent in orch._agents.values():
            assert agent.state.status.value == "idle"

    def test_orchestrator_with_custom_checkpoint(self):
        from langgraph.checkpoint.memory import MemorySaver
        saver = MemorySaver()
        orch = LangGraphOrchestrator(checkpoint_saver=saver)
        assert orch.checkpoint_saver is saver

    def test_orchestrator_with_custom_factory(self):
        factory = AgentFactory()
        orch = LangGraphOrchestrator(agent_factory=factory)
        assert len(orch._agents) == 9

    def test_orchestrator_resolve_without_compile_raises(self):
        orch = LangGraphOrchestrator()
        with pytest.raises(RuntimeError, match="not compiled"):
            orch.resolve_human_approval("thread", {})


@pytest.mark.asyncio
class TestLangGraphWorkflow:
    async def test_run_compliance_workflow(self):
        orch = LangGraphOrchestrator()
        orch.compile()

        task = Task(
            title="Compliance check",
            description="Check compliance for new regulation",
            priority=TaskPriority.MEDIUM,
        )

        result = await orch.run(task, thread_id="test-compliance")
        assert result["task"].status.value == "completed"
        assert len(result["errors"]) == 0
        assert result["elapsed_seconds"] > 0
        assert "supervisor" in result.get("agent_results", {})

    async def test_run_multiple_workflows(self):
        orch = LangGraphOrchestrator()
        orch.compile()

        workflows = [
            ("Legal analysis", "Legal analysis for new policy"),
            ("Audit framework", "Audit existing compliance framework"),
        ]
        for title, desc in workflows:
            task = Task(title=title, description=desc, priority=TaskPriority.MEDIUM)
            result = await orch.run(task, thread_id=title.lower().replace(" ", "-"))
            assert result["task"].status.value == "completed", f"Failed for {title}"
            assert "supervisor" in result.get("agent_results", {})

    async def test_workflow_tracks_agent_results(self):
        orch = LangGraphOrchestrator()
        orch.compile()

        task = Task(
            title="Test tracking",
            description="Verify agent results are tracked",
            priority=TaskPriority.MEDIUM,
        )

        result = await orch.run(task, thread_id="test-tracking")
        agent_results = result.get("agent_results", {})
        assert "supervisor" in agent_results
        supervisor_result = agent_results["supervisor"]
        assert "routing" in supervisor_result
        assert "reasoning" in supervisor_result

    async def test_workflow_agent_fallback_recorded(self):
        orch = LangGraphOrchestrator()
        orch.compile()

        agent = orch.get_agent("legal")
        original_execute = agent._execute

        async def failing_execute(task, context):
            raise RuntimeError("Simulated failure from legal")

        agent._execute = failing_execute

        task = Task(
            title="Failure test",
            description="Legal analysis is needed urgently for this task",
            tags=["legal"],
            priority=TaskPriority.MEDIUM,
        )

        result = await orch.run(task, thread_id="test-failure")
        legal_result = result.get("agent_results", {}).get("legal", {})
        assert legal_result.get("fallback_used", False)
        assert legal_result.get("status", "") == "completed"

        agent._execute = original_execute

    async def test_workflow_with_different_thread_ids(self):
        orch = LangGraphOrchestrator()
        orch.compile()

        task1 = Task(title="Task A", description="First task", priority=TaskPriority.MEDIUM)
        task2 = Task(title="Task B", description="Second task", priority=TaskPriority.MEDIUM)

        result1 = await orch.run(task1, thread_id="thread-a")
        result2 = await orch.run(task2, thread_id="thread-b")

        assert result1["task"].status.value == "completed"
        assert result2["task"].status.value == "completed"

    async def test_workflow_with_all_routing_decisions(self):
        decisions = [
            RoutingDecision.ROUTE_TO_LEGAL,
            RoutingDecision.ROUTE_TO_AUDIT,
            RoutingDecision.ROUTE_TO_RISK_PREDICTION,
            RoutingDecision.ROUTE_TO_CLAUSE_DRAFTING,
            RoutingDecision.ROUTE_TO_MONITORING,
            RoutingDecision.ROUTE_TO_NOTIFICATION,
            RoutingDecision.ROUTE_TO_KNOWLEDGE_GRAPH,
        ]

        for decision in decisions:
            orch = LangGraphOrchestrator()
            orch.compile()

            async def make_routing(t, d=decision):
                return d

            orch.get_agent("supervisor")._determine_routing = make_routing

            task = Task(
                title=f"Test {decision.value}",
                description=f"Testing routing to {decision.value}",
                priority=TaskPriority.MEDIUM,
            )

            result = await orch.run(task, thread_id=f"route-{decision.value}")
            assert result["task"].status.value == "completed", f"Failed for {decision.value}"
            assert len(result["errors"]) == 0, f"Errors for {decision.value}: {result['errors']}"

    async def test_workflow_complete_routing(self):
        orch = LangGraphOrchestrator()
        orch.compile()

        async def complete_routing(task):
            return RoutingDecision.COMPLETE

        orch.get_agent("supervisor")._determine_routing = complete_routing

        task = Task(
            title="Complete task",
            description="Task that should complete immediately",
            priority=TaskPriority.MEDIUM,
        )

        result = await orch.run(task, thread_id="test-complete")
        assert result["task"].status.value == "completed"
        assert "supervisor" in result.get("agent_results", {})
        assert "legal" not in result.get("agent_results", {})

    async def test_workflow_fail_routing(self):
        orch = LangGraphOrchestrator()
        orch.compile()

        async def fail_routing(task):
            return RoutingDecision.FAIL

        orch.get_agent("supervisor")._determine_routing = fail_routing

        task = Task(
            title="Fail task",
            description="Task that should fail",
            priority=TaskPriority.MEDIUM,
        )

        result = await orch.run(task, thread_id="test-fail")
        assert result["task"].status.value == "completed"

    async def test_workflow_handles_supervisor_exception(self):
        orch = LangGraphOrchestrator()
        orch.compile()

        supervisor = orch.get_agent("supervisor")
        original_execute = supervisor._execute

        async def failing_execute(task, context):
            raise RuntimeError("Supervisor crashed")

        supervisor._execute = failing_execute

        task = Task(
            title="Crash test",
            description="Task that crashes supervisor",
            priority=TaskPriority.MEDIUM,
        )

        result = await orch.run(task, thread_id="test-crash")
        assert result["task"].status.value == "completed"
        supervisor_result = result.get("agent_results", {}).get("supervisor", {})
        assert supervisor_result.get("fallback_used", False)

        supervisor._execute = original_execute
