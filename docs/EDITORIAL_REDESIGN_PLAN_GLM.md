# YTV2 Editorial Redesign Plan (Consolidated V2)

Date: March 29, 2026
Branch context: `codex/dashboard-redesign-exploration`
Sources: Original Codex strategy + GLM codebase analysis + Codex V2 strangler direction + GLM review of V2

## Decision

Build the editorial browse experience as a **separate frontend** on its own route, template, JS, and CSS -- while reusing the existing backend APIs unchanged.

Do **not** build it inside the 14,358-line `AudioDashboard` monolith. Do **not** try to extract shell renderers from the monolith. Build fresh, share only what's safe to share.

This is a strangler rebuild:

- `classic` stays on `/` -- untouched, stable, always available
- `editorial` gets its own files on `/editorial` -- new code, new design, same backend
- When editorial proves itself, promote it to `/` and remove classic

---

## Codebase Reality Check

The current frontend is a single monolith:

| File | Lines | Role |
|------|-------|------|
| `dashboard_v3.js` | 14,358 | Single `AudioDashboard` class, ~200 methods, 91 innerHTML assignments |
| `dashboard.css` | 7,788 | No modular organization, no scoping |
| `dashboard_v3_template.html` | 1,420 | Single Jinja2 template |
| `ui_flags.js` | 23/34 | Feature flags |

Rendering pipeline:

```
loadContent() [line 3245]
  -> fetches /api/reports
  -> renderContent(items) [line 3551]
      -> dispatches to card factories (wall/grid/list)
      -> injects HTML strings into #contentGrid via innerHTML
  -> decorateCards(items) [line 3847]
      -> imperative DOM manipulation tightly coupled to card structure
```

Key problems:
- Card factories reach into `this` for ~15 state values
- `decorateCards()` expects specific CSS classes and data attributes
- Event binding is interleaved with rendering
- CSS has no scoping mechanism
- No modules, no imports, no build step, no framework

**This is why we're not building inside the monolith.** The seams aren't there, and creating them would be a refactor project with no product progress. Better to build separately and let the monolith stay frozen.

---

## Product Direction

Move YTV2 from:

- "dense summary dashboard"

toward:

- "editorial intelligence dashboard"

That means:

- stronger layout hierarchy
- calmer chrome, more intentional typography
- better discovery pacing with hero + sections
- a clearer transition into reading and listening
- power-user controls remain available but secondary

---

## Editorial UX Model

### Layout structure

1. **Calm top bar**
   - brand
   - search
   - lightweight primary navigation
   - shell toggle (classic/editorial)
   - utility/settings

2. **Discover subnav**
   - `For You` / `Recent` / `Topics` / `Sources` / optionally `Saved`
   - These are filter presets, not separate pages

3. **Hero row**
   - one featured summary with strong headline treatment
   - large thumbnail/art emphasis
   - short excerpt
   - primary actions: `Read`, `Listen`, `Watch`

4. **Supporting right rail**
   - recent/trending stack
   - queue state
   - optional saved filters or metrics

5. **Mixed-density content sections**
   - `Recent additions` / topic sections derived from categories
   - 2-3 card sizes: hero, feature, compact
   - Sections derived from the same fetched data -- no new API calls

6. **Reader continuity**
   - Phase 1: `Read` opens the existing report page
   - Phase 2+: build a lightweight editorial side reader if needed

### Filter philosophy

- keep top-level quick filters visible
- move less-common controls into progressive disclosure
- active filter chips stay obvious
- filter behavior uses the same `/api/filters` and `/api/reports` semantics

---

## Architecture: Separate Frontend, Shared Backend

### Routes

| Route | Serves | Status |
|-------|--------|--------|
| `/` | `dashboard_v3_template.html` (classic) | Unchanged |
| `/editorial` | `dashboard_editorial_template.html` (editorial) | New |
| `/?ui=editorial` | Redirects or cookie-sets to `/editorial` | New |

Route separation prevents the V3 template and JS from becoming a conditional maze.

**Cutover mechanism (deferred until editorial is stable):**
- During development: `/editorial` is the only way to reach editorial. Do NOT wire cookies or `/` redirection yet.
- Once editorial is dogfood-ready: add `/?ui=editorial` to set a `ytv2_ui=editorial` cookie and redirect to `/editorial`.
- Once editorial is the preferred default: `/` reads the cookie and serves the editorial template. `/classic` becomes the fallback.
- This avoids route migration and avoids premature `/` complexity.

