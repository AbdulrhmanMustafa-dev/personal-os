"""
Structured logging configuration for ATREES.

Uses structlog for structured JSON logging with context propagation.
"""

import sys
import logging
from typing import Any
import structlog
from structlog.types import EventDict, WrappedLogger

from atrees.config import get_settings
from atrees.core.security import sanitize_for_logging


def add_secrets_filter(logger: WrappedLogger, method_name: str, event_dict: EventDict) -> EventDict:
    """Filter out secrets from log entries."""
    return sanitize_for_logging(event_dict)


def add_correlation_id(logger: WrappedLogger, method_name: str, event_dict: EventDict) -> EventDict:
    """Add correlation ID from context if available."""
    # Correlation ID can be set via structlog.contextvars.bind_contextvars
    return event_dict


def setup_logging() -> None:
    """Configure structlog for the application."""
    settings = get_settings()

    # Standard library logging config
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.LOG_LEVEL.upper()),
    )

    # Structlog processors
    processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        add_secrets_filter,
        add_correlation_id,
    ]

    if settings.LOG_FORMAT == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)


# Convenience functions for common logging patterns
def log_sync_start(logger: structlog.BoundLogger, source_name: str, connector_type: str, incremental: bool) -> None:
    logger.info(
        "sync_started",
        source=source_name,
        connector_type=connector_type,
        incremental=incremental,
    )


def log_sync_complete(
    logger: structlog.BoundLogger,
    source_name: str,
    connector_type: str,
    items_processed: int,
    items_created: int,
    items_updated: int,
    items_failed: int,
    duration_ms: int,
) -> None:
    logger.info(
        "sync_completed",
        source=source_name,
        connector_type=connector_type,
        items_processed=items_processed,
        items_created=items_created,
        items_updated=items_updated,
        items_failed=items_failed,
        duration_ms=duration_ms,
    )


def log_sync_error(
    logger: structlog.BoundLogger,
    source_name: str,
    connector_type: str,
    error: Exception,
    incremental: bool,
) -> None:
    logger.error(
        "sync_failed",
        source=source_name,
        connector_type=connector_type,
        incremental=incremental,
        error_type=type(error).__name__,
        error_message=str(error),
    )


def log_ai_request(
    logger: structlog.BoundLogger,
    provider: str,
    model: str,
    prompt_tokens: int | None = None,
    purpose: str = "completion",
) -> None:
    logger.debug(
        "ai_request",
        provider=provider,
        model=model,
        prompt_tokens=prompt_tokens,
        purpose=purpose,
    )


def log_ai_response(
    logger: structlog.BoundLogger,
    provider: str,
    model: str,
    completion_tokens: int | None = None,
    duration_ms: int | None = None,
    success: bool = True,
    error: str | None = None,
) -> None:
    if success:
        logger.debug(
            "ai_response",
            provider=provider,
            model=model,
            completion_tokens=completion_tokens,
            duration_ms=duration_ms,
        )
    else:
        logger.warning(
            "ai_response_failed",
            provider=provider,
            model=model,
            duration_ms=duration_ms,
            error=error,
        )


def log_task_created(
    logger: structlog.BoundLogger,
    task_id: int,
    title: str,
    source: str,
    confidence: float,
    auto_approved: bool,
) -> None:
    logger.info(
        "task_created",
        task_id=task_id,
        title=title[:100],
        source=source,
        confidence=confidence,
        auto_approved=auto_approved,
    )


def log_notification_sent(
    logger: structlog.BoundLogger,
    notification_id: int,
    channel: str,
    priority: str,
    recipient: str,
    success: bool,
    error: str | None = None,
) -> None:
    if success:
        logger.info(
            "notification_sent",
            notification_id=notification_id,
            channel=channel,
            priority=priority,
            recipient=recipient,
        )
    else:
        logger.warning(
            "notification_failed",
            notification_id=notification_id,
            channel=channel,
            priority=priority,
            recipient=recipient,
            error=error,
        )


def log_security_event(
    logger: structlog.BoundLogger,
    event_type: str,
    user_id: str | None = None,
    ip: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    logger.warning(
        "security_event",
        event_type=event_type,
        user_id=user_id,
        ip=ip,
        details=details or {},
    )


# Context managers for operation tracing
class LogContext:
    """Context manager for adding structured context to logs."""

    def __init__(self, logger: structlog.BoundLogger, **context: Any):
        self.logger = logger
        self.context = context
        self.tokens: list[structlog.contextvars.Token] = []

    def __enter__(self) -> structlog.BoundLogger:
        for key, value in self.context.items():
            token = structlog.contextvars.bind_contextvars(**{key: value})
            self.tokens.append(token)
        return self.logger

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        for token in reversed(self.tokens):
            structlog.contextvars.unbind_contextvars(token)


def with_context(logger: structlog.BoundLogger, **context: Any) -> LogContext:
    """Create a log context manager."""
    return LogContext(logger, **context)