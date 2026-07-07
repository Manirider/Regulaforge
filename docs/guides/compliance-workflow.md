# Compliance Assessment Workflow Guide

This guide walks through the complete compliance assessment workflow from entity creation through report generation, with example API call sequences.

## Workflow Overview

```
1. Create Entities   2. Add Regulations   3. Create Assessment
        │                   │                     │
        ▼                   ▼                     ▼
   ┌──────────┐      ┌────────────┐      ┌────────────────┐
   │ Entity   │      │ Regulation │      │ Assessment     │
   │ Created  │      │ Published  │      │ Scheduled      │
   └──────────┘      └────────────┘      └────────┬───────┘
                                                   │
                                                   ▼
                                          ┌────────────────┐
                                          │ Assessment     │
                                          │ Started        │
                                          └────────┬───────┘
                                                   │
                                          ┌────────▼───────┐
                              ┌───────────┤ Conduct         │
                              │           │ Assessment      │
                              │           │ (Add Findings)  │
                              │           └────────┬───────┘
                              │                    │
                         ┌────▼────┐      ┌────────▼───────┐
                         │ Upload  │      │ Assessment     │
                         │ Evidence│      │ Completed      │
                         └─────────┘      └────────┬───────┘
                                                    │
                                           ┌────────▼───────┐
                                           │ Review &       │
                                           │ Approve        │
                                           └────────┬───────┘
                                                    │
                                           ┌────────▼───────┐
                                           │ Report         │
                                           │ Generated      │
                                           └────────────────┘
```

## Step 1: Creating Entities

Entities are the subjects of compliance assessments. Create your organizational hierarchy first.

### Create Organization
```bash
curl -X POST http://localhost:8000/api/v1/entities \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -H "X-Tenant-ID: t1e2d3c4-b5a6-7890-abcd-ef1234567890" \
  -d '{
    "name": "Acme Corporation",
    "entity_type": "organization",
    "tenant_id": "t1e2d3c4-b5a6-7890-abcd-ef1234567890",
    "description": "Global technology corporation",
    "tags": ["global", "tech"]
  }'
```
Response includes the entity ID (e.g., `a1b2c3d4-e5f6-7890-abcd-ef1234567890`).

### Create Child Entities
```bash
# Create a department under the organization
curl -X POST http://localhost:8000/api/v1/entities \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "name": "Data Engineering Division",
    "entity_type": "department",
    "tenant_id": "t1e2d3c4-b5a6-7890-abcd-ef1234567890",
    "parent_entity_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "description": "Data engineering and processing team"
  }'

# Create a system under the department
curl -X POST http://localhost:8000/api/v1/entities \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "name": "Customer Data Platform",
    "entity_type": "system",
    "tenant_id": "t1e2d3c4-b5a6-7890-abcd-ef1234567890",
    "parent_entity_id": "<department-id>",
    "description": "Main customer data processing platform",
    "attributes": {
      "region": "eu-west-1",
      "data_classification": "confidential"
    }
  }'
```

## Step 2: Adding Regulations

Regulations define the compliance requirements against which entities are assessed.

### Create a Regulation
```bash
curl -X POST http://localhost:8000/api/v1/regulations \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "title": "General Data Protection Regulation",
    "code": "GDPR",
    "description": "EU regulation on data protection and privacy",
    "category": "data_protection",
    "jurisdiction": "eu",
    "issuing_body": "European Parliament",
    "effective_date": "2018-05-25"
  }'
```
Response includes the regulation ID (e.g., `r1e2g3u4-l5a6-7890-abcd-ef1234567890`).

### Add Requirements to the Regulation
```bash
# Add Article 5 - Principles
curl -X POST http://localhost:8000/api/v1/regulations/r1e2g3u4-l5a6-7890-abcd-ef1234567890/requirements \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "code": "ART-5",
    "title": "Principles relating to processing of personal data",
    "description": "Personal data shall be processed lawfully, fairly and in a transparent manner",
    "is_mandatory": true,
    "risk_weight": 0.95,
    "guidance": "Implement data processing register and consent management"
  }'

# Add Article 6 - Lawfulness
curl -X POST http://localhost:8000/api/v1/regulations/r1e2g3u4-l5a6-7890-abcd-ef1234567890/requirements \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "code": "ART-6",
    "title": "Lawfulness of processing",
    "description": "Processing shall be lawful only if and to the extent that at least one legal basis applies",
    "is_mandatory": true,
    "risk_weight": 1.0
  }'

# Add Article 32 - Security
curl -X POST http://localhost:8000/api/v1/regulations/.../requirements \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "code": "ART-32",
    "title": "Security of processing",
    "description": "Implement appropriate technical and organizational measures",
    "is_mandatory": true,
    "risk_weight": 0.9,
    "guidance": "Encryption, access controls, incident response"
  }'
```

