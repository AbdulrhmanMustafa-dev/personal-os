"""
SQLAlchemy models for ATREES.

All models are defined in separate modules and exported here.
"""

from atrees.models.base import Base, TimestampMixin, SoftDeleteMixin
from atrees.models.source import Source, SyncState, RawItem
from atrees.models.communication import Conversation, Message, Contact
from atrees.models.task import Task, Project
from atrees.models.calendar import Event, EventPreparation, Reminder
from atrees.models.knowledge import KnowledgeFact, Evidence, Skill, Goal
from atrees.models.research import WebSource, ResearchReport, ResearchClaim
from atrees.models.notification import Notification, AutomationJob, AuditLog
from atrees.models.preferences import UserPreference

__all__ = [
    # Base
    "Base",
    "TimestampMixin",
    "SoftDeleteMixin",
    # Sources & Sync
    "Source",
    "SyncState",
    "RawItem",
    # Communication
    "Conversation",
    "Message",
    "Contact",
    # Tasks & Projects
    "Task",
    "Project",
    # Calendar
    "Event",
    "EventPreparation",
    "Reminder",
    # Knowledge
    "KnowledgeFact",
    "Evidence",
    "Skill",
    "Goal",
    # Research
    "WebSource",
    "ResearchReport",
    "ResearchClaim",
    # Notifications & Automation
    "Notification",
    "AutomationJob",
    "AuditLog",
    # Preferences
    "UserPreference",
]