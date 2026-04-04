# Editorial Reader Admin Actions Brief

Add admin actions (Regenerate, Delete, Manage Images) to the editorial reader. The backend APIs, payloads, and auth patterns all exist — the work here is building editorial-styled UI surfaces that call them.

**Applies to:**
- `static/editorial_dashboard.js` (class `EditorialDashboard`)
- `static/editorial_dashboard.css`

**Do not:**
- Change any backend endpoints or auth logic
- Port the classic modal DOM or CSS classes
- Touch the classic dashboard (`static/v2/report_v2.js`, `static/dashboard_v3.js`)

## Auth Pattern

All admin actions (except Delete) use `DEBUG_TOKEN` stored in `localStorage` under key `ytv2.reprocessToken`.

Read it:
```js
var token = localStorage.getItem('ytv2.reprocessToken') || '';
```

If the token is missing when an admin action is attempted, show a token prompt (text input + save to localStorage) before proceeding. The classic UI does this in `report_v2.js` line 1265-1276.

The token is sent as either:
- `X-Reprocess-Token` header (for `/api/reprocess`)
- `Authorization: Bearer <token>` header (for image endpoints)

Delete (`DELETE /api/delete/:id`) currently has no auth check — but still gate it behind the `...` menu to keep it out of casual reach.

## 1. Admin Menu Shell

Add a small `...` button near the reader close button (top-right corner of the reader panel). Clicking it opens a compact dropdown with:

- **Regenerate...**
- **Manage Images...**
- **Delete...**

HTML structure:
```html
<button class="ed-reader__admin-toggle" data-action="toggle-admin-menu">...</button>
<div class="ed-reader__admin-menu">
  <button class="ed-reader__admin-item" data-action="admin-regenerate">Regenerate...</button>
  <button class="ed-reader__admin-item" data-action="admin-images">Manage Images...</button>
  <button class="ed-reader__admin-item ed-reader__admin-item--danger" data-action="admin-delete">Delete...</button>
</div>
```

The menu is positioned absolute, right-aligned, just below the `...` button. Clicking outside closes it. Same click-outside pattern as Topics/Refine menus.

## 2. Regenerate

### Endpoint

`POST /api/reprocess`

Headers:
```
Content-Type: application/json
X-Reprocess-Token: <token>
```

Payload:
```json
{
  "video_id": "<video_id>",
  "regenerate_audio": true,
  "summary_types": ["comprehensive", "audio", "audio-fr:intermediate"]
}
```

### Available Variants

```js
var REPROCESS_VARIANTS = [
    { id: 'comprehensive', label: 'Comprehensive', kind: 'text' },
    { id: 'bullet-points', label: 'Key Points', kind: 'text' },
    { id: 'key-insights', label: 'Insights', kind: 'text' },
    { id: 'audio', label: 'Audio (EN)', kind: 'audio' },
    { id: 'audio-fr', label: 'Audio français', kind: 'audio', proficiency: true },
    { id: 'audio-es', label: 'Audio español', kind: 'audio', proficiency: true }
];
```

Audio variants with `proficiency: true` append a colon + level to the summary_type: `audio-fr:intermediate`. Proficiency levels: `beginner`, `intermediate`, `advanced`.

### Editorial UI

Open a centered modal overlay with:
- Title: "Regenerate"
- A clean list of variant cards (not a checkbox grid). Each card shows the variant label and a selected state (checkmark or filled state).
- Audio variants with proficiency show a simple segmented control for level selection.
- "Already exists" indicators if the current report already has that variant (check `summary_variants` from the loaded reader data).
- Primary action: "Regenerate selected" button.
- Cancel link.

On success, show a brief toast/status message and close the modal.

### Existing Output Detection

From the reader's loaded data (`this._readerVariants`), you can tell which outputs already exist:
- Check if variant slugs like `comprehensive`, `bullet-points`, `key-insights`, `audio` are in the variants array
- Show a subtle "Exists" badge on those cards
- Still allow selecting them (regenerate replaces)

## 3. Delete

### Endpoint

`DELETE /api/delete/:id`

No auth headers required (personal dashboard).

### Editorial UI

Centered confirmation dialog:
- Title: "Delete report"
- Body: "This will permanently delete this report and all associated files (summary, images, audio). This cannot be undone."
- Two buttons: Cancel (ghost) and Delete (danger/red primary)
- Close the reader and remove the card from the feed on success

On success:
- Close the reader panel
- Remove the card from the DOM with a fade-out animation
- Show a brief toast

## 4. Manage Images

### Endpoints

Set image prompt:
`POST /api/set-image-prompt`
```json
{ "video_id": "<id>", "prompt": "custom prompt text", "mode": "ai1" }
```
Headers: `Authorization: Bearer <token>`, `Content-Type: application/json`
Mode is `"ai1"` (default) or `"ai2"`.

