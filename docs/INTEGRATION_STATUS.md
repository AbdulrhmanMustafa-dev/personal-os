# ATREES Integration Readiness and Authorization

This table distinguishes code presence from a tested, authenticated connection. No credentials were created and no external account was connected during the repository review.

| Service | Current code status | What is required to authorize it | Remaining implementation / test |
|---|---|---|---|
| Telegram MTProto | Connector class exists (Telethon) | Create `api_id` and `api_hash` at `https://my.telegram.org`; authorize the user's own Telegram account with OTP/2FA; store the resulting session securely | Test login, encrypted session persistence, incremental sync, deduplication, reconnect and logout on the user's machine |
| Telegram Bot API | Connector class exists (`python-telegram-bot`) | Create a bot with `@BotFather`; provide `bot_token`; configure Telegram user IDs in allowlist/admin list. For webhooks, configure HTTPS callback URL and a random webhook secret | End-to-end webhook and outbound delivery tests; ensure bot source is created with `connector_type=telegram_bot`; no token is supplied in this repository |
| ntfy | HTTP delivery code exists | Set `NOTIFICATION_NTFY_ENABLED=true`, `NOTIFICATION_NTFY_TOPIC` and server URL. Use a private topic/auth only after auth headers are implemented | Verify delivery, private-topic auth, rate limits and retry behavior |
| Ollama | Configuration fields exist; no complete local provider adapter found | Install Ollama locally, start service, pull a model, set `AI_OLLAMA_BASE_URL` and `AI_LOCAL_MODEL` | Implement provider abstraction, health check, generation and embeddings; settings alone do not mean connected |
| Groq / Cerebras / OpenRouter / Gemini | API-key discovery/use code appears inside Telegram MTProto job-analysis path; no general-purpose provider layer | Create a provider key at the selected provider and set the matching `AI_*_API_KEY`; keep cloud processing disabled until explicitly wanted | Extract provider calls behind a shared AI interface; test timeouts, retries, model selection, privacy redaction and cost limits |
| Google Calendar | Settings and docs only; no complete connector/OAuth callback found | Create a Google Cloud project, enable Calendar API, configure OAuth consent screen, create Desktop/Web OAuth client and redirect URI; user grants minimum scopes | Implement OAuth state/PKCE, token encryption/refresh/revoke, sync cursors, event conflict handling and read/write approval workflow |
| Google Tasks | Settings and docs only | Same Google OAuth project; grant `tasks` scope | Implement connector, incremental sync, task mapping and approval before writes |
| Gmail | Settings/docs only | Same Google OAuth project; start with read-only `gmail.readonly` scope | Implement read-only connector, query controls, pagination and privacy filters; no sending capability should be enabled by default |
| WhatsApp personal | No importer in current code | Export chats using WhatsApp's built-in Export Chat feature; import TXT/ZIP locally | Build parser, media mapping, timestamp/locale handling, deduplication and opt-in retention controls. Do not scrape WhatsApp Web sessions |
| WhatsApp Business | No connector in current code | Meta Business account, WhatsApp Business Platform app, approved phone number, access token and webhook configuration | Implement official Cloud API only; API access is not equivalent to full personal-account history access |
| ChatGPT / Gemini / Claude history | No importers in current code | Download each provider's official account data export | Build independent importers, normalize messages/attachments, preserve conversation/source metadata and deduplicate |
| Instagram / Facebook / TikTok / X | No connectors in current code | Developer app, official API access, review/permissions/scopes where required | Implement only data permitted by each platform's current API. Use user exports for unavailable private history |

## Telegram configuration examples (placeholders only)

```dotenv
# MTProto user account
TELEGRAM_ENABLED=true
TELEGRAM_API_ID=YOUR_NUMERIC_API_ID
TELEGRAM_API_HASH=YOUR_API_HASH
TELEGRAM_SESSION_STRING=GENERATED_SESSION_STRING

# Bot API notifications
TELEGRAM_BOT_ENABLED=true
TELEGRAM_BOT_TOKEN=YOUR_BOTFATHER_TOKEN
TELEGRAM_BOT_ADMIN_USER_IDS=YOUR_TELEGRAM_NUMERIC_USER_ID
TELEGRAM_BOT_ALLOWED_USER_IDS=YOUR_TELEGRAM_NUMERIC_USER_ID
TELEGRAM_BOT_WEBHOOK_URL=https://YOUR_HTTPS_HOST/webhook/telegram
TELEGRAM_BOT_WEBHOOK_SECRET=GENERATE_A_LONG_RANDOM_SECRET
```

These are examples, not active credentials. Do not paste real values into chat or commit them. For local-only use, the bot can be used for outbound notifications without exposing a public webhook; inbound bot commands require a supported polling/webhook lifecycle, which must be tested before enabling.

## Google OAuth values to provide later

- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_REDIRECT_URI` (must exactly match the URI registered in Google Cloud)
- The scopes explicitly approved by the user: Calendar read/events, Tasks, and Gmail read-only as separate opt-ins.

The code currently has configuration placeholders but not a finished OAuth integration. Do not create or paste credentials until the connector and consent flow are implemented.
