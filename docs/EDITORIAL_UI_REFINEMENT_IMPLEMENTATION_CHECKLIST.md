# Editorial UI Refinement Implementation Checklist

Date: March 31, 2026
Companion doc: `EDITORIAL_UI_REFINEMENT_PUNCHLIST.md`
Target route: `/editorial`

## Purpose

This is the implementation checklist for the next editorial UI refinement pass.

It translates the punch-list into:

- exact files to edit
- exact functions and selectors to target
- recommended change order
- acceptance checks for each area

## Current Implementation Targets

### Template

File:

- [dashboard_editorial_template.html](../dashboard_editorial_template.html)

Current mount points:

- `#ed-topbar`
- `#ed-main`
- `#ed-hero`
- `#ed-sections`
- `#ed-rail`
- `#ed-player`

### JS

File:

- [editorial_dashboard.js](../static/editorial_dashboard.js)

Current key functions:

- `renderTopbar()` at [editorial_dashboard.js#L411](../static/editorial_dashboard.js#L411)
- `renderFilterChips()` at [editorial_dashboard.js#L440](../static/editorial_dashboard.js#L440)
- `renderQuickFilters()` at [editorial_dashboard.js#L506](../static/editorial_dashboard.js#L506)
- `render()` rail section at [editorial_dashboard.js#L375](../static/editorial_dashboard.js#L375)
- `groupByCategory()` at [editorial_dashboard.js#L401](../static/editorial_dashboard.js#L401)

### CSS

File:

- [editorial_dashboard.css](../static/editorial_dashboard.css)

Current relevant selectors:

- `#ed-topbar` at [editorial_dashboard.css#L44](../static/editorial_dashboard.css#L44)
- `#ed-rail` at [editorial_dashboard.css#L117](../static/editorial_dashboard.css#L117)
- `.ed-quick-filters` at [editorial_dashboard.css#L127](../static/editorial_dashboard.css#L127)
- `.ed-filter-group` at [editorial_dashboard.css#L136](../static/editorial_dashboard.css#L136)
- `.ed-filter-btn` at [editorial_dashboard.css#L151](../static/editorial_dashboard.css#L151)
- `.ed-filter-chips` at [editorial_dashboard.css#L179](../static/editorial_dashboard.css#L179)
- `.ed-card-hero` at [editorial_dashboard.css#L212](../static/editorial_dashboard.css#L212)
- `.ed-section__grid` at [editorial_dashboard.css#L277](../static/editorial_dashboard.css#L277)
- `.ed-card-compact` at [editorial_dashboard.css#L343](../static/editorial_dashboard.css#L343)
- `.ed-rail__title` at [editorial_dashboard.css#L499](../static/editorial_dashboard.css#L499)

## Implementation Strategy

Do this as a visual refinement pass, not a structural rewrite.

Use the current editorial architecture as-is and focus on:

1. demoting visible filter controls
2. upgrading the right rail from one weak list to curated modules
3. increasing hero dominance
4. reducing repeated visual density below the hero

## Pass 1: Demote The Top Filter Wall

### Goal

Search and sort stay visible. The full chip/filter universe stops dominating the top of the page.

### Files

- [editorial_dashboard.js](../static/editorial_dashboard.js)
- [editorial_dashboard.css](../static/editorial_dashboard.css)
- possibly [dashboard_editorial_template.html](../dashboard_editorial_template.html) if a dedicated refine mount is useful

### JS Tasks

#### `renderTopbar()`

- [ ] Add a compact `Refine` control next to search/sort.
- [ ] Keep the `Classic` link but visually subordinate it.
- [ ] Do not render full filter rows in the default top state.

#### `renderQuickFilters()`

- [ ] Change this from always-visible rows into a hidden or collapsible refinement panel.
- [ ] Render the filter groups only when refine mode is open.
- [ ] Preserve the same filter data and behavior.

#### `renderFilterChips()`

- [ ] Keep active filter chips visible only when filters/search are active.
- [ ] Make sure active chips remain outside the hidden refine panel.
- [ ] Keep chip labels human-readable.

#### Event handling

- [ ] Add click handling for opening/closing the refine panel.
- [ ] Ensure clicking filter buttons still updates state and rerenders correctly.
- [ ] If using a popover, support close on outside click or Escape.

### CSS Tasks

- [ ] Reduce default top control height/weight.
- [ ] Style the new `Refine` control as understated.
- [ ] Lower the visual contrast of active chips.
- [ ] Ensure the refined filter panel reads as secondary UI, not headline UI.

### Acceptance Checks

- [ ] On first load, search and hero dominate more than filters.
- [ ] No full chip wall is visible by default.
- [ ] Filters remain accessible in one click.
- [ ] Active filters remain visible when in use.

## Pass 2: Rebuild The Right Rail

### Goal

Replace the current weak `Recent` rail with 2-3 curated modules that feel editorial.

### Files

- [editorial_dashboard.js](../static/editorial_dashboard.js)
- [editorial_dashboard.css](../static/editorial_dashboard.css)

### Recommended Module Set

Initial recommendation:

- `Related to This Story` — filter already-loaded `allItems` client-side by hero's category, source, or channel. No new API call needed.
- `Quick Pivots` — derive pivot buttons from `this.state.filterOptions` (top categories, sources, audio filter). No new API call needed.

Do NOT build a `Continue` module — no session history API exists yet. Do not stub or fake it.

### JS Tasks

#### `render()` rail block

Current rail render:

- title `Recent`
- last 10 items
- compact cards only

Replace with:

- [ ] `renderRailModules(hero, items)` helper or equivalent inline composition.
- [ ] Build a `Related to This Story` module — filter `this.state.allItems` client-side by hero's category (primary), source or channel (fallback). Limit to 3-5 items.
- [ ] Build a `Quick Pivots` module — derive pivot buttons from `this.state.filterOptions` (top categories, sources, `With Audio` filter). These are clickable filter shortcuts, not cards.
- [ ] Limit each card-based module to fewer items.
- [ ] Use larger card format for rail items, not the current tiny compact stack everywhere.

#### New rail render helpers

- [ ] Add `renderRailModuleTitle(title)` helper if useful.
- [ ] Add `renderRailFeatureCard(item)` or `renderRailCompactCard(item)` variant with larger image.
- [ ] Add `renderPivotButtons()` or `renderPivotLinks()` for non-card rail content.

### CSS Tasks

- [ ] Increase rail card thumbnail size.
- [ ] Increase spacing between rail modules.
- [ ] Reduce rail item count per visible screen.
- [ ] Make rail headings feel editorial, not utilitarian.
- [ ] Avoid the rail becoming a second dense list.

### Acceptance Checks

- [ ] Rail no longer reads as a generic chronological feed.
- [ ] Thumbnails are large enough to matter visually.
- [ ] The rail feels curated and supportive of the hero.

## Pass 3: Hero Hierarchy Tuning

### Goal

Make the hero unquestionably primary.

### Files

- [editorial_dashboard.css](../static/editorial_dashboard.css)
- possibly [editorial_dashboard.js](../static/editorial_dashboard.js) if hero metadata/actions need markup changes

### JS Tasks

#### `renderHeroCard()`

- [ ] Review metadata density.
- [ ] Keep only the most useful metadata near the title.
- [ ] Make sure actions are concise and not louder than the headline.
- [ ] Consider whether the category chip belongs here or should be quieter.

### CSS Tasks

- [ ] Increase vertical spacing around the hero.
- [ ] Consider increasing title size or contrast slightly.
- [ ] Keep excerpt readable but subordinate to the title.
- [ ] Ensure the hero image and text feel balanced, not cramped.

### Acceptance Checks

- [ ] Hero reads as lead story, not “first card.”
- [ ] Eye lands on hero before tools and before rail.

## Pass 4: Below-Hero Rhythm

### Goal

Avoid a uniform “everything is equally important” feeling after the hero.

### Files

- [editorial_dashboard.js](../static/editorial_dashboard.js)
- [editorial_dashboard.css](../static/editorial_dashboard.css)

### JS Tasks

#### `render()` section rendering

- [ ] Reduce the number of feature cards per section if the page still feels too loud.
- [ ] Consider one feature card plus compact cards instead of two feature cards.
- [ ] Consider limiting section size before a “More” affordance if sections feel visually endless.

### CSS Tasks

- [ ] Tune spacing between sections.
- [ ] Tune spacing between feature and compact cards.
- [ ] Make section headers quieter if they compete with content.

### Acceptance Checks

- [ ] The page has rhythm, not repetition.
- [ ] Supporting content looks supporting.

## Suggested Change Order

### Step 1

Implement top filter demotion first.

Reason:

- this will likely produce the biggest immediate improvement to editorial feel

### Step 2

Rebuild the right rail into modules.

Reason:

- current rail is the next biggest mismatch with the target inspiration

### Step 3

Tune hero spacing and hierarchy.

Reason:

- easier to judge once filter noise is reduced

### Step 4

Tune section density below the hero.

Reason:

- final balancing step after the first three changes

## Suggested Agent Tasks

If handing this to the working agent, give them these in order:

### Task A

- [ ] Update `renderTopbar()`, `renderQuickFilters()`, and related CSS so full chip rows are hidden by default behind a `Refine` control.

### Task B

- [ ] Replace the current `Recent` rail in `render()` with module-based rail rendering:
  - `Related to This Story` (client-side filtering from `allItems`)
  - `Quick Pivots` (derived from `filterOptions`)
  - Skip `Continue` — no session history exists

### Task C

- [ ] Increase rail thumbnail size and reduce rail density in CSS.

### Task D

- [ ] Rebalance hero spacing and section density after A-C are in place.

## Review Checklist

Before calling the pass done:

- [ ] Hero is more visually dominant than filter controls.
- [ ] The top of the page feels calmer than it does now.
- [ ] The right rail feels curated, not incidental.
- [ ] Rail thumbnails are actually readable.
- [ ] The page feels more like the reference in mood, not just in dark colors.

## Non-Goals

Do not include in this pass:

- cutover logic
- classic dashboard changes
- backend API changes
- side reader redesign
- audio player redesign

Keep this pass tightly focused on editorial hierarchy and curation.
