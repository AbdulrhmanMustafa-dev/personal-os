"""
Core modules for ATREES.

Provides security, logging, exceptions, and shared utilities.
"""

from atrees.core.security import (
    EncryptionManager,
    SecretManager,
    EncryptedJSON,
    EncryptedString,
    generate_encryption_key,
    generate_api_key,
    sanitize_untrusted_input,
    sanitize_for_logging,
)
from atrees.core.logging import (
    setup_logging,
    get_logger,
    log_sync_start,
    log_sync_complete,
    log_sync_error,
    log_ai_request,
    log_ai_response,
    log_task_created,
    log_notification_sent,
    log_security_event,
    with_context,
)
from atrees.core.exceptions import (
    ATREESError,
    ConfigurationError,
    ValidationError,
    AuthenticationError,
    AuthorizationError,
    NotFoundError,
    ConflictError,
    ExternalServiceError,
    RateLimitError,
    SyncError,
    AIProviderError,
    DatabaseError,
    EncryptionError,
    ConnectorError,
    ApprovalRequiredError,
    TaskPlanningError,
    get_status_code,
    is_recoverable,
)

__all__ = [
    # Security
    "EncryptionManager",
    "SecretManager",
    "EncryptedJSON",
    "EncryptedString",
    "generate_encryption_key",
    "generate_api_key",
    "sanitize_untrusted_input",
    "sanitize_for_logging",
    # Logging
    "setup_logging",
    "get_logger",
    "log_sync_start",
    "log_sync_complete",
    "log_sync_error",
    "log_ai_request",
    "log_ai_response",
    "log_task_created",
    "log_notification_sent",
    "log_security_event",
    "with_context",
    # Exceptions
    "ATREESError",
    "ConfigurationError",
    "ValidationError",
    "AuthenticationError",
    "AuthorizationError",
    "NotFoundError",
    "ConflictError",
    "ExternalServiceError",
    "RateLimitError",
    "SyncError",
    "AIProviderError",
    "DatabaseError",
    "EncryptionError",
    "ConnectorError",
    "ApprovalRequiredError",
    "TaskPlanningError",
    "get_status_code",
    "is_recoverable",
]