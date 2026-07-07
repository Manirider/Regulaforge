from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from regulaforge.common.exceptions import NotFoundError
from regulaforge.common.utils import create_response
from regulaforge.modules.notifications.application.notification_service import NotificationService
from regulaforge.modules.notifications.domain.models import (
    Notification,
    NotificationChannel,
    NotificationPreference,
    NotificationTemplate,
)

logger = logging.getLogger(__name__)


def create_notifications_router(
    notification_service: Optional[NotificationService] = None,
    dependencies: Optional[list[Any]] = None,
) -> APIRouter:
    router = APIRouter(
        prefix="/notifications",
        tags=["Notifications"],
        dependencies=dependencies or [],
    )

    @router.get("")
    async def list_notifications(
        recipient_id: str,
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=1000),
        unread_only: bool = False,
    ) -> dict[str, Any]:
        notifications, unread_count = await notification_service.list_notifications(
            recipient_id, skip, limit, unread_only,
        )
        return create_response(data={
            "items": [{
                "id": n.id,
                "title": n.title,
                "body": n.body,
                "channel": n.channel.value,
                "status": n.status.value,
                "read_at": n.read_at.isoformat() if n.read_at else None,
                "created_at": n.created_at.isoformat(),
            } for n in notifications],
            "unread_count": unread_count,
        })

    @router.post("", status_code=status.HTTP_201_CREATED)
    async def send_notification(
        recipient_id: str,
        title: str,
        body: str,
        channel: NotificationChannel = NotificationChannel.IN_APP,
        data: dict[str, Any] = {},
        template_id: str = "",
        tenant_id: str = "",
    ) -> dict[str, Any]:
        notification = await notification_service.send_notification(
            recipient_id, title, body, channel, data, template_id, tenant_id,
        )
        return create_response(data={
            "id": notification.id,
            "status": notification.status.value,
        })

    @router.post("/{notification_id}/read")
    async def mark_as_read(notification_id: str) -> dict[str, Any]:
        try:
            await notification_service.mark_as_read(notification_id)
            return create_response(message="Marked as read")
        except NotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    @router.post("/read-all")
    async def mark_all_as_read(recipient_id: str) -> dict[str, Any]:
        await notification_service.mark_all_as_read(recipient_id)
        return create_response(message="All notifications marked as read")

    @router.get("/preferences")
    async def get_preferences(user_id: str) -> dict[str, Any]:
        preferences = await notification_service.get_preferences(user_id)
        return create_response(data=[{
            "id": p.id,
            "channel": p.channel.value,
            "enabled": p.enabled,
            "digest_frequency": p.digest_frequency,
        } for p in preferences])

    @router.put("/preferences")
    async def update_preferences(user_id: str, preferences: list[NotificationPreference]) -> dict[str, Any]:
        saved = await notification_service.update_preferences(user_id, preferences)
        return create_response(data={"count": len(saved)})

    @router.get("/templates")
    async def list_templates() -> dict[str, Any]:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Template listing not yet implemented")

    @router.post("/templates", status_code=status.HTTP_201_CREATED)
    async def create_template(body: NotificationTemplate) -> dict[str, Any]:
        template = await notification_service.create_template(body)
        return create_response(data={"id": template.id, "name": template.name})

    return router
