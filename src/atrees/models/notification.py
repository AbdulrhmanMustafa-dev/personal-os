"""
Notification and Automation models for ATREES.

Notification delivery tracking and scheduled background jobs.
"""

from datetime import datetime
from typing import Any
from sqlalchemy import (
    String,
    Text,
    Integer,
    DateTime,
    Boolean,
    ForeignKey,
    Enum as SQLEnum,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from atrees.models.base import Base, TimestampMixin, SoftDeleteMixin, JSONColumn
import enum


class NotificationPriority(str, enum.Enum):
    """Notification priority levels."""
    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class NotificationStatus(str, enum.Enum):
    """Notification delivery status."""
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    DISMISSED = "dismissed"
    READ = "read"


class JobType(str, enum.Enum):
    """Automation job types."""
    SYNC = "sync"
    EXTRACT = "extract"
    BRIEFING = "briefing"
    RESEARCH = "research"
    REMINDER = "reminder"
    CLEANUP = "cleanup"


class JobStatus(str, enum.Enum):
    """Job execution status."""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"


class Notification(Base, TimestampMixin):
    """Notification log and delivery tracking."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[NotificationPriority] = mapped_column(
        SQLEnum(NotificationPriority, native_enum=False),
        default=NotificationPriority.NORMAL,
        nullable=False,
        index=True,
    )
    channels: Mapped[list[str]] = mapped_column(JSONColumn, default=lambda: ["telegram"], nullable=False)
    status: Mapped[NotificationStatus] = mapped_column(
        SQLEnum(NotificationStatus, native_enum=False),
        default=NotificationStatus.PENDING,
        nullable=False,
        index=True,
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_retries: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    related_task_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("tasks.id", ondelete="SET NULL"),
        nullable=True,
    )
    related_event_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("events.id", ondelete="SET NULL"),
        nullable=True,
    )
    related_reminder_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("reminders.id", ondelete="SET NULL"),
        nullable=True,
    )
    metadata: Mapped[dict[str, Any]] = mapped_column(JSONColumn, default=dict, nullable=False)

    __table_args__ = (
        Index("ix_notif_status", "status"),
        Index("ix_notif_priority", "priority"),
        Index("ix_notif_created", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Notification(id={self.id}, title={self.title[:30]}, priority={self.priority.value}, status={self.status.value})>"


class AutomationJob(Base, TimestampMixin):
    """Scheduled background jobs."""

    __tablename__ = "automation_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    job_type: Mapped[JobType] = mapped_column(
        SQLEnum(JobType, native_enum=False),
        nullable=False,
        index=True,
    )
    schedule_cron: Mapped[str | None] = mapped_column(String(100), nullable=True)
    schedule_interval_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_run_status: Mapped[JobStatus | None] = mapped_column(
        SQLEnum(JobStatus, native_enum=False),
        nullable=True,
    )
    last_run_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_run_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    retry_policy: Mapped[dict[str, Any]] = mapped_column(
        JSONColumn,
        default=lambda: {"max_retries": 3, "backoff_factor": 2},
        nullable=False,
    )
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=300, nullable=False)
    metadata: Mapped[dict[str, Any]] = mapped_column(JSONColumn, default=dict, nullable=False)

    __table_args__ = (
        Index("ix_aj_enabled", "is_enabled"),
        Index("ix_aj_next_run", "next_run_at"),
    )

    def __repr__(self) -> str:
        return f"<AutomationJob(id={self.id}, name={self.name}, type={self.job_type.value}, enabled={self.is_enabled})>"


class AuditLog(Base):
    """Security and operation audit trail."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    user_identifier: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSONColumn, default=dict, nullable=False)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.utcnow(),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        Index("ix_audit_action", "action"),
        Index("ix_audit_entity", "entity_type", "entity_id"),
        Index("ix_audit_user", "user_identifier"),
        Index("ix_audit_created", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, action={self.action}, entity={self.entity_type}:{self.entity_id}, user={self.user_identifier})>"