### Publish the Regulation
```bash
curl -X POST http://localhost:8000/api/v1/regulations/r1e2g3u4-l5a6-7890-abcd-ef1234567890/publish \
  -H "Authorization: Bearer <token>"
```

## Step 3: Creating Assessments

Assessments link entities to regulations for evaluation.

```bash
curl -X POST http://localhost:8000/api/v1/assessments \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "title": "GDPR Compliance Assessment - Customer Data Platform",
    "entity_id": "<system-entity-id>",
    "regulation_ids": ["r1e2g3u4-l5a6-7890-abcd-ef1234567890"],
    "assessor_id": "f1e2d3c4-b5a6-7890-abcd-ef1234567890",
    "due_date": "2026-09-30",
    "scope_description": "Full GDPR compliance assessment of the Customer Data Platform"
  }'
```
Save the returned assessment ID (e.g., `a1s2s3e4-s5s6-7890-abcd-ef1234567890`).

## Step 4: Conducting Assessments (Adding Findings)

### Start the Assessment
```bash
curl -X POST http://localhost:8000/api/v1/assessments/a1s2s3e4-s5s6-7890-abcd-ef1234567890/start \
  -H "Authorization: Bearer <token>"
```

### Upload Evidence Documents
```bash
curl -X POST http://localhost:8000/api/v1/documents \
  -H "Authorization: Bearer <token>" \
  -F "file=@data_processing_register.pdf" \
  -F "title=Data Processing Register" \
  -F "artifact_type=document" \
  -F "tenant_id=t1e2d3c4-b5a6-7890-abcd-ef1234567890" \
  -F "description=Current data processing register for CDP" \
  -F "tags=gdpr,data-processing,register"

# Save the document ID (e.g., d1o2c3u4-m5e6-7890-abcd-ef1234567890)

# Verify the document
curl -X POST http://localhost:8000/api/v1/documents/d1o2c3u4-m5e6-7890-abcd-ef1234567890/verify \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "verified_by": "f1e2d3c4-b5a6-7890-abcd-ef1234567890"
  }'
```

### Add Findings
Add findings for each non-compliant or partially compliant requirement.

```bash
# Add a high-risk finding for ART-5 (incomplete consent records)
curl -X POST http://localhost:8000/api/v1/assessments/a1s2s3e4-s5s6-7890-abcd-ef1234567890/findings \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "requirement_code": "ART-5",
    "title": "Incomplete consent management",
    "description": "Consent records not maintained for 3rd-party data processors. Coverage at 60%.",
    "risk_level": "high",
    "impact_score": 8.5,
    "likelihood_score": 7.0,
    "remediation_recommendation": "Implement centralized consent management platform",
    "assigned_to": "a2b3c4d5-e6f7-8901-abcd-ef1234567890"
  }'

# Add a low-risk finding for ART-32 (missing encryption documentation)
curl -X POST http://localhost:8000/api/v1/assessments/a1s2s3e4-s5s6-7890-abcd-ef1234567890/findings \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "requirement_code": "ART-32",
    "title": "Missing encryption policy documentation",
    "description": "Encryption-at-rest policy not formally documented though implemented",
    "risk_level": "low",
    "impact_score": 3.0,
    "likelihood_score": 2.0,
    "remediation_recommendation": "Document existing encryption practices in security policy"
  }'
```

## Step 5: Completing Assessments

Once all findings are added and evidence is collected, complete the assessment with a compliance score.

```bash
curl -X POST http://localhost:8000/api/v1/assessments/a1s2s3e4-s5s6-7890-abcd-ef1234567890/complete \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "score": 72.5
  }'
```

Score interpretation:
| Score Range | Compliance Level | Meaning |
|---|---|---|
| 90-100 | `fully_compliant` | All requirements met with evidence |
| 70-89 | `partially_compliant` | Most requirements met, minor gaps remain |
| 50-69 | `non_compliant` | Significant gaps identified |
| 0-49 | `non_compliant` | Critical compliance failures |

