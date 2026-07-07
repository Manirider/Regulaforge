# API Overview

## Base URL and Versioning

- **Base URL**: `https://api.regulaforge.io/api/v1`
- **Current Version**: `v1` (prefix: `/api/v1`)
- **Content Type**: `application/json`
- **Documentation**: `https://api.regulaforge.io/api/v1/docs` (Swagger UI)
- **Alternate Docs**: `https://api.regulaforge.io/api/v1/redoc` (ReDoc)
- **OpenAPI Schema**: `https://api.regulaforge.io/api/v1/openapi.json`

## Authentication

All API requests require authentication via Bearer JWT tokens.

```
Authorization: Bearer <access_token>
```

### Obtaining a Token

```
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "user@example.com",
  "password": "your-password"
}
```

Response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

### Token Refresh

```
POST /api/v1/auth/refresh
Content-Type: application/json

{
  "refresh_token": "eyJhbGciOiJIUzI1NiIs..."
}
```

### Token Claims
```json
{
  "sub": "user-uuid",
  "tenant_id": "tenant-uuid",
  "roles": ["compliance_officer", "admin"],
  "token_type": "access",
  "jti": "unique-token-id",
  "iat": 1625389200,
  "exp": 1625391000
}
```

## Common Headers

| Header | Required | Description |
|---|---|---|
| `Authorization` | Yes | Bearer JWT access token |
| `X-Tenant-ID` | Yes | Tenant UUID for multi-tenancy |
| `X-Correlation-ID` | Recommended | UUID for request tracing |
| `Content-Type` | Yes | `application/json` (except file uploads) |
| `Accept` | No | `application/json` (default) |
| `User-Agent` | Recommended | Client identifier |

### Correlation ID
The `X-Correlation-ID` header enables distributed tracing across service boundaries. If not provided by the client, the server generates one. It is propagated to audit logs, downstream services, and log entries.

### Tenant ID
The `X-Tenant-ID` header identifies the tenant context. It must match the tenant associated with the authenticated user's JWT claims. The server validates this on every request.

## Pagination

All list endpoints support cursor-free pagination using `page` and `page_size` parameters.

### Request Parameters

| Parameter | Type | Default | Max | Description |
|---|---|---|---|---|
| `page` | integer | 1 | - | Page number (1-indexed) |
| `page_size` | integer | 20 | 100 | Items per page |

### Response Format
```json
{
  "items": [...],
  "total": 157,
  "page": 1,
  "page_size": 20,
  "total_pages": 8
}
```

### Sorting
List endpoints support `sort_by` and `sort_order` parameters:

| Parameter | Values | Description |
|---|---|---|
| `sort_by` | Field name | Field to sort by (endpoint-specific) |
| `sort_order` | `asc`, `desc` | Sort direction (default varies by endpoint) |

### Filtering
Filters are provided as query parameters. Common filters include:

| Filter | Description |
|---|---|
| `status` | Filter by status value |
| `search` | Full-text search query |
| `category` | Filter by category/enum |
| `jurisdiction` | Filter by jurisdiction |
| `tenant_id` | Filter by tenant (UUID) |
| `entity_id` | Filter by entity (UUID) |

## Error Response Format

All errors follow a consistent structure:

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error description",
    "details": [
      {
        "field": "field_name",
        "message": "Validation error message",
        "type": "type_error"
      }
    ]
  }
}
```

### Error Codes

| HTTP Status | Code | Description |
|---|---|---|
| 400 | `BAD_REQUEST` | Validation failure or business rule violation |
| 401 | `UNAUTHORIZED` | Missing or invalid authentication |
| 403 | `FORBIDDEN` | Insufficient permissions |
| 404 | `NOT_FOUND` | Resource not found |
| 409 | `DUPLICATE_ENTITY` | Resource conflict (e.g., duplicate code) |
| 422 | `VALIDATION_ERROR` | Request body validation failure |
| 429 | `TOO_MANY_REQUESTS` | Rate limit exceeded |
| 500 | `INTERNAL_ERROR` | Unexpected server error |
| 503 | `SERVICE_UNAVAILABLE` | Service temporarily unavailable |

### Error Response Examples

**Validation Error (422)**
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "details": [
      {
        "field": "body -> title",
        "message": "String should have at least 3 characters",
        "type": "string_too_short"
      },
      {
        "field": "body -> code",
        "message": "String should have at most 50 characters",
        "type": "string_too_long"
      }
    ]
  }
}
```

**Not Found (404)**
```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Regulation with id 'abc-123' not found"
  }
}
```

**Rate Limited (429)**
```json
{
  "error": {
    "code": "TOO_MANY_REQUESTS",
    "message": "Rate limit exceeded. Retry after 18 seconds."
  }
}
```

## Rate Limiting Headers

All responses include rate limit information:

```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 42
X-RateLimit-Reset: 1625389200
```

When rate limit is exceeded (429 response):
```
Retry-After: 18
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 0
```

## API Changelog

### v0.1.0 (Current - Initial Release)
- Initial release of RegulaForge API v1
- Regulation CRUD and lifecycle management
- Compliance assessment workflow (create, start, findings, complete, approve)
- Entity management with hierarchy support
- Document upload, verification, and deletion
- Health check endpoint
- JWT authentication with refresh tokens
- RBAC with fine-grained permissions
- Rate limiting with token bucket algorithm
- Audit logging for all state changes
