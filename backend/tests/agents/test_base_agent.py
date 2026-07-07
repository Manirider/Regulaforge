import asyncio

from regulaforge.agents.application.base_agent import BaseAgent
from regulaforge.agents.domain.enums import AgentRole, AgentStatus, TaskStatus
from regulaforge.agents.domain.models import (
    ConfidenceScore,
    EvaluationResult,
    Task,
    ToolDefinition,
)


class TestableAgent(BaseAgent):
    async def _execute(self, task: Task, context: dict) -> str:
        self.add_reasoning_step("Executing test task", input_text=task.description)
        return "executed"

    async def _evaluate(self, result, task, context):
        return EvaluationResult(
            passed=True,
            score=ConfidenceScore(overall=0.95, accuracy=0.9, completeness=0.9, relevance=1.0),
            feedback=["Test passed"],
        )


class FailingAgent(BaseAgent):
    async def _execute(self, task: Task, context: dict) -> str:
        raise ValueError("Intentional failure")

    async def _fallback(self, task, context, error):
        return EvaluationResult(
            passed=False,
            score=ConfidenceScore(overall=0.3),
            feedback=[f"Fallback: {error}"],
        )


class ThresholdAgent(BaseAgent):
    def __init__(self):
        super().__init__(role=AgentRole.LEGAL, confidence_threshold=0.8)

    async def _execute(self, task: Task, context: dict) -> str:
        return "low_confidence_result"

    async def _evaluate(self, result, task, context):
        return EvaluationResult(
            passed=False,
            score=ConfidenceScore(overall=0.5),
            feedback=["Low confidence"],
        )

    async def _fallback(self, task, context, error):
        return EvaluationResult(
            passed=False,
            score=ConfidenceScore(overall=0.2),
            feedback=[f"Fallback after low confidence: {error}"],
        )


class TestBaseAgent:
    def test_agent_initialization(self):
        agent = TestableAgent(role=AgentRole.LEGAL, agent_id="test_001")
        assert agent.role == AgentRole.LEGAL
        assert agent.agent_id == "test_001"
        assert agent.state.status == AgentStatus.IDLE

    def test_register_tool(self):
        agent = TestableAgent(role=AgentRole.AUDIT)
        agent.register_tool(
            name="test_tool",
            description="A test tool",
            parameters={"param": {"type": "string"}},
            function=lambda x: x,
        )
        assert "test_tool" in agent.tools
        assert agent.tools["test_tool"].name == "test_tool"

    def test_add_reasoning_step(self):
        agent = TestableAgent(role=AgentRole.SUPERVISOR)
        agent.add_reasoning_step("First step", input_text="input", output_text="output", confidence=0.9)
        assert len(agent.state.reasoning_trace) == 1
        assert agent.state.reasoning_trace[0].step_number == 1

    def test_add_multiple_reasoning_steps(self):
        agent = TestableAgent(role=AgentRole.LEGAL)
        agent.add_reasoning_step("Step 1")
        agent.add_reasoning_step("Step 2")
        assert len(agent.state.reasoning_trace) == 2
        assert agent.state.reasoning_trace[1].step_number == 2

    def test_add_memory(self):
        agent = TestableAgent(role=AgentRole.NOTIFICATION)
        agent.add_memory("user", "Hello agent", {"source": "test"})
        assert len(agent.state.memory.conversation_history) == 1

    def test_store_and_recall_memory(self):
        agent = TestableAgent(role=AgentRole.RISK_PREDICTION)
        agent.store_memory("key", "value")
        assert agent.recall_memory("key") == "value"

    def test_recall_memory_default(self):
        agent = TestableAgent(role=AgentRole.LEGAL)
        assert agent.recall_memory("nonexistent", "default") == "default"

    def test_call_tool(self):
        agent = TestableAgent(role=AgentRole.AUDIT)
        agent.register_tool("echo", "Echo test", {"msg": {"type": "string"}}, lambda msg: f"echo: {msg}")

        async def run():
            result = await agent.call_tool("echo", {"msg": "hello"})
            return result

        result = asyncio.run(run())
        assert result == "echo: hello"

    def test_call_tool_records_in_state(self):
        agent = TestableAgent(role=AgentRole.LEGAL)
        agent.register_tool("echo", "Echo", {"msg": {"type": "string"}}, lambda msg: msg)

        async def run():
            await agent.call_tool("echo", {"msg": "test"})
            return agent.state.tool_calls

        calls = asyncio.run(run())
        assert len(calls) == 1
        assert calls[0].tool_name == "echo"

    def test_call_unknown_tool(self):
        agent = TestableAgent(role=AgentRole.AUDIT)

        async def run():
            try:
                await agent.call_tool("nonexistent", {})
                return False
            except ValueError:
                return True

        assert asyncio.run(run()) is True

    def test_run_completes_successfully(self):
        agent = TestableAgent(role=AgentRole.LEGAL)
        task = Task(title="Test", description="Test task")

        async def run():
            state = await agent.run(task)
            return state

        state = asyncio.run(run())
        assert state.status == AgentStatus.COMPLETED
        assert task.status == TaskStatus.COMPLETED

    def test_run_records_reasoning_trace(self):
        agent = TestableAgent(role=AgentRole.LEGAL)
        task = Task(title="Test", description="Test")

        async def run():
            return await agent.run(task)

        state = asyncio.run(run())
        assert len(state.reasoning_trace) > 0

    def test_run_failing_agent_uses_fallback(self):
        agent = FailingAgent(role=AgentRole.AUDIT)
        task = Task(title="Fail", description="Will fail")

        async def run():
            return await agent.run(task)

        state = asyncio.run(run())
        assert state.status == AgentStatus.COMPLETED
        assert state.fallback_used is True

    def test_run_threshold_triggers_retry(self):
        agent = ThresholdAgent()
        task = Task(title="Threshold", description="Below threshold")

        async def run():
            return await agent.run(task)

        state = asyncio.run(run())
        assert state.fallback_used is True

    def test_reset_state(self):
        agent = TestableAgent(role=AgentRole.LEGAL)
        agent.add_reasoning_step("Step")
        agent.reset_state()
        assert len(agent.state.reasoning_trace) == 0
        assert agent.state.status == AgentStatus.IDLE

    def test_set_interrupt_and_resume(self):
        agent = TestableAgent(role=AgentRole.HUMAN_APPROVAL)
        event = agent.set_interrupt()
        assert event is not None
        assert agent._interrupt_event is not None

        agent.resume()
        assert agent._interrupt_event is None

    def test_wait_for_resume(self):
        agent = TestableAgent(role=AgentRole.HUMAN_APPROVAL)
        agent.set_interrupt()

        async def run():
            async def waiter():
                return await agent.wait_for_resume(timeout=1.0)

            async def resolver():
                await asyncio.sleep(0.05)
                agent.resume()
                return True

            result = await asyncio.gather(waiter(), resolver())
            return result[0]

        assert asyncio.run(run()) is True

    def test_rule_based_generate(self):
        agent = TestableAgent(role=AgentRole.LEGAL)
        result = agent._rule_based_generate("What is the regulation?")
        assert "Rule-based" in result
