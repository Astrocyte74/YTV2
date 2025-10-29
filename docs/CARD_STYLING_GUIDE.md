# Card Styling Guide (V4)

A concise reference for updating the dashboard’s card UI and related styles. Use this when adjusting layout, chip density, CTA buttons, and visual polish for the List (Stream) and Grid (Mosaic) views.

## Scope
- Card renderers: V4 Stream (List) and V4 Mosaic (Grid)
- Filter chevrons, section toggles, and small a11y details
- Cache busting so your browser picks up CSS/JS changes

## Where To Edit
- Structure/HTML (renderers)
  - `static/dashboard_v3.js:3089` → `renderStreamCardV4(item)`
  - `static/dashboard_v3.js:3158` → `renderGridCardV4(item)`
  - Supporting helpers often used by the renderers:
    - `static/dashboard_v3.js:4080` → `renderCategorySection(...)` (chips and “+X more”)
    - `static/dashboard_v3.js:4234` → `renderActionBar(...)` (Read/Listen/Watch CTAs)
- Styling (CSS)
  - `static/dashboard.css` → V4 classes prefixed with `.stream-card*` and `.mosaic-card*`
- Feature flags (enable V4)
  - `ui_flags.js:1` → `cardV4: true`
- Template cache‑bust (browsers are sticky)
  - `dashboard_v3_template.html:742` → bump `ui_flags.js?v=...`
  - `dashboard_v3_template.html:743` → bump `dashboard_v3.js?v=...`
  - Also bump `dashboard.css?v=...` in the template when changing CSS

## Fast Path Changes (Common)
- Title clamp lines (List)
  - CSS: `static/dashboard.css` → `.stream-card__title` uses `-webkit-line-clamp: 3`.
  - Change to 2/4 depending on density. Also see utility `.line-clamp-2`.
- Thumbnail size (List)
  - CSS: `.stream-card__media { width: 10rem; height: 6rem; }`
  - Increase/decrease for larger or tighter cards.
- CTA button density (List + Grid)
  - CSS: see “Compact action buttons for V4 cards” overrides under `.stream-card .variant-*` and `.mosaic-card .variant-*`.
  - Modify padding/size there to tune the Read/Listen/Watch toggles.
- Chip count + “+X more” behavior
  - JS: `renderCategorySection(...)` caps visible chips via `maxPrimary = 3`.
  - Adjust that constant to show fewer/more chips before collapsing extras.
- Source/Language/Summary type pills
  - JS: produced by `renderSourceBadge(...)`, `renderLanguageChip(...)`, `renderSummaryTypeChip(...)` and wrapped in `.stream-card__meta`.
  - CSS: style via `.summary-pill`, `.summary-chip` and related classes in `static/dashboard.css`.
- “Now playing” pill
  - JS: `renderStreamCardV4` sets `nowPlayingPill` when the current card matches the active audio.
  - CSS: `.summary-card__badge` and `.summary-pill--playing`.

## Filter Sections, Chevrons, Sort
- Collapsible filters use native `<details>/<summary>` in the template:
  - `dashboard_v3_template.html:356` and subsequent filter blocks include an inline SVG chevron:
    - `<svg class="chevron" viewBox="0 0 24 24"><path d="M8 5l8 7-8 7"/></svg>`
  - Centering/vertical alignment for the chevron and focus styles are handled in `static/dashboard.css`.
- “All/Clear” buttons per section live directly in the `<summary>` right‑side meta container.
- Sort control
  - Sidebar: radio options live under the “Sort by” filter section.
  - Header: a compact `<select id="sortSelect">` is shown for mobile (`lg:hidden`) in `dashboard_v3_template.html:539`.

## Accessibility Tips
- Summary/focus visibility
  - Ensure `<summary>` elements keep `:focus-visible` outlines for keyboard users (CSS already included).
- Button names and titles
  - Keep ARIA roles minimal; rely on real `<button>`/`<a>` and good text labels.
  - The action bar sets `title` on CTA buttons to expose durations (`Read • 5m`).
- No autoplay
  - The V4 audio UI is “audio‑first” in presentation but never autoplays on load.

## Performance Notes
- Prefer CSS transforms/shadows tuned for 60fps; heavy blur/shadow on many cards can add CPU/GPU cost.
- Avoid forcing sync layout in renderers; build strings and set `innerHTML` once per card (current approach).
- Use image `loading="lazy"` on thumbnails (already enabled) to keep initial load fast.

## Debugging & Cache Busting
- If edits don’t appear in the browser after a Render deploy:
  - Hard refresh, then try DevTools → Network → “Disable cache”.
  - Bump the `?v=` cache params in `dashboard_v3_template.html` for `dashboard.css`, `dashboard_v3.js`, and `ui_flags.js`.
- Confirm `ui_flags.js` at repo root is the one being loaded (not `static/ui_flags.js`, which is reference‑only).

## Sanity Checklist (Cards)
- List and Grid renderers both reflect your changes.
- Title clamp, chip density, and CTA sizes look good at sm/md/lg breakpoints.
- Focus rings are visible on summary toggles, chips, and buttons.
- Play/Pause state updates correctly and the “Now playing” pill syncs.
- No layout jumps when switching sort/pagination.

## Do / Don’t
- Do centralize visuals in `static/dashboard.css`; keep renderers focused on structure.
- Do bump cache params when you change CSS/JS.
- Don’t duplicate flag definitions; edit the root `ui_flags.js` only.
- Don’t introduce autoplay; keep audio user‑initiated.

---
For a quick overview, also see:
- `README.md` → “Card Styling and Cache Busting” and “New Contributor Quick Start”
- `docs/ARCHITECTURE.md` → “Cards (V4 Stream/Mosaic)”
