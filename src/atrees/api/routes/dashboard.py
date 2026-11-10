"""
Dashboard API routes for ATREES.

Aggregated data for the main dashboard view.
"""

from datetime import date, datetime, timedelta
from typing import Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from atrees.database import get_db_session
from atrees.models.task import Task, TaskStatus
from atrees.models.calendar import Event, EventStatus
from atrees.models.notification import Notification, NotificationStatus, NotificationPriority
from atrees.models.source import Source, SourceStatus
from atrees.models.knowledge import KnowledgeFact, FactStatus

router = APIRouter()


@router.get("/overview")
async def get_dashboard_overview(
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Get main dashboard overview data."""
    today = date.today()
    now = datetime.utcnow()

    # Tasks summary
    tasks_stmt = select(
        Task.status,
        func.count(Task.id).label("count")
    ).where(Task.deleted_at.is_(None)).group_by(Task.status)
    tasks_result = await db.execute(tasks_stmt)
    tasks_by_status = {row.status.value: row.count for row in tasks_result}

    # Today's tasks
    today_tasks_stmt = select(func.count(Task.id)).where(
        Task.day_plan_date == today,
        Task.deleted_at.is_(None),
        Task.status.in_([TaskStatus.APPROVED, TaskStatus.SCHEDULED, TaskStatus.IN_PROGRESS]),
    )
    today_tasks_count = await db.execute(today_tasks_stmt)
    today_tasks = today_tasks_count.scalar() or 0

    # Overdue tasks
    overdue_stmt = select(func.count(Task.id)).where(
        Task.due_date < today,
        Task.deleted_at.is_(None),
        Task.status.not_in([TaskStatus.COMPLETED, TaskStatus.CANCELLED]),
    )
    overdue_count = await db.execute(overdue_stmt)
    overdue = overdue_count.scalar() or 0

    # Upcoming events (next 7 days)
    week_later = now + timedelta(days=7)
    events_stmt = select(func.count(Event.id)).where(
        Event.start_datetime >= now,
        Event.start_datetime <= week_later,
        Event.deleted_at.is_(None),
        Event.status != EventStatus.CANCELLED,
    )
    events_count = await db.execute(events_stmt)
    upcoming_events = events_count.scalar() or 0

    # Today's events
    today_start = datetime.combine(today, datetime.min.time())
    today_end = today_start + timedelta(days=1)
    today_events_stmt = select(func.count(Event.id)).where(
        Event.start_datetime >= today_start,
        Event.start_datetime < today_end,
        Event.deleted_at.is_(None),
        Event.status != EventStatus.CANCELLED,
    )
    today_events_count = await db.execute(today_events_stmt)
    today_events = today_events_count.scalar() or 0

    # Unread notifications
    unread_stmt = select(func.count(Notification.id)).where(
        Notification.status.in_([NotificationStatus.PENDING, NotificationStatus.SENT]),
        Notification.read_at.is_(None),
    )
    unread_count = await db.execute(unread_stmt)
    unread_notifications = unread_count.scalar() or 0

    # Source status
    sources_stmt = select(Source.status, func.count(Source.id)).where(
        Source.deleted_at.is_(None)
    ).group_by(Source.status)
    sources_result = await db.execute(sources_stmt)
    sources_by_status = {row.status.value: row.count for row in sources_result}

    # Knowledge facts
    facts_stmt = select(func.count(KnowledgeFact.id)).where(
        KnowledgeFact.status == FactStatus.ACTIVE,
        KnowledgeFact.confidence >= 0.5,
    )
    facts_count = await db.execute(facts_stmt)
    active_facts = facts_count.scalar() or 0

    return {
        "date": today.isoformat(),
        "tasks": {
            "by_status": tasks_by_status,
            "today_planned": today_tasks,
            "overdue": overdue,
        },
        "events": {
            "today": today_events,
            "upcoming_week": upcoming_events,
        },
        "notifications": {
            "unread": unread_notifications,
        },
        "sources": {
            "by_status": sources_by_status,
        },
        "knowledge": {
            "active_facts": active_facts,
        },
    }


@router.get("/inbox")
async def get_unified_inbox(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Get unified inbox - items needing attention."""
    # Tasks needing review
    tasks_stmt = select(Task).where(
        Task.status == TaskStatus.NEEDS_REVIEW,
        Task.deleted_at.is_(None),
    ).order_by(Task.priority, Task.created_at.desc()).limit(limit).offset(offset)
    tasks_result = await db.execute(tasks_stmt)
    tasks = tasks_result.scalars().all()

    # Recent notifications
    notif_stmt = select(Notification).where(
        Notification.status.in_([NotificationStatus.SENT, NotificationStatus.PENDING]),
    ).order_by(Notification.created_at.desc()).limit(limit)
    notif_result = await db.execute(notif_stmt)
    notifications = notif_result.scalars().all()

    return {
        "tasks_needing_review": [
            {
                "id": t.id,
                "title": t.title,
                "priority": t.priority,
                "confidence": t.confidence,
                "source": t.source_id,
                "created_at": t.created_at.isoformat(),
            }
            for t in tasks
        ],
        "recent_notifications": [
            {
                "id": n.id,
                "title": n.title,
                "priority": n.priority.value,
                "status": n.status.value,
                "created_at": n.created_at.isoformat(),
            }
            for n in notifications
        ],
    }


@router.get("/calendar/week")
async def get_week_calendar(
    start_date: date | None = Query(None),
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Get events for a week view."""
    if start_date is None:
        start_date = date.today()
        # Start from Monday
        start_date = start_date - timedelta(days=start_date.weekday())

    end_date = start_date + timedelta(days=7)
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.min.time())

    stmt = select(Event).where(
        Event.start_datetime >= start_dt,
        Event.start_datetime < end_dt,
        Event.deleted_at.is_(None),
        Event.status != EventStatus.CANCELLED,
    ).order_by(Event.start_datetime)

    result = await db.execute(stmt)
    events = result.scalars().all()

    # Group by day
    days = {}
    for i in range(7):
        day = start_date + timedelta(days=i)
        days[day.isoformat()] = []

    for event in events:
        day_key = event.start_datetime.date().isoformat()
        if day_key in days:
            days[day_key].append({
                "id": event.id,
                "title": event.title,
                "start": event.start_datetime.isoformat(),
                "end": event.end_datetime.isoformat() if event.end_datetime else None,
                "location": event.location,
                "status": event.status.value,
            })

    return {
        "week_start": start_date.isoformat(),
        "week_end": (end_date - timedelta(days=1)).isoformat(),
        "days": days,
    }


@router.get("/stats")
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Get statistics for dashboard charts."""
    # Tasks completed over time (last 30 days)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)

    completed_stmt = select(
        func.date(Task.completed_at).label("date"),
        func.count(Task.id).label("count")
    ).where(
        Task.status == TaskStatus.COMPLETED,
        Task.completed_at >= thirty_days_ago,
    ).group_by(func.date(Task.completed_at)).order_by(func.date(Task.completed_at))

    completed_result = await db.execute(completed_stmt)
    tasks_completed = [
        {"date": row.date.isoformat(), "count": row.count}
        for row in completed_result
    ]

    # Tasks by category
    category_stmt = select(
        Task.category,
        func.count(Task.id).label("count")
    ).where(
        Task.deleted_at.is_(None),
    ).group_by(Task.category)
    category_result = await db.execute(category_stmt)
    tasks_by_category = [
        {"category": row.category or "Uncategorized", "count": row.count}
        for row in category_result
    ]

    # Sources sync health
    sources_stmt = select(Source.name, Source.last_sync_at, Source.last_sync_status).where(
        Source.deleted_at.is_(None),
    )
    sources_result = await db.execute(sources_stmt)
    sources_health = [
        {
            "name": row.name,
            "last_sync": row.last_sync_at.isoformat() if row.last_sync_at else None,
            "status": row.last_sync_status.value if row.last_sync_status else None,
        }
        for row in sources_result
    ]

    return {
        "tasks_completed_30d": tasks_completed,
        "tasks_by_category": tasks_by_category,
        "sources_health": sources_health,
    }