# Domain Model

## Ubiquitous Language Glossary

| Term | Definition |
|---|---|
| **Assessment** | The process of evaluating an entity's compliance against one or more regulations |
| **Assessor** | The user responsible for conducting a compliance assessment |
| **Artifact** | A piece of evidence (document, log, certificate) supporting a compliance finding |
| **Compliance Level** | The overall compliance determination (`fully_compliant`, `partially_compliant`, `non_compliant`, `not_applicable`, `under_review`) |
| **Compliance Score** | A numerical score (0-100) representing overall compliance posture |
| **Entity** | Any subject of compliance assessment (organization, department, product, system, process, etc.) |
| **Finding** | A specific compliance gap or observation identified during assessment |
| **Jurisdiction** | The legal or regulatory jurisdiction applicable to a regulation (EU, US Federal, UK, etc.) |
| **Regulation** | A regulatory document, law, standard, or policy with specific requirements |
| **Requirement** | A individual clause, control, or obligation within a regulation |
| **Risk Level** | Severity classification for findings (`critical`, `high`, `medium`, `low`, `negligible`) |
| **Risk Score** | Composite risk calculated as `impact_score × likelihood_score` |
| **Risk Weight** | A 0.0-1.0 multiplier indicating the relative importance of a requirement |
| **Tenant** | An organization that uses the platform in logical isolation |
| **Verification** | The act of confirming a document's authenticity and integrity |

## Entity Relationship Diagram

```
┌──────────────────────────────────┐
│            Tenant                │
│──────────────────────────────────│
│ id: UUID                         │
│ name: str                        │
│ slug: str                        │
│ settings: Dict                   │
│ is_active: bool                  │
│ created_at, updated_at           │
└────────┬─────────────────────────┘
         │ 1
         │ has
         │ *
         ▼
┌──────────────────────────────────┐
│             User                 │
│──────────────────────────────────│
│ id: UUID                         │
│ email: str                       │
│ username: str                    │
│ password_hash: str               │
│ full_name: Optional[str]         │
│ tenant_id: Optional[UUID]        │
│ is_active: bool                  │
│ is_superuser: bool               │
│ failed_login_attempts: int       │
│ locked_until: Optional[datetime] │
│ created_at, updated_at           │
└────────┬─────────────────────────┘
         │ 1
         │ assigned
         │ *
         ▼
┌──────────────────────────────────┐        ┌──────────────────────────────────┐
│      ComplianceAssessment       │        │          Regulation              │
│──────────────────────────────────│        │──────────────────────────────────│
│ id: UUID                         │        │ id: UUID                         │
│ title: str                       │        │ title: str                       │
│ entity_id: UUID                  │        │ code: str (unique)               │
│ entity_type: str                 │        │ description: str                 │
│ regulation_ids: List[UUID]       │────────│ category: RegulationCategory      │
│ assessor_id: UUID                │   *    │ jurisdiction: RegulationJurisdic  │
│ due_date: date                   │        │ issuing_body: str                │
│ status: AssessmentStatus         │        │ effective_date: date             │
│ scope_description: Optional[str] │        │ status: RegulationStatus         │
│ overall_score: Optional[float]   │        │ version: str                     │
│ compliance_level: ComplianceLevel│        │ tags: List[str]                  │
│ approved_by: Optional[UUID]      │        │ parent_regulation_id: Optional   │
│ approved_at: Optional[datetime]  │        │ superseded_by_id: Optional       │
│ completed_at: Optional[datetime] │        │ metadata: Dict                   │
│ created_at, updated_at           │        │ created_at, updated_at           │
└────────┬─────────────────────────┘        └────────────────┬─────────────────┘
         │ 1                                                │ 1
         │ contains                                         │ contains
         │ *                                               │ *
         ▼                                                ▼
┌──────────────────────────────────┐        ┌──────────────────────────────────┐
│       ComplianceFinding         │        │     RegulationRequirement        │
│──────────────────────────────────│        │──────────────────────────────────│
│ id: UUID                         │        │ code: str                        │
│ requirement_code: str            │────────│ title: str                       │
│ title: str                       │        │ description: str                 │
│ description: str                 │        │ parent_requirement_code: Opt     │
│ risk_level: RiskLevel            │        │ is_mandatory: bool               │
│ status: str                      │        │ risk_weight: float (0.0-1.0)     │
│ impact_score: Optional[float]    │        │ guidance: Optional[str]          │
│ likelihood_score: Optional[float]│        │ references: List[str]           │
│ risk_score: Optional[float]      │        └──────────────────────────────────┘
│ remediation_recommendation: Opt  │
│ remediation_due_date: Opt[date] │
│ assigned_to: Optional[UUID]      │
│ created_at, resolved_at          │
│ evidence: List[Dict]             │
└──────────────────────────────────┘


┌──────────────────────────────────┐        ┌──────────────────────────────────┐
│       AssessableEntity          │        │          Document                │
│──────────────────────────────────│        │──────────────────────────────────│
│ id: UUID                         │        │ id: UUID                         │
│ name: str                        │        │ title: str                       │
│ entity_type: EntityType          │        │ file_name: str                   │
│ tenant_id: UUID                  │        │ file_path: str                   │
│ description: Optional[str]       │        │ mime_type: str                   │
│ parent_entity_id: Optional[UUID] │        │ file_size_bytes: int             │
│ tags: List[str]                  │        │ artifact_type: ArtifactType      │
│ attributes: Dict                 │        │ tenant_id: UUID                  │
│ is_active: bool                  │        │ uploaded_by: UUID                │
│ created_at, updated_at           │        │ checksum: Optional[str]          │
└──────────────────────────────────┘        │ is_verified: bool                │
                                            │ verified_by: Optional[UUID]      │
                                            │ verified_at: Optional[datetime]  │
┌──────────────────────────────────┐        │ processing_status: str           │
│            Role                  │        │ extracted_text: Optional[str]    │
│──────────────────────────────────│        │ created_at, updated_at           │
│ id: UUID                         │        └──────────────────────────────────┘
│ name: str                        │
│ description: Optional[str]       │
│ permissions: List[str]           │
│ is_system_role: bool             │
│ created_at, updated_at           │
└────────┬─────────────────────────┘
         │ *
         │ *
         ▼
┌──────────────────────────────────┐
│           UserRole               │
│──────────────────────────────────│
│ user_id: UUID                    │
│ role_id: UUID                    │
│ tenant_id: Optional[UUID]        │
│ created_at, updated_at           │
└──────────────────────────────────┘
```

