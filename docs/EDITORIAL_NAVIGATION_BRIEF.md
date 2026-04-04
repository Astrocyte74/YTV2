# Editorial Navigation Brief

Date: April 2, 2026
Scope: homepage organization, topic selection, and sorting for `/editorial`
Status: active working brief

## Purpose

The homepage layout is now in a much stronger place visually.

The next question is not card styling. It is organization:

- how users move between `Recent` and topical views
- where sort belongs
- how topic selection should affect the hero, support row, and feed

This brief recommends a cleaner editorial navigation model inspired by Perplexity rather than a Google News-style full-width topic strip.

## Core Decision

Use a lightweight editorial nav with:

- `Recent` as the default primary view
- `Topics` as a dropdown menu

Do not add a full horizontal row of visible top categories across the page.

## Why This Direction

This is better than a Google News-style category strip because:

- it keeps the top chrome calm
- it avoids turning the page into a taxonomy dashboard
- it gives topic access without forcing category labels across the whole header
- it fits the current editorial direction better

## Recommended Primary Navigation

Primary editorial nav should become:

- `Recent`
- `Topics` ▾

Optional future additions:

- `Audio`
- `For You`

But do not add those now unless there is a clear product need.

For now, keep it minimal.

## Default Behavior

### `Recent`

This should be the default homepage mode.

In `Recent` mode:

- the newest studies drive the hero and support row
- the remaining studies populate the feed
- this matches the current mental model and is a good default

Yes, the most recent four studies should naturally occupy:

1. hero
2. three support cards

That is acceptable and desirable for the default view.

### `Topics`

`Topics` opens a dropdown menu listing top categories.

Selecting a topic should update the entire page state:

- hero
- support row
- feed

Topic selection should not just filter the lower grid while leaving the hero fixed.

The whole page should re-compose around the selected topic.

## Topic Menu Content

Populate the `Topics` dropdown from the strongest category options already available in filter data.

Guidelines:

- show 6 to 8 top categories max
- prefer human-friendly labels
- prioritize broad useful topics over overly technical or narrow labels

Examples:

- AI Software Development
- Science & Nature
- Reviews & Products
- History
- Computer Hardware
- News

If needed, some labels can be lightly editorialized for clarity, but do not invent categories that do not map cleanly to actual content.

## Sort Placement

Move sort out of the primary editorial nav.

Recommendation:

- keep `Newest/Oldest` inside `Refine`
- do not keep sort as a peer to `Recent` and `Topics`

Reason:

- sort is a mechanical control
- topic selection is an editorial navigation choice
- mixing them in one row makes the page feel more app-like

## Separation Of Concerns

Use this mental model:

### Primary Nav

Controls what kind of page the user is looking at.

Examples:

- `Recent`
- `Topics`

### Refine

Controls how the current page is filtered or sorted.

Examples:

- source
- content type
- audio
- sort

This is a cleaner separation than exposing everything at the same visual level.

## UX Rules

### When `Recent` is active

- show recent studies as the default editorial homepage
- hero and support cards come from the newest studies

### When a topic is active

- indicate the selected topic in the nav state
- rebuild the page from topic-matching studies
- keep the same layout structure:
  - hero
  - support row
  - feed

### Refine behavior

- refine applies within the current nav context
- example:
  - `Recent` + `With Audio`
  - `AI Software Development` + `YouTube`

## Do Not Do

For this pass:

- do not add a long horizontal topic strip
- do not show both a topic strip and a topic dropdown
- do not keep sort in the main nav row if `Recent` and `Topics` are added
- do not let topic selection only affect the bottom feed

## Implementation Guidance

Likely approach:

- add a new editorial nav row under or within the existing top bar
- move current sort select into the refine panel
- add a `currentEditorialMode` or equivalent state:
  - `recent`
  - `topic:<slug or label>`
- when mode changes, reload content and rebuild hero/support/feed from that result set

Use existing filter/category data where possible instead of inventing a separate topic source.

## Working Agent File Targets

- `static/editorial_dashboard.js`
- `static/editorial_dashboard.css`
- `dashboard_editorial_template.html`

## Acceptance Criteria

This pass is successful if:

- the homepage defaults cleanly to `Recent`
- `Topics` is available as a dropdown, not a long category bar
- choosing a topic re-composes the whole page
- sort moves into `Refine`
- the top area feels more editorial and less like a dashboard control row

## Clarifications

### Where topic data comes from

The `/api/filters` endpoint returns a `categories` array. Each entry has `value` (e.g. `"Technology"`), `count` (e.g. `286`), and `subcategories`. Use the top-level categories for the Topics dropdown. The current top categories are:

- Technology (286)
- AI Software Development (190)
- Science & Nature (156)
- Reviews & Products (127)
- History (89)
- Computer Hardware (87)
- Health & Wellness (85)
- How-To & DIY (75)

Show the top 8 by count. Do not hardcode this list — derive it from the filter data already loaded by `loadFilters()`, sorted by count descending, capped at 8.

### How topic selection drives content

When a topic is selected, set `this.state.filters.category = topicValue` and call `this.state.page = 1; this.loadContent()`. The existing `loadContent()` already sends all filter params (including `category`) to `/api/reports`. The response rebuilds hero + support + feed via `render()`. No new API needed.

When switching back to `Recent`, delete `this.state.filters.category` and reload.

### Where to place the nav row

Add the `Recent` / `Topics` nav inside the existing `#ed-topbar` area, below the brand/search row. Do not create a separate DOM element outside the topbar. The topbar already has `.ed-topbar__nav` as a mount point — render the nav tabs there.

### Sort control migration

The current sort is a `<select class="ed-sort__select">` in the topbar. Move it into the Refine panel (the filter popup created by `toggleRefine()`). Add a "Sort" label and the select inside the refine panel's filter groups. Remove the select from its current topbar position.

### Topic dropdown behavior

The Topics dropdown should open on click (not hover). Clicking outside closes it. When a topic is selected, the dropdown closes and the active topic name replaces "Topics" in the nav button (e.g. "Technology ▾"). Clicking `Recent` clears the topic and resets the button to "Topics ▾".

### Active state in nav

`Recent` should have an active visual state (e.g. underline or bold) when no topic is selected. When a topic is active, the topic button gets the active state and `Recent` becomes inactive. Only one nav item is active at a time.

### What this does not change

The hero card, support row, feed cards, side reader, audio player, and all existing refine filters (source, content_type, has_audio) remain unchanged. This pass only adds the nav row, moves sort into refine, and wires topic selection to the existing filter/content pipeline.
