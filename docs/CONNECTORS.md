# ATREES Connectors Architecture

**Version:** 1.0  
**Date:** 2026-11-07

---

## Connector Interface

All connectors implement a common interface for consistency.

```python
# src/atrees/connectors/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any
from datetime import datetime

class ConnectorStatus(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    SYNCING = "syncing"
    ERROR = "error"

class SyncStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"

@dataclass
class ConnectorConfig:
    """Base configuration for all connectors."""
    source_id: int
    name: str
    enabled: bool = True
    config: dict = None  # Encrypted credentials
    sync_interval_minutes: int = 30

@dataclass
class SyncResult:
    """Result of a sync operation."""
    status: SyncStatus
    items_processed: int = 0
    items_created: int = 0
    items_updated: int = 0
    items_failed: int = 0
    errors: list[str] = None
    cursor: dict = None  # For incremental sync
    started_at: datetime = None
    completed_at: datetime = None

class BaseConnector(ABC):
    """Abstract base class for all data connectors."""
    
    # Unique identifier for this connector type
    CONNECTOR_TYPE: str = "base"
    DISPLAY_NAME: str = "Base Connector"
    DESCRIPTION: str = ""
    
    # Capabilities
    SUPPORTS_INCREMENTAL: bool = True
    SUPPORTS_REALTIME: bool = False
    REQUIRES_USER_AUTH: bool = True
    
    def __init__(self, config: ConnectorConfig, db_session):
        self.config = config
        self.db = db_session
        self.status = ConnectorStatus.DISCONNECTED
        self._client = None
    
    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to the source."""
        pass
    
    @abstractmethod
    async def disconnect(self) -> bool:
        """Close connection gracefully."""
        pass
    
    @abstractmethod
    async def test_connection(self) -> tuple[bool, str]:
        """Test if connection works. Returns (success, message)."""
        pass
    
    @abstractmethod
    async def sync(self, incremental: bool = True) -> SyncResult:
        """Perform synchronization."""
        pass
    
    @abstractmethod
    async def get_sync_status(self) -> dict:
        """Get current sync status and cursor info."""
        pass
    
    async def __aenter__(self):
        await self.connect()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.disconnect()
```

---

## Connector Registry

```python
# src/atrees/connectors/__init__.py
from .base import BaseConnector, ConnectorConfig, SyncResult, ConnectorStatus, SyncStatus
from .telegram_mtproto import TelegramMTProtoConnector
from .telegram_bot import TelegramBotConnector
from .google_calendar import GoogleCalendarConnector
from .google_tasks import GoogleTasksConnector
from .gmail import GmailConnector
from .whatsapp import WhatsAppImporter
from .chatgpt import ChatGPTImporter
from .gemini import GeminiImporter
from .claude import ClaudeImporter

CONNECTOR_REGISTRY: dict[str, type[BaseConnector]] = {
    "telegram_mtproto": TelegramMTProtoConnector,
    "telegram_bot": TelegramBotConnector,
    "google_calendar": GoogleCalendarConnector,
    "google_tasks": GoogleTasksConnector,
    "gmail": GmailConnector,
    "whatsapp_import": WhatsAppImporter,
    "chatgpt_import": ChatGPTImporter,
    "gemini_import": GeminiImporter,
    "claude_import": ClaudeImporter,
}

def get_connector(connector_type: str) -> type[BaseConnector]:
    if connector_type not in CONNECTOR_REGISTRY:
        raise ValueError(f"Unknown connector type: {connector_type}")
    return CONNECTOR_REGISTRY[connector_type]

def list_connectors() -> list[dict]:
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
```

---

## Phase 1 Connectors

### 1. Telegram MTProto (Telethon)

**Purpose**: Monitor channels/groups for job postings using user account.

**File**: `src/atrees/connectors/telegram_mtproto/connector.py`

**Configuration**:
```python
{
    "api_id": int,
    "api_hash": "encrypted",
    "session_string": "encrypted",
    "target_keywords": ["مستقل", "خمسات", "نفذلي", "Nafezly"],
    "excluded_keywords": ["تصميم", "تدريب", "دعم"],
    "target_contact_name": "3bdo",
    "test_contacts": [],
    "test_saved_messages": false,
    "fetch_media": false
}
```

