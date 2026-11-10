"""
Custom exceptions for ATREES.

Provides structured error handling with error codes and context.
"""

from typing import Any


class ATREESError(Exception):
    """Base exception for all ATREES errors."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        details: dict[str, Any] | None = None,
        status_code: int = 500,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.details = details or {}
        self.status_code = status_code

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": self.code,
            "message": self.message,
            "details": self.details,
        }


class ConfigurationError(ATREESError):
    """Configuration-related errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message, code="CONFIGURATION_ERROR", details=details, status_code=500)


class ValidationError(ATREESError):
    """Input validation errors."""

    def __init__(self, message: str, field: str | None = None, details: dict[str, Any] | None = None):
        super().__init__(message, code="VALIDATION_ERROR", details=details, status_code=400)
        if field:
            self.details["field"] = field


class AuthenticationError(ATREESError):
    """Authentication failures."""

    def __init__(self, message: str = "Authentication required", details: dict[str, Any] | None = None):
        super().__init__(message, code="AUTHENTICATION_ERROR", details=details, status_code=401)


class AuthorizationError(ATREESError):
    """Authorization failures (insufficient permissions)."""

    def __init__(self, message: str = "Insufficient permissions", details: dict[str, Any] | None = None):
        super().__init__(message, code="AUTHORIZATION_ERROR", details=details, status_code=403)


class NotFoundError(ATREESError):
    """Resource not found."""

    def __init__(self, resource: str, identifier: str | int, details: dict[str, Any] | None = None):
        message = f"{resource} not found: {identifier}"
        super().__init__(message, code="NOT_FOUND", details=details, status_code=404)
        self.details["resource"] = resource
        self.details["identifier"] = str(identifier)


class ConflictError(ATREESError):
    """Resource conflict (e.g., duplicate)."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message, code="CONFLICT", details=details, status_code=409)


class ExternalServiceError(ATREESError):
    """Errors from external APIs (Telegram, Google, AI providers)."""

    def __init__(
        self,
        service: str,
        message: str,
        status_code: int | None = None,
        response_body: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        full_details = details or {}
        full_details["service"] = service
        if status_code:
            full_details["status_code"] = status_code
        if response_body:
            full_details["response_body"] = response_body[:500]  # Truncate
        super().__init__(message, code="EXTERNAL_SERVICE_ERROR", details=full_details, status_code=502)


class RateLimitError(ExternalServiceError):
    """Rate limit exceeded from external service."""

    def __init__(self, service: str, retry_after: int | None = None, details: dict[str, Any] | None = None):
        full_details = details or {}
        full_details["service"] = service
        if retry_after:
            full_details["retry_after_seconds"] = retry_after
        super().__init__(
            service=service,
            message=f"Rate limit exceeded for {service}",
            details=full_details,
            status_code=429,
        )


class SyncError(ATREESError):
    """Synchronization errors."""

    def __init__(
        self,
        source: str,
        message: str,
        connector_type: str | None = None,
        cursor: dict | None = None,
        details: dict[str, Any] | None = None,
    ):
        full_details = details or {}
        full_details["source"] = source
        if connector_type:
            full_details["connector_type"] = connector_type
        if cursor:
            full_details["cursor"] = cursor
        super().__init__(message, code="SYNC_ERROR", details=full_details, status_code=500)


class AIProviderError(ATREESError):
    """AI provider errors."""

    def __init__(
        self,
        provider: str,
        model: str | None,
        message: str,
        error_type: str = "unknown",
        details: dict[str, Any] | None = None,
    ):
        full_details = details or {}
        full_details["provider"] = provider
        if model:
            full_details["model"] = model
        full_details["error_type"] = error_type
        super().__init__(message, code="AI_PROVIDER_ERROR", details=full_details, status_code=502)


class DatabaseError(ATREESError):
    """Database operation errors."""

    def __init__(self, operation: str, message: str, details: dict[str, Any] | None = None):
        full_details = details or {}
        full_details["operation"] = operation
        super().__init__(message, code="DATABASE_ERROR", details=full_details, status_code=500)


class EncryptionError(ATREESError):
    """Encryption/decryption errors."""

    def __init__(self, operation: str, message: str, details: dict[str, Any] | None = None):
        full_details = details or {}
        full_details["operation"] = operation
        super().__init__(message, code="ENCRYPTION_ERROR", details=full_details, status_code=500)


class ConnectorError(ATREESError):
    """Connector-specific errors."""

    def __init__(
        self,
        connector_type: str,
        operation: str,
        message: str,
        recoverable: bool = True,
        details: dict[str, Any] | None = None,
    ):
        full_details = details or {}
        full_details["connector_type"] = connector_type
        full_details["operation"] = operation
        full_details["recoverable"] = recoverable
        super().__init__(message, code="CONNECTOR_ERROR", details=full_details, status_code=500)


class ApprovalRequiredError(ATREESError):
    """Action requires user approval."""

    def __init__(
        self,
        action: str,
        resource_type: str,
        resource_id: int | str,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        full_details = details or {}
        full_details["action"] = action
        full_details["resource_type"] = resource_type
        full_details["resource_id"] = str(resource_id)
        msg = message or f"Approval required for {action} on {resource_type} {resource_id}"
        super().__init__(msg, code="APPROVAL_REQUIRED", details=full_details, status_code=403)


class TaskPlanningError(ATREESError):
    """Task planning/scheduling errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message, code="TASK_PLANNING_ERROR", details=details, status_code=400)


# Error code to HTTP status mapping
ERROR_STATUS_CODES = {
    "CONFIGURATION_ERROR": 500,
    "VALIDATION_ERROR": 400,
    "AUTHENTICATION_ERROR": 401,
    "AUTHORIZATION_ERROR": 403,
    "NOT_FOUND": 404,
    "CONFLICT": 409,
    "EXTERNAL_SERVICE_ERROR": 502,
    "RATE_LIMIT_ERROR": 429,
    "SYNC_ERROR": 500,
    "AI_PROVIDER_ERROR": 502,
    "DATABASE_ERROR": 500,
    "ENCRYPTION_ERROR": 500,
    "CONNECTOR_ERROR": 500,
    "APPROVAL_REQUIRED": 403,
    "TASK_PLANNING_ERROR": 400,
    "INTERNAL_ERROR": 500,
}


def get_status_code(error_code: str) -> int:
    """Get HTTP status code for error code."""
    return ERROR_STATUS_CODES.get(error_code, 500)


def is_recoverable(error: Exception) -> bool:
    """Check if an error is recoverable (should retry)."""
    if isinstance(error, (RateLimitError, ExternalServiceError, AIProviderError)):
        return True
    if isinstance(error, ConnectorError):
        return error.details.get("recoverable", True)
    return False