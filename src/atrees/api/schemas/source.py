"""
Source schemas.
"""

from pydantic import BaseModel, Field
from typing import Any, Optional
from datetime import datetime
from enum import Enum


class SourceType(str, Enum):
    TELEGRAM_MTPROTO = "telegram_mtproto"
    TELEGRAM_BOT = "telegram_bot"
    WHATSAPP = "whatsapp"
    GOOGLE_CALENDAR = "google_calendar"
    GOOGLE_TASKS = "google_tasks"
    GMAIL = "gmail"
    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GROQ = "groq"
    CEREBRAS = "cerebras"
    OPENROUTER = "openrouter"
    GEMINI = "gemini"
    RSS = "rss"
    WEB_SCRAPER = "web_scraper"
    FILE_IMPORTER = "file_importer"
    MANUAL = "manual"


class SourceStatus(str, Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    SYNCING = "syncing"
    AUTH_REQUIRED = "auth_required"


class SourceBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    display_name: str = Field(..., min_length=1, max_length=200)
    type: SourceType
    config: dict[str, Any] = Field(default_factory=dict)


class SourceCreate(SourceBase):
    pass


class SourceUpdate(BaseModel):
    display_name: Optional[str] = Field(None, max_length=200)
    config: Optional[dict[str, Any]] = None
    status: Optional[SourceStatus] = None


class SourceResponse(SourceBase):
    id: int
    status: SourceStatus
    last_sync_at: Optional[datetime] = None
    last_sync_status: Optional[str] = None
    last_sync_error: Optional[str] = None
    sync_cursor: Optional[dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True
