# Google Sign‑In Setup Guide (GIS + OIDC)

This guide captures a lightweight, repeatable recipe for adding Google Sign‑In to any static frontend + API backend stack using Google Identity Services (GIS) for ID tokens and server‑side OIDC verification.

Use this when you want:
- A static site (no SSR) to obtain an `id_token` in the browser.
- An API backend to verify that token and authorize user‑scoped endpoints.
- Stateless auth (no cookies or sessions), simple CORS, and low operational overhead.

## Overview
- Frontend: load GIS, request an ID token, store it in memory, and attach it as `Authorization: Bearer <id_token>` on calls to protected routes (e.g., `/api/my/*`).
- Backend: verify the ID token’s signature, `aud`, `iss`, and expiry on each request; derive `user_id = sub`; namespace storage by `user_id`.
- Config: allowlist the frontend origins with CORS, and configure acceptable Client IDs on the backend.

## Prerequisites
- Google Cloud Console access (any project you control).
- A deployed frontend origin (or localhost for dev).
- A deployed backend URL for smoke testing.

## 1) Create OAuth Consent Screen
1. Open Google Cloud Console → APIs & Services → OAuth consent screen.
2. User type: External.
3. Fill basic app info and support email.
4. Scopes: add `openid`, `email`, `profile`.
5. Test users: add Gmail addresses for anyone testing.
6. Save. (Publishing is not required for test mode.)

## 2) Create “Web” OAuth Client (GIS)
1. APIs & Services → Credentials → Create credentials → OAuth client ID.
2. Application type: Web application.
3. Authorized JavaScript origins: add each frontend origin (no trailing slash). Examples:
   - `https://yourapp.onrender.com`
   - `https://staging.yourdomain.com`
   - `http://localhost:5173` (dev, if used)
4. Authorized redirect URIs: leave empty for GIS ID-token flow.
5. Create and download the JSON. This contains:
   - `web.client_id` (used by frontend and backend config)
   - `web.javascript_origins` (your origins)

Important: Do not commit this JSON to git. The frontend only needs the Client ID string.

## 3) Extract Values for Config
You will populate two backend env vars:
- `GOOGLE_CLIENT_IDS`: CSV of accepted Web Client IDs (staging/prod). Single value is fine.
- `ALLOWED_ORIGINS`: CSV of allowed frontend origins (no trailing slash).

From the downloaded JSON (example commands):
- Client ID: `python -c "import json;print(json.load(open('client_secret.json'))['web']['client_id'])"`
- Origins CSV: `python -c "import json;print(','.join(json.load(open('client_secret.json'))['web']['javascript_origins']))"`

Example values:
- `GOOGLE_CLIENT_IDS=abc123.apps.googleusercontent.com,xyz987.apps.googleusercontent.com`
- `ALLOWED_ORIGINS=https://yourapp.onrender.com,https://staging.yourdomain.com`

## 4) Frontend Integration (GIS)
Load GIS and request an ID token. Minimal example:

```html
<script src="https://accounts.google.com/gsi/client" async defer></script>
<script>
  let idToken = null;
  function onSignIn(response) {
    idToken = response.credential; // This is the ID token (JWT)
  }
  window.onload = () => {
    google.accounts.id.initialize({
      client_id: 'YOUR_WEB_CLIENT_ID',
      callback: onSignIn,
      ux_mode: 'popup' // optional: or 'redirect'
    });
    google.accounts.id.renderButton(document.getElementById('gsi'), { theme: 'outline', size: 'large' });
  };

  async function api(url, opts={}) {
    const headers = new Headers(opts.headers || {});
    if (idToken && url.includes('/api/my/')) headers.set('Authorization', `Bearer ${idToken}`);
    return fetch(url, { ...opts, headers });
  }
</script>
<div id="gsi"></div>
```

Notes
- Store tokens in memory only; avoid localStorage for security.
- Only attach the token to protected routes (e.g., `/api/my/*`).

## 5) Backend Verification (Python example)
Install dependency:
- `pip install google-auth`

