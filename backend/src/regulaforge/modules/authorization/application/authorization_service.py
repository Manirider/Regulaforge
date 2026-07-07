from __future__ import annotations

import logging
from typing import Any, Optional

from regulaforge.common.exceptions import ForbiddenError, NotFoundError
from regulaforge.modules.authorization.domain.models import (
    Action,
    Permission,
    Policy,
    Resource,
    Role,
    RoleAssignment,
)
from regulaforge.modules.authorization.domain.repository import (
    PermissionRepository,
    PolicyRepository,
    RoleAssignmentRepository,
    RoleRepository,
)

logger = logging.getLogger(__name__)


class AuthorizationService:
    def __init__(
        self,
        role_repo: RoleRepository,
        assignment_repo: RoleAssignmentRepository,
        permission_repo: PermissionRepository,
        policy_repo: PolicyRepository,
    ) -> None:
        self._role_repo = role_repo
        self._assignment_repo = assignment_repo
        self._permission_repo = permission_repo
        self._policy_repo = policy_repo

    async def check_permission(
        self,
        user_id: str,
        resource: Resource,
        action: Action,
        context: Optional[dict[str, Any]] = None,
    ) -> bool:
        assignments = await self._assignment_repo.find_by_user(user_id)
        if not assignments:
            return False

        for assignment in assignments:
            role = await self._role_repo.find_by_id(assignment.role_id)
            if not role:
                continue
            for perm in role.permissions:
                if perm.resource == resource and perm.action == action:
                    if self._evaluate_conditions(perm.conditions, context):
                        return True

        policies = await self._policy_repo.find_all()
        for policy in policies:
            if resource in policy.resources and action in policy.actions:
                if self._evaluate_conditions(policy.conditions, context):
                    return policy.effect == "allow"

        return False

    async def enforce(
        self,
        user_id: str,
        resource: Resource,
        action: Action,
        context: Optional[dict[str, Any]] = None,
    ) -> None:
        allowed = await self.check_permission(user_id, resource, action, context)
        if not allowed:
            raise ForbiddenError(f"Access denied: {action.value} on {resource.value}")

    async def get_user_permissions(self, user_id: str) -> list[Permission]:
        permissions: list[Permission] = []
        assignments = await self._assignment_repo.find_by_user(user_id)
        seen: set[str] = set()
        for assignment in assignments:
            role = await self._role_repo.find_by_id(assignment.role_id)
            if not role:
                continue
            for perm in role.permissions:
                key = f"{perm.resource.value}:{perm.action.value}"
                if key not in seen:
                    seen.add(key)
                    permissions.append(perm)
        return permissions

    async def get_user_roles(self, user_id: str) -> list[Role]:
        roles: list[Role] = []
        assignments = await self._assignment_repo.find_by_user(user_id)
        for assignment in assignments:
            role = await self._role_repo.find_by_id(assignment.role_id)
            if role:
                roles.append(role)
        return roles

    async def assign_role(
        self,
        user_id: str,
        role_id: str,
        assigned_by: str,
        tenant_id: str = "",
    ) -> RoleAssignment:
        role = await self._role_repo.find_by_id(role_id)
        if not role:
            raise NotFoundError(f"Role {role_id} not found")
        assignment = RoleAssignment(
            user_id=user_id,
            role_id=role_id,
            tenant_id=tenant_id,
            assigned_by=assigned_by,
        )
        return await self._assignment_repo.save(assignment)

    async def create_role(self, role: Role) -> Role:
        return await self._role_repo.save(role)

    async def update_role(self, role: Role) -> Role:
        existing = await self._role_repo.find_by_id(role.id)
        if not existing:
            raise NotFoundError(f"Role {role.id} not found")
        return await self._role_repo.save(role)

    async def delete_role(self, role_id: str) -> None:
        existing = await self._role_repo.find_by_id(role_id)
        if not existing:
            raise NotFoundError(f"Role {role_id} not found")
        await self._role_repo.delete(role_id)

    def _evaluate_conditions(
        self,
        conditions: dict[str, Any],
        context: Optional[dict[str, Any]] = None,
    ) -> bool:
        if not conditions:
            return True
        if not context:
            return False
        for key, value in conditions.items():
            if context.get(key) != value:
                return False
        return True
