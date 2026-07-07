from datetime import datetime

from regulaforge.agents.domain.enums import (
    AgentRole,
    AgentStatus,
    RoutingDecision,
    TaskPriority,
    TaskStatus,
)
from regulaforge.agents.domain.models import (
    AgentMemory,
    AgentState,
    ConfidenceScore,
    EvaluationResult,
    ReasoningStep,
    Task,
    ToolCall,
    ToolDefinition,
)


class TestEnums:
    def test_agent_role_values(self):
        assert AgentRole.SUPERVISOR.value == "supervisor"
        assert AgentRole.LEGAL.value == "legal"
        assert AgentRole.HUMAN_APPROVAL.value == "human_approval"

    def test_agent_status_values(self):
        assert AgentStatus.IDLE.value == "idle"
        assert AgentStatus.RUNNING.value == "running"
        assert AgentStatus.WAITING_FOR_INPUT.value == "waiting_for_input"

    def test_routing_decision_values(self):
        assert RoutingDecision.ROUTE_TO_LEGAL.value == "route_to_legal"
        assert RoutingDecision.COMPLETE.value == "complete"
        assert RoutingDecision.ESCALATE.value == "escalate"

    def test_task_priority_values(self):
        assert TaskPriority.LOW.value == 1
        assert TaskPriority.CRITICAL.value == 4

    def test_task_status_values(self):
        assert TaskStatus.WAITING_FOR_HUMAN.value == "waiting_for_human"
        assert TaskStatus.CANCELLED.value == "cancelled"


class TestDomainModels:
    def test_tool_definition(self):
        td = ToolDefinition(
            name="test_tool",
            description="A test tool",
            parameters={"param1": {"type": "string"}},
        )
        assert td.name == "test_tool"
        assert td.function is None

    def test_tool_call_defaults(self):
        tc = ToolCall(tool_name="test", arguments={"arg": 1})
        assert tc.error is None
        assert tc.duration_ms == 0.0
        assert tc.timestamp is not None

    def test_tool_call_with_error(self):
        tc = ToolCall(tool_name="test", arguments={}, error="Something failed")
        assert tc.error == "Something failed"

    def test_reasoning_step(self):
        rs = ReasoningStep(step_number=1, description="Analyzing input")
        assert rs.step_number == 1
        assert rs.confidence == 1.0

    def test_reasoning_step_with_output(self):
        rs = ReasoningStep(
            step_number=1, description="Analysis",
            input="test input", output="test output",
            confidence=0.85, duration_ms=150.0,
        )
        assert rs.output == "test output"
        assert rs.duration_ms == 150.0

    def test_confidence_score_defaults(self):
        cs = ConfidenceScore()
        assert cs.overall == 0.0
        assert cs.reasoning_quality == 0.0

    def test_confidence_score_custom(self):
        cs = ConfidenceScore(overall=0.9, accuracy=0.85, completeness=0.8, relevance=0.95, reasoning_quality=0.88)
        assert cs.overall == 0.9
        assert cs.reasoning_quality == 0.88

    def test_evaluation_result_defaults(self):
        er = EvaluationResult()
        assert er.passed is False
        assert er.feedback == []

    def test_evaluation_result_with_data(self):
        cs = ConfidenceScore(overall=0.9)
        er = EvaluationResult(passed=True, score=cs, feedback=["Good"], suggestions=["Improve X"])
        assert er.passed is True
        assert "Improve X" in er.suggestions

    def test_agent_memory_add_interaction(self):
        mem = AgentMemory()
        mem.add_interaction("user", "Hello")
        assert len(mem.conversation_history) == 1
        assert mem.conversation_history[0]["role"] == "user"

    def test_agent_memory_store_recall(self):
        mem = AgentMemory()
        mem.store("key1", "value1")
        assert mem.recall("key1") == "value1"

    def test_agent_memory_store_persistent(self):
        mem = AgentMemory()
        mem.store("perm_key", "perm_value", persistent=True)
        assert mem.recall("perm_key") == "perm_value"
        mem.clear_short_term()
        assert mem.recall("perm_key") == "perm_value"

    def test_agent_memory_recall_default(self):
        mem = AgentMemory()
        assert mem.recall("nonexistent", "default") == "default"

    def test_agent_memory_clear_short_term(self):
        mem = AgentMemory()
        mem.store("temp", "value")
        mem.store("perm", "value", persistent=True)
        mem.clear_short_term()
        assert mem.recall("temp") is None
        assert mem.recall("perm") == "value"

    def test_agent_memory_max_history(self):
        mem = AgentMemory(max_history=5)
        for i in range(10):
            mem.add_interaction("user", f"msg {i}")
        assert len(mem.conversation_history) == 5

    def test_task_defaults(self):
        task = Task()
        assert task.status == TaskStatus.PENDING
        assert task.priority == TaskPriority.MEDIUM
        assert task.id is not None

    def test_task_with_data(self):
        task = Task(
            title="Test Task",
            description="A test",
            priority=TaskPriority.HIGH,
            tags=["urgent", "compliance"],
            input_data={"query": "test"},
        )
        assert task.title == "Test Task"
        assert task.priority == TaskPriority.HIGH
        assert "urgent" in task.tags

    def test_task_timestamps(self):
        task = Task()
        assert task.created_at is not None
        assert task.started_at is None
        assert task.completed_at is None

    def test_task_hierarchy(self):
        parent = Task()
        child = Task(parent_task_id=parent.id)
        parent.subtask_ids.append(child.id)
        assert child.parent_task_id == parent.id
        assert parent.subtask_ids == [child.id]

    def test_agent_state_defaults(self):
        state = AgentState()
        assert state.status == AgentStatus.IDLE
        assert state.current_task is None
        assert state.error_count == 0
        assert state.max_retries == 3

    def test_agent_state_with_role(self):
        state = AgentState(agent_id="test_001", role=AgentRole.LEGAL)
        assert state.agent_id == "test_001"
        assert state.role == AgentRole.LEGAL

    def test_agent_state_task_queue(self):
        state = AgentState()
        t1 = Task(title="Task 1")
        t2 = Task(title="Task 2")
        state.task_queue = [t1, t2]
        assert len(state.task_queue) == 2
