"""Sanity tests for the existing domain schema."""

from atrees.models import Base, Task, Source, KnowledgeFact, Event, Notification
from atrees.models.task import TaskStatus, DayPlanSlot, ApprovalState


def test_core_tables_are_registered() -> None:
    required = {
        "sources", "sync_states", "raw_items", "conversations", "messages",
        "contacts", "tasks", "projects", "events", "reminders",
        "knowledge_facts", "evidence", "web_sources", "research_reports",
        "notifications", "automation_jobs", "audit_logs", "user_preferences",
    }
    assert required.issubset(Base.metadata.tables)
    assert "connector_type" in Base.metadata.tables["sources"].columns


def test_task_lifecycle_has_review_and_approval_states() -> None:
    assert TaskStatus.NEEDS_REVIEW.value == "needs_review"
    assert TaskStatus.APPROVED.value == "approved"
    assert DayPlanSlot.BIG.value == "big"
    assert ApprovalState.PENDING.value == "pending"


def test_core_models_are_importable() -> None:
    assert all((Source, Task, KnowledgeFact, Event, Notification))
