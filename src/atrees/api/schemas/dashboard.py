"""
Dashboard schemas.
"""

from pydantic import BaseModel, Field
from typing import Any, Optional, List
from datetime import datetime, date


class DashboardStats(BaseModel):
    total_tasks: int = 0
    tasks_by_status: dict[str, int] = Field(default_factory=dict)
    overdue_tasks: int = 0
    today_tasks: int = 0
    total_events: int = 0
    today_events: int = 0
    unread_notifications: int = 0
    active_sources: int = 0
    sync_errors: int = 0


class TodaySummary(BaseModel):
    date: date
    tasks: List[dict[str, Any]] = Field(default_factory=list)
    events: List[dict[str, Any]] = Field(default_factory=list)
    reminders: List[dict[str, Any]] = Field(default_factory=list)
    day_plan: dict[str, Any] = Field(default_factory=dict)
    weather: Optional[dict[str, Any]] = None
