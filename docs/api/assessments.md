# Assessments API

Base path: `/api/v1/assessments`

## Status Lifecycle

```
SCHEDULED ──► IN_PROGRESS ──► PENDING_REVIEW ──► COMPLETED
                ▲                  │
                │                  ├── reject ──► IN_PROGRESS
                │                  │
                └── cancel ──► CANCELLED
```

## Create Assessment

Creates a new compliance assessment in `scheduled` status.

```
POST /api/v1/assessments
Content-Type: application/json
Authorization: Bearer <token>
```

### Request Body
```json
{
  "title": "GDPR Compliance Assessment - Q2 2026",
  "entity_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "regulation_ids": [
    "3a4b5c6d-7e8f-9a0b-1c2d-3e4f5a6b7c8d",
    "9b8c7d6e-5f4a-3b2c-1d0e-f1a2b3c4d5e6"
  ],
  "assessor_id": "f1e2d3c4-b5a6-7890-abcd-ef1234567890",
  "due_date": "2026-09-30",
  "scope_description": "Assessment of data processing activities against GDPR requirements",
  "metadata": {
    "business_unit": "Engineering",
    "assessment_type": "periodic"
  }
}
```

### Response (201 Created)
```json
{
  "id": "d1e2f3a4-b5c6-7890-abcd-ef1234567890",
  "title": "GDPR Compliance Assessment - Q2 2026",
  "entity_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "entity_type": "organization",
  "regulation_ids": [
    "3a4b5c6d-7e8f-9a0b-1c2d-3e4f5a6b7c8d",
    "9b8c7d6e-5f4a-3b2c-1d0e-f1a2b3c4d5e6"
  ],
  "assessor_id": "f1e2d3c4-b5a6-7890-abcd-ef1234567890",
  "due_date": "2026-09-30",
  "status": "scheduled",
  "scope_description": "Assessment of data processing activities against GDPR requirements",
  "findings": [],
  "overall_score": null,
  "compliance_level": null,
  "approved_by": null,
  "approved_at": null,
  "completed_at": null,
  "created_at": "2026-07-04T12:00:00Z",
  "updated_at": "2026-07-04T12:00:00Z"
}
```

### Error Responses
- **404 Not Found**: Entity or one of the regulations not found
- **400 Bad Request**: Validation failure (e.g., no regulation IDs, invalid title)

---

## List Assessments

Retrieves assessments with filtering and pagination.

```
GET /api/v1/assessments?page=1&page_size=20&status=in_progress&entity_id=a1b2c3d4-...
```

### Query Parameters

| Parameter | Type | Description |
|---|---|---|
| `page` | integer | Page number (default: 1) |
| `page_size` | integer | Items per page (default: 20, max: 100) |
| `status` | string | Filter: `scheduled`, `in_progress`, `pending_review`, `completed`, `cancelled` |
| `entity_id` | UUID | Filter by assessed entity |
| `sort_by` | string | Sort field (e.g., `title`, `due_date`, `created_at`, `status`) |
| `sort_order` | string | `asc` or `desc` (default: `desc`) |

### Response (200 OK)
```json
{
  "items": [
    {
      "id": "d1e2f3a4-b5c6-7890-abcd-ef1234567890",
      "title": "GDPR Compliance Assessment - Q2 2026",
      "status": "in_progress",
      "entity_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "entity_type": "organization",
      "overall_score": null,
      "due_date": "2026-09-30",
      "findings": [],
      "created_at": "2026-07-04T12:00:00Z",
      "updated_at": "2026-07-04T12:30:00Z"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20,
  "total_pages": 1
}
```

---

## Get Assessment

Retrieves a compliance assessment by its ID, including all findings.

```
GET /api/v1/assessments/{assessment_id}
```

### Response (200 OK)
Full assessment object with findings array (see Get Assessment response above).

### Error Responses
- **404 Not Found**: Assessment not found

---

