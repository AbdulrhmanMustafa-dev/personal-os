"""
Connector modules for ATREES.

Each connector implements a standard interface for data synchronization.
"""

from atrees.connectors.base import (
    BaseConnector,
    ConnectorConfig,
    SyncResult,
    ConnectorStatus,
    SyncStatus,
)
from atrees.connectors.telegram_mtproto import TelegramMTProtoConnector
from atrees.connectors.telegram_bot import TelegramBotConnector

CONNECTOR_REGISTRY: dict[str, type[BaseConnector]] = {
    "telegram_mtproto": TelegramMTProtoConnector,
    "telegram_bot": TelegramBotConnector,
}

# Future connectors (to be implemented in later phases)
# "google_calendar": GoogleCalendarConnector,
# "google_tasks": GoogleTasksConnector,
# "gmail": GmailConnector,
# "whatsapp_import": WhatsAppImporter,
# "chatgpt_import": ChatGPTImporter,
# "gemini_import": GeminiImporter,
# "claude_import": ClaudeImporter,


def get_connector(connector_type: str) -> type[BaseConnector]:
    """Get connector class by type."""
    if connector_type not in CONNECTOR_REGISTRY:
        raise ValueError(f"Unknown connector type: {connector_type}")
    return CONNECTOR_REGISTRY[connector_type]


def list_connectors() -> list[dict]:
    """List all available connectors with metadata."""
    return [
        {
            "type": k,
            "display_name": v.DISPLAY_NAME,
            "description": v.DESCRIPTION,
            "supports_incremental": v.SUPPORTS_INCREMENTAL,
            "supports_realtime": v.SUPPORTS_REALTIME,
            "requires_user_auth": v.REQUIRES_USER_AUTH,
        }
        for k, v in CONNECTOR_REGISTRY.items()
    ]


__all__ = [
    "BaseConnector",
    "ConnectorConfig",
    "SyncResult",
    "ConnectorStatus",
    "SyncStatus",
    "TelegramMTProtoConnector",
    "TelegramBotConnector",
    "get_connector",
    "list_connectors",
    "CONNECTOR_REGISTRY",
]