# ✅ Status Tracker (Phased Rollout)

| Phase   | Status |
|---------|--------|
| Phase 0 | **[DONE]** |
| Phase 1 | **[DONE]** |
| Phase 2 | **[DONE]** |
| Phase 3 | **[NEXT]** |

# 🧩 Feature Flags (Runtime)

Current feature flags:
```js
{
  compactCardActions: true,
  cardExpandInline: true,
  queueEnabled: false,
  showWaveformPreview: false
}
```

# 🔌 API Contracts (Client Expectations)

- **GET `/api/report/:id`**
  - Returns detail for a report.
  - Example response:
    ```json
    {
      "id": "abc123",
      "title": "Sample Title",
      "summary": "Summary text here.",
      "channel": "Channel Name",
      "duration": 123,
      "language": "en"
    }
    ```
- **POST `/api/delete`**
  - Request body:
    ```json
    { "ids": ["abc123"] }
    ```
  - Response:
    ```json
    { "status": "ok" }
    ```
- **POST `/api/refresh`**
  - Triggers a refresh of data (if supported).
  - Example response:
    ```json
    { "status": "ok", "refreshed": true }
    ```

# ⌨️ Keyboard Map

| Action   | Shortcut |
|----------|----------|
| Listen   | L        |
| Read     | R        |
| Watch    | W        |
| Collapse (expanded card) | Escape   |
| Next in queue | N    |
| Previous in queue | P |
| Focus mini-player | M |
| Delete (with focus) | Del or D |
| Move between cards | Arrow keys / Tab |


# YTV2 Dashboard UI/UX Enhancement Plan

This plan details phased UI/UX improvements for the YTV2 Audio dashboard, focusing on clarity, usability, and polished interactions.

---

## Feature Flags Setup (Phase 0)

### Files to touch:
- `static/ui_flags.js`
- Dashboard template (e.g., `dashboard_v3_template.html`)

### Tasks:

1. Create `static/ui_flags.js` exporting:
   ```js
   export const UI_FLAGS = {
     compactCardActions: true,
     cardExpandInline: false,  // Enable in Phase 2
     queueEnabled: false,       // Enable in Phase 3
     showWaveformPreview: false
   };
   ```
2. Ensure the dashboard template loads `ui_flags.js` **before** `dashboard_v3.js`.
3. Verify flags are readable at runtime without a build step.
4. Confirm old UI renders correctly when flags are off.

### Done when:
- [ ] Flags module exists and exports correct flags.
- [ ] Dashboard loads flags before main JS.
- [ ] Old UI works with flags disabled.

---

## Phase 1 — Card CTAs, Delete Redesign, Mini-Player Visibility

### Files to touch:
- `dashboard_v3_template.html`
- `static/dashboard_v3.js`

### Tasks:

1. **Add Card CTA Strip (Top-Right of Each Card)**
   - Insert this Tailwind-based HTML snippet inside each card:
     ```html
     <div class="flex items-center gap-2 absolute top-3 right-3">
       <button class="ybtn ybtn-ghost" data-action="listen" title="Listen (L)">
         <span class="i">▶</span><span class="sr-only">Listen</span>
       </button>
       <button class="ybtn ybtn-ghost" data-action="read" title="Read (R)">
         <span class="i">☰</span><span class="sr-only">Read</span>
       </button>
       <button class="ybtn ybtn-ghost" data-action="watch" title="Watch on YouTube (W)">
         <span class="i">▣</span><span class="sr-only">Watch on YouTube</span>
       </button>
     </div>
     ```
   - Add keyboard shortcuts **L**, **R**, **W** that trigger respective actions when a card has focus.

2. **Redesign Delete Control**
   - Replace the hover trash icon with a small secondary icon button (e.g., kebab ⋮ or bin) inside the CTA group.
   - Show this icon on card hover/focus only.
   - Implement a lightweight confirmation popover before deletion.
   - On delete success, optimistically remove the card and show a toast notification.

3. **Mini-Player Refresh**
   - Make mini-player always visible in the left rail.
   - Display "Now Playing" title and thumbnail.
   - Use clear iconography and ensure keyboard focus styles.

4. **JS Hooks:**
   - Add delegated event handler for card actions:
     ```js
     onClickCardAction(e) {
       const btn = e.target.closest('[data-action]');
       if (!btn) return;
       const action = btn.dataset.action;
       const id = btn.closest('[data-report-id]').dataset.reportId;
       if (action === 'listen') this.playReport(id);
       if (action === 'read') this.handleRead(id);
       if (action === 'watch') this.openYoutube(id);
     }
     ```
   - Implement `handleDelete(id)` with a fetch POST to `/api/delete`.

### Done when:
- [ ] Cards have visible Listen, Read, Watch buttons with accessible titles.
- [ ] Keyboard shortcuts L/R/W work on focused cards.
- [ ] Delete button is discoverable, requires confirmation, and does not cause layout shifts.
- [ ] Mini-player is always visible, clear, and keyboard accessible.

---

