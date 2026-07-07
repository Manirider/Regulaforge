"""Async task scheduler for background execution.

Supports interval-based, cron-based, and delayed one-shot task executions.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
import logging
from typing import Any, Optional

from regulaforge.config.logging import get_logger

logger = get_logger(__name__)


def _field_matches(val: int, pattern: str) -> bool:
    """Check if a numeric value matches a cron field pattern."""
    if pattern == "*":
        return True
    if "," in pattern:
        return any(_field_matches(val, p) for p in pattern.split(","))
    if "/" in pattern:
        base, step = pattern.split("/")
        step_val = int(step)
        if base == "*":
            return val % step_val == 0
        if "-" in base:
            start, end = base.split("-")
            return val >= int(start) and val <= int(end) and (val - int(start)) % step_val == 0
        return val >= int(base) and (val - int(base)) % step_val == 0
    if "-" in pattern:
        start, end = pattern.split("-")
        return val >= int(start) and val <= int(end)
    try:
        return val == int(pattern)
    except ValueError:
        return False


def _cron_matches(dt: datetime, cron_expression: str) -> bool:
    """Check if the given datetime matches a 5-field cron expression."""
    fields = cron_expression.split()
    if len(fields) != 5:
        raise ValueError(f"Invalid cron expression: {cron_expression}")

    dow_val = dt.isoweekday()  # Monday=1, Sunday=7
    cron_dow = fields[4]

    matches = (
        _field_matches(dt.minute, fields[0])
        and _field_matches(dt.hour, fields[1])
        and _field_matches(dt.day, fields[2])
        and _field_matches(dt.month, fields[3])
    )

    if not matches:
        return False

    if cron_dow == "*":
        return True

    if dow_val == 7:  # Sunday
        return _field_matches(0, cron_dow) or _field_matches(7, cron_dow)
    return _field_matches(dow_val, cron_dow)


class Task:
    """Represents a scheduled task."""

    def __init__(
        self,
        name: str,
        func: Callable[[], Awaitable[Any]],
        task_type: str,
        interval_seconds: Optional[float] = None,
        cron_expression: Optional[str] = None,
        delay_seconds: Optional[float] = None,
        retries: int = 3,
        retry_delay_seconds: float = 5.0,
    ) -> None:
        self.name = name
        self.func = func
        self.task_type = task_type
        self.interval_seconds = interval_seconds
        self.cron_expression = cron_expression
        self.delay_seconds = delay_seconds
        self.retries = retries
        self.retry_delay_seconds = retry_delay_seconds

        self.last_run: Optional[datetime] = None
        self.last_success: Optional[datetime] = None
        self.last_failure: Optional[datetime] = None
        self.run_count = 0
        self.success_count = 0
        self.failure_count = 0
        self.is_running = False
        self._created_at = datetime.now(timezone.utc)


class TaskScheduler:
    """Asynchronous background task scheduler."""

    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}
        self._running = False
        self._loop_task: Optional[asyncio.Task[None]] = None
        self._metrics = {
            "runs": 0,
            "successes": 0,
            "failures": 0,
        }

    def schedule_interval(
        self,
        name: str,
        func: Callable[[], Awaitable[Any]],
        seconds: float,
        retries: int = 3,
        retry_delay_seconds: float = 5.0,
    ) -> None:
        """Schedule a recurring task to run at fixed intervals."""
        self._tasks[name] = Task(
            name=name,
            func=func,
            task_type="interval",
            interval_seconds=seconds,
            retries=retries,
            retry_delay_seconds=retry_delay_seconds,
        )
        logger.debug("Scheduled interval task '%s' every %.2fs", name, seconds)

    def schedule_cron(
        self,
        name: str,
        func: Callable[[], Awaitable[Any]],
        cron_expression: str,
        retries: int = 3,
        retry_delay_seconds: float = 5.0,
    ) -> None:
        """Schedule a task using a standard 5-field cron expression."""
        fields = cron_expression.split()
        if len(fields) != 5:
            raise ValueError(f"Invalid cron expression: {cron_expression}")

        self._tasks[name] = Task(
            name=name,
            func=func,
            task_type="cron",
            cron_expression=cron_expression,
            retries=retries,
            retry_delay_seconds=retry_delay_seconds,
        )
        logger.debug("Scheduled cron task '%s' with expression '%s'", name, cron_expression)

    def schedule_once(
        self,
        name: str,
        func: Callable[[], Awaitable[Any]],
        delay_seconds: float,
        retries: int = 3,
        retry_delay_seconds: float = 5.0,
    ) -> None:
        """Schedule a one-shot task after a delay."""
        self._tasks[name] = Task(
            name=name,
            func=func,
            task_type="once",
            delay_seconds=delay_seconds,
            retries=retries,
            retry_delay_seconds=retry_delay_seconds,
        )
        logger.debug("Scheduled one-shot task '%s' in %.2fs", name, delay_seconds)

    def cancel(self, name: str) -> None:
        """Cancel a scheduled task."""
        if name in self._tasks:
            del self._tasks[name]
            logger.debug("Cancelled task '%s'", name)

    def list_tasks(self) -> list[dict[str, Any]]:
        """Introspect active tasks and their runtime metadata."""
        return [
            {
                "name": task.name,
                "type": task.task_type,
                "interval_seconds": task.interval_seconds,
                "cron_expression": task.cron_expression,
                "delay_seconds": task.delay_seconds,
                "last_run": task.last_run.isoformat() if task.last_run else None,
                "last_success": task.last_success.isoformat() if task.last_success else None,
                "last_failure": task.last_failure.isoformat() if task.last_failure else None,
                "run_count": task.run_count,
                "success_count": task.success_count,
                "failure_count": task.failure_count,
                "is_running": task.is_running,
            }
            for task in self._tasks.values()
        ]

    def start(self) -> None:
        """Start the scheduler background loop."""
        if self._running:
            return
        self._running = True
        self._loop_task = asyncio.create_task(self._scheduler_loop())
        logger.info("Task scheduler started")

    async def shutdown(self) -> None:
        """Gracefully stop the scheduler, draining active tasks."""
        if not self._running:
            return
        self._running = False
        logger.info("Stopping task scheduler and draining tasks...")
        if self._loop_task:
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass
            self._loop_task = None

        # Wait for running tasks to finish
        running_tasks = [t for t in self._tasks.values() if t.is_running]
        if running_tasks:
            logger.info("Waiting for %d running tasks to drain...", len(running_tasks))
            for _ in range(10):
                if not any(t.is_running for t in self._tasks.values()):
                    break
                await asyncio.sleep(1.0)
        logger.info("Task scheduler stopped")

    async def _scheduler_loop(self) -> None:
        """Main scheduling evaluation loop running once per second."""
        while self._running:
            try:
                now = datetime.now(timezone.utc)
                tasks_snapshot = list(self._tasks.values())
                for task in tasks_snapshot:
                    if task.is_running:
                        continue

                    should_run = False
                    if task.task_type == "interval":
                        if task.last_run is None:
                            should_run = True
                        elif (now - task.last_run).total_seconds() >= (task.interval_seconds or 0):
                            should_run = True
                    elif task.task_type == "cron":
                        if task.last_run is None or (now - task.last_run).total_seconds() >= 59:
                            if _cron_matches(now, task.cron_expression or ""):
                                should_run = True
                    elif task.task_type == "once":
                        if task.last_run is None:
                            if (now - task._created_at).total_seconds() >= (task.delay_seconds or 0):
                                should_run = True

                    if should_run:
                        task.is_running = True
                        task.last_run = now
                        task.run_count += 1
                        self._metrics["runs"] += 1
                        asyncio.create_task(self._run_task(task))

                await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Error in scheduler loop: %s", exc, exc_info=True)
                await asyncio.sleep(1.0)

    async def _run_task(self, task: Task) -> None:
        """Execute a single task with retry logic."""
        attempts = task.retries + 1
        for attempt in range(attempts):
            try:
                logger.debug("Executing task '%s' (attempt %d/%d)", task.name, attempt + 1, attempts)
                await task.func()
                task.last_success = datetime.now(timezone.utc)
                task.success_count += 1
                self._metrics["successes"] += 1
                task.is_running = False
                if task.task_type == "once":
                    self.cancel(task.name)
                return
            except Exception as exc:
                logger.error(
                    "Task '%s' failed on attempt %d/%d: %s",
                    task.name,
                    attempt + 1,
                    attempts,
                    exc,
                    exc_info=True,
                )
                if attempt < task.retries:
                    await asyncio.sleep(task.retry_delay_seconds)
                else:
                    task.last_failure = datetime.now(timezone.utc)
                    task.failure_count += 1
                    self._metrics["failures"] += 1

        task.is_running = False
        if task.task_type == "once":
            self.cancel(task.name)

    @property
    def metrics(self) -> dict[str, int]:
        return dict(self._metrics)
