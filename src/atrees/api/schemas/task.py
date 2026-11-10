"""
Task schemas.
"""

from pydantic import BaseModel, Field
from typing import Any, Optional, List
from datetime import datetime, date, time
from enum import Enum


class TaskStatus(str, Enum):
    INBOX = "inbox"
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELLED = "cancelled"
    DEFERRED = "deferred"
    WAITING = "waiting"


class TaskPriority(int, Enum):
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4
    NONE = 5


class ApprovalState(str, Enum):
    AUTO = "auto"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class DayPlanSlot(str, Enum):
    BIG = "big"
    MEDIUM = "medium"
    SMALL = "small"
    EVENING = "evening"


class TaskBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    category: Optional[str] = Field(None, max_length=50)
    project_id: Optional[int] = None
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.INBOX
    due_date: Optional[date] = None
    due_time: Optional[time] = None
    estimated_duration_minutes: Optional[int] = None
    energy_level: Optional[int] = Field(None, ge=1, le=5)
    day_plan_slot: Optional[DayPlanSlot] = None
    day_plan_date: Optional[date] = None
    tags: List[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskCreate(TaskBase):
    source_id: Optional[int] = None
    source_task_id: Optional[str] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    category: Optional[str] = Field(None, max_length=50)
    project_id: Optional[int] = None
    priority: Optional[TaskPriority] = None
    status: Optional[TaskStatus] = None
    due_date: Optional[date] = None
    due_time: Optional[time] = None
    estimated_duration_minutes: Optional[int] = None
    energy_level: Optional[int] = Field(None, ge=1, le=5)
    day_plan_slot: Optional[DayPlanSlot] = None
    day_plan_date: Optional[date] = None
    tags: Optional[List[str]] = None
    metadata: Optional[dict[str, Any]] = None
    approval_state: Optional[ApprovalState] = None


class TaskResponse(TaskBase):
    id: int
    source_id: Optional[int] = None
    source_task_id: Optional[str] = None
    actual_duration_minutes: Optional[int] = None
    confidence: float
    approval_state: ApprovalState
    approval_requested_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    source_message_id: Optional[int] = None
    source_event_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DayPlanResponse(BaseModel):
    date: date
    big: Optional[TaskResponse] = None
    medium: List[TaskResponse] = Field(default_factory=list)
    small: List[TaskResponse] = Field(default_factory=list)
    evening: List[TaskResponse] = Field(default_factory=list)
    total_estimated_minutes: int = 0


class ProjectBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    category: Optional[str] = Field(None, max_length=50)
    color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    parent_project_id: Optional[int] = None


class ProjectCreate(ProjectBase):
    pass


class ProjectResponse(ProjectBase):
    id: int
    status: str
    progress: float
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True
