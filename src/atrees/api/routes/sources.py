"""
Sources API routes for ATREES.
"""

from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from atrees.database import get_db_session
from atrees.models.source import Source, SourceType, SourceStatus
from atrees.services.sync_service import SyncService
from atrees.core.security import EncryptionManager
from atrees.core.exceptions import NotFoundError, ValidationError
from atrees.connectors import list_connectors

router = APIRouter()


class SourceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    display_name: str = Field(..., min_length=1, max_length=200)
    connector_type: str
    config: dict[str, Any] = Field(default_factory=dict)


class SourceUpdate(BaseModel):
    display_name: str | None = Field(None, max_length=200)
    config: dict[str, Any] | None = None
    enabled: bool | None = None


class SourceResponse(BaseModel):
    id: int
    name: str
    display_name: str
    connector_type: str | None
    enabled: bool
    type: str
    status: str
    last_sync_at: str | None
    last_sync_status: str | None
    last_sync_error: str | None
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


@router.get("/", response_model=list[SourceResponse])
async def list_sources(db: AsyncSession = Depends(get_db_session)) -> list[Source]:
    """List all sources."""
    stmt = select(Source).where(Source.deleted_at.is_(None)).order_by(Source.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/connectors")
async def list_available_connectors() -> list[dict]:
    """List available connector types."""
    return list_connectors()


@router.post("/", response_model=SourceResponse, status_code=status.HTTP_201_CREATED)
async def create_source(
    source_data: SourceCreate,
    db: AsyncSession = Depends(get_db_session),
) -> Source:
    """Create a new source."""
    sync_service = SyncService(db)

    # Validate connector type
    try:
        source = await sync_service.create_source(
            name=source_data.name,
            display_name=source_data.display_name,
            connector_type=source_data.connector_type,
            config=source_data.config,
        )
    except ValueError as e:
        raise ValidationError(str(e))

    return source


@router.get("/{source_id}", response_model=SourceResponse)
async def get_source(
    source_id: int,
    db: AsyncSession = Depends(get_db_session),
) -> Source:
    """Get source by ID."""
    source = await db.get(Source, source_id)
    if not source or source.deleted_at:
        raise NotFoundError("Source", source_id)
    return source


@router.patch("/{source_id}", response_model=SourceResponse)
async def update_source(
    source_id: int,
    source_data: SourceUpdate,
    db: AsyncSession = Depends(get_db_session),
) -> Source:
    """Update source configuration."""
    sync_service = SyncService(db)

    update_data = source_data.model_dump(exclude_unset=True)

    if "config" in update_data:
        source = await sync_service.update_source_config(source_id, update_data["config"])
        # Return updated source
        source = await db.get(Source, source_id)
        return source

    # For other fields, direct update
    source = await db.get(Source, source_id)
    if not source or source.deleted_at:
        raise NotFoundError("Source", source_id)

    for key, value in update_data.items():
        if hasattr(source, key):
            setattr(source, key, value)

    await db.commit()
    await db.refresh(source)
    return source


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    source_id: int,
    db: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete (soft) a source."""
    sync_service = SyncService(db)
    success = await sync_service.delete_source(source_id)
    if not success:
        raise NotFoundError("Source", source_id)


@router.post("/{source_id}/sync")
async def sync_source(
    source_id: int,
    incremental: bool = True,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Trigger manual sync for a source."""
    sync_service = SyncService(db)
    result = await sync_service.sync_source(source_id, incremental)
    return {
        "status": result.status.value,
        "items_processed": result.items_processed,
        "items_created": result.items_created,
        "items_updated": result.items_updated,
        "items_failed": result.items_failed,
        "errors": result.errors,
    }


@router.post("/{source_id}/test")
async def test_source(
    source_id: int,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Test connection to a source."""
    sync_service = SyncService(db)
    success, message = await sync_service.test_source(source_id)
    return {"success": success, "message": message}


@router.get("/{source_id}/status")
async def get_source_status(
    source_id: int,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Get detailed source status."""
    sync_service = SyncService(db)
    return await sync_service.get_source_status(source_id)