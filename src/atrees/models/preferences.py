"""
User Preferences model for ATREES.

System configuration stored in database for runtime updates.
"""

from datetime import datetime
from typing import Any
from sqlalchemy import (
    String,
    Text,
    Integer,
    DateTime,
    Boolean,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column

from atrees.models.base import Base, JSONColumn


class UserPreference(Base):
    """User preferences stored in database for runtime configuration."""

    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    value: Mapped[dict[str, Any] | list[Any] | str | int | float | bool] = mapped_column(
        JSONColumn, nullable=False
    )
    category: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_sensitive: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_pref_category", "category"),
    )

    def __repr__(self) -> str:
        return f"<UserPreference(key={self.key}, category={self.category})>"


# Default preferences to insert on initialization
DEFAULT_PREFERENCES = [
    {
        "key": "ai.provider_preference",
        "value": ["local", "groq", "cerebras", "openrouter", "gemini"],
        "category": "ai",
        "description": "Order of AI provider preference",
        "is_sensitive": False,
    },
    {
        "key": "ai.local_model",
        "value": "llama3.1:8b",
        "category": "ai",
        "description": "Default local model (Ollama)",
        "is_sensitive": False,
    },
    {
        "key": "ai.cloud_enabled",
        "value": False,
        "category": "ai",
        "description": "Enable cloud AI providers",
        "is_sensitive": False,
    },
    {
        "key": "notifications.quiet_hours_start",
        "value": "22:00",
        "category": "notifications",
        "description": "Quiet hours start time (24h format)",
        "is_sensitive": False,
    },
    {
        "key": "notifications.quiet_hours_end",
        "value": "08:00",
        "category": "notifications",
        "description": "Quiet hours end time (24h format)",
        "is_sensitive": False,
    },
    {
        "key": "notifications.priority_threshold",
        "value": "normal",
        "category": "notifications",
        "description": "Minimum priority for immediate notifications",
        "is_sensitive": False,
    },
    {
        "key": "calendar.timezone",
        "value": "Africa/Cairo",
        "category": "calendar",
        "description": "Default timezone for calendar",
        "is_sensitive": False,
    },
    {
        "key": "calendar.default_reminder_minutes",
        "value": 15,
        "category": "calendar",
        "description": "Default reminder minutes before event",
        "is_sensitive": False,
    },
    {
        "key": "tasks.default_priority",
        "value": 3,
        "category": "tasks",
        "description": "Default task priority (1-5)",
        "is_sensitive": False,
    },
    {
        "key": "tasks.day_plan_method",
        "value": "1-3-5",
        "category": "tasks",
        "description": "Daily planning method",
        "is_sensitive": False,
    },
    {
        "key": "privacy.encrypt_backups",
        "value": True,
        "category": "privacy",
        "description": "Encrypt backups with age",
        "is_sensitive": False,
    },
    {
        "key": "privacy.retention_days",
        "value": 365,
        "category": "privacy",
        "description": "Data retention period in days",
        "is_sensitive": False,
    },
    {
        "key": "sync.auto_sync_interval_minutes",
        "value": 30,
        "category": "sync",
        "description": "Automatic sync interval in minutes",
        "is_sensitive": False,
    },
    {
        "key": "ui.theme",
        "value": "system",
        "category": "ui",
        "description": "UI theme: light, dark, system",
        "is_sensitive": False,
    },
    {
        "key": "ui.language",
        "value": "ar",
        "category": "ui",
        "description": "UI language: ar, en",
        "is_sensitive": False,
    },
]