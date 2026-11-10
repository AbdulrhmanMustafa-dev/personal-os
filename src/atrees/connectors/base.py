"""
Base connector interface for ATREES.

All data connectors must implement this interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class ConnectorStatus(str, Enum):
    """Connector connection status."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    SYNCING = "syncing"
    ERROR = "error"


class SyncStatus(str, Enum):
    """Synchronization result status."""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


@dataclass
class ConnectorConfig:
    """Base configuration for all connectors."""
    source_id: int
    name: str
    enabled: bool = True
    config: dict[str, Any] = field(default_factory=dict)  # Encrypted credentials
    sync_interval_minutes: int = 30


@dataclass
class SyncResult:
    """Result of a sync operation."""
    status: SyncStatus
    items_processed: int = 0
    items_created: int = 0
    items_updated: int = 0
    items_failed: int = 0
    errors: list[str] = field(default_factory=list)
    cursor: dict[str, Any] | None = None  # For incremental sync
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None

    def mark_completed(self) -> None:
        self.completed_at = datetime.utcnow()


class BaseConnector(ABC):
    """Abstract base class for all data connectors."""

    # Unique identifier for this connector type
    CONNECTOR_TYPE: str = "base"
    DISPLAY_NAME: str = "Base Connector"
    DESCRIPTION: str = ""

    # Capabilities
    SUPPORTS_INCREMENTAL: bool = True
    SUPPORTS_REALTIME: bool = False
    REQUIRES_USER_AUTH: bool = True

    def __init__(self, config: ConnectorConfig, db_session: "AsyncSession"):
        self.config = config
        self.db = db_session
        self.status = ConnectorStatus.DISCONNECTED
        self._client = None
        self._logger = None

    @property
    def logger(self):
        """Lazy logger initialization."""
        if self._logger is None:
            from atrees.core.logging import get_logger
            self._logger = get_logger(f"connector.{self.CONNECTOR_TYPE}")
        return self._logger

    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to the source."""
        pass

    @abstractmethod
    async def disconnect(self) -> bool:
        """Close connection gracefully."""
        pass

    @abstractmethod
    async def test_connection(self) -> tuple[bool, str]:
        """Test if connection works. Returns (success, message)."""
        pass

    @abstractmethod
    async def sync(self, incremental: bool = True) -> SyncResult:
        """Perform synchronization."""
        pass

    @abstractmethod
    async def get_sync_status(self) -> dict[str, Any]:
        """Get current sync status and cursor info."""
        pass

    async def __aenter__(self) -> "BaseConnector":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.disconnect()

    async def _update_source_status(self, status: ConnectorStatus, error: str | None = None) -> None:
        """Update source status in database."""
        from atrees.models.source import Source, SourceStatus
        source = await self.db.get(Source, self.config.source_id)
        if source:
            source.status = SourceStatus(status.value)
            if error:
                source.last_sync_error = error
            await self.db.commit()

    async def _create_sync_state(
        self,
        entity_type: str,
        cursor_key: str,
        cursor_value: str,
        status: str = "running",
    ) -> None:
        """Create or update sync state record."""
        from atrees.models.source import SyncState
        from sqlalchemy import select

        stmt = select(SyncState).where(
            SyncState.source_id == self.config.source_id,
            SyncState.entity_type == entity_type,
            SyncState.cursor_key == cursor_key,
        )
        result = await self.db.execute(stmt)
        sync_state = result.scalar_one_or_none()

        if sync_state:
            sync_state.cursor_value = cursor_value
            sync_state.status = status
            sync_state.updated_at = datetime.utcnow()
        else:
            sync_state = SyncState(
                source_id=self.config.source_id,
                entity_type=entity_type,
                cursor_key=cursor_key,
                cursor_value=cursor_value,
                status=status,
            )
            self.db.add(sync_state)

        await self.db.commit()

    async def _get_sync_cursor(self, entity_type: str, cursor_key: str) -> str | None:
        """Get sync cursor value."""
        from atrees.models.source import SyncState
        from sqlalchemy import select

        stmt = select(SyncState.cursor_value).where(
            SyncState.source_id == self.config.source_id,
            SyncState.entity_type == entity_type,
            SyncState.cursor_key == cursor_key,
            SyncState.status == "completed",
        ).order_by(SyncState.completed_at.desc()).limit(1)

        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()