Verification sketch:
```python
from google.oauth2 import id_token
from google.auth.transport import requests as grequests
ALLOWED_ISS = {'https://accounts.google.com', 'accounts.google.com'}
GOOGLE_CLIENT_IDS = [id1, id2]  # from env CSV

def verify_google_bearer(header_value: str):
    if not header_value or not header_value.startswith('Bearer '):
        raise PermissionError('Missing token')
    token = header_value.split(' ', 1)[1].strip()
    last_err = None
    for aud in GOOGLE_CLIENT_IDS or [None]:
        try:
            info = id_token.verify_oauth2_token(token, grequests.Request(), audience=aud)
            if info.get('iss') not in ALLOWED_ISS: raise PermissionError('Invalid issuer')
            return { 'user_id': info['sub'], 'email': info.get('email') }
        except Exception as e:
            last_err = e
    raise PermissionError('Invalid token')
```

Then protect your user‑scoped routes and namespace storage under `data/<resource>/<user_id>/...` (or use a DB keyed by `user_id`).

## 6) Environment Variables (Backend)
- `GOOGLE_CLIENT_IDS` — CSV of accepted Client IDs.
- `ALLOWED_ORIGINS` — CSV of FE origins without trailing slash.
- Optional knobs:
  - `RL_USER_PER_MIN`, `RL_IP_PER_MIN`, `RL_USER_PER_DAY`
  - `MAX_QUIZ_KB`

Example
```
GOOGLE_CLIENT_IDS=abc.apps.googleusercontent.com
ALLOWED_ORIGINS=https://yourapp.onrender.com
RL_USER_PER_MIN=5
RL_IP_PER_MIN=10
RL_USER_PER_DAY=50
MAX_QUIZ_KB=128
```

## 7) Smoke Tests
- Public: `GET /api/health` → `{ status: 'ok' }`.
- Auth: `GET /api/health/auth` with `Authorization: Bearer <ID_TOKEN>` → 200.
- User routes: `GET /api/my/list` → 200; `POST /api/my/save` → 200; repeat without overwrite → 409.

Example curl
```
curl -sS https://BACKEND_URL/api/health
curl -sS -H "Authorization: Bearer ID_TOKEN" https://BACKEND_URL/api/health/auth
curl -sS -H "Authorization: Bearer ID_TOKEN" https://BACKEND_URL/api/my/list-quizzes
```

## 8) Troubleshooting
- 401 Unauthorized
  - Decode token in console: `JSON.parse(atob(idToken.split('.')[1]))`; ensure `aud` equals a configured Client ID and `iss` is Google.
  - Ensure you used an ID token (GIS), not an OAuth access token.
- CORS blocked
  - Ensure `ALLOWED_ORIGINS` matches exactly (no trailing slash).
- 429 Rate limit
  - Confirm per‑IP/per‑user quotas; wait 60s or raise limits for testing.
- Local dev
  - Add `http://localhost:5173` (or your port) to GIS origins and to `ALLOWED_ORIGINS`.

## 9) Security Notes
- Do not commit `client_secret.json`.
- Backend should never log raw tokens; log `user_id` at info at most.
- Prefer ISO 8601 timestamps and 404 for cross‑tenant access to avoid resource enumeration.

## 10) Multi‑Environment Tips
- Use CSV for `GOOGLE_CLIENT_IDS` to support both staging and production.
- Mirror origins in GIS and `ALLOWED_ORIGINS`.
- Consider a Redis or DB‑backed rate limiter if horizontally scaling.

## 11) Quick Checklist
- [ ] OAuth consent screen set (External, test users added).
- [ ] Web OAuth client created; origins added; redirect URIs empty.
- [ ] Client ID copied; JSON stored securely (not committed).
- [ ] Backend configured with `GOOGLE_CLIENT_IDS` and `ALLOWED_ORIGINS`.
- [ ] Frontend initializes GIS and attaches bearer on `/api/my/*`.
- [ ] Smoke tests pass (health/auth + list/save/get/delete).

---
This document is generic and can be reused across projects that follow GIS + OIDC verification.