## Aggregate Boundaries

### Regulation Aggregate
- **Aggregate Root**: `Regulation`
- **Entities**: `Regulation`, `RegulationRequirement`
- **Invariants**:
  - Regulation code must be unique within the system
  - Title must be 3-500 characters
  - Code must be 2-50 characters, uppercase
  - Only `DRAFT` regulations can be published
  - Requirement codes must be unique within a regulation
  - Risk weight must be between 0.0 and 1.0
  - Status lifecycle: `DRAFT` → `ACTIVE` → `SUPERSEDED`/`ARCHIVED` → `RETIRED`

### ComplianceAssessment Aggregate
- **Aggregate Root**: `ComplianceAssessment`
- **Entities**: `ComplianceAssessment`, `ComplianceFinding`
- **Invariants**:
  - At least one regulation must be specified
  - Entity must exist and be active
  - Findings can only be added to `IN_PROGRESS` or `PENDING_REVIEW` assessments
  - Only `SCHEDULED` assessments can be started
  - Only `IN_PROGRESS` assessments can be completed
  - Only `PENDING_REVIEW` assessments can be approved
  - Score must be between 0.0 and 100.0
  - Status lifecycle: `SCHEDULED` → `IN_PROGRESS` → `PENDING_REVIEW` → `COMPLETED`

