import asyncio

from regulaforge.agents.application.audit import AuditAgent
from regulaforge.agents.application.clause_drafting import ClauseDraftingAgent
from regulaforge.agents.application.human_approval import HumanApprovalAgent
from regulaforge.agents.application.knowledge_graph import KnowledgeGraphAgent
from regulaforge.agents.application.legal import LegalAgent
from regulaforge.agents.application.monitoring import MonitoringAgent
from regulaforge.agents.application.notification import NotificationAgent
from regulaforge.agents.application.risk_prediction import RiskPredictionAgent
from regulaforge.agents.domain.enums import AgentRole, AgentStatus, TaskStatus
from regulaforge.agents.domain.models import Task


class TestMonitoringAgent:
    def test_role(self):
        agent = MonitoringAgent()
        assert agent.role == AgentRole.MONITORING

    def test_registered_tools(self):
        agent = MonitoringAgent()
        assert "check_agent_health" in agent.tools
        assert "get_system_metrics" in agent.tools
        assert "alert" in agent.tools

    def test_check_health_logic(self):
        agent = MonitoringAgent()
        result = agent._check_health_logic("agent_001")
        assert result["healthy"] is True

    def test_get_metrics_logic(self):
        agent = MonitoringAgent()
        result = agent._get_metrics_logic()
        assert result["status"] == "healthy"

    def test_alert_logic(self):
        agent = MonitoringAgent()
        result = agent._alert_logic("high", "Test alert", "monitoring")
        assert result["severity"] == "high"

    def test_run_no_alerts(self):
        agent = MonitoringAgent()
        task = Task(title="Monitor", description="Check health", input_data={"agents": []})

        async def run():
            return await agent.run(task)

        state = asyncio.run(run())
        assert state.status == AgentStatus.COMPLETED


class TestKnowledgeGraphAgent:
    def test_role(self):
        agent = KnowledgeGraphAgent()
        assert agent.role == AgentRole.KNOWLEDGE_GRAPH

    def test_query_graph_logic(self):
        agent = KnowledgeGraphAgent()
        result = agent._query_graph_logic("RBI")
        assert len(result) > 0

    def test_vector_search_logic(self):
        agent = KnowledgeGraphAgent()
        result = agent._vector_search_logic("banking regulation", top_k=3)
        assert len(result) == 3

    def test_get_relationships_logic(self):
        agent = KnowledgeGraphAgent()
        result = agent._get_relationships_logic("RBI")
        assert len(result) == 2

    def test_run(self):
        agent = KnowledgeGraphAgent()
        task = Task(title="Query", description="Find regulations", input_data={"query": "RBI", "query_type": "graph"})

        async def run():
            return await agent.run(task)

        state = asyncio.run(run())
        assert state.status == AgentStatus.COMPLETED


class TestRiskPredictionAgent:
    def test_role(self):
        agent = RiskPredictionAgent()
        assert agent.role == AgentRole.RISK_PREDICTION

    def test_assess_risk_logic(self):
        agent = RiskPredictionAgent()
        result = agent._assess_risk_logic("New regulation", "banking")
        assert "risk_level" in result

    def test_predict_outcome_logic(self):
        agent = RiskPredictionAgent()
        result = agent._predict_outcome_logic("Comply with regulation", "banking context")
        assert "predicted_outcome" in result

    def test_get_risk_factors_logic(self):
        agent = RiskPredictionAgent()
        result = agent._get_risk_factors_logic("Compliance scenario")
        assert len(result) == 3

    def test_run(self):
        agent = RiskPredictionAgent()
        task = Task(title="Risk", description="Assess compliance risk", input_data={"scenario": "New banking regulation"})

        async def run():
            return await agent.run(task)

        state = asyncio.run(run())
        assert state.status == AgentStatus.COMPLETED


class TestClauseDraftingAgent:
    def test_role(self):
        agent = ClauseDraftingAgent()
        assert agent.role == AgentRole.CLAUSE_DRAFTING

    def test_draft_clause_logic(self):
        agent = ClauseDraftingAgent()
        result = agent._draft_clause_logic("compliance", "Capital adequacy", "India")
        assert "clause_text" in result
        assert "COMPLIANCE" in result["clause_text"]

    def test_review_clause_logic(self):
        agent = ClauseDraftingAgent()
        result = agent._review_clause_logic("Existing clause", "Make clearer")
        assert "REVISED" in result["clause_text"]

    def test_validate_clause_logic(self):
        agent = ClauseDraftingAgent()
        result = agent._validate_clause_logic("Some clause text")
        assert result["valid"] is True

    def test_run(self):
        agent = ClauseDraftingAgent()
        task = Task(title="Draft", description="Draft compliance clause", input_data={"clause_type": "reporting"})

        async def run():
            return await agent.run(task)

        state = asyncio.run(run())
        assert state.status == AgentStatus.COMPLETED


