# YTV2 Editorial Redesign Phase Tasks

Date: March 29, 2026
Primary plan: `EDITORIAL_REDESIGN_PLAN_GLM.md`
Scope: execution checklist for the separate-route editorial rebuild

## Use This Document

This is the implementation companion to the consolidated plan.

Use it to:

- execute phase work in order
- stop cleanly after any phase
- verify scope before coding
- avoid pulling classic dashboard code into the editorial frontend

## Ground Rules

- `dashboard_v3.js` is frozen during the editorial build unless a bug fix is separately required.
- `dashboard_v3_template.html` is frozen.
- `dashboard.css` is frozen.
- `server.py` is the only existing application file expected to change for Phase 0.
- Editorial uses the same backend contracts as classic:
  - `/api/reports`
  - `/api/filters`
  - `/<video_id>.json`
  - `/<video_id>`
- Editorial is a separate frontend:
  - separate route
  - separate template
  - separate JS
  - separate CSS

## Overall Sequence

1. Phase 0: bootstrap `/editorial`
2. Phase 1: build editorial browse MVP
3. Phase 2: refine filters, URL state, load behavior
4. Phase 3: add reader/audio integration only if needed
5. Phase 4: evaluate and prepare cutover

## Honest Scope

This is not a 1-3 day task.

Expected scope:

- Phase 0: small
- Phase 1: medium
- Phase 2: medium to large
- Phase 3: optional but potentially medium
- Phase 4: decision and cleanup

In practice this is likely weeks of work, not days, if done carefully.

## Phase 0: Bootstrap Editorial Route

### Goal

Create a working `/editorial` page with its own template, JS, and CSS, using the same bootstrapped data as classic.

### Files

- [server.py](/Volumes/markdarby16/16projects/ytv2/dashboard16/server.py)
- `/Volumes/markdarby16/16projects/ytv2/dashboard16/dashboard_editorial_template.html`
- `/Volumes/markdarby16/16projects/ytv2/dashboard16/static/editorial_dashboard.js`
- `/Volumes/markdarby16/16projects/ytv2/dashboard16/static/editorial_dashboard.css`

### Tasks

- [ ] Add `serve_dashboard_editorial()` to `server.py`.
- [ ] Add `/editorial` route in `do_GET`.
- [ ] Reuse classic bootstrap payload generation for:
  - `reports_data`
  - `nas_config`
  - `dashboard_config`
- [ ] Inject a small editorial config object from `server.py`.
- [ ] Add editorial asset version computation in `server.py`.
- [ ] Create `dashboard_editorial_template.html`.
- [ ] Add mount points for:
  - top bar
  - hero
  - sections
  - rail
  - player area
- [ ] Load only editorial JS and CSS in the editorial template.
- [ ] Do not load `dashboard_v3.js`, `dashboard.css`, or the V3 UI flag stack.
- [ ] Create `static/editorial_dashboard.css` with base tokens and shell layout.
- [ ] Create `static/editorial_dashboard.js` with:
  - `EditorialDashboard` skeleton
  - bootstrap config read
  - bootstrapped data read
  - `loadContent()` stub
  - `render()` stub
  - inline helper functions only

### Acceptance Checks

- [ ] `http://marks-macbook-pro-2:10000/` still serves classic unchanged.
- [ ] `http://marks-macbook-pro-2:10000/editorial` returns 200.
- [ ] Editorial template loads with no console errors.
- [ ] `node --check static/editorial_dashboard.js` passes.
- [ ] Both classic and editorial can be open in separate tabs.

### Stop Point

Safe to stop after Phase 0. You have isolated the new frontend and removed the need to keep touching the monolith.

## Phase 1: Editorial Browse MVP

### Goal

Make `/editorial` useful for discovery with a distinct visual identity and working browse interactions.

### Files

