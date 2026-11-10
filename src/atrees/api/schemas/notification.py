"""
Notification schemas.
"""

from pydantic import BaseModel, Field
from typing import Any, Optional, List
from datetime import datetime
from enum import Enum


class NotificationPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class NotificationStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    DISMISSED = "dismissed"
    FAILED = "failed"


class NotificationBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    body: Optional[str] = None
    priority: NotificationPriority = NotificationPriority.NORMAL
    channels: List[str] = Field(default_factory=lambda: ["telegram"])
    related_task_id: Optional[int] = None
    related_event_id: Optional[int] = None
    related_reminder_id: Optional[int] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class NotificationCreate(NotificationBase):
    pass


class NotificationResponse(NotificationBase):
    id: int
    status: NotificationStatus
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    dismissed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    retry_count: int
    max_retries: int
    created_at: datetime

    class Config:
        from_attributes = True
