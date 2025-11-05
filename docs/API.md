# YTV2 Dashboard API

This service exposes the JSON endpoints that power the dashboard UI.

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
- `summary_image_url` (optional): model‑generated illustration under `/exports/images/...`
- `media`: `{ has_audio: boolean, audio_url?: string, summary_image_url?: string, ... }`
- `media_metadata`: `{ mp3_duration_seconds?: number, video_duration_seconds?: number }`

Audio enrichment
- For any `summary_variants` entry with kind `audio` (or variant starting with `audio`), the API injects:
  - `audio_url` (server‑returned public path such as `/exports/audio/<file>.mp3`)
  - `duration` (integer seconds)
  These come from the authoritative `content.media` / `content.media_metadata` fields.

## Empty states and guard rails
The UI may require at least one selection in certain groups (e.g., category, source, channel). When none are selected the client intentionally shows an empty state and does not call `/api/reports`.

## GET /api/metrics
When `NGROK_BASE_URL` (or `NGROK_URL`) is configured, the dashboard exposes `/api/metrics` as a same‑origin proxy to the NAS metrics endpoint. This avoids browser CORS restrictions when the NAS is exposed via ngrok. Returns 404 when NAS bridging is not configured.

## NAS ingest (private)
For NAS → Dashboard syncing, use the private ingest endpoints with `X-INGEST-TOKEN`:
- `POST /ingest/report` – content upsert
- `POST /ingest/audio` – MP3 upload and `has_audio` update

Details and curl examples: see `docs/NAS_INTEGRATION.md`.

## GET /<video_id>.json (single report)
Returns a single item payload matching the list format, plus `deployment_commit` for deploy verification. The server computes `has_audio` as true if the content row is flagged, if a media `audio_url` is present, or if any audio variant exists.

Notes
- Static files under `/exports/...` support both `GET` and `HEAD`, and tolerate cache‑busting query params (e.g., `?v=1762174657`).

## Admin-only (debug)

These endpoints are gated by `DEBUG_TOKEN`. Call with either `Authorization: Bearer <DEBUG_TOKEN>` or `X-Debug-Token: <DEBUG_TOKEN>`.

- `GET /api/debug/content?video_id=<id>` — raw row preview for ops; JSON-serializes datetimes safely.
- `GET /api/health/storage` — returns disk totals/used/free, `used_pct`, and small samples of zero‑byte and recent files under `/app/data/exports`. Returns HTTP 503 when `used_pct` ≥ 98 to allow alerting.
