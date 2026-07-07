# Documents / Evidence API

Base path: `/api/v1/documents`

Artifact types: `document`, `policy`, `procedure`, `log`, `report`, `certificate`, `audit_trail`, `screenshot`, `configuration`, `code_repository`, `interview_note`, `other`

Allowed file extensions: `.pdf`, `.docx`, `.doc`, `.xlsx`, `.xls`, `.csv`, `.json`, `.xml`, `.txt`, `.md`, `.png`, `.jpg`, `.jpeg`, `.tiff`

Maximum file size: **50 MB**

## Upload Document

Uploads a compliance evidence document. Accepts multipart form data with file and metadata fields.

```
POST /api/v1/documents
Content-Type: multipart/form-data
Authorization: Bearer <token>
```

### Request (Multipart Form Data)

| Field | Type | Required | Description |
|---|---|---|---|
| `file` | file | Yes | The file to upload |
| `title` | string | Yes | Document title (2-500 chars) |
| `artifact_type` | string | Yes | Type of evidence artifact |
| `tenant_id` | UUID | Yes | Tenant UUID |
| `description` | string | No | Document description |
| `tags` | string | No | Comma-separated tags |
| `metadata` | string (JSON) | No | Flexible metadata as JSON string |

### Example (cURL)
```bash
curl -X POST https://api.regulaforge.io/api/v1/documents \
  -H "Authorization: Bearer <token>" \
  -F "file=@/path/to/evidence.pdf" \
  -F "title=GDPR Consent Records - Q2 2026" \
  -F "artifact_type=report" \
  -F "tenant_id=t1e2d3c4-b5a6-7890-abcd-ef1234567890" \
  -F "description=Quarterly consent records for data processing activities" \
  -F "tags=gdpr,consent,q2-2026" \
  -F 'metadata={"department":"legal","review_date":"2026-08-01"}'
```

### Response (201 Created)
```json
{
  "id": "f0a1b2c3-d4e5-6789-abcd-ef0123456789",
  "title": "GDPR Consent Records - Q2 2026",
  "file_name": "evidence.pdf",
  "file_path": "storage/documents/t1e2d3c4/20260704120000_f1e2d3c4_evidence.pdf",
  "mime_type": "application/pdf",
  "file_size_bytes": 245760,
  "artifact_type": "report",
  "tenant_id": "t1e2d3c4-b5a6-7890-abcd-ef1234567890",
  "uploaded_by": "f1e2d3c4-b5a6-7890-abcd-ef1234567890",
  "description": "Quarterly consent records for data processing activities",
  "tags": ["gdpr", "consent", "q2-2026"],
  "checksum": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "is_verified": false,
  "verified_by": null,
  "verified_at": null,
  "processing_status": "pending",
  "created_at": "2026-07-04T12:00:00Z",
  "updated_at": "2026-07-04T12:00:00Z"
}
```

### Error Responses
- **400 Bad Request**: Invalid file extension, file too large, validation failure
- **422 Unprocessable Entity**: Missing required fields

---

## List Documents

Retrieves documents with filtering and pagination.

```
GET /api/v1/documents?page=1&page_size=20&tenant_id=t1e2d3c4-...&artifact_type=report&processing_status=completed&is_verified=true
```

### Query Parameters

| Parameter | Type | Description |
|---|---|---|
| `page` | integer | Page number (default: 1) |
| `page_size` | integer | Items per page (default: 20, max: 100) |
| `tenant_id` | UUID | Filter by tenant |
| `artifact_type` | string | Filter by artifact type |
| `processing_status` | string | Filter: `pending`, `processing`, `completed`, `failed` |
| `is_verified` | boolean | Filter by verification status |
| `sort_by` | string | Sort field (e.g., `created_at`, `title`, `file_name`) |
| `sort_order` | string | `asc` or `desc` (default: `desc`) |

### Response (200 OK)
```json
{
  "items": [
    {
      "id": "f0a1b2c3-d4e5-6789-abcd-ef0123456789",
      "title": "GDPR Consent Records - Q2 2026",
      "file_name": "evidence.pdf",
      "mime_type": "application/pdf",
      "file_size_bytes": 245760,
      "artifact_type": "report",
      "tenant_id": "t1e2d3c4-...",
      "is_verified": true,
      "processing_status": "completed",
      "created_at": "2026-07-04T12:00:00Z"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 20,
  "total_pages": 1
}
```

---

## Get Document

Retrieves a document by its ID.

```
GET /api/v1/documents/{document_id}
```

### Response (200 OK)
Full document object as shown in upload response.

### Error Responses
- **404 Not Found**: Document not found

---

## Verify Document

Marks a document as verified, confirming its authenticity and integrity. A verified document carries more weight as evidence in compliance assessments.

```
POST /api/v1/documents/{document_id}/verify
Content-Type: application/json
Authorization: Bearer <token>
```

### Request Body
```json
{
  "verified_by": "f1e2d3c4-b5a6-7890-abcd-ef1234567890"
}
```

### Response (200 OK)
```json
{
  "id": "f0a1b2c3-d4e5-6789-abcd-ef0123456789",
  "is_verified": true,
  "verified_by": "f1e2d3c4-b5a6-7890-abcd-ef1234567890",
  "verified_at": "2026-07-04T14:00:00Z",
  "...": "..."
}
```

### Error Responses
- **404 Not Found**: Document not found
- **400 Bad Request**: Document already verified

---

## Delete Document

Deletes a document. Supports soft delete (default) and hard delete (permanent).

```
DELETE /api/v1/documents/{document_id}?hard_delete=false
```

### Query Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `hard_delete` | boolean | `false` | If `true`, permanently removes the file from storage |

### Response (204 No Content)
No response body on success.

### Error Responses
- **404 Not Found**: Document not found
