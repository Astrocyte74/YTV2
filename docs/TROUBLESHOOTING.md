# Troubleshooting

## 500: list index out of range (psycopg2)
This usually means the number of `%s` placeholders in SQL didn’t match the number of parameters passed to `cursor.execute`. Fix by ensuring the WHERE builder appends placeholders and parameters together, and don’t mutate the same list for both count and main queries.

## 500 from percent signs in SQL
Psycopg2 treats `%` as a formatting marker. For literal patterns in LIKE/ILIKE, use `%%` (e.g., `LIKE '%%youtube.com%%'`) and for prefixes like `reddit:%` use `reddit:%%`.

## Filters appear but counts look wrong
Ensure `/api/filters` is returning real counts and the UI isn’t overwriting them. The current UI trusts server counts and only augments missing slugs.

## Nothing shows when clearing filters
By design, the UI requires at least one selection for some groups (e.g., category/source/channel). Clearing all shows a helpful empty-state card.

## 401 on /ingest/* endpoints
The ingest endpoints require `X-INGEST-TOKEN` and are separate from legacy Bearer auth. Verify:
- Render has `INGEST_TOKEN` set on the dashboard service
- NAS calls include header `X-INGEST-TOKEN: $INGEST_TOKEN`
- Check `/health/ingest` for `token_set: true`

## 500 during audio/image upload (Errno 28: No space left on device)
Uploads write to `/app/data/exports` on the attached Render disk. If the disk is full, uploads will 500 and may leave zero‑byte artifacts.

Fix:
- Increase disk size on the Render service (Disks → the volume mounted at `/app/data`). 2–10 GB is typical.
- Remove zero‑byte files under `/app/data/exports/audio` and `/app/data/exports/images`.
- Retry the upload. Handlers write via temp+rename and reject zero‑size writes. Response JSON includes `size`; also `HEAD` on the public URL should report non‑zero `Content-Length`.

Quick checks:
- `GET /health/ingest` → token + DB flags
- `HEAD /exports/audio/<file>.mp3` → 200 and non‑zero `Content-Length`

## Verify PostgreSQL connectivity
Quick check from your workstation:
```
psql "$DATABASE_URL_POSTGRES_NEW" -c "SELECT 1;"
```
If this fails, verify network egress and credentials (user, host, db, password). Add `connect_timeout=5` to DSN and retry with exponential backoff.
