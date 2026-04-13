# Editorial Reader Admin Rebuild Brief

This brief replaces the previous corrective brief for the next pass.

The current editorial admin surfaces are still not good enough.

## Current Assessment

### Regenerate

The current regenerate modal is not acceptable.

Problems:

- too much wasted space
- weak hierarchy
- rows feel empty and under-designed
- text/audio grouping exists, but the presentation still reads like a generic form
- the CTA area feels disconnected from the selection surface

The classic regenerate modal is denser, clearer, and more intentional.

### Manage Images

The current `Manage Images` modal is still below the bar.

Problems:

- too much empty space when few variants exist
- weak visual hierarchy
- the surface still feels like a placeholder admin form, not a finished workflow
- parity with classic is still incomplete at the state-management level
- AI1/AI2 flow is better than before, but the overall experience is still much worse than classic

The classic implementation is functionally richer and visually more resolved.

## Goal

Keep the editorial design language, but rebuild the admin surfaces so they feel:

- compact
- intentional
- dense enough to be useful
- clearly organized
- closer to the classic workflow quality

This is **not** a request for “lighter polish.”
This is a **rebuild of the admin surfaces**.

## Applies To

Working-agent local paths:

- `/Users/markdarby16/16projects/ytv2/dashboard16/static/editorial_dashboard.js`
- `/Users/markdarby16/16projects/ytv2/dashboard16/static/editorial_dashboard.css`

Reference for behavior and interaction quality:

- `/Users/markdarby16/16projects/ytv2/dashboard16/static/dashboard_v3.js`
- `/Users/markdarby16/16projects/ytv2/dashboard16/docs/HANDOFF_DASHBOARD.md`

## Non-Negotiable Principles

1. Reuse classic functionality.
2. Do not reuse classic DOM/CSS directly.
3. Do not accept sparse, placeholder-like modal layouts.
4. Prefer compact, high-signal surfaces over oversized empty cards.
5. Use editorial styling, but keep utility workflows efficient.

## 1. Admin Menu

The admin menu shell is now conceptually correct.

Keep:

- `...` button near the close button
- anchored dropdown
- `Regenerate...`
- `Manage Images...`
- `Delete...`

Only tune this further if spacing/alignment still feels off after the rebuild.

This is not the main problem now.

## 0. Critical Bug: Modal Backdrop Click Handler

Before touching Regenerate or Manage Images, fix this bug in `bindEvents()` (currently around line 1047):

```js
// BUG: This matches any click inside the modal because the modal is a child of the backdrop
if (e.target.closest('.ed-modal-backdrop')) {
    this.closeModal();
}
```

Since `.ed-modal` is rendered inside `.ed-modal-backdrop`, clicking ANY element inside the modal (checkboxes, buttons, text, images) matches `.closest('.ed-modal-backdrop')` and closes the modal.

**Fix:** Only close when the click is directly on the backdrop element itself:

```js
// FIXED: Only close on direct backdrop click, not clicks on children
if (e.target.classList.contains('ed-modal-backdrop')) {
    this.closeModal();
}
```

This is blocking ALL modal interactions right now. Fix it first.

## 2. Regenerate Rebuild

### Direction

Rebuild the regenerate modal to be:

- more compact
- more grid-like
- more card-based
- closer to the classic modal’s scannability

Do **not** keep the current long vertical list of large empty rows.

### Recommended Layout

Use a compact 2-column option grid on desktop.

Example structure:

- modal title + one short explanatory sentence
- output options grid
- optional model/token row below if needed later
- footer actions

Each output option should feel like a compact selectable tile, not a giant empty form row.

### Tile Requirements

Each regenerate option tile should show:

- label
- optional icon/emoji or subtle leading marker
- selected state
- `Exists` / `Already generated` as a small secondary badge

For audio FR/ES:

- show proficiency selector only when the tile is selected
- or show it inline but compact and visually subordinate

### CTA Improvements

The footer CTA should reflect selection clearly:

- `Regenerate 1 output`
- `Regenerate 3 outputs`

Disable when nothing is selected.

### Density Goal

The modal should feel like a purposeful control panel for one task, not a stack of oversized empty cards.

### Functional Requirements

Keep existing behavior:

- same `/api/reprocess` endpoint
- same `X-Reprocess-Token`
- same summary type payloads
- same audio proficiency encoding

## 3. Manage Images Rebuild

### Direction

Rebuild `Manage Images` as a real editorial admin workspace.

It should be:

- wider
- denser
- more structured
- closer to classic usefulness
- less empty

### Layout Recommendation

Use a compact structured modal with:

1. header
2. AI1 / AI2 tabs
3. prompt area
4. action row
5. variants list
6. footer

Do **not** let the variants area collapse into a giant blank region when there are few items.

### Prompt Area

Make the prompt area more compact and useful:

- label
- textarea
- optional `Default:` helper line
- action row right below

Action row:

- `Regenerate AI1` / `Regenerate AI2`
- `Use default prompt`

This row should feel like a compact tool strip, not two giant floating buttons.

### Variants List

The variants area should be the main value of the modal.

Each variant row/card should include:

- thumbnail
- relative timestamp
- prompt preview
- selected badge/state
- `Use this prompt`
- `Select this image`
- `Delete`

### Visual Direction

Use a tighter row layout similar in spirit to classic:

