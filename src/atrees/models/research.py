"""
Research models for ATREES.

Verified internet research with source tracking and evidence.
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
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from atrees.models.base import Base, TimestampMixin, JSONColumn
import enum


class SourceType(str, enum.Enum):
    """Web source credibility types."""
    GOVERNMENT = "government"
    UNIVERSITY = "university"
    SCHOLARSHIP = "scholarship"
    DOCUMENTATION = "documentation"
    ACADEMIC = "academic"
    NEWS = "news"
    BLOG = "blog"
    OTHER = "other"


class CrawlStatus(str, enum.Enum):
    """Web crawling status."""
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    BLOCKED = "blocked"


class ReportStatus(str, enum.Enum):
    """Research report status."""
    DRAFT = "draft"
    VERIFIED = "verified"
    ARCHIVED = "archived"


class VerificationStatus(str, enum.Enum):
    """Claim verification status."""
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    CONTRADICTED = "contradicted"
    OUTDATED = "outdated"


class ResearchCategory(str, enum.Enum):
    """Research categories."""
    SCHOLARSHIP = "scholarship"
    INTERNSHIP = "internship"
    UNIVERSITY = "university"
    PROGRAMMING = "programming"
    CYBERSECURITY = "cybersecurity"
    TECH_NEWS = "tech_news"
    CAREER = "career"
    PERSONAL = "personal"


class WebSource(Base, TimestampMixin):
    """Verified external sources for research."""

    __tablename__ = "web_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    url: Mapped[str] = mapped_column(String(2000), nullable=False, unique=True, index=True)
    domain: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    publisher: Mapped[str | None] = mapped_column(String(200), nullable=True)
    source_type: Mapped[SourceType | None] = mapped_column(
        SQLEnum(SourceType, native_enum=False),
        nullable=True,
        index=True,
    )
    credibility_score: Mapped[float] = mapped_column(Float, default=0.5, nullable=False, index=True)
    last_crawled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    crawl_status: Mapped[CrawlStatus | None] = mapped_column(
        SQLEnum(CrawlStatus, native_enum=False),
        nullable=True,
    )
    robots_txt_allows: Mapped[bool | None] = mapped_column(nullable=True)
    metadata: Mapped[dict[str, Any]] = mapped_column(JSONColumn, default=dict, nullable=False)

    __table_args__ = (
        Index("ix_ws_domain", "domain"),
        Index("ix_ws_type", "source_type"),
        Index("ix_ws_credibility", "credibility_score"),
    )

    def __repr__(self) -> str:
        return f"<WebSource(id={self.id}, domain={self.domain}, type={self.source_type})>"


class ResearchReport(Base, TimestampMixin):
    """Structured research outputs."""

    __tablename__ = "research_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[ResearchCategory | None] = mapped_column(
        SQLEnum(ResearchCategory, native_enum=False),
        nullable=True,
        index=True,
    )
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    findings: Mapped[list[dict[str, Any]]] = mapped_column(JSONColumn, default=list, nullable=False)
    source_ids: Mapped[list[int]] = mapped_column(JSONColumn, default=list, nullable=False)
    status: Mapped[ReportStatus] = mapped_column(
        SQLEnum(ReportStatus, native_enum=False),
        default=ReportStatus.DRAFT,
        nullable=False,
        index=True,
    )
    confidence: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    requested_by: Mapped[str | None] = mapped_column(String(100), nullable=True)

    __table_args__ = (
        Index("ix_rr_category", "category"),
        Index("ix_rr_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<ResearchReport(id={self.id}, title={self.title[:30]}, category={self.category})>"


class ResearchClaim(Base, TimestampMixin):
    """Individual verified claims from research."""

    __tablename__ = "research_claims"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("research_reports.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    claim_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("web_sources.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    source_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    publisher: Mapped[str | None] = mapped_column(String(200), nullable=True)
    publication_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    event_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    retrieval_date: Mapped[date] = mapped_column(
        Date,
        default=lambda: date.today(),
        nullable=False,
    )
    supporting_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    verification_status: Mapped[VerificationStatus] = mapped_column(
        SQLEnum(VerificationStatus, native_enum=False),
        default=VerificationStatus.UNVERIFIED,
        nullable=False,
        index=True,
    )
    confidence: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    contradictory_evidence: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata: Mapped[dict[str, Any]] = mapped_column(JSONColumn, default=dict, nullable=False)

    __table_args__ = (
        Index("ix_rc_report", "report_id"),
        Index("ix_rc_verification", "verification_status"),
    )

    def __repr__(self) -> str:
        return f"<ResearchClaim(id={self.id}, report_id={self.report_id}, status={self.verification_status.value})>"