"""
Notification service for ATREES.

Handles notification delivery, deduplication, and scheduling.
"""

import asyncio
from datetime import datetime, timedelta, time
from typing import Any

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from atrees.models.notification import Notification, NotificationPriority, NotificationStatus
from atrees.models.task import Task
from atrees.models.calendar import Event, Reminder
from atrees.connectors.telegram_bot import TelegramBotConnector
from atrees.connectors.base import ConnectorConfig
from atrees.core.logging import get_logger, log_notification_sent
from atrees.core.security import EncryptionManager
from atrees.config import get_settings

logger = get_logger(__name__)


class NotificationService:
    """Service for managing notifications across channels."""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.settings = get_settings()
        self._telegram_connector: TelegramBotConnector | None = None
        self._encryption = EncryptionManager()

    async def initialize(self) -> None:
        """Initialize notification channels."""
        # Initialize Telegram Bot connector if available
        try:
            from atrees.models.source import Source
            stmt = select(Source).where(Source.connector_type == "telegram_bot", Source.deleted_at.is_(None))
            result = await self.db.execute(stmt)
            bot_source = result.scalar_one_or_none()

            if bot_source and bot_source.config.get("bot_token"):
                # The service may be initialized by a short-lived worker. Do not
                # emit a "startup" message every time a worker reconnects.
                connector_config = dict(bot_source.config)
                connector_config["notify_on_startup"] = False
                connector_config.setdefault("webhook_url", self.settings.telegram_bot.WEBHOOK_URL)
                webhook_secret = self.settings.telegram_bot.WEBHOOK_SECRET
                if webhook_secret:
                    connector_config.setdefault("webhook_secret", webhook_secret.get_secret_value())
                connector_config.setdefault("admin_user_ids", self.settings.telegram_bot.ADMIN_USER_IDS)
                connector_config.setdefault("allowed_user_ids", self.settings.telegram_bot.ALLOWED_USER_IDS)
                config = ConnectorConfig(
                    source_id=bot_source.id,
                    name=bot_source.name,
                    config=connector_config,
                )
                self._telegram_connector = TelegramBotConnector(config, self.db)
                await self._telegram_connector.connect()
        except Exception as e:
            logger.warning("telegram_bot_init_failed", error=str(e))

    async def send_notification(
        self,
        title: str,
        body: str | None = None,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        channels: list[str] | None = None,
        related_task_id: int | None = None,
        related_event_id: int | None = None,
        related_reminder_id: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Notification:
        """Create and queue a notification for delivery."""
        if channels is None:
            channels = ["telegram"] if self._telegram_connector else ["dashboard"]

        # Check deduplication
        if await self._is_duplicate(title, body, channels):
            logger.info("notification_duplicate_skipped", title=title[:50])
            return None

        # Check quiet hours
        if self._is_quiet_hours() and priority not in (NotificationPriority.CRITICAL, NotificationPriority.HIGH):
            # Schedule for after quiet hours
            return await self._schedule_after_quiet_hours(
                title, body, priority, channels, related_task_id, related_event_id, related_reminder_id, metadata
            )

        # Create notification record
        notification = Notification(
            title=title,
            body=body,
            priority=priority,
            channels=channels,
            status=NotificationStatus.PENDING,
            related_task_id=related_task_id,
            related_event_id=related_event_id,
            related_reminder_id=related_reminder_id,
            metadata=metadata or {},
        )
        self.db.add(notification)
        await self.db.commit()
        await self.db.refresh(notification)

        # Deliver immediately
        await self._deliver_notification(notification)
        return notification

    async def _deliver_notification(self, notification: Notification) -> None:
        """Deliver notification to all channels."""
        errors = []

        for channel in notification.channels:
            try:
                if channel == "telegram" and self._telegram_connector:
                    await self._deliver_telegram(notification)
                elif channel == "ntfy":
                    await self._deliver_ntfy(notification)
                elif channel == "dashboard":
                    # Dashboard notifications are just stored in DB
                    pass
                else:
                    errors.append(f"Unknown channel: {channel}")
            except Exception as e:
                errors.append(f"{channel}: {e}")

        # Update status
        if errors:
            notification.status = NotificationStatus.FAILED
            notification.error_message = "; ".join(errors)
            notification.retry_count += 1
        else:
            notification.status = NotificationStatus.SENT
            notification.sent_at = datetime.utcnow()

        await self.db.commit()

        log_notification_sent(
            logger,
            notification.id,
            ", ".join(notification.channels),
            notification.priority.value,
            "broadcast" if len(notification.channels) > 1 else "single",
            not errors,
            errors[0] if errors else None,
        )

    async def _deliver_telegram(self, notification: Notification) -> None:
        """Deliver via Telegram Bot."""
        if not self._telegram_connector:
            raise RuntimeError("Telegram connector not initialized")

        # Get admin users to notify
        from atrees.models.source import Source
        stmt = select(Source).where(Source.id == self._telegram_connector.config.source_id)
        result = await self.db.execute(stmt)
        source = result.scalar_one_or_none()

        admin_ids = source.config.get("admin_user_ids", []) if source else []

        for admin_id in admin_ids:
            await self._telegram_connector.send_notification(
                admin_id,
                notification.title,
                notification.body or "",
                notification.priority.value,
            )

    async def _deliver_ntfy(self, notification: Notification) -> None:
        """Deliver via ntfy.sh."""
        import httpx

        topic = self.settings.notifications.NTFY_TOPIC
        server = self.settings.notifications.NTFY_SERVER

        if not topic:
            raise RuntimeError("NTFY_TOPIC not configured")

        priority_map = {
            NotificationPriority.CRITICAL: 5,
            NotificationPriority.HIGH: 4,
            NotificationPriority.NORMAL: 3,
            NotificationPriority.LOW: 2,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{server}/{topic}",
                content=f"{notification.title}\n\n{notification.body or ''}".encode("utf-8"),
                headers={
                    "Priority": str(priority_map.get(notification.priority, 3)),
                    "Title": notification.title,
                },
                timeout=10,
            )
            response.raise_for_status()

    async def _is_duplicate(self, title: str, body: str | None, channels: list[str]) -> bool:
        """Check if similar notification was sent recently."""
        dedup_window = timedelta(minutes=self.settings.notifications.DEDUP_WINDOW_MINUTES)
        cutoff = datetime.utcnow() - dedup_window

        stmt = select(Notification).where(
            Notification.title == title,
            Notification.created_at >= cutoff,
            Notification.status.in_([NotificationStatus.SENT, NotificationStatus.PENDING]),
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none() is not None

    def _is_quiet_hours(self) -> bool:
        """Check if current time is in quiet hours."""
        start_str = self.settings.notifications.QUIET_HOURS_START
        end_str = self.settings.notifications.QUIET_HOURS_END

        start_time = time.fromisoformat(start_str)
        end_time = time.fromisoformat(end_str)
        now = datetime.now().time()

        if start_time <= end_time:
            # Same day (e.g., 22:00 - 08:00 next day)
            return start_time <= now or now <= end_time
        else:
            # Overnight (e.g., 22:00 - 08:00)
            return start_time <= now <= end_time

    async def _schedule_after_quiet_hours(
        self,
        title: str,
        body: str | None,
        priority: NotificationPriority,
        channels: list[str],
        related_task_id: int | None,
        related_event_id: int | None,
        related_reminder_id: int | None,
        metadata: dict[str, Any] | None,
    ) -> Notification:
        """Schedule notification for after quiet hours."""
        end_str = self.settings.notifications.QUIET_HOURS_END
        end_time = time.fromisoformat(end_str)
        tomorrow = datetime.now().date() + timedelta(days=1)
        send_at = datetime.combine(tomorrow, end_time)

        notification = Notification(
            title=title,
            body=body,
            priority=priority,
            channels=channels,
            status=NotificationStatus.PENDING,
            related_task_id=related_task_id,
            related_event_id=related_event_id,
            related_reminder_id=related_reminder_id,
            metadata={**(metadata or {}), "scheduled_for": send_at.isoformat()},
        )
        self.db.add(notification)
        await self.db.commit()
        return notification

    async def process_scheduled_notifications(self) -> int:
        """Process notifications scheduled for delivery."""
        now = datetime.utcnow()

        stmt = select(Notification).where(
            Notification.status == NotificationStatus.PENDING,
            Notification.metadata.has_key("scheduled_for"),
        )
        result = await self.db.execute(stmt)
        notifications = result.scalars().all()

        sent = 0
        for notif in notifications:
            scheduled_str = notif.metadata.get("scheduled_for")
            if scheduled_str:
                scheduled = datetime.fromisoformat(scheduled_str)
                if scheduled <= now:
                    await self._deliver_notification(notif)
                    sent += 1

        return sent

    async def send_daily_briefing(self) -> None:
        """Send daily briefing notification."""
        from atrees.services.task_service import TaskService

        task_service = TaskService(self.db)
        today_plan = await task_service.get_today_plan()

        # Build briefing message
        lines = ["🌅 **صباح الخير! إليك موجز يومك:**\n"]

        # Big task
        if today_plan["big"]:
            lines.append(f"🎯 **المهمة الكبيرة:** {today_plan['big'][0]['title']}")
        else:
            lines.append("🎯 **المهمة الكبيرة:** (لا توجد)")

        # Medium tasks
        if today_plan["medium"]:
            lines.append("\n📋 **مهام متوسطة:**")
            for i, task in enumerate(today_plan["medium"], 1):
                lines.append(f"  {i}. {task['title']}")
        else:
            lines.append("\n📋 **مهام متوسطة:** (لا توجد)")

        # Small tasks
        if today_plan["small"]:
            lines.append("\n✅ **مهام صغيرة:**")
            for i, task in enumerate(today_plan["small"], 1):
                lines.append(f"  {i}. {task['title']}")
        else:
            lines.append("\n✅ **مهام صغيرة:** (لا توجد)")

        # Events
        if today_plan["events"]:
            lines.append("\n📆 **المواعيد:**")
            for event in today_plan["events"]:
                start = datetime.fromisoformat(event["start"]).strftime("%H:%M")
                lines.append(f"  • {start} - {event['title']}")
        else:
            lines.append("\n📆 **المواعيد:** (لا توجد)")

        message = "\n".join(lines)

        await self.send_notification(
            title="الموجز اليومي",
            body=message,
            priority=NotificationPriority.NORMAL,
            channels=["telegram", "dashboard"],
            metadata={"type": "daily_briefing"},
        )

    async def send_weekly_review(self) -> None:
        """Send weekly review notification."""
        # TODO: Implement weekly review
        pass

    async def check_reminders(self) -> int:
        """Check and send due reminders."""
        now = datetime.utcnow()

        stmt = select(Reminder).where(
            Reminder.remind_at <= now,
            Reminder.status == "pending",
            Reminder.deleted_at.is_(None),
        )
        result = await self.db.execute(stmt)
        reminders = result.scalars().all()

        sent = 0
        for reminder in reminders:
            await self.send_notification(
                title=reminder.title,
                body=reminder.description,
                priority=NotificationPriority(reminder.priority),
                channels=reminder.channels,
                related_task_id=reminder.related_task_id,
                related_event_id=reminder.related_event_id,
                related_reminder_id=reminder.id,
            )
            reminder.status = "sent"
            sent += 1

        if sent > 0:
            await self.db.commit()

        return sent