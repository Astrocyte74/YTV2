# Editorial Reader Redesign Brief

Visual and structural pass on the editorial side reader. No new data features — layout, typography, and interaction polish only.

**Applies to:**
- `static/editorial_dashboard.css`
- `static/editorial_dashboard.js` (only `renderReaderContent()` HTML template strings)

**Do not:**
- Add a centered modal mode
- Change any data loading or API logic
- Change audio player behavior
- Touch the classic dashboard reader (separate component)

## Current State

The reader is a 560px fixed right panel that slides in. Structure (JS line 1104):

```
.ed-reader (fixed, right, 560px, z-index 300)
  .ed-reader__header (flex, close button only)
  .ed-reader__body (scrollable)
    .ed-reader__meta (channel, duration, category)
    h1.ed-reader__title (1.4rem)
    .ed-reader__thumb (16:9 image)
    .ed-reader__actions (Full page, Watch source, Listen)
    .ed-reader__summary (rendered HTML)
```

Current CSS values:
- Width: `560px`
- Title: `1.4rem`, `font-weight: 700`, `line-height: 1.3`
- Body padding: `var(--ed-space-md) var(--ed-space-lg)`
- Summary: `0.95rem`, `line-height: 1.75`
- Summary headings: h1=1.25rem, h2=1.1rem, h3=1rem
- Backdrop: `rgba(0, 0, 0, 0.5)`
- Panel background: `var(--ed-color-bg)` (same as page)

## What To Improve

### 1. Width and Presence

The reader should feel like a reading workspace, not a narrow drawer.

- Widen to **720px** (from 560px)
- Keep `max-width: 90vw` for smaller screens
- The inner text column inside `.ed-reader__summary` should be constrained to **~520px max** so lines don't stretch too wide. Add `max-width: 520px` to `.ed-reader__summary`
- The title, meta, and actions can use the full panel width — only the prose/summary text needs to be narrower

### 2. Header — Close Button Alone Is Wasteful

The current header is a full-width row that only contains the close button. This wastes vertical space.

**Replace the header row entirely.** Instead of a separate header bar:
- Put the close button as a small fixed-position `×` in the top-right corner of the reader, absolutely positioned within the reader panel
- Remove `.ed-reader__header` as a separate flex row
- This frees up space and removes the visual border between "header" and "body"

### 3. Title Block — More Breathing Room

The title and meta area should feel composed:

- Increase title size from `1.4rem` to `1.6rem`
- Increase title `margin-bottom` from `var(--ed-space-sm)` to `var(--ed-space-md)`
- Meta row should be quieter — same `0.75rem` size as card meta, slightly reduced opacity
- Add a subtle separator (thin border or increased gap) between the title block and the actions

### 4. Image — Less Dominant

The 16:9 thumbnail pushes content down too far in the reader.

- Reduce from `aspect-ratio: 16/9` to `aspect-ratio: 16/10` or use a `max-height: 240px` with `object-fit: cover`
- Add a small border-radius (already has `var(--ed-radius-md)`)
- Consider moving the image BELOW the actions row, so the text flow is: meta → title → actions → image → summary. This puts text first and image as supporting content.
- The HTML order change goes in `renderReaderContent()` (JS ~line 1149-1154)

### 5. Actions — Cleaner Grouping

- Keep `Full page` as the primary action (use `ed-btn--primary`)
- `Watch source` and `Listen` are secondary (use `ed-btn--secondary` or `ed-btn--ghost`)
- Wrap in a slightly more spaced layout — increase gap from `0.5rem` to `0.6rem`
- Rename `Full page` label to `Open full report` in the JS template

### 6. Reading Typography

The summary/prose area needs to feel like a real reading surface:

- Keep summary at `0.95rem` but increase line-height from `1.75` to `1.8`
- Increase paragraph spacing: change `margin-bottom` on `p` from `var(--ed-space-sm)` to `0.75rem`
- Summary headings should be slightly more distinct — increase h2 from `1.1rem` to `1.15rem`
- List items: increase `li` margin from `0.25rem` to `0.35rem`
- Add `color: var(--ed-color-muted)` to the summary text (not full bright white — easier on the eyes for long reading)

### 7. Layering and Backdrop

The backdrop should make the reader feel like a selected layer:

- Increase backdrop opacity slightly: from `rgba(0, 0, 0, 0.5)` to `rgba(0, 0, 0, 0.6)`
- Add a subtle left border/shadow on the reader panel itself: `box-shadow: -4px 0 24px rgba(0, 0, 0, 0.3)` to create depth between the reader and the browse layer
- The reader background should be `var(--ed-color-bg)` (same as page) — keep it consistent

## Layout Order Change (JS Template)

Current order in `renderReaderContent()`:
```
header (close button row)
meta
title
image
actions
summary
```

New order:
```
close button (absolutely positioned, no header row)
meta
title
actions
image
summary
```

This puts interactive controls earlier and lets the image sit between actions and the reading text.

## Acceptance Standard

This pass is successful if:
- The reader feels substantially more like a reading surface than a utility drawer
- Text starts sooner (no wasted header row, image moves below actions)
- Title and meta have more breathing room
- The prose column is constrained (~520px) even in the wider panel
- Actions are clearly prioritized (primary vs secondary)
- Summary text is comfortable for extended reading (muted color, loose line-height)
- The backdrop creates clear visual separation from the browse layer
