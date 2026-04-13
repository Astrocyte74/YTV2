# Ponderings Tab Redesign — Agent Implementation Prompt

You are implementing a UI redesign of the "Research" tab in the editorial dashboard. Read this entire document before writing any code.

## Project Location

`/Users/markdarby16/16projects/ytv2/dashboard16/`

## Files to Modify

- `static/editorial_dashboard.js` — all JS logic changes
- `static/editorial_dashboard.css` — all CSS additions

**No changes to `server.py` or any backend files.** All needed API endpoints already exist and are proxied.

## Context

The editorial dashboard has a reader panel with tabs (Summary variants, Research, Transcript). The "Research" tab currently opens a modal popup when the user clicks "Run Research" to select suggested deep-research questions. This redesign:

1. Renames the tab to "Ponderings"
2. Eliminates the modal entirely
3. Shows suggested deep-research questions inline in a "Dig Deeper" section
4. Keeps the existing chat interface below
5. Lets users click a suggested question to start research directly (no popup)

This is **Phase 1 only** — frontend UI redesign with lazy suggestion fetching. Phase 2 (backend pre-generation of suggestions during summary creation) is a separate future task.

## Key Design Decisions

1. **No auto-running deep research** — only runs when user clicks a suggestion or types + "Research this"
2. **Lazy suggestion fetch** — `POST /api/research/follow-up/suggestions` when tab opens
3. **Composer UX**: Primary "Ask" button, secondary "Research this" (only visible when composer has text)
4. **Auto-collapse threshold**: Dig Deeper collapses after 2 completed chat pairs
5. **Keep internal API names** — `data-action="show-research"`, endpoint paths all stay as `research`/`follow-up`. Only the visible UI label changes to "Ponderings"
6. **Keep custom research** — user can type their own question and run research inline
7. **No streaming** — keep non-streaming chat path (SimpleHTTP proxy limitation)

## Section Order Inside Ponderings Tab

1. **Dig Deeper** — suggested question cards (collapsible, top of tab)
2. **Existing deep-research report** (if present, rendered as before)
3. **Research/chat turns** (existing turns + chat pairs)
4. **Composer** — Ask (primary) + Research this (secondary, hidden until text) + Clear Chat (hidden until chat turns exist)

## Key Existing Code References

Read these before starting:

- `_renderResearchPanel(data)` — builds the Research tab HTML. This is the main method to restructure.
- `_showResearch()` — shows the Research panel, calls `_loadResearchThread()`. Add `_loadDigDeeperSuggestions()` call here.
- `_loadResearchThread()` — fetches thread data from `GET /api/research/follow-up/thread`
- `_renderResearchTurns(threadData)` — renders research turns + chat pairs
- `_openResearchSuggestions()` / `_openResearchSuggestionsWithToken()` — THE MODAL. This will be stubbed to a no-op.
- `_executeResearchRun()` — triggers research run from the modal. Reference for building `_executeInlineResearch()`.
- `_sendResearchChatWithToken()` — sends chat follow-up questions
- `renderReaderContent(data)` — builds the full reader, calls `_renderResearchPanel`. Tab label "Research" is at ~line 2992.
- `_updateClearChatButton()` — shows/hides Clear Chat button

## Implementation Steps

### Step 1: Tab Label Rename

In `renderReaderContent`, change the tab button text:
```
"Research" → "Ponderings"
```
Keep `data-action="show-research"` unchanged.

### Step 2: Helper Method `_getResearchSourceContext()`

Add a new helper that extracts source context from reader data. This logic is currently duplicated in `_openResearchSuggestionsWithToken` and will be used by both `_loadDigDeeperSuggestions` and `_executeInlineResearch`.

Returns: `{ summaryText: string, sourceContext: object, videoId: string }`

Logic:
- Get videoId from `this._readerData.video.video_id`
- Get summaryText: iterate `this._readerData.summary_variants`, find first non-deep-research variant with text/html. Fallback to `data.summary.text`
- Build sourceContext: channel from `video.channel`, source_url from `video.url`, content_type inferred from URL (youtube vs web)

### Step 3: Restructure `_renderResearchPanel` HTML

Replace the current panel HTML with the two-section layout below. Keep the same outer container attributes (`data-research-panel`, `data-video-id`).

```
.ed-research[data-research-panel]
  .ed-research__loading[data-research-loading] — hidden by default
  .ed-research__dig-deeper[data-dig-deeper-section]
    .ed-research__dig-deeper-header — "DIG DEEPER" uppercase label
    .ed-research__dig-deeper-collapsed[data-dig-deeper-collapsed] — "▸ N research questions available" (hidden by default)
    .ed-research__dig-deeper-body[data-dig-deeper-body]
      .ed-research__dig-deeper-status[data-dig-deeper-status] — "Loading suggestions..." / empty state
      .ed-research__dig-deeper-cards[data-dig-deeper-cards] — suggestion cards container
  .ed-research__chat-section
    .ed-research__thread[data-research-thread] — hidden unless hasResearch
      .ed-research__report — existing deep-research variant HTML
      .ed-research__followups[data-research-turns] — turn rendering target
    .ed-research__hint[data-research-hint] — "Ask questions or run deeper research anytime."
    .ed-research__composer
      textarea[data-research-composer] — "Ask about this report..."
      .ed-research__composer-actions
        button[data-action="research-ask"] — "Ask" (primary, disabled by default)
        button[data-action="research-run"] — "Research this" (ghost, hidden by default, shown when composer has text)
        button[data-action="clear-chat-history"] — "Clear Chat" (hidden by default)
  .ed-research__error[data-research-error] — hidden
```

