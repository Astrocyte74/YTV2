# Editorial Refine Popover Brief

Date: April 2, 2026
Scope: active topic display and refine interaction for `/editorial`
Status: active working brief

## Purpose

The homepage navigation is now much closer to the intended editorial model:

- `Recent`
- `Topics` dropdown
- `Refine`

The next cleanup is to make the interaction model feel consistent with that design.

Two issues remain:

1. the active topic appears twice
2. the current refine interface feels too much like a dashboard filter tray

## Decision 1: Remove Duplicate Topic Chip

When a topic is chosen from the `Topics` dropdown, do not also show it as a removable chip in the page body.

Reason:

- it is already visible in the active navigation state
- repeating it as a chip is redundant
- it makes the page feel filter-driven rather than editorial

### Recommendation

Do not render a visible chip for the active nav topic/category.

Keep active chips only for secondary refinements such as:

- search
- source
- content type
- audio

If additional topic context is needed, use a quiet text label rather than a pill chip.

Example:

- `In AI Software Development`

But do not make that part of this pass unless the page clearly needs it.

## Decision 2: Replace Full-Width Refine Panel With Header Popover

The current `Refine` experience is functionally fine, but visually it breaks the editorial tone.

Current problem:

- opening `Refine` creates a wide filter slab
- it feels like faceted search UI
- it is visually heavier than the rest of the page

### Recommendation

Keep `Refine` in the header, but make it open a compact floating popover or dropdown panel attached to the button.

This should feel like:

- a modern header control
- a lightweight editing surface
- a secondary tool, not a page section

## Intended Interaction Model

### Top row

- `Recent`
- `Topics` dropdown
- `Refine`
- `Classic`

### `Topics`

- controls the editorial page context
- selecting a topic updates hero, support row, and feed

### `Refine`

- controls secondary filtering and sorting within the current topic context
- does not take over the page visually

## Popover Contents

The refine popover should contain:

- `Sort`
- `Source`
- `Type`
- `Audio`

Do not include `Category` in `Refine` if topic/category is already being controlled by the `Topics` nav.

That duplication should remain removed.

## UI Guidelines

### Popover layout

- anchored to the `Refine` button
- compact width
- dark surface with border and light shadow
- internal spacing that matches the rest of the editorial UI
- closes on outside click

### Controls

Use clean, compact controls:

- select for sort, or a two-option toggle
- compact pills, segmented controls, or short button groups for source/type/audio

Avoid:

- giant full-width rows
- large counts everywhere
- oversized chip walls

### Active filter visibility

After closing the popover:

- the active topic remains visible in nav only
- secondary active filters may still appear as chips below the header
- these chips should stay visually subtle

## Separation Of Concerns

Use this mental model:

- `Topics` chooses what kind of page you are looking at
- `Refine` adjusts the current page

That distinction should be obvious in both layout and behavior.

## Do Not Do

For this pass:

- do not show a duplicate chip for the active topic
- do not keep the large full-width refine tray
- do not reintroduce category/topic controls inside the refine popover
- do not add more top-level nav items

## Implementation Guidance

Likely approach:

- update chip rendering so `category` is excluded from visible active chips when it is the active nav topic
- replace the current inserted refine panel block with a positioned popover attached to the header button
- keep existing filter logic and state handling where possible
- preserve outside-click close behavior

This is primarily a UI-shell change, not a filtering-logic rewrite.

## Working Agent File Targets

- `static/editorial_dashboard.js`
- `static/editorial_dashboard.css`
- `dashboard_editorial_template.html`

## Acceptance Criteria

This pass is successful if:

- the selected topic is not duplicated as a chip
- `Refine` opens as a compact header popover
- the popover contains sort and secondary filters only
- the top area feels more editorial and less like a dashboard control surface

## Clarifications

### Excluding topic chip

In `renderFilterChips()` (currently around line 547), the loop over `activeFilters` includes `category`. Add a skip: if `key === 'category'`, continue. The topic is already shown in the nav tab — no chip needed. This is a one-line guard, not a restructure.

### Popover positioning

The current refine panel is created by `toggleRefine()` (around line 671) and inserted as a full-width block in the DOM. Replace this with an absolutely-positioned popover anchored to the Refine button. Key CSS:

- `position: absolute` or `fixed` relative to the button
- `top` aligned to bottom of the button
- `right: 0` (since Refine is on the right side of the topbar)
- `z-index` above content
- max-width ~320px
- dark surface (`var(--ed-color-surface)`) with subtle border and shadow

The popover container is the same `#ed-quick-filters` element — just restyle it from a full-width slab to a compact floating panel. The internal filter groups (Sort, Source, Type, Audio) stay the same markup.

### Popover open/close

The current outside-click close behavior (click delegation around line 776) already works. Keep it. The only change is that clicking Refine toggles the popover visibility instead of inserting/removing a DOM block. Use a CSS class like `.ed-quick-filters--open` to show/hide with `display: none` / `display: block`.

### What this does not change

Topic selection, nav tabs, hero, support row, feed cards, side reader, audio player all remain unchanged. This pass only affects: (1) chip rendering excludes category, (2) refine panel becomes a compact popover.
