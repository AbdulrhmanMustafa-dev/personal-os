"""
Telegram MTProto connector using Telethon.

Monitors channels/groups for job postings and other content.
Preserves existing atrees_bot.py functionality.
"""

import asyncio
import random
import re
import json
from datetime import datetime, timedelta
from typing import Any

from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import Channel, Chat, User

from atrees.connectors.base import BaseConnector, ConnectorConfig, SyncResult, SyncStatus, ConnectorStatus
from atrees.models.source import Source, RawItem, SyncState
from atrees.models.communication import Conversation, Message, Contact
from atrees.database import get_session
from atrees.core.security import EncryptionManager, sanitize_untrusted_input
from atrees.core.logging import get_logger, log_sync_start, log_sync_complete, log_sync_error
from atrees.config import get_settings


class TelegramMTProtoConnector(BaseConnector):
    """Telegram MTProto connector for monitoring channels and chats."""

    CONNECTOR_TYPE = "telegram_mtproto"
    DISPLAY_NAME = "Telegram (MTProto)"
    DESCRIPTION = "Monitor Telegram channels/groups using user account via Telethon"
    SUPPORTS_INCREMENTAL = True
    SUPPORTS_REALTIME = True
    REQUIRES_USER_AUTH = True

    def __init__(self, config: ConnectorConfig, db_session):
        super().__init__(config, db_session)
        self.client: TelegramClient | None = None
        self._monitored_chats: dict[int, dict] = {}
        self._target_recipient = None
        self._job_queue: asyncio.Queue = asyncio.Queue()
        self._worker_task: asyncio.Task | None = None
        self._event_handler_registered = False
        self._http_session = None
        self._candidates: list[tuple[dict, str]] = []
        self._encryption = EncryptionManager()

    async def connect(self) -> bool:
        """Connect to Telegram using Telethon."""
        try:
            # Decrypt credentials
            api_id = self.config.config.get("api_id")
            api_hash_encrypted = self.config.config.get("api_hash")
            session_string_encrypted = self.config.config.get("session_string")

            if not api_id or not api_hash_encrypted:
                self.logger.error("missing_credentials", source_id=self.config.source_id)
                await self._update_source_status(ConnectorStatus.ERROR, "Missing API credentials")
                return False

            api_hash = self._encryption.decrypt(api_hash_encrypted)
            session_string = self._encryption.decrypt(session_string_encrypted) if session_string_encrypted else None

            # Create client
            session = StringSession(session_string) if session_string else f"atrees_session_{self.config.source_id}"
            self.client = TelegramClient(session, api_id, api_hash)

            await self.client.start()
            self.logger.info("telegram_connected", source_id=self.config.source_id)

            # Discover models for AI analysis
            await self._discover_ai_models()

            # Find monitored chats and target recipient
            await self._discover_chats()

            # Register event handler for real-time messages
            if not self._event_handler_registered:
                self._register_event_handler()

            # Start background worker
            self._worker_task = asyncio.create_task(self._worker_loop())

            self.status = ConnectorStatus.CONNECTED
            await self._update_source_status(ConnectorStatus.CONNECTED)
            return True

        except Exception as e:
            self.logger.error("telegram_connect_failed", error=str(e))
            await self._update_source_status(ConnectorStatus.ERROR, str(e))
            return False

    async def disconnect(self) -> bool:
        """Disconnect from Telegram."""
        try:
            if self._worker_task:
                self._worker_task.cancel()
                try:
                    await self._worker_task
                except asyncio.CancelledError:
                    pass

            if self.client:
                await self.client.disconnect()
                self.client = None

            if self._http_session:
                await self._http_session.close()
                self._http_session = None

            self.status = ConnectorStatus.DISCONNECTED
            await self._update_source_status(ConnectorStatus.DISCONNECTED)
            return True
        except Exception as e:
            self.logger.error("telegram_disconnect_failed", error=str(e))
            return False

    async def test_connection(self) -> tuple[bool, str]:
        """Test Telegram connection."""
        try:
            if not self.client or not self.client.is_connected():
                return False, "Not connected"
            me = await self.client.get_me()
            return True, f"Connected as @{me.username or me.id}"
        except Exception as e:
            return False, str(e)

    async def sync(self, incremental: bool = True) -> SyncResult:
        """Sync messages from monitored chats."""
        result = SyncResult(status=SyncStatus.SUCCESS)
        result.started_at = datetime.utcnow()

        log_sync_start(self.logger, self.config.name, self.CONNECTOR_TYPE, incremental)

        try:
            if not self.client or not self.client.is_connected():
                await self.connect()

            # Sync each monitored chat
            for chat_id, chat_info in self._monitored_chats.items():
                chat_result = await self._sync_chat(chat_id, chat_info, incremental)
                result.items_processed += chat_result.items_processed
                result.items_created += chat_result.items_created
                result.items_updated += chat_result.items_updated
                result.items_failed += chat_result.items_failed
                result.errors.extend(chat_result.errors)

            result.mark_completed()
            log_sync_complete(
                self.logger,
                self.config.name,
                self.CONNECTOR_TYPE,
                result.items_processed,
                result.items_created,
                result.items_updated,
                result.items_failed,
                int((result.completed_at - result.started_at).total_seconds() * 1000),
            )

        except Exception as e:
            result.status = SyncStatus.FAILED
            result.errors.append(str(e))
            result.mark_completed()
            log_sync_error(self.logger, self.config.name, self.CONNECTOR_TYPE, e, incremental)

        return result

    async def get_sync_status(self) -> dict[str, Any]:
        """Get current sync status."""
        return {
            "status": self.status.value,
            "monitored_chats": len(self._monitored_chats),
            "target_recipient": self._target_recipient,
            "queue_size": self._job_queue.qsize(),
            "candidates": len(self._candidates),
        }

    # --- Internal Methods ---

    async def _discover_ai_models(self) -> None:
        """Discover available AI models from configured providers."""
        import aiohttp
        settings = get_settings()

        self._candidates.clear()
        providers = []

        # Build provider list from settings
        if settings.ai.GROQ_API_KEY:
            providers.append({
                'name': 'groq',
                'base': 'https://api.groq.com/openai/v1',
                'key': settings.ai.GROQ_API_KEY.get_secret_value(),
                'model_env': 'GROQ_MODELS',
            })
        if settings.ai.CEREBRAS_API_KEY:
            providers.append({
                'name': 'cerebras',
                'base': 'https://api.cerebras.ai/v1',
                'key': settings.ai.CEREBRAS_API_KEY.get_secret_value(),
                'model_env': 'CEREBRAS_MODELS',
            })
        if settings.ai.OPENROUTER_API_KEY:
            providers.append({
                'name': 'openrouter',
                'base': 'https://openrouter.ai/api/v1',
                'key': settings.ai.OPENROUTER_API_KEY.get_secret_value(),
                'model_env': 'OPENROUTER_MODELS',
            })
        if settings.ai.GEMINI_API_KEY:
            providers.append({
                'name': 'gemini',
                'base': 'https://generativelanguage.googleapis.com/v1beta/openai',
                'key': settings.ai.GEMINI_API_KEY.get_secret_value(),
                'model_env': 'GEMINI_MODELS',
            })

        self._http_session = aiohttp.ClientSession()

        PREFER = ['gpt-oss-120b', '120b', '235b', '70b', 'qwen', 'gpt-oss', 'llama', 'gemma', 'flash']
        SKIP = ('whisper', 'guard', 'tts', 'embed', 'orpheus', 'image', 'audio', 'live', 'omni',
                'veo', 'imagen', 'robotics', 'vision', 'moderation', 'safeguard', 'distil')
        MODELS_PER_PROVIDER = 3

        def rank(model_id: str) -> int:
            low = model_id.lower()
            for i, k in enumerate(PREFER):
                if k in low:
                    return i
            return len(PREFER)

        for p in providers:
            forced = getattr(settings.ai, p['model_env'].lower(), '') or ''
            if forced:
                ids = [m.strip() for m in forced.split(',') if m.strip()]
            else:
                ids = []
                try:
                    async with self._http_session.get(
                        p['base'] + '/models',
                        headers={'Authorization': 'Bearer ' + p['key']},
                        timeout=aiohttp.ClientTimeout(total=30),
                    ) as r:
                        data = await r.json()
                    for m in data.get('data', []):
                        mid = (m.get('id') or '').replace('models/', '')
                        low = mid.lower()
                        if not mid or any(s in low for s in SKIP):
                            continue
                        if p['name'] == 'openrouter' and not mid.endswith(':free'):
                            continue
                        if p['name'] == 'gemini' and 'flash' not in low:
                            continue
                        if p['name'] == 'gemini' and any(w in low for w in ('preview', 'exp')):
                            continue
                        ids.append(mid)
                    ids.sort(key=rank)
                    ids = ids[:MODELS_PER_PROVIDER]
                except Exception as e:
                    self.logger.warning("model_discovery_failed", provider=p['name'], error=str(e))
            for mid in ids:
                self._candidates.append((p, mid))
            self.logger.info("provider_models", provider=p['name'], models=ids)

    async def _discover_chats(self) -> None:
        """Discover monitored chats and target recipient."""
        settings = get_settings()
        telegram_config = settings.telegram_mtproto

        self._monitored_chats.clear()
        target_name = telegram_config.TARGET_CONTACT_NAME.lower()
        keywords = [k.lower() for k in telegram_config.TARGET_KEYWORDS]
        excluded = [e.lower() for e in telegram_config.EXCLUDED_KEYWORDS]
        test_contacts = [t.lower() for t in telegram_config.TEST_CONTACTS]

        async for dialog in self.client.iter_dialogs():
            entity = dialog.entity
            name = dialog.name or ""

            # Check for target contact
            if target_name in name.lower():
                self._target_recipient = entity
                self.logger.info("target_contact_found", name=dialog.name)

            # Check test contacts
            elif isinstance(entity, User) and any(t in name.lower() for t in test_contacts):
                self._monitored_chats[entity.id] = {
                    "name": name,
                    "type": "test_contact",
                    "entity": entity,
                }
                self.logger.info("monitoring_test_contact", name=name)

            # Check channels/groups for keywords
            elif isinstance(entity, (Channel, Chat)):
                name_lower = name.lower()
                if any(k in name_lower for k in keywords) and not any(e in name_lower for e in excluded):
                    self._monitored_chats[entity.id] = {
                        "name": name,
                        "type": "channel" if isinstance(entity, Channel) else "group",
                        "entity": entity,
                    }
                    self.logger.info("monitoring_chat", name=name, type=type(entity).__name__)

        # Add Saved Messages for testing
        if telegram_config.TEST_SAVED_MESSAGES:
            me = await self.client.get_me()
            self._monitored_chats[me.id] = {
                "name": "Saved Messages",
                "type": "saved_messages",
                "entity": me,
            }
            self.logger.info("monitoring_saved_messages")

    def _register_event_handler(self) -> None:
        """Register real-time message handler."""
        if not self.client:
            return

        @self.client.on(events.NewMessage(chats=list(self._monitored_chats.keys())))
        async def handler(event):
            text = event.raw_text
            if not text or len(text) < 20:
                return

            self.logger.debug("new_message_received", chat_id=event.chat_id, length=len(text))
            await self._job_queue.put((event, text, 0))

        self._event_handler_registered = True

    async def _worker_loop(self) -> None:
        """Background worker to process queued messages."""
        WORKER_COOLDOWN = 2
        MAX_QUEUE_TRIES = 5
        REQUEUE_DELAY = 90

        while True:
            try:
                event, text, tries = await self._job_queue.get()
                try:
                    await self._process_message(event, text)
                except Exception as e:
                    self.logger.error("worker_process_failed", error=str(e), tries=tries)
                    if tries < MAX_QUEUE_TRIES:
                        await asyncio.sleep(REQUEUE_DELAY)
                        await self._job_queue.put((event, text, tries + 1))
                    else:
                        self.logger.error("worker_giving_up", text_preview=text[:50])
                finally:
                    self._job_queue.task_done()
                await asyncio.sleep(WORKER_COOLDOWN)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error("worker_loop_error", error=str(e))
                await asyncio.sleep(5)

    async def _process_message(self, event, text: str) -> None:
        """Process a message through AI analysis."""
        # Analyze with AI
        analysis = await self._analyze_with_ai(text)
        if not analysis:
            return

        if analysis.get("is_relevant"):
            # Send proposal to target recipient
            await self._send_proposal(event, analysis)
        else:
            self.logger.info("message_not_relevant", text_preview=text[:50])

    async def _analyze_with_ai(self, text: str) -> dict | None:
        """Analyze job text with AI providers."""
        if not self._candidates:
            return None

        # Prepare system prompt
        settings = get_settings()
        profile = self._load_profile()
        system_prompt = f"""أنت مساعد ذكي لمستقل مطور تطبيقات موبايل. دي بياناته:

{profile}

اقرأ الوظيفة اللي هتتبعتلك:
- لو مناسبة لمجال تطبيقات الموبايل والبرمجة اجعل is_relevant=true، واكتب بروبوزال احترافي باللهجة المصرية المهذبة،
  يوضح فهمك للمطلوب ويربطه بخبرتك ومشاريعك الحقيقية من البيانات اللي فوق فقط (متألفش خبرات مش موجودة).
- لو مش مناسبة اجعل is_relevant=false.

ردّ بـ JSON فقط، من غير أي شرح أو علامات markdown، بالمفاتيح دي بالظبط:
{{"is_relevant": true/false, "job_title": "...", "summary": "...", "proposal": "...", "suggested_price_and_duration": "..."}}"""

        # Try candidates with randomization
        order = self._candidates[:]
        if len(order) > 1:
            shift = random.randrange(min(len(order), 3))
            order = order[shift:] + order[:shift]

        for provider, model in order:
            try:
                result = await self._call_model(provider, model, system_prompt, text)
                self.logger.info("ai_analysis_ok", provider=provider['name'], model=model)
                return result
            except Exception as e:
                self.logger.warning("ai_analysis_failed", provider=provider['name'], model=model, error=str(e))
                await asyncio.sleep(1 + random.random())

        return None

    def _load_profile(self) -> str:
        """Load user profile from file or default."""
        import os
        profile_path = os.path.join(os.path.dirname(__file__), "../../../profile.txt")
        if os.path.exists(profile_path):
            with open(profile_path, encoding='utf-8') as f:
                return f.read().strip()
        return """الاسم: عبدالرحمن
التخصص: مطور تطبيقات موبايل (Flutter و Android Native Kotlin)
الخبرة: بناء تطبيقات كاملة بنمط MVVM و Clean Architecture
مشاريع: SafeRoute (تطبيق أمان وطوارئ)، Open Fashion (تطبيق متجر أزياء)
خبرة تقنية: Firebase, REST APIs, State Management, Material Design
الأسعار: حسب حجم المشروع، أبدأ من (اكتب سعرك)
مدة التسليم: حسب المشروع، مع تحديثات مستمرة لل客户"""

    async def _call_model(self, provider: dict, model: str, system_prompt: str, job_text: str) -> dict:
        """Call AI model API."""
        import aiohttp

        payload = {
            'model': model,
            'temperature': 0.7,
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': 'حلل الوظيفة التالية:\n' + job_text},
            ],
        }

        async with self._http_session.post(
            provider['base'] + '/chat/completions',
            headers={'Authorization': 'Bearer ' + provider['key'], 'Content-Type': 'application/json'},
            json=payload,
            timeout=aiohttp.ClientTimeout(total=60),
        ) as r:
            body = await r.text()
            if r.status != 200:
                raise RuntimeError(f'{r.status} {body[:150]}')
            data = json.loads(body)

        content = data['choices'][0]['message']['content']
        return self._extract_json(content)

    def _extract_json(self, text: str) -> dict | None:
        """Extract JSON from model response."""
        text = (text or '').strip()
        text = re.sub(r'^```(?:json)?|```$', '', text, flags=re.MULTILINE).strip()
        start, end = text.find('{'), text.rfind('}')
        if start == -1 or end == -1:
            return None
        try:
            return json.loads(text[start:end + 1])
        except Exception:
            return None

    async def _send_proposal(self, event, analysis: dict) -> None:
        """Send proposal to target recipient."""
        if not self._target_recipient or not self.client:
            return

        nl = '\n'
        bt = '```'
        msg = (
            f'🎯 **فرصة جديدة:** {analysis.get("job_title", "")}{nl}'
            f'📝 **الملخص:** {analysis.get("summary", "")}{nl}'
            f'💰 **الاقتراح:** {analysis.get("suggested_price_and_duration", "")}{nl}{nl}'
            f'📋 **البروبوزال (اضغط للنسخ):**{nl}'
            f'{bt}{nl}{analysis.get("proposal", "")}{nl}{bt}{nl}{nl}'
            f'🔗 **الروابط:**{nl}{self._extract_links(event)}'
        )

        await self.client.send_message(self._target_recipient, msg, link_preview=False)
        self.logger.info("proposal_sent", job_title=analysis.get("job_title"))

    def _extract_links(self, event) -> str:
        """Extract links from message."""
        links = []
        if event.message.entities:
            for ent in event.message.entities:
                if hasattr(ent, 'url') and ent.url:
                    links.append(ent.url)
        if event.message.reply_markup and hasattr(event.message.reply_markup, 'rows'):
            for row in event.message.reply_markup.rows:
                for btn in row.buttons:
                    if hasattr(btn, 'url') and btn.url:
                        links.append(btn.url)
        return '\n'.join(dict.fromkeys(links)) if links else 'الرابط داخل الرسالة'

    async def _sync_chat(self, chat_id: int, chat_info: dict, incremental: bool) -> SyncResult:
        """Sync messages from a specific chat."""
        result = SyncResult(status=SyncStatus.SUCCESS)

        try:
            # Get cursor for incremental sync
            cursor = None
            if incremental:
                cursor = await self._get_sync_cursor("message", str(chat_id))

            # Fetch messages
            entity = chat_info["entity"]
            min_id = int(cursor) if cursor else 0
            max_messages = get_settings().telegram_mtproto.MAX_MESSAGES_PER_SYNC

            async for message in self.client.iter_messages(entity, min_id=min_id, limit=max_messages):
                if not message.text or len(message.text) < 20:
                    continue

                # Store raw message
                await self._store_raw_message(message, chat_id)
                result.items_processed += 1
                result.items_created += 1

                # Update cursor
                if message.id > min_id:
                    min_id = message.id

            # Save cursor
            if min_id > 0:
                await self._create_sync_state("message", str(chat_id), str(min_id), "completed")

        except Exception as e:
            result.status = SyncStatus.FAILED
            result.errors.append(f"Chat {chat_id}: {e}")

        return result

    async def _store_raw_message(self, message, chat_id: int) -> None:
        """Store message as raw item and normalized message."""
        from atrees.models.communication import Conversation, Message as MsgModel, Contact
        import hashlib

        # Create content hash for deduplication
        content_str = f"{chat_id}:{message.id}:{message.text or ''}"
        content_hash = hashlib.sha256(content_str.encode()).hexdigest()

        # Check if already exists
        from sqlalchemy import select
        stmt = select(RawItem).where(RawItem.content_hash == content_hash)
        existing = await self.db.execute(stmt)
        if existing.scalar_one_or_none():
            return  # Already stored

        # Get or create conversation
        conv_stmt = select(Conversation).where(
            Conversation.source_id == self.config.source_id,
            Conversation.source_conversation_id == str(chat_id),
        )
        conv_result = await self.db.execute(conv_stmt)
        conversation = conv_result.scalar_one_or_none()

        if not conversation:
            conversation = Conversation(
                source_id=self.config.source_id,
                source_conversation_id=str(chat_id),
                title=message.chat.title if hasattr(message.chat, 'title') else None,
                type="channel" if hasattr(message.chat, 'broadcast') and message.chat.broadcast else "group",
            )
            self.db.add(conversation)
            await self.db.flush()

        # Store raw item
        raw_item = RawItem(
            source_id=self.config.source_id,
            source_record_id=str(message.id),
            source_parent_id=str(chat_id),
            item_type="message",
            raw_content={
                "id": message.id,
                "text": message.text,
                "date": message.date.isoformat() if message.date else None,
                "sender_id": message.sender_id,
                "chat_id": chat_id,
            },
            content_hash=content_hash,
            source_timestamp=message.date or datetime.utcnow(),
            processing_status="completed",
        )
        self.db.add(raw_item)
        await self.db.flush()

        # Store normalized message
        sender = await message.get_sender()
        sender_name = None
        if sender:
            sender_name = getattr(sender, 'first_name', '') + ' ' + getattr(sender, 'last_name', '')
            sender_name = sender_name.strip() or getattr(sender, 'username', None)

            # Store contact
            contact_stmt = select(Contact).where(
                Contact.source_id == self.config.source_id,
                Contact.source_contact_id == str(sender.id),
            )
            contact_result = await self.db.execute(contact_stmt)
            contact = contact_result.scalar_one_or_none()

            if not contact:
                contact = Contact(
                    source_id=self.config.source_id,
                    source_contact_id=str(sender.id),
                    name=sender_name,
                    username=getattr(sender, 'username', None),
                    phone=getattr(sender, 'phone', None),
                )
                self.db.add(contact)

        msg = MsgModel(
            raw_item_id=raw_item.id,
            conversation_id=conversation.id,
            source_message_id=str(message.id),
            source_sender_id=str(message.sender_id) if message.sender_id else None,
            sender_name=sender_name,
            sender_role="user",
            content_text=message.text,
            message_timestamp=message.date or datetime.utcnow(),
        )
        self.db.add(msg)