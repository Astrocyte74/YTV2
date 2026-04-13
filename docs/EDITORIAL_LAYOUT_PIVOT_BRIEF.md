# Editorial Layout Pivot Brief

Date: April 1, 2026
Scope: homepage layout direction for `/editorial`
Status: active working brief for the next design pass

## Purpose

This document updates the editorial direction after the first refinement passes.

The current `/editorial` page is cleaner than the original card wall, but it is still too driven by backend structure:

- homepage rail is anchored too tightly to the hero
- sections are named directly from raw categories
- supporting stories are still too small and too feed-like
- the page feels grouped and indexed, not curated

The target is closer to the feel of Perplexity News:

- one clear lead story
- a few larger supporting stories
- quieter structural labels
- less explicit taxonomy on first view
- stronger sense of editorial judgment

## Core Decision

Do not keep iterating on the current "hero + category sections + related rail" structure as the primary homepage model.

Instead, pivot the homepage toward:

- hero
- supporting story row
- flowing story feed
- optional lightweight rail or no rail

This is a layout change, not a backend or architecture change.

## What Should Change

### 1. Remove `Related to This Story` from the homepage

Reason:

- it only makes sense in relation to the hero
- it is more appropriate for reader context than browse context
- it makes the homepage rail feel narrow and over-explained

Recommendation:

- remove it from the homepage entirely
- keep "related" logic available for the side reader if useful later

### 2. Stop using raw categories as the main page structure

Right now the page groups stories under labels like:

- `AI Software Development 11`
- `Computer Hardware 2`

That may be technically correct, but it is not editorially strong.

Problems:

- category names are too mechanical
- counts make the page feel like search results
- section boundaries are determined by metadata, not by presentation needs

Recommendation:

- stop auto-sectioning the whole homepage by `primary category`
- use category and topic metadata for ranking, clustering, and optional pivots
- do not let taxonomy dictate the visible layout

### 3. Make supporting stories larger

The current sub-story treatment is still too dense.

Problems:

- thumbnails are too small
- titles do not have enough room
- too many cards appear too quickly below the hero
- the page drops back into "result list" mode too fast

Recommendation:

- show fewer supporting items at once
- give them more width and breathing room
- make the first row below hero feel chosen, not accumulated

## Target Homepage Model

### Block 1: Lead Story

One clear hero story:

- large image
- strong serif headline
- short deck
- restrained metadata
- primary action

This stays.

### Block 2: Supporting Stories

Immediately below the hero, show 2 to 4 stronger supporting stories.

Preferred treatment:

- larger horizontal cards or medium vertical cards
- each card should feel like a real story, not a tiny linked tile
- no tiny multi-column compact grid here

This block should answer:

"What else is important right now?"

### Block 3: Main Feed

Below the support block, switch into a calmer story feed.

Preferred treatment:

- medium-density cards
- 2-column layout on desktop
- no hard category sectioning at first
- light metadata only

Optional:

- later in the page, introduce one or two softer topical bands if needed
- examples: `AI`, `Science`, `History`

These should be editorial labels, not raw category dumps with counts.

## Rail Recommendation

### Preferred Option

Remove the right rail from the homepage for the next pass and give that space back to the feed.

Why:

- the current rail weakens the page more than it helps
- the homepage is strong enough without a hero-anchored side stack
- Perplexity's feel comes partly from letting content dominate the width

### Acceptable Fallback Option

If removing the rail is too disruptive for this pass, keep a very minimal rail with only one lightweight module:

- `Quick Pivots`

Rules for the fallback rail:

- no `Related to This Story`
- no mini recent list
- no dense card stack
- use buttons or very simple links only

## Section Labels And Counts

For the next pass:

- remove visible item counts from homepage headings
- avoid headings like `AI Software Development 11`
- if a label is needed, use something softer and shorter

Examples:

- `In AI`
- `Worth Watching`
- `From YouTube`
- `Audio Ready`

These do not need to map 1:1 to backend taxonomy.

## Implementation Guidance

### Keep

- current top bar structure
- search
- sort
- `Refine`
- side reader
- audio player
- current route and API contracts

### Change

- homepage layout algorithm
- section rendering logic
- rail rendering logic
- card sizing and density below hero

### Do Not Do

- do not add more rail modules
- do not create more category sections
- do not expose more counts or metadata noise
- do not let backend categories directly define the homepage skeleton

## Practical Rendering Plan

Use the existing loaded item set, but render it differently.

Suggested client-side allocation:

1. `heroItem`
   - first ranked item

2. `supportItems`
   - next 2 to 4 items
   - optionally bias toward variety so they do not all come from the same source

3. `feedItems`
   - everything after that
   - render in medium cards without hard category grouping

Optional later enhancement:

- derive soft topical clusters from the feed
- only surface a cluster if it is visually useful and clearly populated

## Clarifications

### Card format for Block 2 (Supporting Stories)

Use horizontal cards (image left, text right) for supporting stories. The hero is already a full-width vertical card, so horizontal cards give visual variety. Each card should be roughly 50/50 image-to-text and feel like a real story presentation, not a compact list tile.

### Variety logic for supportItems

Bias toward different `source` values. If the first 4 items after the hero are all from the same source, scan up to 8 items and pick up to 2 from any single source. This keeps the supporting row from looking like a single-feed dump. If the first 4 are already mixed, use them as-is.

### Progressive load behavior

- `heroItem` and `supportItems` are assigned from the first page of results only
- Progressive load (scroll / load more) appends to `feedItems` only
- Hero and support block do not shift or reassign on subsequent pages

### Relationship to prior refinement work

This brief replaces the Pass 4 section-density model (1 feature card per category section). The category-section structure is removed entirely. The hero spacing and filter demotion from earlier passes are preserved.

### Fallback rail: Quick Pivots only

If the rail is kept, render only the Quick Pivots module (pivot buttons in a vertical stack). No card stack, no thumbnails, no Related section. The rail should feel like a quiet sidebar shortcut, not a content column. If removing the rail entirely is clean, prefer that.

## Acceptance Criteria

The next homepage pass should make these statements true:

- the page no longer feels organized by taxonomy first
- the first screen emphasizes stories over structure
- supporting stories are large enough to feel intentional
- the homepage rail is either gone or minimal
- the layout reads closer to "editorial discovery" than "categorized results"

## File Targets

Primary implementation files:

- `static/editorial_dashboard.js`
- `static/editorial_dashboard.css`

Optional note:

- this brief should be read as a follow-on to `docs/EDITORIAL_UI_REFINEMENT_PUNCHLIST.md`
- when they conflict, this brief wins for homepage layout decisions
