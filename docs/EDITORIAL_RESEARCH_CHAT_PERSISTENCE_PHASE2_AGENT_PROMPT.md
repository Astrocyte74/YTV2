# Agent Prompt: Editorial Research Chat Persistence — Phases 2 & 3

## READ FIRST

Read these files in order before writing any code:

1. `/Users/markdarby16/16projects/ytv2/AI_AGENT_GUIDELINES.md` — project rules
2. `/Users/markdarby16/16projects/ytv2/dashboard16/docs/EDITORIAL_RESEARCH_CHAT_PERSISTENCE_BRIEF.md` — the full persistence brief (read the "Chat Persistence Modes", "Chat Turn Deletion", and "Rollout Plan" sections)
3. `/Users/markdarby16/16projects/ytv2/dashboard16/docs/EDITORIAL_RESEARCH_CONVERSATION_BRIEF.md` — Phase 1 feature context

## YOUR TASK

Implement **Phase 2** (Frontend Hydration) and **Phase 3** (Deletion UI) from the persistence brief.

Phase 1 (backend) is already done and verified. The backend now:
- Persists chat turns to `follow_up_chat_turns` table
- Returns `chat_turns` array in the thread response alongside `turns`
- Supports `persist: bool` on the chat request (default True)
- Returns `persisted: bool` on the chat response
- Has DELETE endpoints at `/api/research/follow-up/chat-turns/{turn_id}` and `/api/research/follow-up/chat-turns?follow_up_run_id={id}`
- Dashboard `server.py` proxies both DELETE routes

## FILES TO MODIFY

Only modify files in `/Users/markdarby16/16projects/ytv2/dashboard16/`:

- `static/editorial_dashboard.js` — main changes
- `static/editorial_dashboard.css` — styling for delete UI

Do NOT modify:
- Any backend files (`backend/` directory)
- `server.py` (proxy routes already exist from Phase 1)
- `backup/`, `archive/`, `render_backup/`, `DO_NOT_TOUCH_*`

## BACKEND API SHAPES (read-only reference)

### Thread response (GET `/api/research/follow-up/thread`)

```json
{
  "video_id": "string",
  "root_follow_up_run_id": 123,
  "current_follow_up_run_id": 123,
  "turns": [
    {
      "follow_up_run_id": 123,
      "approved_questions": ["question text"],
      "answer": "research report text (markdown)",
      "sources": [{"name": "", "url": "", "domain": "", "tier": ""}],
      "status": "completed",
      "created_at": "2026-04-07T..."
    }
  ],
  "chat_turns": [
    {
      "id": 456,
      "follow_up_run_id": 123,
      "video_id": "string",
      "summary_id": null,
      "question": "What about oil prices?",
      "answer": "markdown answer text",
      "sources": [],
      "chat_meta": {"llm_provider": "openrouter", "llm_model": "...", "mode": "report-chat"},
      "created_at": "2026-04-07T..."
    }
  ]
}
```

Key difference: `turns` have `approved_questions` (array), `chat_turns` have `question` (single string).

### Chat request (POST `/api/research/follow-up/chat`)

```json
{
  "video_id": "string",
  "follow_up_run_id": 123,
  "preferred_variant": "deep-research",
  "question": "string",
  "history": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}],
  "persist": true
}
```

### Chat response

```json
{
  "video_id": "string",
  "follow_up_run_id": 123,
  "answer": "markdown text",
  "sources": [],
  "meta": {"mode": "report-chat", "llm_provider": "...", "llm_model": "..."},
  "persisted": true
}
```

### Delete single turn

```
DELETE /api/research/follow-up/chat-turns/{turn_id}?video_id=xxx
→ {"deleted": true, "turn_id": 456}
```

### Delete all turns for a run

```
DELETE /api/research/follow-up/chat-turns?follow_up_run_id=123&video_id=xxx
→ {"deleted": true, "follow_up_run_id": 123, "count": 5}
```

## IMPLEMENTATION ORDER

### Step 1: Update `_loadResearchThread` to render `chat_turns` (~line 2172)

Currently, after loading the thread, it only calls `_renderResearchTurns(data)` which renders `data.turns`. You need to also render `data.chat_turns` below the research turns.

Change the success handler (around line 2245) to also render chat turns:

```javascript
// We have content (variant report, thread turns, or both)
if (data && Array.isArray(data.turns) && data.turns.length > 0) {
    self._researchThreadData = data;
    self._researchVideoId = videoId;
    self._renderResearchTurns(data);
}

// Render persisted chat turns
if (data && Array.isArray(data.chat_turns) && data.chat_turns.length > 0) {
    self._researchVideoId = videoId;
    self._renderChatTurns(data.chat_turns);
}
```

Also store the `follow_up_run_id` for later use in delete requests:
```javascript
self._researchRunId = (data && data.current_follow_up_run_id) || (data && data.root_follow_up_run_id) || null;
```

### Step 2: Add `_renderChatTurns(chatTurns)` method

Add a new method that renders persisted chat turns into the `[data-research-turns]` container. Chat turns have a different shape than research turns:

