"""
Notifications API routes for ATREES.
"""

from datetime import datetime
from typing import Any
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from atrees.database import get_db_session
from atrees.models.notification import Notification, NotificationStatus, NotificationPriority
from atrees.services.notification_service import NotificationService

router = APIRouter()


class NotificationResponse(BaseModel):
    id: int
    title: str
    body: str | None
    priority: str
    channels: list[str]
    status: str
    sent_at: str | None
    read_at: str | None
    created_at: str

    class Config:
        from_attributes = True


class SendNotificationRequest(BaseModel):
    title: str
    body: str | None = None
    priority: str = "normal"
    channels: list[str] | None = None
    related_task_id: int | None = None
    related_event_id: int | None = None


@router.get("/", response_model=list[NotificationResponse])
async def list_notifications(
    status: str | None = Query(None),
    priority: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db_session),
) -> list[Notification]:
    """List notifications with filters."""
    stmt = select(Notification).order_by(Notification.created_at.desc())

    if status:
        try:
            stmt = stmt.where(Notification.status == NotificationStatus(status))
        except ValueError:
            pass

    if priority:
        try:
            stmt = stmt.where(Notification.priority == NotificationPriority(priority))
        except ValueError:
            pass

    stmt = stmt.limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/unread-count")
async def get_unread_count(
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Get count of unread notifications."""
    stmt = select(func.count(Notification.id)).where(
        Notification.status.in_([NotificationStatus.PENDING, NotificationStatus.SENT]),
        Notification.read_at.is_(None),
    )
    result = await db.execute(stmt)
    count = result.scalar() or 0
    return {"unread_count": count}


@router.post("/", response_model=NotificationResponse, status_code=201)
async def send_notification(
    request: SendNotificationRequest,
    db: AsyncSession = Depends(get_db_session),
) -> Notification:
    """Send a new notification."""
    notification_service = NotificationService(db)

    try:
        priority = NotificationPriority(request.priority)
    except ValueError:
        priority = NotificationPriority.NORMAL

    notification = await notification_service.send_notification(
        title=request.title,
        body=request.body,
        priority=priority,
        channels=request.channels,
        related_task_id=request.related_task_id,
        related_event_id=request.related_event_id,
    )

    if notification is None:
        # Duplicate was skipped
        from fastapi import HTTPException
        raise HTTPException(status_code=409, detail="Duplicate notification skipped")

    return notification


@router.post("/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Mark notification as read."""
    notification = await db.get(Notification, notification_id)
    if not notification:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Notification not found")

    notification.read_at = datetime.utcnow()
    if notification.status == NotificationStatus.SENT:
        notification.status = NotificationStatus.READ
    await db.commit()
    return {"success": True}


@router.post("/{notification_id}/dismiss")
async def dismiss_notification(
    notification_id: int,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Dismiss a notification."""
    notification = await db.get(Notification, notification_id)
    if not notification:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Notification not found")

    notification.dismissed_at = datetime.utcnow()
    notification.status = NotificationStatus.DISMISSED
    await db.commit()
    return {"success": True}


@router.delete("/{notification_id}")
async def delete_notification(
    notification_id: int,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Delete a notification."""
    notification = await db.get(Notification, notification_id)
    if not notification:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Notification not found")

    await db.delete(notification)
    await db.commit()
    return {"success": True}


@router.post("/mark-all-read")
async def mark_all_read(
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Mark all notifications as read."""
    stmt = select(Notification).where(
        Notification.read_at.is_(None),
        Notification.status.in_([NotificationStatus.PENDING, NotificationStatus.SENT]),
    )
    result = await db.execute(stmt)
    notifications = result.scalars().all()

    for n in notifications:
        n.read_at = datetime.utcnow()
        n.status = NotificationStatus.READ

    await db.commit()
    return {"marked_read": len(notifications)}