### AssessableEntity Aggregate
- **Aggregate Root**: `AssessableEntity`
- **Entities**: `AssessableEntity`
- **Invariants**:
  - Name must be 2-200 characters
  - Entity type must be valid (`organization`, `department`, `product`, `service`, `process`, `system`, etc.)
  - Tenant ID is required
  - Parent entity must exist when specified (circular reference prevented)
  - Name must be unique within a tenant

### Document Aggregate
- **Aggregate Root**: `Document`
- **Entities**: `Document`
- **Invariants**:
  - File size must be positive and ≤ 100MB
  - File extension must be in allowed list
  - A document can only be verified once
  - Processing status must be `pending`, `processing`, `completed`, or `failed`

## Domain Events Catalog

| Event | Raised By | Payload | Consumers |
|---|---|---|---|
| **regulation.created** | CreateRegulationUseCase | regulation_id, code, title | Audit log, search index |
| **regulation.updated** | UpdateRegulationUseCase | regulation_id, code, changes | Audit log |
| **regulation.published** | Regulation.publish() | regulation_id, code, title | Notification service |
| **regulation.archived** | Regulation.archive() | regulation_id, code | Search index |
| **regulation.superseded** | Regulation.supersede() | regulation_id, code, new_regulation_id | Notification |
| **assessment.requested** | CreateAssessmentUseCase | assessment_id, entity_id | Notification |
| **assessment.started** | ComplianceAssessment.start() | assessment_id, entity_id | Audit log |
| **assessment.completed** | ComplianceAssessment.complete() | assessment_id, entity_id, score, finding_count | Notification, report generation |
| **assessment.approved** | ComplianceAssessment.approve() | assessment_id, reviewer_id | Report generation |
| **compliance.gap_detected** | AddFindingUseCase | assessment_id, finding_id, requirement_code, risk_level | Notification, escalation |
| **entity.created** | CreateEntityUseCase | entity_id, name, entity_type, tenant_id | Audit log |
| **entity.updated** | UpdateEntityUseCase | entity_id, name, changes | Audit log |
| **entity.deactivated** | AssessableEntity.deactivate() | entity_id, name | Audit log |
| **entity.activated** | AssessableEntity.activate() | entity_id, name | Audit log |
| **document.uploaded** | UploadDocumentUseCase | document_id, file_name, artifact_type, tenant_id | AI processing pipeline |
| **document.verified** | Document.verify() | document_id, file_name, verified_by | Audit log |
| **document.deleted** | DeleteDocumentUseCase | document_id, file_name | Audit log |
| **user.created** | (User registration) | user_id, email, full_name, tenant_id | Notification, audit log |
| **user.logged_in** | User.record_login() | user_id, email, ip_address | Audit log |
| **user.locked** | User.record_failed_attempt() | user_id, email, failed_attempts, locked_until | Security alert |
| **user.password_changed** | User.set_password_hash() | user_id, email | Notification |

## Value Objects

### Address
- **Immutability**: Fully immutable (no setters, hashable)
- **Equality**: By value (street, city, country, state, postal_code)
- **Fields**: street, city, country, state (optional), postal_code (optional), building_name (optional), floor (optional), po_box (optional)
- **Validation**: Street ≥ 3 chars, city ≥ 2 chars, country ≥ 2 chars
- **Methods**: `full_address` (human-readable), `to_dict`, `from_dict`

### ContactInfo
- **Purpose**: Represents contact information for entities and tenants
- **Fields**: email, phone, address (value object)

### Permission
- **Immutability**: Fully immutable, hashable
- **Format**: `resource:action` (e.g., `regulation:create`, `assessment:read`)
- **Equality**: By key string
- **Factory**: `Permission.from_string("regulation:create")`
- **System Permissions**: `regulation:create`, `regulation:read`, `regulation:update`, `regulation:delete`, `assessment:create`, `assessment:read`, `assessment:update`, `assessment:delete`, `entity:create`, `entity:read`, `entity:update`, `entity:delete`, `document:upload`, `document:read`, `document:verify`, `document:delete`, `user:manage`, `role:manage`, `tenant:configure`, `report:generate`, `audit:view`, `audit:export`

