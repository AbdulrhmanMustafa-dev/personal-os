"""
Tasks API routes for ATREES.
"""

from datetime import date, datetime, time
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from atrees.database import get_db_session
from atrees.models.task import Task, Project, TaskStatus, TaskPriority, DayPlanSlot, ApprovalState
from atrees.services.task_service import TaskService
from atrees.core.exceptions import NotFoundError, TaskPlanningError
from atrees.api.schemas import (
    TaskResponse, TaskCreate, TaskUpdate, TaskStatus as SchemaTaskStatus,
    TaskPriority as SchemaTaskPriority, DayPlanSlot as SchemaDayPlanSlot,
    ApprovalState as SchemaApprovalState, DayPlanResponse,
    ProjectResponse, ProjectCreate
)

router = APIRouter()


def _task_to_response(task: Task) -> TaskResponse:
    """Convert SQLAlchemy Task to Pydantic TaskResponse."""
    return TaskResponse(
        id=task.id,
        source_id=task.source_id,
        source_task_id=task.source_task_id,
        title=task.title,
        description=task.description,
        category=task.category,
        project_id=task.project_id,
        priority=SchemaTaskPriority(task.priority),
        status=SchemaTaskStatus(task.status.value),
        due_date=task.due_date,
        due_time=task.due_time,
        estimated_duration_minutes=task.estimated_duration_minutes,
        actual_duration_minutes=task.actual_duration_minutes,
        energy_level=task.energy_level,
        day_plan_slot=SchemaDayPlanSlot(task.day_plan_slot.value) if task.day_plan_slot else None,
        day_plan_date=task.day_plan_date,
        confidence=task.confidence,
        approval_state=SchemaApprovalState(task.approval_state.value),
        approval_requested_at=task.approval_requested_at,
        approved_at=task.approved_at,
        approved_by=task.approved_by,
        source_message_id=task.source_message_id,
        source_event_id=task.source_event_id,
        tags=task.tags or [],
        metadata=task.metadata or {},
        created_at=task.created_at,
        updated_at=task.updated_at,
        completed_at=task.completed_at,
        deleted_at=task.deleted_at,
    )


def _project_to_response(project: Project) -> ProjectResponse:
    """Convert SQLAlchemy Project to Pydantic ProjectResponse."""
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        category=project.category,
        color=project.color,
        status=project.status.value,
        progress=project.progress,
        parent_project_id=project.parent_project_id,
        metadata=project.metadata or {},
        created_at=project.created_at,
        updated_at=project.updated_at,
        deleted_at=project.deleted_at,
    )


# --- Routes ---

@router.get("/", response_model=list[TaskResponse])
async def list_tasks(
    status: str | None = Query(None),
    project_id: int | None = Query(None),
    category: str | None = Query(None),
    day_plan_date: date | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db_session),
) -> list[TaskResponse]:
    """List tasks with filters."""
    task_service = TaskService(db)

    # Parse status filter
    status_filter = None
    if status:
        try:
            status_filter = TaskStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    tasks = await task_service.list_tasks(
        status=status_filter,
        project_id=project_id,
        category=category,
        day_plan_date=day_plan_date,
        limit=limit,
        offset=offset,
    )
    return [_task_to_response(t) for t in tasks]


@router.post("/", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    task_data: TaskCreate,
    db: AsyncSession = Depends(get_db_session),
) -> TaskResponse:
    """Create a new task."""
    task_service = TaskService(db)

    # Parse due_time
    due_time = None
    if task_data.due_time:
        try:
            due_time = datetime.strptime(task_data.due_time, "%H:%M").time()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid due_time format, use HH:MM")

    task = await task_service.create_task(
        title=task_data.title,
        description=task_data.description,
        category=task_data.category,
        project_id=task_data.project_id,
        priority=task_data.priority.value,
        due_date=task_data.due_date,
        due_time=due_time,
        estimated_minutes=task_data.estimated_duration_minutes,
        energy_level=task_data.energy_level,
        source_id=task_data.source_id,
        source_task_id=task_data.source_task_id,
        confidence=task_data.confidence,
        approval_state=ApprovalState(task_data.approval_state.value),
        tags=task_data.tags,
    )
    return _task_to_response(task)


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: int,
    db: AsyncSession = Depends(get_db_session),
) -> TaskResponse:
    """Get task by ID."""
    task_service = TaskService(db)
    task = await task_service.get_task(task_id)
    if not task:
        raise NotFoundError("Task", task_id)
    return _task_to_response(task)


