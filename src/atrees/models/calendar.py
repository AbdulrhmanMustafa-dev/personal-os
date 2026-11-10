"""
Calendar models for ATREES.

Events with preparation support and reminders.
"""

from datetime import datetime, date, time
from typing import Any
from sqlalchemy import (
    String,
    Text,
    Integer,
    DateTime,
    Date,
    Time,
    Boolean,
    ForeignKey,
    Enum as SQLEnum,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from atrees.models.base import Base, TimestampMixin, SoftDeleteMixin, JSONColumn
import enum


class EventStatus(str, enum.Enum):
    """Calendar event status."""
    TENTATIVE = "tentative"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class EventVisibility(str, enum.Enum):
    """Event visibility."""
    DEFAULT = "default"
    PUBLIC = "public"
    PRIVATE = "private"
    CONFIDENTIAL = "confidential"


class PreparationStatus(str, enum.Enum):
    """Event preparation status."""
    DRAFT = "draft"
    READY = "ready"
    COMPLETED = "completed"


class Event(Base, TimestampMixin, SoftDeleteMixin):
    """Calendar events with preparation support."""

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("sources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_event_id: Mapped[str | None] = mapped_column(String(500), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(String(500), nullable=True)
    start_datetime: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    end_datetime: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    timezone: Mapped[str] = mapped_column(String(50), default="Africa/Cairo", nullable=False)
    is_all_day: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    recurrence_rule: Mapped[str | None] = mapped_column(Text, nullable=True)
    recurrence_id: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[EventStatus] = mapped_column(
        SQLEnum(EventStatus, native_enum=False),
        default=EventStatus.CONFIRMED,
        nullable=False,
        index=True,
    )
    visibility: Mapped[EventVisibility] = mapped_column(
        SQLEnum(EventVisibility, native_enum=False),
        default=EventVisibility.DEFAULT,
        nullable=False,
    )
    meeting_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    meeting_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    meeting_password: Mapped[str | None] = mapped_column(String(200), nullable=True)
    organizer_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("contacts.id", ondelete="SET NULL"),
        nullable=True,
    )
    attendees: Mapped[list[dict[str, Any]]] = mapped_column(JSONColumn, default=list, nullable=False)
    reminders: Mapped[list[dict[str, Any]]] = mapped_column(JSONColumn, default=list, nullable=False)
    project_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_message_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    requires_preparation: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    preparation_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata: Mapped[dict[str, Any]] = mapped_column(JSONColumn, default=dict, nullable=False)

    # Relationships
    preparation: Mapped["EventPreparation | None"] = relationship(
        "EventPreparation",
        back_populates="event",
        foreign_keys="EventPreparation.event_id",
        uselist=False,
        lazy="joined",
    )

    __table_args__ = (
        Index("ix_event_start", "start_datetime"),
        Index("ix_event_project", "project_id"),
        Index("ix_event_status", "status"),
        Index("ix_event_source", "source_id", "source_event_id"),
    )

    def __repr__(self) -> str:
        return f"<Event(id={self.id}, title={self.title[:30]}, start={self.start_datetime}, status={self.status.value})>"


class EventPreparation(Base, TimestampMixin):
    """Preparation packages for important events."""

    __tablename__ = "event_preparations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("events.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    participants: Mapped[list[dict[str, Any]]] = mapped_column(JSONColumn, default=list, nullable=False)
    required_documents: Mapped[list[dict[str, Any]]] = mapped_column(JSONColumn, default=list, nullable=False)
    checklist: Mapped[list[dict[str, Any]]] = mapped_column(JSONColumn, default=list, nullable=False)
    related_projects: Mapped[list[int]] = mapped_column(JSONColumn, default=list, nullable=False)
    links_resources: Mapped[list[dict[str, Any]]] = mapped_column(JSONColumn, default=list, nullable=False)
    reminders: Mapped[list[dict[str, Any]]] = mapped_column(JSONColumn, default=list, nullable=False)
    follow_up_tasks: Mapped[list[dict[str, Any]]] = mapped_column(JSONColumn, default=list, nullable=False)
    status: Mapped[PreparationStatus] = mapped_column(
        SQLEnum(PreparationStatus, native_enum=False),
        default=PreparationStatus.DRAFT,
        nullable=False,
    )

    # Relationships
    event: Mapped["Event"] = relationship(
        "Event",
        back_populates="preparation",
        foreign_keys="EventPreparation.event_id",
    )

    __table_args__ = (
        Index("ix_event_prep_event", "event_id"),
    )

    def __repr__(self) -> str:
        return f"<EventPreparation(id={self.id}, event_id={self.event_id}, status={self.status.value})>"


class Reminder(Base, TimestampMixin, SoftDeleteMixin):
    """Standalone reminders (not tied to events)."""

    __tablename__ = "reminders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    remind_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    timezone: Mapped[str] = mapped_column(String(50), default="Africa/Cairo", nullable=False)
    recurrence_rule: Mapped[str | None] = mapped_column(Text, nullable=True)
    channels: Mapped[list[str]] = mapped_column(JSONColumn, default=lambda: ["telegram"], nullable=False)
    priority: Mapped[str] = mapped_column(String(20), default="normal", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
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
    related_contact_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("contacts.id", ondelete="SET NULL"),
        nullable=True,
    )
    snoozed_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata: Mapped[dict[str, Any]] = mapped_column(JSONColumn, default=dict, nullable=False)

    __table_args__ = (
        Index("ix_reminder_remind_at", "remind_at"),
        Index("ix_reminder_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<Reminder(id={self.id}, title={self.title[:30]}, remind_at={self.remind_at}, status={self.status})>"