- `/Volumes/markdarby16/16projects/ytv2/dashboard16/dashboard_editorial_template.html`
- `/Volumes/markdarby16/16projects/ytv2/dashboard16/static/editorial_dashboard.js`
- `/Volumes/markdarby16/16projects/ytv2/dashboard16/static/editorial_dashboard.css`

### Tasks

- [ ] Build `EditorialDashboard` state model:
  - items
  - page
  - size
  - filters
  - search
  - sort
  - loading flags
- [ ] Implement hero card renderer.
- [ ] Implement feature card renderer.
- [ ] Implement compact card renderer.
- [ ] Render first item as hero.
- [ ] Group remaining items into sections from existing data.
- [ ] Add right rail stack of compact cards.
- [ ] Render source/channel/context metadata on cards.
- [ ] Render audio indicator when applicable.
- [ ] Implement event delegation for:
  - card click
  - read
  - listen
  - watch
  - filter chip actions
- [ ] Implement basic search box.
- [ ] Implement basic sort UI.
- [ ] Implement basic quick filters:
  - source
  - category
- [ ] Implement active filter chips.

### Reader Strategy For This Phase

- [ ] `Read` opens the existing `/<video_id>` page.
- [ ] Accept the visual context switch for now.
- [ ] Do not build a side reader yet.

### Acceptance Checks

- [ ] Editorial looks materially different from classic.
- [ ] Hero, sections, and rail all render.
- [ ] Search works.
- [ ] Sort works.
- [ ] Basic quick filters work.
- [ ] `Read` opens the existing report page.
- [ ] `Watch` opens the source target correctly.
- [ ] No dependency on classic card classes or `decorateCards()`.

### Stop Point

Safe to stop after Phase 1. You will have a working editorial discovery prototype even without reader/audio parity.

## Phase 2: URL State, Filter Completion, Progressive Load

### Goal

Make the editorial browse experience shareable, navigable, and reliable with larger result sets.

### Files

- `/Volumes/markdarby16/16projects/ytv2/dashboard16/static/editorial_dashboard.js`
- `/Volumes/markdarby16/16projects/ytv2/dashboard16/static/editorial_dashboard.css`
- possibly [server.py](/Volumes/markdarby16/16projects/ytv2/dashboard16/server.py) only if a tiny bootstrap/config adjustment is needed

### Tasks

- [ ] Rebuild URL state management in editorial JS.
- [ ] Support shareable query params for:
  - `q`
  - `source`
  - `category`
  - `subcategory`
  - `channel`
  - `language`
  - `summary_type`
  - `sort`
  - `page` if needed
- [ ] Initialize editorial state from URL on first load.
- [ ] Update URL with `replaceState` as controls change.
- [ ] Add browser back/forward compatibility.
- [ ] Expand filters beyond quick filters using `/api/filters`.
- [ ] Implement progressive load for additional pages.
- [ ] Append incremental results without rebuilding the whole page.
- [ ] Add loading and empty states.
- [ ] Test with large result sets.

### SSE / Realtime Decision

Editorial does not need SSE for MVP.

Tasks:

- [ ] Explicitly skip SSE in Phase 2 unless it becomes a real user need.
- [ ] If needed later, treat it as additive client work only.

### Acceptance Checks

- [ ] A copied `/editorial?...` URL reproduces the same state on reload.
- [ ] Back/forward navigation behaves correctly.
- [ ] Filter changes update both results and URL.
- [ ] Progressive load works across multiple pages.
- [ ] Editorial stays responsive with 500+ loaded items.

### Stop Point

Safe to stop after Phase 2. At that point editorial is a serious alternate browse interface.

## Phase 3: Reader And Audio Integration

### Goal

Decide whether editorial needs a more native read/listen flow, then build the smallest useful version.

### Principle

Do not import kaleido, docked reader, or `AudioDashboard` internals unless a tiny isolated utility is clearly worth extracting.

### Files

