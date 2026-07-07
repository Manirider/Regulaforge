from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from regulaforge.common.exceptions import NotFoundError
from regulaforge.modules.notifications.domain.models import (
    Notification,
    NotificationChannel,
    NotificationPreference,
    NotificationStatus,
    NotificationTemplate,
)
from regulaforge.modules.notifications.domain.repository import (
    NotificationPreferenceRepository,
    NotificationRepository,
    NotificationTemplateRepository,
)

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(
        self,
        notification_repo: NotificationRepository,
        preference_repo: NotificationPreferenceRepository,
        template_repo: NotificationTemplateRepository,
    ) -> None:
        self._notification_repo = notification_repo
        self._preference_repo = preference_repo
        self._template_repo = template_repo

    async def send_notification(
        self,
        recipient_id: str,
        title: str,
        body: str,
        channel: NotificationChannel = NotificationChannel.IN_APP,
        data: Optional[dict[str, Any]] = None,
        template_id: str = "",
        tenant_id: str = "",
    ) -> Notification:
        notification = Notification(
            recipient_id=recipient_id,
            title=title,
            body=body,
            channel=channel,
            data=data or {},
            template_id=template_id,
            tenant_id=tenant_id,
        )

        preferences = await self._preference_repo.find_by_user(recipient_id)
        pref = next((p for p in preferences if p.channel == channel), None)
        if pref and not pref.enabled:
            notification.status = NotificationStatus.CANCELLED
            return await self._notification_repo.save(notification)

        saved = await self._notification_repo.save(notification)
        try:
            await self._dispatch_notification(saved)
            saved.status = NotificationStatus.SENT
            saved.sent_at = datetime.utcnow()
        except Exception as exc:
            saved.status = NotificationStatus.FAILED
            saved.data = {**(saved.data), "error": str(exc)}

        return await self._notification_repo.save(saved)

    async def get_notification(self, notification_id: str) -> Notification:
        notification = await self._notification_repo.find_by_id(notification_id)
        if not notification:
            raise NotFoundError(f"Notification {notification_id} not found")
        return notification

    async def list_notifications(
        self, recipient_id: str, skip: int = 0, limit: int = 100, unread_only: bool = False,
    ) -> tuple[list[Notification], int]:
        notifications = await self._notification_repo.find_by_recipient(
            recipient_id, skip, limit, unread_only,
        )
        unread_count = await self._notification_repo.count_unread(recipient_id)
        return notifications, unread_count

    async def mark_as_read(self, notification_id: str) -> None:
        notification = await self.get_notification(notification_id)
        await self._notification_repo.mark_as_read(notification_id)

    async def mark_all_as_read(self, recipient_id: str) -> None:
        await self._notification_repo.mark_all_as_read(recipient_id)

    async def get_preferences(self, user_id: str) -> list[NotificationPreference]:
        return await self._preference_repo.find_by_user(user_id)

    async def update_preferences(self, user_id: str, preferences: list[NotificationPreference]) -> list[NotificationPreference]:
        saved: list[NotificationPreference] = []
        for pref in preferences:
            pref.user_id = user_id
            saved.append(await self._preference_repo.save(pref))
        return saved

    async def create_template(self, template: NotificationTemplate) -> NotificationTemplate:
        return await self._template_repo.save(template)

    async def get_template(self, template_id: str) -> NotificationTemplate:
        template = await self._template_repo.find_by_id(template_id)
        if not template:
            raise NotFoundError(f"Notification template {template_id} not found")
        return template

    async def _dispatch_notification(self, notification: Notification) -> None:
        logger.info("Dispatching notification %s via %s", notification.id, notification.channel.value)