### ComplianceLevel
- **Values**: `fully_compliant`, `partially_compliant`, `non_compliant`, `not_applicable`, `under_review`, `insufficient_data`
- **Derivation**: From compliance score (≥ 90 = fully_compliant, ≥ 70 = partially_compliant, ≥ 50 = non_compliant, < 50 = non_compliant)

### RiskLevel
- **Values**: `critical`, `high`, `medium`, `low`, `negligible`
- **Ordering**: critical(5) > high(4) > medium(3) > low(2) > negligible(1)

### AuditAction
- **Values**: `create`, `read`, `update`, `delete`, `export`, `import`, `login`, `logout`, `assessment_started`, `assessment_completed`, `assessment_approved`, `assessment_rejected`, `document_uploaded`, `document_verified`, `report_generated`, `role_assigned`, etc.

## Repository Interfaces

### Base Repository
```python
class SearchableRepository[T](ABC):
    async def save(self, entity: T) -> T
    async def get_by_id(self, id: UUID) -> Optional[T]
    async def delete(self, id: UUID) -> None
    async def search(
        self, filters: Optional[Dict], sort_by: Optional[str],
        sort_order: str, page: int, page_size: int
    ) -> Tuple[List[T], int]
```

### RegulationRepository
```python
class RegulationRepository(SearchableRepository[Regulation]):
    async def get_by_code(self, code: str) -> Optional[Regulation]
    async def get_by_category(self, category: str, page: int, page_size: int) -> Tuple[List[Regulation], int]
    async def get_by_jurisdiction(self, jurisdiction: str, page: int, page_size: int) -> Tuple[List[Regulation], int]
    async def get_active(self, page: int, page_size: int) -> Tuple[List[Regulation], int]
    async def search_full_text(self, query: str, page: int, page_size: int) -> Tuple[List[Regulation], int]
```

### AssessmentRepository
```python
class AssessmentRepository(SearchableRepository[ComplianceAssessment]):
    async def get_by_entity(self, entity_id: UUID, page: int, page_size: int) -> Tuple[List[ComplianceAssessment], int]
    async def get_by_regulation(self, regulation_id: UUID, page: int, page_size: int) -> Tuple[List[ComplianceAssessment], int]
    async def get_by_assignee(self, assignee_id: UUID, page: int, page_size: int) -> Tuple[List[ComplianceAssessment], int]
    async def get_by_status(self, status: str, page: int, page_size: int) -> Tuple[List[ComplianceAssessment], int]
    async def get_overdue(self, page: int, page_size: int) -> Tuple[List[ComplianceAssessment], int]
    async def get_compliance_summary(self, entity_id: UUID) -> Dict
```

### EntityRepository
```python
class EntityRepository(SearchableRepository[AssessableEntity]):
    async def get_by_name(self, name: str, tenant_id: UUID) -> Optional[AssessableEntity]
    async def get_by_type(self, entity_type: str, page: int, page_size: int) -> Tuple[List[AssessableEntity], int]
    async def get_by_tenant(self, tenant_id: UUID, page: int, page_size: int) -> Tuple[List[AssessableEntity], int]
    async def get_children(self, parent_id: UUID, page: int, page_size: int) -> Tuple[List[AssessableEntity], int]
    async def get_hierarchy(self, entity_id: UUID) -> List[AssessableEntity]
```

### DocumentRepository
```python
class DocumentRepository(SearchableRepository[Document]):
    async def get_by_checksum(self, checksum: str) -> Optional[Document]
    async def get_by_tenant(self, tenant_id: UUID, page: int, page_size: int) -> Tuple[List[Document], int]
    async def get_by_artifact_type(self, artifact_type: str, page: int, page_size: int) -> Tuple[List[Document], int]
    async def get_unprocessed(self, page: int, page_size: int) -> Tuple[List[Document], int]
```

### Error Types
```python
class EntityNotFoundError(Exception):    # 404
    # entity_type, entity_id
class DuplicateEntityError(Exception):   # 409
    # entity_type, field, value
class RepositoryError(Exception):         # 500
```