**Composer "Research this" visibility**: Add logic to the existing composer input handler to show/hide the "Research this" button based on whether the textarea has text. The button should use `style.display` toggling, same pattern as the Clear Chat button.

### Step 4: Auto-Load Suggestions on Tab Open

Add `_loadDigDeeperSuggestions()` method. Called from `_showResearch()`.

Flow:
1. Get videoId from panel dataset
2. If `this._ponderingsSuggestionsVideoId === videoId` and suggestions exist, re-render cached cards and return
3. Show "Loading suggestions..." in status element
4. Call `requireAdminToken()` to get auth
5. Use `_getResearchSourceContext()` for request params
6. `POST /api/research/follow-up/suggestions` with body: `{ video_id, summary, preferred_variant: 'deep-research', source_context, max_suggestions: 4 }`
7. On success: cache suggestions in `this._ponderingsSuggestions` and `this._ponderingsSuggestionsVideoId`, hide status, render cards
8. On failure: show "No prompts yet. Ask about this report or start a custom research run."
9. Call `_updateDigDeeperCollapse()` after rendering

### Step 5: Render Suggestion Cards

Add `_renderDigDeeperCards(suggestions)` method.

Each suggestion renders as:
```html
<button class="ed-research__dig-deeper-card" data-action="run-suggested-research" data-question="...">
  <span class="ed-research__dig-deeper-arrow">&#x25B8;</span>
  <span class="ed-research__dig-deeper-card-text">Question text here</span>
</button>
```

Card states (applied via CSS class):
- **available** (default) — clickable, accent arrow
- **running** — `ed-research__dig-deeper-card--running`: dashed border, spinner replaces arrow, text appends "(Researching...)", card disabled
- **completed** — `ed-research__dig-deeper-card--done`: checkmark replaces arrow, reduced opacity
- **failed** — restore to available state, show toast error

### Step 6: Inline Research Execution

**6a. Add click handler for `run-suggested-research`:**
In the delegated click handler, add:
```js
if (e.target.closest('[data-action="run-suggested-research"]')) {
    var card = e.target.closest('[data-action="run-suggested-research"]');
    var question = card.dataset.question || '';
    if (question) this._executeInlineResearch(question, card);
    return;
}
```

**6b. Add `_executeInlineResearch(question, cardEl)` method:**
- Get source context via `_getResearchSourceContext()`
- If cardEl: set to `running` state (add `--running` class, disable, replace arrow with spinner)
- `requireAdminToken()` then POST to `/api/research/follow-up/run` with: `{ video_id, summary, preferred_variant: 'deep-research', source_context, approved_questions: [question], question_provenance: ['suggested'], provider_mode: 'auto', depth: 'balanced' }`
- On success: card → `completed` (checkmark, `--done` class), toast "Research started — results will appear below."
- On failure: card → restore, toast error

**6c. Modify `research-run` click handler:**
Currently calls `_openResearchSuggestions()`. Change to:
```js
if (e.target.closest('[data-action="research-run"]')) {
    var composer = document.querySelector('[data-research-composer]');
    var customQuestion = composer ? composer.value.trim() : '';
    if (customQuestion) {
        this._executeInlineResearch(customQuestion, null);
        composer.value = '';
        // update button states
    }
    return;
}
```

**6d. Stub the modal methods:**
```js
_openResearchSuggestions() { return; }
_openResearchSuggestionsWithToken() { return; }
```

### Step 7: Auto-Collapse Logic

Add `_updateDigDeeperCollapse()` method:

- Count completed chat pairs: `(this._researchThreadData.chat_turns || []).length`
- Count suggestions: `(this._ponderingsSuggestions || []).length`
- If chat pairs >= 2 AND suggestions.length > 0:
  - Hide `[data-dig-deeper-body]` and `.ed-research__dig-deeper-header`
  - Show `[data-dig-deeper-collapsed]` with text "▸ N research questions available"
- Otherwise:
  - Show body + header, hide collapsed bar

Add collapsed bar click handler — click `[data-dig-deeper-collapsed]` to expand:
```js
if (e.target.closest('[data-dig-deeper-collapsed]')) {
    // hide collapsed, show body + header
    return;
}
```

Call `_updateDigDeeperCollapse()` from:
- `_loadResearchThread` — after thread data is loaded
- `_sendResearchChatWithToken` — after chat response is received
- `_renderResearchTurns` — after rendering
- `_loadDigDeeperSuggestions` — after suggestions load

