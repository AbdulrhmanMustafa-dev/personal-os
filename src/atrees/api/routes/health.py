"""
Health check routes for ATREES.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from atrees.database import get_db_session
from atrees.config import get_settings

router = APIRouter()


@router.get("/health")
async def health_check() -> dict:
    """Basic health check."""
    settings = get_settings()
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


@router.get("/health/detailed")
async def detailed_health_check(db: AsyncSession = Depends(get_db_session)) -> dict:
    """Detailed health check with database connectivity."""
    settings = get_settings()

    # Check database
    db_status = "healthy"
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = "unhealthy"

    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "database": db_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/health/ready")
async def readiness_check(db: AsyncSession = Depends(get_db_session)) -> dict:
    """Kubernetes readiness probe."""
    try:
        await db.execute(text("SELECT 1"))
        return {"ready": True}
    except Exception:
        return {"ready": False}