# Security Architecture

## Authentication Flow (JWT)

```
┌──────────┐          ┌──────────────┐          ┌──────────────┐          ┌──────────┐
│  Client  │          │  API Server  │          │  JWT Service  │          │  DB/RDS  │
└────┬─────┘          └──────┬───────┘          └──────┬───────┘          └────┬─────┘
     │                       │                        │                       │
     │  POST /auth/login     │                        │                       │
     │  {email, password}    │                        │                       │
     │──────────────────────▶│                        │                       │
     │                       │  Load User             │                       │
     │                       │──────────────────────────────────────────────▶│
     │                       │◀──────────────────────────────────────────────│
     │                       │                        │                       │
     │                       │  Verify Password       │                       │
     │                       │  (bcrypt compare)      │                       │
     │                       │                        │                       │
     │                       │  Record Login          │                       │
     │                       │──────────────────────────────────────────────▶│
     │                       │                        │                       │
     │                       │  Create Access Token   │                       │
     │                       │──────────────────────▶│                        │
     │                       │  sub=user_id           │                        │
     │                       │  tenant_id=xxx         │                        │
     │                       │  roles=[...]           │                        │
     │                       │  exp=now+30min         │                        │
     │                       │◀──────────────────────│                        │
     │                       │                        │                       │
     │                       │  Create Refresh Token  │                       │
     │                       │──────────────────────▶│                        │
     │                       │  sub=user_id           │                        │
     │                       │  token_type=refresh    │                        │
     │                       │  exp=now+7days         │                        │
     │                       │◀──────────────────────│                        │
     │                       │                        │                       │
     │  {access_token,       │                        │                       │
     │   refresh_token}      │                        │                       │
     │◀──────────────────────│                        │                       │
     │                       │                        │                       │
     │  GET /api/v1/...      │                        │                       │
     │  Authorization:       │                        │                       │
     │  Bearer <access_token>│                        │                       │
     │──────────────────────▶│                        │                       │
     │                       │  Verify Token          │                       │
     │                       │  (JWT decode+verify)   │                       │
     │                       │                        │                       │
     │                       │  Extract: sub,tenant_id,roles                │
     │                       │                        │                       │
     │                       │  Check Permissions     │                       │
     │                       │  (RBAC)                │                       │
     │                       │                        │                       │
     │  {response data}      │                        │                       │
     │◀──────────────────────│                        │                       │
```

### Token Refresh Flow

```
┌──────────┐          ┌──────────────┐          ┌──────────────┐
│  Client  │          │  API Server  │          │  JWT Service  │
└────┬─────┘          └──────┬───────┘          └──────┬───────┘
     │                       │                        │
     │  POST /auth/refresh   │                        │
     │  {refresh_token}      │                        │
     │──────────────────────▶│                        │
     │                       │  Verify Refresh Token  │
     │                       │──────────────────────▶│
     │                       │  (verify signature,    │
     │                       │   check token_type,    │
     │                       │   check expiry)        │
     │                       │◀──────────────────────│
     │                       │                        │
     │                       │  Revoke Old Refresh    │
     │                       │  (Redis blacklist jti) │
     │                       │                        │
     │                       │  Create New Pair       │
     │                       │──────────────────────▶│
     │                       │◀──────────────────────│
     │  {new_access_token,   │                        │
     │   new_refresh_token}  │                        │
     │◀──────────────────────│                        │
```

### Token Rotation & Revocation
- Refresh tokens are rotated on every use (old token blacklisted)
- Token blacklist stored in Redis with TTL matching token expiry
- Force logout clears user's token family
- JWT `jti` (JWT ID) claim enables per-token revocation

## Authorization Model (RBAC + Permissions)

### Permission Format
All permissions follow the `resource:action` pattern:

```
regulation:create       | assessment:create       | entity:create
regulation:read         | assessment:read         | entity:read
regulation:update       | assessment:update       | entity:update
regulation:delete       | assessment:delete       | entity:delete
                        |                         |
document:upload         | user:manage             | tenant:configure
document:read           | role:manage             | audit:view
document:verify         | report:generate         | audit:export
document:delete
```

### System Roles

