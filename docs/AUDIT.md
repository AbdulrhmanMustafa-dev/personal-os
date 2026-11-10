# ATREES Existing Repository Audit

**Reviewed:** 2026-11-07  
**Input:** user-uploaded `Archive.zip`  
**Scope:** archive contents only; no access to the user's live workstation, running services, Git history, or third-party accounts.

## Executive summary

The archive is already a substantial Python backend foundation. It is not the earlier single-file `atrees_bot.py` snapshot described by the previous audit document. It contains a `src/atrees` package, FastAPI routes, SQLAlchemy models, an initial Alembic migration, two Telegram connectors, service classes, documentation, a SQLite database, and a `uv.lock` file.

However, the repository is **not yet a complete or verified Phase 1 release**. The frontend and tests directories were empty in the uploaded archive; README and `.env.example` were missing; API key settings existed but were not enforced; background worker functions contained undefined names; and the supplied database had no Alembic revision marker.

## Repository inventory

| Area | Observed state |
|---|---|
| Python packaging | `pyproject.toml`, `uv.lock`, src-layout package, CLI entry points |
| API | FastAPI app and routes for health, sources, connectors, tasks, dashboard and notifications |
| Database | SQLAlchemy 2 models, SQLite async URL, initial Alembic migration, supplied SQLite file |
| Domain models | Sources/sync, raw items, conversations/messages/contacts, tasks/projects, events/reminders, knowledge/evidence, skills/goals, research, notifications/jobs/audit, preferences |
| Connectors | Telegram MTProto (Telethon) and Telegram Bot API |
| Services | Sync, task planning, notifications |
| Frontend | Empty directory; no React/Vite application found |
| Tests | Empty directory in original archive; no tests were present |
| Documentation | Audit, migration, schema, connector, configuration and security documents |
| Runtime data | SQLite database included; logs/backups directories were empty |

The archive also contains `__pycache__` bytecode files. These are generated artifacts and should not be versioned.

## Confirmed findings

### Strengths

1. The project uses a modular package layout and separates API, models, connectors, services and core utilities.
2. SQLAlchemy models cover most of the intended personal operating system domain.
3. The initial migration includes FTS5 tables and triggers for messages, knowledge facts and tasks.
4. Telegram MTProto and Bot API are separate connectors, which is the correct architectural distinction.
5. The SQLite database passed `PRAGMA integrity_check` (`ok`) when inspected read-only.
6. Configuration uses Pydantic Settings and `SecretStr` for important credential fields.
7. A Fernet-based encryption helper and untrusted-input filtering utility exist.

### Defects / incomplete work found

| Severity | Finding | Impact |
|---|---|---|
| Critical | `API_KEY` was validated in settings but no API route or middleware enforced it | Local API routes were unauthenticated |
| Critical | `_background_sync_loop` and `_background_notification_loop` referenced `get_session` without importing it into their scope | Background workers fail when their loop reaches the database code |
| Critical | `_background_notification_loop` referenced `settings` without defining it | Notification worker fails at runtime |
| High | Background tasks were created without retained task handles or shutdown cancellation | Shutdown can leave pending tasks and database operations |
| High | Webhook endpoint accepted updates without validating Telegram's configured secret-token header | Forged webhook requests were not rejected at the HTTP boundary |
| High | No tests were present | No automated regression evidence |
| High | `frontend/` was empty | No usable dashboard UI exists |
| High | SQLite file has domain tables but no `alembic_version` table | Migration state is unknown; blindly running the initial migration risks table conflicts |
| Medium | `README.md` referenced by `pyproject.toml` was absent | Packaging/documentation entry point incomplete |
| Medium | `.env.example` was absent | Setup required reconstructing configuration from docs/code |
| Medium | CLI `create_admin`, `sync`, `backup`, and `restore` commands contain placeholders or unimplemented behavior | CLI output can imply capabilities that do not exist |
| Medium | AI task extraction explicitly logs a placeholder; weekly review method is a TODO | Message-to-task intelligence and weekly review are not implemented |
| Medium | Connector registry only registers the two Telegram connectors | Google, WhatsApp, AI-chat import and social integrations are not available connectors |
| Medium | API exception logging and some connector paths may include exception text | Must continue auditing for credential/PII leakage before production |

## Database inspection

- Database file: `data/atrees.db` (approximately 725 KB in the archive).
- Read-only SQLite integrity check: passed.
- The database contains the domain tables expected by the existing schema/migration.
- No `alembic_version` table was found.
- Personal records were not queried, printed, or summarized.

**Migration warning:** before running `alembic upgrade head` on this database, compare the live schema against `alembic/versions/001_initial.py`. If and only if the schema matches that revision, stamp the database at that revision. Otherwise create a reviewed forward migration. Keep a verified backup before either operation.

## Current integration readiness

| Integration | Code in repository | Credentials / authorization | Verified connected? |
|---|---|---|---|
| Telegram MTProto | Connector implementation exists | `api_id`, `api_hash`, user-account login/session | No |
| Telegram Bot API | Connector implementation exists | Bot token from `@BotFather`; configure allowed/admin user IDs | No |
| Ollama | Settings and some provider code exist | Local Ollama service and model pull | No end-to-end verification |
| Groq / Cerebras / OpenRouter / Gemini | Provider settings and MTProto-side provider discovery/use | Provider API key for each enabled provider | No end-to-end verification |
| Google Calendar / Tasks / Gmail | Settings/docs only; no registered production connector or complete OAuth flow found | Google Cloud OAuth client and consent | No |
| WhatsApp personal export | Documentation/plan only | User exports chats manually | No importer found |
| ChatGPT / Gemini / Claude exports | Documentation/plan only | User downloads account export | No importer found |
| Instagram / Facebook / TikTok / X | Documentation/plan only | Official API app review/scopes where supported | No |
| ntfy | Settings and notification service path exist | Topic; auth if private topic | Not verified |

## Quality and readiness assessment

| Dimension | Assessment |
|---|---|
| Architecture | Good initial separation; some lifecycle coupling remains |
| Persistence | Models and initial migration exist; migration state must be reconciled |
| Security | Useful primitives exist, but enforcement was missing and needs continued hardening |
| Reliability | Background worker defects and no durable queue are significant gaps |
| Tests | No original tests; review package adds initial unit tests, not yet run in a fully provisioned environment |
| UI | Not implemented |
| AI/memory | Schema groundwork exists; import/extraction/retrieval workflows are incomplete |
| Integrations | Telegram code exists; external authentication and end-to-end behavior unverified |

## Recommendation

Do not rewrite the repository. Preserve the current domain model and connector separation. First repair application lifecycle and access control, establish a reproducible environment and test baseline, reconcile the database migration state, and then add integrations incrementally behind explicit authorization and approval gates.
