# ATREES — Personal Life OS

ATREES is a local-first personal knowledge and productivity system. The current codebase is an early backend foundation: SQLite/SQLAlchemy models, FastAPI routes, task and notification services, and Telegram Bot API / MTProto connector implementations.

> **Status:** Phase 1 is a foundation, not the finished Personal Life OS. The React frontend, AI conversation importers, WhatsApp importer, Google OAuth flows, evidence-backed research pipeline, and reliable production scheduler are not implemented yet.

## Requirements

- Python 3.11 or newer (Python 3.12 is the recommended baseline; test Python 3.13 against all pinned dependencies before using it in production).
- `uv` package manager.
- Arch Linux or another Linux distribution.
- Optional: Ollama for local AI; Telegram account/bot credentials only when enabling those connectors.

## Quick start (Arch Linux)

```bash
sudo pacman -S --needed python python-pip git
curl -LsSf https://astral.sh/uv/install.sh | sh
cd /path/to/ATREES
uv sync --extra dev
cp .env.example .env
```

Generate independent secrets and paste them into `.env`:

```bash
python - <<'PY'
import base64, secrets
print('ENCRYPTION_KEY=' + base64.b64encode(secrets.token_bytes(32)).decode())
print('API_KEY=' + base64.b64encode(secrets.token_bytes(32)).decode())
PY
```

Apply the versioned schema migrations, insert default preferences and run the API (fresh database):

```bash
uv run atrees-init
uv run atrees serve --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/api/health`. Private API endpoints require the `X-ATREES-API-Key` header. Keep `.env`, Telegram session files, OAuth tokens, and the SQLite database private.

## Development checks

```bash
uv run pytest
uv run python -m compileall -q src
uv run ruff check src tests
```

## Existing architecture

- `src/atrees/api`: FastAPI application and REST routes.
- `src/atrees/models`: SQLAlchemy domain models.
- `src/atrees/connectors`: Telegram Bot API and Telegram MTProto connectors.
- `src/atrees/services`: task planning, sync, and notification services.
- `src/atrees/core`: configuration, logging, errors, encryption, and security helpers.
- `alembic/`: initial schema migration.
- `docs/`: audit, schema, configuration, connectors, migration and security notes.

See [Phase 1 status](docs/PHASE1_STATUS.md), [configuration](docs/CONFIGURATION.md), and [security](docs/SECURITY.md).
# personal-os
