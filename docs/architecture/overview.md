# System Architecture Overview

## High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────────────────────────┐
│                                  CLIENT LAYER                                        │
│                                                                                      │
│  ┌──────────┐  ┌───────────┐  ┌──────────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │  Web UI  │  │  Mobile   │  │  CLI / Admin  │  │  3rd-Pty │  │  Event Bridge   │  │
│  │ (React)  │  │   (PWA)   │  │   Commands   │  │  Integr.  │  │  (Webhook/API)  │  │
│  └─────┬────┘  └─────┬─────┘  └──────┬───────┘  └─────┬────┘  └────────┬─────────┘  │
│        │             │               │                │               │            │
├────────┼─────────────┼───────────────┼────────────────┼───────────────┼────────────┤
│        ▼             ▼               ▼                ▼               ▼            │
│  ┌──────────────────────────────────────────────────────────────────────────────┐  │
│  │                         API GATEWAY & EDGE                                    │  │
│  │                                                                              │  │
│  │  ┌─────────────┐  ┌────────────────┐  ┌───────────────┐  ┌───────────────┐  │  │
│  │  │   Rate      │  │   Auth/SSL     │  │   Request     │  │   Response    │  │  │
│  │  │   Limiter   │  │   Termination  │  │   Validation  │  │   Caching     │  │  │
│  │  └─────────────┘  └────────────────┘  └───────────────┘  └───────────────┘  │  │
│  └──────────────────────────────────────────────────────────────────────────────┘  │
├────────────────────────────────────────────────────────────────────────────────────┤
│                                INTERFACE LAYER                                      │
│                                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │  REST API (FastAPI)                                                         │   │
│  │  ┌───────────┐ ┌───────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────┐ │   │
│  │  │Regulations│ │Assessments│ │Entities  │ │Documents │ │ Health/Auth    │ │   │
│  │  │ Router    │ │ Router    │ │ Router   │ │ Router   │ │ Endpoints      │ │   │
│  │  └───────────┘ └───────────┘ └──────────┘ └──────────┘ └────────────────┘ │   │
│  │                                                                           │   │
│  │  ┌────────────────────────────────────────────────────────────────────┐   │   │
│  │  │ Middleware: Auth  |  Logging  |  Error Handler  |  CORS  |  CSP    │   │   │
│  │  └────────────────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
├────────────────────────────────────────────────────────────────────────────────────┤
│                               APPLICATION LAYER                                     │
│                                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │  Use Cases (Orchestration Layer)                                            │   │
│  │  ┌────────────────┐ ┌──────────────────┐ ┌──────────────┐ ┌──────────────┐ │   │
│  │  │Regulation UC   │ │Assessment UC     │ │Entity UC     │ │Document UC   │ │   │
│  │  │- Create        │ │- Create          │ │- Create      │ │- Upload      │ │   │
│  │  │- Update        │ │- Start           │ │- Update      │ │- Verify      │ │   │
│  │  │- Publish       │ │- Add Finding     │ │- Search      │ │- Search      │ │   │
│  │  │- Add Req       │ │- Complete        │ │- Hierarchy   │ │- Delete      │ │   │
│  │  │- Search        │ │- Approve         │ │- Deactivate  │ │              │ │   │
│  │  └────────────────┘ └──────────────────┘ └──────────────┘ └──────────────┘ │   │
│  │                                                                             │   │
│  │  Port Interfaces (Inbound/Outbound)                                         │   │
│  │  ┌────────────────────────────────────────────────────────────────────┐   │   │
│  │  │ Repository Interfaces  |  Event Publisher  |  LLM Provider Ports   │   │   │
│  │  └────────────────────────────────────────────────────────────────────┘   │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
├────────────────────────────────────────────────────────────────────────────────────┤
│                                 DOMAIN LAYER                                        │
│                                                                                     │
│  ┌─────────────────────────────────────────────────────────────────────────────┐   │
│  │  ┌───────────────┐  ┌──────────────────┐  ┌──────────────────────────────┐ │   │
│  │  │  Entities      │  │  Value Objects   │  │  Domain Events               │ │   │
│  │  │  - Regulation  │  │  - Address       │  │  - RegulationCreated         │ │   │
│  │  │  - Compliance  │  │  - Contact       │  │  - RegulationPublished       │ │   │
│  │  │    Assessment  │  │  - Permission    │  │  - AssessmentStarted         │ │   │
│  │  │  - Assessable  │  │  - ComplianceLvl │  │  - AssessmentCompleted       │ │   │
│  │  │    Entity      │  │  - RiskLevel      │  │  - ComplianceGapDetected    │ │   │
│  │  │  - Document    │  │  - ArtifactType   │  │  - DocumentUploaded          │ │   │
│  │  │  - User        │  │                   │  │  - UserLoggedIn              │ │   │
│  │  │  - Tenant      │  │                   │  │  - UserLocked                │ │   │
│  │  │  - Role        │  │                   │  │                              │ │   │
│  │  └───────────────┘  └──────────────────┘  └──────────────────────────────┘ │   │
│  │                                                                             │   │
│  │  Business Rules & Invariants                                                │   │
│  │  - Password policy enforcement                                              │   │
│  │  - Regulation lifecycle (Draft->Active->Superseded->Retired)               │   │
│  │  - Assessment workflow (Scheduled->InProgress->PendingReview->Completed)   │   │
│  │  - Compliance scoring (0-100 scale)                                         │   │
│  │  - Entity hierarchy validation                                              │   │
│  └─────────────────────────────────────────────────────────────────────────────┘   │
├────────────────────────────────────────────────────────────────────────────────────┤
│                              INFRASTRUCTURE LAYER                                    │
│                                                                                     │
│  ┌──────────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐  ┌────────────┐   │
│  │  PostgreSQL  │  │  Redis   │  │ RabbitMQ │  │  OpenAI /    │  │ File       │   │
│  │  + SQLAlch.  │  │  Cache   │  │  Bus     │  │  Anthropic   │  │ Storage    │   │
│  │  2.0 Async   │  │          │  │  DLQ     │  │  LLM Prov.   │  │ (S3/Local) │   │
│  └──────┬───────┘  └────┬─────┘  └────┬─────┘  └──────┬───────┘  └──────┬─────┘   │
│         │               │             │               │                │         │
│         ▼               ▼             ▼               ▼                ▼         │
│  ┌────────────────────────────────────────────────────────────────────────────┐  │
│  │  Adapters: Repository Impls  |  Cache Adapter  |  Event Publisher  |  AI  │  │
│  └────────────────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────────────────┘
```

## Bounded Context Map

| Bounded Context | Responsibilities | Aggregate Roots | Events Published |
|---|---|---|---|
| **Regulation Management** | Ingest, decompose, version regulations | `Regulation` | `regulation.created`, `regulation.published`, `regulation.updated`, `regulation.archived`, `regulation.superseded` |
| **Compliance Assessment** | Assess entities, track findings, score risk | `ComplianceAssessment` | `assessment.requested`, `assessment.started`, `assessment.completed`, `assessment.approved`, `compliance.gap_detected` |
| **Entity Management** | Register and organize assessable entities | `AssessableEntity` | `entity.created`, `entity.updated`, `entity.deactivated`, `entity.activated` |
| **Document Management** | Upload, verify, process evidence artifacts | `Document` | `document.uploaded`, `document.verified`, `document.deleted` |
| **Identity & Access** | Users, tenants, roles, authentication | `User`, `Tenant`, `Role` | `user.created`, `user.logged_in`, `user.locked`, `user.password_changed` |
| **AI Analysis** | Regulation analysis, compliance eval, gap analysis | - | - |
| **Audit** | Immutable audit trail for compliance | `AuditEntry` | - |

## Key Architectural Decisions (ADR Summary)

| ID | Decision | Rationale |
|---|---|---|
| **ADR-001** | **Clean/Hexagonal Architecture** | Strict separation of concerns; domain core has zero external dependencies; adapters are swappable without business logic changes |
| **ADR-002** | **Python 3.11+ with FastAPI** | Async-native performance, automatic OpenAPI docs, Pydantic validation, strong AI/ML ecosystem |
| **ADR-003** | **Domain-Driven Design** | Ubiquitous language aligns domain experts and developers; aggregate roots enforce invariants; domain events enable eventual consistency |
| **ADR-004** | **PostgreSQL 16 + SQLAlchemy 2.0 Async** | ACID compliance for financial-grade data; JSONB for flexible metadata; full-text search; async ORM for non-blocking I/O |
| **ADR-005** | **RabbitMQ for Event Bus** | Reliable message delivery, delayed retries, dead-letter queues, mature and stable |
| **ADR-006** | **Redis for Caching and Rate Limiting** | Sub-millisecond reads, atomic Lua scripting for token bucket rate limiter, session store |
| **ADR-007** | **Provider-Agnostic AI Layer** | Port/adapter pattern for LLM providers (OpenAI, Anthropic, Azure); easy swap without domain impact |
| **ADR-008** | **JWT + RBAC for Auth** | Stateless authentication scales horizontally; fine-grained permissions at resource:action level |
| **ADR-009** | **Multi-Tenant Data Isolation** | Tenant ID on all tables (shared schema, isolated data); logical separation without per-tenant databases |
| **ADR-010** | **CQRS-lite via Separate Queries** | Commands go through use case pipeline; queries use dedicated repository search methods; no separate read model needed initially |

## Technology Stack

| Component | Technology | Version | Rationale |
|---|---|---|---|
| **Language** | Python | 3.11+ | AI/ML ecosystem maturity, async support, broad enterprise adoption |
| **API Framework** | FastAPI | 0.104+ | Async-native, automatic OpenAPI generation, Pydantic v2 validation |
| **ORM** | SQLAlchemy | 2.0+ | Mature, async support, enterprise-proven, migrations via Alembic |
| **Database** | PostgreSQL | 16+ | ACID compliance, JSONB, full-text search, row-level security |
| **Cache** | Redis | 7+ | Sub-millisecond reads, atomic Lua scripting, pub/sub |
| **Message Broker** | RabbitMQ | 3.12+ | AMQP 0-9-1 standard, delayed messages, DLQ, management UI |
| **AI Provider** | OpenAI / Anthropic | Provider-agnostic | Market-leading models, embedding API, pluggable via adapter |
| **Auth** | PyJWT + bcrypt | - | Industry-standard JWT with refresh tokens, bcrypt hashing |
| **Container** | Docker | 24+ | Reproducible builds, CI/CD, dev/prod parity |
| **Orchestration** | Kubernetes | 1.28+ | Production-grade orchestration, auto-scaling, rolling updates |
| **Monitoring** | Prometheus + Grafana | - | CNCF-standard metrics, rich dashboards, alerting |
| **Tracing** | OpenTelemetry | - | Vendor-neutral distributed tracing, span context propagation |
| **Error Tracking** | Sentry | - | Real-time error monitoring, performance tracking |

## Security Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                        SECURITY ARCHITECTURE                       │
├────────────────────────────────────────────────────────────────────┤
│  Layer 1: Transport Security                                       │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  TLS 1.3  |  HSTS  |  CSP Headers  |  CORS  |  Host Filter  │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  Layer 2: Authentication                                           │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  JWT (HS256) Access + Refresh Tokens  |  Bearer Scheme       │  │
│  │  Token Claims: sub, tenant_id, roles, jti, exp, iat         │  │
│  │  Access Token TTL: 30 min  |  Refresh Token TTL: 7 days     │  │
│  │  Password Policy: 12+ chars, upper, lower, digit, special   │  │
│  │  Account Lockout: 5 failed attempts -> 15 min lock          │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  Layer 3: Authorization                                            │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  RBAC with Fine-Grained Permissions (resource:action)        │  │
│  │  System Roles: admin, compliance_officer, auditor, viewer    │  │
│  │  Custom Roles: Tenant-defined role compositions               │  │
│  │  Superuser bypass for platform administrators                 │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  Layer 4: Data Isolation                                           │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Multi-Tenancy: tenant_id on all tables (logical isolation)   │  │
│  │  Row-Level Security policies (PostgreSQL RLS)                 │  │
│  │  Cross-tenant data access prevented at repository layer      │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  Layer 5: Data Encryption                                          │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  At Rest: AES-256 (PostgreSQL TDE / disk encryption)         │  │
│  │  In Transit: TLS 1.2+ for all service-to-service comms       │  │
│  │  Secrets: Environment variables (never in VCS)               │  │
│  │  Passwords: bcrypt (12 rounds)                               │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  Layer 6: Audit Trail                                              │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Immutable audit entries for all state changes               │  │
│  │  Captures: who, what, when, resource, changes, IP, user-agent │  │
│  │  Tamper-evident via append-only storage                      │  │
│  │  Retention: Configurable (default 7 years)                   │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  Layer 7: Rate Limiting                                            │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Token Bucket Algorithm (Redis-backed)                       │  │
│  │  Default: 60 req/min per tenant/user                         │  │
│  │  Strict: 10 req/min for auth endpoints                       │  │
│  │  Fail-Open: Allow request if Redis is unavailable            │  │
│  └──────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────┘
```