### New files

| File | Purpose |
|------|---------|
| `dashboard_editorial_template.html` | Layout shell, mount points, data bootstrap |
| `static/editorial_dashboard.js` | Own state, fetch/render/filter/sort, progressive load |
| `static/editorial_dashboard.css` | Scoped styles, design tokens, layout, cards |

No shared helper file initially. Duplicate small utilities in the editorial JS. Extract later if both frontends stabilize.

### JS architecture for the new frontend

The editorial frontend should be **better structured** than the monolith but still practical:

- **Vanilla JS, no framework, no build step** (same constraint as classic)
- **Template literals** instead of string concatenation (cleaner than the monolith)
- **Simple state + render pattern:** a lightweight class or module that owns state, fetches data, and renders into mount points
- **Event delegation** on container elements, not inline handlers
- **Keep it under 3,000 lines.** If it's growing toward 5K+, something is wrong.

Example pattern:

```javascript
class EditorialDashboard {
  constructor() {
    this.state = { items: [], filters: {}, search: '', sort: 'newest', page: 1 };
    this.mounts = {
      hero: document.getElementById('ed-hero'),
      sections: document.getElementById('ed-sections'),
      rail: document.getElementById('ed-rail'),
    };
  }

  async loadContent() { /* fetch /api/reports */ }
  render() { /* template literals into this.mounts */ }
  renderHeroCard(item) { /* returns HTML string */ }
  renderFeatureCard(item) { /* returns HTML string */ }
  renderCompactCard(item) { /* returns HTML string */ }
  bindEvents() { /* delegation on containers */ }
}
```

### Existing files that change

| File | Change | Risk |
|------|--------|------|
| `server.py` | Add `/editorial` route + serve method | Low -- additive only |
| `ui_flags.js` | Optional `editorialEnabled` flag | Minimal |

### What we do NOT touch

- `dashboard_v3.js` -- frozen during editorial build
- `dashboard_v3_template.html` -- frozen
- `dashboard.css` -- frozen
- `decorateCards()` -- not reused
- `AudioDashboard` -- not imported, not branched, not refactored
- Any backend API contracts
- `backend/` directory at all

---

## Reuse Matrix

### Reuse unchanged (shared backend)

- `/api/reports` -- pagination, filtering, sort, search
- `/api/filters` -- available filter values
- `/<video_id>.json` -- report detail payload
- `/<video_id>` -- existing report detail page (Phase 1 reader fallback)
- Current query parameter semantics (source, category, q, sort, etc.)
- PostgreSQL-backed content model

### Extract only if safe

Small, stateless, short utilities:

- HTML escaping (`escapeHtml`)
- Duration formatting
- Source-label mapping
- Filter query-string builder

**But:** only extract to a shared file if both frontends are actively using it. Until then, duplicate the 10-line functions in editorial JS. Premature extraction creates coupling.

### Do NOT reuse

- `AudioDashboard` class
- `decorateCards()`
- `renderWallCardTW()` / `renderGridCardTW()` / `renderStreamCardV4()`
- Docked reader logic
- Kaleido modal logic
- Classic CSS selectors or card class names
- Classic event binding patterns

If the editorial frontend depends on any of these, it is not a real rebuild.

---

## Implementation Plan

### Phase 0: Bootstrap the editorial route

**Goal:** Create a working `/editorial` page that loads data but has no real UI yet.

#### Step 0A: Add `/editorial` route to server.py

1. Add a `serve_dashboard_editorial()` method that:
   - Bootstraps the same `reports_data`, `nas_config`, `dashboard_config` as classic
   - Injects a small editorial config object (not the V3 flag matrix)
   - Renders `dashboard_editorial_template.html`
   - Computes editorial asset versions

2. Register the route on `/editorial`

3. `/?ui=editorial` redirect deferred until editorial is stable (see cutover section below)

**Verification:** `/editorial` returns a 200 with the new template. `/` still serves classic unchanged.

#### Step 0B: Create the editorial template

Create `dashboard_editorial_template.html` with:

- Minimal layout shell: top bar, content area, right rail mount points
- Data bootstrap: inject `reports_data`, `nas_config`, `dashboard_config` as JSON in a `<script>` tag (same pattern as classic)
- Load `editorial_dashboard.css` and `editorial_dashboard.js` only
- Do NOT load `dashboard_v3.js`, `dashboard.css`, or `ui_flags.js`
- Instead of the V3 flag system, inject a small editorial-specific config object from `server.py` (e.g., `{ features: { audio: true, search: true } }`)

```html
<!-- Mount points -->
<div id="ed-topbar"></div>
<div id="ed-main">
  <div id="ed-hero"></div>
  <div id="ed-sections"></div>
</div>
<aside id="ed-rail"></aside>
<div id="ed-player"></div>
```

**Verification:** `/editorial` loads a blank styled shell. No console errors.

#### Step 0C: Create the editorial CSS foundation

Create `static/editorial_dashboard.css` with:

- Design tokens as CSS custom properties (no overrides of classic variables)
- Layout grid
- Card style stubs (hero, feature, compact)
- Responsive breakpoints
- No dependency on classic CSS class names

```css
:root {
  --ed-space-xs: 0.5rem;
  --ed-space-sm: 1rem;
  --ed-space-md: 1.5rem;
  --ed-space-lg: 2.5rem;
  --ed-space-xl: 4rem;
  --ed-font-display: 'Playfair Display', Georgia, serif;
  --ed-font-body: 'Inter', -apple-system, sans-serif;
  --ed-color-bg: #0a0a0a;
  --ed-color-surface: #141414;
  --ed-color-text: #e5e5e5;
  --ed-color-muted: #737373;
  --ed-color-accent: #3b82f6;
}
```

**Verification:** CSS loads, tokens are available, no conflicts with classic.

#### Step 0D: Create the editorial JS skeleton

Create `static/editorial_dashboard.js` with:

- `EditorialDashboard` class stub
- Constructor that reads bootstrapped data
- `loadContent()` that fetches `/api/reports` and logs the response
- `render()` stub that populates hero with "Loading..." placeholder

Duplicate small utilities inline:
- `escapeHtml()` (10 lines)
- `formatDuration()` (8 lines)
- Filter query-string builder (20 lines)

**Verification:** `/editorial` fetches data and shows a loading state in console. Classic still works.

#### Step 0E: Smoke test

1. `node --check static/editorial_dashboard.js` -- must pass
2. `docker restart ytv2-dashboard`
3. Hard refresh `http://marks-macbook-pro-2:10000/` -- classic unchanged
4. Visit `http://marks-macbook-pro-2:10000/editorial` -- blank shell loads, data fetches
5. Check browser console -- no errors on either page

**Phase 0 Definition of Done:**

- `/` serves classic, zero changes
- `/editorial` serves a new template with its own JS and CSS
- Editorial JS successfully fetches `/api/reports` and logs data
- No files from the monolith are modified (except `server.py` route addition)
- Both pages can be open in different tabs simultaneously

**Files touched:**

| File | Change |
|------|--------|
| `server.py` | Add `/editorial` route + serve method |
| `dashboard_editorial_template.html` | New file |
| `static/editorial_dashboard.js` | New file |
| `static/editorial_dashboard.css` | New file |

---

### Phase 1: Editorial browse MVP

**Goal:** Make `/editorial` useful for content discovery.

#### Step 1A: Build card factories

Three card variants, all returning HTML strings via template literals:

1. **Hero card** -- full-width, large image, headline, excerpt, actions
2. **Feature card** -- horizontal, image + text side by side
3. **Compact card** -- thumbnail + title + source, list-style

Each card must include:
- `data-video-id` attribute (for click handling)
- Source/channel metadata
- Audio indicator if applicable
- Category/context chips

#### Step 1B: Build the editorial layout

Implement `render()`:

1. **Hero section:** First item from result set -> hero card
2. **Content sections:** Group remaining items by category
   - Use `item.categories` or `item.source` to create sections
   - Fall back to a flat "Recent" section if categories are sparse
   - Mix feature cards and compact cards per section
3. **Right rail:** Stack of compact cards (next N items by recency)

