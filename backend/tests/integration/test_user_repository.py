"""Integration tests for SqlAlchemyUserRepository using SQLite in-memory."""

import pytest
from regulaforge.domain.entities.user import User
from regulaforge.domain.repositories.base import RepositoryError
from regulaforge.infrastructure.security.password_service import PasswordService


class TestUserRepository:
    """Suite of integration tests for the user repository."""

    async def test_create_user(self, user_repo, db_session):
        user = User(
            email="alice@example.com",
            username="alice",
            full_name="Alice Wonderland",
        )
        saved = await user_repo.save(user)
        assert saved.id == user.id
        assert saved.email == "alice@example.com"

        # verify persisted
        db_session.expire_all()
        fetched = await user_repo.get_by_id(user.id)
        assert fetched is not None
        assert fetched.email == "alice@example.com"
        assert fetched.username == "alice"
        assert fetched.full_name == "Alice Wonderland"

    async def test_get_by_email(self, user_repo, db_session):
        user = User(
            email="bob@example.com",
            username="bob",
            full_name="Bob Builder",
        )
        await user_repo.save(user)
        db_session.expire_all()

        fetched = await user_repo.get_by_email("bob@example.com")
        assert fetched is not None
        assert fetched.id == user.id
        assert fetched.full_name == "Bob Builder"

    async def test_get_by_email_not_found(self, user_repo):
        fetched = await user_repo.get_by_email("nobody@example.com")
        assert fetched is None

    async def test_get_by_id(self, user_repo, db_session):
        user = User(
            email="carol@example.com",
            username="carol",
        )
        await user_repo.save(user)
        db_session.expire_all()

        fetched = await user_repo.get_by_id(user.id)
        assert fetched is not None
        assert fetched.email == "carol@example.com"
        assert fetched.username == "carol"

    async def test_authenticate_success(self, user_repo):
        pw = PasswordService()
        pw_hash = pw.hash_password("S3cur3P@ss!")
        user = User(
            email="dave@example.com",
            username="dave",
            password_hash=pw_hash,
        )
        await user_repo.save(user)

        authenticated = await user_repo.authenticate("dave@example.com", "S3cur3P@ss!")
        assert authenticated is not None
        assert authenticated.id == user.id

    async def test_authenticate_wrong_password(self, user_repo):
        pw = PasswordService()
        pw_hash = pw.hash_password("CorrectP@ss1")
        user = User(
            email="eve@example.com",
            username="eve",
            password_hash=pw_hash,
        )
        await user_repo.save(user)

        authenticated = await user_repo.authenticate("eve@example.com", "WrongP@ss1")
        assert authenticated is None

    async def test_authenticate_nonexistent_user(self, user_repo):
        authenticated = await user_repo.authenticate("ghost@example.com", "AnyP@ss1")
        assert authenticated is None

    async def test_list_users(self, user_repo, db_session):
        users = [
            User(email="frank@example.com", username="frank"),
            User(email="grace@example.com", username="grace"),
            User(email="heidi@example.com", username="heidi"),
        ]
        for u in users:
            await user_repo.save(u)
        db_session.expire_all()

        result, total = await user_repo.search(page=1, page_size=100)
        assert total >= 3
        emails = {u.email for u in result}
        assert "frank@example.com" in emails
        assert "grace@example.com" in emails
        assert "heidi@example.com" in emails

    async def test_update_user(self, user_repo, db_session):
        user = User(
            email="ivan@example.com",
            username="ivan",
            full_name="Ivan Original",
        )
        await user_repo.save(user)
        db_session.expire_all()

        fetched = await user_repo.get_by_id(user.id)
        fetched._full_name = "Ivan Updated"
        await user_repo.save(fetched)
        db_session.expire_all()

        updated = await user_repo.get_by_id(user.id)
        assert updated is not None
        assert updated.full_name == "Ivan Updated"

    async def test_delete_user(self, user_repo, db_session):
        user = User(
            email="judy@example.com",
            username="judy",
        )
        await user_repo.save(user)
        db_session.expire_all()

        assert await user_repo.exists(user.id) is True

        await user_repo.delete(user.id)

        assert await user_repo.exists(user.id) is False
        fetched = await user_repo.get_by_id(user.id)
        assert fetched is None

    async def test_email_unique_constraint(self, user_repo):
        user1 = User(
            email="dupe@example.com",
            username="user_one",
        )
        await user_repo.save(user1)

        user2 = User(
            email="dupe@example.com",
            username="user_two",
        )
        with pytest.raises(RepositoryError):
            await user_repo.save(user2)