## Data Flows

### Regulation Ingestion Flow

```
Regulatory Body API/File
        │
        ▼
┌───────────────────┐     ┌───────────────────┐     ┌───────────────────┐
│  Document Upload  │────▶│  Text Extraction  │────▶│  AI Analysis      │
│  (PDF/DOCX/HTML)  │     │  (OCR + Parsing)  │     │  (Requirement     │
└───────────────────┘     └───────────────────┘     │   Decomposition)  │
                                                    └─────────┬─────────┘
                                                              │
                                                              ▼
┌───────────────────┐     ┌───────────────────┐     ┌───────────────────┐
│  Regulation       │◀────│  Manual Review    │◀────│  Draft            │
│  Active/Live      │     │  + Adjustments    │     │  Regulation       │
└───────────────────┘     └───────────────────┘     └───────────────────┘
```

### Compliance Assessment Flow

```
┌──────────┐    ┌──────────────┐    ┌──────────────┐    ┌────────────┐
│  Entity  │    │  Regulation  │    │  Assessment  │    │  Evidence  │
│  Created  │    │  Published   │    │  Scheduled   │    │  Uploaded  │
└──────────┘    └──────────────┘    └──────┬───────┘    └────────────┘
                                           │
                                           ▼
                                   ┌──────────────────┐
                                   │  Assessment      │
                                   │  Started         │
                                   └────────┬─────────┘
                                            │
                                            ▼
                                   ┌──────────────────┐     ┌────────────────┐
                                   │  AI Analysis     │────▶│  Hallucination │
                                   │  (Compliance     │     │  Detection     │
                                   │   Assessment)    │     └────────────────┘
                                   └────────┬─────────┘
                                            │
                                            ▼
                                   ┌──────────────────┐
                                   │  Findings Added  │
                                   │  (Manual + AI)   │
                                   └────────┬─────────┘
                                            │
                                            ▼
                                   ┌──────────────────┐
                                   │  Assessment      │
                                   │  Completed       │
                                   └────────┬─────────┘
                                            │
                                            ▼
                                   ┌──────────────────┐
                                   │  Review &        │
                                   │  Approval        │
                                   └────────┬─────────┘
                                            │
                                            ▼
                                   ┌──────────────────┐
                                   │  Report          │
                                   │  Generated       │
                                   └──────────────────┘
```

