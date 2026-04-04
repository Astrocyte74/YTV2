# Editorial Refine Menu Brief

Date: April 1, 2026
Scope: visual and interaction redesign for the `Refine` control in `/editorial`
Status: active working brief

## Purpose

The current `Refine` popover is better than the old full-width filter tray, but it still does not feel like a natural part of the editorial header.

Current problem:

- it looks like a floating popup, not a menu
- it is much heavier than the `Topics` dropdown
- it still exposes filter choices like chip walls inside a box
- it overlaps the page in a way that feels detached from the header system

This brief defines the next refinement pass.

## Core Decision

Make `Refine` behave like a true sibling to `Topics`.

That means:

- same interaction family
- same visual language
- same sense of being attached to the header

Do not keep the current “filter slab inside a popover” approach as the final direction.

## Design Goal

`Topics` should feel like:

- editorial navigation

`Refine` should feel like:

- lightweight page controls

Both should still look like they belong to the same system.

## Desired Behavior

### `Topics`

- dropdown menu
- simple list of topic choices

### `Refine`

- compact dropdown or popover
- anchored tightly to the `Refine` button
- smaller and more structured than the current panel
- no giant chip walls

## Recommended `Refine` Structure

Inside the `Refine` menu, organize controls as small grouped sections:

- `Sort`
- `Source`
- `Type`
- `Audio`

Do not include:

- `Category`
- `Topic`

Those belong to the `Topics` nav only.

## Interaction Model

### Option A: Single Compact Menu

One compact menu with grouped sections.

Each section contains:

- a small select
- short segmented controls
- compact text options

This is the preferred option for now.

### Option B: Two-Level Menu

If the single menu still feels crowded:

- first level lists:
  - `Sort`
  - `Source`
  - `Type`
  - `Audio`
- selecting one opens a submenu or swaps the panel content

Only use this if the single compact version still feels too dense.

## Visual Rules

### Placement

- attach directly under the `Refine` button
- align with the header/nav system
- reduce the sense that it is floating in the middle of the page

### Size

- narrower than the current popover
- less padding
- tighter grouping

### Styling

- same dark surface family as `Topics`
- similar border radius and shadow
- similar vertical rhythm
- lighter, cleaner typography

### Internal Controls

Avoid:

- long rows of chips with counts everywhere
- controls that look like faceted-search UI

Prefer:

- short option rows
- compact toggles
- simple segmented buttons
- restrained labels

## What Feels Wrong Today

The current `Refine` panel still reads like:

- dashboard filter UI compressed into a floating box

It does not yet read like:

- a lightweight editorial dropdown

That is the gap this pass should close.

## Recommendation For Counts

Do not show counts on every filter choice if that makes the menu noisy.

Counts can be:

- removed entirely
- shown only for some groups
- shown only on hover or secondary treatment

The menu should optimize for clarity before density.

## Do Not Do

For this pass:

- do not reintroduce a full-width filter tray
- do not keep giant chip clusters as the main interaction pattern
- do not include category/topic inside `Refine`
- do not make `Refine` visually larger than `Topics`

## Implementation Guidance

Likely approach:

- keep the existing `Refine` button and outside-click logic
- rebuild the internal panel markup so it uses grouped menu sections instead of chip walls
- reduce width and padding
- tighten its anchor position so it feels attached to the button

This is primarily a UI interaction cleanup, not a filtering-state rewrite.

## Working Agent File Targets

Use these local-machine paths:

- `/Users/markdarby16/16projects/ytv2/dashboard16/static/editorial_dashboard.js`
- `/Users/markdarby16/16projects/ytv2/dashboard16/static/editorial_dashboard.css`
- `/Users/markdarby16/16projects/ytv2/dashboard16/dashboard_editorial_template.html`

## Acceptance Criteria

This pass is successful if:

- `Refine` feels like a true menu, not a popup
- it visually belongs with `Topics`
- it no longer reads as a chip-wall filter panel
- it stays compact and header-anchored
- topic/category remains controlled only by the main nav
