# Editorial Card System Plan

Date: April 2, 2026
Scope: next visual pass for `/editorial`
Status: active working brief

## Purpose

The current homepage structure is better than the earlier category-led version, but the card system is still doing too many jobs with too few patterns.

Current problem:

- hero works reasonably well
- the second row is visually awkward
- lower feed cards are still not differentiated enough

The page needs a clearer hierarchy of card types.

## Core Decision

Do not keep using the current horizontal support card as the main pattern for the second row.

Instead, move to a 3-tier card system:

1. hero card
2. support card
3. feed row card

This is the simplest way to get closer to the Perplexity-style editorial feel.

## Target Structure

### Block 1: Hero

Keep the current hero model:

- large image
- strong serif headline
- short summary/deck
- restrained metadata
- primary action(s)

The hero should remain the only card with visible buttons by default.

### Block 2: Support Row

Replace the current horizontal support cards with Perplexity-style support cards.

Desktop target:

- 3 cards across
- image on top
- title below
- light metadata below title
- no excerpt
- no visible `Read` or `Watch` buttons
- entire card is clickable

This row should answer:

"What are the next 3 stories worth noticing?"

Visual goal:

- strong image presence
- larger titles than feed items
- cleaner and calmer than the current support cards

### Block 3: Feed

All remaining items should use a distinct compact feed treatment.

Desktop target:

- 2 or 3 columns depending on viewport
- each item is a compact horizontal row
- small thumbnail on the left
- title on the right
- one metadata line only
- no excerpt
- no buttons
- entire row clickable

This block should be optimized for scanning rather than showcasing.

## Why This Change

Right now the second-row cards are in an awkward middle state:

- too large to feel like feed rows
- too cramped to feel like true featured tiles

Borrowing more directly from the Perplexity layout solves that:

- support row becomes more visual and editorial
- lower feed becomes more compact and scannable
- hierarchy becomes obvious at a glance

## Design Rules

### Hero Rules

- keep deck text
- keep action buttons
- keep strong serif title
- keep larger image-to-text balance

### Support Card Rules

- image-first
- no excerpt
- no action buttons
- title should get more space than current support cards
- metadata should be quiet and short
- cards should breathe more than feed rows

### Feed Row Rules

- thumbnail-led but compact
- no excerpt
- no action buttons
- title should be readable in 2 lines max
- metadata line should include only useful essentials
- rows should feel clean and fast to scan

## Interaction Rules

For all non-hero cards:

- clicking anywhere on card opens the editorial side reader
- remove inline `Read` / `Watch` buttons from support and feed cards
- keep secondary actions inside the side reader instead

Why:

- fewer repetitive controls
- less UI noise
- more editorial, less app-like

## Layout Recommendation

### Desktop

- hero at top
- support row below hero
- feed below support row

Support row:

- 3 columns
- equal card heights where possible

Feed:

- 3 columns if width supports it cleanly
- otherwise 2 columns

### Tablet

- hero stacked
- support row becomes 2 columns
- feed becomes 2 columns

### Mobile

- hero stacked
- support cards become single-column vertical cards
- feed becomes single-column compact rows

## Data Allocation Recommendation

Suggested homepage allocation:

1. `heroItem`
   - first ranked story

2. `supportItems`
   - next 3 strong stories
   - keep light source/topic variety when possible

3. `feedItems`
   - all remaining stories
   - no category sectioning

Do not over-engineer the support selection.

Simple rules are enough:

- avoid showing 3 nearly identical stories if obvious alternatives exist
- otherwise preserve ranking order

## What To Remove

For this pass, remove from support and feed cards:

- excerpts
- inline `Read` buttons
- inline `Watch` buttons
- extra category chips
- unnecessary border clutter if it hurts readability

## What To Keep

- top bar
- search
- sort
- refine control
- side reader
- audio player
- existing APIs and route structure

## Acceptance Criteria

The new card system should make these statements true:

- the second row feels intentional and editorial, not cramped
- the feed below clearly shifts into scan mode
- non-hero cards are visually quieter
- the page is easier to read top-to-bottom
- the hierarchy is obvious without section labels

## File Targets

Primary implementation files:

- `static/editorial_dashboard.js`
- `static/editorial_dashboard.css`

This document should be used together with:

- `docs/EDITORIAL_LAYOUT_PIVOT_BRIEF.md`

If the two documents conflict, this card-system brief wins for support-row and feed-card decisions.

## Part 2: Bigger Lower Feed

Date: April 2, 2026
Status: active addendum

### Why This Addendum Exists

