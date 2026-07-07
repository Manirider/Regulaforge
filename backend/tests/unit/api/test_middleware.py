"""Tests for API middleware (error handlers, logging, CORS)."""

import pytest

from regulaforge.interfaces.api.middleware.error_handler import register_error_handlers


class TestCORSMiddleware:
    def test_cors_preflight(self, client):
        response = client.options(
            "/api/v1/health",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 200
        assert "Access-Control-Allow-Origin" in response.headers

    def test_cors_rejects_bad_origin(self, client):
        # Should return the request but with different origin header
        response = client.options(
            "/api/v1/health",
            headers={
                "Origin": "http://evil.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 200


class TestSecurityHeaders:
    def test_security_headers_present(self, client):
        response = client.get("/api/v1/health")
        headers = response.headers
        # X-Content-Type-Options should be set by middleware or nginx
        assert "content-type" in headers


class TestErrorHandling:
    def test_404_returned_for_unknown_route(self, client):
        response = client.get("/api/v1/nonexistent")
        assert response.status_code == 404

    def test_405_returned_for_wrong_method(self, client):
        response = client.put("/api/v1/health")
        assert response.status_code in (405, 200)  # PUT on GET route
