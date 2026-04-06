# Editorial Related Mode Animation Brief

Date: April 5, 2026
Target route: `/editorial`

This brief defines the recommended interaction model for a future `Related` mode in the editorial dashboard.

The goal is not to add one more generic sort option. The goal is to create a focused editorial state where a selected story becomes the anchor and the rest of the page reorganizes around it with a deliberate, legible animation.

## Summary Recommendation

Build `Related` as a selected-story focus mode.

Recommended behavior:

1. User selects a story.
2. User toggles `Related`.
3. That selected story becomes the anchor in the hero slot.
4. Supporting and feed cards re-rank beneath it by relatedness.
5. The transition is animated so the user can see where cards moved.
6. Turning `Related` off restores the prior recent-order layout.

Do not treat this as an ordinary global sort with no anchor.

## Why This Model Fits Better

The question `related to what?` must always have a visible answer.

If the page reorders by relatedness without clearly promoting the selected story into the lead position, the ranking will feel arbitrary. The user should not need to remember which card they clicked several seconds ago to understand the order.

Promoting the selected story into the hero slot solves that problem, but it must read as an explicit mode shift rather than a silent card jump.

The right mental model is:

- not `move this random card to slot one`
- but `enter focus mode for this selected story`

## Current Editorial Constraints

Current editorial layout is sequence-driven:

- hero is simply `items[0]` in [editorial_dashboard.js](/Volumes/markdarby16/16projects/ytv2/dashboard16/static/editorial_dashboard.js#L394)
- supporting cards are derived from the next slice in [editorial_dashboard.js](/Volumes/markdarby16/16projects/ytv2/dashboard16/static/editorial_dashboard.js#L403)
- feed cards are the remainder of the current ordered set in [editorial_dashboard.js](/Volumes/markdarby16/16projects/ytv2/dashboard16/static/editorial_dashboard.js#L416)

Current sort state is limited:

- `this.state.sort` defaults to `newest` in [editorial_dashboard.js](/Volumes/markdarby16/16projects/ytv2/dashboard16/static/editorial_dashboard.js#L263)
- the refine menu only exposes `Newest` and `Oldest` in [editorial_dashboard.js](/Volumes/markdarby16/16projects/ytv2/dashboard16/static/editorial_dashboard.js#L717) and [editorial_dashboard.js](/Volumes/markdarby16/16projects/ytv2/dashboard16/static/editorial_dashboard.js#L769)
- click handling simply swaps sort value and reloads in [editorial_dashboard.js](/Volumes/markdarby16/16projects/ytv2/dashboard16/static/editorial_dashboard.js#L954)
- the reports API does not currently validate a `related` sort in [server.py](/Volumes/markdarby16/16projects/ytv2/dashboard16/server.py#L3735)

Current editorial styling is also layout-specific:

- hero styling in [editorial_dashboard.css](/Volumes/markdarby16/16projects/ytv2/dashboard16/static/editorial_dashboard.css#L614)
- support grid in [editorial_dashboard.css](/Volumes/markdarby16/16projects/ytv2/dashboard16/static/editorial_dashboard.css#L683)
- feed grid in [editorial_dashboard.css](/Volumes/markdarby16/16projects/ytv2/dashboard16/static/editorial_dashboard.css#L725)

This means the first implementation should be a client-side presentation mode, not a backend sort rewrite.

## Existing Relatedness Capability To Reuse

The codebase already has a real relatedness path:

- semantic similar API at [server.py](/Volumes/markdarby16/16projects/ytv2/dashboard16/server.py#L3457)
- semantic lookup implementation at [semantic_search.py](/Volumes/markdarby16/16projects/ytv2/dashboard16/modules/semantic_search.py#L159)
- classic reader related strip behavior at [dashboard_v3.js](/Volumes/markdarby16/16projects/ytv2/dashboard16/static/dashboard_v3.js#L8309)

This is enough to make the editorial mode feasible without inventing new ranking logic from scratch.

## Recommended Experience Model

### Default State

The page behaves exactly as it does now:

- recent-first ordering
- lead hero from the most recent story
- support and feed cards below

### Selected State

When a user clicks or otherwise selects a card, the UI should remember:

- selected story id
- the selected story's original index in the recent ordering

This selection alone should not immediately reorder the page.

### Related Mode On

When the user explicitly toggles `Related`:

- selected story becomes the hero anchor
- remaining loaded items are ranked by relatedness to that story
- support block pulls from the top of that related set
- feed follows in descending relatedness
- page shows a visible state label such as `Related to: [title]`

This keeps the interaction explicit and understandable.

### Related Mode Off

When the user turns `Related` off:

- restore the exact previous recent-order list
- restore hero/support/feed based on that order
- preserve user orientation as much as possible

If feasible, also preserve scroll position or return focus near the selected story.

## Animation Direction

The recommended visual model is not a hard re-render cut. It is a staged transition:

1. The selected card visually lifts from its current position.
2. The hero area acknowledges the incoming story.
3. The selected card settles into the hero slot.
4. Remaining cards cascade into their new related positions.

This should feel like the page is reorganizing around the chosen story, not refreshing.

## Animation Technique Recommendation

Use a FLIP-style transition for the editorial cards.

Meaning:

- capture each card's first position
- compute the new ordered DOM/layout
- capture each card's last position
- animate the delta using transforms

Why this is the right approach:

- it preserves continuity when many cards move
- it is compatible with the current card/grid layout
- it avoids needing heavy bespoke per-card choreography

Animation guidance:

- keep timing in the `220ms` to `420ms` range
- use slightly softer easing for the hero promotion than for the feed shuffle
- stagger very lightly, if at all
- prioritize clarity over spectacle

Avoid:

- long springy motion
- cards flying across the screen
- opacity-only transitions that hide where items came from

## UX Rules

Rules that should hold for the first implementation:

- `Related` is disabled unless a story is selected
- the selected story remains visibly identified while the mode is active
- the page always tells the user what the list is related to
- turning the mode off is one click and fully reversible
- if related results are weak or unavailable, the UI falls back gracefully

Recommended topbar language:

- `Recent`
- `Topics`
- `Related` as a contextual toggle only when a story is selected

Avoid presenting `Related` as a general always-available sort beside `Newest` and `Oldest`.

## First-Pass Technical Strategy

Phase 1 should avoid backend changes to `/api/reports`.

Recommended implementation shape:

- add editorial state for:
  - `selectedItemId`
  - `relatedMode`
  - `baseOrderedItems`
  - `displayItems`
- preserve the incoming recent order as the base order
- when `Related` is enabled, compute a new derived order client-side
- use `/api/semantic-similar` for the ranking source when available
- fall back to a simpler heuristic only if semantic results are unavailable

Important: do not permanently mutate the base recent order. Keep related ordering as a derived presentation state.

## Rendering Recommendation

Treat the related-mode hero as a pinned anchor state, not as a normal first card.

That can still be rendered through the current hero area, but conceptually it should be distinct:

- current mode: `lead story`
- related mode: `selected anchor story`

This distinction matters because the hero is no longer merely the latest item; it is the active focus item.

## Copy / UI Signaling

The page needs explicit copy during related mode.

Recommended elements:

- a small active label: `Related to`
- truncated title of the anchor story
- a clear close control such as `Back to Recent`

Optional:

- a brief subtitle like `Stories ranked by semantic similarity`

Do not over-explain. Just make the mode legible.

## Mobile Behavior

This interaction is still viable on mobile, but motion must be more restrained.

Mobile recommendations:

- shorter animation distances
- lower motion intensity
- no dependence on users seeing both original and destination slots at once
- explicit state label near the hero

If needed, the selected card can crossfade/lift into the hero more simply on small screens while the feed reorders below.

## Fallback Strategy

If semantic similarity is unavailable:

- keep the selected anchor promotion behavior
- use a simpler overlap heuristic for category, source, and channel
- label the mode the same way
- do not break or disable the entire feature if the semantic service is temporarily unavailable

The feature is about focus and orientation first. Semantic ranking quality improves it, but should not be a single point of failure.

## Risks

Main risks:

- confusing users if the selected card jumps without enough signaling
- losing scroll/focus context during the reorder
- making the mode feel like a bug if the transition is too abrupt
- poor relatedness quality if the candidate pool is too small
- JS fragility if new state is added without strict null checks

Implementation note:

Follow the existing project rule to null-check all new JS state and DOM references.

## Orchestrator Additions (Claude Opus)

### Ranking Source: Heuristic First, Semantic Later

The existing `computeHeuristicSimilarity()` in `dashboard_v3.js` (line 8639) is fast and runs entirely client-side using categories (+4.0 subcategory pairs), channel (+1.5), and title tokens (Jaccard * 0.8). For Phases A and B, use this as the **primary** ranking source rather than `/api/semantic-similar`.

Reasons:
- Zero network latency — re-rank is instant, which matters for animation timing
- No dependency on ChromaDB being populated or the semantic endpoint being available
- The classic dashboard's `hybrid` mode already uses it successfully for wall dock arrangement
- Subcategory pair scoring at +4.0 is quite good for editorial content that is well-categorized

Semantic API integration should be treated as a Phase C+ enhancement, not a prerequisite.

### Heuristic Port Strategy

Since `computeHeuristicSimilarity()` lives in `dashboard_v3.js` (classic dashboard), the editorial dashboard needs its own copy or a shared utility. For Phase A, copy the minimal logic into `editorial_dashboard.js` as private methods:
- `_computeHeuristicSimilarity(baseItem, candItem)` — the scoring function
- `_tokenizeTitle(text)` — title tokenization
- `_jaccard(a, b)` — Jaccard index
- `_extractCatsAndSubcats(item)` — category extraction from `subcategories_json` or `analysis.categories`

This avoids coupling the two dashboards. A shared module can be extracted later if both use it.

### Animation Stagger

The brief says "stagger very lightly, if at all." For editorial's hero+support+feed hierarchy, a **slight stagger** (20-30ms) on feed cards after the hero settles creates a cascade feel that reinforces the "reorganizing around" metaphor. This is different from the classic dashboard's uniform grid where no stagger works fine. The editorial layout has visual hierarchy — the cascade should respect it:
1. Hero promotion: first, ~300ms ease-out
2. Support cards: next, ~250ms, slight 15ms stagger
3. Feed cards: last, ~250ms, 20-30ms stagger

### Implementation Constraints

- All new JS state (`selectedItemId`, `relatedMode`, `baseOrderedItems`, `displayItems`) MUST have null-checks per project guidelines in `AI_AGENT_GUIDELINES.md`
- Test with `node --check static/editorial_dashboard.js` before restarting Docker
- Hard refresh browser (Cmd+Shift+R) to verify — if page shows loading state without content, there is a JS error
- Docker restart: `docker restart ytv2-dashboard` (source files bind-mounted)

### State Management Pattern

```
class EditorialDashboard {
  constructor() {
    // ... existing state ...
    this._selectedItemId = null;       // currently selected story ID
    this._relatedMode = false;         // whether related mode is active
    this._baseOrderedItems = null;     // snapshot of items in recent order before entering related mode
    this._relatedAnchorIndex = -1;     // original index of anchor card (for scroll restoration)
  }
}
```

Key rule: `baseOrderedItems` is never mutated. `displayItems` is always derived from it. When related mode turns off, discard `displayItems` and render from `baseOrderedItems`.

## Recommended Scope Split

### Phase A: State + Static Re-rank (IMPLEMENT FIRST)

- selectable editorial cards (click handler to set `_selectedItemId`)
- selected-story visual state (subtle border/highlight on selected card)
- related toggle button in refine bar (disabled unless story selected, only visible when story selected)
- on toggle: snapshot `baseOrderedItems`, compute related order via heuristic, re-render hero/support/feed from derived order
- "Related to: [title]" label + "Back to Recent" close control
- on toggle off: restore from `baseOrderedItems`, clear selected state
- NO animation yet — just instant re-render to validate ranking quality

### Phase B: Animated Re-rank (AFTER A IS VALIDATED)

- FLIP position capture (rects before reorder)
- hero lift/promotion transition (~300ms)
- feed/support cascade reorder animation with stagger
- related-mode label entrance animation
- scroll position restoration on exit

### Phase C: Refinement

- semantic API as optional ranking source (async, with loading state)
- improved scroll restoration
- small-screen tuning (restrained animation)
- optional persistence of last selected item within the session
- shared utility extraction if classic dashboard also needs updates

## Acceptance Standard

This feature is successful if:

- users understand what the page is related to without guessing
- the selected story clearly becomes the active anchor
- the transition feels intentional and premium
- turning related mode on and off feels safe and reversible
- the editorial page stays calm and readable rather than becoming dashboard-like

This feature is not successful if it feels like a hidden sort mutation.

## File Targets For Future Implementation

Primary implementation files:

- [dashboard_editorial_template.html](/Volumes/markdarby16/16projects/ytv2/dashboard16/dashboard_editorial_template.html)
- [editorial_dashboard.js](/Volumes/markdarby16/16projects/ytv2/dashboard16/static/editorial_dashboard.js)
- [editorial_dashboard.css](/Volumes/markdarby16/16projects/ytv2/dashboard16/static/editorial_dashboard.css)

Reference behavior:

- [dashboard_v3.js](/Volumes/markdarby16/16projects/ytv2/dashboard16/static/dashboard_v3.js)
- [server.py](/Volumes/markdarby16/16projects/ytv2/dashboard16/server.py)
- [semantic_search.py](/Volumes/markdarby16/16projects/ytv2/dashboard16/modules/semantic_search.py)
