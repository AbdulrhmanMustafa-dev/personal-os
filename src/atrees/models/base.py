"""
Base model classes and mixins for ATREES.
"""

from datetime import datetime
from typing import Any
from sqlalchemy import DateTime, func, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, declared_attr
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON

from atrees.database import metadata


class Base(DeclarativeBase):
    """Base class for all models with naming convention."""
    metadata = metadata

    def __repr__(self) -> str:
        cols = ", ".join(
            f"{c.name}={getattr(self, c.name)!r}"
            for c in self.__table__.columns
            if not c.name.startswith("_")
        )
        return f"<{self.__class__.__name__}({cols})>"


class TimestampMixin:
    """Mixin for created_at and updated_at timestamps."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.utcnow(),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
        server_default=func.now(),
        server_onupdate=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    """Mixin for soft delete support."""

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def soft_delete(self) -> None:
        self.deleted_at = datetime.utcnow()

    def restore(self) -> None:
        self.deleted_at = None


# JSON column type that works with both SQLite and PostgreSQL
JSONColumn = JSON().with_variant(SQLiteJSON(), "sqlite")