```javascript
_renderChatTurns(chatTurns) {
    var turnsEl = document.querySelector('[data-research-turns]');
    if (!turnsEl) return;

    for (var i = 0; i < chatTurns.length; i++) {
        var ct = chatTurns[i];
        var turnDiv = document.createElement('div');
        turnDiv.className = 'ed-research__turn ed-research__turn--chat';
        turnDiv.setAttribute('data-chat-turn-id', ct.id);

        // User question
        var qDiv = document.createElement('div');
        qDiv.className = 'ed-research__turn-question ed-research__turn-question--chat';
        qDiv.textContent = ct.question || '';
        turnDiv.appendChild(qDiv);

        // Assistant answer (rendered as markdown)
        if (ct.answer) {
            var aDiv = document.createElement('div');
            aDiv.className = 'ed-research__turn-answer';
            aDiv.innerHTML = renderMarkdown(ct.answer);
            turnDiv.appendChild(aDiv);
        }

        // Delete button (small, on hover)
        var deleteBtn = document.createElement('button');
        deleteBtn.className = 'ed-research__turn-delete';
        deleteBtn.setAttribute('data-action', 'research-delete-turn');
        deleteBtn.setAttribute('data-turn-id', ct.id);
        deleteBtn.textContent = '×';
        deleteBtn.title = 'Delete this exchange';
        turnDiv.appendChild(deleteBtn);

        turnsEl.appendChild(turnDiv);
    }
}
```

### Step 3: Update `_sendResearchChatWithToken` (~line 2330)

Three changes needed:

**A. Include `persist: true` in the request body:**

In the `body` object (around line 2371), add:
```javascript
var body = {
    video_id: videoId,
    preferred_variant: 'deep-research',
    question: question,
    history: history,
    persist: true
};
```

**B. Include chat_turns in history building:**

The history builder (around line 2350) only uses `threadData.turns`. It should also include persisted chat turns so the LLM has full conversation context. Add chat turns to the history:

```javascript
var history = [];
// From research turns
var existingTurns = (threadData.turns) || [];
for (var h = 0; h < existingTurns.length; h++) {
    if (existingTurns[h].answer) {
        if (existingTurns[h].approved_questions && existingTurns[h].approved_questions.length > 0) {
            history.push({ role: 'user', content: existingTurns[h].approved_questions[0] });
        }
        history.push({ role: 'assistant', content: existingTurns[h].answer });
    }
}
// From persisted chat turns
var existingChatTurns = (threadData.chat_turns) || [];
for (var c = 0; c < existingChatTurns.length; c++) {
    if (existingChatTurns[c].question) {
        history.push({ role: 'user', content: existingChatTurns[c].question });
    }
    if (existingChatTurns[c].answer) {
        history.push({ role: 'assistant', content: existingChatTurns[c].answer });
    }
}
```

**C. After successful answer, re-hydrate from thread instead of manually pushing to turns:**

Currently on success (~line 2395), it manually pushes into `self._researchThreadData.turns`. Change to reload from backend:

```javascript
// Replace the manual push with a thread reload
if (data.persisted) {
    // Reload thread to get the persisted chat turn with its ID
    self._loadResearchThread();
} else {
    // Fallback: manually append the turn (not persisted)
    var fallbackTurn = document.createElement('div');
    // ... same as current optimistic rendering
}
```

Actually, a simpler approach that avoids a full reload: after the answer comes back, just append the turn to the DOM with the turn ID from the response (if `persisted`). The response includes `follow_up_run_id` but NOT the chat turn ID. So you'll need to either:

- **Option A (simpler):** Keep the current optimistic append approach AND also do a full `_loadResearchThread()` call. This gives you the persisted turn IDs. But it causes a visual flash.

- **Option B (recommended):** Keep the current optimistic append. Don't reload. The next time the user opens the reader, `_loadResearchThread()` will fetch the persisted turns. For the current session, the optimistic turns are sufficient. The delete button won't show on optimistic turns (no `data-chat-turn-id`), but that's fine — you can't delete a turn that hasn't been persisted yet.

Go with **Option B**. Keep the current optimistic rendering. Store `data.persisted` somewhere if needed, but don't change the DOM append logic. The key change is just adding `persist: true` to the request body and including `chat_turns` in history.

### Step 4: Add delete handlers to `bindEvents`

Add these delegated click handlers alongside the existing research handlers (around line 1751):

```javascript
// Research: Delete single chat turn
if (e.target.closest('[data-action="research-delete-turn"]')) {
    var turnId = e.target.closest('[data-action="research-delete-turn"]').dataset.turnId;
    if (turnId) this._deleteResearchChatTurn(turnId);
    return;
}

// Research: Clear all chat history
if (e.target.closest('[data-action="research-clear-chat"]')) {
    this._clearResearchChat();
    return;
}
```

### Step 5: Add delete methods

