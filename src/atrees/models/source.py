"""
Source and sync state models for ATREES.

Defines the core tables for managing external data sources and synchronization.
"""

from datetime import datetime
from typing import Any
from sqlalchemy import (
    String,
    Text,
    Integer,
    Boolean,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from atrees.models.base import Base, TimestampMixin, SoftDeleteMixin, JSONColumn
import enum


class SourceType(str, enum.Enum):
    """Types of data sources."""
    COMMUNICATION = "communication"
    CALENDAR = "calendar"
    EMAIL = "email"
    SOCIAL = "social"
    AI_CHAT = "ai_chat"
    DOCUMENT = "document"
    OTHER = "other"


class SourceStatus(str, enum.Enum):
    """Connection status of a source."""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    SYNCING = "syncing"


class SyncStatus(str, enum.Enum):
    """Status of a sync operation."""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class Source(Base, TimestampMixin, SoftDeleteMixin):
    """External data source connected to ATREES."""

    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    # Connector implementation key (e.g. telegram_mtproto); distinct from the
    # broad SourceType category (communication, calendar, email, ...).
    connector_type: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="1", nullable=False, index=True)
    type: Mapped[SourceType] = mapped_column(
        SQLEnum(SourceType, native_enum=False),
        nullable=False,
        index=True,
    )
    status: Mapped[SourceStatus] = mapped_column(
        SQLEnum(SourceStatus, native_enum=False),
        default=SourceStatus.DISCONNECTED,
        nullable=False,
        index=True,
    )
    config: Mapped[dict[str, Any]] = mapped_column(JSONColumn, default=dict, nullable=False)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync_status: Mapped[SyncStatus | None] = mapped_column(
        SQLEnum(SyncStatus, native_enum=False),
        nullable=True,
    )
    last_sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    sync_cursor: Mapped[dict[str, Any] | None] = mapped_column(JSONColumn, nullable=True)

    # Relationships
    sync_states: Mapped[list["SyncState"]] = relationship(
        "SyncState",
        back_populates="source",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    raw_items: Mapped[list["RawItem"]] = relationship(
        "RawItem",
        back_populates="source",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Source(id={self.id}, name={self.name}, connector_type={self.connector_type}, type={self.type.value}, status={self.status.value})>"


class SyncState(Base, TimestampMixin):
    """Tracks synchronization progress per source and entity type."""

    __tablename__ = "sync_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    cursor_key: Mapped[str] = mapped_column(String(200), nullable=False)
    cursor_value: Mapped[str] = mapped_column(Text, nullable=False)
    items_processed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    items_failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.utcnow(),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="running", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    source: Mapped["Source"] = relationship("Source", back_populates="sync_states")

    __table_args__ = (
        UniqueConstraint("source_id", "entity_type", "cursor_key", name="uq_sync_state_source_entity_cursor"),
        Index("ix_sync_state_source_entity", "source_id", "entity_type"),
    )

    def __repr__(self) -> str:
        return f"<SyncState(source_id={self.source_id}, entity={self.entity_type}, key={self.cursor_key}, status={self.status})>"


class RawItem(Base, TimestampMixin):
    """Immutable raw records from all sources (write-once, append-only)."""

    __tablename__ = "raw_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_record_id: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    source_parent_id: Mapped[str | None] = mapped_column(String(500), nullable=True, index=True)
    item_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    raw_content: Mapped[dict[str, Any]] = mapped_column(JSONColumn, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.utcnow(),
        nullable=False,
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processing_status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False,
        index=True,
    )
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    source: Mapped["Source"] = relationship("Source", back_populates="raw_items")

    __table_args__ = (
        UniqueConstraint("source_id", "source_record_id", name="uq_raw_item_source_record"),
        Index("ix_raw_item_source_parent", "source_id", "source_parent_id"),
        Index("ix_raw_item_type", "item_type"),
        Index("ix_raw_item_source_ts", "source_id", "source_timestamp"),
        Index("ix_raw_item_status", "processing_status"),
        Index("ix_raw_item_hash", "content_hash"),
    )

    def __repr__(self) -> str:
        return f"<RawItem(id={self.id}, source={self.source_id}, type={self.item_type}, record={self.source_record_id[:20]})>"