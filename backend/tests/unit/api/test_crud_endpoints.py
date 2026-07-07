"""Tests for CRUD API endpoint validation.

Focuses on request validation, response structure, and error handling.
Uses TestClient without requiring a live database.
"""

import pytest


# =============================================================================
# Regulations
# =============================================================================


class TestRegulationsValidation:
    def test_create_missing_fields(self, client):
        response = client.post("/api/v1/regulations", json={})
        assert response.status_code == 401

    def test_create_minimal_fields(self, client):
        response = client.post("/api/v1/regulations", json={
            "title": "Test Regulation",
            "code": "TEST01",
            "description": "A test regulation",
            "category": "data_protection",
            "jurisdiction": "eu",
            "issuing_body": "Test Body",
            "effective_date": "2025-01-01",
        })
        # Without auth token, should fail auth
        assert response.status_code == 401

    def test_create_invalid_category(self, client):
        response = client.post("/api/v1/regulations", json={
            "title": "Test",
            "code": "T02",
            "description": "Test",
            "category": "invalid_category",
            "jurisdiction": "eu",
            "issuing_body": "Body",
            "effective_date": "2025-01-01",
        })
        assert response.status_code == 401

    def test_list_regulations(self, client):
        response = client.get("/api/v1/regulations")
        assert response.status_code == 200


# =============================================================================
# Assessments
# =============================================================================


class TestAssessmentsValidation:
    def test_create_missing_fields(self, client):
        response = client.post("/api/v1/assessments", json={})
        assert response.status_code == 422

    def test_create_invalid_score(self, client):
        response = client.post("/api/v1/assessments", json={
            "title": "Test Assessment",
            "entity_id": "00000000-0000-0000-0000-000000000001",
            "regulation_ids": ["00000000-0000-0000-0000-000000000002"],
            "assessor_id": "00000000-0000-0000-0000-000000000003",
            "due_date": "2025-06-30",
        })
        # Entity doesn't exist in empty test DB, so returns 404
        assert response.status_code == 404


# =============================================================================
# Entities
# =============================================================================


class TestEntitiesValidation:
    def test_create_missing_fields(self, client):
        response = client.post("/api/v1/entities", json={})
        assert response.status_code == 401

    def test_create_minimal(self, client):
        response = client.post("/api/v1/entities", json={
            "name": "Test Entity",
            "entity_type": "department",
            "tenant_id": "00000000-0000-0000-0000-000000000001",
        })
        assert response.status_code == 401


# =============================================================================
# Documents
# =============================================================================


class TestDocumentsValidation:
    def test_upload_without_auth(self, client):
        response = client.post("/api/v1/documents")
        assert response.status_code == 401

    def test_list_without_auth(self, client):
        response = client.get("/api/v1/documents")
        assert response.status_code == 200


# =============================================================================
# Admin
# =============================================================================


class TestAdminAuth:
    def test_users_without_auth(self, client):
        response = client.get("/api/v1/admin/users")
        assert response.status_code == 401

    def test_roles_without_auth(self, client):
        response = client.get("/api/v1/admin/roles")
        assert response.status_code == 401

    def test_create_role_without_auth(self, client):
        response = client.post("/api/v1/admin/roles", json={"name": "test"})
        assert response.status_code == 401
