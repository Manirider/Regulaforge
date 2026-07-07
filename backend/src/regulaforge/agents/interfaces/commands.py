from __future__ import annotations

import json
import logging
from typing import Any

from regulaforge.agents.domain.enums import TaskPriority
from regulaforge.agents.domain.models import Task

logger = logging.getLogger(__name__)


def create_agents_cli(subparsers: Any) -> None:
    parser = subparsers.add_parser(
        "agents",
        help="Multi-agent workflow operations",
    )
    parser.set_defaults(command="agents")
    sub = parser.add_subparsers(dest="agents_command")

    workflow_parser = sub.add_parser("workflow", help="Run a multi-agent workflow")
    workflow_parser.add_argument("--title", required=True)
    workflow_parser.add_argument("--description", required=True)
    workflow_parser.add_argument("--priority", type=int, default=2)
    workflow_parser.add_argument("--tags", default="")
    workflow_parser.add_argument("--input", default="{}")
    workflow_parser.add_argument("--output", choices=["text", "json"], default="text")

    direct_parser = sub.add_parser("run", help="Run a single agent directly")
    direct_parser.add_argument("--agent", required=True,
                               choices=["supervisor", "monitoring", "knowledge_graph",
                                        "risk_prediction", "clause_drafting", "legal",
                                        "audit", "notification", "human_approval"])
    direct_parser.add_argument("--title", required=True)
    direct_parser.add_argument("--description", required=True)
    direct_parser.add_argument("--input", default="{}")

    approve_parser = sub.add_parser("approve", help="Resolve a human approval request")
    approve_parser.add_argument("--request-id", required=True)
    approve_parser.add_argument("--decision", required=True, choices=["approve", "reject", "request_changes"])
    approve_parser.add_argument("--notes", default=None)

    sub.add_parser("status", help="List all agent statuses")
    sub.add_parser("reset", help="Reset all agents")


async def _run_workflow(args: Any) -> None:
    from regulaforge.agents.interfaces.api import get_orchestrator

    orch = get_orchestrator()
    task = Task(
        title=args.title,
        description=args.description,
        priority=TaskPriority(args.priority),
        tags=[t.strip() for t in args.tags.split(",") if t.strip()],
        input_data=json.loads(args.input),
    )
    state = await orch.run_workflow(task)

    state.get("routing_decision")
    if args.output == "json":
        pass
    else:
        if state["agent_results"]:
            for _agent, result in state["agent_results"].items():
                result.get("evaluation", {})
        if state["errors"]:
            pass


async def _run_direct(args: Any) -> None:
    from regulaforge.agents.domain.enums import AgentRole
    from regulaforge.agents.domain.models import Task
    from regulaforge.agents.interfaces.api import get_orchestrator

    orch = get_orchestrator()
    role = AgentRole(args.agent)
    agent = orch.get_agent(role)
    task = Task(
        title=args.title,
        description=args.description,
        input_data=json.loads(args.input),
    )
    await agent.run(task)



async def _run_approve(args: Any) -> None:
    from regulaforge.agents.interfaces.api import get_orchestrator

    orch = get_orchestrator()
    orch.resolve_human_approval(args.request_id, args.decision, args.notes)


async def _run_status(_args: Any) -> None:
    from regulaforge.agents.interfaces.api import get_orchestrator

    orch = get_orchestrator()
    from regulaforge.agents.domain.enums import AgentRole
    agents = {}
    for role in AgentRole:
        agent = orch.get_agent(role)
        agents[role.value] = {
            "agent_id": agent.agent_id,
            "status": agent.state.status.value,
            "reasoning_steps": len(agent.state.reasoning_trace),
            "tool_calls": len(agent.state.tool_calls),
        }


async def _run_reset(_args: Any) -> None:
    from regulaforge.agents.interfaces.api import get_orchestrator

    orch = get_orchestrator()
    orch.reset_all()


COMMAND_MAP = {
    "workflow": _run_workflow,
    "run": _run_direct,
    "approve": _run_approve,
    "status": _run_status,
    "reset": _run_reset,
}


async def handle_agents_command(args: Any) -> None:
    cmd = getattr(args, "agents_command", None)
    if cmd and cmd in COMMAND_MAP:
        await COMMAND_MAP[cmd](args)
    else:
        pass
