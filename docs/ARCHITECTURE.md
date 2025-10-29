# Architecture (Dashboard)

The dashboard is a small HTTP server with a Postgres-backed content index and a static frontend.

## Components
- `server.py`: runs the HTTP server (routes, static files, API endpoints).
- `modules/postgres_content_index.py`: Postgres queries and mapping to the UI’s data model.
- `static/dashboard_v3.js`: filter UI, pagination, and rendering.
- `ui_flags.js`: runtime feature flags loaded by the template (authoritative).

## Source normalization
We infer a `content_source` slug (e.g., youtube, reddit) using a SQL CASE expression over canonical_url/video_id with safe fallbacks. The same slug is returned in API items as `content_source` and human label `source_label`.

## Filters
`/api/filters` aggregates facet counts; `/api/reports` accepts filters and returns paginated items. Category queries look into both `subcategories_json` and `analysis_json->'categories'`. Source filters use the normalized slug.

## Guard rails (UI)
The UI may intentionally require at least one selection in certain groups (category/source/channel). With nothing selected, the client shows an empty state and does not call `/api/reports`.

## Cards (V4 Stream/Mosaic)
- Runtime flag: set `cardV4: true` in `ui_flags.js` to enable.
- List view renderer: `renderStreamCardV4()` in `static/dashboard_v3.js`.
- Grid view renderer: `renderGridCardV4()` in `static/dashboard_v3.js`.
- Styling lives in `static/dashboard.css`:
  - Stream classes: `.stream-card`, `.stream-card__media`, `.stream-card__eq`, `.stream-card__progress`, `.stream-card__body`, etc.
  - Mosaic classes: `.mosaic-card`, `.mosaic-card__media`, `.mosaic-card__progress`, `.mosaic-card__body`, etc.
- When changing CSS/JS, bump the query params in `dashboard_v3_template.html`:
  - CSS: `dashboard.css?v=...`
  - JS: `dashboard_v3.js?v=...`
