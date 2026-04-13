# Agent Prompt: Editorial Research Chat Persistence (Phase 1)

## READ FIRST

Read these files in order before writing any code:

1. `/Users/markdarby16/16projects/ytv2/AI_AGENT_GUIDELINES.md` — project rules
2. `/Users/markdarby16/16projects/ytv2/dashboard16/docs/EDITORIAL_RESEARCH_CHAT_PERSISTENCE_BRIEF.md` — your primary brief (updated with deletion and temporary mode)
3. `/Users/markdarby16/16projects/ytv2/dashboard16/docs/EDITORIAL_RESEARCH_CONVERSATION_BRIEF.md` — the Phase 1 feature that's already built (for context)

## YOUR TASK

Implement **Phase 1 only** (Backend Persistence) from the persistence brief.

Phase 1 scope:
1. Create the PostgreSQL migration for `follow_up_chat_turns` table
2. Add store methods in `follow_up_store.py`
3. Add `persist` field to `FollowUpChatRequest`, `persisted` flag to `FollowUpChatResponse` in `models.py`
4. Persist chat turns in `answer_follow_up_chat_endpoint` (after successful LLM answer)
5. Extend thread endpoint to return `chat_turns` alongside existing `turns`
6. Add proxy routes in `server.py` for DELETE endpoints (Phase 3 preparation)

## EXISTING CODE TO READ FIRST (read-only, do NOT modify unless noted)

### Backend (in `/Users/markdarby16/16projects/ytv2/backend/`)

- `ytv2_api/follow_up_store.py` — existing store layer for research runs. Read the full file. You'll add new methods here.
- `ytv2_api/models.py` — read lines 189-250 for existing `FollowUpChatRequest`, `FollowUpChatResponse`, `FollowUpThreadResponse`, `FollowUpThreadTurn`. You'll extend these.
- `ytv2_api/main.py` — read lines 948-1065 for the `/thread` and `/chat` endpoint implementations. You'll modify these.
- `research_api/migrations/001_add_follow_up_research.sql` — read the existing migration to understand the schema conventions and table naming. Your migration should follow the same pattern.
- `research_api/research_service/service.py` — read lines 406-451 for `answer_follow_up_chat`. This is the stateless LLM call. You do NOT need to modify this file.

### Dashboard (in `/Users/markdarby16/16projects/ytv2/dashboard16/`)

- `server.py` — read the `_proxy_follow_up_request()` method (~line 6064) and the `_proxy_follow_up_get_request()` method for the proxy patterns. You'll add DELETE proxy routes.
- `static/editorial_dashboard.js` — read `_sendResearchChatWithToken` (~line 2295), `_loadResearchThread` (~line 2137), and `_renderResearchTurns` (~line 2253). These are the frontend methods that will consume the new `chat_turns` data. **Do NOT modify this file in Phase 1** — frontend changes are Phase 2.

## IMPLEMENTATION ORDER

### Step 1: Migration

Create `/Users/markdarby16/16projects/ytv2/backend/research_api/migrations/002_add_follow_up_chat_turns.sql`.

Use the schema from the brief. Follow the conventions from `001_add_follow_up_research.sql`.

Check: does `follow_up_research_runs` use `id` as its primary key? Verify before writing the foreign key reference. Also check if a `summaries` table exists for the `summary_id` FK — if not, omit that FK constraint.

Run the migration against the database:
```bash
source /Users/markdarby16/16projects/ytv2/backend/.env.nas
psql "$DATABASE_URL" -f /Users/markdarby16/16projects/ytv2/backend/research_api/migrations/002_add_follow_up_chat_turns.sql
```

### Step 2: Store methods

In `follow_up_store.py`, add:

- `store_follow_up_chat_turn(follow_up_run_id, video_id, question, answer, sources, chat_meta, summary_id=None)` → returns the new row id
- `get_follow_up_chat_turns(follow_up_run_id, *, video_id=None)` → returns list of dicts
- `delete_follow_up_chat_turn(turn_id, *, video_id=None)` → deletes single turn
- `delete_follow_up_chat_turns_by_run(follow_up_run_id)` → deletes all turns for a run

Follow the existing patterns in the file for DB access (likely psycopg2 or similar).

### Step 3: Models

In `models.py`:

- Add `persist: bool = True` to `FollowUpChatRequest`
- Add `persisted: bool` to `FollowUpChatResponse`
- Add a new `FollowUpChatTurnResponse` model with fields: `id`, `follow_up_run_id`, `video_id`, `question`, `answer`, `sources`, `chat_meta`, `created_at`
- Add `chat_turns: List[FollowUpChatTurnResponse] = []` to `FollowUpThreadResponse`

