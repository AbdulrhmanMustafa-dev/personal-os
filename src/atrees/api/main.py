"""FastAPI application and lifecycle management for ATREES."""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from atrees.api.routes import connectors, dashboard, health, notifications, sources, tasks
from atrees.config import get_settings
from atrees.core.auth import secret_matches
from atrees.core.exceptions import ATREESError, get_status_code
from atrees.core.logging import get_logger, setup_logging
from atrees.database import close_db, get_session, init_db

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Initialize resources and reliably stop background workers on shutdown."""
    settings = get_settings()
    setup_logging()
    logger.info("application_starting", version=settings.APP_VERSION)
    await init_db()

    tasks = [
        asyncio.create_task(_background_sync_loop(), name="atrees-sync"),
        asyncio.create_task(_background_notification_loop(), name="atrees-notifications"),
    ]
    app.state.background_tasks = tasks
    logger.info("application_started")
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await close_db()
        logger.info("application_stopped")


def create_app() -> FastAPI:
    """Create the ATREES API application."""
    settings = get_settings()
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description="Local-first Personal Life Operating System",
        lifespan=lifespan,
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.frontend.CORS_ORIGINS,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "X-ATREES-API-Key", "X-Telegram-Bot-Api-Secret-Token"],
    )

    @app.middleware("http")
    async def require_api_key(request: Request, call_next):
        """Protect private API routes; expose only the liveness endpoint."""
        path = request.url.path
        if path.startswith("/api/") and path != "/api/health":
            supplied = request.headers.get("X-ATREES-API-Key", "")
            expected = settings.API_KEY.get_secret_value()
            if not secret_matches(supplied, expected):
                return JSONResponse(
                    status_code=401,
                    content={"error": "UNAUTHORIZED", "message": "A valid X-ATREES-API-Key header is required."},
                    headers={"WWW-Authenticate": "ApiKey"},
                )
        if path == "/webhook/telegram":
            expected_secret = settings.telegram_bot.WEBHOOK_SECRET
            if expected_secret is None:
                return JSONResponse(status_code=503, content={"error": "WEBHOOK_NOT_CONFIGURED"})
            supplied_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
            if not secret_matches(supplied_secret, expected_secret.get_secret_value()):
                return JSONResponse(status_code=401, content={"error": "INVALID_WEBHOOK_SECRET"})
        return await call_next(request)

    @app.exception_handler(ATREESError)
    async def atrees_exception_handler(request: Request, exc: ATREESError) -> JSONResponse:
        return JSONResponse(status_code=get_status_code(exc.code), content=exc.to_dict())

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("unhandled_exception", error_type=type(exc).__name__, path=request.url.path)
        return JSONResponse(status_code=500, content={"error": "INTERNAL_ERROR", "message": "Internal server error"})

    app.include_router(health.router, prefix="/api", tags=["Health"])
    app.include_router(sources.router, prefix="/api/sources", tags=["Sources"])
    app.include_router(connectors.router, prefix="/api/connectors", tags=["Connectors"])
    app.include_router(tasks.router, prefix="/api/tasks", tags=["Tasks"])
    app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
    app.include_router(notifications.router, prefix="/api/notifications", tags=["Notifications"])

    @app.post("/webhook/telegram")
    async def telegram_webhook(request: Request) -> dict[str, bool]:
        """Process Telegram updates using a request-scoped database session."""
        from atrees.services.notification_service import NotificationService

        payload = await request.json()
        async with get_session() as db:
            service = NotificationService(db)
            await service.initialize()
            connector = service._telegram_connector
            if connector is None:
                return {"ok": False}
            try:
                await connector.process_webhook(payload)
            finally:
                await connector.disconnect()
        return {"ok": True}

    if not settings.DEBUG and settings.frontend.BUILD_PATH.exists():
        app.mount("/", StaticFiles(directory=settings.frontend.BUILD_PATH, html=True), name="frontend")
    return app


async def _background_sync_loop() -> None:
    """Run connector synchronization in independent, short-lived DB sessions."""
    from atrees.services.sync_service import SyncService

    settings = get_settings()
    while True:
        try:
            await asyncio.sleep(max(60, settings.sync.SYNC_INTERVAL_MINUTES * 60))
            if not settings.sync.AUTO_SYNC_ENABLED:
                continue
            async with get_session() as db:
                results = await SyncService(db).sync_all()
            logger.info("auto_sync_completed", results={key: value.status.value for key, value in results.items()})
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("auto_sync_failed", error_type=type(exc).__name__)
            await asyncio.sleep(60)


async def _background_notification_loop() -> None:
    """Process reminders and scheduled notifications once per minute."""
    from atrees.services.notification_service import NotificationService

    settings = get_settings()
    last_briefing_date: str | None = None
    timezone = ZoneInfo(settings.TIMEZONE)
    while True:
        try:
            async with get_session() as db:
                service = NotificationService(db)
                try:
                    await service.initialize()
                    await service.process_scheduled_notifications()
                    await service.check_reminders()
                    now = datetime.now(timezone)
                    briefing_hour, briefing_minute = map(int, settings.notifications.DAILY_DIGEST_TIME.split(":"))
                    today = now.date().isoformat()
                    if now.hour == briefing_hour and now.minute == briefing_minute and today != last_briefing_date:
                        await service.send_daily_briefing()
                        last_briefing_date = today
                finally:
                    if service._telegram_connector:
                        await service._telegram_connector.disconnect()
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("notification_loop_failed", error_type=type(exc).__name__)
            await asyncio.sleep(60)


app = create_app()