Select a variant as the active image:
`POST /api/select-image-variant`
```json
{ "video_id": "<id>", "url": "/exports/images/image.png", "mode": "ai1" }
```
Headers: `Authorization: Bearer <token>`, `Content-Type: application/json`

Delete a single variant:
`POST /api/delete-image-variant`
```json
{ "video_id": "<id>", "url": "/exports/images/image.png" }
```
Headers: `Authorization: Bearer <token>`, `Content-Type: application/json`

Delete all AI images:
`POST /api/delete-all-ai-images`
```json
{ "video_id": "<id>", "modes": ["ai1", "ai2"] }
```
Headers: `Authorization: Bearer <token>`, `Content-Type: application/json`

### Image Data Available

From the reader's loaded JSON (the `/{video_id}.json` response), `data.analysis` contains:
- `summary_image_prompt` — current AI1 prompt (may be null)
- `summary_image_prompt_original` — first custom prompt (may be null)
- `summary_image_prompt_last_used` — last prompt used for generation
- `summary_image_ai2_prompt` / `ai2_prompt_original` / `ai2_prompt_last_used` — same for AI2
- `summary_image_selected_url` — currently selected image path
- `summary_image_variants` — array of `{ url, seed, model, width, height, preset }`
- `summary_image_ai2_url` — AI2 generated image URL

### Editorial UI

A centered modal with:

1. **Mode switch** — segmented control: AI1 | AI2 (only if AI2 data exists; if only AI1, no switch needed)

2. **Prompt section** — textarea showing the current prompt (from `_last_used` field), with a "Regenerate" button. On save, calls `/api/set-image-prompt` with the new prompt.

3. **Variant gallery** — horizontal card stack of available image variants. Each card:
   - Shows the image thumbnail
   - Has a "Select" button (calls `/api/select-image-variant`)
   - Has a small "×" delete button (calls `/api/delete-image-variant` with confirmation)
   - Currently selected variant gets a highlight/border

4. **Destructive actions** — at the bottom, muted: "Delete all AI images..." with confirmation

Avoid: dense grid layouts, heavy workspace panels, nested tabs.

## 5. CSS

Admin menu button — positioned near close button, same visual family:
```css
.ed-reader__admin-toggle {
    position: absolute;
    top: 0.75rem;
    right: 3rem;
    background: var(--ed-color-surface);
    border: 1px solid var(--ed-color-border);
    color: var(--ed-color-muted);
    font-size: 1rem;
    cursor: pointer;
    width: 2rem;
    height: 2rem;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 10;
    transition: color var(--ed-transition-fast), border-color var(--ed-transition-fast);
}
.ed-reader__admin-toggle:hover {
    color: var(--ed-color-text);
    border-color: var(--ed-color-muted);
}
```

Admin menu dropdown — same visual family as Topics/Refine dropdowns:
```css
.ed-reader__admin-menu {
    display: none;
    position: absolute;
    top: 2.75rem;
    right: 3rem;
    min-width: 180px;
    background: var(--ed-color-surface);
    border: 1px solid var(--ed-color-border);
    border-radius: var(--ed-radius-md);
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.35);
    z-index: 310;
    padding: 0.35rem 0;
}
.ed-reader__admin-menu--open {
    display: block;
}

.ed-reader__admin-item {
    display: block;
    width: 100%;
    padding: 0.55rem 1rem;
    background: none;
    border: none;
    color: var(--ed-color-muted);
    font-size: 0.85rem;
    font-weight: 500;
    font-family: var(--ed-font-body);
    text-align: left;
    cursor: pointer;
    transition: all var(--ed-transition-fast);
}
.ed-reader__admin-item:hover {
    color: var(--ed-color-text);
    background: var(--ed-color-surface-hover);
}
.ed-reader__admin-item--danger {
    color: #ef4444;
}
.ed-reader__admin-item--danger:hover {
    background: rgba(239, 68, 68, 0.1);
}
```

Modal overlays should use the existing design tokens: dark background, rounded corners, centered, with backdrop.

## Implementation Order

1. Admin menu shell (`...` button + dropdown)
2. Delete (simplest — confirmation dialog + one API call)
3. Regenerate (variant picker + one API call)
4. Manage Images (most complex — multi-endpoint modal)

## Acceptance Standard

- `...` menu appears near the close button when the reader is open
- Regenerate lets you pick variants and triggers reprocessing
- Delete shows confirmation and removes the item
- Manage Images lets you view/select/delete image variants and edit prompts
- All three reuse existing backend endpoints with correct payloads and auth
- Admin UI matches the editorial aesthetic — calm, dark, restrained
- The reader remains reading-first — admin controls are secondary and hidden behind the menu
- Both `/editorial` and `/` still return 200
