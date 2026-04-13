# Editorial Reader Admin Actions Corrective Brief

This brief replaces the earlier admin-actions brief for the next implementation pass.

The current editorial reader admin work is **not** ready. It has three separate problems:

1. The admin menu shell is visually broken in production.
2. `Manage Images` is only a partial shell and does not match classic functionality.
3. `Regenerate` is wired, but the modal design does not fit the editorial reader.

Use this brief as the source of truth for the fix.

## Goal

Keep the editorial reader aesthetic, but restore the useful classic admin capabilities properly:

- `Regenerate`
- `Manage Images`
- `Delete`

Reuse:

- existing backend endpoints
- existing payload shapes
- existing auth pattern
- classic logic for image handling and selection state

Rebuild:

- menu shell
- modal/dialog surfaces
- picker layouts
- image management UI

Do **not** port the classic DOM/CSS wholesale.

## Applies To

Working-agent local paths:

- `/Users/markdarby16/16projects/ytv2/dashboard16/static/editorial_dashboard.js`
- `/Users/markdarby16/16projects/ytv2/dashboard16/static/editorial_dashboard.css`

Reference files for functionality parity:

- `/Users/markdarby16/16projects/ytv2/dashboard16/static/dashboard_v3.js`
- `/Users/markdarby16/16projects/ytv2/dashboard16/docs/HANDOFF_DASHBOARD.md`
- `/Users/markdarby16/16projects/ytv2/dashboard16/modules/postgres_content_index.py`
- `/Users/markdarby16/16projects/ytv2/dashboard16/server.py`

## What Is Broken Right Now

### 1. Admin menu shell has no CSS

The reader injects:

- `.ed-reader__admin-toggle`
- `.ed-reader__admin-menu`
- `.ed-reader__admin-item`

but the CSS file currently has no matching styling rules, so the controls render as default browser buttons at the top of the reader.

This must be fixed first.

### 2. Manage Images is not classic-parity

The editorial modal currently behaves like a placeholder:

- AI2 handling is based on `summary_image_ai2_variants`, which is not the real shared dashboard model
- it does not properly derive AI2 variants from `summary_image_variants[]`
- it does not bring over classic prompt reuse, timestamps, selected-state handling, or robust URL normalization
- it still uses browser-native confirmation dialogs

Classic already solved these problems. Port the behavior, not the old chrome.

### 3. Regenerate modal is too generic

The current regenerate UI is basically a checkbox form with light styling. It is functional, but it does not feel like part of the editorial reader.

## Fix Order

Implement in this order:

1. Fix the admin menu shell and positioning.
2. Rebuild `Manage Images` to near-classic parity.
3. Replace browser `confirm()` and `prompt()` usage with editorial modal surfaces.
4. Redesign `Regenerate` to fit the editorial reader.
5. Final visual polish and QA.

## 1. Admin Menu Shell

### Required behavior

Keep the `...` button near the reader close button.

Clicking it should open a compact anchored dropdown containing:

- `Regenerate...`
- `Manage Images...`
- `Delete...`

### Required CSS

Add these rules to `editorial_dashboard.css`. Use the same visual language as the close button and Topics/Refine dropdowns:

```css
.ed-reader__admin-toggle {
    position: absolute;
    top: 0.75rem;
    right: 3rem;
    background: var(--ed-color-surface);
    border: 1px solid var(--ed-color-border);
    color: var(--ed-color-muted);
    font-size: 1.1rem;
    font-weight: 700;
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

The toggle must sit in the same top-right corner as the close button (`.ed-reader__close`), spaced to its left by `right: 3rem` vs close's `right: 0.75rem`.

## 2. Manage Images

This is the biggest gap.

### Functional parity target

Use the classic implementation in:

- `/Users/markdarby16/16projects/ytv2/dashboard16/static/dashboard_v3.js`

especially the `handleManageImages` / `openManageImagesModal` flow as the behavioral reference.

### Data model requirements

Do **not** assume separate AI2 variant arrays.

Use the real shared model described in:

- `/Users/markdarby16/16projects/ytv2/dashboard16/docs/HANDOFF_DASHBOARD.md`

Key facts:

- both AI1 and AI2 history live in `analysis.summary_image_variants[]`
- AI2 selected image lives in `analysis.summary_image_ai2_url`
- AI1 selected image lives in top-level `summary_image_url` and `analysis.summary_image_selected_url`

### Required AI2 detection

Port this exact logic from `dashboard_v3.js` lines 12429-12434. Do **not** simplify it:

```js
// Inside your class or as a standalone function
function isAi2Variant(v) {
    var m = (v.image_mode || '').toLowerCase();
    var tmpl = (v.template || '').toLowerCase();
    var ps = (v.prompt_source || '').toLowerCase();
    var url = v.url || '';
    return m === 'ai2' || tmpl === 'ai2_freestyle' || (ps && ps.startsWith('ai2')) || /(?:^|\/)AI2_/i.test(url);
}
```

### Required URL normalization

Port from `dashboard_v3.js` line 10375. Variant URLs in the API can be absolute (`http://hostname:10000/exports/...`) or relative (`/exports/...`). Selected URLs are usually relative. All comparisons must normalize first:

```js
function normalizeAssetUrl(u) {
    if (!u || typeof u !== 'string') return u || '';
    var trimmed = u.trim();
    if (!trimmed) return '';
    // Keep absolute URLs as-is (they are valid image src attributes)
    if (trimmed.startsWith('http://') || trimmed.startsWith('https://')) return trimmed;
    if (trimmed.startsWith('/')) return trimmed;
    return '/' + trimmed;
}
```

For **selected-state comparison**, strip the hostname to compare paths:

```js
function urlPath(url) {
    if (!url) return '';
    try { return new URL(url, 'http://x').pathname; }
    catch (_) { return url.replace(/^https?:\/\/[^\/]+/, ''); }
}
// Usage: urlPath(variantUrl) === urlPath(selectedUrl)
```

### Required AI2 variant URL collection

Port from `dashboard_v3.js` lines 10415-10431. Derive AI2 variant URLs from the shared `summary_image_variants[]` array:

```js
function getAi2VariantUrls(analysis) {
    var urls = [];
    var seen = {};
    function push(u) {
        var n = normalizeAssetUrl(u);
        if (n && !seen[n]) { seen[n] = true; urls.push(n); }
    }
    // Direct AI2 URL field
    var direct = (analysis && analysis.summary_image_ai2_url) || '';
    push(direct);
    // Scan shared variants for AI2 entries
    var variants = (analysis && Array.isArray(analysis.summary_image_variants)) ? analysis.summary_image_variants : [];
    for (var i = 0; i < variants.length; i++) {
        var v = variants[i] || {};
        var u = v.url || '';
        if (isAi2Variant(v)) push(u);
    }
    return urls;
}
```

### Required prompt defaults logic

Port from `dashboard_v3.js` lines 12436-12447. Prompt text comes from multiple fallback sources:

```js
// AI1 default prompt
var a1Default = analysis.summary_image_prompt || '';
if (!a1Default) {
    // Last AI1 variant with a prompt
    for (var i = allVars.length - 1; i >= 0; i--) {
        if (!isAi2Variant(allVars[i]) && allVars[i].prompt) {
            a1Default = allVars[i].prompt;
            break;
        }
    }
    if (!a1Default) a1Default = analysis.summary_image_prompt_last_used || '';
}

// AI2 default prompt
var a2Default = analysis.summary_image_ai2_prompt || analysis.summary_image_ai2_prompt_last_used || '';
if (!a2Default) {
    for (var i = allVars.length - 1; i >= 0; i--) {
        if (isAi2Variant(allVars[i]) && allVars[i].prompt) {
            a2Default = allVars[i].prompt;
            break;
        }
    }
}
```

Populate the textarea with this default when the modal opens.

### Required UI features

The editorial `Manage Images` modal must include:

1. `AI1` / `AI2` tabs (segmented control, not heavy workspace tabs).
2. Prompt textarea for the active mode, pre-populated with the default prompt logic above.
3. "Default:" helper line below textarea showing the original prompt (`analysis.summary_image_prompt_original` for AI1, `analysis.summary_image_ai2_prompt_original` for AI2). Only show if original exists.
4. `Regenerate AI1` / `Regenerate AI2` button (calls `/api/set-image-prompt`).
5. `Use default prompt` button (restores original prompt text into textarea — does NOT trigger regeneration).
6. Variant rows/cards for the active mode.
7. Per-variant row:
   - thumbnail image
   - relative timestamp (e.g. "5m ago" — port `formatRelativeTime` from `dashboard_v3.js`, or use a simple helper)
   - prompt preview (first ~120 chars of `v.prompt`)
   - `Use this prompt` button (loads that variant's prompt into the textarea)
   - `Select this image` button (calls `/api/select-image-variant`)
   - `Delete` button (calls `/api/delete-image-variant` with editorial confirmation dialog)
8. Visible `Selected` state for the active image (highlight border + "Selected" badge).
9. `Delete all AI images...` at bottom (calls `/api/delete-all-ai-images` with editorial confirmation dialog).
10. Footer close button.

### Required interaction behavior

- `Use this prompt` loads that variant’s prompt into the textarea.
- `Select this image` updates the selected pointer and refreshes local state immediately.
- delete of a selected variant must clear the correct pointer:
  - AI1: `summary_image_url` and/or `analysis.summary_image_selected_url`
  - AI2: `analysis.summary_image_ai2_url`
- comparisons must use normalized URLs, not raw string equality
- lists must sort by `created_at` descending

### Required visual direction

Keep the editorial modal shell, but bring back the useful richness:

- calm dark surface
- clear section headings
- proper row spacing
- no default browser controls
- no “empty placeholder” feel

### Confirmations

Replace browser-native confirms with editorial confirmation dialogs for:

- delete single variant
- delete all AI images

## 3. Token Prompt

Current browser `prompt()` usage is not acceptable in the editorial reader.

Replace it with a small editorial modal:

- title: `Admin token required`
- one password/text input
- explanatory helper copy
- `Cancel`
- `Save token`

Store to the same key:

- `localStorage['ytv2.reprocessToken']`

Do not change the underlying auth pattern.

## 4. Regenerate

Keep the underlying `/api/reprocess` endpoint and payload behavior.

### Required behavior

Support the existing set:

- comprehensive
- bullet-points / key points
- key-insights
- audio EN
- audio FR with proficiency
- audio ES with proficiency

Continue showing subtle `Exists` state if a variant already exists.

### Redesign requirements

The regenerate modal should no longer feel like a raw checkbox wall.

Preferred structure:

1. Intro/header.
2. Text outputs group.
3. Audio outputs group.
4. Within each group, selectable variant cards/rows with:
   - clearer selected state
   - cleaner label hierarchy
   - quiet `Exists` badge
5. Audio proficiency controls visually subordinate to the audio rows.

### UX improvements

- make selected state visually obvious
- make the primary CTA smarter, e.g. `Regenerate 2 selected`
- keep the modal calm and editorial, not tool-y

## 5. Delete

Delete is closest to acceptable already.

Keep:

- editorial confirmation modal
- danger action styling
- close reader on success
- remove card from feed on success

Only tune this if needed for consistency with the other rebuilt admin surfaces.

## Acceptance Checklist

Do not call this done unless all of the following are true:

- the `...` admin menu is visually styled and anchored correctly
- no admin controls render as raw browser buttons
- `Manage Images` supports both AI1 and AI2 using the shared variant model
- AI2 variants appear when classic would show them
- selected-image highlighting works via normalized URL comparison
- deleting a selected image clears the correct selected pointer
- no browser `confirm()` remains in editorial admin flows
- no browser `prompt()` remains for token entry
- `Regenerate` looks like an editorial modal, not a raw checkbox form
- `Delete`, `Regenerate`, and `Manage Images` all open from the same styled reader admin menu

## Non-Goals

Do not do these in this pass:

- backend endpoint changes
- auth model redesign
- role/session system changes
- restoring every legacy classic utility control

The goal is parity for the useful admin actions, not a full classic-reader clone.

## Final Standard

The correct outcome is:

- classic-level capability where it matters
- editorial-level presentation everywhere

If there is a tradeoff, do **not** choose “simpler but visibly incomplete” for `Manage Images`. That is the main thing to fix in this recovery pass.
