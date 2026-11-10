"""
Task service for ATREES.

Business logic for task management, 1-3-5 planning, and task extraction.
"""

from datetime import datetime, date, timedelta
from typing import Any

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from atrees.models.task import Task, Project, TaskStatus, TaskPriority, DayPlanSlot, ApprovalState
from atrees.models.calendar import Event
from atrees.core.logging import get_logger
from atrees.core.exceptions import TaskPlanningError, NotFoundError
from atrees.config import get_settings

logger = get_logger(__name__)


class TaskService:
    """Service for task management and daily planning."""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.settings = get_settings()

    # --- Task CRUD ---

    async def create_task(
        self,
        title: str,
        description: str | None = None,
        category: str | None = None,
        project_id: int | None = None,
        priority: int = 3,
        due_date: date | None = None,
        due_time: str | None = None,
        estimated_minutes: int | None = None,
        energy_level: int | None = None,
        source_id: int | None = None,
        source_task_id: str | None = None,
        source_message_id: int | None = None,
        confidence: float = 1.0,
        approval_state: ApprovalState = ApprovalState.AUTO,
        tags: list[str] | None = None,
    ) -> Task:
        """Create a new task."""
        task = Task(
            title=title,
            description=description,
            category=category,
            project_id=project_id,
            priority=priority,
            status=TaskStatus.INBOX,
            due_date=due_date,
            estimated_duration_minutes=estimated_minutes,
            energy_level=energy_level,
            source_id=source_id,
            source_task_id=source_task_id,
            source_message_id=source_message_id,
            confidence=confidence,
            approval_state=approval_state,
            tags=tags or [],
        )
        self.db.add(task)
        await self.db.commit()
        await self.db.refresh(task)
        logger.info("task_created", task_id=task.id, title=title[:50])
        return task

    async def get_task(self, task_id: int) -> Task | None:
        """Get task by ID."""
        return await self.db.get(Task, task_id)

    async def update_task(self, task_id: int, **kwargs) -> Task:
        """Update task fields."""
        task = await self.get_task(task_id)
        if not task:
            raise NotFoundError("Task", task_id)

        for key, value in kwargs.items():
            if hasattr(task, key):
                setattr(task, key, value)

        task.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(task)
        return task

    async def delete_task(self, task_id: int, soft: bool = True) -> bool:
        """Delete (or soft delete) a task."""
        task = await self.get_task(task_id)
        if not task:
            return False

        if soft:
            task.soft_delete()
        else:
            await self.db.delete(task)

        await self.db.commit()
        return True

    async def list_tasks(
        self,
        status: TaskStatus | list[TaskStatus] | None = None,
        project_id: int | None = None,
        category: str | None = None,
        day_plan_date: date | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Task]:
        """List tasks with filters."""
        stmt = select(Task).where(Task.deleted_at.is_(None))

        if status:
            if isinstance(status, list):
                stmt = stmt.where(Task.status.in_(status))
            else:
                stmt = stmt.where(Task.status == status)

        if project_id:
            stmt = stmt.where(Task.project_id == project_id)

        if category:
            stmt = stmt.where(Task.category == category)

        if day_plan_date:
            stmt = stmt.where(Task.day_plan_date == day_plan_date)

        stmt = stmt.order_by(Task.priority, Task.due_date.nulls_last(), Task.created_at.desc())
        stmt = stmt.limit(limit).offset(offset)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    # --- 1-3-5 Daily Planning ---

    async def get_today_plan(self, target_date: date | None = None) -> dict[str, Any]:
        """Get 1-3-5 plan for a specific date."""
        if target_date is None:
            target_date = date.today()

        settings = self.settings.tasks

        # Get tasks planned for this date
        tasks = await self.list_tasks(day_plan_date=target_date)

        # Organize by slot
        big_tasks = [t for t in tasks if t.day_plan_slot == DayPlanSlot.BIG]
        medium_tasks = [t for t in tasks if t.day_plan_slot == DayPlanSlot.MEDIUM]
        small_tasks = [t for t in tasks if t.day_plan_slot == DayPlanSlot.SMALL]
        unslotted = [t for t in tasks if t.day_plan_slot is None]

        # Get calendar events for the day
        events = await self._get_day_events(target_date)

        return {
            "date": target_date.isoformat(),
            "big": [self._task_to_dict(t) for t in big_tasks[:settings.BIG_TASK_COUNT]],
            "medium": [self._task_to_dict(t) for t in medium_tasks[:settings.MEDIUM_TASK_COUNT]],
            "small": [self._task_to_dict(t) for t in small_tasks[:settings.SMALL_TASK_COUNT]],
            "unslotted": [self._task_to_dict(t) for t in unslotted],
            "events": events,
            "capacity": {
                "big": settings.BIG_TASK_COUNT,
                "medium": settings.MEDIUM_TASK_COUNT,
                "small": settings.SMALL_TASK_COUNT,
            },
        }

    async def assign_day_plan_slot(
        self,
        task_id: int,
        slot: DayPlanSlot,
        plan_date: date | None = None,
    ) -> Task:
        """Assign a task to a 1-3-5 slot."""
        task = await self.get_task(task_id)
        if not task:
            raise NotFoundError("Task", task_id)

        if plan_date is None:
            plan_date = date.today()

        # Check slot capacity
        current_count = await self._count_tasks_in_slot(slot, plan_date)
        capacity = getattr(self.settings.tasks, f"{slot.value.upper()}_TASK_COUNT")

        if current_count >= capacity:
            raise TaskPlanningError(
                f"Slot {slot.value} is full for {plan_date} (capacity: {capacity})"
            )

        task.day_plan_slot = slot
        task.day_plan_date = plan_date
        task.status = TaskStatus.SCHEDULED
        await self.db.commit()
        await self.db.refresh(task)
        return task

    async def auto_plan_day(self, target_date: date | None = None) -> dict[str, Any]:
        """Automatically plan a day using 1-3-5 method."""
        if target_date is None:
            target_date = date.today()

        # Get available tasks (approved, not scheduled, not completed)
        available_tasks = await self.list_tasks(
            status=[TaskStatus.APPROVED, TaskStatus.INBOX],
            day_plan_date=None,
        )

        # Filter out already planned for this date
        available_tasks = [t for t in available_tasks if t.day_plan_date != target_date]

        # Sort by priority, due date, energy level
        available_tasks.sort(key=lambda t: (
            t.priority,
            t.due_date or date.max,
            -(t.energy_level or 0),
        ))

        settings = self.settings.tasks
        plan = {"big": [], "medium": [], "small": []}

        # Assign big task (highest priority, longest duration)
        for task in available_tasks:
            if len(plan["big"]) < settings.BIG_TASK_COUNT:
                if (task.estimated_duration_minutes or 60) >= 60:
                    plan["big"].append(task)
                    continue
            break

        # Assign medium tasks
        for task in available_tasks:
            if task in plan["big"]:
                continue
            if len(plan["medium"]) < settings.MEDIUM_TASK_COUNT:
                if (task.estimated_duration_minutes or 30) >= 30:
                    plan["medium"].append(task)
                    continue
            break

        # Assign small tasks
        for task in available_tasks:
            if task in plan["big"] or task in plan["medium"]:
                continue
            if len(plan["small"]) < settings.SMALL_TASK_COUNT:
                if (task.estimated_duration_minutes or 15) <= 30:
                    plan["small"].append(task)
                    continue
            break

        # Actually assign in database
        for slot_name, tasks in plan.items():
            slot = DayPlanSlot(slot_name)
            for task in tasks:
                task.day_plan_slot = slot
                task.day_plan_date = target_date
                task.status = TaskStatus.SCHEDULED

        await self.db.commit()

        return {
            "date": target_date.isoformat(),
            "assigned": {k: [self._task_to_dict(t) for t in v] for k, v in plan.items()},
        }

    async def _count_tasks_in_slot(self, slot: DayPlanSlot, plan_date: date) -> int:
        """Count tasks assigned to a slot on a date."""
        stmt = select(func.count(Task.id)).where(
            Task.day_plan_slot == slot,
            Task.day_plan_date == plan_date,
            Task.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        return result.scalar() or 0

    async def _get_day_events(self, target_date: date) -> list[dict]:
        """Get events for a specific day."""
        start = datetime.combine(target_date, datetime.min.time())
        end = start + timedelta(days=1)

        stmt = select(Event).where(
            Event.start_datetime >= start,
            Event.start_datetime < end,
            Event.deleted_at.is_(None),
            Event.status != "cancelled",
        ).order_by(Event.start_datetime)

        result = await self.db.execute(stmt)
        events = result.scalars().all()

        return [
            {
                "id": e.id,
                "title": e.title,
                "start": e.start_datetime.isoformat(),
                "end": e.end_datetime.isoformat() if e.end_datetime else None,
                "location": e.location,
            }
            for e in events
        ]

    def _task_to_dict(self, task: Task) -> dict[str, Any]:
        """Convert task to dictionary."""
        return {
            "id": task.id,
            "title": task.title,
            "description": task.description,
            "priority": task.priority,
            "status": task.status.value,
            "due_date": task.due_date.isoformat() if task.due_date else None,
            "estimated_minutes": task.estimated_duration_minutes,
            "energy_level": task.energy_level,
            "project_id": task.project_id,
            "tags": task.tags,
        }

    # --- Project Management ---

    async def create_project(
        self,
        name: str,
        description: str | None = None,
        category: str | None = None,
        color: str | None = None,
        parent_id: int | None = None,
    ) -> Project:
        """Create a new project."""
        project = Project(
            name=name,
            description=description,
            category=category,
            color=color,
            parent_project_id=parent_id,
        )
        self.db.add(project)
        await self.db.commit()
        await self.db.refresh(project)
        return project

    async def get_project(self, project_id: int) -> Project | None:
        """Get project by ID."""
        return await self.db.get(Project, project_id)

    async def list_projects(
        self,
        status: str | None = None,
        category: str | None = None,
    ) -> list[Project]:
        """List projects."""
        stmt = select(Project).where(Project.deleted_at.is_(None))

        if status:
            stmt = stmt.where(Project.status == status)
        if category:
            stmt = stmt.where(Project.category == category)

        stmt = stmt.order_by(Project.updated_at.desc())
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    # --- Task Extraction from Messages ---

    async def extract_tasks_from_message(
        self,
        message_id: int,
        message_text: str,
        source_id: int,
    ) -> list[Task]:
        """
        Extract tasks from a message using AI.

        This is a placeholder - actual implementation would use AI provider.
        """
        # TODO: Implement AI-based task extraction
        # For now, return empty list
        logger.info("task_extraction_placeholder", message_id=message_id)
        return []