| Role | Permissions | Description |
|---|---|---|
| **superuser** | All (bypass) | Platform administrator with unrestricted access |
| **admin** | All tenant-level permissions | Tenant administrator, can manage users, roles, settings |
| **compliance_officer** | CRUD for regulations, assessments, entities, documents; report:generate | Primary user conducting compliance activities |
| **auditor** | Read-only for regulations, assessments, entities, documents; audit:view | External/internal auditors reviewing compliance |
| **viewer** | Read-only for reports and dashboards | Stakeholders with read-only access |

### Permission Check Flow

```
Request → Auth Middleware
  → Extract JWT → Verify Signature → Decode Claims
  → Get User from DB (verify active, not locked)
  → Superuser? → Allow (skip permission check)
  → Get User Roles
  → Get Role Permissions
  → Check Required Permission against User's Permissions
  → Allow/Deny (403 Forbidden)
```

## Multi-Tenancy Data Isolation

### Architecture
- **Schema**: Single database, shared schema, tenant-isolated via `tenant_id` column
- **Scope**: User, Entity, Document, AuditEntry, Assessment are tenant-scoped
- **System Tables**: Regulations, Roles are optionally tenant-scoped (some are global)

### Isolation Strategy
```sql
-- Every tenant-scoped table has tenant_id column
CREATE TABLE assessable_entities (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id),
    name VARCHAR(200) NOT NULL,
    -- ... other fields
);

-- Row-Level Security (RLS) enabled
ALTER TABLE assessable_entities ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON assessable_entities
    USING (tenant_id = current_setting('app.current_tenant_id')::UUID);
```

### Enforcement Layers
1. **Database**: RLS policies prevent cross-tenant reads/writes
2. **Repository**: All queries include `tenant_id` filter
3. **Application**: Use cases receive tenant context from auth
4. **API**: `X-Tenant-ID` header validated against JWT claims

## Encryption at Rest and in Transit

### In Transit
- **TLS 1.2/1.3** required for all HTTP traffic
- **mTLS** for inter-service communication (Kubernetes service mesh)
- **Database connections**: TLS enforced for PostgreSQL
- **Redis connections**: TLS via Redis 7 TLS support
- **RabbitMQ connections**: TLS for AMQP connections

### At Rest
- **Database**: AES-256 encryption (PostgreSQL TDE or disk-level)
- **File Storage**: Server-side encryption (S3 SSE-S3 or AES-256)
- **Backups**: Encrypted with GPG/AES-256 before storage
- **Secrets**: Never stored in database; environment variables / secrets manager

### Password Storage
- Algorithm: bcrypt with 12 rounds (configurable)
- Salt: Automatic, per-password (bcrypt built-in)
- Plain text passwords never logged or stored

## Audit Logging

### Audit Entry Schema
```json
{
  "id": "uuid",
  "action": "assessment_completed",
  "actor_id": "uuid",
  "actor_email": "user@example.com",
  "tenant_id": "uuid",
  "resource_type": "compliance_assessment",
  "resource_id": "uuid",
  "details": { "score": 85.0, "finding_count": 3 },
  "changes": { "status": { "old": "in_progress", "new": "pending_review" } },
  "ip_address": "192.168.1.1",
  "user_agent": "Mozilla/5.0...",
  "correlation_id": "uuid",
  "timestamp": "2026-07-04T12:00:00Z"
}
```

### Audited Actions
All state-changing operations are audited:
- Resource CRUD (create, update, delete)
- Assessment lifecycle (start, complete, approve, reject)
- Document operations (upload, verify, delete)
- Authentication events (login, logout, failed attempts, lockout)
- Role/permission changes
- Configuration changes
- Data exports

### Audit Log Guarantees
- **Append-only**: Entries are never modified or deleted
- **Temporal ordering**: By `timestamp` with monotonic clock
- **Correlation**: `correlation_id` links distributed events
- **Tamper evidence**: Optional hash chain for tamper-evident logging

## Secrets Management

### Configuration Loading
```
Environment Variables
  ├── .env file (development only, excluded from VCS)
  ├── Docker secrets (container deployment)
  ├── Kubernetes Secrets (K8s deployment)
  └── Vault/Secrets Manager (production)
```

### Secret Inventory

