from __future__ import annotations

from typing import Optional

from regulaforge.modules.notifications.domain.models import (
    Notification,
    NotificationPreference,
    NotificationTemplate,
)


class NotificationRepository:
    async def find_by_id(self, notification_id: str) -> Optional[Notification]:
        raise NotImplementedError

    async def find_by_recipient(
        self, recipient_id: str, skip: int = 0, limit: int = 100, unread_only: bool = False,
    ) -> list[Notification]:
        raise NotImplementedError

    async def count_unread(self, recipient_id: str) -> int:
        raise NotImplementedError

    async def save(self, notification: Notification) -> Notification:
        raise NotImplementedError

    async def mark_as_read(self, notification_id: str) -> None:
        raise NotImplementedError

    async def mark_all_as_read(self, recipient_id: str) -> None:
        raise NotImplementedError


class NotificationPreferenceRepository:
    async def find_by_user(self, user_id: str) -> list[NotificationPreference]:
        raise NotImplementedError

    async def save(self, preference: NotificationPreference) -> NotificationPreference:
        raise NotImplementedError


class NotificationTemplateRepository:
    async def find_by_id(self, template_id: str) -> Optional[NotificationTemplate]:
        raise NotImplementedError

    async def find_by_name(self, name: str) -> Optional[NotificationTemplate]:
        raise NotImplementedError

    async def save(self, template: NotificationTemplate) -> NotificationTemplate:
        raise NotImplementedError