### Step 4: Chat endpoint persistence

In `main.py`, modify `answer_follow_up_chat_endpoint`:

After the LLM answer is produced successfully (line ~1038), if `request.persist` is True:
- Call `store.store_follow_up_chat_turn(...)` with the run id, video id, question, answer, sources, and metadata
- If the DB write fails, log the error but still return the answer with `persisted=False`
- If it succeeds, return with `persisted=True`
- If `request.persist` is False, skip the write entirely and return `persisted=False`

### Step 5: Thread endpoint extension

In `main.py`, modify the thread endpoint (`get_follow_up_thread_endpoint`):

After loading research runs, also load chat turns:
- Call `store.get_follow_up_chat_turns(active_run_id)` 
- Add them to the response as `chat_turns`

### Step 6: Delete proxy routes (preparation for Phase 3)

In `server.py`, add:

- `DELETE /api/research/follow-up/chat-turns/{turn_id}` — proxy to backend
- `DELETE /api/research/follow-up/chat-turns` (query param `follow_up_run_id`) — proxy to backend

You'll need a `_proxy_follow_up_delete_request()` method or reuse the POST proxy pattern. Add a handler in `do_DELETE` and route entries.

Also add the backend DELETE endpoints in `main.py`:
- `DELETE /api/research/follow-up/chat-turns/{turn_id}`
- `DELETE /api/research/follow-up/chat-turns?follow_up_run_id={id}`

## CRITICAL RULES

- **Git repo** is at `dashboard16/`, run git commands from there. Backend has its own git repo at `backend/`.
- **Do NOT modify** `editorial_dashboard.js` or `editorial_dashboard.css` — frontend is Phase 2.
- **Do NOT modify** `research_service/service.py` — it's stateless and correct.
- **Do NOT touch** backup/, archive/, render_backup/, DO_NOT_TOUCH_* folders.
- After every Python change: `python3 -c "import py_compile; py_compile.compile('main.py', doraise=True)"`
- After backend changes: `cd /Users/markdarby16/16projects/ytv2/backend && docker-compose restart` (or appropriate restart command)
- After server.py changes: `docker restart ytv2-dashboard`
- Verify with curl against real data (the Iran article video_id is `31eae7ffa4a1d8e0b09956d6`)
- Null-check ALL class properties in JS (not relevant for Phase 1, but remember for Phase 2)

## VERIFICATION

After implementation, test end-to-end:

```bash
# 1. Send a chat question (should persist)
source /Users/markdarby16/16projects/ytv2/backend/.env.nas 2>/dev/null
source /Users/markdarby16/16projects/ytv2/dashboard16/.env 2>/dev/null

curl -s -X POST "http://localhost:6453/api/research/follow-up/chat" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $YTV2_API_SECRET" \
  -d '{"video_id":"31eae7ffa4a1d8e0b09956d6","preferred_variant":"deep-research","question":"What are the implications for oil prices?","history":[]}' | python3 -c "import sys,json; d=json.load(sys.stdin); print('persisted:', d.get('persisted'), 'answer_len:', len(d.get('answer','')))"

# 2. Load thread (should include chat_turns)
curl -s "http://localhost:6453/api/research/follow-up/thread?video_id=31eae7ffa4a1d8e0b09956d6&preferred_variant=deep-research" \
  -H "Authorization: Bearer $YTV2_API_SECRET" | python3 -c "import sys,json; d=json.load(sys.stdin); print('turns:', len(d.get('turns',[])), 'chat_turns:', len(d.get('chat_turns',[])))"

# 3. Test temporary mode (should NOT persist)
curl -s -X POST "http://localhost:6453/api/research/follow-up/chat" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $YTV2_API_SECRET" \
  -d '{"video_id":"31eae7ffa4a1d8e0b09956d6","preferred_variant":"deep-research","question":"Quick question","history":[],"persist":false}' | python3 -c "import sys,json; d=json.load(sys.stdin); print('persisted:', d.get('persisted'))"
```

## PHASES YOU SHOULD NOT START

- Phase 2 (frontend hydration from backend chat_turns) — separate session
- Phase 3 (delete UI in editorial reader) — separate session
- Phase 4 (classic dashboard migration, merged timeline) — separate session

## QUESTIONS TO ASK BEFORE STARTING

1. Does the existing `follow_up_research_runs` table use `id` as BIGSERIAL PK?
2. Does a `summaries` table exist for the summary_id FK?
3. What DB access pattern does `follow_up_store.py` use (psycopg2, asyncpg, etc)?
4. What's the backend container restart command?
