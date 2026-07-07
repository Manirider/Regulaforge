from __future__ import annotations

from uuid import uuid4

import pytest
from regulaforge.application.use_cases.auth_use_cases import (
    ChangePasswordUseCase,
    LoginUserUseCase,
    RefreshTokenUseCase,
    RegisterUserUseCase,
)
from regulaforge.domain.entities.user import User
from regulaforge.infrastructure.security.adapters.token_service_adapter import JwtTokenAdapter
from regulaforge.infrastructure.security.jwt_service import JWTService
from regulaforge.infrastructure.security.password_service import PasswordService

pytestmark = pytest.mark.unit


_password_service = PasswordService()


@pytest.fixture
def mock_user_repo(mocker):
    return mocker.AsyncMock()


@pytest.fixture
def mock_role_repo(mocker):
    return mocker.AsyncMock()


@pytest.fixture
def password_service():
    return PasswordService()


@pytest.fixture
def jwt_service():
    return JWTService()


class TestRegisterUserUseCase:
    async def test_register_success(self, mock_user_repo, mock_role_repo, password_service):
        mock_user_repo.get_by_email.return_value = None
        mock_user_repo.search.return_value = ([], 0)
        mock_user_repo.save.side_effect = lambda u: u

        uc = RegisterUserUseCase(mock_user_repo, mock_role_repo, password_service)
        user = await uc.execute(
            email="new@example.com",
            username="newuser",
            password="StrongPass1!",
            full_name="New User",
        )

        assert user.email == "new@example.com"
        assert user.is_active is True
        mock_user_repo.save.assert_called_once()

    async def test_register_duplicate_email(self, mock_user_repo, mock_role_repo, password_service):
        mock_user_repo.get_by_email.return_value = User(
            email="dup@example.com", username="dupuser", password_hash="hash"
        )

        uc = RegisterUserUseCase(mock_user_repo, mock_role_repo, password_service)
        with pytest.raises(ValueError, match="already exists"):
            await uc.execute(
                email="dup@example.com",
                username="newuser",
                password="StrongPass1!",
            )

    async def test_register_weak_password(self, mock_user_repo, mock_role_repo, password_service):
        mock_user_repo.get_by_email.return_value = None
        mock_user_repo.search.return_value = ([], 0)

        uc = RegisterUserUseCase(mock_user_repo, mock_role_repo, password_service)
        with pytest.raises(ValueError, match="Password"):
            await uc.execute(
                email="test@example.com",
                username="testuser",
                password="short",
            )


class TestLoginUserUseCase:
    async def test_login_success(self, mock_user_repo, password_service, jwt_service):
        pw_hash = password_service.hash_password("StrongPass1!")
        user = User(email="test@example.com", username="testuser", password_hash=pw_hash)
        mock_user_repo.get_by_email.return_value = user
        mock_user_repo.save.side_effect = lambda u: u

        uc = LoginUserUseCase(mock_user_repo, password_service, jwt_service)
        result = await uc.execute(email="test@example.com", password="StrongPass1!")

        assert "access_token" in result
        assert "refresh_token" in result
        assert result["token_type"] == "bearer"

    async def test_login_wrong_password(self, mock_user_repo, password_service, jwt_service):
        pw_hash = password_service.hash_password("StrongPass1!")
        user = User(email="test@example.com", username="testuser", password_hash=pw_hash)
        mock_user_repo.get_by_email.return_value = user
        mock_user_repo.save.side_effect = lambda u: u

        uc = LoginUserUseCase(mock_user_repo, password_service, jwt_service)
        with pytest.raises(ValueError, match="Invalid email or password"):
            await uc.execute(email="test@example.com", password="WrongPass1!")

    async def test_login_nonexistent_user(self, mock_user_repo, password_service, jwt_service):
        mock_user_repo.get_by_email.return_value = None

        uc = LoginUserUseCase(mock_user_repo, password_service, jwt_service)
        with pytest.raises(ValueError, match="Invalid email or password"):
            await uc.execute(email="nobody@example.com", password="StrongPass1!")


class TestRefreshTokenUseCase:
    async def test_refresh_success(self, mock_user_repo, jwt_service):
        user = User(email="test@example.com", username="testuser")
        mock_user_repo.get_by_id.return_value = user

        token_adapter = JwtTokenAdapter(jwt_service)
        refresh_token = jwt_service.create_refresh_token(subject=str(user.id))

        uc = RefreshTokenUseCase(token_adapter, mock_user_repo)
        result = await uc.execute(refresh_token)

        assert "access_token" in result
        assert result["token_type"] == "bearer"

    async def test_refresh_invalid_token(self, mock_user_repo, jwt_service):
        token_adapter = JwtTokenAdapter(jwt_service)
        uc = RefreshTokenUseCase(token_adapter, mock_user_repo)
        with pytest.raises(Exception):
            await uc.execute("invalid-token")


class TestChangePasswordUseCase:
    async def test_change_password_success(self, mock_user_repo, password_service):
        pw_hash = password_service.hash_password("OldPass1!")
        user = User(email="test@example.com", username="testuser", password_hash=pw_hash)
        mock_user_repo.save.side_effect = lambda u: u

        uc = ChangePasswordUseCase(mock_user_repo, password_service)
        await uc.execute(user, old_password="OldPass1!", new_password="NewStrongPass1!")

        assert password_service.verify_password("NewStrongPass1!", user.password_hash)
        mock_user_repo.save.assert_called_once()

    async def test_change_password_wrong_old(self, mock_user_repo, password_service):
        pw_hash = password_service.hash_password("OldPass1!")
        user = User(email="test@example.com", username="testuser", password_hash=pw_hash)

        uc = ChangePasswordUseCase(mock_user_repo, password_service)
        with pytest.raises(ValueError, match="incorrect"):
            await uc.execute(user, old_password="WrongPass1!", new_password="NewStrongPass1!")
