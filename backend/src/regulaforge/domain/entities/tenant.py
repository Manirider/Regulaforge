"""Tenant entity for multi-tenant isolation.

Each tenant represents an organization that uses the platform
independently. All data is scoped to a tenant, ensuring full
logical isolation between organizations.
"""

import re
from typing import Any, Optional
from uuid import UUID

from regulaforge.domain.entities.base import DomainEntity

SLUG_REGEX: re.Pattern = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


class Tenant(DomainEntity):
    """An organization that uses the platform as a tenant.

    Each tenant operates in isolation with its own regulations,
    assessments, users, and configuration settings. Tenants are
    identified by their unique slug in URLs.
    """

    def __init__(
        self,
        name: str,
        slug: str,
        settings: Optional[dict[str, Any]] = None,
        is_active: bool = True,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self._validate_name(name)
        self._validate_slug(slug)

        self._name: str = name.strip()
        self._slug: str = slug.strip().lower()
        self._settings: dict[str, Any] = settings or {}
        self._is_active: bool = is_active

    @staticmethod
    def _validate_name(name: str) -> None:
        """Validate tenant name."""
        if not name or len(name.strip()) < 2:
            raise ValueError("Tenant name must be at least 2 characters")
        if len(name) > 200:
            raise ValueError("Tenant name must not exceed 200 characters")

    @staticmethod
    def _validate_slug(slug: str) -> None:
        """Validate tenant slug (URL-friendly identifier)."""
        if not slug or not SLUG_REGEX.match(slug.strip()):
            raise ValueError(
                "Slug must contain only lowercase letters, digits, and hyphens "
                "(e.g., 'acme-corp')"
            )
        if len(slug) < 2:
            raise ValueError("Slug must be at least 2 characters")
        if len(slug) > 100:
            raise ValueError("Slug must not exceed 100 characters")

    @property
    def name(self) -> str:
        return self._name

    @property
    def slug(self) -> str:
        return self._slug

    @property
    def settings(self) -> dict[str, Any]:
        return dict(self._settings)

    @property
    def is_active(self) -> bool:
        return self._is_active

    def update_settings(self, settings: dict[str, Any], by: Optional[UUID] = None) -> None:
        """Merge new settings into existing tenant configuration."""
        self._settings.update(settings)
        self.mark_updated(by)

    def replace_settings(self, settings: dict[str, Any], by: Optional[UUID] = None) -> None:
        """Replace all tenant settings entirely."""
        self._settings = dict(settings)
        self.mark_updated(by)

    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a specific setting value."""
        return self._settings.get(key, default)

    def activate(self, by: Optional[UUID] = None) -> None:
        """Activate this tenant."""
        self._is_active = True
        self.mark_updated(by)

    def deactivate(self, by: Optional[UUID] = None) -> None:
        """Deactivate this tenant."""
        self._is_active = False
        self.mark_updated(by)

    def to_dict(self) -> dict[str, Any]:
        base = super().to_dict()
        base.update({
            "name": self._name,
            "slug": self._slug,
            "settings": dict(self._settings),
            "is_active": self._is_active,
        })
        return base

    def __repr__(self) -> str:
        return f"<Tenant {self._slug}: {self._name}>"