## Phase 2 — Inline Expand ("Read") with Virtualized List

### Files to touch:
- `dashboard_v3_template.html`
- `static/dashboard_v3.js`

### Tasks:

1. **Expandable Region per Card**
   - Append a hidden section under each card header:
     ```html
     <section role="region" aria-live="polite" hidden></section>
     ```
   - On "Read" action:
     - If `UI_FLAGS.cardExpandInline` is true, fetch `/api/report/:id` for summary.
     - Render summary inside the section with smooth max-height transition.
     - Show badges (channel, duration, language, etc.) and summary text.
     - Include buttons for Listen and Collapse inside expanded content:
       ```html
       <div class="mt-3 rounded-xl bg-slate-800/60 border border-slate-700 p-4 space-y-4" data-expanded>
         <div class="flex items-center gap-3 text-slate-300 text-sm flex-wrap">
           <!-- badges here -->
         </div>
         <div class="prose prose-invert max-w-none text-slate-100 leading-7">
           <!-- summary paragraphs -->
         </div>
         <div class="flex items-center justify-between">
           <button class="ybtn" data-action="listen">▶ Listen</button>
           <button class="ybtn ybtn-ghost" data-action="collapse">Collapse</button>
         </div>
       </div>
       ```

2. **URL State & Deep Linking**
   - Update URL hash to `#report=<id>` on expand.
   - On page load, auto-expand card if URL hash matches.
   - Scroll expanded card into view.
   - Support Escape key and browser Back button to collapse.

3. **Accessibility & Performance**
   - Allow only one card expanded at a time.
   - Move keyboard focus to expanded region title.
   - Provide visible Collapse button.
   - Maintain existing virtual scroll logic for performance with 100+ items.

### Done when:
- [ ] "Read" expands card inline with smooth animation.
- [ ] URL hash reflects expanded card; deep linking works.
- [ ] Escape and Back button collapse expanded card.
- [ ] Only one card expanded at a time.
- [ ] Performance is smooth with large lists.

---

## Phase 3 — Queue, Waveform Preview, and Polishing

### Files to touch:
- `static/dashboard_v3.js`
- Possibly template files for UI updates

### Tasks:

1. **Queue (behind `queueEnabled` flag)**
   - On Listen, set queue to current result order.
   - Mini-player shows "Next" button.
   - Highlight currently playing card.
   - Persist queue state in `sessionStorage`.

2. **Micro-Progress / Waveform Preview (flagged)**
   - Add simple horizontal progress bar under card thumbnail reflecting playback position.

3. **Thumbnail Consistency**
   - Use `loading="lazy"` on images.
   - Add placeholders to prevent layout shifts.

4. **Telemetry**
   - Fire events for key actions: `cta_listen`, `cta_read`, `cta_watch`, etc.

### Done when:
- [ ] Continuous listening queue works.
- [ ] Playing card is visually highlighted.
- [ ] Thumbnails load lazily without layout shift.
- [ ] Telemetry events fire on CTA actions.

---

## Component & API Notes

### CSS (Insert in global stylesheet or component CSS)

```css
.ybtn {
  @apply px-2.5 py-1.5 rounded-lg bg-slate-700/60 hover:bg-slate-600/60 text-slate-100 text-sm
         border border-slate-600/50 transition active:scale-[0.98] focus-visible:outline-none
         focus-visible:ring-2 ring-offset-2 ring-offset-slate-900 ring-indigo-400;
}
.ybtn-ghost {
  @apply bg-transparent border-slate-600/40 hover:bg-slate-700/30;
}
.ycard {
  @apply relative rounded-2xl bg-slate-800/60 border border-slate-700 overflow-hidden shadow
         hover:shadow-lg transition;
}
```

### API Contracts

- **Inline detail:**  
  `GET /api/report/:id` →  
  ```json
  { "id": "...", "title": "...", "summary": "...", ... }
  ```
- **Delete:**  
  `POST /api/delete` with body:  
  ```json
  { "ids": ["<id>"] }
  ```  
  Response:  
  ```json
  { "status": "ok" }
  ```

---

## Acceptance Criteria & Testing

### Phase 1
- [ ] Cards have 3 CTAs (Listen, Read, Watch) working with mouse and keyboard.
- [ ] Delete action requires confirmation and removes card smoothly.
- [ ] Mini-player is visible, accessible, and shows current track.

### Phase 2
- [ ] "Read" expands inline with smooth animation.
- [ ] URL hash updates and deep linking works.
- [ ] Escape and Back button collapse expanded card.
- [ ] Performance remains smooth with 100+ items.

### Phase 3
- [ ] Queue enables continuous playback.
- [ ] Playing card is visually highlighted.
- [ ] Thumbnails load lazily without causing layout shift.
- [ ] Telemetry events fire correctly.

### General
- [ ] Full keyboard navigation (Tab, Enter, Space, L/R/W shortcuts).
- [ ] Screen reader announces all controls and states properly.
- [ ] Mobile tap targets are ≥ 40px and layouts are fluid.