### API Request Lifecycle

```
Client                       API Gateway                    Application                    Database/External
  │                              │                              │                              │
  │── HTTP Request ─────────────▶│                              │                              │
  │                              │── Rate Limit Check ─────────▶│                              │
  │                              │   (Redis Token Bucket)       │                              │
  │                              │◀── Allowed/Denied ──────────│                              │
  │                              │                              │                              │
  │                              │── Auth Check ───────────────▶│                              │
  │                              │   (JWT Verify)               │                              │
  │                              │◀── Authenticated ───────────│                              │
  │                              │                              │                              │
  │                              │── Permission Check ─────────▶│                              │
  │                              │   (RBAC)                     │                              │
  │                              │◀── Authorized ──────────────│                              │
  │                              │                              │                              │
  │                              │── Request ──────────────────▶│                              │
  │                              │   (Route + Validate)         │                              │
  │                              │                              │── Use Case ─────────────────▶│
  │                              │                              │   (Business Logic)           │
  │                              │                              │── Domain Entity ────────────▶│
  │                              │                              │   (Invariants)               │
  │                              │                              │── Repository ───────────────▶│
  │                              │                              │   (Persist)                  │
  │                              │                              │── Event Publisher ──────────▶│
  │                              │                              │   (Publish Events)           │
  │                              │                              │◀── Response ◀───────────────│
  │                              │── Response ─────────────────▶│                              │
  │◀── HTTP Response ──────────│                              │                              │
  │   (JSON)                    │                              │                              │
```

