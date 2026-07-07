# Event-Driven Architecture

## Overview

RegulaForge uses event-driven architecture for asynchronous communication between bounded contexts. Domain events are published when aggregates change state, enabling loose coupling, eventual consistency, and auditability.

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Publisher   │────▶│  Event Bus   │────▶│  Consumer    │
│  (Use Case)  │     │  (RabbitMQ)  │     │  (Service)   │
└──────────────┘     └──────────────┘     └──────────────┘
                           │
                    ┌──────┴──────┐
                    │             │
                    ▼             ▼
           ┌────────────┐  ┌────────────┐
           │   DLQ      │  │   Retry    │
           │ (.dlq)     │  │ (.retry)   │
           └────────────┘  └────────────┘
```

## Event Catalog

### Regulation Events

| Event | Type | Published By | Payload |
|---|---|---|---|
| **RegulationCreated** | `regulation.created` | `CreateRegulationUseCase` | `regulation_id, code, title` |
| **RegulationUpdated** | `regulation.updated` | `UpdateRegulationUseCase` | `regulation_id, code, changes` |
| **RegulationPublished** | `regulation.published` | `Regulation.publish()` | `regulation_id, code, title` |
| **RegulationArchived** | `regulation.archived` | `Regulation.archive()` | `regulation_id, code` |
| **RegulationSuperseded** | `regulation.superseded` | `Regulation.supersede()` | `regulation_id, code, new_regulation_id` |

### Assessment Events

| Event | Type | Published By | Payload |
|---|---|---|---|
| **AssessmentRequested** | `assessment.requested` | `CreateAssessmentUseCase` | `assessment_id, entity_id` |
| **AssessmentStarted** | `assessment.started` | `ComplianceAssessment.start()` | `assessment_id, entity_id` |
| **AssessmentCompleted** | `assessment.completed` | `ComplianceAssessment.complete()` | `assessment_id, entity_id, score, finding_count` |
| **AssessmentApproved** | `assessment.approved` | `ComplianceAssessment.approve()` | `assessment_id, reviewer_id` |
| **ComplianceGapDetected** | `compliance.gap_detected` | `AddFindingUseCase` | `assessment_id, finding_id, requirement_code, risk_level` |

### Entity Events

| Event | Type | Published By | Payload |
|---|---|---|---|
| **EntityCreated** | `entity.created` | `CreateEntityUseCase` | `entity_id, name, entity_type, tenant_id` |
| **EntityUpdated** | `entity.updated` | `UpdateEntityUseCase` | `entity_id, name, changes` |
| **EntityDeactivated** | `entity.deactivated` | `AssessableEntity.deactivate()` | `entity_id, name` |
| **EntityActivated** | `entity.activated` | `AssessableEntity.activate()` | `entity_id, name` |

### Document Events

| Event | Type | Published By | Payload |
|---|---|---|---|
| **DocumentUploaded** | `document.uploaded` | `UploadDocumentUseCase` | `document_id, file_name, artifact_type, tenant_id` |
| **DocumentVerified** | `document.verified` | `Document.verify()` | `document_id, file_name, verified_by` |
| **DocumentDeleted** | `document.deleted` | `DeleteDocumentUseCase` | `document_id, file_name` |

### User Events

| Event | Type | Published By | Payload |
|---|---|---|---|
| **UserCreated** | `user.created` | (User registration) | `user_id, email, full_name, tenant_id` |
| **UserLoggedIn** | `user.logged_in` | `User.record_login()` | `user_id, email, ip_address` |
| **UserLocked** | `user.locked` | `User.record_failed_attempt()` | `user_id, email, failed_attempts, locked_until` |
| **UserPasswordChanged** | `user.password_changed` | `User.set_password_hash()` | `user_id, email` |

### Additional Event Types (Constants)
```python
class EventType(str, Enum):
    # Risk events
    RISK_ESCALATED = "risk.escalated"
    REMEDIATION_REQUIRED = "remediation.required"
    REMEDIATION_COMPLETED = "remediation.completed"

    # Processing events
    DOCUMENT_PROCESSED = "document.processed"
    REPORT_GENERATED = "report.generated"
    ALERT_TRIGGERED = "alert.triggered"

    # System events
    AUDIT_TRAIL_CREATED = "audit_trail.created"
    TENANT_CONFIGURED = "tenant.configured"
    USER_INVITED = "user.invited"
    USER_ROLE_CHANGED = "user.role_changed"
    THRESHOLD_BREACHED = "threshold.breached"
    INTEGRATION_FAILED = "integration.failed"
