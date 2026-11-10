"""
Knowledge and Memory models for ATREES.

Unified personal knowledge system with fact verification and evidence tracking.
"""

from datetime import datetime, date
from typing import Any
from sqlalchemy import (
    String,
    Text,
    Integer,
    DateTime,
    Date,
    Float,
    ForeignKey,
    Enum as SQLEnum,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from atrees.models.base import Base, TimestampMixin, SoftDeleteMixin, JSONColumn
import enum


class EvidenceCategory(str, enum.Enum):
    """Evidence categories for fact verification."""
    SELF_REPORTED = "SELF_REPORTED"
    OBSERVED = "OBSERVED"
    DEMONSTRATED = "DEMONSTRATED"
    EXTERNALLY_VERIFIED = "EXTERNALLY_VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    CONFLICTING = "CONFLICTING"
    OUTDATED = "OUTDATED"


class FactStatus(str, enum.Enum):
    """Knowledge fact status."""
    ACTIVE = "active"
    OUTDATED = "outdated"
    CONFLICTING = "conflicting"
    ARCHIVED = "archived"
    DELETED = "deleted"


class SkillStatus(str, enum.Enum):
    """Skill status."""
    LEARNING = "learning"
    MAINTAINING = "maintaining"
    RUSTY = "rusty"
    MASTERED = "mastered"


class GoalStatus(str, enum.Enum):
    """Goal status."""
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class KnowledgeFact(Base, TimestampMixin):
    """Extracted and verified facts about the user."""

    __tablename__ = "knowledge_facts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fact_text: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    subcategory: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    evidence_category: Mapped[EvidenceCategory] = mapped_column(
        SQLEnum(EvidenceCategory, native_enum=False),
        nullable=False,
        index=True,
    )
    confidence: Mapped[float] = mapped_column(Float, default=0.5, nullable=False, index=True)
    status: Mapped[FactStatus] = mapped_column(
        SQLEnum(FactStatus, native_enum=False),
        default=FactStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    source_platform: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    source_record_id: Mapped[str | None] = mapped_column(String(500), nullable=True, index=True)
    extraction_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.utcnow(),
        nullable=False,
    )
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    conflicting_fact_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("knowledge_facts.id", ondelete="SET NULL"),
        nullable=True,
    )
    supersedes_fact_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("knowledge_facts.id", ondelete="SET NULL"),
        nullable=True,
    )
    metadata: Mapped[dict[str, Any]] = mapped_column(JSONColumn, default=dict, nullable=False)

    # Relationships
    evidence: Mapped[list["Evidence"]] = relationship(
        "Evidence",
        back_populates="fact",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    conflicting_fact: Mapped["KnowledgeFact | None"] = relationship(
        "KnowledgeFact",
        backref="conflicted_by",
        foreign_keys="KnowledgeFact.conflicting_fact_id",
        remote_side="KnowledgeFact.id",
        lazy="joined",
    )
    supersedes_fact: Mapped["KnowledgeFact | None"] = relationship(
        "KnowledgeFact",
        backref="superseded_by",
        foreign_keys="KnowledgeFact.supersedes_fact_id",
        remote_side="KnowledgeFact.id",
        lazy="joined",
    )

    __table_args__ = (
        Index("ix_kf_category", "category"),
        Index("ix_kf_evidence", "evidence_category"),
        Index("ix_kf_status", "status"),
        Index("ix_kf_source", "source_platform", "source_record_id"),
        Index("ix_kf_confidence", "confidence"),
    )

    def __repr__(self) -> str:
        return f"<KnowledgeFact(id={self.id}, category={self.category}, confidence={self.confidence:.2f}, status={self.status.value})>"


class Evidence(Base, TimestampMixin):
    """Supporting evidence for facts."""

    __tablename__ = "evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fact_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("knowledge_facts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_reference: Mapped[str] = mapped_column(String(500), nullable=False)
    excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    strength: Mapped[str] = mapped_column(String(20), default="supporting", nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.utcnow(),
        nullable=False,
    )
    metadata: Mapped[dict[str, Any]] = mapped_column(JSONColumn, default=dict, nullable=False)

    # Relationships
    fact: Mapped["KnowledgeFact"] = relationship("KnowledgeFact", back_populates="evidence")

    __table_args__ = (
        Index("ix_evidence_fact", "fact_id"),
    )

    def __repr__(self) -> str:
        return f"<Evidence(id={self.id}, fact_id={self.fact_id}, type={self.source_type}, strength={self.strength})>"


class Skill(Base, TimestampMixin, SoftDeleteMixin):
    """User skills and learning progress."""

    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    proficiency: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    years_experience: Mapped[float | None] = mapped_column(nullable=True)
    last_practiced: Mapped[date | None] = mapped_column(Date, nullable=True)
    learning_goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_fact_ids: Mapped[list[int]] = mapped_column(JSONColumn, default=list, nullable=False)
    status: Mapped[SkillStatus] = mapped_column(
        SQLEnum(SkillStatus, native_enum=False),
        default=SkillStatus.LEARNING,
        nullable=False,
        index=True,
    )
    metadata: Mapped[dict[str, Any]] = mapped_column(JSONColumn, default=dict, nullable=False)

    __table_args__ = (
        Index("ix_skill_category", "category"),
        Index("ix_skill_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<Skill(id={self.id}, name={self.name}, proficiency={self.proficiency}, status={self.status.value})>"


class Goal(Base, TimestampMixin, SoftDeleteMixin):
    """User goals with progress tracking."""

    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    timeframe: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[GoalStatus] = mapped_column(
        SQLEnum(GoalStatus, native_enum=False),
        default=GoalStatus.ACTIVE,
        nullable=False,
        index=True,
    )
    progress: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    metric: Mapped[str | None] = mapped_column(String(200), nullable=True)
    target_value: Mapped[float | None] = mapped_column(nullable=True)
    current_value: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    parent_goal_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("goals.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    related_project_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
    )
    related_skill_ids: Mapped[list[int]] = mapped_column(JSONColumn, default=list, nullable=False)
    metadata: Mapped[dict[str, Any]] = mapped_column(JSONColumn, default=dict, nullable=False)

    # Relationships
    subgoals: Mapped[list["Goal"]] = relationship(
        "Goal",
        backref="parent",
        remote_side="Goal.id",
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_goal_status", "status"),
        Index("ix_goal_category", "category"),
        Index("ix_goal_timeframe", "timeframe"),
    )

    def __repr__(self) -> str:
        return f"<Goal(id={self.id}, title={self.title[:30]}, progress={self.progress:.1f}%, status={self.status.value})>"