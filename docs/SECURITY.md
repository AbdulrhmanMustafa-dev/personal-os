# ATREES Security Architecture

**Reviewed:** 2026-11-07  
**Default deployment:** single-user, local-only service on `127.0.0.1`.

## Security boundary and current guarantees

ATREES handles messages, schedules, contacts, personal knowledge, account sessions and provider credentials. Treat the entire database and `storage/` directory as sensitive.

The review package implements these HTTP controls:

- `/api/*` routes require `X-ATREES-API-Key`, except the liveness endpoint `/api/health`.
- API key comparison uses `hmac.compare_digest`.
- `/webhook/telegram` requires `TELEGRAM_BOT_WEBHOOK_SECRET` and validates Telegram's `X-Telegram-Bot-Api-Secret-Token` header.
- CORS credentials are disabled and allowed headers are explicit.
- Default bind address remains `127.0.0.1`.
- Unhandled exception responses do not return stack traces or raw exception text.

This is not multi-user authentication, a role system, or a hardened internet-facing deployment. Do not port-forward this service or bind it to `0.0.0.0` without a separate threat review, TLS, rate limiting, stronger session authentication and an authorization model.

## Secrets and encryption

Required settings:

- `ENCRYPTION_KEY`: independent random 32-byte value encoded as base64. It encrypts connector secrets stored in supported encrypted fields.
- `API_KEY`: independent random 32-byte value encoded as base64. It authenticates private HTTP API requests.

Generate each separately:

```bash
python - <<'PY'
import base64, secrets
print(base64.b64encode(secrets.token_bytes(32)).decode())
PY
```

The current `EncryptionManager` uses Fernet authenticated encryption. Fernet uses AES-128-CBC plus HMAC-SHA256; it is **not AES-256-GCM**. The code base64-decodes the configured 32-byte key and then creates a Fernet key. Keep the master key outside the database and backups. Losing it can make encrypted connector credentials unrecoverable.

The encryption helper is not equivalent to full-database encryption. SQLite records and message bodies may remain readable at rest. Use encrypted disk/home storage and encrypted backups. Do not assume every JSON config value is encrypted: inspect connector save/load paths and test every secret-bearing field.

`EncryptionManager.rotate_key()` is explicitly unimplemented. Do not rotate `ENCRYPTION_KEY` until a tested migration exists that decrypts and re-encrypts every affected field with rollback and backup support.

## Credential handling

- Never commit `.env`, Telegram session files, OAuth refresh tokens, bot tokens, provider keys, or real message exports.
- Set `.env` permissions to `0600`; restrict `data/`, `backups/`, `logs/` and session directories to the local user.
- Do not put secrets in command-line arguments, shell history, issue reports, screenshots, or logs.
- Use separate credentials for Telegram MTProto, Telegram Bot API, Google OAuth and each cloud AI provider.
- Revoke credentials at the provider if exposed; then update local configuration and restart the service.

## External data and AI safety

Messages, files, emails, websites and imported AI transcripts are untrusted data, not instructions. The existing `sanitize_untrusted_input` is only a basic heuristic filter; it does not reliably stop prompt injection. Future AI workflows must:

1. Preserve source IDs and provenance.
2. Clearly separate system instructions from retrieved content.
3. Never allow retrieved text to authorize tools, reveal secrets, or change permissions.
4. Use structured outputs with validation and confidence/provenance fields.
5. Require explicit approval for sending messages, publishing, deleting, spending money, or changing external calendar records.
6. Avoid sending private content to cloud AI unless cloud processing is explicitly enabled and the user has approved the data scope.

## Backups and recovery

- Back up the SQLite database before schema changes and before importing large archives.
- Use SQLite's backup API or a consistent snapshot; do not copy a live WAL database as a single file without handling its WAL state.
- Encrypt backups before storing or syncing them outside the machine.
- Test restore into a separate directory before relying on a backup.
- The CLI backup/restore commands in the original code contain placeholders; use the scripts only after verifying their current implementation and tests.

## Required hardening before remote or unattended production use

- Complete tests for API auth, webhook auth, connector lifecycle, secret encryption and backup/restore.
- Replace in-process loops with a durable job queue/scheduler with idempotency and retry state.
- Add request size limits, rate limiting and security event auditing.
- Add explicit user approval records for all external write actions.
- Implement tested key rotation and field-level encryption coverage.
- Pin/scan dependencies and run vulnerability checks.
- Implement secure OAuth token storage, refresh, revocation and minimal scopes.
- Define data export/deletion and retention policies.
