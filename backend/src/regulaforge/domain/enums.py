"""Domain enumerations for RegulaForge."""

from enum import Enum


class RegulationStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    AMENDED = "amended"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"
    RETIRED = "retired"


class RegulationCategory(str, Enum):
    DATA_PROTECTION = "data_protection"
    PRIVACY = "privacy"
    FINANCIAL = "financial"
    ENVIRONMENTAL = "environmental"
    HEALTH_SAFETY = "health_safety"
    LABOR = "labor"
    CORPORATE_GOVERNANCE = "corporate_governance"
    ANTI_MONEY_LAUNDERING = "anti_money_laundering"
    KNOW_YOUR_CUSTOMER = "know_your_customer"
    CYBERSECURITY = "cybersecurity"
    AI_GOVERNANCE = "ai_governance"
    TRADE_COMPLIANCE = "trade_compliance"
    INDUSTRY_SPECIFIC = "industry_specific"
    GENERAL = "general"


class RegulationJurisdiction(str, Enum):
    GLOBAL = "global"
    EU = "eu"
    US_FEDERAL = "us_federal"
    US_STATE = "us_state"
    UK = "uk"
    APAC = "apac"
    EMEA = "emea"
    LATAM = "latam"
    AFRICA = "africa"
    COUNTRY_SPECIFIC = "country_specific"


class ComplianceLevel(str, Enum):
    FULLY_COMPLIANT = "fully_compliant"
    PARTIALLY_COMPLIANT = "partially_compliant"
    NON_COMPLIANT = "non_compliant"
    NOT_APPLICABLE = "not_applicable"
    UNDER_REVIEW = "under_review"
    INSUFFICIENT_DATA = "insufficient_data"


class RiskLevel(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NEGLIGIBLE = "negligible"


class EntityType(str, Enum):
    ORGANIZATION = "organization"
    DEPARTMENT = "department"
    PRODUCT = "product"
    SERVICE = "service"
    PROCESS = "process"
    SYSTEM = "system"
    DATA_FLOW = "data_flow"
    THIRD_PARTY = "third_party"
    APPLICATION = "application"
    INFRASTRUCTURE = "infrastructure"


class ArtifactType(str, Enum):
    DOCUMENT = "document"
    POLICY = "policy"
    PROCEDURE = "procedure"
    LOG = "log"
    REPORT = "report"
    CERTIFICATE = "certificate"
    AUDIT_TRAIL = "audit_trail"
    SCREENSHOT = "screenshot"
    CONFIGURATION = "configuration"
    CODE_REPOSITORY = "code_repository"
    INTERVIEW_NOTE = "interview_note"
    OTHER = "other"


class AssessmentStatus(str, Enum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    PENDING_REVIEW = "pending_review"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ON_HOLD = "on_hold"


class NotificationPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class NotificationChannel(str, Enum):
    EMAIL = "email"
    SLACK = "slack"
    WEBHOOK = "webhook"
    IN_APP = "in_app"
    SMS = "sms"
    PAGER_DUTY = "pager_duty"


class AuditAction(str, Enum):
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    EXPORT = "export"
    IMPORT = "import"
    LOGIN = "login"
    LOGOUT = "logout"
    ASSESSMENT_STARTED = "assessment_started"
    ASSESSMENT_COMPLETED = "assessment_completed"
    ASSESSMENT_APPROVED = "assessment_approved"
    ASSESSMENT_REJECTED = "assessment_rejected"
    DOCUMENT_UPLOADED = "document_uploaded"
    DOCUMENT_VERIFIED = "document_verified"
    REPORT_GENERATED = "report_generated"
    ALERT_TRIGGERED = "alert_triggered"
    CONFIGURATION_CHANGED = "configuration_changed"
    ROLE_ASSIGNED = "role_assigned"
    ROLE_REVOKED = "role_revoked"
    API_KEY_ROTATED = "api_key_rotated"


class PromptTemplateType(str, Enum):
    REGULATION_ANALYSIS = "regulation_analysis"
    COMPLIANCE_ASSESSMENT = "compliance_assessment"
    RISK_EVALUATION = "risk_evaluation"
    DOCUMENT_SUMMARIZATION = "document_summarization"
    ENTITY_EXTRACTION = "entity_extraction"
    REQUIREMENT_DECOMPOSITION = "requirement_decomposition"
    GAP_ANALYSIS = "gap_analysis"
    REPORT_GENERATION = "report_generation"
    REMEDIATION_SUGGESTION = "remediation_suggestion"
    AUDIT_QUESTION_GENERATION = "audit_question_generation"


class EventType(str, Enum):
    REGULATION_CREATED = "regulation.created"
    REGULATION_UPDATED = "regulation.updated"
    REGULATION_ARCHIVED = "regulation.archived"
    ASSESSMENT_REQUESTED = "assessment.requested"
    ASSESSMENT_STARTED = "assessment.started"
    ASSESSMENT_COMPLETED = "assessment.completed"
    ASSESSMENT_APPROVED = "assessment.approved"
    COMPLIANCE_GAP_DETECTED = "compliance.gap_detected"
    RISK_ESCALATED = "risk.escalated"
    REMEDIATION_REQUIRED = "remediation.required"
    REMEDIATION_COMPLETED = "remediation.completed"
    DOCUMENT_PROCESSED = "document.processed"
    DOCUMENT_VERIFIED = "document.verified"
    REPORT_GENERATED = "report.generated"
    ALERT_TRIGGERED = "alert.triggered"
    AUDIT_TRAIL_CREATED = "audit_trail.created"
    TENANT_CONFIGURED = "tenant.configured"
    USER_INVITED = "user.invited"
    USER_ROLE_CHANGED = "user.role_changed"
    THRESHOLD_BREACHED = "threshold.breached"
    INTEGRATION_FAILED = "integration.failed"


__all__ = [
    "RegulationStatus",
    "RegulationCategory",
    "RegulationJurisdiction",
    "ComplianceLevel",
    "RiskLevel",
    "EntityType",
    "ArtifactType",
    "AssessmentStatus",
    "NotificationPriority",
    "NotificationChannel",
    "AuditAction",
    "PromptTemplateType",
    "EventType",
]