```javascript
_deleteResearchChatTurn(turnId) {
    var self = this;
    this.requireAdminToken(function (token) {
        var videoId = self._researchVideoId || '';
        fetch('/api/research/follow-up/chat-turns/' + encodeURIComponent(turnId) + '?video_id=' + encodeURIComponent(videoId), {
            method: 'DELETE',
            headers: { 'Authorization': 'Bearer ' + token }
        })
            .then(function (resp) { return resp.json(); })
            .then(function (data) {
                if (data.deleted) {
                    // Remove the turn from DOM
                    var el = document.querySelector('[data-chat-turn-id="' + turnId + '"]');
                    if (el) {
                        el.style.transition = 'opacity 0.3s ease';
                        el.style.opacity = '0';
                        setTimeout(function () { el.remove(); }, 300);
                    }
                }
            })
            .catch(function (err) {
                self.showToast('Failed to delete turn: ' + err.message, 'error');
            });
    });
}

_clearResearchChat() {
    var self = this;
    if (!this._researchRunId) return;

    this.showConfirm('Clear all chat history for this research?', function () {
        self.requireAdminToken(function (token) {
            var videoId = self._researchVideoId || '';
            var params = 'follow_up_run_id=' + encodeURIComponent(self._researchRunId) + '&video_id=' + encodeURIComponent(videoId);
            fetch('/api/research/follow-up/chat-turns?' + params, {
                method: 'DELETE',
                headers: { 'Authorization': 'Bearer ' + token }
            })
                .then(function (resp) { return resp.json(); })
                .then(function (data) {
                    if (data.deleted) {
                        // Remove all chat turns from DOM
                        var chatTurns = document.querySelectorAll('[data-chat-turn-id]');
                        for (var i = 0; i < chatTurns.length; i++) {
                            chatTurns[i].remove();
                        }
                        self.showToast('Chat history cleared');
                    }
                })
                .catch(function (err) {
                    self.showToast('Failed to clear chat: ' + err.message, 'error');
                });
        });
    });
}
```

### Step 6: Add "Clear conversation" button to the composer

In `_renderResearchPanel` (~line 2084), add a "Clear" button in the composer actions:

```javascript
html += '<button class="ed-btn ed-btn--ghost ed-btn--sm" data-action="research-run">Run Research</button>';
html += '<button class="ed-btn ed-btn--ghost ed-btn--sm" data-action="research-clear-chat">Clear Chat</button>';
```

### Step 7: CSS for delete UI

Add to `editorial_dashboard.css`:

```css
/* Chat turn — distinct from research turn */
.ed-research__turn--chat {
    position: relative;
}
.ed-research__turn--chat .ed-research__turn-question--chat {
    font-family: var(--ed-font-body);
    font-size: 0.82rem;
    color: var(--ed-color-text);
    font-style: italic;
    padding-left: 0.5rem;
    border-left: 2px solid var(--ed-color-accent);
    margin-bottom: 0.5rem;
}

/* Delete button — visible on hover */
.ed-research__turn-delete {
    position: absolute;
    top: 0.4rem;
    right: 0.4rem;
    background: none;
    border: none;
    color: var(--ed-color-muted);
    font-size: 1rem;
    cursor: pointer;
    opacity: 0;
    transition: opacity var(--ed-transition-fast);
    padding: 0.1rem 0.4rem;
    line-height: 1;
}
.ed-research__turn--chat:hover .ed-research__turn-delete {
    opacity: 0.6;
}
.ed-research__turn-delete:hover {
    opacity: 1 !important;
    color: #f87171;
}
```

## CRITICAL RULES

- **Git repo** is at `dashboard16/`, run git commands from there
- After every JS change: `cd /Users/markdarby16/16projects/ytv2/dashboard16 && node --check static/editorial_dashboard.js`
- After every change: `docker restart ytv2-dashboard`, then hard-refresh browser (Cmd+Shift+R)
- **Null-check ALL class properties** before accessing them (see AI_AGENT_GUIDELINES.md section 6). Every `this._researchThreadData`, `this._researchRunId`, `this._researchVideoId` access must have a fallback.
- Use `var` not `let/const` (matching existing code style)
- Use `.bind(this)` or `var self = this` for callbacks (no arrow functions)
- Test incrementally — don't write 100+ lines before testing
- Do NOT modify backend files or server.py

## VERIFICATION

After implementation, test:

1. **Thread hydration:** Open the Iran article (`31eae7ffa4a1d8e0b09956d6`), click Research tab. If you previously asked questions, the persisted chat turns should appear below the research report.

2. **Ask a new question:** Type a question, press Enter. The answer should appear. Refresh the page, open Research tab again — the chat turn should still be there (loaded from backend).

3. **Delete a turn:** Hover over a chat turn, click the × button. The turn should fade out and be removed. Refresh the page — it should stay gone.

4. **Clear all chat:** Click "Clear Chat" in the composer. Confirm the dialog. All chat turns should be removed. Refresh — they should stay gone.

5. **Tab switching:** Switch between Summary, Research, and Transcript tabs. Everything should show/hide correctly.

6. **Single-variant report:** Open a report with only one summary variant (no transcript). The Research tab should still appear.