## Deployment Architecture

```
                         ┌───────────────────────────────┐
                         │   Load Balancer (Nginx/ALB)    │
                         │   TLS Termination, Routing     │
                         └───────────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
           ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
           │  API Pod 1   │ │  API Pod 2   │ │  API Pod N   │
           │  (FastAPI)   │ │  (FastAPI)   │ │  (FastAPI)   │
           └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
                  │                │                │
     ┌────────────┼────────────────┼────────────────┼────────────┐
     │            ▼                ▼                ▼            │
     │   ┌──────────────────────────────────────────────────┐   │
     │   │           PostgreSQL 16 (Primary)                │   │
     │   │           + Read Replica (optional)              │   │
     │   └──────────────────────────────────────────────────┘   │
     │                                                         │
     │   ┌──────────────────────────────────────────────────┐   │
     │   │           Redis 7 (Cache + Rate Limit)           │   │
     │   └──────────────────────────────────────────────────┘   │
     │                                                         │
     │   ┌──────────────────────────────────────────────────┐   │
     │   │    RabbitMQ 3.12 (Event Bus + DLQ)              │   │
     │   └──────────────────────────────────────────────────┘   │
     │                                                         │
     │   ┌──────────────────────────────────────────────────┐   │
     │   │           OpenAI / Anthropic API                 │   │
     │   │           (External Provider)                    │   │
     │   └──────────────────────────────────────────────────┘   │
     │                                                         │
     │   ┌──────────────────────────────────────────────────┐   │
     │   │           File Storage (S3 / Local)              │   │
     │   └──────────────────────────────────────────────────┘   │
     └──────────────────────────────────────────────────────────┘

     Monitoring Stack:
     ┌──────────────────────────────────────────────────────────┐
     │  Prometheus (Metrics)  |  Grafana (Dashboards)          │
     │  Sentry (Errors)       |  OpenTelemetry (Tracing)       │
     │  ELK/Datadog (Logs)    |  PagerDuty (Alerts)           │
     └──────────────────────────────────────────────────────────┘
```

