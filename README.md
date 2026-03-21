# YTV2 Dashboard (PostgreSQL)

Web UI + API for browsing AI‑generated summaries (with audio). This service runs locally on i9 Mac (Docker) and reads from a PostgreSQL database.

> **See also:** [../ARCHITECTURE.md](../ARCHITECTURE.md) for full system architecture.

## Key endpoints
- `/` – dashboard UI
- `/api/filters` – facet counts (sources, categories, channels, languages, etc.)
- `/api/reports` – paginated cards with filtering, search and sorting
- `/api/reprocess` – regenerate summaries (proxied to backend)
- `/health` – health probe

Full API reference: `docs/API.md`.

## Environment
```
# Required - PostgreSQL connection
DATABASE_URL_POSTGRES_NEW=postgres://user:pass@host:5432/dbname

# Required for backend ingest (private endpoints)
INGEST_TOKEN=shared_ingest_token

# Required for sync with backend
SYNC_SECRET=shared_secret

# Backend connection for regenerate functionality
# Use port 6452 (telegram_bot HTTP server), NOT 6453 (FastAPI)
BACKEND_API_URL=http://host.docker.internal:6452

# Auth token for regenerate endpoint (must match backend's REPROCESS_AUTH_TOKEN)
DEBUG_TOKEN=your_shared_secret

# Optional (UI behaviour)
DASHBOARD_AUTOPLAY_ON_LOAD=1  # set to 0/false to keep audio idle until a user clicks

# Optional locally
PORT=10000
```

## Run locally
```
# Docker (recommended, production-like)
docker-compose up -d --build
# open http://localhost:10000

# Docker live-edit mode (bind mounts for code/templates/static)
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d dashboard

# Or native
pip install -r requirements.txt
python server.py
# open http://localhost:10000
```

## Docker modes
- `docker-compose.yml`
  - Production-safe default.
  - App code, templates, and static assets are baked into the image.
  - Use this on the Intel Mac for the real running dashboard.
- `docker-compose.dev.yml`
  - Development override for live editing.
  - Bind-mounts `static/`, `templates/`, `server.py`, and `modules/`.
  - Use only when you explicitly want a live-edit workflow.

Recommended commands:
```
# Production-like rebuild/recreate
docker-compose up -d --build --force-recreate dashboard

# Live-edit development
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d dashboard
```

## Access via Tailscale
The dashboard is accessible remotely via Tailscale:
- URL: `http://marks-macbook-pro-2.tail9e123c.ts.net:10000`

Integration guide: `docs/NAS_INTEGRATION.md`.

## Filter model (UI summary)
- Source, Category and Channel all participate in narrowing results.
- The UI may require at least one selection (e.g., category/source/channel). Clearing those shows an empty state by design.
- Backend filtering is implemented in `modules/postgres_content_index.py` and mirrors the UI chip logic.

## Project structure (selected)
```
YTV2-Dashboard/
├─ server.py                        # HTTP server (dashboard + API)
├─ docker-compose.yml               # Production-safe container definition
├─ docker-compose.dev.yml           # Live-edit bind-mount override
├─ modules/
│  ├─ postgres_content_index.py     # Postgres queries and mapping
├─ static/
│  ├─ dashboard_v3.js               # UI logic
│  └─ dashboard.css                 # Styles
│  
├─ ui_flags.js                      # Feature flags loaded by the template (authoritative)
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
- To keep the audio player idle until a user clicks, set `DASHBOARD_AUTOPLAY_ON_LOAD=0`.

## UI Feature Flags
- File: `ui_flags.js` (root). This is loaded by the HTML template and is the authoritative source for runtime flags.
- Common flags:
  - `cardV4`: enable Stream (List) and Mosaic (Grid) card renderers.
  - `cardExpandInline`: inline expand for card summaries.
  - `twRevamp`: experimental Tailwind‑first cards (V5) for List/Grid.
- Asset versions are generated server-side from file mtimes plus commit SHA. If you don’t see a change, recreate the container or verify you are actually running the dev override.

## Card Styling and Assets
- Structure/HTML: `static/dashboard_v3.js` (renderers)
  - V4: `renderStreamCardV4()` and `renderGridCardV4()`
- Styling: `static/dashboard.css`
  - V4 classes: `.stream-card*` and `.mosaic-card*`
- Asset versions are computed in `server.py`; do not hand-edit `?v=` query params in templates.
- Detailed tips: see `docs/CARD_STYLING_GUIDE.md`

## New Contributor Quick Start
- Branch
  - Create a topic branch from `main` and point Render to it for preview.
- Turn on features (optional)
  - Edit `ui_flags.js` and set flags (e.g., `cardV4: true`).
- Change cards
  - List view: edit `static/dashboard_v3.js` → `renderStreamCardV4()`
  - Grid view: edit `static/dashboard_v3.js` → `renderGridCardV4()`
  - Keep structure/HTML in JS; keep visual styles in `static/dashboard.css` (`.stream-card*`, `.mosaic-card*`).
- Style
  - Add/adjust CSS in `static/dashboard.css`. Prefer extending the existing V4 classes rather than inline styles.
- Deploy and verify
  - For Docker on the Intel Mac, rebuild/recreate the production container.
  - For local live-edit work, use the dev compose override.
  - For Render, commit + push; wait for deploy.
  - Hard‑refresh in the browser. If needed, open DevTools → Network → “Disable cache” and refresh once.
- Sanity checklist
  - Filters list and cards render; pagination and sort work.
  - List (Stream) and Grid (Mosaic) views switch correctly.
  - Play/Pause, progress scrub, and expand/collapse work.
  - Keyboard basics: `L` (listen), `R` (read), `W` (watch) if present; arrow/tab navigation.
- Troubleshooting
  - Still seeing old UI? Confirm you rebuilt/recreated the production container or that you are intentionally running the dev override.
  - Feature flags not applying? Confirm you edited root `ui_flags.js` (not `static/ui_flags.js`).
# Trigger redeploy for pyjwt
