# Multi‑User Auth Rollout — Backend Status (YTV2)

Owner: Backend Codex (this repo)
Branch: `quizzernator_multi_user`

## Summary
- Implemented Google OIDC verification and user‑scoped quiz endpoints per plan.
- Added CORS allowlist via env, health endpoints, rate limits, and payload limits.
- Requirements and templates updated; branch pushed and ready for deploy.

## Completed (Backend)
- [x] Add Google auth lib: `google-auth` in `requirements.txt`.
- [x] Env support: `GOOGLE_CLIENT_IDS` (CSV), `ALLOWED_ORIGINS` (CSV; no trailing slash).
- [x] Token verification helper (`verify_google_bearer`):
  - Strict `aud` against any in `GOOGLE_CLIENT_IDS`.
  - Strict `iss` in `{accounts.google.com, https://accounts.google.com}`.
  - Short in‑memory cache; never logs tokens.
- [x] CORS
  - Honors `ALLOWED_ORIGINS`; includes `DELETE`; sends `Vary: Origin`.
  - Defaults are permissive to avoid breaking legacy flows.
- [x] Endpoints (protected)
  - `POST /api/my/save-quiz` (409 unless `{ overwrite: true }`).
  - `GET /api/my/list-quizzes` (ISO 8601 timestamps).
  - `GET /api/my/quiz/:filename`.
  - `DELETE /api/my/quiz/:filename`.
- [x] Health endpoints
  - `GET /api/health` (public JSON).
  - `GET /api/health/auth` (requires valid token).
- [x] Namespaced filesystem storage
  - `data/quiz/<user_id>/*.json` with filename sanitization.
  - Cross‑tenant attempts return 404 (no enumeration).
- [x] Limits
  - Per‑IP RL on `POST /api/generate-quiz` and `POST /api/categorize-quiz`.
  - Per‑user per‑minute and per‑day RL on `POST /api/my/save-quiz` (IP fallback too).
  - `MAX_QUIZ_KB` (default 128) → HTTP 413 on exceed.
- [x] Templates/config
  - `.env.template` updated with multi‑user vars and RL defaults.
  - `render.yaml` includes placeholders for `GOOGLE_CLIENT_IDS`, `ALLOWED_ORIGINS`.

## Pending / To Verify
- [ ] Deploy this branch to Render (service may still track `main`).
- [ ] Frontend obtain GIS ID token and run smoke tests:
  - `GET /api/health/auth` → 401 → 200 with token.
  - `GET /api/my/list-quizzes` → 200 (likely empty initially).
  - `POST /api/my/save-quiz` → 200; repeat without `overwrite` should 409; with `overwrite: true` should 200.
  - `GET /api/my/quiz/:filename` → 200; `DELETE` → 200.
- [ ] Confirm 429 behavior on `generate-quiz`/`categorize-quiz` under per‑IP limits.
- [ ] Optional: Add info‑level logging of `user_id` on `/api/my/*` hits (no email; never tokens).

## Environment (Staging)
- GOOGLE_CLIENT_IDS: `804684000712-adcj015736vosioefknv5jdkonh1mi6k.apps.googleusercontent.com`
- ALLOWED_ORIGINS: `https://quizzernator.onrender.com`
- Note: Parser tolerates wrapping quotes in env CSVs.

## Notes
- Response shapes for `/api/my/*` use ISO 8601 `created` fields; public endpoints are unchanged for Phase 1.
- Per‑instance caches/rate limits are acceptable for MVP.
- Telegram linking: out of scope for Phase 1.

## Quick Curls (replace BACKEND_URL and ID_TOKEN)
```
# Health (public)
curl -sS https://BACKEND_URL/api/health

# Health (auth)
curl -sS -H "Authorization: Bearer ID_TOKEN" https://BACKEND_URL/api/health/auth

# My list
curl -sS -H "Authorization: Bearer ID_TOKEN" https://BACKEND_URL/api/my/list-quizzes

# Save (409 on duplicate unless overwrite)
curl -sS -X POST -H "Content-Type: application/json" -H "Authorization: Bearer ID_TOKEN" \
  -d '{"filename":"hello_quiz.json","quiz":{"count":1,"meta":{"topic":"Hello","difficulty":"Easy"},"items":[{"q":"1+1?","choices":["1","2","3","4"],"answer":1}]}}' \
  https://BACKEND_URL/api/my/save-quiz

# Overwrite
curl -sS -X POST -H "Content-Type: application/json" -H "Authorization: Bearer ID_TOKEN" \
  -d '{"overwrite":true,"filename":"hello_quiz.json","quiz":{"count":1,"meta":{"topic":"Hello","difficulty":"Easy"},"items":[{"q":"1+1?","choices":["1","2","3","4"],"answer":1}]}}' \
  https://BACKEND_URL/api/my/save-quiz

# Get / Delete
curl -sS -H "Authorization: Bearer ID_TOKEN" https://BACKEND_URL/api/my/quiz/hello_quiz.json
curl -sS -X DELETE -H "Authorization: Bearer ID_TOKEN" https://BACKEND_URL/api/my/quiz/hello_quiz.json
```

