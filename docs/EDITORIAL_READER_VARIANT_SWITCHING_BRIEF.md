# Editorial Reader: Summary Variant Switching

Add summary variant switching to the editorial reader. This is the single highest-value classic-reader capability to bring back — multiple summary formats already exist in the API response but the editorial reader only shows the first one.

**Applies to:**
- `static/editorial_dashboard.js` (only `renderReaderContent()` and click handlers)
- `static/editorial_dashboard.css`

**Do not:**
- Add Transcript, Research, or Discussion modes (future phases)
- Change the reader layout or aesthetic
- Touch the classic dashboard (`static/v2/report_v2.js`)

## Current State

The editorial reader renders one summary. In `renderReaderContent()` (JS ~line 1106):

```js
var summary = data.summary || {};
var summaryHtml = summary.html || summary.text || '<p>No summary available.</p>';
```

It ignores `data.summary_variants[]` entirely except for extracting audio URLs.

## What the API Returns

The `/{video_id}.json` endpoint returns:

```js
{
  "summary": { "html": "...", "text": "...", "variant": "key-insights" },
  "summary_variants": [
    { "variant": "key-insights", "html": "...", "text": "..." },
    { "variant": "bullet-points", "html": "...", "text": "..." },
    { "variant": "comprehensive", "html": "...", "text": "..." }
  ],
  "has_audio": true/false,
  "transcript": "...",           // only for YouTube items
  "transcript_segments": [...]   // only for YouTube items
}
```

Most items have 1 variant (just `key-insights`). Some have 2-3. A few YouTube items also have `transcript` and `transcript_segments`.

## What To Implement

### 1. Store All Variants

In `renderReaderContent()`, after reading `summary_variants`, store them for later switching:

```js
// Store variants for switching
this._readerVariants = variants;       // the full array
this._readerActiveVariant = 0;         // index into the array
```

### 2. Render Variant Tabs

If `variants.length > 1`, render a compact tab row above the summary content, below the image:

```
[Key Insights]  [Bullet Points]  [Comprehensive]
```

The active tab gets a subtle highlight (accent color text, no heavy background). Inactive tabs are muted.

Humanize variant names using this mapping:
- `key-insights` → "Key Insights"
- `bullet-points` → "Key Points"
- `comprehensive` → "Full Summary"
- `deep-research` → "Research"
- For any unknown variant: capitalize and replace hyphens with spaces

HTML structure:
```html
<div class="ed-reader__variants">
  <button class="ed-reader__variant active" data-variant-idx="0">Key Insights</button>
  <button class="ed-reader__variant" data-variant-idx="1">Key Points</button>
  <button class="ed-reader__variant" data-variant-idx="2">Full Summary</button>
</div>
```

Only render this row if `variants.length > 1`. If only one variant exists, skip it entirely — no empty tab bar.

### 3. Handle Variant Switching

Add a click handler for `.ed-reader__variant` buttons:

1. Update `this._readerActiveVariant` to the clicked index
2. Update the active class on tabs
3. Replace `.ed-reader__summary` innerHTML with the selected variant's HTML
4. Also update the Listen button's audio URL if the selected variant has one (check `variants[idx].audio_url`)

### 4. Update Audio URL on Variant Switch

When switching variants, check if the new variant has an audio URL. If so, update the Listen button's `data-audio-url` attribute and enable the button. If not, disable it.

### 5. CSS

Style the variant tabs as a quiet, editorial segmented control:

```css
.ed-reader__variants {
    display: flex;
    gap: 0.15rem;
    margin-bottom: var(--ed-space-md);
    padding-bottom: var(--ed-space-sm);
    border-bottom: 1px solid var(--ed-color-border);
}

.ed-reader__variant {
    padding: 0.3rem 0.7rem;
    background: none;
    border: none;
    border-radius: var(--ed-radius-sm);
    color: var(--ed-color-muted);
    font-size: 0.82rem;
    font-family: var(--ed-font-body);
    font-weight: 500;
    cursor: pointer;
    transition: color var(--ed-transition-fast), background var(--ed-transition-fast);
}

.ed-reader__variant:hover {
    color: var(--ed-color-text);
    background: var(--ed-color-surface);
}

.ed-reader__variant--active {
    color: var(--ed-color-accent);
    background: rgba(59, 130, 246, 0.08);
}
```

The tabs should feel like the Topics/Refine nav tabs — same visual family.

## Acceptance Standard

- When an item has multiple summary variants, a tab row appears above the summary
- Clicking a tab swaps the summary content without reloading the reader
- Audio button updates when the selected variant has/doesn't have audio
- When an item has only one variant, no tab row appears
- The tab styling is quiet and editorial — matches the nav aesthetic
- Both `/editorial` and `/` still return 200
