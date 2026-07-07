from __future__ import annotations

import asyncio
import logging
import time
import traceback
from collections.abc import Callable
from datetime import datetime
from typing import Any, Optional

from regulaforge.agents.domain.enums import (
    AgentRole,
    AgentStatus,
    TaskStatus,
)
from regulaforge.agents.domain.models import (
    AgentState,
    ConfidenceScore,
    EvaluationResult,
    ReasoningStep,
    Task,
    ToolCall,
    ToolDefinition,
)

logger = logging.getLogger(__name__)


class BaseAgent:
    def __init__(
        self,
        role: AgentRole,
        agent_id: Optional[str] = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        confidence_threshold: float = 0.6,
        llm_client: Optional[Any] = None,
        llm_model: str = "gpt-4o",
    ) -> None:
        self.role = role
        self.agent_id = agent_id or f"{role.value}_{datetime.utcnow().timestamp():.0f}"
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.confidence_threshold = confidence_threshold
        self.llm_client = llm_client
        self.llm_model = llm_model
        self.state = AgentState(
            agent_id=self.agent_id,
            role=role,
        )
        self.tools: dict[str, ToolDefinition] = {}
        self._interrupt_event: Optional[asyncio.Event] = None

    def register_tool(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        function: Callable[..., Any],
    ) -> None:
        self.tools[name] = ToolDefinition(
            name=name,
            description=description,
            parameters=parameters,
            function=function,
        )

    async def run(
        self,
        task: Task,
        context: Optional[dict[str, Any]] = None,
    ) -> AgentState:
        self.state.status = AgentStatus.RUNNING
        self.state.current_task = task
        task.status = TaskStatus.IN_PROGRESS
        task.started_at = datetime.utcnow()

        logger.info(
            "Agent %s (%s) starting task %s",
            self.agent_id, self.role.value, task.id,
        )

        try:
            result = await self._run_with_retry(task, context or {})
            self.state.evaluation = result
            if self.state.status != AgentStatus.WAITING_FOR_INPUT:
                self.state.status = AgentStatus.COMPLETED
            if task.status != TaskStatus.WAITING_FOR_HUMAN:
                task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.utcnow()
            task.output_data = {
                "evaluation": {
                    "passed": result.passed,
                    "confidence": {
                        "overall": result.score.overall,
                        "accuracy": result.score.accuracy,
                        "completeness": result.score.completeness,
                        "relevance": result.score.relevance,
                    },
                    "feedback": result.feedback,
                },
                "reasoning_trace": [
                    {
                        "step": s.step_number,
                        "description": s.description,
                        "output": s.output,
                        "confidence": s.confidence,
                    }
                    for s in self.state.reasoning_trace
                ],
                "tool_calls": [
                    {
                        "tool": tc.tool_name,
                        "arguments": tc.arguments,
                        "result": tc.result,
                        "error": tc.error,
                    }
                    for tc in self.state.tool_calls
                ],
                "fallback_used": self.state.fallback_used,
            }
        except Exception as exc:
            logger.error(
                "Agent %s failed on task %s: %s",
                self.agent_id, task.id, exc,
            )
            self.state.status = AgentStatus.FAILED
            task.status = TaskStatus.FAILED
            task.completed_at = datetime.utcnow()
            self.state.evaluation = EvaluationResult(
                passed=False,
                feedback=[str(exc), traceback.format_exc()],
            )

        return self.state

    async def _run_with_retry(
        self,
        task: Task,
        context: dict[str, Any],
    ) -> EvaluationResult:
        last_error: Optional[str] = None

        for attempt in range(1, self.max_retries + 1):
            try:
                self.state.error_count = attempt - 1
                if attempt > 1:
                    self.state.status = AgentStatus.RETRYING
                    logger.info(
                        "Retry attempt %d/%d for agent %s",
                        attempt, self.max_retries, self.agent_id,
                    )
                    await asyncio.sleep(self.retry_delay * (2 ** (attempt - 1)))

                result = await self._execute(task, context)
                eval_result = await self._evaluate(result, task, context)

                if eval_result.passed or eval_result.score.overall >= self.confidence_threshold:
                    return eval_result

                last_error = f"Evaluation failed: confidence={eval_result.score.overall:.3f} < threshold={self.confidence_threshold}"  # noqa: E501
                logger.warning("%s for agent %s (attempt %d)", last_error, self.agent_id, attempt)

            except Exception as exc:
                last_error = str(exc)
                logger.warning(
                    "Agent %s attempt %d failed: %s",
                    self.agent_id, attempt, exc,
                )

                self.state.tool_calls.append(ToolCall(
                    tool_name="_internal",
                    arguments={},
                    error=str(exc),
                    duration_ms=0.0,
                ))

        logger.warning(
            "Agent %s using fallback after %d failed attempts",
            self.agent_id, self.max_retries,
        )
        self.state.fallback_used = True
        return await self._fallback(task, context, last_error or "unknown error")

    async def _execute(
        self,
        task: Task,
        context: dict[str, Any],
    ) -> Any:
        raise NotImplementedError("Subclasses must implement _execute")

    async def _evaluate(
        self,
        _result: Any,
        _task: Task,
        _context: dict[str, Any],
    ) -> EvaluationResult:
        return EvaluationResult(
            passed=True,
            score=ConfidenceScore(overall=1.0, accuracy=1.0, completeness=1.0, relevance=1.0),
        )

    async def _fallback(
        self,
        _task: Task,
        _context: dict[str, Any],
        error: str,
    ) -> EvaluationResult:
        return EvaluationResult(
            passed=False,
            score=ConfidenceScore(overall=0.0),
            feedback=[f"Fallback activated: {error}"],
        )

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> Any:
        start = time.monotonic()
        tool_call = ToolCall(tool_name=tool_name, arguments=arguments)

        try:
            if tool_name not in self.tools:
                raise ValueError(f"Unknown tool: {tool_name}")

            tool_def = self.tools[tool_name]
            if tool_def.function is None:
                raise ValueError(f"Tool {tool_name} has no function defined")
            if asyncio.iscoroutinefunction(tool_def.function):
                result = await tool_def.function(**arguments)
            else:
                result = tool_def.function(**arguments)
            tool_call.result = result
            logger.info("Tool %s executed successfully", tool_name)
        except Exception as exc:
            tool_call.error = str(exc)
            logger.error("Tool %s failed: %s", tool_name, exc)
            raise
        finally:
            tool_call.duration_ms = (time.monotonic() - start) * 1000
            tool_call.timestamp = datetime.utcnow()
            self.state.tool_calls.append(tool_call)

        return tool_call.result

    def add_reasoning_step(
        self,
        description: str,
        input_text: Optional[str] = None,
        output_text: Optional[str] = None,
        confidence: float = 1.0,
        duration_ms: float = 0.0,
    ) -> ReasoningStep:
        step = ReasoningStep(
            step_number=len(self.state.reasoning_trace) + 1,
            description=description,
            input=input_text,
            output=output_text,
            confidence=confidence,
            duration_ms=duration_ms,
        )
        self.state.reasoning_trace.append(step)
        return step

    def add_memory(
        self,
        role: str,
        content: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        self.state.memory.add_interaction(role, content, metadata)

    def store_memory(self, key: str, value: Any, persistent: bool = False) -> None:
        self.state.memory.store(key, value, persistent)

    def recall_memory(self, key: str, default: Any = None) -> Any:
        return self.state.memory.recall(key, default)

    async def _compute_confidence(
        self,
        _result: Any,
        _task: Task,
        _context: dict[str, Any],
    ) -> ConfidenceScore:
        return ConfidenceScore(
            overall=0.85,
            accuracy=0.85,
            completeness=0.80,
            relevance=0.90,
            reasoning_quality=0.85,
        )

    async def _llm_generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.3,
    ) -> str:
        if self.llm_client is not None:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            try:
                response = await self.llm_client.chat.completions.create(
                    model=self.llm_model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                return response.choices[0].message.content or ""
            except Exception as exc:
                logger.warning("LLM call failed: %s", exc)

        return self._rule_based_generate(prompt)

    def _rule_based_generate(self, prompt: str) -> str:
        return f"[Rule-based response] {prompt[:200]}..."

    def set_interrupt(self) -> asyncio.Event:
        self._interrupt_event = asyncio.Event()
        return self._interrupt_event

    async def wait_for_resume(self, timeout: Optional[float] = None) -> bool:
        if self._interrupt_event is None:
            return True
        try:
            await asyncio.wait_for(self._interrupt_event.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    def resume(self) -> None:
        if self._interrupt_event is not None:
            self._interrupt_event.set()
            self._interrupt_event = None

    def reset_state(self) -> None:
        self.state = AgentState(agent_id=self.agent_id, role=self.role)
