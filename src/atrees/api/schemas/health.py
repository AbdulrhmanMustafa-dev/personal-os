"""
Health check schemas.
"""

from pydantic import BaseModel
from typing import Any, Optional
from datetime import datetime


class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: datetime
    database: str
    checks: dict[str, Any] = {}
