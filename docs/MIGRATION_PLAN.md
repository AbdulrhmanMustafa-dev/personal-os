# ATREES Migration Plan — Existing Repository

**Reviewed:** 2026-11-07. This plan starts from the uploaded modular repository, not the older single-file bot snapshot.

## Principles

- Preserve existing Telegram functionality and domain data.
- Do not replace working code just to match a target folder tree.
- Do not run destructive migrations against the supplied SQLite file until its schema is reconciled.
- Build vertical slices that are testable and useful, not empty folders for every future feature.
- Treat integrations as disconnected until OAuth/login and an end-to-end test succeed.

## Current baseline

Already present: Python src-layout package, FastAPI routes, SQLAlchemy domain models, initial Alembic migration, SQLite database, Telegram Bot API and MTProto connectors, task/sync/notification services, CLI, docs, `uv.lock`.

Missing or incomplete: frontend, tests in original archive, README, `.env.example`, API authentication enforcement (added in review patch), correct background worker lifecycle (patched), complete migration baseline, durable scheduler, importers, Google OAuth implementation, evidence-backed research pipeline.

## Stage 0 — Protect and baseline (first)

1. Keep an untouched copy of `data/atrees.db` and the original archive.
2. Run `PRAGMA integrity_check` and schema comparison against `001_initial.py`.
3. Determine whether the existing database is exactly revision `001_initial`.
4. If exact, use `alembic stamp 001_initial` after backup. If not, create a forward migration that reconciles differences; do not stamp by assumption.
5. Create `.env` from `.env.example`, generate independent keys and set file permissions to `0600`.
6. Install locked dependencies and establish a passing test baseline on the target Arch machine.

## Stage 1 — Foundation (current milestone)

- Keep the current domain model and connector abstraction.
- Enforce API key auth and Telegram webhook secret validation.
- Make FastAPI worker lifecycle deterministic and cancel background tasks at shutdown.
- Fix undefined worker references and daily briefing timezone/deduplication.
- Add README, environment template, security notes and initial unit tests.
- Add temporary-database integration tests for CRUD and migration behavior.
- Choose one database initialization strategy: Alembic migrations for deployment; `create_all()` only for disposable tests/development. Avoid allowing startup `create_all()` to silently become the production migration mechanism.

**Exit criteria:** clean install, API starts on localhost, liveness works, private API rejects missing/wrong key, webhook rejects missing/wrong secret, database migrates on a clean file, tests pass, graceful shutdown closes workers and DB engine.

## Stage 2 — Memory ingestion

- Add importers for ChatGPT export, Google Takeout/Gemini and Claude export.
- Add WhatsApp official TXT/ZIP export importer; preserve timestamps, participants, attachments and source metadata.
- Store raw immutable records and normalized conversations/messages separately.
- Make import idempotent using source IDs and content hashes.
- Add extraction pipeline with fact categories, source evidence, confidence, verification state and correction history.
- Add FTS5 search first; add embeddings only after retrieval quality can be evaluated.

## Stage 3 — Personal management

- Complete task lifecycle, approvals, project relations and 1-3-5 daily planning.
- Add conflict-aware calendar sync and event preparation records.
- Add reminder engine with timezone-aware recurrence, deduplication and delivery logs.
- Add Google Calendar and Tasks OAuth connectors using minimal scopes.
- Start Gmail read-only only after OAuth storage and consent UX are tested.

## Stage 4 — Communication and notifications

- Test Telegram MTProto authorization, sync cursor persistence, deduplication, disconnect/reconnect and session encryption.
- Test Bot API commands, allowlists, webhook signature and delivery retries.
- Add explicit approval before any outgoing message.
- Add ntfy as an optional notification channel after testing private topic authentication.

## Stage 5 — Research and social data

- Implement source capture with URL, publisher, publication date, retrieval date, evidence excerpt and claim-level verification.
- Prioritize official and primary sources; store contradictions and stale status.
- Add social platform integrations only where official APIs and granted permissions permit the requested data.
- Provide export/import fallback where private account data is not available through APIs.

## Stage 6 — Local intelligence and autonomy

- Add local model provider abstraction and explicit opt-in cloud provider policy.
- Evaluate extraction and planning accuracy against curated examples before enabling automatic actions.
- Add durable job queue, persistent retries, idempotency keys, health metrics and audit log.
- Keep external writes approval-gated; allow autonomous read/summarize/recommend only within configured source permissions.

## Recommended package organization

Do not move all existing files immediately. Introduce the following modules incrementally while retaining stable imports:

```text
src/atrees/
  api/                 # existing FastAPI app, routes, schemas
  core/                # config, auth, logging, security, exceptions
  database.py          # engine/session; migration-managed schema
  models/               # existing domain models
  connectors/
    telegram_mtproto/   # existing
    telegram_bot/       # existing
    imports/            # future WhatsApp and AI export importers
    google/             # future Calendar, Tasks, Gmail OAuth connectors
    social/             # future official API connectors
  services/             # existing task/sync/notification services
  intelligence/
    extraction/         # future evidence-aware extraction
    memory/             # future retrieval and correction pipeline
    research/           # future research/evidence workflows
    planner/            # future 1-3-5 planner
  workers/              # future durable scheduler/worker process
  scripts/              # existing CLI scripts
frontend/               # future React/Vite PWA; currently empty
alembic/                # existing migrations
 tests/                  # unit + integration; review adds initial unit tests
 docs/
```

## Rollback

Before each migration: stop ATREES, create a verified backup, record current Alembic revision, apply migration to a copy, run tests, then migrate the live DB. Rollback means restoring the verified backup unless a reviewed downgrade has been tested; do not assume Alembic downgrade restores imported data or external account state.