- smaller gaps
- stronger alignment
- less wasted vertical space
- clearer row boundaries

Do not make each variant feel like a huge isolated card unless there are only one or two and the design still feels intentional.

### Selected State

Selected state must be obvious:

- badge and/or border
- consistent for AI1 and AI2
- URL comparisons must stay normalized

### Empty State

If there are no variants:

- make the empty state compact
- keep the prompt tools useful
- avoid a giant empty dead zone

Example:

- one short muted message
- maybe a subtle note that regenerating will create the first variant

### Functional Requirements

Must keep or improve:

- AI1/AI2 derived from shared `summary_image_variants[]`
- AI2 detection parity with classic
- prompt reuse
- timestamp display
- default prompt restoration
- selected pointer clearing on delete
- delete all images
- editorial confirmation dialogs
- token modal instead of browser prompt

### State Requirements

Fix remaining local-state issues. These are the exact field names from the API response (`/{video_id}.json`):

**AI1 selected image fields (BOTH must be updated on select):**
- Top-level: `this._readerData.summary_image_url`
- Analysis: `this._readerData.analysis.summary_image_selected_url`

**AI2 selected image field:**
- `this._readerData.analysis.summary_image_ai2_url`

**Shared variant array:**
- `this._readerData.analysis.summary_image_variants[]` — contains BOTH AI1 and AI2 variants

**On select AI1 image:** update both `summary_image_url` AND `analysis.summary_image_selected_url` to the selected URL.

**On select AI2 image:** update `analysis.summary_image_ai2_url`.

**On delete a variant:**
1. Remove the variant from `analysis.summary_image_variants` (filter out matching URL)
2. If the deleted URL was the selected AI1 image, clear both `summary_image_url` and `analysis.summary_image_selected_url`
3. If the deleted URL was the selected AI2 image, clear `analysis.summary_image_ai2_url`
4. Then rerender

**On delete all images:**
1. Clear `analysis.summary_image_variants` to `[]`
2. Clear `analysis.summary_image_ai2_url`
3. Clear `analysis.summary_image_selected_url`
4. Clear top-level `summary_image_url`
5. Then rerender

### Classic Variant Row Reference

The classic implementation (`dashboard_v3.js` line 12502-12523) renders each variant row with this structure. Match this density and information hierarchy:

```
┌──────────────────────────────────────────────────────────────────┐
│ [thumbnail 64×64]  5m ago                                        │
│                    Photorealistic image capturing the essence... │
│                    [Use this prompt] [Select this image] [Delete]│
└──────────────────────────────────────────────────────────────────┘
```

Key details from classic:
- Thumbnail: 64×64, rounded, overflow hidden
- Selected badge: "Selected" in a small colored pill on the thumbnail
- Timestamp: relative time (e.g. "5m ago", "11h ago") — `formatRelativeTime()` already exists in the editorial JS
- Prompt preview: first 120 chars of `v.prompt`, truncated
- Three action buttons per row: "Use this prompt", "Select this image" (hidden if already selected), "Delete" (red)
- Sorted by `created_at` descending (newest first)
- Row hover state for scannability

### Prompt Defaults

When opening Manage Images, derive default prompt text from multiple fallback sources (ported from `dashboard_v3.js` lines 12436-12447):

**AI1 default prompt:**
1. `analysis.summary_image_prompt` (if non-empty)
2. Last AI1 variant's prompt (iterate `summary_image_variants` in reverse, skip AI2 variants)
3. `analysis.summary_image_prompt_last_used`
4. Empty string

**AI2 default prompt:**
1. `analysis.summary_image_ai2_prompt` (if non-empty)
2. `analysis.summary_image_ai2_prompt_last_used` (if non-empty)
3. Last AI2 variant's prompt (iterate `summary_image_variants` in reverse, only AI2 variants)
4. Empty string

Show "Default:" helper line below textarea using `analysis.summary_image_prompt_original` (AI1) or `analysis.summary_image_ai2_prompt_original` (AI2). Only show if the field is non-empty.

## 4. Delete

Delete is the least problematic.

Keep the current calm confirmation modal, but ensure:

- copy is clear
- danger CTA is visually strong but controlled
- success cleanup still works

No major redesign needed unless spacing or typography needs consistency tuning.

## 5. Visual Standard

The admin surfaces should now match this standard:

- editorial shell on the outside
- compact utility on the inside

That means:

- more density than the current editorial admin attempt
- more restraint than the classic dashboard chrome

The right target is **classic usefulness, editorial calm**.

## 6. Acceptance Checklist

Do not call this done unless all of the following are true:

- the regenerate modal no longer feels like a sparse checkbox wall
- regenerate options are laid out in a compact, intentional system
- `Manage Images` no longer feels like a placeholder
- the variants area is the star of the modal, not an afterthought
- AI1 and AI2 workflows both feel complete
- selection state is visually obvious and technically correct
- AI1 local state updates both selected-image fields
- delete/delete-all update local state correctly before rerender
- no browser `prompt()` remains
- no browser `confirm()` remains
- the result is visibly closer in usefulness to classic than the current editorial attempt

## Explicit Instruction

If forced to choose between:

- “minimal editorial elegance”
- “practical classic-level usefulness”

choose the second, then style it cleanly.

The current failure mode is under-designed admin tooling.
This pass should correct that directly.
