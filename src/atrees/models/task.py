"""
Task and Project models for ATREES.

Centralized task management with 1-3-5 daily planning support.
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
    Float,
    Boolean,
    ForeignKey,
    Enum as SQLEnum,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from atrees.models.base import Base, TimestampMixin, SoftDeleteMixin, JSONColumn
import enum


class TaskStatus(str, enum.Enum):
    """Task lifecycle states."""
    INBOX = "inbox"
    DRAFT = "draft"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DEFERRED = "deferred"
    CANCELLED = "cancelled"


class TaskPriority(int, enum.Enum):
    """Task priority levels (1=highest)."""
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4
    SOMEDAY = 5


class DayPlanSlot(str, enum.Enum):
    """1-3-5 daily planning slots."""
    BIG = "big"
    MEDIUM = "medium"
    SMALL = "small"


class ApprovalState(str, enum.Enum):
    """Approval workflow states."""
    AUTO = "auto"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class Task(Base, TimestampMixin, SoftDeleteMixin):
    """Centralized task management with 1-3-5 support."""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("sources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_task_id: Mapped[str | None] = mapped_column(String(500), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    project_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    priority: Mapped[int] = mapped_column(
        Integer,
        default=TaskPriority.MEDIUM.value,
        nullable=False,
    )
    status: Mapped[TaskStatus] = mapped_column(
        SQLEnum(TaskStatus, native_enum=False),
        default=TaskStatus.INBOX,
        nullable=False,
        index=True,
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    due_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    estimated_duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actual_duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    energy_level: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 1=Low, 2=Medium, 3=High
    day_plan_slot: Mapped[DayPlanSlot | None] = mapped_column(
        SQLEnum(DayPlanSlot, native_enum=False),
        nullable=True,
    )
    day_plan_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    approval_state: Mapped[ApprovalState] = mapped_column(
        SQLEnum(ApprovalState, native_enum=False),
        default=ApprovalState.AUTO,
        nullable=False,
        index=True,
    )
    approval_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    source_message_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_event_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("events.id", ondelete="SET NULL"),
        nullable=True,
    )
    tags: Mapped[list[str]] = mapped_column(JSONColumn, default=list, nullable=False)
    metadata: Mapped[dict[str, Any]] = mapped_column(JSONColumn, default=dict, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    project: Mapped["Project | None"] = relationship("Project", back_populates="tasks", lazy="joined")

    __table_args__ = (
        Index("ix_task_status", "status"),
        Index("ix_task_due_date", "due_date"),
        Index("ix_task_project", "project_id"),
        Index("ix_task_day_plan", "day_plan_date", "day_plan_slot"),
        Index("ix_task_priority", "priority"),
        Index("ix_task_approval", "approval_state"),
        Index("ix_task_source", "source_id", "source_task_id"),
    )

    def __repr__(self) -> str:
        return f"<Task(id={self.id}, title={self.title[:30]}, status={self.status.value}, priority={self.priority})>"


class Project(Base, TimestampMixin, SoftDeleteMixin):
    """Projects that group tasks and events."""

    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)  # Hex color
    icon: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False, index=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    progress: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    parent_project_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    metadata: Mapped[dict[str, Any]] = mapped_column(JSONColumn, default=dict, nullable=False)

    # Relationships
    tasks: Mapped[list["Task"]] = relationship("Task", back_populates="project", lazy="selectin")
    subprojects: Mapped[list["Project"]] = relationship(
        "Project",
        backref="parent",
        remote_side="Project.id",
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_project_status", "status"),
        Index("ix_project_parent", "parent_project_id"),
        Index("ix_project_category", "category"),
    )

    def __repr__(self) -> str:
        return f"<Project(id={self.id}, name={self.name}, status={self.status})>"