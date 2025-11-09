Handoff: YTV2 Dashboard — Images, AI2, and Manage Images (Nov 2025)

Scope
- This memo hands off the recent dashboard work around image modes (OG/A1/AI2), the new Manage Images modal, and backend API tweaks. It’s written for the next dashboard maintainer.

Key Concepts
- OG: original thumbnail from the source (YouTube, site, etc.).
- A1: themed AI image (existing pipeline). Selected URL lives at top level `summary_image_url`.
- AI2: freestyle AI image (new pipeline). Selected URL lives in `analysis.summary_image_ai2_url`.
- Variants: history entries in `analysis.summary_image_variants[]` with fields like `{ url, prompt, image_mode, model, seed, created_at, ... }`.

Frontend Changes (static/dashboard_v3.js)
- Global image modes
  - Buttons in Settings → Images: `OG`, `A1`, `AI2`, `Rotate`.
  - Mode behavior:
    - `OG`: show thumbnail; if missing, fall back to AI (A1 then AI2).
    - `A1`: explicitly set summary image `src` to `summary_image_url` and store as `data-ai1-url`.
    - `AI2`: explicitly set `src` to `analysis.summary_image_ai2_url` (or best-matched AI2 variant) and store as `data-ai2-url`.
    - `Rotate`: cycles deterministically across OG → A1 → all AI2 variants per card; advances when you reselect Rotate.

- Manage Images modal (replaces “Create image…”) — per card
  - Tabs: `AI1` and `AI2`.
  - Each tab shows:
    - Prompt textarea (defaults):
      - AI1 → `analysis.summary_image_prompt` → last A1 variant prompt → `summary_image_prompt_last_used`.
      - AI2 → `analysis.summary_image_ai2_prompt` → last AI2 variant prompt.
    - “Regenerate AI1/AI2” saves prompt with mode (does not touch `_last_used`). NAS picks it up.
    - Variants list with prompt preview, “Selected” badge overlay, “Use this prompt” and “Select this image”.
  - Selection reflects immediately in the card and persists across mode toggles.
  - We purposely hid the old “Dashboard default” radio; backend support remains if a future “Default” global mode is desired.

Backend Changes (server.py, modules/postgres_content_index.py)
- New/updated endpoints (all Bearer DEBUG_TOKEN):
  - `POST /api/set-image-prompt` → { video_id, prompt, mode: 'ai1'|'ai2' }
    - ai1: writes `analysis.summary_image_prompt`
    - ai2: writes `analysis.summary_image_ai2_prompt`
    - emits SSE `image-prompt-set` with `{ video_id, mode }`
  - `POST /api/select-image-variant` → { video_id, url, mode }
    - ai1: sets `summary_image_url` and `analysis.summary_image_selected_url`
    - ai2: sets `analysis.summary_image_ai2_url`
  - `POST /api/set-image-display-mode` (available but UI hidden for now)
    - { video_id, mode: 'og'|'ai1'|'ai2' } → `analysis.summary_image_display_mode`

- Postgres mappers
  - List API includes: `analysis.summary_image_ai2_url`, `analysis.summary_image_variants`.
  - Updaters:
    - `update_summary_image_prompt(video_id, prompt)`
    - `update_summary_image_ai2_prompt(video_id, prompt)`
    - `update_selected_image_url(video_id, url)` (A1)
    - `update_selected_image_ai2_url(video_id, url)` (AI2)
    - `update_summary_image_display_mode(video_id, mode)` (optional)

NAS Contract (assumed and validated)
- Regeneration seeding uses “diff vs last_used” per mode:
  - AI1: enqueue when `analysis.summary_image_prompt` != `analysis.summary_image_prompt_last_used`.
  - AI2: enqueue when `analysis.summary_image_ai2_prompt` != `analysis.summary_image_ai2_prompt_last_used`.
- On success, NAS:
  - updates the corresponding `_last_used` field to the actual prompt,
  - appends a variant entry with `image_mode:'ai1'|'ai2'`,
  - sets `summary_image_url` (A1) or `analysis.summary_image_ai2_url` (AI2).
- Optional fast-path: listen to dashboard SSE `image-prompt-set` and enqueue immediately.

Debugging Tips
- Check which asset the card shows:
  - Look at `[data-role="thumb-summary"]` `data-ai1-url` / `data-ai2-url`.
  - OG fallback if thumbnail missing.
- If “Regenerate …” appears to do nothing:
  - Verify prompt fields in Postgres: the active prompt field (per mode) should differ from `_last_used` until NAS renders.
  - If they match immediately, the prompt was written into the wrong field or `_last_used` was updated incorrectly.

Files Touched
- `static/dashboard_v3.js`: image mode logic, Manage Images modal, mode-aware selection, rotate.
- `dashboard_v3_template.html`: cache-buster, remove debug stamp, header layout.
- `server.py`: mode-aware prompt/save endpoints + SSE payload includes mode.
- `modules/postgres_content_index.py`: new setters for AI2 prompt/selection; pass-through fields.

Known UX Decisions
- Rotate now includes all AI2 variants.
- OG mode shows AI fallback when no thumbnail exists.
- Manage Images hides per-card “default mode” selector for now; backend endpoint remains.

Follow-Ups (optional)
- Add “Delete variant” per row (soft-delete/flag in `analysis.summary_image_variants`).
- Add a star/favorite for variants to influence Rotate ordering.
- Add a global “Default” mode that honors `analysis.summary_image_display_mode` per card.

Cache-Buster
- Last pushed at `dashboard_v3.js?v=pg91` and later fixes through `pg90/pg91`. Always hard refresh after deploy while testing.