**Sync Logic**:
1. Connect with Telethon
2. Iterate dialogs, filter by keywords
3. For each monitored chat, fetch new messages since last cursor
4. Store raw messages in `raw_items`
5. Update sync cursor per chat
6. Trigger job analysis (existing logic)

**Cursor Format**:
```json
{
    "chat_id": 123456789,
    "last_message_id": 98765,
    "last_message_date": "2026-11-07T10:30:00Z"
}
```

### 2. Telegram Bot API

**Purpose**: Send notifications, receive commands.

**File**: `src/atrees/connectors/telegram_bot/connector.py`

**Configuration**:
```python
{
    "bot_token": "encrypted",
    "webhook_url": "https://...",
    "webhook_secret": "encrypted",
    "admin_user_ids": [123456789],
    "allowed_user_ids": [123456789]  // Optional restriction
}
```

**Commands**:
| Command | Description | Approval |
|---------|-------------|----------|
| `/start` | Welcome, show help | No |
| `/today` | Show today's tasks & events | No |
| `/tasks` | List tasks with filters | No |
| `/add_task` | Create new task | Yes (if auto_approve=false) |
| `/calendar` | Show upcoming events | No |
| `/sync` | Trigger manual sync | No |
| `/status` | Show connector status | No |
| `/ask` | Ask ATREES a question | No |
| `/approve` | Approve pending action | Yes |
| `/help` | Show all commands | No |

**Webhook Events**:
- `message` - User commands
- `callback_query` - Inline button callbacks

---

## Phase 2 Connectors

### 3. WhatsApp Importer

**Purpose**: Import official WhatsApp chat exports.

**File**: `src/atrees/connectors/whatsapp/importer.py`

**Input**: ZIP file from WhatsApp export (chat.txt + media folder)

**Parsing**:
- `chat.txt` format varies by platform (iOS/Android)
- Extract: sender, timestamp, message text, media references
- Handle system messages (group changes, etc.)

**Configuration**:
```python
{
    "export_path": "/path/to/export.zip",
    "chat_name_filter": [],  // Optional filter
    "date_from": "2024-01-01",
    "date_to": "2026-11-07",
    "include_media": false
}
```

**Sync**: One-time import, then incremental re-imports with dedup.

### 4. AI Conversation Importers

#### ChatGPT
- Input: `conversations.json` from data export
- Extract: conversations, messages, metadata
- Parse: Custom GPTs, plugins, code interpreter outputs

#### Gemini (Google Takeout)
- Input: Multiple JSON files in Takeout archive
- Extract: Conversations, prompts, responses

#### Claude
- Input: `conversations.json` from Claude export
- Extract: Conversations, projects, artifacts

**Common Configuration**:
```python
{
    "export_path": "/path/to/export.zip",
    "extract_facts": true,
    "extract_tasks": true,
    "extract_skills": true,
    "date_from": "2024-01-01"
}
```

---

## Phase 3 Connectors

### 5. Google Calendar

**Purpose**: Two-way calendar sync.

**OAuth Scopes**:
- `https://www.googleapis.com/auth/calendar.readonly`
- `https://www.googleapis.com/auth/calendar.events`

**Sync Logic**:
1. Fetch calendars list
2. For each selected calendar, fetch events since last sync token
3. Upsert to `events` table
4. Store next sync token
5. Push local events created in ATREES (if approved)

**Conflict Handling**:
- Local changes pending approval → don't overwrite
- Remote changes → create draft for review
- Deleted remotely → mark local as cancelled

### 6. Google Tasks

**Purpose**: Two-way tasks sync.

**OAuth Scopes**:
- `https://www.googleapis.com/auth/tasks`

**Mapping**:
| Google Tasks | ATREES Tasks |
|--------------|--------------|
| Task list | Project (or category) |
| Title | Title |
| Notes | Description |
| Due date | Due date |
| Status | Status (needs_review ↔ completed) |
| Parent task | Subtask (future) |

### 7. Gmail (Read-Only)

**Purpose**: Extract important emails, tasks, events.

**OAuth Scopes**:
- `https://www.googleapis.com/auth/gmail.readonly`

**Sync Logic**:
1. Search with query (configurable)
2. Fetch message metadata + body
3. Classify: important, task-related, event-related, newsletter, spam
4. Extract tasks, dates, commitments
5. Store raw in `raw_items`, normalized in `messages`

