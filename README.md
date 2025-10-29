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

# Required for NAS ingest (private endpoints)
INGEST_TOKEN=shared_ingest_token

# Optional (protect upload endpoints if used)
SYNC_SECRET=shared_secret

# Optional (NAS metrics bridge; enables /api/metrics proxy)
NGROK_BASE_URL=https://<your-ngrok-subdomain>.ngrok-free.app
# Or NGROK_URL can be used equivalently
NGROK_BASIC_USER=optional_basic_user
NGROK_BASIC_PASS=optional_basic_pass

# Optional locally (Render sets the port)
PORT=10000
```

## Run locally
```
pip install -r requirements.txt
python server.py
# open http://localhost:10000
```

## Deploy on Render
Use Docker runtime with Start Command `python server.py` and set `DATABASE_URL_POSTGRES_NEW`.

Step‑by‑step guide: `docs/DEPLOY_RENDER.md`.
NAS integration guide: `docs/NAS_INTEGRATION.md`.

## Filter model (UI summary)
- Source, Category and Channel all participate in narrowing results.
- The UI may require at least one selection (e.g., category/source/channel). Clearing those shows an empty state by design.
- Backend filtering is implemented in `modules/postgres_content_index.py` and mirrors the UI chip logic.

## Project structure (selected)
```
YTV2-Dashboard/
├─ server.py                        # HTTP server (dashboard + API)
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

## UI Feature Flags
- File: `ui_flags.js` (root). This is loaded by the HTML template and is the authoritative source for runtime flags.
- Common flags:
  - `cardV4`: enable Stream (List) and Mosaic (Grid) card renderers.
  - `cardExpandInline`: inline expand for card summaries.
  - `twRevamp`: experimental Tailwind‑first cards (V5) for List/Grid.
- After changing flags, if you don’t see the effect, bump the script cache in `dashboard_v3_template.html` (e.g., `ui_flags.js?v=2`).

## Card Styling and Cache Busting
- Structure/HTML: `static/dashboard_v3.js` (renderers)
  - V4: `renderStreamCardV4()` and `renderGridCardV4()`
- Styling: `static/dashboard.css`
  - V4 classes: `.stream-card*` and `.mosaic-card*`
- Cache bust:
  - CSS: change `dashboard.css?v=...` in `dashboard_v3_template.html`
  - JS: change `dashboard_v3.js?v=...` in `dashboard_v3_template.html`
 - Detailed tips: see `docs/CARD_STYLING_GUIDE.md`

## New Contributor Quick Start
- Branch
  - Create a topic branch from `main` and point Render to it for preview.
- Turn on features (optional)
  - Edit `ui_flags.js` and set flags (e.g., `cardV4: true`). If flags don’t apply after deploy, bump the query param in the template (e.g., `ui_flags.js?v=2`).
- Change cards
  - List view: edit `static/dashboard_v3.js` → `renderStreamCardV4()`
  - Grid view: edit `static/dashboard_v3.js` → `renderGridCardV4()`
  - Keep structure/HTML in JS; keep visual styles in `static/dashboard.css` (`.stream-card*`, `.mosaic-card*`).
- Style
  - Add/adjust CSS in `static/dashboard.css`. Prefer extending the existing V4 classes rather than inline styles.
- Cache‑bust
  - Update `dashboard_v3_template.html` to bump `dashboard.css?v=...` and/or `dashboard_v3.js?v=...` so browsers pick up changes.
- Deploy and verify
  - Commit + push; wait for Render to deploy.
  - Hard‑refresh in the browser. If needed, open DevTools → Network → “Disable cache” and refresh once.
- Sanity checklist
  - Filters list and cards render; pagination and sort work.
  - List (Stream) and Grid (Mosaic) views switch correctly.
  - Play/Pause, progress scrub, and expand/collapse work.
  - Keyboard basics: `L` (listen), `R` (read), `W` (watch) if present; arrow/tab navigation.
- Troubleshooting
  - Still seeing old UI? Confirm the `?v=` query params changed in `dashboard_v3_template.html` and the Render deploy completed.
  - Feature flags not applying? Confirm you edited root `ui_flags.js` (not `static/ui_flags.js`).