class TestLegalAgent:
    def test_role(self):
        agent = LegalAgent()
        assert agent.role == AgentRole.LEGAL

    def test_analyze_regulation_logic(self):
        agent = LegalAgent()
        result = agent._analyze_regulation_logic("Regulation text")
        assert "key_requirements" in result

    def test_check_compliance_logic(self):
        agent = LegalAgent()
        result = agent._check_compliance_logic("Some scenario")
        assert result["compliant"] is True

    def test_get_legal_opinion_logic(self):
        agent = LegalAgent()
        result = agent._get_legal_opinion_logic("Is this compliant?")
        assert "opinion" in result

    def test_run(self):
        agent = LegalAgent()
        task = Task(title="Legal", description="Legal analysis request")

        async def run():
            return await agent.run(task)

        state = asyncio.run(run())
        assert state.status == AgentStatus.COMPLETED


class TestAuditAgent:
    def test_role(self):
        agent = AuditAgent()
        assert agent.role == AgentRole.AUDIT

    def test_conduct_audit_logic(self):
        agent = AuditAgent()
        result = agent._conduct_audit_logic("compliance", "full")
        assert result["status"] == "completed"

    def test_generate_findings_logic(self):
        agent = AuditAgent()
        result = agent._generate_findings_logic("audit data")
        assert "critical_count" in result

    def test_recommend_actions_logic(self):
        agent = AuditAgent()
        result = agent._recommend_actions_logic("findings data", "high")
        assert len(result["actions"]) > 0

    def test_run(self):
        agent = AuditAgent()
        task = Task(title="Audit", description="Conduct compliance audit")

        async def run():
            return await agent.run(task)

        state = asyncio.run(run())
        assert state.status == AgentStatus.COMPLETED


class TestNotificationAgent:
    def test_role(self):
        agent = NotificationAgent()
        assert agent.role == AgentRole.NOTIFICATION

    def test_send_notification_logic(self):
        agent = NotificationAgent()
        result = agent._send_notification_logic(["user@test.com"], "Test", "Body", "high", "email")
        assert result["delivered"] is True

    def test_get_history_logic(self):
        agent = NotificationAgent()
        result = agent._get_history_logic("user@test.com", limit=3)
        assert len(result) == 3

    def test_update_preferences_logic(self):
        agent = NotificationAgent()
        result = agent._update_preferences_logic("user", {"email": True})
        assert result["updated"] is True

    def test_run(self):
        agent = NotificationAgent()
        task = Task(title="Notify", description="Send notification", input_data={"recipients": ["test@test.com"]})

        async def run():
            return await agent.run(task)

        state = asyncio.run(run())
        assert state.status == AgentStatus.COMPLETED


class TestHumanApprovalAgent:
    def test_role(self):
        agent = HumanApprovalAgent()
        assert agent.role == AgentRole.HUMAN_APPROVAL

    def test_request_approval_logic(self):
        agent = HumanApprovalAgent()
        result = agent._request_approval_logic("task_1", "Approve?", "Details", ["approve", "reject"])
        assert result["status"] == "pending"

    def test_check_status_logic(self):
        agent = HumanApprovalAgent()
        agent._pending_approvals["req_1"] = {"status": "pending"}
        result = agent._check_status_logic("req_1")
        assert result["status"] == "pending"

    def test_approve_logic(self):
        agent = HumanApprovalAgent()
        agent._request_approval_logic("task_1", "Test", "Details", ["approve"])
        request_id = list(agent._pending_approvals.keys())[0]
        result = agent._approve_logic(request_id, "Looks good")
        assert result["decision"] == "approved"

    def test_reject_logic(self):
        agent = HumanApprovalAgent()
        agent._request_approval_logic("task_1", "Test", "Details", ["reject"])
        request_id = list(agent._pending_approvals.keys())[0]
        result = agent._reject_logic(request_id, "Not ready")
        assert result["decision"] == "rejected"

    def test_resolve_approval(self):
        agent = HumanApprovalAgent()
        agent._pending_approvals["req_1"] = {"status": "pending", "task_id": "t1"}
        result = agent.resolve_approval("req_1", "approved", "Approved by manager")
        assert result["decision"] == "approved"

    def test_run_creates_approval_request(self):
        agent = HumanApprovalAgent()
        task = Task(title="Approve", description="Need approval for clause")

        async def run():
            return await agent.run(task)

        state = asyncio.run(run())
        assert state.status == AgentStatus.WAITING_FOR_INPUT
        assert task.status == TaskStatus.WAITING_FOR_HUMAN
