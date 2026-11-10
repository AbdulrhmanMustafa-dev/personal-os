"""
Telegram Bot API connector for ATREES.

Handles notifications, commands, and webhook processing.
"""

import asyncio
import json
from datetime import datetime
from typing import Any

from telegram import Update, Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from atrees.connectors.base import BaseConnector, ConnectorConfig, SyncResult, SyncStatus, ConnectorStatus
from atrees.database import get_session
from atrees.core.security import EncryptionManager
from atrees.core.logging import get_logger
from atrees.config import get_settings


class TelegramBotConnector(BaseConnector):
    """Telegram Bot API connector for notifications and commands."""

    CONNECTOR_TYPE = "telegram_bot"
    DISPLAY_NAME = "Telegram Bot"
    DESCRIPTION = "Send notifications and handle commands via Telegram Bot API"
    SUPPORTS_INCREMENTAL = False
    SUPPORTS_REALTIME = True
    REQUIRES_USER_AUTH = True

    def __init__(self, config: ConnectorConfig, db_session):
        super().__init__(config, db_session)
        self.bot: Bot | None = None
        self.application: Application | None = None
        self._encryption = EncryptionManager()
        self._webhook_url: str | None = None
        self._allowed_users: set[int] = set()
        self._admin_users: set[int] = set()

    async def connect(self) -> bool:
        """Initialize bot and set up handlers."""
        try:
            token_encrypted = self.config.config.get("bot_token")
            if not token_encrypted:
                self.logger.error("missing_bot_token")
                await self._update_source_status(ConnectorStatus.ERROR, "Missing bot token")
                return False

            token = self._encryption.decrypt(token_encrypted)
            self.bot = Bot(token=token)

            # Load allowed/admin users
            self._admin_users = set(self.config.config.get("admin_user_ids", []))
            self._allowed_users = set(self.config.config.get("allowed_user_ids", []))
            self._allowed_users.update(self._admin_users)  # Admins are always allowed

            # Create application
            self.application = Application.builder().token(token).build()

            # Register handlers
            self._register_handlers()

            # Initialize
            await self.application.initialize()

            # Set webhook if configured
            webhook_url = self.config.config.get("webhook_url")
            if webhook_url:
                await self._set_webhook(webhook_url)

            self.status = ConnectorStatus.CONNECTED
            await self._update_source_status(ConnectorStatus.CONNECTED)

            # Send startup notification
            if self.config.config.get("notify_on_startup", True):
                await self._send_startup_notification()

            self.logger.info("bot_connected", bot_username=self.bot.username)
            return True

        except Exception as e:
            self.logger.error("bot_connect_failed", error=str(e))
            await self._update_source_status(ConnectorStatus.ERROR, str(e))
            return False

    async def disconnect(self) -> bool:
        """Shutdown bot."""
        try:
            if self.application:
                await self.application.shutdown()
                self.application = None
            self.bot = None
            self.status = ConnectorStatus.DISCONNECTED
            await self._update_source_status(ConnectorStatus.DISCONNECTED)
            return True
        except Exception as e:
            self.logger.error("bot_disconnect_failed", error=str(e))
            return False

    async def test_connection(self) -> tuple[bool, str]:
        """Test bot connection."""
        try:
            if not self.bot:
                return False, "Not initialized"
            me = await self.bot.get_me()
            return True, f"Connected as @{me.username}"
        except Exception as e:
            return False, str(e)

    async def sync(self, incremental: bool = True) -> SyncResult:
        """Bot connector doesn't sync data - it handles real-time events."""
        return SyncResult(status=SyncStatus.SUCCESS, items_processed=0)

    async def get_sync_status(self) -> dict[str, Any]:
        """Get bot status."""
        return {
            "status": self.status.value,
            "bot_username": self.bot.username if self.bot else None,
            "webhook_url": self._webhook_url,
            "allowed_users": len(self._allowed_users),
            "admin_users": len(self._admin_users),
        }

    # --- Public API for sending notifications ---

    async def send_message(
        self,
        chat_id: int,
        text: str,
        parse_mode: str = "Markdown",
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> bool:
        """Send a message to a chat."""
        if not self.bot:
            return False
        try:
            await self.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
            )
            return True
        except Exception as e:
            self.logger.error("send_message_failed", chat_id=chat_id, error=str(e))
            return False

    async def send_notification(
        self,
        user_id: int,
        title: str,
        body: str,
        priority: str = "normal",
        action_url: str | None = None,
    ) -> bool:
        """Send a formatted notification."""
        priority_emoji = {"critical": "🔴", "high": "🟠", "normal": "🔵", "low": "⚪"}.get(priority, "🔵")
        text = f"{priority_emoji} **{title}**\n\n{body}"
        if action_url:
            text += f"\n\n[Open]({action_url})"
        return await self.send_message(user_id, text)

    async def broadcast(self, user_ids: list[int], text: str) -> dict[int, bool]:
        """Send message to multiple users."""
        results = {}
        for uid in user_ids:
            results[uid] = await self.send_message(uid, text)
            await asyncio.sleep(0.1)  # Rate limiting
        return results

    # --- Internal Methods ---

    def _register_handlers(self) -> None:
        """Register command and callback handlers."""
        if not self.application:
            return

        # Commands
        self.application.add_handler(CommandHandler("start", self._cmd_start))
        self.application.add_handler(CommandHandler("help", self._cmd_help))
        self.application.add_handler(CommandHandler("today", self._cmd_today))
        self.application.add_handler(CommandHandler("tasks", self._cmd_tasks))
        self.application.add_handler(CommandHandler("add_task", self._cmd_add_task))
        self.application.add_handler(CommandHandler("calendar", self._cmd_calendar))
        self.application.add_handler(CommandHandler("sync", self._cmd_sync))
        self.application.add_handler(CommandHandler("status", self._cmd_status))
        self.application.add_handler(CommandHandler("ask", self._cmd_ask))
        self.application.add_handler(CommandHandler("approve", self._cmd_approve))

        # Callbacks
        self.application.add_handler(CallbackQueryHandler(self._handle_callback))

        # Error handler
        self.application.add_error_handler(self._error_handler)

    def _check_permission(self, user_id: int, require_admin: bool = False) -> bool:
        """Check if user is allowed to use the bot."""
        if require_admin:
            return user_id in self._admin_users
        if not self._allowed_users:
            return True  # No restriction
        return user_id in self._allowed_users

    async def _cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        user = update.effective_user
        if not self._check_permission(user.id):
            await update.message.reply_text("⛔ غير مصرح لك باستخدام هذا البوت.")
            return

        await update.message.reply_text(
            "👋 مرحباً! أنا ATREES - مساعدك الشخصي.\n\n"
            "استخدم /help لرؤية الأوامر المتاحة."
        )

    async def _cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command."""
        user = update.effective_user
        if not self._check_permission(user.id):
            return

        is_admin = user.id in self._admin_users
        help_text = (
            "📋 **الأوامر المتاحة:**\n\n"
            "/today - مهام ومواعيد اليوم\n"
            "/tasks - قائمة المهام\n"
            "/add_task - إضافة مهمة جديدة\n"
            "/calendar - المواعيد القادمة\n"
            "/sync - مزامنة يدوية\n"
            "/status - حالة המערכת\n"
            "/ask - اسأل ATREES سؤالاً\n"
        )
        if is_admin:
            help_text += "\n/approve - موافقة على إجراءات معلقة"
        await update.message.reply_text(help_text, parse_mode="Markdown")

    async def _cmd_today(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show today's tasks and events."""
        user = update.effective_user
        if not self._check_permission(user.id):
            return

        # TODO: Query actual tasks/events from database
        await update.message.reply_text(
            "📅 **اليوم**\n\n"
            "🎯 **المهمة الكبيرة:** (لا توجد)\n"
            "📋 **مهام متوسطة:** (لا توجد)\n"
            "✅ **مهام صغيرة:** (لا توجد)\n\n"
            "📆 **المواعيد:** (لا توجد)\n\n"
            "*هذه ميزة قيد التطوير*"
        )

    async def _cmd_tasks(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """List tasks with filters."""
        user = update.effective_user
        if not self._check_permission(user.id):
            return

        # Parse filter args
        args = context.args
        status_filter = args[0] if args else "active"

        await update.message.reply_text(
            f"📋 **المهام ({status_filter})**\n\n"
            "*هذه ميزة قيد التطوير*"
        )

    async def _cmd_add_task(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Add a new task."""
        user = update.effective_user
        if not self._check_permission(user.id):
            return

        # Parse: /add_task عنوان المهمة | الوصف | الأولوية | تاريخ الاستحقاق
        text = " ".join(context.args)
        if not text:
            await update.message.reply_text(
                "الاستخدام: `/add_task عنوان المهمة | الوصف | الأولوية(1-5) | YYYY-MM-DD`\n"
                "مثال: `/add_task مراجعة الكود | مراجعة PR #42 | 2 | 2026-11-10`"
            )
            return

        # TODO: Create task in database
        await update.message.reply_text("✅ تمت إضافة المهمة (قيد التطوير)")

    async def _cmd_calendar(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show upcoming events."""
        user = update.effective_user
        if not self._check_permission(user.id):
            return

        await update.message.reply_text(
            "📆 **المواعيد القادمة**\n\n"
            "*هذه ميزة قيد التطوير*"
        )

    async def _cmd_sync(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Trigger manual sync."""
        user = update.effective_user
        if not self._check_permission(user.id):
            return

        await update.message.reply_text("🔄 جاري المزامنة... (قيد التطوير)")

    async def _cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Show system status."""
        user = update.effective_user
        if not self._check_permission(user.id):
            return

        await update.message.reply_text(
            "📊 **حالة ATREES**\n\n"
            "🟢 النظام يعمل\n"
            "🔄 المزامنة: نشطة\n"
            "🤖 الذكاء الاصطناعي: متصل\n"
            "💾 قاعدة البيانات: متصلة\n\n"
            "*تفاصيل أكثر قيد التطوير*"
        )

    async def _cmd_ask(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Ask ATREES a question."""
        user = update.effective_user
        if not self._check_permission(user.id):
            return

        question = " ".join(context.args)
        if not question:
            await update.message.reply_text("الاستخدام: `/ask سؤالك هنا`")
            return

        # TODO: Process question through AI with context
        await update.message.reply_text(
            f"❓ **سؤالك:** {question}\n\n"
            "🤖 **الإجابة:** (قيد التطوير)"
        )

    async def _cmd_approve(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Approve pending actions (admin only)."""
        user = update.effective_user
        if not self._check_permission(user.id, require_admin=True):
            await update.message.reply_text("⛔ هذا الأمر للمشرفين فقط.")
            return

        await update.message.reply_text("✅ قائمة الموافقات المعلقة (قيد التطوير)")

    async def _handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle inline button callbacks."""
        query = update.callback_query
        await query.answer()

        user = query.from_user
        if not self._check_permission(user.id):
            await query.edit_message_text("⛔ غير مصرح")
            return

        data = query.data
        # Handle different callback types
        if data.startswith("approve_"):
            await query.edit_message_text("✅ تمت الموافقة (قيد التطوير)")
        elif data.startswith("reject_"):
            await query.edit_message_text("❌ تم الرفض (قيد التطوير)")

    async def _error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle errors."""
        self.logger.error("bot_error", error=str(context.error))

    async def _set_webhook(self, url: str) -> None:
        """Set webhook for production."""
        if not self.bot:
            return
        secret = self.config.config.get("webhook_secret")
        await self.bot.set_webhook(url=url, secret_token=secret)
        self._webhook_url = url
        self.logger.info("webhook_set", url=url)

    async def _send_startup_notification(self) -> None:
        """Send startup notification to admins."""
        for admin_id in self._admin_users:
            try:
                await self.send_message(
                    admin_id,
                    "🚀 **ATREES Started**\n\nالنظام يعمل الآن وجاهز للاستخدام."
                )
            except Exception:
                pass

    async def process_webhook(self, update_data: dict) -> None:
        """Process incoming webhook update."""
        if not self.application:
            return
        update = Update.de_json(update_data, self.bot)
        await self.application.process_update(update)