**Classification Categories**:
- `important` - From known contacts, urgent keywords
- `task` - Contains action items, deadlines
- `event` - Calendar invites, appointments
- `newsletter` - Subscriptions, digests
- `spam` - Promotional, automated

---

## Phase 4 Connectors

### 8. Social Media (Official APIs Only)

| Platform | API | Scope | Limitations |
|----------|-----|-------|-------------|
| Instagram | Graph API | Business/Creator accounts only | No DM access for personal |
| Facebook | Graph API | Pages/Groups you manage | No personal profile feed |
| X (Twitter) | API v2 | OAuth 2.0 | Rate limited, paid tiers |
| TikTok | TikTok API | Creator/Business | Very limited |

**Approach**: 
- Only implement what APIs actually allow
- Document limitations clearly
- Offer manual import as fallback

---

## Connector Development Guide

### Adding a New Connector

1. **Create directory**: `src/atrees/connectors/<name>/`
2. **Implement connector**:
```python
# connector.py
from atrees.connectors.base import BaseConnector, ConnectorConfig, SyncResult

class MyConnector(BaseConnector):
    CONNECTOR_TYPE = "my_connector"
    DISPLAY_NAME = "My Connector"
    DESCRIPTION = "Description"
    
    async def connect(self) -> bool:
        # Setup client
        self.status = ConnectorStatus.CONNECTED
        return True
    
    async def disconnect(self) -> bool:
        # Cleanup
        self.status = ConnectorStatus.DISCONNECTED
        return True
    
    async def test_connection(self) -> tuple[bool, str]:
        try:
            # Test API call
            return True, "Connected"
        except Exception as e:
            return False, str(e)
    
    async def sync(self, incremental: bool = True) -> SyncResult:
        # Implement sync logic
        return SyncResult(status=SyncStatus.SUCCESS, items_processed=0)
    
    async def get_sync_status(self) -> dict:
        return {"status": self.status.value, "cursor": {}}
```

3. **Register** in `src/atrees/connectors/__init__.py`
4. **Add config model** in `src/atrees/config.py`
5. **Add API routes** in `src/atrees/api/routes/connectors.py`
6. **Add frontend components** for configuration
7. **Write tests**

### Best Practices

1. **Idempotency**: Same sync twice = no duplicates
2. **Cursors**: Always store and use sync cursors
3. **Rate Limits**: Respect API limits, implement backoff
4. **Errors**: Distinguish retryable vs fatal errors
5. **Logging**: Structured logs with correlation IDs
6. **Testing**: Mock external APIs, test edge cases
7. **Security**: Encrypt credentials, minimal scopes

---

## Sync Orchestration

```python
# src/atrees/services/sync_service.py
class SyncService:
    def __init__(self, db_session, connector_factory):
        self.db = db_session
        self.factory = connector_factory
    
    async def sync_source(self, source_id: int, incremental: bool = True) -> SyncResult:
        source = await self.get_source(source_id)
        connector = self.factory.create(source)
        
        async with connector:
            # Update source status
            source.status = "syncing"
            await self.db.commit()
            
            try:
                result = await connector.sync(incremental)
                
                # Update sync state
                await self.update_sync_state(source_id, result)
                
                # Update source status
                source.last_sync_at = datetime.utcnow()
                source.last_sync_status = result.status.value
                if result.errors:
                    source.last_sync_error = "; ".join(result.errors[:3])
                source.status = "connected"
                
                await self.db.commit()
                return result
                
            except Exception as e:
                source.status = "error"
                source.last_sync_error = str(e)
                await self.db.commit()
                raise
    
    async def sync_all(self, incremental: bool = True) -> dict[str, SyncResult]:
        sources = await self.get_enabled_sources()
        results = {}
        
        # Run with concurrency limit
        semaphore = asyncio.Semaphore(3)
        
        async def sync_one(source):
            async with semaphore:
                results[source.name] = await self.sync_source(source.id, incremental)
        
        await asyncio.gather(*[sync_one(s) for s in sources])
        return results
```

---

## Monitoring & Alerting

### Sync Health Metrics
- Last successful sync time
- Items processed per sync
- Error rate
- Latency
- Cursor lag (how far behind)

### Alerts
- Sync failed 3x in a row
- No sync for > 2x interval
- Error rate > 10%
- Rate limit hit

### Dashboard
- Connector status cards
- Sync history timeline
- Error details
- Manual sync trigger