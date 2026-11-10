# ATREES Configuration Guide

**Version:** 1.0  
**Date:** 2026-11-07

---

## Configuration Philosophy

- **Local-first**: All config in `.env` file (gitignored)
- **Type-safe**: Pydantic Settings with validation
- **Environment-specific**: `.env`, `.env.local`, `.env.production`
- **Secrets management**: Encryption key protects sensitive values in DB
- **Documentation**: Every setting documented in `.env.example`

---

## Configuration Layers (Priority Order)

1. **Defaults** (code) → Lowest priority
2. **`.env`** (committed template: `.env.example`)
3. **`.env.local`** (local overrides, gitignored)
4. **Environment variables** → Highest priority

---

## Core Settings

### Application
```python
# src/atrees/config.py
class AppSettings(BaseSettings):
    # Application
    APP_NAME: str = "ATREES"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"  # DEBUG, INFO, WARNING, ERROR
    LOG_FORMAT: str = "json"  # json, console
    
    # Server
    HOST: str = "127.0.0.1"  # Local-first default
    PORT: int = 8000
    WORKERS: int = 1
    
    # Security
    ENCRYPTION_KEY: SecretStr  # Required, 32 bytes base64
    API_KEY: SecretStr         # Required, 32 bytes base64
    SESSION_COOKIE_SECURE: bool = False  # True in production with HTTPS
    
    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/atrees.db"
    DB_ECHO: bool = False
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    
    # Timezone
    TIMEZONE: str = "Africa/Cairo"
    
    # Paths
    DATA_DIR: Path = Path("./data")
    BACKUP_DIR: Path = Path("./backups")
    LOGS_DIR: Path = Path("./logs")
```

### Telegram MTProto (User Account)
```python
class TelegramMTProtoSettings(BaseSettings):
    ENABLED: bool = True
    API_ID: int
    API_HASH: SecretStr
    SESSION_STRING: SecretStr | None = None  # Encrypted in DB after first login
    SESSION_FILE: str = "telegram_session"   # Fallback file session
    
    # Monitoring
    TARGET_KEYWORDS: list[str] = ["مستقل", "خمسات", "نفذلي", "Nafezly"]
    EXCLUDED_KEYWORDS: list[str] = ["تصميم", "تدريب", "دعم"]
    TARGET_CONTACT_NAME: str = "3bdo"
    
    # Test mode
    TEST_CONTACTS: list[str] = []
    TEST_SAVED_MESSAGES: bool = False
    
    # Sync
    SYNC_INTERVAL_MINUTES: int = 30
    MAX_MESSAGES_PER_SYNC: int = 1000
    FETCH_MEDIA: bool = False
    MEDIA_MAX_SIZE_MB: int = 50
```

### Telegram Bot API
```python
class TelegramBotSettings(BaseSettings):
    ENABLED: bool = True
    BOT_TOKEN: SecretStr
    WEBHOOK_URL: str | None = None  # Set for production webhook
    WEBHOOK_SECRET: SecretStr | None = None
    WEBHOOK_PATH: str = "/webhook/telegram"
    
    # Commands
    COMMAND_PREFIX: str = "/"
    ADMIN_USER_IDS: list[int] = []  # Telegram user IDs with admin access
    
    # Notifications
    NOTIFY_ON_STARTUP: bool = True
    NOTIFY_ON_ERROR: bool = True
    DAILY_BRIEFING_TIME: str = "08:00"  # Local time
    QUIET_HOURS_START: str = "22:00"
    QUIET_HOURS_END: str = "08:00"
```

### Google Services
```python
class GoogleSettings(BaseSettings):
    ENABLED: bool = False
    CLIENT_ID: SecretStr
    CLIENT_SECRET: SecretStr
    REDIRECT_URI: str = "http://127.0.0.1:8000/auth/google/callback"
    
    # Scopes (minimal required)
    CALENDAR_SCOPES: list[str] = [
        "https://www.googleapis.com/auth/calendar.readonly",
        "https://www.googleapis.com/auth/calendar.events"
    ]
    TASKS_SCOPES: list[str] = [
        "https://www.googleapis.com/auth/tasks"
    ]
    GMAIL_SCOPES: list[str] = [
        "https://www.googleapis.com/auth/gmail.readonly"
    ]
    
    # Sync
    CALENDAR_SYNC_INTERVAL_MINUTES: int = 15
    TASKS_SYNC_INTERVAL_MINUTES: int = 15
    GMAIL_SYNC_INTERVAL_MINUTES: int = 30
    GMAIL_MAX_RESULTS: int = 100
    GMAIL_QUERY: str = "is:unread OR newer_than:7d"
```

