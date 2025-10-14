# YTV2 Dashboard (PostgreSQL)

Web UI + API for browsing AI‑generated summaries (with audio). This service runs on Render (Docker) and reads from a PostgreSQL database.

## Key endpoints
- `/` – dashboard UI
- `/api/filters` – facet counts (sources, categories, channels, languages, etc.)
- `/api/reports` – paginated cards with filtering, search and sorting
- `/health` – health probe

Full API reference: `docs/API.md`.

## Environment
```
# Required
DATABASE_URL_POSTGRES_NEW=postgres://user:pass@host:5432/dbname

# Optional (protect upload endpoints if used)
SYNC_SECRET=shared_secret

# Optional locally (Render sets the port)
PORT=10000
```

## Run locally
```
pip install -r requirements.txt
python telegram_bot.py
# open http://localhost:10000
```

## Deploy on Render
Use Docker runtime with Start Command `python telegram_bot.py` and set `DATABASE_URL_POSTGRES_NEW`.

Step‑by‑step guide: `docs/DEPLOY_RENDER.md`.

## Filter model (UI summary)
- Source, Category and Channel all participate in narrowing results.
- The UI may require at least one selection (e.g., category/source/channel). Clearing those shows an empty state by design.
- Backend filtering is implemented in `modules/postgres_content_index.py` and mirrors the UI chip logic.

## Project structure (selected)
```
YTV2-Dashboard/
├─ telegram_bot.py                  # HTTP server (dashboard + API)
├─ modules/
│  ├─ postgres_content_index.py     # Postgres queries and mapping
├─ static/
│  ├─ dashboard_v3.js               # UI logic
│  └─ dashboard.css                 # Styles
├─ docs/
│  ├─ API.md                        # API reference
│  ├─ DEPLOY_RENDER.md              # Render deployment
│  ├─ ARCHITECTURE.md               # Backend + UI integration
│  ├─ TROUBLESHOOTING.md            # Common fixes
│  └─ SMOKE_TESTS.md                # Quick filter tests
└─ archive/                         # Old plans and notes
```

## Notes
- The backend normalizes a `content_source` slug per item (e.g., `youtube`, `reddit`) and returns a user‑friendly `source_label`.
- If you see 500s, check `docs/TROUBLESHOOTING.md` for placeholder/percent issues and the logging guidance.
