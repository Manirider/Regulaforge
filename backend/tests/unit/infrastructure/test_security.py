"""Tests for security infrastructure (JWT, password hashing, rate limiting)."""

import time
from uuid import uuid4

import jwt as pyjwt
import pytest
from regulaforge.infrastructure.security.jwt_service import JWTService
from regulaforge.infrastructure.security.password_service import PasswordService

# =============================================================================
# JWT Service Tests
# =============================================================================


class TestJWTService:
    @pytest.fixture
    def jwt_service(self):
        return JWTService(
            secret_key="this-is-a-test-secret-key-that-is-long-enough--32chars",
            algorithm="HS256",
            access_token_expire_minutes=15,
            refresh_token_expire_days=7,
        )

    def test_create_access_token(self, jwt_service):
        subject = str(uuid4())
        token = jwt_service.create_access_token(subject=subject)
        assert isinstance(token, str)
        assert len(token) > 20

    def test_create_refresh_token(self, jwt_service):
        subject = str(uuid4())
        token = jwt_service.create_refresh_token(subject=subject)
        assert isinstance(token, str)

    def test_decode_verify_access_token(self, jwt_service):
        subject = str(uuid4())
        token = jwt_service.create_access_token(subject=subject)
        payload = jwt_service.verify_token(token, expected_type="access")
        assert payload["sub"] == subject
        assert payload["token_type"] == "access"

    def test_decode_verify_refresh_token(self, jwt_service):
        subject = str(uuid4())
        token = jwt_service.create_refresh_token(subject=subject)
        payload = jwt_service.verify_token(token, expected_type="refresh")
        assert payload["sub"] == subject
        assert payload["token_type"] == "refresh"

    def test_access_token_has_short_expiry(self, jwt_service):
        subject = str(uuid4())
        token = jwt_service.create_access_token(subject=subject)
        payload = jwt_service.decode_token(token, verify=False)
        exp = payload["exp"]
        iat = payload["iat"]
        # Access token should expire in ~15 minutes
        assert (exp - iat) == 15 * 60

    def test_refresh_token_has_long_expiry(self, jwt_service):
        subject = str(uuid4())
        token = jwt_service.create_refresh_token(subject=subject)
        payload = jwt_service.decode_token(token, verify=False)
        exp = payload["exp"]
        iat = payload["iat"]
        # Refresh token should expire in ~7 days
        assert (exp - iat) == 7 * 24 * 60 * 60

    def test_invalid_token_raises(self, jwt_service):
        with pytest.raises(pyjwt.InvalidTokenError):
            jwt_service.verify_token("invalid-token")

    def test_tampered_token_raises(self, jwt_service):
        subject = str(uuid4())
        token = jwt_service.create_access_token(subject=subject)
        tampered = token[:-5] + "XXXXX"
        with pytest.raises(pyjwt.InvalidTokenError):
            jwt_service.verify_token(tampered)

    def test_wrong_token_type_raises(self, jwt_service):
        subject = str(uuid4())
        token = jwt_service.create_refresh_token(subject=subject)
        with pytest.raises(ValueError, match="Invalid token type"):
            jwt_service.verify_token(token, expected_type="access")

    def test_expired_token_raises(self, jwt_service):
        # Create a token with 0-minute expiry
        svc = JWTService(
            secret_key="this-is-a-test-secret-key-that-is-long-enough--32chars",
            access_token_expire_minutes=0,
        )
        subject = str(uuid4())
        token = svc.create_access_token(subject=subject)
        time.sleep(0.1)  # Ensure expiry
        with pytest.raises(pyjwt.ExpiredSignatureError):
            svc.verify_token(token)

    def test_is_token_expired(self, jwt_service):
        svc = JWTService(
            secret_key="this-is-a-test-secret-key-that-is-long-enough--32chars",
            access_token_expire_minutes=0,
        )
        token = svc.create_access_token(subject=str(uuid4()))
        time.sleep(0.1)
        assert svc.is_token_expired(token) is True

    def test_get_subject(self, jwt_service):
        subject = str(uuid4())
        token = jwt_service.create_access_token(subject=subject)
        extracted = jwt_service.get_subject(token)
        assert extracted == subject

    def test_access_token_with_roles(self, jwt_service):
        token = jwt_service.create_access_token(
            subject=str(uuid4()),
            roles=["admin", "auditor"],
        )
        payload = jwt_service.verify_token(token)
        assert "admin" in payload["roles"]
        assert "auditor" in payload["roles"]

    def test_access_token_with_tenant(self, jwt_service):
        tenant_id = str(uuid4())
        token = jwt_service.create_access_token(
            subject=str(uuid4()),
            tenant_id=tenant_id,
        )
        payload = jwt_service.verify_token(token)
        assert payload["tenant_id"] == tenant_id

    def test_short_secret_raises(self):
        with pytest.raises(ValueError, match="at least 32"):
            JWTService(secret_key="short")

    def test_invalid_algorithm_raises(self):
        with pytest.raises(ValueError, match="Unsupported"):
            JWTService(
                secret_key="this-is-a-test-secret-key-that-is-long-enough",
                algorithm="INVALID",
            )


# =============================================================================
# Password Service Tests
# =============================================================================


class TestPasswordService:
    @pytest.fixture
    def password_service(self):
        return PasswordService(rounds=4)  # Use low rounds for speed

    def test_hash_password(self, password_service):
        hashed = password_service.hash_password("ValidP@ss1")
        assert isinstance(hashed, str)
        assert len(hashed) > 20
        assert hashed != "ValidP@ss1"

    def test_verify_correct_password(self, password_service):
        hashed = password_service.hash_password("ValidP@ss1")
        assert password_service.verify_password("ValidP@ss1", hashed) is True

    def test_verify_incorrect_password(self, password_service):
        hashed = password_service.hash_password("ValidP@ss1")
        assert password_service.verify_password("WrongPass1!", hashed) is False

    def test_hash_is_deterministic(self, password_service):
        # Two hashes of the same password should be different (different salt)
        h1 = password_service.hash_password("ValidP@ss1")
        h2 = password_service.hash_password("ValidP@ss1")
        assert h1 != h2

    def test_empty_password_raises(self, password_service):
        with pytest.raises(ValueError, match="cannot be empty"):
            password_service.hash_password("")

    def test_long_password_raises(self, password_service):
        with pytest.raises(ValueError, match="128"):
            password_service.hash_password("A" * 200)

    def test_invalid_rounds_raises(self):
        with pytest.raises(ValueError, match="between 4 and 20"):
            PasswordService(rounds=0)

    @pytest.mark.parametrize("password", [
        "ValidP@ss1",
        "Short1@A",
        "abcdefghijklmnop1@A",  # 17 chars
    ])
    def test_valid_passwords(self, password_service, password):
        hashed = password_service.hash_password(password)
        assert password_service.verify_password(password, hashed)
