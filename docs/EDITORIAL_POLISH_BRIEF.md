# Editorial Polish Brief

Visual-only pass on the editorial dashboard. No new data model work, no new filtering logic, no changes to topic/subtopic behavior. The goal is tighter, more intentional styling across the header, dropdowns, and card typography.

**Applies to:**
- `static/editorial_dashboard.css`
- `static/editorial_dashboard.js` (template HTML strings only — no logic changes)

**Do not:**
- change the single-select topic/subtopic model
- move filters back into the page body
- add new nav items or card types
- reintroduce rails or category sections
- change any JS logic — only CSS changes and HTML string adjustments in `renderHeroCard()` / `renderFeatureCard()`

## 1. Header Spacing And Alignment

**Current state (CSS lines 44-160):**

The top bar works functionally but spacing feels mechanical. Key measurements:
- `#ed-topbar` gap: `var(--ed-space-md)` (0.75rem)
- `.ed-topbar__nav` gap: `var(--ed-space-sm)` (0.5rem)
- `.ed-nav` gap: `0.15rem`
- `.ed-refine-btn` padding: `0.4rem 0.75rem`, has its own border
- `.ed-nav__tab` padding: `0.35rem 0.75rem`, no border
- `.ed-topbar__link` ("Classic") has no visual differentiation from nav tabs

**Issues:**
- `Recent`, `Topics`, `Refine`, `Classic` feel adjacent rather than composed
- Refine button has a border, nav tabs don't — visual family is broken
- No visual separator between the nav group and the "Classic" utility link
- Overall topbar height feels slightly tall

**Target adjustments:**
- Unify `Recent`, `Topics`, `Refine` into one visual family — consistent padding, no mixed border/no-border
- Add a subtle separator (thin border or wider gap) between the nav group and `Classic`
- Reduce overall topbar vertical padding slightly (from `var(--ed-space-sm)` to `0.5rem`)
- Make `Classic` feel like a quiet utility link: smaller or more muted than nav tabs
- Ensure active nav state is clear without being heavy — current `background: var(--ed-color-surface)` is good, just ensure consistency
- Consider making the brand name slightly smaller or lighter to reduce its dominance

## 2. Dropdown Menus (Topics + Refine)

**Current state (CSS lines 164-260):**

Both dropdowns share similar structure. The Topics dropdown now has a 2-level submenu (categories → subcategories).

**Issues:**
- Row heights and horizontal padding are slightly tight inside the dropdowns
- The submenu back button and header area feel visually equal to the items — needs more hierarchy
- Count badges on the right are useful but visually equal weight to labels
- The dropdown border/shadow is slightly heavy
- First-level items and second-level subcategory items look identical — needs visual differentiation

**Target adjustments:**

### Shared dropdown refinements
- Slightly increase horizontal padding (from `0.5rem 1rem` to `0.55rem 1rem` or similar)
- Soften the box-shadow (reduce from `0.5` opacity to `0.35` or similar)
- Ensure hover states are subtle and premium, not bright

### Topics dropdown specifics
- First-level category items: slightly larger or bolder text
- Second-level subcategory items: slightly smaller, more muted — use `padding-left: 1.25rem` or similar to create visual indent
- Back button row: visually quieter than items — smaller text, more padding, lighter color
- Count badges: reduce opacity or font-size slightly so labels dominate
- "All [Category]" option in submenu: visually distinct from subcategories (could use a thin bottom border separator)

### Refine menu specifics
- Already structurally good — just ensure visual consistency with Topics dropdown refinements
- The `ed-refine-menu__item` (Sort, Source, Type, Audio rows) should match Topics first-level items
- The submenu buttons should match Topics subcategory items

## 3. Hero And Support Card Typography

**Current state:**

Hero card (CSS line 402):
- Title: `2rem`, `font-weight: 700`, `line-height: 1.2`
- Excerpt: `0.95rem`, `line-height: 1.65`, `max-width: 520px`
- Body gap: `0.6rem`
- Hero meta: `0.7rem`, `opacity: 0.7`

Support cards (CSS line 479):
- Title: `1rem`, `font-weight: 600`, `line-height: 1.35`, `-webkit-line-clamp: 3`
- Body gap: `0.25rem`
- Meta: `0.72rem`

Feed cards (CSS line 517):
- Title: `0.9rem`, `font-weight: 500`, `line-height: 1.35`, `-webkit-line-clamp: 2`
- Meta: `0.7rem`

**Issues:**
- Hero title at `2rem` feels slightly large relative to the excerpt at `0.95rem` — jump in scale is a bit harsh
- Hero body gap `0.6rem` is slightly tight for the amount of content (meta + title + excerpt + chip + actions)
- Support card body gap `0.25rem` feels cramped — title, meta, and potential excerpt need breathing room
- The typographic hierarchy between hero (2rem) → support (1rem) → feed (0.9rem) has a large gap between hero and support

**Target adjustments:**

### Hero
- Consider reducing title to `1.75rem` or increasing excerpt to `0.95rem` with slightly looser line-height
- Increase body gap from `0.6rem` to `0.75rem` for better breathing room
- Ensure the category chip stays very quiet (it already has `opacity: 0.55` which is good)
- Consider adding `max-width: 560px` to the hero body column to prevent overly wide text on large screens

### Support cards
- Increase body gap from `0.25rem` to `0.4rem`
- Ensure meta text sits clearly below the title with enough margin
- Consider bumping title from `1rem` to `1.05rem` to better bridge the gap between hero and feed

### Feed cards
- These are already tight and scannable — minor adjustments only
- Ensure the gap between feed card image and title matches support cards

## 4. Responsive Quick Review

**Current state (CSS lines 850-862):**

Only two breakpoints:
- `1024px`: hero goes single column, support goes 2-column, feed goes 1-column
- `640px`: smaller hero title, support goes 1-column

**Target adjustments:**
- At `1024px`: verify the header nav still fits without wrapping. The `Recent / Topics / Refine / Classic` group may need to tighten.
- At `640px`: consider hiding the search input behind a toggle icon to save space, or reduce its width
- At `640px`: ensure dropdown menus don't overflow the viewport width — may need `right: 0; left: auto` on Topics dropdown at small widths
- Do NOT do a full mobile redesign — just prevent breakage and obvious overflow

## Acceptance Standard

This pass is successful if:
- the top bar feels composed — nav items read as one family, Classic reads as utility
- both dropdowns feel polished and consistent with each other
- the hero reads confidently as the page anchor with better vertical rhythm
- support cards feel less cramped
- nothing breaks at tablet width

This pass is not about adding capability. It is about making the existing system feel finished.
