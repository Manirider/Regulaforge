from __future__ import annotations

from typing import Optional

from regulaforge.modules.authorization.domain.models import Permission, Policy, Role, RoleAssignment


class RoleRepository:
    async def find_by_id(self, role_id: str) -> Optional[Role]:
        raise NotImplementedError

    async def find_by_name(self, name: str) -> Optional[Role]:
        raise NotImplementedError

    async def find_all(self) -> list[Role]:
        raise NotImplementedError

    async def save(self, role: Role) -> Role:
        raise NotImplementedError

    async def delete(self, role_id: str) -> None:
        raise NotImplementedError


class RoleAssignmentRepository:
    async def find_by_user(self, user_id: str) -> list[RoleAssignment]:
        raise NotImplementedError

    async def save(self, assignment: RoleAssignment) -> RoleAssignment:
        raise NotImplementedError

    async def delete(self, assignment_id: str) -> None:
        raise NotImplementedError


class PermissionRepository:
    async def find_all(self) -> list[Permission]:
        raise NotImplementedError

    async def save(self, permission: Permission) -> Permission:
        raise NotImplementedError


class PolicyRepository:
    async def find_all(self) -> list[Policy]:
        raise NotImplementedError

    async def save(self, policy: Policy) -> Policy:
        raise NotImplementedError