The assessment transitions to `pending_review` status.

## Step 6: Reviewing and Approving

A reviewer (typically a different user) reviews the completed assessment.

### List Assessments Pending Review
```bash
curl -X GET "http://localhost:8000/api/v1/assessments?status=pending_review" \
  -H "Authorization: Bearer <token>"
```

### Review Assessment Details
```bash
curl -X GET http://localhost:8000/api/v1/assessments/a1s2s3e4-s5s6-7890-abcd-ef1234567890 \
  -H "Authorization: Bearer <token>"
```

### Approve the Assessment
```bash
curl -X POST http://localhost:8000/api/v1/assessments/a1s2s3e4-s5s6-7890-abcd-ef1234567890/approve \
  -H "Authorization: Bearer <token>"
```

The assessment is now `completed` with `approved_by`, `approved_at` fields set.

### (Optional) Reject for Revision
If the reviewer finds issues, they can reject:
```bash
# Note: Rejection is not yet exposed via API directly but
# the domain model supports assessment.reject(reviewer_id, reason)
# which returns the assessment to IN_PROGRESS status
```

## Step 7: Generating Reports

### View Compliance Summary
```bash
# Get the final assessment with all findings and scores
curl -X GET http://localhost:8000/api/v1/assessments/a1s2s3e4-s5s6-7890-abcd-ef1234567890 \
  -H "Authorization: Bearer <token>"
```

Response includes:
- Overall compliance score and level
- All findings with risk levels and scores
- Evidence artifacts attached to findings
- Approval metadata (reviewer, timestamp)

### View Entity Compliance History
```bash
# List all assessments for the entity
curl -X GET "http://localhost:8000/api/v1/assessments?entity_id=<entity-id>&sort_by=created_at&sort_order=desc" \
  -H "Authorization: Bearer <token>"
```

## End-to-End Script Example

```bash
#!/bin/bash
# Complete compliance workflow script

# Configuration
TENANT_ID="t1e2d3c4-b5a6-7890-abcd-ef1234567890"
AUTH="Authorization: Bearer <token>"
API="http://localhost:8000/api/v1"

# Step 1: Create entity
ENTITY=$(curl -s -X POST "$API/entities" \
  -H "Content-Type: application/json" \
  -H "$AUTH" \
  -d '{"name":"Test Entity","entity_type":"organization","tenant_id":"'"$TENANT_ID"'","description":"Test"}')
ENTITY_ID=$(echo $ENTITY | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# Step 2: Create and publish regulation
REG=$(curl -s -X POST "$API/regulations" \
  -H "Content-Type: application/json" \
  -H "$AUTH" \
  -d '{"title":"Test Reg","code":"TEST-001","description":"Test","category":"data_protection","jurisdiction":"global","issuing_body":"Test","effective_date":"2026-01-01"}')
REG_ID=$(echo $REG | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

curl -s -X POST "$API/regulations/$REG_ID/publish" -H "$AUTH" > /dev/null

# Step 3: Create assessment
ASM=$(curl -s -X POST "$API/assessments" \
  -H "Content-Type: application/json" \
  -H "$AUTH" \
  -d '{"title":"Test Assessment","entity_id":"'"$ENTITY_ID"'","regulation_ids":["'"$REG_ID"'"],"assessor_id":"00000000-0000-0000-0000-000000000001","due_date":"2026-12-31","scope_description":"Test"}')
ASM_ID=$(echo $ASM | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# Step 4: Start assessment
curl -s -X POST "$API/assessments/$ASM_ID/start" -H "$AUTH" > /dev/null

# Step 5: Add finding
curl -s -X POST "$API/assessments/$ASM_ID/findings" \
  -H "Content-Type: application/json" \
  -H "$AUTH" \
  -d '{"requirement_code":"GEN-1","title":"Test Finding","description":"Test","risk_level":"medium"}' > /dev/null

# Step 6: Complete assessment
curl -s -X POST "$API/assessments/$ASM_ID/complete" \
  -H "Content-Type: application/json" \
  -H "$AUTH" \
  -d '{"score":85.0}' > /dev/null

# Step 7: Approve assessment
curl -s -X POST "$API/assessments/$ASM_ID/approve" -H "$AUTH" > /dev/null

# Step 8: View result
curl -s "$API/assessments/$ASM_ID" -H "$AUTH" | python3 -m json.tool
```