### AI Providers
```python
class AISettings(BaseSettings):
    # Provider preference order (first available used)
    PROVIDER_PREFERENCE: list[str] = ["local", "groq", "cerebras", "openrouter", "gemini"]
    
    # Local (Ollama)
    LOCAL_ENABLED: bool = True
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    LOCAL_MODEL: str = "llama3.1:8b"
    LOCAL_EMBEDDING_MODEL: str = "nomic-embed-text"
    
    # Cloud (optional)
    CLOUD_ENABLED: bool = False
    GROQ_API_KEY: SecretStr | None = None
    GROQ_MODELS: list[str] = []
    CEREBRAS_API_KEY: SecretStr | None = None
    CEREBRAS_MODELS: list[str] = []
    OPENROUTER_API_KEY: SecretStr | None = None
    OPENROUTER_MODELS: list[str] = []
    GEMINI_API_KEY: SecretStr | None = None
    GEMINI_MODELS: list[str] = []
    
    # Behavior
    REQUEST_TIMEOUT: int = 60
    MAX_RETRIES: int = 3
    TEMPERATURE: float = 0.3
    MAX_TOKENS: int = 4096
    
    # Privacy
    REDACT_PII: bool = True
    MINIMIZE_CONTEXT: bool = True
    MAX_CONTEXT_CHARS: int = 8000
```

### Notifications
```python
class NotificationSettings(BaseSettings):
    # Channels
    TELEGRAM_ENABLED: bool = True
    NTFY_ENABLED: bool = False
    NTFY_TOPIC: str | None = None
    NTFY_SERVER: str = "https://ntfy.sh"
    DASHBOARD_ENABLED: bool = True
    
    # Priority thresholds
    IMMEDIATE_PRIORITIES: list[str] = ["critical", "high"]
    DAILY_DIGEST_TIME: str = "08:00"
    WEEKLY_DIGEST_DAY: int = 0  # Monday
    WEEKLY_DIGEST_TIME: str = "09:00"
    
    # Deduplication
    DEDUP_WINDOW_MINUTES: int = 60
    MAX_NOTIFICATIONS_PER_HOUR: int = 20
```

### Tasks & Calendar
```python
class TaskCalendarSettings(BaseSettings):
    # Task defaults
    DEFAULT_PRIORITY: int = 3
    DEFAULT_ESTIMATED_MINUTES: int = 30
    DAY_PLAN_METHOD: str = "1-3-5"  # "1-3-5" or "custom"
    
    # 1-3-5 slots
    BIG_TASK_COUNT: int = 1
    MEDIUM_TASK_COUNT: int = 3
    SMALL_TASK_COUNT: int = 5
    
    # Calendar
    DEFAULT_REMINDER_MINUTES: int = 15
    WORK_HOURS_START: str = "09:00"
    WORK_HOURS_END: str = "18:00"
    WEEKEND_DAYS: list[int] = [4, 5]  # Fri, Sat (0=Mon)
    
    # Auto-scheduling
    AUTO_SCHEDULE_ENABLED: bool = False
    MAX_DAILY_HOURS: float = 8.0
    BUFFER_MINUTES: int = 15
```

### Sync & Automation
```python
class SyncSettings(BaseSettings):
    # Global sync
    AUTO_SYNC_ENABLED: bool = True
    SYNC_INTERVAL_MINUTES: int = 30
    MAX_CONCURRENT_SYNCS: int = 3
    
    # Retry
    MAX_RETRIES: int = 3
    BACKOFF_FACTOR: float = 2.0
    MAX_BACKOFF_SECONDS: int = 300
    
    # Cleanup
    RAW_ITEM_RETENTION_DAYS: int = 365
    NOTIFICATION_RETENTION_DAYS: int = 90
    AUDIT_LOG_RETENTION_DAYS: int = 365
    COMPLETED_TASK_RETENTION_DAYS: int = 1095  # 3 years
```

### Privacy & Data
```python
class PrivacySettings(BaseSettings):
    ENCRYPT_BACKUPS: bool = True
    BACKUP_PASSPHRASE: SecretStr | None = None  # For age encryption
    RETENTION_DAYS: int = 365
    AUTO_DELETE_ENABLED: bool = False
    EXPORT_FORMAT: str = "json"  # json, csv
    ANONYMIZE_EXPORTS: bool = False
```

### Frontend
```python
class FrontendSettings(BaseSettings):
    ENABLED: bool = True
    BUILD_PATH: Path = Path("../frontend/dist")
    DEV_SERVER_URL: str = "http://127.0.0.1:5173"
    CORS_ORIGINS: list[str] = ["http://127.0.0.1:5173", "http://127.0.0.1:8000"]
    
    # i18n
    DEFAULT_LANGUAGE: str = "ar"
    SUPPORTED_LANGUAGES: list[str] = ["ar", "en"]
    RTL_LANGUAGES: list[str] = ["ar"]
```

---

## Complete `.env.example`

