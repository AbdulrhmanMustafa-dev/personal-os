"""
Configuration management for ATREES using Pydantic Settings.

All configuration is loaded from environment variables with validation.
Sensitive values use SecretStr for protection.
"""

from pathlib import Path
from typing import Any
from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class TelegramMTProtoSettings(BaseSettings):
    """Telegram MTProto (Telethon) configuration for user account monitoring."""
    model_config = SettingsConfigDict(env_prefix="TELEGRAM_", extra="ignore")

    ENABLED: bool = True
    API_ID: int | None = None
    API_HASH: SecretStr | None = None
    SESSION_STRING: SecretStr | None = None

    # Monitoring settings
    TARGET_KEYWORDS: list[str] = Field(
        default=["مستقل", "خمسات", "نفذلي", "Nafezly"],
        description="Keywords to match channel/group names",
    )
    EXCLUDED_KEYWORDS: list[str] = Field(
        default=["تصميم", "تدريب", "دعم"],
        description="Keywords to exclude from monitoring",
    )
    TARGET_CONTACT_NAME: str = "3bdo"

    # Test mode
    TEST_CONTACTS: list[str] = Field(default_factory=list)
    TEST_SAVED_MESSAGES: bool = False

    # Sync settings
    SYNC_INTERVAL_MINUTES: int = 30
    MAX_MESSAGES_PER_SYNC: int = 1000
    FETCH_MEDIA: bool = False
    MEDIA_MAX_SIZE_MB: int = 50

    @field_validator("TARGET_KEYWORDS", "EXCLUDED_KEYWORDS", "TEST_CONTACTS", mode="before")
    @classmethod
    def parse_list(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        return v


class TelegramBotSettings(BaseSettings):
    """Telegram Bot API configuration for notifications and commands."""
    model_config = SettingsConfigDict(env_prefix="TELEGRAM_BOT_", extra="ignore")

    ENABLED: bool = True
    BOT_TOKEN: SecretStr | None = None
    WEBHOOK_URL: str | None = None
    WEBHOOK_SECRET: SecretStr | None = None
    WEBHOOK_PATH: str = "/webhook/telegram"

    ADMIN_USER_IDS: list[int] = Field(default_factory=list)
    ALLOWED_USER_IDS: list[int] = Field(default_factory=list)

    # Notification settings
    NOTIFY_ON_STARTUP: bool = True
    NOTIFY_ON_ERROR: bool = True
    DAILY_BRIEFING_TIME: str = "08:00"
    QUIET_HOURS_START: str = "22:00"
    QUIET_HOURS_END: str = "08:00"

    @field_validator("ADMIN_USER_IDS", "ALLOWED_USER_IDS", mode="before")
    @classmethod
    def parse_int_list(cls, v: str | list[int]) -> list[int]:
        if isinstance(v, str):
            return [int(x.strip()) for x in v.split(",") if x.strip()]
        return v


class GoogleSettings(BaseSettings):
    """Google OAuth and API configuration."""
    model_config = SettingsConfigDict(env_prefix="GOOGLE_", extra="ignore")

    ENABLED: bool = False
    CLIENT_ID: SecretStr | None = None
    CLIENT_SECRET: SecretStr | None = None
    REDIRECT_URI: str = "http://127.0.0.1:8000/auth/google/callback"

    # Scopes (minimal required)
    CALENDAR_SCOPES: list[str] = Field(
        default=[
            "https://www.googleapis.com/auth/calendar.readonly",
            "https://www.googleapis.com/auth/calendar.events",
        ]
    )
    TASKS_SCOPES: list[str] = Field(
        default=["https://www.googleapis.com/auth/tasks"]
    )
    GMAIL_SCOPES: list[str] = Field(
        default=["https://www.googleapis.com/auth/gmail.readonly"]
    )

    # Feature flags
    CALENDAR_ENABLED: bool = False
    TASKS_ENABLED: bool = False
    GMAIL_ENABLED: bool = False

    # Sync intervals
    CALENDAR_SYNC_INTERVAL_MINUTES: int = 15
    TASKS_SYNC_INTERVAL_MINUTES: int = 15
    GMAIL_SYNC_INTERVAL_MINUTES: int = 30
    GMAIL_MAX_RESULTS: int = 100
    GMAIL_QUERY: str = "is:unread OR newer_than:7d"


class AISettings(BaseSettings):
    """AI Provider configuration."""
    model_config = SettingsConfigDict(env_prefix="AI_", extra="ignore")

    # Provider preference order
    PROVIDER_PREFERENCE: list[str] = Field(
        default=["local", "groq", "cerebras", "openrouter", "gemini"]
    )

    # Local (Ollama)
    LOCAL_ENABLED: bool = True
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    LOCAL_MODEL: str = "llama3.1:8b"
    LOCAL_EMBEDDING_MODEL: str = "nomic-embed-text"

    # Cloud providers (optional)
    CLOUD_ENABLED: bool = False
    GROQ_API_KEY: SecretStr | None = None
    GROQ_MODELS: list[str] = Field(default_factory=list)
    CEREBRAS_API_KEY: SecretStr | None = None
    CEREBRAS_MODELS: list[str] = Field(default_factory=list)
    OPENROUTER_API_KEY: SecretStr | None = None
    OPENROUTER_MODELS: list[str] = Field(default_factory=list)
    GEMINI_API_KEY: SecretStr | None = None
    GEMINI_MODELS: list[str] = Field(default_factory=list)

    # Behavior
    REQUEST_TIMEOUT: int = 60
    MAX_RETRIES: int = 3
    TEMPERATURE: float = 0.3
    MAX_TOKENS: int = 4096

    # Privacy
    REDACT_PII: bool = True
    MINIMIZE_CONTEXT: bool = True
    MAX_CONTEXT_CHARS: int = 8000

    @field_validator("PROVIDER_PREFERENCE", "GROQ_MODELS", "CEREBRAS_MODELS", "OPENROUTER_MODELS", "GEMINI_MODELS", mode="before")
    @classmethod
    def parse_list(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        return v


class NotificationSettings(BaseSettings):
    """Notification channels and behavior."""
    model_config = SettingsConfigDict(env_prefix="NOTIFICATION_", extra="ignore")

    TELEGRAM_ENABLED: bool = True
    NTFY_ENABLED: bool = False
    NTFY_TOPIC: str | None = None
    NTFY_SERVER: str = "https://ntfy.sh"
    DASHBOARD_ENABLED: bool = True

    IMMEDIATE_PRIORITIES: list[str] = Field(default=["critical", "high"])
    DAILY_DIGEST_TIME: str = "08:00"
    WEEKLY_DIGEST_DAY: int = 0  # Monday
    WEEKLY_DIGEST_TIME: str = "09:00"

    DEDUP_WINDOW_MINUTES: int = 60
    MAX_NOTIFICATIONS_PER_HOUR: int = 20


class TaskCalendarSettings(BaseSettings):
    """Task and Calendar defaults."""
    model_config = SettingsConfigDict(env_prefix="TASK_", extra="ignore")

    DEFAULT_PRIORITY: int = Field(default=3, ge=1, le=5)
    DEFAULT_ESTIMATED_MINUTES: int = 30
    DAY_PLAN_METHOD: str = "1-3-5"

    BIG_TASK_COUNT: int = 1
    MEDIUM_TASK_COUNT: int = 3
    SMALL_TASK_COUNT: int = 5

    # Calendar
    CALENDAR_DEFAULT_REMINDER_MINUTES: int = 15
    WORK_HOURS_START: str = "09:00"
    WORK_HOURS_END: str = "18:00"
    WEEKEND_DAYS: list[int] = Field(default=[4, 5])  # Fri, Sat

    AUTO_SCHEDULE_ENABLED: bool = False
    MAX_DAILY_HOURS: float = 8.0
    BUFFER_MINUTES: int = 15


class SyncSettings(BaseSettings):
    """Global sync and automation settings."""
    model_config = SettingsConfigDict(env_prefix="SYNC_", extra="ignore")

    AUTO_SYNC_ENABLED: bool = True
    SYNC_INTERVAL_MINUTES: int = 30
    MAX_CONCURRENT_SYNCS: int = 3

    MAX_RETRIES: int = 3
    BACKOFF_FACTOR: float = 2.0
    MAX_BACKOFF_SECONDS: int = 300

    RAW_ITEM_RETENTION_DAYS: int = 365
    NOTIFICATION_RETENTION_DAYS: int = 90
    AUDIT_LOG_RETENTION_DAYS: int = 365
    COMPLETED_TASK_RETENTION_DAYS: int = 1095


class PrivacySettings(BaseSettings):
    """Privacy and data retention settings."""
    model_config = SettingsConfigDict(env_prefix="PRIVACY_", extra="ignore")

    ENCRYPT_BACKUPS: bool = True
    BACKUP_PASSPHRASE: SecretStr | None = None
    RETENTION_DAYS: int = 365
    AUTO_DELETE_ENABLED: bool = False
    EXPORT_FORMAT: str = "json"
    ANONYMIZE_EXPORTS: bool = False


class FrontendSettings(BaseSettings):
    """Frontend configuration."""
    model_config = SettingsConfigDict(env_prefix="FRONTEND_", extra="ignore")

    ENABLED: bool = True
    BUILD_PATH: Path = Path("../frontend/dist")
    DEV_SERVER_URL: str = "http://127.0.0.1:5173"
    CORS_ORIGINS: list[str] = Field(
        default=["http://127.0.0.1:5173", "http://127.0.0.1:8000"]
    )

    DEFAULT_LANGUAGE: str = "ar"
    SUPPORTED_LANGUAGES: list[str] = Field(default=["ar", "en"])
    RTL_LANGUAGES: list[str] = Field(default=["ar"])


class Settings(BaseSettings):
    """Main application settings combining all sub-settings."""

    model_config = SettingsConfigDict(
        env_file=[".env", ".env.local"],
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        nested_model_default_partial_update=True,
    )

    # Application
    APP_NAME: str = "ATREES"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"

    # Server
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    WORKERS: int = 1

    # Security (REQUIRED - no defaults)
    ENCRYPTION_KEY: SecretStr
    API_KEY: SecretStr

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

    # Nested settings
    telegram_mtproto: TelegramMTProtoSettings = Field(default_factory=TelegramMTProtoSettings)
    telegram_bot: TelegramBotSettings = Field(default_factory=TelegramBotSettings)
    google: GoogleSettings = Field(default_factory=GoogleSettings)
    ai: AISettings = Field(default_factory=AISettings)
    notifications: NotificationSettings = Field(default_factory=NotificationSettings)
    tasks: TaskCalendarSettings = Field(default_factory=TaskCalendarSettings)
    sync: SyncSettings = Field(default_factory=SyncSettings)
    privacy: PrivacySettings = Field(default_factory=PrivacySettings)
    frontend: FrontendSettings = Field(default_factory=FrontendSettings)

    @model_validator(mode="after")
    def validate_secrets(self) -> "Settings":
        """Ensure required secrets are not using default/placeholder values."""
        encryption_key = self.ENCRYPTION_KEY.get_secret_value()
        api_key = self.API_KEY.get_secret_value()

        if encryption_key in ("changeme", "your_encryption_key_here", ""):
            raise ValueError(
                "ENCRYPTION_KEY must be set to a secure random value. "
                "Generate with: python -c \"import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())\""
            )
        if api_key in ("changeme", "your_api_key_here", ""):
            raise ValueError(
                "API_KEY must be set to a secure random value. "
                "Generate with: python -c \"import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())\""
            )

        # Validate key lengths (32 bytes = 44 chars base64)
        import base64
        try:
            enc_bytes = base64.b64decode(encryption_key)
            if len(enc_bytes) != 32:
                raise ValueError("ENCRYPTION_KEY must be 32 bytes (44 chars base64)")
            api_bytes = base64.b64decode(api_key)
            if len(api_bytes) != 32:
                raise ValueError("API_KEY must be 32 bytes (44 chars base64)")
        except Exception as e:
            raise ValueError(f"Invalid secret format: {e}")

        return self

    @model_validator(mode="after")
    def create_directories(self) -> "Settings":
        """Ensure data directories exist."""
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        self.LOGS_DIR.mkdir(parents=True, exist_ok=True)
        return self


# Global settings instance
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get the global settings instance (singleton)."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """Reload settings from environment (useful for testing)."""
    global _settings
    _settings = Settings()
    return _settings