- `/Volumes/markdarby16/16projects/ytv2/dashboard16/static/editorial_dashboard.js`
- `/Volumes/markdarby16/16projects/ytv2/dashboard16/static/editorial_dashboard.css`
- `/Volumes/markdarby16/16projects/ytv2/dashboard16/dashboard_editorial_template.html`

### Phase 3A: Decide

- [ ] Review actual usage of the Phase 1 report-page fallback.
- [ ] Decide whether the context switch is acceptable.

### Phase 3B: Minimal Side Reader

Only if needed:

- [ ] Build a lightweight slide-in or right-side reader.
- [ ] Render from `/<video_id>.json`.
- [ ] Style with editorial typography and spacing.
- [ ] Keep logic simple and local.
- [ ] No variant tab explosion on first pass.

### Phase 3C: Audio Integration

Only if needed:

- [ ] Add simple local player controls to editorial.
- [ ] Bind to report audio URLs already returned by backend data.
- [ ] Support only the needed playback actions first:
  - play/pause
  - seek
  - duration/time

### Phase 3D: Richer Reader Features

Only after the side reader proves necessary:

- [ ] Consider variant tabs.
- [ ] Consider related items.
- [ ] Consider queue behavior.

### Acceptance Checks

- [ ] Reader/audio additions make editorial feel more coherent.
- [ ] New code remains independent of V3 browse internals.
- [ ] No accidental imports of `AudioDashboard` behavior.

### Stop Point

Safe to stop after Phase 3A or 3B. Full parity is not required unless the editorial flow proves worthy of it.

## Phase 4: Evaluation And Cutover

### Goal

Decide whether editorial should become the default and prepare the lowest-risk transition.

### Files

- [server.py](/Volumes/markdarby16/16projects/ytv2/dashboard16/server.py)
- possibly a small editorial config change if needed

### Tasks

- [ ] Compare classic and editorial for:
  - discovery quality
  - readability
  - speed
  - maintenance cost
- [ ] Dogfood `/editorial` long enough to expose missing essentials.
- [ ] Decide whether editorial becomes the preferred default.

### Cookie Cutover

Do not implement this early.

Only once editorial is dogfood-ready:

- [ ] Add `/?ui=editorial` to set `ytv2_ui=editorial` cookie and redirect.
- [ ] Add `/?ui=classic` to set `ytv2_ui=classic` cookie and redirect.
- [ ] Let `/` read that cookie and choose which template to serve.
- [ ] Keep `/classic` as fallback during transition.

### Cleanup

- [ ] If editorial loses, archive or delete it.
- [ ] If editorial wins, eventually remove classic browse code after stabilization.
- [ ] Avoid permanent dual-front-end maintenance.

### Acceptance Checks

- [ ] Cutover behavior is explicit and reversible.
- [ ] There is one clearly preferred default.
- [ ] Fallback path exists during stabilization.

## Suggested Milestones

### Milestone A

Complete Phase 0 only.

Outcome:

- separate editorial route exists
- monolith pressure is relieved

### Milestone B

Complete Phase 1.

Outcome:

- editorial discovery prototype is real and testable

### Milestone C

Complete Phase 2.

Outcome:

- editorial is viable for real day-to-day browsing

### Milestone D

Complete Phase 3A or 3B.

Outcome:

- editorial has an acceptable read/listen flow

## Anti-Goals

Do not do these as part of this initiative:

- modularize `dashboard_v3.js`
- refactor `AudioDashboard` into components
- reuse `decorateCards()`
- make editorial depend on classic CSS
- change backend APIs just to suit the new frontend
- rewrite the report page before proving the editorial browse shell

## Immediate Next Task

Start with Phase 0 only.

The exact first coding tasks should be:

- [ ] add `/editorial` route in `server.py`
- [ ] add `serve_dashboard_editorial()` in `server.py`
- [ ] create `dashboard_editorial_template.html`
- [ ] create `static/editorial_dashboard.js`
- [ ] create `static/editorial_dashboard.css`
- [ ] verify classic remains unchanged