## Start Assessment

Transitions an assessment from `scheduled` to `in_progress`.

```
POST /api/v1/assessments/{assessment_id}/start
Authorization: Bearer <token>
```

### Response (200 OK)
```json
{
  "id": "d1e2f3a4-b5c6-7890-abcd-ef1234567890",
  "status": "in_progress",
  "...": "..."
}
```

### Error Responses
- **404 Not Found**: Assessment not found
- **400 Bad Request**: Cannot start (not in `scheduled` status)

---

## Add Finding

Adds a compliance finding to an in-progress assessment.

```
POST /api/v1/assessments/{assessment_id}/findings
Content-Type: application/json
Authorization: Bearer <token>
```

### Request Body
```json
{
  "requirement_code": "ART-5-1-A",
  "title": "Incomplete consent records",
  "description": "Data processing consent records are not maintained for 3rd-party data sharing activities. Current records cover only 60% of data processors.",
  "risk_level": "high",
  "impact_score": 8.5,
  "likelihood_score": 7.0,
  "remediation_recommendation": "Implement a data processing register and establish consent management procedures covering all third-party data processors",
  "assigned_to": "a2b3c4d5-e6f7-8901-abcd-ef1234567890"
}
```

### Response (200 OK)
```json
{
  "id": "d1e2f3a4-b5c6-7890-abcd-ef1234567890",
  "status": "in_progress",
  "findings": [
    {
      "id": "x1y2z3a4-b5c6-7890-abcd-ef1234567890",
      "requirement_code": "ART-5-1-A",
      "title": "Incomplete consent records",
      "description": "Data processing consent records are not maintained...",
      "risk_level": "high",
      "status": "open",
      "impact_score": 8.5,
      "likelihood_score": 7.0,
      "risk_score": 59.5,
      "evidence": [],
      "remediation_recommendation": "Implement a data processing register...",
      "remediation_due_date": null,
      "assigned_to": "a2b3c4d5-e6f7-8901-abcd-ef1234567890",
      "category": null,
      "created_at": "2026-07-04T13:00:00Z",
      "resolved_at": null
    }
  ],
  "...": "..."
}
```

### Error Responses
- **404 Not Found**: Assessment not found
- **400 Bad Request**: Cannot add findings (assessment not `in_progress` or `pending_review`)

---

## Complete Assessment

Completes an in-progress assessment with a final compliance score. Transitions to `pending_review`.

```
POST /api/v1/assessments/{assessment_id}/complete
Content-Type: application/json
Authorization: Bearer <token>
```

### Request Body
```json
{
  "score": 72.5
}
```

Score is 0-100. Compliance level is derived as:
- ≥ 90: `fully_compliant`
- ≥ 70: `partially_compliant`
- ≥ 50: `non_compliant`
- < 50: `non_compliant`

### Response (200 OK)
```json
{
  "id": "d1e2f3a4-b5c6-7890-abcd-ef1234567890",
  "status": "pending_review",
  "overall_score": 72.5,
  "compliance_level": "partially_compliant",
  "completed_at": "2026-07-04T14:00:00Z",
  "...": "..."
}
```

### Error Responses
- **404 Not Found**: Assessment not found
- **400 Bad Request**: Cannot complete (not `in_progress`)

---

## Approve Assessment

Approves a completed assessment (in `pending_review` status). Transitions to `completed`.

```
POST /api/v1/assessments/{assessment_id}/approve
Authorization: Bearer <token>
```

### Response (200 OK)
```json
{
  "id": "d1e2f3a4-b5c6-7890-abcd-ef1234567890",
  "status": "completed",
  "approved_by": "f1e2d3c4-b5a6-7890-abcd-ef1234567890",
  "approved_at": "2026-07-04T15:00:00Z",
  "...": "..."
}
```

### Error Responses
- **404 Not Found**: Assessment not found
- **400 Bad Request**: Cannot approve (not `pending_review`)