## API Route Map

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/v1/regulations` | Create regulation |
| `GET` | `/api/v1/regulations` | List/search regulations |
| `GET` | `/api/v1/regulations/{id}` | Get regulation details |
| `PATCH` | `/api/v1/regulations/{id}` | Update regulation |
| `POST` | `/api/v1/regulations/{id}/publish` | Publish regulation |
| `POST` | `/api/v1/regulations/{id}/requirements` | Add requirement |
| `POST` | `/api/v1/assessments` | Create assessment |
| `GET` | `/api/v1/assessments` | List assessments |
| `GET` | `/api/v1/assessments/{id}` | Get assessment |
| `POST` | `/api/v1/assessments/{id}/start` | Start assessment |
| `POST` | `/api/v1/assessments/{id}/findings` | Add finding |
| `POST` | `/api/v1/assessments/{id}/complete` | Complete assessment |
| `POST` | `/api/v1/assessments/{id}/approve` | Approve assessment |
| `POST` | `/api/v1/entities` | Create entity |
| `GET` | `/api/v1/entities` | List entities |
| `GET` | `/api/v1/entities/{id}` | Get entity |
| `PATCH` | `/api/v1/entities/{id}` | Update entity |
| `POST` | `/api/v1/entities/{id}/deactivate` | Deactivate entity |
| `POST` | `/api/v1/entities/{id}/activate` | Reactivate entity |
| `GET` | `/api/v1/entities/{id}/hierarchy` | Get entity hierarchy |
| `GET` | `/api/v1/entities/{id}/children` | Get child entities |
| `POST` | `/api/v1/documents` | Upload document |
| `GET` | `/api/v1/documents` | List documents |
| `GET` | `/api/v1/documents/{id}` | Get document |
| `POST` | `/api/v1/documents/{id}/verify` | Verify document |
| `DELETE` | `/api/v1/documents/{id}` | Delete document |
| `GET` | `/api/v1/health` | Health check |