### Step 8: CSS Styling

Add these styles to `editorial_dashboard.css`. Place after the existing research-related styles.

**Visual direction**: Editorial, calm, notebook-like. Subtle cards with hover states. NOT loud blue action cards.

```css
/* ---- Dig Deeper Section ---- */
.ed-research__dig-deeper {
    margin-bottom: var(--ed-space-sm);
    padding-bottom: var(--ed-space-sm);
    border-bottom: 1px solid var(--ed-color-border);
}
.ed-research__dig-deeper-header {
    margin-bottom: var(--ed-space-xs);
}
.ed-research__dig-deeper-title {
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--ed-color-muted);
    text-transform: uppercase;
    letter-spacing: 0.08em;
}
/* Collapsed bar */
.ed-research__dig-deeper-collapsed {
    display: flex;
    align-items: center;
    padding: var(--ed-space-xs) var(--ed-space-sm);
    background: var(--ed-color-surface);
    border: 1px solid var(--ed-color-border);
    border-radius: var(--ed-radius-sm);
    cursor: pointer;
    font-size: 0.82rem;
    color: var(--ed-color-muted);
}
.ed-research__dig-deeper-collapsed:hover {
    border-color: var(--ed-color-accent);
    color: var(--ed-color-text);
}
/* Cards */
.ed-research__dig-deeper-cards {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
}
.ed-research__dig-deeper-card {
    display: flex;
    align-items: flex-start;
    gap: 0.5rem;
    padding: 0.55rem 0.75rem;
    background: transparent;
    border: 1px solid var(--ed-color-border);
    border-radius: var(--ed-radius-sm);
    cursor: pointer;
    text-align: left;
    width: 100%;
    font-family: var(--ed-font-body);
    font-size: 0.85rem;
    color: var(--ed-color-text);
    line-height: 1.4;
}
.ed-research__dig-deeper-card:hover {
    border-color: var(--ed-color-accent);
    background: var(--ed-color-surface-hover);
}
.ed-research__dig-deeper-card:disabled {
    cursor: default;
    opacity: 0.7;
}
.ed-research__dig-deeper-arrow {
    flex-shrink: 0;
    color: var(--ed-color-accent);
    font-size: 0.8rem;
    line-height: 1.4;
}
/* Running state */
.ed-research__dig-deeper-card--running {
    border-style: dashed;
}
.ed-research__dig-deeper-spinner {
    display: inline-block;
    width: 0.8rem;
    height: 0.8rem;
    border: 2px solid var(--ed-color-border);
    border-top-color: var(--ed-color-accent);
    border-radius: 50%;
    animation: ed-spin 0.8s linear infinite;
}
@keyframes ed-spin {
    to { transform: rotate(360deg); }
}
/* Done state */
.ed-research__dig-deeper-card--done {
    opacity: 0.55;
}
.ed-research__dig-deeper-card--done .ed-research__dig-deeper-arrow {
    color: #34d399;
}
/* Status text */
.ed-research__dig-deeper-status {
    font-size: 0.82rem;
    color: var(--ed-color-muted);
    font-style: italic;
}
/* Chat section wrapper */
.ed-research__chat-section {
    display: flex;
    flex-direction: column;
    flex: 1;
    min-height: 0;
}
```

### Step 9: Empty State

If no suggestions load or suggestions array is empty:
- Show in the status element: "No prompts yet. Ask about this report or start a custom research run."
- Do NOT revert to old modal-like empty state language

## What NOT to Do

1. Do NOT modify `server.py` or any backend files
2. Do NOT auto-run deep research — only on user click
3. Do NOT rename API routes or `data-action` attributes from `research` to `ponderings`
4. Do NOT enable streaming — keep `useStream = false`
5. Do NOT fully delete `_openResearchSuggestions` / `_executeResearchRun` — stub them as no-ops
6. Do NOT remove the ability to type custom research questions
7. Do NOT give "Ask" and "Research this" equal visual weight

## State Model

Use these new instance properties (set dynamically, same pattern as existing code):
- `this._ponderingsSuggestions` — array of suggestion objects
- `this._ponderingsSuggestionsVideoId` — cache key to avoid re-fetching
- `this._researchThreadData` — existing, unchanged

Do NOT reuse `this._researchModalState` — that was for the old modal.

## Verification Checklist

After implementation, verify by testing in the browser at `http://localhost:10000/editorial`:

1. Open an editorial item → click "Ponderings" tab → suggested questions appear inline (no modal)
2. Custom "Ask" still works for grounded chat
3. Typed text in composer → "Research this" button appears → click starts research inline
4. Click a suggested question card → spinner appears → checkmark when research starts
5. Research output appears in conversation area after the run completes (may need to switch tabs and back)
6. After 2+ chat pairs → Dig Deeper section auto-collapses to slim bar with question count
7. Click collapsed bar → Dig Deeper expands
8. Switch to Summary tab and back to Ponderings → all state preserved
9. Hard refresh → persisted chat turns reload from database
10. "Clear Chat" button still works with the custom HTML modal (not browser confirm)
