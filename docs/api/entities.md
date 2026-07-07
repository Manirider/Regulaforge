# Entities API

Base path: `/api/v1/entities`

Entity types: `organization`, `department`, `product`, `service`, `process`, `system`, `data_flow`, `third_party`, `application`, `infrastructure`

## Create Entity

Registers a new assessable entity (organization, department, product, system, etc.) within a tenant.

```
POST /api/v1/entities
Content-Type: application/json
Authorization: Bearer <token>
```

### Request Body
```json
{
  "name": "Acme Corp - Data Processing Platform",
  "entity_type": "system",
  "tenant_id": "t1e2d3c4-b5a6-7890-abcd-ef1234567890",
  "description": "Customer data processing platform handling PII for EU customers",
  "parent_entity_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "tags": ["data-processing", "pii", "production"],
  "attributes": {
    "region": "eu-west-1",
    "criticality": "high",
    "data_classification": "confidential",
    "owner": "platform-team"
  }
}
```

### Response (201 Created)
```json
{
  "id": "e5f6a7b8-c9d0-1234-5678-9abcdef01234",
  "name": "Acme Corp - Data Processing Platform",
  "entity_type": "system",
  "tenant_id": "t1e2d3c4-b5a6-7890-abcd-ef1234567890",
  "description": "Customer data processing platform handling PII for EU customers",
  "parent_entity_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "tags": ["data-processing", "pii", "production"],
  "attributes": {
    "region": "eu-west-1",
    "criticality": "high",
    "data_classification": "confidential"
  },
  "is_active": true,
  "created_at": "2026-07-04T12:00:00Z",
  "updated_at": "2026-07-04T12:00:00Z"
}
```

### Error Responses
- **409 Conflict**: Entity with same name already exists in tenant
- **400 Bad Request**: Validation failure

---

## List Entities

Retrieves entities with filtering and pagination.

```
GET /api/v1/entities?page=1&page_size=20&tenant_id=t1e2d3c4-...&entity_type=system&is_active=true&search=platform
```

### Query Parameters

| Parameter | Type | Description |
|---|---|---|
| `page` | integer | Page number (default: 1) |
| `page_size` | integer | Items per page (default: 20, max: 100) |
| `tenant_id` | UUID | Filter by tenant |
| `entity_type` | string | Filter by entity type |
| `is_active` | boolean | Filter by active status |
| `search` | string | Full-text search |
| `sort_by` | string | Sort field (e.g., `name`, `entity_type`, `created_at`) |
| `sort_order` | string | `asc` or `desc` (default: `asc`) |

### Response (200 OK)
```json
{
  "items": [
    {
      "id": "e5f6a7b8-c9d0-1234-5678-9abcdef01234",
      "name": "Acme Corp - Data Processing Platform",
      "entity_type": "system",
      "tenant_id": "t1e2d3c4-b5a6-7890-abcd-ef1234567890",
      "description": "Customer data processing platform handling PII",
      "parent_entity_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "tags": ["data-processing", "pii"],
      "attributes": {},
      "is_active": true,
      "created_at": "2026-07-04T12:00:00Z",
      "updated_at": "2026-07-04T12:00:00Z"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20,
  "total_pages": 1
}
```

---

## Get Entity

Retrieves an entity by its unique ID.

```
GET /api/v1/entities/{entity_id}
```

### Response (200 OK)
Full entity object as shown above.

### Error Responses
- **404 Not Found**: Entity not found

---

## Update Entity

Updates one or more fields of an existing entity.

```
PATCH /api/v1/entities/{entity_id}
Content-Type: application/json
Authorization: Bearer <token>
```

### Request Body
```json
{
  "name": "Acme Corp - Updated Data Platform",
  "description": "Updated description",
  "tags": ["data-processing", "pii", "production", "critical"],
  "attributes": {
    "criticality": "critical",
    "last_assessed": "2026-07-04"
  },
  "parent_entity_id": null
}
```

All fields optional. Updateable: `name`, `description`, `tags`, `attributes`, `parent_entity_id`.

### Response (200 OK)
Returns the updated entity object.

### Error Responses
- **404 Not Found**: Entity not found
- **400 Bad Request**: Validation failure

---

## Deactivate Entity

Marks an entity as inactive. Inactive entities cannot be used in new assessments.

```
POST /api/v1/entities/{entity_id}/deactivate
Authorization: Bearer <token>
```

### Response (200 OK)
```json
{
  "id": "e5f6a7b8-...",
  "is_active": false,
  "...": "..."
}
```

---

## Reactivate Entity

Reactivates a previously deactivated entity.

```
POST /api/v1/entities/{entity_id}/activate
Authorization: Bearer <token>
```

### Response (200 OK)
```json
{
  "id": "e5f6a7b8-...",
  "is_active": true,
  "...": "..."
}
```

---

## Get Entity Hierarchy

Retrieves the ancestor chain from root to the specified entity. Useful for understanding organizational structure.

```
GET /api/v1/entities/{entity_id}/hierarchy
```

### Response (200 OK)
```json
{
  "items": [
    {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "name": "Acme Corporation",
      "entity_type": "organization",
      "is_active": true
    },
    {
      "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
      "name": "Engineering Division",
      "entity_type": "department",
      "is_active": true
    },
    {
      "id": "e5f6a7b8-c9d0-1234-5678-9abcdef01234",
      "name": "Acme Corp - Data Processing Platform",
      "entity_type": "system",
      "is_active": true
    }
  ]
}
```

---

## Get Child Entities

Retrieves direct children of a parent entity with pagination.

```
GET /api/v1/entities/{entity_id}/children?page=1&page_size=20
```

### Response (200 OK)
```json
{
  "items": [
    {
      "id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
      "name": "Data Processing Subsystem A",
      "entity_type": "system",
      "parent_entity_id": "e5f6a7b8-c9d0-1234-5678-9abcdef01234",
      "is_active": true
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20,
  "total_pages": 1
}
```

### Error Responses
- **404 Not Found**: Parent entity not found
