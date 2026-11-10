"""
Pydantic schemas for ATREES API.
"""

from .source import SourceResponse, SourceCreate, SourceUpdate, SourceType, SourceStatus
from .task import (
    TaskResponse, TaskCreate, TaskUpdate, DayPlanResponse, DayPlanSlot,
    TaskStatus, TaskPriority, ApprovalState, ProjectResponse, ProjectCreate
)
from .connector import ConnectorResponse, ConnectorStatus, ConnectorType, SyncStatusResponse
from .dashboard import DashboardStats, TodaySummary
from .notification import NotificationResponse, NotificationCreate, NotificationPriority, NotificationStatus
from .health import HealthResponse

__all__ = [
    "SourceResponse",
    "SourceCreate",
    "SourceUpdate",
    "SourceType",
    "SourceStatus",
    "TaskResponse",
    "TaskCreate",
    "TaskUpdate",
    "DayPlanResponse",
    "DayPlanSlot",
    "TaskStatus",
    "TaskPriority",
    "ApprovalState",
    "ProjectResponse",
    "ProjectCreate",
    "ConnectorResponse",
    "ConnectorStatus",
    "ConnectorType",
    "SyncStatusResponse",
    "DashboardStats",
    "TodaySummary",
    "NotificationResponse",
    "NotificationCreate",
    "NotificationPriority",
    "NotificationStatus",
    "HealthResponse",
]
