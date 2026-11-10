"""
Communication models for ATREES.

Defines conversations, messages, and contacts from various sources.
"""

from datetime import datetime
from typing import Any
from sqlalchemy import (
    String,
    Text,
    Integer,
    DateTime,
    Boolean,
    ForeignKey,
    UniqueConstraint,
    Index,
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from atrees.models.base import Base, TimestampMixin, SoftDeleteMixin, JSONColumn


class Conversation(Base, TimestampMixin, SoftDeleteMixin):
    """Normalized conversation/thread metadata."""

    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_conversation_id: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # private, group, channel, email_thread
    participant_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    metadata: Mapped[dict[str, Any]] = mapped_column(JSONColumn, default=dict, nullable=False)

    # Relationships
    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        UniqueConstraint("source_id", "source_conversation_id", name="uq_conversation_source"),
        Index("ix_conversation_source", "source_id"),
    )

    def __repr__(self) -> str:
        return f"<Conversation(id={self.id}, source={self.source_id}, title={self.title})>"


class Message(Base, TimestampMixin):
    """Normalized messages with extracted content."""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    raw_item_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("raw_items.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    conversation_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_message_id: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    source_sender_id: Mapped[str | None] = mapped_column(String(500), nullable=True, index=True)
    sender_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    sender_role: Mapped[str | None] = mapped_column(String(50), nullable=True)  # user, assistant, system, bot
    content_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)
    has_media: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    media_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSONColumn, nullable=True)
    reply_to_message_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    forward_info: Mapped[dict[str, Any] | None] = mapped_column(JSONColumn, nullable=True)
    reaction_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONColumn, nullable=True)
    is_outgoing: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_edited: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    message_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )

    # Relationships
    raw_item: Mapped["RawItem"] = relationship("RawItem", lazy="joined")
    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")
    replies: Mapped[list["Message"]] = relationship(
        "Message",
        backref="reply_to",
        remote_side="Message.id",
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_message_conversation", "conversation_id"),
        Index("ix_message_sender", "source_sender_id"),
        Index("ix_message_timestamp", "message_timestamp"),
        Index("ix_message_conversation_ts", "conversation_id", "message_timestamp"),
        Index("ix_message_outgoing", "is_outgoing"),
    )

    def __repr__(self) -> str:
        return f"<Message(id={self.id}, conversation={self.conversation_id}, sender={self.sender_name}, ts={self.message_timestamp})>"


class Contact(Base, TimestampMixin, SoftDeleteMixin):
    """People and entities from communications."""

    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("sources.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_contact_id: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    relationship_category: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
    )  # family, friend, colleague, client, service, unknown
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    metadata: Mapped[dict[str, Any]] = mapped_column(JSONColumn, default=dict, nullable=False)

    __table_args__ = (
        UniqueConstraint("source_id", "source_contact_id", name="uq_contact_source"),
        Index("ix_contact_source", "source_id"),
        Index("ix_contact_name", "name"),
        Index("ix_contact_category", "relationship_category"),
        Index("ix_contact_email", "email"),
    )

    def __repr__(self) -> str:
        return f"<Contact(id={self.id}, name={self.name}, category={self.relationship_category})>"