```

## Event Flows for Key Processes

### Regulation Publishing Flow
```
[Use Case]                    [Domain Entity]              [Event Bus]
    │                              │                            │
    │  PublishRegulationUseCase    │                            │
    │  ──────────────────────────▶│                            │
    │                              │  regulation.publish()     │
    │                              │  ───► validates status    │
    │                              │  ───► sets ACTIVE         │
    │                              │  ───► register_event()    │
    │                              │                            │
    │                            │  RegulationPublished        │
    │◀───────────────────────────│  ──────────────────────────▶│
    │                              │                            │
    │  save()                      │                            │
    │  ──────────────────────────▶│                            │
    │                              │                            │
    │                              │  clear_events()            │
    │  return Regulation           │  ───► publish to bus      │
    │◀───────────────────────────│                            │
    │                              │                            │
    │                              │             ┌─────────────┴──────┐
    │                              │             │                    │
    │                              │             ▼                    ▼
    │                              │     ┌──────────────┐    ┌──────────────┐
    │                              │     │  Audit Log   │    │  Search      │
    │                              │     │  (record     │    │  Index       │
    │                              │     │   action)    │    │  (update)    │
    │                              │     └──────────────┘    └──────────────┘
```

### Assessment Completion Flow
```
[Assessor]           [API]               [Domain]              [Event Bus]
    │                  │                    │                       │
    │ POST /complete   │                    │                       │
    │ {score: 72.5}    │                    │                       │
    │─────────────────▶│                    │                       │
    │                  │  CompleteUseCase   │                       │
    │                  │ ──────────────────▶│                       │
    │                  │                    │  assessment.complete()│
    │                  │                    │  ──► validate status  │
    │                  │                    │  ──► set score        │
    │                  │                    │  ──► PENDING_REVIEW   │
    │                  │                    │  ──► register event   │
    │                  │                    │                       │
    │                  │                    │  AssessmentCompleted  │
    │                  │                    │  ────────────────────▶│
    │                  │                    │                       │
    │                  │                    │             ┌─────────┴──────────┐
    │                  │                    │             │                    │
    │                  │                    │             ▼                    ▼
    │                  │                    │     ┌──────────────┐    ┌──────────────┐
    │  Response        │                    │     │  Notify      │    │  Audit Log   │
    │◀────────────────│                    │     │  Reviewer    │    │  (record)    │
    │  200 OK          │                    │     └──────────────┘    └──────────────┘
```

## Domain Event Base Class

```python
class DomainEvent:
    """Base for all domain events with tracing metadata."""

    event_id: UUID        # Unique event identifier
    event_type: str       # Dot-notation type (e.g., "regulation.published")
    aggregate_id: UUID    # ID of the source aggregate
    aggregate_type: str   # Type of the source aggregate
    data: Dict            # Event-specific payload
    occurred_at: datetime # UTC timestamp
    correlation_id: str   # Distributed tracing correlation ID
```

### Event Publishing Flow in Use Cases
```python
class CreateRegulationUseCase(UseCase):
    async def execute(self, ...):
        # 1. Create domain entity
        regulation = Regulation(...)

        # 2. Entity registers events internally
        #    (regulation.register_event(RegulationCreated(...)))

        # 3. Persist aggregate (saves events in transaction)
        saved = await self._regulation_repo.save(regulation)

        # 4. Publish events after successful persistence
        await self._publish_events(saved)
        # This calls saved.clear_events() and publishes to message bus

        return saved
```

## Message Broker Configuration

### RabbitMQ Setup
```python
# Configuration
settings.broker.url = "amqp://guest:guest@localhost:5672/"
settings.broker.max_retries = 3
settings.broker.prefetch_count = 10
```

### Exchange and Queue Structure
```
Exchange: regulaforge (topic)
  │
  ├── Queue: regulation.events
  │     ├── Binding: regulation.#
  │     └── Consumers: AuditLogService, SearchIndexService
  │
  ├── Queue: assessment.events
  │     ├── Binding: assessment.#
  │     └── Consumers: NotificationService, ReportService
  │
  ├── Queue: compliance.events
  │     ├── Binding: compliance.#
  │     └── Consumers: EscalationService, RemediationTracker
  │
  ├── Queue: entity.events
  │     ├── Binding: entity.#
  │     └── Consumers: AuditLogService
  │
  ├── Queue: document.events
  │     ├── Binding: document.#
  │     └── Consumers: AIProcessingService
  │
  ├── Queue: user.events
  │     ├── Binding: user.#
  │     └── Consumers: AuditLogService, SecurityAlertService
  │
  └── Queue: all.events
        ├── Binding: #
        └── Consumers: EventStore, AuditTrailService
