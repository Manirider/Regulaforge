# RegulaForge Architecture

## System Architecture Overview

RegulaForge follows a **Clean Architecture** (Hexagonal Architecture) pattern with strict separation of concerns across four layers:

### Layer Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     Interface Layer                           │
│  REST API (FastAPI)  │  CLI  │  Event Consumers  │  Webhooks │
│  Authentication  │  Rate Limiting  │  Request Validation      │
├──────────────────────────────────────────────────────────────┤
│                    Application Layer                          │
│  Use Cases  │  Domain Services  │  DTOs  │  Port Interfaces  │
│  Orchestration  │  Authorization  │  Event Publishing        │
├──────────────────────────────────────────────────────────────┤
│                      Domain Layer                             │
│  Entities  │  Value Objects  │  Aggregate Roots               │
│  Domain Events  │  Repository Interfaces  │  Domain Services  │
│  Business Rules  │  Invariants  │  Specifications             │
├──────────────────────────────────────────────────────────────┤
│                   Infrastructure Layer                        │
│  PostgreSQL/SQLAlchemy  │  Redis  │  RabbitMQ  │  OpenAI     │
│  Repositories  │  Cache Adapters  │  Message Bus  │  LLM      │
│  Monitoring  │  Logging  │  External API Clients             │
└──────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

#### 1. Domain-Driven Design (DDD)
- **Bounded Contexts**: Regulation Management, Compliance Assessment, Entity Management, Document Processing, AI Analysis, Reporting, Notification
- **Aggregates**: `Regulation`, `ComplianceAssessment`, `AssessableEntity`, `Document`
- **Domain Events**: `RegulationPublished`, `AssessmentCompleted`, `ComplianceGapDetected`
- **Value Objects**: `Address`, `ContactInfo`, `ComplianceLevel`, `RiskLevel`

#### 2. Hexagonal Architecture (Ports & Adapters)
- **Inbound Ports**: Use case interfaces consumed by API controllers
- **Outbound Ports**: Repository interfaces, event publisher, LLM provider
- **Adapters**: SQLAlchemy repositories, RabbitMQ publisher, OpenAI provider

#### 3. Event-Driven Architecture
- Domain events are published to a message bus (RabbitMQ)
- Events enable eventual consistency between bounded contexts
- Dead letter queues for failed event processing
- Delayed delivery for retry logic

#### 4. CQRS-like Separation
- Commands: Create/Update/Delete operations through use cases
- Queries: Search/list operations through dedicated repository methods

### Data Flow

```
Client → API Gateway → Auth Middleware → Route Handler
  → Use Case (validates) → Domain Entity (business rules)
  → Repository (persists) → Database
  → Event Publisher (async) → Message Queue → Consumers
```

## Database Schema

### Core Tables
- `regulations` - Regulatory documents
- `regulation_requirements` - Individual requirements within regulations
- `compliance_assessments` - Assessment records
- `compliance_findings` - Assessment findings
- `assessment_regulations` - Many-to-many link
- `assessable_entities` - Entities subject to assessment
- `documents` - Evidence artifacts
- `audit_logs` - Immutable audit trail

## AI/ML Pipeline

```
Document Upload → Text Extraction → Chunking
  → Embedding Generation → Vector Storage
  → LLM Analysis → Hallucination Detection
  → Confidence Scoring → Result Persistence
```

## Security Architecture

- **Multi-tenancy**: Data isolation via tenant_id on all tables
- **Authentication**: JWT-based with refresh tokens
- **Authorization**: RBAC with fine-grained permissions
- **Encryption**: TLS for transit, AES-256 for data at rest
- **Audit**: Immutable audit log for all state changes
- **Rate Limiting**: Per-tenant and per-endpoint rate limits
