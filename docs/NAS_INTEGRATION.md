# Local Integration (PostgreSQL Ingest)

This describes how the backend syncs content, audio, and images to the dashboard. Both services run locally on i9 Mac in separate Docker containers.

> **Note:** This was previously NAS_INTEGRATION.md for Render deployment. The system now runs locally.

## Overview
- Database: PostgreSQL only (`DATABASE_URL_POSTGRES_NEW` on the dashboard)
- Ingest endpoints (private):
  - `POST /ingest/report` – upsert content and optional summary variants
  - `POST /ingest/audio` – upload MP3 and flip `has_audio=true`
  - Images use the modern upload endpoint (see below)
- Auth headers:
  - Primary: `X-INGEST-TOKEN: <token>`
  - Legacy compatibility (uploads only): `Authorization: Bearer <SYNC_SECRET>`
- Public read endpoints (unchanged): `/api/reports`, `/api/filters`

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                           i9 Mac                                │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Docker Containers                     │   │
│  │  ┌─────────────────┐  ┌─────────────────────────────┐   │   │
│  │  │ Backend Bot     │  │ Dashboard                   │   │   │
│  │  │ Port 6452/6453  │  │ Port 10000                  │   │   │
│  │  │ - Telegram Bot  │──│ - Web Interface             │   │   │
│  │  │ - /api/reprocess│  │ - BACKEND_API_URL ──────────┘   │   │
│  │  └────────┬────────┘  │   (points to 6452)              │   │
│  │           │           └──────────────────────────────────┘   │
│  │           │                          │                        │
│  │           └────────────┬─────────────┘                        │
│  │                        │                                      │
│  │              host.docker.internal                             │
│  └────────────────────────┼─────────────────────────────────────┘
│                           │                                      │
│  ┌────────────────────────┴────────────────────────────────────┐│
│  │              PostgreSQL (Homebrew)                          ││
│  │              Port 5432                                      ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

## Environment Variables

Dashboard (.env):
- `DATABASE_URL_POSTGRES_NEW` – PostgreSQL connection
- `INGEST_TOKEN` – for backend sync (private ingest)
- `SYNC_SECRET` – shared secret for uploads
- `BACKEND_API_URL=http://host.docker.internal:6452` – for regenerate proxy
- `DEBUG_TOKEN` – auth for regenerate endpoint

Backend (.env.nas):
- `DATABASE_URL=postgresql://ytv2:pass@host.docker.internal:5432/ytv2`
- `DASHBOARD_URL=http://marks-macbook-pro-2.tail9e123c.ts.net:10000`
- `SYNC_SECRET` – must match dashboard
- `REPROCESS_AUTH_TOKEN` – must match dashboard's `DEBUG_TOKEN`

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
- Public paths are under `/exports/audio/` (filenames can be canonical or timestamped; prefer the server‑returned `public_url` in the upload response)
- The API supports `HEAD` and cache‑busting query params (e.g., `?v=<audio_version>`)

Modern upload (alternate):
- `POST /api/upload-audio` – accepts either `Authorization: Bearer <SYNC_SECRET>` or `X-INGEST-TOKEN: <token>` and returns a JSON body including `public_url`, `relative_path`, and `size`.
  NAS should prefer the server‑returned path and verify `size > 0`.

### POST /api/upload-image
Uploads a summary image PNG and returns a `public_url` under `/exports/images/...`.

Headers:
- Either `Authorization: Bearer <SYNC_SECRET>` or `X-INGEST-TOKEN: <token>`
- multipart form: `image=@/path/file.png;type=image/png`

Storage and URLs:
- Files are stored under `/app/data/exports/images/`
- Public path: `/exports/images/<filename>.png`

## Health Checks
- `GET /health/ingest` → reports `{ status: "ok", token_set: true, pg_dsn_set: true }`
- `GET /api/reports?size=1` → sanity read check (no auth required)

## ID and Source Conventions
- Prefer `video_id` (e.g., 11‑char YouTube ID). No `yt:` prefix required.
- `id` is optional and ignored by ingest; the database keys by `video_id`.
- Source is inferred from `canonical_url`/identifiers; do not send `content_source`.

## Troubleshooting
- 401 Unauthorized: Missing or wrong `X-INGEST-TOKEN` (or `SYNC_SECRET` for legacy uploads).
- 500 upsert_failed: Check Render has `DATABASE_URL_POSTGRES_NEW` set; inspect logs for SQL details.
- Upload returns 500 or creates zero‑byte file: Check Render disk space. Increase the `/app/data` disk size, remove zero‑byte artifacts under `/app/data/exports`, and retry. Upload handlers write atomically (temp → rename) and reject zero‑size writes.
- Wrong path/404: Prefer the server‑returned `public_url`; both `GET` and `HEAD` should return 200 with non‑zero Content‑Length.

---

This NAS integration replaces legacy SQLite sync. Use the ingest endpoints with `X-INGEST-TOKEN` for content, and the modern upload endpoints for audio/images when convenient. Legacy Bearer uploads remain accepted for compatibility.