@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int,
    task_data: TaskUpdate,
    db: AsyncSession = Depends(get_db_session),
) -> TaskResponse:
    """Update a task."""
    task_service = TaskService(db)

    update_data = task_data.model_dump(exclude_unset=True)

    # Parse enums
    if "status" in update_data:
        try:
            update_data["status"] = TaskStatus(update_data["status"])
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {update_data['status']}")

    if "day_plan_slot" in update_data and update_data["day_plan_slot"]:
        try:
            update_data["day_plan_slot"] = DayPlanSlot(update_data["day_plan_slot"])
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid day_plan_slot: {update_data['day_plan_slot']}")

    if "approval_state" in update_data and update_data["approval_state"]:
        try:
            update_data["approval_state"] = ApprovalState(update_data["approval_state"])
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid approval_state: {update_data['approval_state']}")

    # Parse due_time
    if "due_time" in update_data and update_data["due_time"]:
        try:
            update_data["due_time"] = datetime.strptime(update_data["due_time"], "%H:%M").time()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid due_time format, use HH:MM")

    task = await task_service.update_task(task_id, **update_data)
    return _task_to_response(task)


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: int,
    soft: bool = Query(True),
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete a task."""
    task_service = TaskService(db)
    success = await task_service.delete_task(task_id, soft=soft)
    if not success:
        raise NotFoundError("Task", task_id)


@router.post("/{task_id}/assign-slot", response_model=TaskResponse)
async def assign_day_plan_slot(
    task_id: int,
    slot: str,
    plan_date: date | None = None,
    db: AsyncSession = Depends(get_db_session),
) -> TaskResponse:
    """Assign task to a 1-3-5 slot."""
    task_service = TaskService(db)

    try:
        day_plan_slot = DayPlanSlot(slot)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid slot: {slot}")

    try:
        task = await task_service.assign_day_plan_slot(task_id, day_plan_slot, plan_date)
    except TaskPlanningError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _task_to_response(task)


@router.get("/plan/today", response_model=DayPlanResponse)
async def get_today_plan(
    target_date: date | None = Query(None),
    db: AsyncSession = Depends(get_db_session),
) -> DayPlanResponse:
    """Get 1-3-5 plan for today (or specified date)."""
    task_service = TaskService(db)
    plan = await task_service.get_today_plan(target_date)
    
    # Convert to Pydantic response
    return DayPlanResponse(
        date=target_date or date.today(),
        big=_task_to_response(plan["big"]) if plan.get("big") else None,
        medium=[_task_to_response(t) for t in plan.get("medium", [])],
        small=[_task_to_response(t) for t in plan.get("small", [])],
        evening=[_task_to_response(t) for t in plan.get("evening", [])],
        total_estimated_minutes=plan.get("total_estimated_minutes", 0),
    )


@router.post("/plan/auto", response_model=DayPlanResponse)
async def auto_plan_day(
    target_date: date | None = Query(None),
    db: AsyncSession = Depends(get_db_session),
) -> DayPlanResponse:
    """Automatically plan a day using 1-3-5 method."""
    task_service = TaskService(db)
    plan = await task_service.auto_plan_day(target_date)
    
    return DayPlanResponse(
        date=target_date or date.today(),
        big=_task_to_response(plan["big"]) if plan.get("big") else None,
        medium=[_task_to_response(t) for t in plan.get("medium", [])],
        small=[_task_to_response(t) for t in plan.get("small", [])],
        evening=[_task_to_response(t) for t in plan.get("evening", [])],
        total_estimated_minutes=plan.get("total_estimated_minutes", 0),
    )


# --- Project Routes ---

@router.get("/projects/", response_model=list[ProjectResponse])
async def list_projects(
    status: str | None = Query(None),
    category: str | None = Query(None),
    db: AsyncSession = Depends(get_db_session),
) -> list[ProjectResponse]:
    """List projects."""
    task_service = TaskService(db)
    projects = await task_service.list_projects(status=status, category=category)
    return [_project_to_response(p) for p in projects]


@router.post("/projects/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    project_data: ProjectCreate,
    db: AsyncSession = Depends(get_db_session),
) -> ProjectResponse:
    """Create a new project."""
    task_service = TaskService(db)
    project = await task_service.create_project(
        name=project_data.name,
        description=project_data.description,
        category=project_data.category,
        color=project_data.color,
        parent_id=project_data.parent_id,
    )
    return _project_to_response(project)


@router.get("/projects/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: int,
    db: AsyncSession = Depends(get_db_session),
) -> ProjectResponse:
    """Get project by ID."""
    task_service = TaskService(db)
    project = await task_service.get_project(project_id)
    if not project:
        raise NotFoundError("Project", project_id)
    return _project_to_response(project)
