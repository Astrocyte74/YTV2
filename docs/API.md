# YTV2 Dashboard API

This service exposes two public JSON endpoints that power the dashboard UI.

## GET /api/filters
Returns facet counts for building the filter sidebar.

Response fields (abbreviated):
- `source`: [{ value, label, count }]
- `categories`: [{ value, count, subcategories?: [{ value, count }] }]
- `channels`: [{ value, count }]
- `languages`: [{ value, count }]
- `summary_type`: [{ value, count }]
- `has_audio`: [{ value: true|false, count }]

Notes:
- Source labels currently include: youtube, reddit (future: wikipedia, lds, web).
- Category counts consider both `subcategories_json` and `analysis_json->'categories'`.

## GET /api/reports
Paginated list of cards with optional filtering and sorting.

Query parameters:
- `source`: single or repeated (e.g., `source=youtube&source=reddit`)
- `category`: one or more parent categories
- `subcategory` + `parentCategory`: sub-faceting within a category
- `channel`, `language`, `summary_type`
- `has_audio`: `true` or `false`
- `q`: free-text search (title + latest summary)
- `page` (default 1), `size` (default 12, max 50)
- `sort`: `newest` (default), `oldest`, `title_az`, `title_za`, `duration_desc`, `duration_asc`, `added_desc`, `video_newest`

Response:
```
{
  "reports": [ { id, title, channel_name, content_source, source_label, ... } ],
  "pagination": { page, size, total_count, total_pages, has_next, has_prev },
  "sort": "newest"
}
```

Item fields (selected):
- `content_source` (slug) and `source_label` (friendly)
- `analysis`: `{ category:[], categories:[{category, subcategories:[]}], language, ... }`
- `summary_html`, `summary_text`, `summary_variant`, `summary_variants`

## Empty states and guard rails
The UI may require at least one selection in certain groups (e.g., category, source, channel). When none are selected the client intentionally shows an empty state and does not call `/api/reports`.

## GET /api/metrics
When `NGROK_BASE_URL` (or `NGROK_URL`) is configured, the dashboard exposes `/api/metrics` as a same‑origin proxy to the NAS metrics endpoint. This avoids browser CORS restrictions when the NAS is exposed via ngrok. Returns 404 when NAS bridging is not configured.

## NAS ingest (private)
For NAS → Dashboard syncing, use the private ingest endpoints with `X-INGEST-TOKEN`:
- `POST /ingest/report` – content upsert
- `POST /ingest/audio` – MP3 upload and `has_audio` update

Details and curl examples: see `docs/NAS_INTEGRATION.md`.
