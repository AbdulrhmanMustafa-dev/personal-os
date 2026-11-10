# ATREES Phase 1 — implementation status

Audit date: 2026-11-07. Reviewed from the uploaded `Archive.zip`; the local machine and live third-party accounts were not accessed.

## Implemented in this review package

- Added a project README and `.env.example` with no fabricated credentials.
- Added constant-time secret comparison helper and API key middleware. All `/api/*` endpoints except `/api/health` require `X-ATREES-API-Key`.
- Telegram webhook now requires a configured `TELEGRAM_BOT_WEBHOOK_SECRET` and the Telegram secret-token header.
- Reworked FastAPI lifespan to cancel and await background tasks before closing the database engine.
- Fixed undefined `get_session` / `settings` references in background loops.
- Background notification worker uses Cairo-configured timezone and only sends one daily briefing per local date.
- Notification worker suppresses repeated Telegram startup notifications when it reconnects.
- Health endpoint now returns a real UTC timestamp and does not expose raw database exception details.
- Added unit tests for secret generation/validation, encryption round-trip, untrusted input filtering, core model registration, and API key comparison.
- Added `connector_type` as a distinct source field, mapped broad `SourceType` categories correctly, updated source creation/connector lookup/Telegram notification lookup, and added Alembic revision `002_source_connector_type`.
- Added a persisted `enabled` flag and revision `003_source_enabled`; automatic sync now selects enabled disconnected sources instead of accidentally skipping newly configured sources.

## Validation results in the review environment

- `python -m compileall -q src`: passed before the final test additions; rerun after any local edits.
- Original `pytest -q`: collected zero tests (the archive contained an empty `tests/` directory).
- New tests were added, but could not be executed in this review environment because the archive dependencies are not installed (`structlog`, `telethon`, `python-telegram-bot`, `aiosqlite`, among others). `uv sync --offline --extra dev` also failed because required wheels were not cached and network access was unavailable. This is **not** a passing test result.

## Remaining Phase 1 work

1. Install dependencies with `uv sync --extra dev` and run the tests on the target Arch machine.
2. Add async SQLite integration tests and API lifecycle tests with a temporary database.
3. Resolve the database migration baseline: the supplied SQLite file is structurally valid and contains the domain tables, but it has no `alembic_version` table. Compare every column/index against `001_initial.py`, then stamp the verified revision; do not run `alembic upgrade head` blindly against this existing database.
4. Replace `Base.metadata.create_all()` startup behavior with an explicit migration-first production startup policy.
5. Add user-facing dashboard frontend (the supplied `frontend/` directory is empty).
6. Review the Telegram Bot connector lifecycle and MTProto login flow end-to-end with real test accounts; no accounts were authenticated in this review.
7. Add a durable scheduler/worker with job persistence, retry/backoff, idempotency and graceful recovery. Current loops are in-process and are not sufficient for reliable unattended automation.
8. Add API key provisioning in the frontend (or a local authenticated session) before exposing the dashboard.

## Important cautions

- The API key middleware protects HTTP API routes, but this is a single-user local application, not a multi-user identity system. Keep the server bound to `127.0.0.1`; do not expose it directly to the internet.
- Telegram MTProto session strings and bot tokens are credentials. Store them encrypted and never commit them.
- Existing `docs/AUDIT.md` had described an older single-file bot snapshot and is superseded by this audit of the uploaded repository.
