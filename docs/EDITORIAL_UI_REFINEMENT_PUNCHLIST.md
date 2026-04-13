# Editorial UI Refinement Punchlist

Date: March 31, 2026
Scope: visual and interaction refinements for the editorial dashboard at `/editorial`

## Purpose

This document is a focused working brief for the next editorial UI pass.

It is intentionally narrower than the larger redesign plans. The goal here is not architecture. The goal is to improve what is already built so the page feels more editorial, less like a filter dashboard with a hero attached.

## Current Problems

### 1. Top filter chips are too prominent

Right now the filter rows:

- take visual priority away from the hero
- make the page feel control-first rather than story-first
- create a dense, app-like first impression

### 2. Right rail is too weak

The current `Recent` rail:

- has thumbnails that are too small to matter
- has too many items competing in a narrow space
- feels like overflow content, not curation
- is too literal in concept

### 3. The page still lacks editorial pacing

The target inspiration works because it has:

- a clear first focal point
- quieter chrome
- supporting modules that feel chosen, not dumped

The current editorial page still needs more hierarchy and restraint.

## Design Direction

The page should feel like:

- curated
- calm
- content-led
- selective

It should not feel like:

- a control panel
- a faceted search app with bigger cards
- a mini dashboard stuffed into an editorial shell

## Priority Decisions

### Decision 1: Demote top filters

Recommendation:

- Keep search visible.
- Keep sort visible.
- Hide the large chip groups by default.
- Replace the always-open filter rows with one understated refinement control.

Preferred pattern:

- `Search`
- `Sort`
- `Refine` button

When filters are active:

- show a slim active-filter row below the top bar
- only show active filters, not the full filter universe

### Decision 2: Replace the `Recent` rail with curated modules

Recommendation:

Do not keep the rail as a single chronological list.

The rail should become 2-3 small editorial modules such as:

- `Continue`
  - recently opened or listened items
- `Related`
  - items related to the hero topic/category/source
- `Worth Your Time`
  - longer-form, audio-ready, or especially strong summaries
- `Quick Pivots`
  - topic/source jump links instead of cards
- `From This Source`
  - supporting items from the hero’s source or channel

Initial recommendation:

Use these three modules:

- `Continue`
- `Related to This Story`
- `Quick Pivots`

That gives the rail more editorial purpose than `Recent`.

### Decision 3: Make rail cards fewer and larger

Recommendation:

- fewer cards
- larger thumbnails
- stronger type hierarchy
- one metadata line max

The rail should show fewer things better, not more things worse.

## Concrete UI Changes

### A. Top Bar And Filters

#### Current

- search
- sort
- large chip groups always visible

#### Target

- top bar: brand, search, sort, classic link
- secondary line: small `Refine` button
- active filters row only when filters exist

#### Tasks

- [ ] Remove always-visible source/category/type/audio chip rows from the default page state.
- [ ] Add a compact `Refine` trigger in the header area.
- [ ] Put full filters in a popover, dropdown panel, or drawer.
- [ ] Show active filters only when selected.
- [ ] Keep active filters visually subtle:
  - smaller height
  - lower contrast
  - tighter spacing

#### Visual Notes

- filter UI should feel like tooling in the background
- hero content should remain the first thing the eye lands on

### B. Hero Area

#### Goal

Increase the sense that the hero is the main story of the page.

#### Tasks

- [ ] Increase spacing above and below the hero block.
- [ ] Keep metadata line lighter and more restrained.
- [ ] Let the headline dominate more strongly.
- [ ] Reduce nearby UI noise so the hero can lead.
- [ ] Consider slightly increasing image prominence or text contrast if needed.

#### Visual Notes

- hero should feel like an editorial lead story, not just the first result

### C. Right Rail

#### Current

- one narrow `Recent` list
- small thumbnails
- high density
- low impact

#### Target

A curated support rail with 2-3 modules.

#### Module Recommendation

##### Module 1: `Related to This Story`

Use for:

- items from same category
- same source
- same channel
- or same broad topic cluster as hero

This should be the primary rail module for now.

##### Module 2: `Quick Pivots`

Use for:

- topic jump buttons
- source jump buttons
- curated links like:
  - `AI Coding`
  - `Science`
  - `History`
  - `Audio Ready`

This gives the rail variety without requiring another card stack.

#### Tasks

- [ ] Remove or demote the current generic `Recent` list.
- [ ] Build `Related to This Story` module — filter already-loaded `allItems` client-side by matching hero's category, source, or channel. No new API call needed.
- [ ] Build `Quick Pivots` module — derive pivot buttons from `this.state.filterOptions` (top categories, sources, audio filter). No new API call needed.
- [ ] Create module headings with stronger editorial labels.
- [ ] Increase thumbnail size for rail cards.
- [ ] Reduce visible item count per module (3-5 items max per module).
- [ ] Limit metadata to one concise line.
- [ ] Add more vertical spacing between modules.

#### Visual Notes

- the rail should feel curated, not chronological by default
- modules should look intentionally different from the main content stream

### D. Card Density Below The Hero

#### Goal

Avoid dropping immediately into a uniform content wall.

#### Tasks

- [ ] Keep 2-3 visual densities below the hero.
- [ ] Consider reducing the number of feature cards per section.
- [ ] Let compact cards do more work for scanning.
- [ ] Avoid making every section feel equally loud.

#### Visual Notes

- rhythm matters more than volume
- a page feels editorial when some items are clearly supporting items

## Suggested Implementation Order

### Pass 1

- hide/demote top chip rows
- add `Refine` control
- keep active filter chips only when in use

### Pass 2

- redesign right rail from `Recent` list into modules
- increase rail thumbnail size
- reduce rail item count

### Pass 3

- retune hero spacing and hierarchy
- rebalance section density below hero

## Acceptance Criteria

The refinement pass is successful if:

- the hero is visually more dominant than filters
- the top of the page feels calmer
- the right rail feels curated, not incidental
- thumbnails in the rail are large enough to actually matter
- the page reads as editorial before it reads as tooling

## Non-Goals

This pass should not try to:

- redesign the backend contract
- rebuild the side reader
- add cutover logic
- chase full feature parity with classic
- add generic filler widgets just to occupy rail space

## Immediate Recommendation To The Working Agent

Start with these exact changes:

- [ ] collapse the full quick-filter chip rows behind a `Refine` control
- [ ] show only active filters by default
- [ ] replace `Recent` with `Related to This Story` (client-side filtering from `allItems`) plus `Quick Pivots` (derived from `filterOptions`)
- [ ] make rail cards larger and fewer
- [ ] skip `Continue` module — no session history API exists yet, do not stub or fake it

Those four changes should materially improve the editorial feel without reopening the broader architecture work.
