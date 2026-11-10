"""
Connector schemas.
"""

from pydantic import BaseModel, Field
from typing import Any, Optional, List
from datetime import datetime
from enum import Enum


class ConnectorType(str, Enum):
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


class ConnectorStatus(str, Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    SYNCING = "syncing"
    AUTH_REQUIRED = "auth_required"


class ConnectorBase(BaseModel):
    name: str
    type: ConnectorType
    config: dict[str, Any] = Field(default_factory=dict)


class ConnectorResponse(ConnectorBase):
    id: int
    status: ConnectorStatus
    last_sync_at: Optional[datetime] = None
    last_sync_status: Optional[str] = None
    last_sync_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SyncStatusResponse(BaseModel):
    source_id: int
    entity_type: str
    status: str
    items_processed: int
    items_failed: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
