# Deploy on Render (Dashboard Only)

This service runs the dashboard UI + API using PostgreSQL.

## Service settings
- Environment: Docker
- Start Command: `python server.py`

## Environment variables
Set these on the Render service:

```
DATABASE_URL_POSTGRES_NEW=postgres://user:pass@host:5432/db

# Required for NAS ingest (private endpoints)
INGEST_TOKEN=shared_ingest_token

# Optional (upload protection)
SYNC_SECRET=shared_secret

# Optional (admin-only debug endpoints)
DEBUG_TOKEN=super_secret_debug_token

# Optional (NAS metrics bridge; enables /api/metrics proxy)
NGROK_BASE_URL=https://<your-ngrok-subdomain>.ngrok-free.app
# Or NGROK_URL can be used equivalently
NGROK_BASIC_USER=optional_basic_user
NGROK_BASIC_PASS=optional_basic_pass

# Optional locally; Render sets the port
PORT=10000
```

## Disks and storage

Uploads (audio/images) are written under `/app/data/exports` on the attached Render disk. Ensure adequate space:

- Attach a disk mounted at `/app/data` (Service → Disks). Start with 5–10 GB for comfort.
- Verify via `/api/config` (directories.exports shows `/app/data/exports`).
- When disk is full, upload endpoints will 500 and may create zero‑byte artifacts. Increase disk size or clean old files, then retry.

Admin health
- `GET /api/health/storage` (requires `DEBUG_TOKEN`) reports totals/used/free and flags zero‑byte files; returns 503 when critically full.

## Notes
- Cold builds can take a while (container build + extract).
- Auto-deploy from Git works; use “Deploy latest commit” if Render misses a push.
- Check Logs → look for `Using PostgreSQL database` and `/health` OK.

See `docs/NAS_INTEGRATION.md` for NAS sync details and examples.