After implementing the compact lower feed, the page is cleaner, but the smaller feed rows still feel too slight.

The support cards are now the strongest non-hero pattern on the page.

That suggests a simpler direction:

- stop using a separate compact-row card for the lower feed
- reuse the optimized support-card language below the fold
- keep one coherent non-hero card family across the homepage

### New Decision

Use the same visual family for:

- the second row under the hero
- the main feed below it

Do not keep the compact horizontal feed-row system as the default long-term direction.

### Recommended Homepage Structure

1. Hero
   - unchanged

2. Support row
   - 3 larger vertical cards
   - this is the current optimized second-row style

3. Main feed
   - continue with vertical cards in a grid
   - same overall card language as support row
   - may be slightly tighter than the support row, but should clearly be the same family

### Feed Card Rules

The lower feed cards should:

- keep image on top
- keep title below image
- keep one quiet metadata line
- remove excerpts
- remove inline `Read` and `Watch` buttons
- open the side reader on click

### Difference Between Support And Feed

Support cards and feed cards should be siblings, not different design species.

Recommended distinction:

- support cards
  - slightly larger
  - slightly more spacing
  - top of page emphasis

- feed cards
  - slightly smaller title
  - slightly tighter gap
  - more repeatable in a grid

But both should still look like members of the same editorial card system.

### Why This Is Better

Benefits:

- more premium editorial feel
- more visual consistency
- less context switching between card styles
- lower part of the page still feels like stories, not utility rows

Tradeoff:

- fewer items visible at once
- scanning density drops somewhat

That tradeoff is acceptable if the product goal is discovery and reading, not operational density.

### What To Remove From The Current Direction

For this pass:

- do not keep the compact horizontal feed-row as the primary feed treatment
- do not introduce another third non-hero card style
- do not add back excerpts or action buttons to the lower feed

### Implementation Guidance

Likely approach:

- keep `renderFeatureCard()` as the base non-hero card factory
- introduce a feed-specific modifier class if needed
- render support cards and feed cards from the same core markup structure
- use CSS modifiers for scale and spacing rather than two unrelated layouts

Suggested rendering model:

- support block uses 3 cards
- feed block uses repeated vertical cards in a 3-column grid on wide desktop
- collapse to 2 columns on medium screens
- collapse to 1 column on mobile

### Working Agent File Targets

- `static/editorial_dashboard.js`
- `static/editorial_dashboard.css`

### Acceptance Criteria For Part 2

This pass is successful if:

- the lower feed feels materially bigger and more story-like
- the page uses one coherent non-hero card language
- the support row still feels slightly more prominent than the main feed
- the page no longer drops into a small utility-feed feeling below the second row

## Part 1 Clarifications (still active)

### Support card count

`getSupportItems()` is already called with max 3. No change needed for Part 2.

### Click handler for non-hero cards

The current click delegation handles `.ed-card` click → opens side reader via `data-video-id`. After Part 2 changes, verify that clicking anywhere on feed cards still triggers the reader. The `data-video-id` attribute must stay on the outermost `<article>` element.

### Support card CSS class

Uses `.ed-card-feature` with vertical (image-top, text-below) layout overridden within `.ed-support`. No new card class needed.

## Part 2 Clarifications

### Feed rendering

Replace `renderCompactCard()` calls in the feed block with `renderFeatureCard()`. Both support and feed blocks now use the same card factory function.

### Feed CSS class

Keep using `.ed-feed` as the feed container. Inside it, cards use `.ed-card-feature` (same as support). Add a CSS modifier to distinguish feed cards from support cards:

- `.ed-feed .ed-card-feature` — slightly smaller title font, tighter gap, less padding
- `.ed-support .ed-card-feature` — current treatment, slightly more spacious

Do not use `.ed-card-compact` for the feed anymore.

### Feed grid

Use `grid-template-columns: repeat(auto-fill, minmax(280px, 1fr))` for `.ed-feed`. This gives 3 columns on wide desktop, 2 on medium, 1 on mobile. Do not hardcode column counts.

### renderCompactCard cleanup

After Part 2, `renderCompactCard()` is no longer called anywhere on the homepage. Delete the function. Also delete any CSS rules that only apply to `.ed-card-compact` elements (thumbnail size, compact-specific spacing, etc.). If `.ed-card-compact` is still referenced elsewhere, leave the CSS but note it as dead code.

### What this replaces

Part 2 replaces the compact horizontal feed from commit f69dad1. The hero, topbar, refine control, side reader, audio player, and support row are unchanged.
