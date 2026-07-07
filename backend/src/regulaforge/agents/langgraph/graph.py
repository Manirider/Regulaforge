from __future__ import annotations

import logging
from typing import Any, Optional

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.constants import END
from langgraph.graph import StateGraph

from regulaforge.agents.application.audit import AuditAgent
from regulaforge.agents.application.base_agent import BaseAgent
from regulaforge.agents.application.clause_drafting import ClauseDraftingAgent
from regulaforge.agents.application.human_approval import HumanApprovalAgent
from regulaforge.agents.application.knowledge_graph import KnowledgeGraphAgent
from regulaforge.agents.application.legal import LegalAgent
from regulaforge.agents.application.monitoring import MonitoringAgent
from regulaforge.agents.application.notification import NotificationAgent
from regulaforge.agents.application.risk_prediction import RiskPredictionAgent
from regulaforge.agents.application.supervisor import SupervisorAgent
from regulaforge.agents.domain.models import Task
from regulaforge.agents.langgraph.nodes import (
    audit_node,
    clause_drafting_node,
    finalize_node,
    human_approval_node,
    knowledge_graph_node,
    legal_node,
    monitoring_node,
    notification_node,
    risk_prediction_node,
    supervisor_node,
)
from regulaforge.agents.langgraph.routing import route_after_agent, route_after_supervisor
from regulaforge.agents.langgraph.state import AgentWorkflowState, create_initial_state

logger = logging.getLogger(__name__)

_NODE_FN_MAP: dict[str, Any] = {
    "supervisor": supervisor_node,
    "monitoring": monitoring_node,
    "knowledge_graph": knowledge_graph_node,
    "risk_prediction": risk_prediction_node,
    "clause_drafting": clause_drafting_node,
    "legal": legal_node,
    "audit": audit_node,
    "notification": notification_node,
    "human_approval": human_approval_node,
}

_AGENT_NAMES = list(_NODE_FN_MAP.keys())

_ROUTE_MAP: dict[str, str] = {
    "monitoring": "monitoring",
    "knowledge_graph": "knowledge_graph",
    "risk_prediction": "risk_prediction",
    "clause_drafting": "clause_drafting",
    "legal": "legal",
    "audit": "audit",
    "notification": "notification",
    "human_approval": "human_approval",
    "finalize": "finalize",
    "escalate": "notification",
    "fail": "finalize",
}

_FINALIZE_OR_NOTIFY: dict[str, str] = {
    "finalize": "finalize",
    "notification": "notification",
}


class AgentFactory:
    @staticmethod
    def create_agents(llm_client: Optional[Any] = None) -> dict[str, BaseAgent]:
        return {
            "supervisor": SupervisorAgent(llm_client=llm_client),
            "monitoring": MonitoringAgent(llm_client=llm_client),
            "knowledge_graph": KnowledgeGraphAgent(llm_client=llm_client),
            "risk_prediction": RiskPredictionAgent(llm_client=llm_client),
            "clause_drafting": ClauseDraftingAgent(llm_client=llm_client),
            "legal": LegalAgent(llm_client=llm_client),
            "audit": AuditAgent(llm_client=llm_client),
            "notification": NotificationAgent(llm_client=llm_client),
            "human_approval": HumanApprovalAgent(llm_client=llm_client),
        }


class GraphBuilder:
    def __init__(self, agents: dict[str, BaseAgent]) -> None:
        self._agents = agents

    def _make_node_fn(self, agent_name: str):
        node_fn = _NODE_FN_MAP[agent_name]

        async def wrapper(state: AgentWorkflowState) -> AgentWorkflowState:
            agent = self._agents[agent_name]
            return await node_fn(state, agent)

        return wrapper

    def build(self) -> StateGraph:
        workflow = StateGraph(AgentWorkflowState)

        for name in _AGENT_NAMES:
            workflow.add_node(name, self._make_node_fn(name))

        workflow.add_node("finalize", finalize_node)

        workflow.add_conditional_edges(
            "supervisor",
            route_after_supervisor,
            _ROUTE_MAP,
        )

        agent_nodes = [
            "monitoring", "knowledge_graph", "risk_prediction",
            "clause_drafting", "legal", "audit",
        ]
        for node_name in agent_nodes:
            workflow.add_conditional_edges(
                node_name,
                route_after_agent,
                _FINALIZE_OR_NOTIFY,
            )

        workflow.add_edge("notification", "finalize")
        workflow.add_edge("human_approval", "finalize")
        workflow.add_edge("finalize", END)

        workflow.set_entry_point("supervisor")

        return workflow


class LangGraphOrchestrator:
    def __init__(
        self,
        llm_client: Optional[Any] = None,
        checkpoint_saver: Optional[BaseCheckpointSaver] = None,
        agent_factory: Optional[AgentFactory] = None,
        graph_builder: Optional[GraphBuilder] = None,
    ) -> None:
        self.llm_client = llm_client
        factory = agent_factory or AgentFactory()
        self._agents = factory.create_agents(llm_client)
        builder = graph_builder or GraphBuilder(self._agents)
        self.checkpoint_saver = checkpoint_saver or MemorySaver()
        self._graph: Optional[StateGraph] = None
        self._compiled: Optional[Any] = None

    def get_agent(self, name: str) -> BaseAgent:
        if name not in self._agents:
            raise KeyError(f"Unknown agent '{name}'. Available: {list(self._agents.keys())}")
        return self._agents[name]

    def build_graph(self) -> StateGraph:
        builder = GraphBuilder(self._agents)
        self._graph = builder.build()
        return self._graph

    def compile(self) -> Any:
        if self._graph is None:
            self.build_graph()
        compiled = self._graph.compile(
            checkpointer=self.checkpoint_saver,
        )
        self._compiled = compiled
        return compiled

    async def run(
        self,
        task: Task,
        thread_id: str = "default",
    ) -> AgentWorkflowState:
        if self._compiled is None:
            self.compile()

        initial_state = create_initial_state(task)
        config = {"configurable": {"thread_id": thread_id}}

        result = await self._compiled.ainvoke(initial_state, config)
        return result

    def resolve_human_approval(
        self,
        thread_id: str,
        decision: dict[str, Any],
    ) -> Any:
        if self._compiled is None:
            raise RuntimeError("Graph not compiled. Call compile() first.")

        config = {"configurable": {"thread_id": thread_id}}
        return self._compiled.resume(config, decision)

    def reset_all(self) -> None:
        for agent in self._agents.values():
            agent.reset_state()
