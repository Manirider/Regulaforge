# Regulations API

Base path: `/api/v1/regulations`

## Create Regulation

Creates a new regulatory document. The regulation starts in `draft` status and must be published before it can be used in assessments.

```
POST /api/v1/regulations
Content-Type: application/json
Authorization: Bearer <token>
```

### Request Body
```json
{
  "title": "General Data Protection Regulation",
  "code": "GDPR",
  "description": "EU regulation on data protection and privacy in the European Union and the European Economic Area",
  "category": "data_protection",
  "jurisdiction": "eu",
  "issuing_body": "European Parliament",
  "effective_date": "2018-05-25",
  "tags": ["privacy", "data-protection", "eu"],
  "metadata": {
    "official_url": "https://eur-lex.europa.eu/eli/reg/2016/679/oj"
  }
}
```

### Response (201 Created)
```json
{
  "id": "3a4b5c6d-7e8f-9a0b-1c2d-3e4f5a6b7c8d",
  "title": "General Data Protection Regulation",
  "code": "GDPR",
  "description": "EU regulation on data protection and privacy in the European Union and the European Economic Area",
  "category": "data_protection",
  "jurisdiction": "eu",
  "issuing_body": "European Parliament",
  "effective_date": "2018-05-25",
  "status": "draft",
  "version": "1.0",
  "tags": ["privacy", "data-protection", "eu"],
  "parent_regulation_id": null,
  "superseded_by_id": null,
  "requirements": [],
  "created_at": "2026-07-04T12:00:00Z",
  "updated_at": "2026-07-04T12:00:00Z"
}
```

### Error Responses
- **409 Conflict**: Regulation code already exists
- **400 Bad Request**: Validation failure (e.g., title too short, invalid category)
- **422 Unprocessable Entity**: Request body validation failure

---

## List/Search Regulations

Retrieves regulations with optional filtering, full-text search, and pagination.

```
GET /api/v1/regulations?page=1&page_size=20&status=active&category=data_protection&jurisdiction=eu&search=GDPR&sort_by=title&sort_order=asc
```

### Query Parameters

| Parameter | Type | Description |
|---|---|---|
| `page` | integer | Page number (default: 1) |
| `page_size` | integer | Items per page (default: 20, max: 100) |
| `status` | string | Filter by status: `draft`, `active`, `superseded`, `archived`, `amended`, `retired` |
| `category` | string | Filter by category: `data_protection`, `privacy`, `financial`, `cybersecurity`, etc. |
| `jurisdiction` | string | Filter by jurisdiction: `eu`, `us_federal`, `us_state`, `uk`, `global`, etc. |
| `search` | string | Full-text search query |
| `sort_by` | string | Sort field (e.g., `title`, `code`, `effective_date`, `created_at`) |
| `sort_order` | string | Sort direction: `asc` or `desc` (default: `asc`) |

### Response (200 OK)
```json
{
  "items": [
    {
      "id": "3a4b5c6d-7e8f-9a0b-1c2d-3e4f5a6b7c8d",
      "title": "General Data Protection Regulation",
      "code": "GDPR",
      "description": "EU regulation on data protection and privacy...",
      "category": "data_protection",
      "jurisdiction": "eu",
      "issuing_body": "European Parliament",
      "effective_date": "2018-05-25",
      "status": "active",
      "version": "1.0",
      "tags": ["privacy", "data-protection"],
      "requirements": [
        {
          "code": "ART-5",
          "title": "Principles relating to processing of personal data",
          "description": "Personal data shall be...",
          "is_mandatory": true,
          "risk_weight": 1.0
        }
      ],
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

## Get Regulation

Retrieves a regulation by its unique ID.

```
GET /api/v1/regulations/{regulation_id}
```

### Path Parameters

| Parameter | Type | Description |
|---|---|---|
| `regulation_id` | UUID | Regulation unique identifier |

### Response (200 OK)
Same structure as regulation object shown above.

### Error Responses
- **404 Not Found**: Regulation with the given ID does not exist

---

## Update Regulation

Updates one or more fields of an existing regulation. Only provided fields are updated.

```
PATCH /api/v1/regulations/{regulation_id}
Content-Type: application/json
Authorization: Bearer <token>
```

### Request Body
```json
{
  "title": "General Data Protection Regulation (Updated)",
  "description": "Updated description of the regulation",
  "tags": ["privacy", "data-protection", "eu", "gdpr"],
  "metadata": {
    "enforcement_date": "2018-05-25",
    "status_notes": "Currently under review for amendment"
  }
}
```

All fields are optional. Possible update fields: `title`, `description`, `category`, `jurisdiction`, `issuing_body`, `effective_date`, `tags`, `metadata`.

### Response (200 OK)
Returns the updated regulation object.

### Error Responses
- **404 Not Found**: Regulation not found
- **400 Bad Request**: Validation failure

---

## Publish Regulation

Publishes a draft regulation, changing its status to `active`. Only draft regulations can be published. Active regulations are available for use in compliance assessments.

```
POST /api/v1/regulations/{regulation_id}/publish
Authorization: Bearer <token>
```

### Response (200 OK)
```json
{
  "id": "3a4b5c6d-7e8f-9a0b-1c2d-3e4f5a6b7c8d",
  "code": "GDPR",
  "status": "active",
  "...": "..."
}
```

### Error Responses
- **404 Not Found**: Regulation not found
- **400 Bad Request**: Cannot publish (e.g., already published, archived)

---

## Add Requirement

Adds a requirement clause to a regulation. Requirements are individual controls or obligations within the regulation that can be independently assessed.

```
POST /api/v1/regulations/{regulation_id}/requirements
Content-Type: application/json
Authorization: Bearer <token>
```

### Request Body
```json
{
  "code": "ART-5-1-A",
  "title": "Lawfulness, fairness and transparency",
  "description": "Personal data shall be processed lawfully, fairly and in a transparent manner in relation to the data subject",
  "is_mandatory": true,
  "risk_weight": 0.95,
  "guidance": "Implement data processing register and consent management mechanisms",
  "references": [
    "https://gdpr-info.eu/art-5-gdpr/",
    "https://ico.org.uk/for-organisations/guide-to-data-protection/principle-a-lawfulness-fairness-and-transparency/"
  ],
  "parent_requirement_code": "ART-5"
}
```

### Response (200 OK)
Returns the regulation with the new requirement included in the `requirements` array.

### Error Responses
- **404 Not Found**: Regulation not found
- **400 Bad Request**: Validation failure (e.g., duplicate requirement code, invalid risk weight)
- **422 Unprocessable Entity**: Request body validation failure
