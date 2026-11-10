"""
Connectors API routes for ATREES.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from atrees.database import get_db_session
from atrees.connectors import get_connector, CONNECTOR_REGISTRY
from atrees.connectors.base import ConnectorConfig
from atrees.models.source import Source
from atrees.core.exceptions import NotFoundError

router = APIRouter()


class ConnectorInfo(BaseModel):
    type: str
    display_name: str
    description: str
    supports_incremental: bool
    supports_realtime: bool
    requires_user_auth: bool


@router.get("/", response_model=list[ConnectorInfo])
async def list_connectors() -> list[dict]:
    """List all available connector types with metadata."""
    return [
        ConnectorInfo(
            type=k,
            display_name=v.DISPLAY_NAME,
            description=v.DESCRIPTION,
            supports_incremental=v.SUPPORTS_INCREMENTAL,
            supports_realtime=v.SUPPORTS_REALTIME,
            requires_user_auth=v.REQUIRES_USER_AUTH,
        )
        for k, v in CONNECTOR_REGISTRY.items()
    ]


@router.get("/{connector_type}")
async def get_connector_info(connector_type: str) -> dict:
    """Get detailed info for a connector type."""
    try:
        connector_class = get_connector(connector_type)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Unknown connector type: {connector_type}")

    return {
        "type": connector_type,
        "display_name": connector_class.DISPLAY_NAME,
        "description": connector_class.DESCRIPTION,
        "supports_incremental": connector_class.SUPPORTS_INCREMENTAL,
        "supports_realtime": connector_class.SUPPORTS_REALTIME,
        "requires_user_auth": connector_class.REQUIRES_USER_AUTH,
    }


@router.post("/{connector_type}/test")
async def test_connector_config(
    connector_type: str,
    config: dict,
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Test a connector configuration without saving."""
    try:
        connector_class = get_connector(connector_type)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Unknown connector type: {connector_type}")

    # Create temporary connector instance
    connector_config = ConnectorConfig(
        source_id=0,
        name="test",
        config=config,
    )
    connector = connector_class(connector_config, db)

    try:
        async with connector:
            success, message = await connector.test_connection()
        return {"success": success, "message": message}
    except Exception as e:
        return {"success": False, "message": str(e)}