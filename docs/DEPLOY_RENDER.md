# Deploy on Render (Dashboard Only)

This service runs the dashboard UI + API using PostgreSQL.

## Service settings
- Environment: Docker
- Start Command: `python server.py`

## Environment variables
Set these on the Render service:

```
DATABASE_URL_POSTGRES_NEW=postgres://user:pass@host:5432/db

# Optional (upload protection)
SYNC_SECRET=shared_secret

# Optional (NAS metrics bridge; enables /api/metrics proxy)
NGROK_BASE_URL=https://<your-ngrok-subdomain>.ngrok-free.app
# Or NGROK_URL can be used equivalently
NGROK_BASIC_USER=optional_basic_user
NGROK_BASIC_PASS=optional_basic_pass

# Optional locally; Render sets the port
PORT=10000
```

## Notes
- Cold builds can take a while (container build + extract).
- Auto-deploy from Git works; use “Deploy latest commit” if Render misses a push.
- Check Logs → look for `Using PostgreSQL database` and `/health` OK.
