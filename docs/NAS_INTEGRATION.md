# NAS Integration (PostgreSQL Ingest)

This describes how the NAS backend syncs content and audio to the Render‑hosted dashboard using the Postgres ingest endpoints. The legacy SQLite sync endpoints are removed.

## Overview
- Database: PostgreSQL only (`DATABASE_URL_POSTGRES_NEW` on the dashboard)
- Ingest endpoints (private):
  - `POST /ingest/report` – upsert content and optional summary variants
  - `POST /ingest/audio` – upload MP3 and flip `has_audio=true`
- Auth header: `X-INGEST-TOKEN: <token>`
- Public read endpoints (unchanged): `/api/reports`, `/api/filters`

## Environment Variables

Dashboard (Render):
- `DATABASE_URL_POSTGRES_NEW` – required
- `INGEST_TOKEN` – required for NAS sync (private ingest)
- Optional legacy: `SYNC_SECRET` (legacy upload endpoints only)

NAS (backend):
- `RENDER_DASHBOARD_URL=https://<your-render-app>.onrender.com`
- `INGEST_TOKEN=<same-as-Render>`
- Optional: `DASHBOARD_URL` for building “Open summary” links
- Optional: `DATABASE_URL_POSTGRES_NEW` if the NAS also writes directly to Postgres (not required for ingest)

## Endpoints

### POST /ingest/report
Upserts a content row by `video_id`. JSON fields can be objects or JSON strings.

Headers:
- `Content-Type: application/json`
- `X-INGEST-TOKEN: <token>`

Payload (example):
```
{
  "video_id": "n2Fluyr3lbc",
  "title": "Sample Title",
  "channel_name": "Channel",
  "canonical_url": "https://www.youtube.com/watch?v=n2Fluyr3lbc",
  "thumbnail_url": "https://img.youtube.com/vi/n2Fluyr3lbc/hqdefault.jpg",
  "duration_seconds": 1234,
  "indexed_at": "2025-10-25T16:12:34Z",
  "analysis_json": {"sentiment": "neutral"},
  "subcategories_json": {"categories": [{"category": "Education", "subcategories": ["Tutorials & Courses"]}]},
  "topics_json": ["AI", "Science"],
  "summary_variants": [
    { "variant": "comprehensive", "text": "…", "html": "<p>…</p>" }
  ]
}
```

Notes:
- Required field: `video_id`
- `summary_variants` are stored in `content_summaries` with latest-pointer management
- Content source is inferred (YouTube, Reddit, etc.) from `canonical_url`/ids

Example curl:
```
curl -sS -X POST "$RENDER_DASHBOARD_URL/ingest/report" \
  -H "Content-Type: application/json" \
  -H "X-INGEST-TOKEN: $INGEST_TOKEN" \
  -d '{
        "video_id":"n2Fluyr3lbc",
        "title":"Sample Title",
        "channel_name":"Channel",
        "canonical_url":"https://www.youtube.com/watch?v=n2Fluyr3lbc",
        "thumbnail_url":"https://img.youtube.com/vi/n2Fluyr3lbc/hqdefault.jpg",
        "duration_seconds":1234,
        "indexed_at":"2025-10-25T16:12:34Z",
        "analysis_json":{"sentiment":"neutral"},
        "subcategories_json":{"categories":[{"category":"Education","subcategories":["Tutorials & Courses"]}]},
        "topics_json":["AI","Science"],
        "summary_variants":[{"variant":"comprehensive","text":"...","html":"<p>...</p>"}]
      }'
```

### POST /ingest/audio
Uploads an MP3 and updates the content record to set `has_audio=true` and `analysis_json.audio_url`.

Headers:
- `X-INGEST-TOKEN: <token>`
- multipart form: `video_id=<id>`, `audio=@/path/file.mp3;type=audio/mpeg`

Example curl:
```
curl -sS -X POST "$RENDER_DASHBOARD_URL/ingest/audio" \
  -H "X-INGEST-TOKEN: $INGEST_TOKEN" \
  -F "video_id=n2Fluyr3lbc" \
  -F "audio=@/path/to/n2Fluyr3lbc.mp3;type=audio/mpeg"
```

Storage and URLs:
- Files are stored under `/app/data/exports/audio/`
- Public path: `/exports/audio/<video_id>.mp3`

## Health Checks
- `GET /health/ingest` → reports `{ status: "ok", token_set: true, pg_dsn_set: true }`
- `GET /api/reports?size=1` → sanity read check (no auth required)

## ID and Source Conventions
- Prefer `video_id` (e.g., 11‑char YouTube ID). No `yt:` prefix required.
- `id` is optional and ignored by ingest; the database keys by `video_id`.
- Source is inferred from `canonical_url`/identifiers; do not send `content_source`.

## Troubleshooting
- 401 Unauthorized: Missing or wrong `X-INGEST-TOKEN`.
- 500 upsert_failed: Check Render has `DATABASE_URL_POSTGRES_NEW` set; inspect logs for SQL details.
- Audio uploaded but not visible: Ensure you used `/ingest/audio` (not legacy `/api/upload-audio`).
- Wrong path/404: Verify public URL is `/exports/audio/<video_id>.mp3`.

---

This NAS integration replaces legacy SQLite sync. Use the ingest endpoints with `X-INGEST-TOKEN` for all new content and audio.