```bash
# =============================================================================
# ATREES Configuration - Copy to .env and fill in your values
# =============================================================================

# -----------------------------------------------------------------------------
# GENERAL (Required)
# -----------------------------------------------------------------------------
# Generate with: python -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"
ENCRYPTION_KEY=
API_KEY=

# Application
DEBUG=false
LOG_LEVEL=INFO
LOG_FORMAT=json
HOST=127.0.0.1
PORT=8000
TIMEZONE=Africa/Cairo

# Database
DATABASE_URL=sqlite+aiosqlite:///./data/atrees.db

# -----------------------------------------------------------------------------
# TELEGRAM MTProto (User Account) - Required for channel monitoring
# -----------------------------------------------------------------------------
# Get from https://my.telegram.org
TELEGRAM_API_ID=
TELEGRAM_API_HASH=

# Session string (generate once with scripts/gen_telegram_session.py)
# Or leave empty to use file session
TELEGRAM_SESSION_STRING=

# Monitoring keywords (Arabic freelance platforms)
TELEGRAM_TARGET_KEYWORDS=مستقل,خمسات,نفذلي,Nafezly
TELEGRAM_EXCLUDED_KEYWORDS=تصميم,تدريب,دعم
TELEGRAM_TARGET_CONTACT_NAME=3bdo

# Test mode (optional)
TELEGRAM_TEST_CONTACTS=abdo
TELEGRAM_TEST_SAVED_MESSAGES=false

# -----------------------------------------------------------------------------
# TELEGRAM BOT API - Required for notifications & commands
# -----------------------------------------------------------------------------
# Get from @BotFather
TELEGRAM_BOT_TOKEN=

# Webhook (production only)
TELEGRAM_WEBHOOK_URL=
TELEGRAM_WEBHOOK_SECRET=

# Admin users (Telegram user IDs)
TELEGRAM_ADMIN_USER_IDS=

# Notification settings
TELEGRAM_NOTIFY_ON_STARTUP=true
TELEGRAM_NOTIFY_ON_ERROR=true
TELEGRAM_DAILY_BRIEFING_TIME=08:00
TELEGRAM_QUIET_HOURS_START=22:00
TELEGRAM_QUIET_HOURS_END=08:00

# -----------------------------------------------------------------------------
# GOOGLE SERVICES (Optional)
# -----------------------------------------------------------------------------
# Get from Google Cloud Console
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://127.0.0.1:8000/auth/google/callback

GOOGLE_CALENDAR_ENABLED=false
GOOGLE_TASKS_ENABLED=false
GOOGLE_GMAIL_ENABLED=false

# -----------------------------------------------------------------------------
# AI PROVIDERS (At least one required)
# -----------------------------------------------------------------------------
# Local (Ollama) - Preferred for privacy
OLLAMA_BASE_URL=http://127.0.0.1:11434
LOCAL_MODEL=llama3.1:8b
LOCAL_EMBEDDING_MODEL=nomic-embed-text

# Cloud (optional - enable with CLOUD_ENABLED=true)
CLOUD_ENABLED=false
GROQ_API_KEY=
CEREBRAS_API_KEY=
OPENROUTER_API_KEY=
GEMINI_API_KEY=

# AI behavior
AI_REQUEST_TIMEOUT=60
AI_MAX_RETRIES=3
AI_TEMPERATURE=0.3
AI_MAX_TOKENS=4096
AI_REDACT_PII=true
AI_MINIMIZE_CONTEXT=true
AI_MAX_CONTEXT_CHARS=8000

# -----------------------------------------------------------------------------
# NOTIFICATIONS
# -----------------------------------------------------------------------------
NTFY_ENABLED=false
NTFY_TOPIC=
NTFY_SERVER=https://ntfy.sh

# -----------------------------------------------------------------------------
# TASKS & CALENDAR
# -----------------------------------------------------------------------------
TASK_DEFAULT_PRIORITY=3
TASK_DEFAULT_ESTIMATED_MINUTES=30
TASK_DAY_PLAN_METHOD=1-3-5
CALENDAR_DEFAULT_REMINDER_MINUTES=15
CALENDAR_WORK_HOURS_START=09:00
CALENDAR_WORK_HOURS_END=18:00

# -----------------------------------------------------------------------------
# SYNC & AUTOMATION
# -----------------------------------------------------------------------------
AUTO_SYNC_ENABLED=true
SYNC_INTERVAL_MINUTES=30
MAX_CONCURRENT_SYNCS=3

# -----------------------------------------------------------------------------
# PRIVACY
# -----------------------------------------------------------------------------
ENCRYPT_BACKUPS=true
BACKUP_PASSPHRASE=
RETENTION_DAYS=365

# -----------------------------------------------------------------------------
# FRONTEND
# -----------------------------------------------------------------------------
FRONTEND_ENABLED=true
FRONTEND_DEFAULT_LANGUAGE=ar
```

---

## Generating Secrets

```bash
# Encryption key (32 bytes base64)
python -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"

# API key (32 bytes base64)
python -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"

# Or use the helper script
python scripts/generate_secrets.py
```

---

## Configuration Validation

All settings validated at startup:
- Required fields present
- Types correct
- Values in allowed ranges
- Secrets not using defaults
- Paths exist or can be created

```python
# In config.py
@model_validator(mode="after")
def validate_secrets(self) -> "Settings":
    if self.ENCRYPTION_KEY.get_secret_value() == "changeme":
        raise ValueError("ENCRYPTION_KEY must be changed from default")
    if self.API_KEY.get_secret_value() == "changeme":
        raise ValueError("API_KEY must be changed from default")
    return self
```

---

## Runtime Configuration Updates

Some settings can be updated via API (stored in `user_preferences` table):
- Notification preferences
- Task/Calendar defaults
- AI provider preferences
- Sync intervals
- UI theme/language

Changes require authentication and are audited.