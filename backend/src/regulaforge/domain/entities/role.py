"""Role entity and Permission value object for authorization.

Defines the role-based access control model with system and
custom roles, each composed of a set of permissions.
"""

from typing import Any, Optional
from uuid import UUID

from regulaforge.domain.entities.base import DomainEntity


class Permission:
    """An immutable value object representing a single permission.

    Permissions follow a resource:action naming convention (e.g.,
    "regulation:create", "assessment:read"). They are compared
    by value and have no identity.
    """

    def __init__(self, resource: str, action: str) -> None:
        self._validate(resource, action)
        self._resource: str = resource.strip().lower()
        self._action: str = action.strip().lower()
        self._key: str = f"{self._resource}:{self._action}"

    @staticmethod
    def _validate(resource: str, action: str) -> None:
        if not resource or len(resource.strip()) < 1:
            raise ValueError("Permission resource is required")
        if not action or len(action.strip()) < 1:
            raise ValueError("Permission action is required")

    @property
    def resource(self) -> str:
        return self._resource

    @property
    def action(self) -> str:
        return self._action

    @property
    def key(self) -> str:
        return self._key

    @classmethod
    def from_string(cls, permission_str: str) -> "Permission":
        """Parse a permission string in 'resource:action' format.

        Args:
            permission_str: The permission string to parse.

        Returns:
            A Permission instance.

        Raises:
            ValueError: If the string format is invalid.
        """
        parts = permission_str.strip().split(":", 1)
        if len(parts) != 2:
            raise ValueError(
                "Permission string must be in 'resource:action' format"
            )
        return cls(resource=parts[0], action=parts[1])

    def to_dict(self) -> dict[str, str]:
        return {
            "resource": self._resource,
            "action": self._action,
            "key": self._key,
        }

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Permission):
            return NotImplemented
        return self._key == other._key

    def __hash__(self) -> int:
        return hash(self._key)

    def __repr__(self) -> str:
        return f"<Permission {self._key}>"


class Role(DomainEntity):
    """A named collection of permissions for authorization.

    Roles can be system-defined (immutable) or custom roles created
    by tenants. System roles include built-in roles like 'admin',
    'auditor', and 'compliance_officer'.
    """

    def __init__(
        self,
        name: str,
        description: Optional[str] = None,
        permissions: Optional[list[str]] = None,
        is_system_role: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._validate_name(name)

        self._name: str = name.strip().lower()
        self._description: Optional[str] = description.strip() if description else None
        self._permissions: list[str] = sorted(set(permissions or []))
        self._is_system_role: bool = is_system_role

    @staticmethod
    def _validate_name(name: str) -> None:
        """Validate role name."""
        if not name or len(name.strip()) < 2:
            raise ValueError("Role name must be at least 2 characters")
        if len(name) > 100:
            raise ValueError("Role name must not exceed 100 characters")

    @staticmethod
    def _validate_permission_key(permission_key: str) -> None:
        """Validate a permission key string format."""
        Permission.from_string(permission_key)

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> Optional[str]:
        return self._description

    @property
    def permissions(self) -> list[str]:
        return list(self._permissions)

    @property
    def is_system_role(self) -> bool:
        return self._is_system_role

    def has_permission(self, permission_key: str) -> bool:
        """Check if this role has a specific permission.

        Args:
            permission_key: The permission key (e.g., 'regulation:create').

        Returns:
            True if the role has the permission, False otherwise.
        """
        self._validate_permission_key(permission_key)
        return permission_key in self._permissions

    def has_all_permissions(self, permission_keys: list[str]) -> bool:
        """Check if this role has all specified permissions."""
        return all(self.has_permission(p) for p in permission_keys)

    def add_permission(self, permission_key: str, by: Optional[UUID] = None) -> None:
        """Add a permission to this role.

        Args:
            permission_key: The permission key to add.
            by: The user making the change.

        Raises:
            ValueError: If this is a system role that cannot be modified.
        """
        if self._is_system_role:
            raise ValueError("Cannot modify permissions of a system role")
        self._validate_permission_key(permission_key)
        if permission_key not in self._permissions:
            self._permissions.append(permission_key)
            self._permissions.sort()
            self.mark_updated(by)

    def remove_permission(self, permission_key: str, by: Optional[UUID] = None) -> None:
        """Remove a permission from this role.

        Args:
            permission_key: The permission key to remove.
            by: The user making the change.

        Raises:
            ValueError: If this is a system role that cannot be modified.
        """
        if self._is_system_role:
            raise ValueError("Cannot modify permissions of a system role")
        self._validate_permission_key(permission_key)
        if permission_key in self._permissions:
            self._permissions.remove(permission_key)
            self.mark_updated(by)

    def set_permissions(self, permission_keys: list[str], by: Optional[UUID] = None) -> None:
        """Replace all permissions on this role.

        Args:
            permission_keys: The full list of permission keys.
            by: The user making the change.

        Raises:
            ValueError: If this is a system role that cannot be modified.
        """
        if self._is_system_role:
            raise ValueError("Cannot modify permissions of a system role")
        for p in permission_keys:
            self._validate_permission_key(p)
        self._permissions = sorted(set(permission_keys))
        self.mark_updated(by)

    def update_description(self, description: Optional[str], by: Optional[UUID] = None) -> None:
        """Update the role description.

        Raises:
            ValueError: If this is a system role that cannot be modified.
        """
        if self._is_system_role:
            raise ValueError("Cannot modify a system role")
        self._description = description.strip() if description else None
        self.mark_updated(by)

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update({
            "name": self._name,
            "description": self._description,
            "permissions": list(self._permissions),
            "is_system_role": self._is_system_role,
        })
        return base

    def __repr__(self) -> str:
        return f"<Role {self._name}>"


class UserRole(DomainEntity):
    """Assignment of a role to a user, optionally scoped to a tenant.

    Represents the many-to-many relationship between users and
    roles, with optional tenant scoping for multi-tenant RBAC.
    """

    def __init__(
        self,
        user_id: UUID,
        role_id: UUID,
        tenant_id: Optional[UUID] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)

        self._user_id: UUID = user_id
        self._role_id: UUID = role_id
        self._tenant_id: Optional[UUID] = tenant_id

    @property
    def user_id(self) -> UUID:
        return self._user_id

    @property
    def role_id(self) -> UUID:
        return self._role_id

    @property
    def tenant_id(self) -> Optional[UUID]:
        return self._tenant_id

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update({
            "user_id": str(self._user_id),
            "role_id": str(self._role_id),
            "tenant_id": str(self._tenant_id) if self._tenant_id else None,
        })
        return base

    def __repr__(self) -> str:
        return f"<UserRole user={self._user_id} role={self._role_id}>"