```

### Dead Letter Queues
```
Each primary queue has a corresponding DLQ:
  regulation.events.dlq
  assessment.events.dlq
  entity.events.dlq
  document.events.dlq
  user.events.dlq
```

### Retry Mechanism
```python
# Configuration constants
DLQ_SUFFIX = ".dlq"
RETRY_SUFFIX = ".retry"
MAX_RETRY_DELAY_SECONDS = 3600
MAX_RETRY_ATTEMPTS = 3
```

## Event Versioning Strategy

### Schema Evolution
Events are versioned using a `event_version` field in the payload. Backward compatibility is maintained for at least 2 major versions.

### Versioning Policy
```python
class RegulationCreated(DomainEvent):
    """v1 (2026-07-04): Initial schema
       v2 (2026-10-01): Added category field
    """
    event_version = 2  # Current version

    def __init__(self, regulation_id, code, title, category=None, **kwargs):
        data = {
            "event_version": self.event_version,
            "code": code,
            "title": title,
        }
        if category:
            data["category"] = category
        super().__init__(
            event_type="regulation.created",
            aggregate_id=regulation_id,
            aggregate_type="regulation",
            data=data,
            **kwargs,
        )
```

### Consumer Compatibility
- Consumers MUST tolerate missing optional fields
- Consumers MUST ignore unknown fields
- Breaking changes use a new `event_type` with a v2 suffix (e.g., `regulation.created.v2`)
- Deprecated event types are supported for 6 months

## Error Handling and DLQ

### Error Classification

| Error Type | Retry Strategy | DLQ Action |
|---|---|---|
| **Transient** (network timeout, DB deadlock) | Retry 3x with exponential backoff | After max retries → DLQ |
| **Business** (validation failure) | No retry | Immediate DLQ |
| **Poison Message** (malformed payload) | No retry | Immediate DLQ + alert |

### Retry with Exponential Backoff
```python
async def process_with_retry(event, max_retries=3):
    for attempt in range(max_retries):
        try:
            await handle_event(event)
            return
        except TransientError:
            if attempt < max_retries - 1:
                delay = 2 ** attempt  # 1s, 2s, 4s
                await asyncio.sleep(delay)
            else:
                await send_to_dlq(event, "Max retries exceeded")
        except BusinessError as e:
            await send_to_dlq(event, str(e))
            return
```

### DLQ Message Format
```json
{
  "original_event": { ... },
  "error": {
    "type": "TransientError",
    "message": "Database connection timeout",
    "timestamp": "2026-07-04T12:00:00Z",
    "retry_count": 3
  },
  "metadata": {
    "original_queue": "assessment.events",
    "failed_at": "2026-07-04T12:00:05Z",
    "correlation_id": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

### DLQ Monitoring
- Alert when DLQ depth exceeds threshold (e.g., > 100 messages)
- Scheduled DLQ reprocessing job
- Manual DLQ inspection via RabbitMQ management UI
- DLQ events logged to audit trail

## Exactly-Once Processing Semantics

### Approach: Idempotent Consumers + Deduplication

RegulaForge achieves **at-least-once delivery** with **idempotent consumers** rather than true exactly-once, which provides the best balance of performance and reliability.

### Consumer Idempotency
```python
class AssessmentEventConsumer:
    async def handle_assessment_completed(self, event):
        # Check if already processed (idempotency key)
        event_id = event["event_id"]
        already_processed = await self._event_store.exists(event_id)
        if already_processed:
            logger.info(f"Event {event_id} already processed, skipping")
            return

        # Process event
        await self._process(event)

        # Mark as processed
        await self._event_store.mark_processed(event_id)
```

### Deduplication Key
- Primary key: `event_id` (UUID, globally unique)
- Event store table records all processed events
- TTL-based cleanup of processed event IDs (configurable, default 7 days)
- Transactional outbox pattern ensures events are published only when the aggregate is persisted

### Ordering Guarantees
- Events from a single aggregate root are published in order
- No global ordering across aggregates (intentional for scalability)
- Consumer can use `occurred_at` timestamp for ordering if needed
- Correlation ID ties related events across aggregates together
