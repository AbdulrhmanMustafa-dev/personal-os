"""
Sync service for ATREES.

Orchestrates synchronization across all connectors.
"""

import asyncio
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from atrees.connectors import get_connector, CONNECTOR_REGISTRY
from atrees.connectors.base import ConnectorConfig, SyncResult, SyncStatus
from atrees.models.source import Source, SourceStatus, SourceType
from atrees.core.logging import get_logger, log_sync_start, log_sync_complete, log_sync_error
from atrees.core.exceptions import SyncError, ConnectorError

logger = get_logger(__name__)


class SyncService:
    """Service for managing data synchronization across all sources."""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self._connector_instances: dict[int, Any] = {}
        self._sync_locks: dict[int, asyncio.Lock] = {}

    async def sync_source(self, source_id: int, incremental: bool = True) -> SyncResult:
        """
        Sync a single source.

        Args:
            source_id: ID of the source to sync
            incremental: Whether to do incremental sync

        Returns:
            SyncResult with sync statistics
        """
        # Get or create lock for this source
        if source_id not in self._sync_locks:
            self._sync_locks[source_id] = asyncio.Lock()

        async with self._sync_locks[source_id]:
            return await self._sync_source_unlocked(source_id, incremental)

    async def _sync_source_unlocked(self, source_id: int, incremental: bool) -> SyncResult:
        """Internal sync without lock (caller must handle locking)."""
        # Get source
        source = await self.db.get(Source, source_id)
        if not source:
            raise SyncError("unknown", f"Source {source_id} not found")

        if not source.status == SourceStatus.CONNECTED and not source.status == SourceStatus.SYNCING:
            # Try to connect if disconnected
            if source.status == SourceStatus.DISCONNECTED:
                pass  # Will be handled by connector
            elif source.status == SourceStatus.ERROR:
                raise SyncError(source.name, f"Source in error state: {source.last_sync_error}")

        # Create connector
        connector = await self._get_or_create_connector(source)
        if not connector:
            raise SyncError(source.name, f"Failed to create connector for {source.connector_type or '<missing connector_type>'}")

        log_sync_start(logger, source.name, source.connector_type, incremental)

        try:
            # Perform sync
            async with connector:
                result = await connector.sync(incremental=incremental)

            # Update source status
            source.last_sync_at = datetime.utcnow()
            source.last_sync_status = result.status
            source.status = SourceStatus.CONNECTED
            if result.errors:
                source.last_sync_error = "; ".join(result.errors[:3])
            else:
                source.last_sync_error = None

            await self.db.commit()

            log_sync_complete(
                logger,
                source.name,
                source.connector_type,
                result.items_processed,
                result.items_created,
                result.items_updated,
                result.items_failed,
                int((result.completed_at - result.started_at).total_seconds() * 1000) if result.completed_at else 0,
            )

            return result

        except Exception as e:
            source.status = SourceStatus.ERROR
            source.last_sync_error = str(e)
            await self.db.commit()

            log_sync_error(logger, source.name, source.connector_type, e, incremental)
            raise SyncError(source.name, str(e), connector_type=source.connector_type) from e

    async def sync_all(self, incremental: bool = True, max_concurrent: int = 3) -> dict[str, SyncResult]:
        """
        Sync all enabled sources concurrently.

        Args:
            incremental: Whether to do incremental sync
            max_concurrent: Maximum concurrent syncs

        Returns:
            Dict mapping source name to SyncResult
        """
        # Eligibility is independent of connection state: a newly configured
        # disconnected source must still be attempted by the sync worker.
        stmt = select(Source).where(
            Source.deleted_at.is_(None),
            Source.enabled.is_(True),
            Source.status != SourceStatus.ERROR,
        )
        result = await self.db.execute(stmt)
        enabled_sources = list(result.scalars().all())

        if not enabled_sources:
            logger.info("no_enabled_sources_to_sync")
            return {}

        # Run with semaphore for concurrency control
        semaphore = asyncio.Semaphore(max_concurrent)
        results: dict[str, SyncResult] = {}

        async def sync_one(source: Source) -> None:
            async with semaphore:
                try:
                    results[source.name] = await self.sync_source(source.id, incremental)
                except Exception as e:
                    logger.error("sync_source_failed", source=source.name, error=str(e))
                    results[source.name] = SyncResult(
                        status=SyncStatus.FAILED,
                        errors=[str(e)],
                    )

        await asyncio.gather(*[sync_one(s) for s in enabled_sources])
        return results

    async def get_source_status(self, source_id: int) -> dict[str, Any]:
        """Get detailed status for a source."""
        source = await self.db.get(Source, source_id)
        if not source:
            return {"error": "Source not found"}

        connector = await self._get_or_create_connector(source)
        connector_status = {}
        if connector:
            try:
                connector_status = await connector.get_sync_status()
            except Exception as e:
                connector_status = {"error": str(e)}

        return {
            "id": source.id,
            "name": source.name,
            "connector_type": source.connector_type,
            "enabled": source.enabled,
            "type": source.type.value,
            "status": source.status.value,
            "last_sync_at": source.last_sync_at.isoformat() if source.last_sync_at else None,
            "last_sync_status": source.last_sync_status.value if source.last_sync_status else None,
            "last_sync_error": source.last_sync_error,
            "connector_status": connector_status,
        }

    async def test_source(self, source_id: int) -> tuple[bool, str]:
        """Test connection to a source."""
        source = await self.db.get(Source, source_id)
        if not source:
            return False, "Source not found"

        connector = await self._get_or_create_connector(source)
        if not connector:
            return False, "Failed to create connector"

        try:
            async with connector:
                return await connector.test_connection()
        except Exception as e:
            return False, str(e)

    async def _get_or_create_connector(self, source: Source):
        """Get or create connector instance for a source."""
        if source.id in self._connector_instances:
            return self._connector_instances[source.id]

        try:
            if not source.connector_type:
                logger.error("source_missing_connector_type", source_id=source.id, source_name=source.name)
                return None
            connector_class = get_connector(source.connector_type)
        except ValueError:
            logger.error("unknown_connector_type", type=source.connector_type)
            return None

        # Prepare config
        config = ConnectorConfig(
            source_id=source.id,
            name=source.name,
            enabled=source.enabled,
            config=source.config,
            sync_interval_minutes=30,
        )

        connector = connector_class(config, self.db)
        self._connector_instances[source.id] = connector
        return connector

    async def create_source(
        self,
        name: str,
        display_name: str,
        connector_type: str,
        config: dict[str, Any],
    ) -> Source:
        """Create a new source."""
        # Validate connector type
        if connector_type not in CONNECTOR_REGISTRY:
            raise ValueError(f"Unknown connector type: {connector_type}")

        # Encrypt sensitive config
        from atrees.core.security import EncryptionManager
        encryption = EncryptionManager()
        encrypted_config = {}
        for key, value in config.items():
            if key in ("api_hash", "session_string", "bot_token", "client_secret", "api_key"):
                encrypted_config[key] = encryption.encrypt(str(value))
            else:
                encrypted_config[key] = value

        source_category = {
            "telegram_mtproto": SourceType.COMMUNICATION,
            "telegram_bot": SourceType.COMMUNICATION,
            "google_calendar": SourceType.CALENDAR,
            "google_tasks": SourceType.OTHER,
            "gmail": SourceType.EMAIL,
            "whatsapp_import": SourceType.COMMUNICATION,
            "chatgpt_import": SourceType.AI_CHAT,
            "gemini_import": SourceType.AI_CHAT,
            "claude_import": SourceType.AI_CHAT,
        }.get(connector_type, SourceType.OTHER)
        source = Source(
            name=name,
            display_name=display_name,
            connector_type=connector_type,
            enabled=True,
            type=source_category,
            config=encrypted_config,
            status=SourceStatus.DISCONNECTED,
        )
        self.db.add(source)
        await self.db.commit()
        await self.db.refresh(source)
        return source

    async def update_source_config(self, source_id: int, config: dict[str, Any]) -> Source:
        """Update source configuration."""
        source = await self.db.get(Source, source_id)
        if not source:
            raise ValueError(f"Source {source_id} not found")

        # Encrypt sensitive config
        from atrees.core.security import EncryptionManager
        encryption = EncryptionManager()
        encrypted_config = {}
        for key, value in config.items():
            if key in ("api_hash", "session_string", "bot_token", "client_secret", "api_key"):
                encrypted_config[key] = encryption.encrypt(str(value))
            else:
                encrypted_config[key] = value

        source.config = encrypted_config
        await self.db.commit()
        await self.db.refresh(source)

        # Invalidate connector cache
        if source_id in self._connector_instances:
            del self._connector_instances[source_id]

        return source

    async def delete_source(self, source_id: int) -> bool:
        """Soft delete a source."""
        source = await self.db.get(Source, source_id)
        if not source:
            return False

        source.deleted_at = datetime.utcnow()
        await self.db.commit()

        # Cleanup connector
        if source_id in self._connector_instances:
            del self._connector_instances[source_id]

        return True