Layout via CSS Grid:
```css
#ed-main {
  display: grid;
  grid-template-columns: 1fr 320px;
}
#ed-hero { grid-column: 1 / -1; }
#ed-sections { grid-column: 1; }
#ed-rail { grid-column: 2; }
```

#### Step 1C: Build search and basic filters

Wire up:
- Search input -> `/api/reports?q=...`
- Source/category quick filters -> `/api/reports?source=...&category=...`
- Sort controls -> `/api/reports?sort=...`
- Active filter chips display

All using the same query parameter semantics as classic. Rebuild the URL state management fresh (don't import from monolith).

**Important: URL state / deep linking.** Editorial must support shareable URLs:
- `/editorial?q=AI&source=YouTube&sort=newest` should produce the same results as classic with those params
- URL params should update as filters change (replaceState, not pushState)
- This is new code, not imported from the monolith

#### Step 1D: Progressive load

- First page loads 50 items (same as classic)
- Scroll to bottom triggers next page fetch
- Appended items go into a "More" section at the bottom as compact cards
- Do NOT re-run hero/section grouping on incremental loads -- just append
- Target: handle 500+ items without lag

#### Step 1E: Reader fallback

For the MVP, `Read` opens the existing report page at `/<video_id>`.

This creates a visual context switch (old report page template), but it's acceptable for proving the browse experience. The report page is functional and the user can always navigate back.

**Phase 1 Definition of Done:**

- `/editorial` shows a visually distinct layout with hero, sections, and right rail
- Search, filters, and sort work with correct query semantics
- URL state is shareable (deep linking works)
- Progressive load handles large result sets
- Clicking a card opens the existing report page
- Classic is still completely untouched
- No dependency on `AudioDashboard`, `decorateCards()`, or classic CSS

---

### Phase 2: Search, filters, and progressive load refinement

**Goal:** Reach real usability parity on discovery controls.

This phase polishes what Phase 1 built rough:

1. **Full filter UI** -- bind to `/api/filters` for dynamic filter options
2. **Advanced filter popover** -- source, category, subcategory, channel, language, summary type
3. **Filter chips** -- active filter display with individual removal
4. **Progressive load polish** -- loading indicators, scroll position preservation, error handling
5. **Empty states** -- no results, loading, error states
6. **SSE/realtime consideration** -- Decide whether editorial needs live report additions
   - MVP: skip SSE, user refreshes to see new content
   - If needed later: connect to same EventSource as classic, append to sections

**Phase 2 Definition of Done:**

- Editorial and classic produce materially similar result sets for the same filters
- Filter and sort UX feels complete, not placeholder
- Progressive load is smooth with large datasets
- Page remains responsive with 500+ items rendered

---

### Phase 3: Reader and audio integration

**Goal:** Deepen the editorial experience without importing V3 complexity.

#### Reader strategy (in order)

1. **Phase 3a:** `Read` opens existing report page (carried from Phase 1). This is the quick path.
2. **Phase 3b:** Build a lightweight editorial side reader -- a slide-in panel that renders the same `/<video_id>.json` payload with editorial typography. Does NOT import docked reader or kaleido logic. Fresh, simple, ~300 lines.
3. **Phase 3c (if needed):** Richer reader with variant tabs, audio controls, related items. Only build this if the side reader proves insufficient.

#### Audio strategy (in order)

1. **Phase 3a:** `Listen` opens a simple `<audio>` player in the editorial page. No queue, no docked player. Just play/pause/progress.
2. **Phase 3b:** Lightweight queue in the right rail. Add-to-queue, next/previous.
3. **Phase 3c (if needed):** Full audio parity with queue management, waveform, etc.

**Important rule:** Build new reader/audio UI against existing JSON/report payloads. Do NOT transplant kaleido or docked-reader logic. If a piece is both isolated AND valuable, consider extracting it. Otherwise, rebuild it simpler.

**Phase 3 Definition of Done:**

- Reading and listening feel integrated into the editorial experience
- Opening a summary does not feel like jumping to a different app
- Editorial frontend remains independent of V3 internals
- Audio playback works for TTS summaries

---

### Phase 4: Evaluation and cutover

**Goal:** Decide whether editorial replaces classic.

#### Step 4A: Side-by-side evaluation

1. Use both shells for real work for 1-2 weeks
2. Compare:
   - Discovery quality (do you find what you want faster?)
   - Reading/listening flow (is it smoother?)
   - Filter/power-user capability (can you do everything you need?)
   - Performance (is it responsive with 500+ items?)
   - Maintenance cost (how clean is the editorial codebase?)

#### Step 4B: Decide

- If editorial wins: promote to `/` via cookie mechanism, keep classic on `/classic` temporarily
- If classic wins: archive editorial files, update this doc with lessons learned
- If hybrid wins: identify which pieces from each are worth keeping

#### Step 4C: Clean up

- Delete the losing shell
- Remove the cutover mechanism
- Update documentation
- Celebrate / mourn

**Phase 4 Definition of Done:**

- One maintained default browse experience
- No permanent dual-frontend burden
- Clean git history with the deleted shell removed

---

## Design Principles

### 1. Content hierarchy before control density

Not every summary should be equally loud. The first screen should communicate what matters now.

### 2. Power remains available, but secondary

Filters, metadata, and operations should stay present but stop dominating the page.

### 3. Reader is the product, not a side effect

Discovery exists to lead into reading/listening. The redesign should strengthen that transition.

### 4. Visual identity should feel intentional

Avoid generic app chrome. The current product needs more editorial contrast in typography, spacing, scale, and section rhythm.

### 5. Performance is a feature

Do not trade a prettier layout for sluggish browsing across hundreds of summaries.

### 6. Independence over reuse

If the editorial frontend depends on classic internals, it's not a rebuild -- it's a skin. Maintain real separation even if it means duplicating small utilities.

---

## Risks

### Risk: scope is real

Rebuilding filter UI, search, sort, pagination, card rendering, and progressive load from scratch is significant. This is weeks of work, not days.

**Mitigation:**
- Phase boundaries let you stop after any phase and still have something useful
- Phase 0 alone is days. Phase 0 + Phase 1 is 1-2 weeks. Full product parity is longer.
- Classic is always available as fallback

### Risk: reader context switch

In Phase 1-2, clicking "Read" opens the old report page -- a visual context switch that undermines the editorial feel.

**Mitigation:**
- Accept it temporarily as a known gap
- Phase 3a (side reader) is the fix
- The report page is functional, just visually different

### Risk: feature drift during build

Classic keeps evolving while editorial is being built. If classic adds features, editorial falls behind.

**Mitigation:**
- Freeze feature work on classic browse during editorial build
- Or accept that editorial v1 won't have parity with every classic feature
- Reader/audio parity is explicitly deferred to Phase 3

### Risk: duplicated logic in the wrong places

Some duplication is healthy (10-line utility functions). The wrong duplication is business rules and API semantics.

**Mitigation:**
- Share backend contracts -- that's where the business rules live
- Duplicate small pure frontend utilities freely
- Never duplicate API call patterns -- use the same endpoints and parameters

### Risk: trying to reach full parity too early

That would slow the redesign and recreate the old complexity.

**Mitigation:**
- Ship browse-first MVP (Phase 1)
- Defer rich reader/audio parity to Phase 3
- The editorial frontend does not need every feature classic has

### Risk: SSE/realtime gap

Classic has live report additions via EventSource. Editorial MVP won't.

**Mitigation:**
- Acceptable for MVP -- users refresh to see new content
- Add SSE in Phase 2 if it proves important
- The SSE endpoint is shared; only the client connection is new code

---

## Success Criteria

This approach is successful if:

- Classic remains stable and untouched while editorial is built
- Editorial becomes useful without depending on `AudioDashboard`
- Both frontends use the same backend contracts
- Editorial proves the new UX direction within the first 2 phases
- The editorial JS stays under 3,000 lines
- The team can later delete one shell rather than maintain both forever
- No files in the monolith grow as a result of this work

---

## Recommended Next Step

Start Phase 0. It touches only `server.py` (additive) and creates 3 new files. Zero risk to classic.

After Phase 0, reassess. If the data bootstrap works and the editorial shell loads cleanly, proceed to Phase 1 (the real product work). If something feels wrong about the separation, pivot before investing in card factories.

Do not start by modifying `dashboard_v3.js`. The point of this plan is to stop making the monolith the center of all future UI work.