| Secret | Environment Variable | Source |
|---|---|---|
| Secret Key (JWT) | `REGULAFORGE_SECURITY_SECRET_KEY` | Secrets manager |
| Database Password | `REGULAFORGE_DB_URL` (embedded) | Secrets manager |
| LLM API Key | `REGULAFORGE_AI_LLM_API_KEY` | Secrets manager |
| Sentry DSN | `REGULAFORGE_MONITORING_SENTRY_DSN` | Secrets manager |
| Redis Password | `REGULAFORGE_CACHE_URL` (embedded) | Secrets manager |
| RabbitMQ Password | `REGULAFORGE_BROKER_URL` (embedded) | Secrets manager |

### Best Practices
- Secret key minimum 32 characters
- Rotation policy: Every 90 days or on compromise
- No secrets in VCS (.env.example has placeholder values)
- Audit log for secret access and rotation
- Least privilege for secret access

## Rate Limiting

### Algorithm: Token Bucket (Redis-backed)
```
┌─────────────────────────────────────────────────────┐
│  Token Bucket (per client_key)                      │
│                                                     │
│  capacity = 60 tokens  (max burst)                  │
│  refill_rate = 1 token / sec                        │
│  refill_interval = 1.0 sec                          │
│                                                     │
│  ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌────┐  ← tokens     │
│  │ T  │ │ T  │ │ T  │ │ T  │ │ T  │               │
│  └────┘ └────┘ └────┘ └────┘ └────┘               │
│                                                     │
│  Request consumes 1 token:                          │
│  ┌────┐ ┌────┐ ┌────┐ ┌────┐ ┌  X                 │
│                                                     │
│  Refill adds tokens over time:                      │
│  After 5 seconds idle → +5 tokens (up to capacity)  │
└─────────────────────────────────────────────────────┘
```

### Lua Script (Atomic Operation)
```lua
-- Executed atomically on Redis
local tokens = redis.call('HMGET', key, 'tokens', 'last_refill')
-- Calculate refill
-- Check if tokens >= cost
-- If yes: consume, return allowed=true, remaining
-- If no: return allowed=false, retry_after
```

### Limit Tiers

| Tier | Rate | Applied To |
|---|---|---|
| Default | 60 requests/min | All API endpoints |
| Strict | 10 requests/min | Auth endpoints (/auth/login, /auth/refresh) |
| Burst | 100 requests | Shared burst pool per tenant |
| AI | 20 requests/min | AI analysis endpoints |

### Rate Limit Headers
```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 42
X-RateLimit-Reset: 1625389200
Retry-After: 18    (only when limit exceeded, 429 response)
```

## Input Validation and Sanitization

### Validation Layers

1. **Transport**: Request size limit (10MB default, configurable)
2. **Pydantic Schemas**: Field-level validation (types, ranges, regex)
3. **Business Rules**: Domain entity validation (invariants)
4. **Use Cases**: Cross-field and state-based validation

### Example Pydantic Validations
```python
class RegulationCreateRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=500)
    code: str = Field(..., min_length=2, max_length=50)
    # Automatic type coercion, range checks, regex patterns

    @field_validator("code")
    @classmethod
    def validate_code(cls, v: str) -> str:
        return v.upper().strip()  # Normalization
```

### Sanitization
- HTML tags stripped from text fields
- SQL injection prevented by parameterized queries (SQLAlchemy)
- No `eval()` or dynamic imports from user input
- File uploads validated for extension and MIME type
- JSON metadata validated by Pydantic
- Correlation ID must be UUID format

## CORS and CSP Configuration

### CORS (Cross-Origin Resource Sharing)
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.security.cors_origins,  # Configurable list
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### Trusted Hosts
```python
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.security.allowed_hosts,
)
```

### CSP Headers (Recommended Configuration)
```
Content-Security-Policy:
  default-src 'self';
  script-src 'self' 'strict-dynamic';
  style-src 'self' 'unsafe-inline';
  img-src 'self' data:;
  connect-src 'self' https://*.regulaforge.io;
  frame-ancestors 'none';
  base-uri 'self';
  form-action 'self';
```

### Security Headers
```
Strict-Transport-Security: max-age=31536000; includeSubDomains
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Referrer-Policy: strict-origin-when-cross-origin
Cache-Control: no-store (for authenticated endpoints)
```
