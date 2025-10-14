# Deploy on Render (Dashboard Only)

This service runs the dashboard UI + API using PostgreSQL.

## Service settings
- Environment: Docker
- Start Command: `python telegram_bot.py`

## Environment variables
Set these on the Render service:

```
DATABASE_URL_POSTGRES_NEW=postgres://user:pass@host:5432/db

# Optional (upload protection)
SYNC_SECRET=shared_secret

# Optional locally; Render sets the port
PORT=10000
```

## Notes
- Cold builds can take a while (container build + extract).
- Auto-deploy from Git works; use “Deploy latest commit” if Render misses a push.
- Check Logs → look for `Using PostgreSQL database` and `/health` OK.

