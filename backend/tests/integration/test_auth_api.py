from __future__ import annotations

from typing import Any, Dict
from uuid import uuid4

import pytest
from regulaforge.domain.entities.user import User
from regulaforge.infrastructure.security.jwt_service import JWTService
from regulaforge.infrastructure.security.password_service import PasswordService

pytestmark = pytest.mark.integration


_password_service = PasswordService()


def _make_user(
    email: str = "test@example.com",
    username: str = "testuser",
    password: str = "StrongPass1!",
    **overrides: Any,
) -> User:
    pw_hash = _password_service.hash_password(password)
    return User(
        email=email,
        username=username,
        password_hash=pw_hash,
        full_name="Test User",
        **overrides,
    )


class TestRegister:
    """POST /api/v1/auth/register"""

    async def test_register_success(self, async_client, mock_user_repo, mock_role_repo):
        mock_user_repo.get_by_email.return_value = None
        mock_user_repo.search.return_value = ([], 0)
        mock_user_repo.save.side_effect = lambda u: u

        payload = {
            "email": "newuser@example.com",
            "username": "newuser",
            "password": "StrongPass1!",
            "full_name": "New User",
        }
        response = await async_client.post("/api/v1/auth/register", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "newuser@example.com"
        assert data["username"] == "newuser"
        assert "id" in data
        assert data["is_active"] is True
        mock_user_repo.save.assert_called_once()

    async def test_register_duplicate_email(self, async_client, mock_user_repo):
        mock_user_repo.get_by_email.return_value = _make_user()

        payload = {
            "email": "test@example.com",
            "username": "another",
            "password": "StrongPass1!",
        }
        response = await async_client.post("/api/v1/auth/register", json=payload)

        assert response.status_code == 400
        assert "already exists" in response.json()["detail"]

    async def test_register_weak_password(self, async_client, mock_user_repo):
        mock_user_repo.get_by_email.return_value = None
        mock_user_repo.search.return_value = ([], 0)

        payload = {
            "email": "weak@example.com",
            "username": "weakuser",
            "password": "alllowercasenodigits",
        }
        response = await async_client.post("/api/v1/auth/register", json=payload)

        assert response.status_code == 400
        assert "Password" in response.json()["detail"]

    async def test_register_missing_fields(self, async_client):
        response = await async_client.post("/api/v1/auth/register", json={})

        assert response.status_code == 422


class TestLogin:
    """POST /api/v1/auth/login"""

    async def test_login_success(self, async_client, mock_user_repo):
        user = _make_user()
        mock_user_repo.get_by_email.return_value = user
        mock_user_repo.save.side_effect = lambda u: u

        payload = {"email": "test@example.com", "password": "StrongPass1!"}
        response = await async_client.post("/api/v1/auth/login", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    async def test_login_wrong_password(self, async_client, mock_user_repo):
        user = _make_user()
        mock_user_repo.get_by_email.return_value = user
        mock_user_repo.save.side_effect = lambda u: u

        payload = {"email": "test@example.com", "password": "WrongPass1!"}
        response = await async_client.post("/api/v1/auth/login", json=payload)

        assert response.status_code == 401

    async def test_login_nonexistent_user(self, async_client, mock_user_repo):
        mock_user_repo.get_by_email.return_value = None

        payload = {"email": "nobody@example.com", "password": "StrongPass1!"}
        response = await async_client.post("/api/v1/auth/login", json=payload)

        assert response.status_code == 401


class TestRefresh:
    """POST /api/v1/auth/refresh"""

    async def test_refresh_success(self, async_client, mock_user_repo):
        user = _make_user()
        mock_user_repo.get_by_id.return_value = user
        mock_user_repo.save.side_effect = lambda u: u

        jwt_service = JWTService()
        refresh_token = jwt_service.create_refresh_token(subject=str(user.id))

        payload = {"refresh_token": refresh_token}
        response = await async_client.post("/api/v1/auth/refresh", json=payload)

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    async def test_refresh_invalid_token(self, async_client):
        payload = {"refresh_token": "invalid-token"}
        response = await async_client.post("/api/v1/auth/refresh", json=payload)

        assert response.status_code == 401


class TestMe:
    """GET /api/v1/auth/me"""

    async def test_get_me_authenticated(self, async_client, mock_user_repo):
        user = _make_user()
        mock_user_repo.get_by_id.return_value = user

        jwt_service = JWTService()
        token = jwt_service.create_access_token(subject=str(user.id))

        response = await async_client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"

    async def test_get_me_unauthenticated(self, async_client):
        pytest.skip("Auth is mocked in integration test fixtures")


class TestChangePassword:
    """POST /api/v1/auth/change-password"""

    async def test_change_password_success(self, async_client, mock_user_repo):
        user = _make_user()
        mock_user_repo.get_by_id.return_value = user
        mock_user_repo.save.side_effect = lambda u: u

        jwt_service = JWTService()
        token = jwt_service.create_access_token(subject=str(user.id))

        payload = {"old_password": "StrongPass1!", "new_password": "NewStrongPass1!"}
        response = await async_client.post(
            "/api/v1/auth/change-password",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200

    async def test_change_password_wrong_old(self, async_client, mock_user_repo):
        user = _make_user()
        mock_user_repo.get_by_id.return_value = user
        mock_user_repo.save.side_effect = lambda u: u

        jwt_service = JWTService()
        token = jwt_service.create_access_token(subject=str(user.id))

        payload = {"old_password": "WrongPass1!", "new_password": "NewStrongPass1!"}
        response = await async_client.post(
            "/api/v1/auth/change-password",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 400
