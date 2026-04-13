# Editorial Research Chat Persistence Brief

Date: April 7, 2026
Scope: Persist deep-research follow-up chat turns in PostgreSQL and hydrate them back into the editorial research thread.

## Goal

Deep Research runs are already persisted in PostgreSQL.

Grounded follow-up chat answers are not.

The objective is to persist follow-up chat exchanges so the research conversation survives:

- page refresh
- browser restart
- different devices/browsers
- future classic/editorial UI convergence

This should become backend truth, not browser-local state.

## Current State

### What is already persisted

Deep Research runs are stored in `follow_up_research_runs`.

Relevant files:

- [backend/ytv2_api/follow_up_store.py](/Users/markdarby16/16projects/ytv2/backend/ytv2_api/follow_up_store.py)
- [backend/research_api/migrations/001_add_follow_up_research.sql](/Users/markdarby16/16projects/ytv2/backend/research_api/migrations/001_add_follow_up_research.sql)

The current thread endpoint returns persisted research runs only:

- [backend/ytv2_api/main.py](/Users/markdarby16/16projects/ytv2/backend/ytv2_api/main.py)
- `GET /api/research/follow-up/thread`

### What is not persisted

The chat endpoint is stateless today:

- [backend/ytv2_api/main.py](/Users/markdarby16/16projects/ytv2/backend/ytv2_api/main.py)
- `POST /api/research/follow-up/chat`

It:

- resolves the active deep-research run
- loads thread context
- calls `answer_follow_up_chat`
- returns an answer

It does **not** write the user question + assistant answer anywhere.

## Recommendation

Persist chat turns in a **dedicated PostgreSQL table**, not in browser storage and not by shoving them into `research_meta` JSON on the research run row.

Recommended approach:

- keep `follow_up_research_runs` as the canonical table for research runs
- add a second table for grounded chat exchanges linked to a persisted research run

This keeps the data model clean:

- research run = one persisted deep-research report
- chat turn = one follow-up question/answer exchange over that report

## Why A Separate Table

Do **not** store chat turns inside `follow_up_research_runs.research_meta`.

Reasons:

- chat is append-only and potentially unbounded
- per-turn timestamps matter
- per-turn sources and LLM metadata matter
- querying a JSON blob for thread hydration is weaker than a relational table
- future thread UIs will want ordered retrieval and pagination

## Proposed Schema

Add a new table, for example:

`follow_up_chat_turns`

Recommended columns:

- `id BIGSERIAL PRIMARY KEY`
- `follow_up_run_id BIGINT NOT NULL REFERENCES follow_up_research_runs(id) ON DELETE CASCADE`
- `video_id TEXT NOT NULL`
- `summary_id BIGINT NULL REFERENCES summaries(id) ON DELETE CASCADE`
- `question TEXT NOT NULL`
- `answer TEXT NOT NULL`
- `sources JSONB NOT NULL DEFAULT '[]'::jsonb`
- `chat_meta JSONB NOT NULL DEFAULT '{}'::jsonb`
- `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`

Recommended indexes:

- index on `follow_up_run_id`
- index on `video_id`
- index on `created_at DESC`

Optional:

- `parent_chat_turn_id` only if future UI wants explicit branching

Do not add branching now unless there is a real requirement.

## Recommended Metadata In `chat_meta`

Useful metadata to persist:

- `llm_provider`
- `llm_model`
- `mode` such as `report-chat`
- `source_count`
- `thread_turn_count_at_answer_time`

Do not duplicate large prompt/context payloads unless truly needed for audit/debug.

## Backend Changes

### 1. Migration

Add a new migration after the current follow-up research migration.

Likely file:

- `/Users/markdarby16/16projects/ytv2/backend/research_api/migrations/002_add_follow_up_chat_turns.sql`

If you also use the Python migration helper pattern, add the companion script too.

### 2. Store layer

Extend:

- [follow_up_store.py](/Users/markdarby16/16projects/ytv2/backend/ytv2_api/follow_up_store.py)

Add methods such as:

- `store_follow_up_chat_turn(...)`
- `get_follow_up_chat_turns(follow_up_run_id, *, video_id=None)`

Recommended store contract:

- write one row per user question / assistant answer pair
- return persisted id + created timestamp if helpful

### 3. Models

Extend:

- [models.py](/Users/markdarby16/16projects/ytv2/backend/ytv2_api/models.py)

Add response models for persisted chat turns, for example:

- `FollowUpPersistedChatTurn`

Extend `FollowUpChatRequest` with:

- `persist: bool = True` — controls whether the turn is written to the database

Extend `FollowUpChatResponse` with:

- `persisted: bool` — whether the turn was actually persisted (false if DB write failed or `persist=False`)

Then extend the thread response with either:

- a dedicated `chat_turns` field

or

- a unified ordered `events` array with `kind = research|chat`

Recommendation for first pass:

- add `chat_turns`

Reason:

- lower risk for existing consumers of `turns`
- preserves backward compatibility

### 4. Chat endpoint persistence

Update:

- [main.py](/Users/markdarby16/16projects/ytv2/backend/ytv2_api/main.py)
- `answer_follow_up_chat_endpoint`

After the LLM answer is produced successfully:

- persist the exchange via `store_follow_up_chat_turn(...)`

Persist:

- active `follow_up_run_id`
- resolved `video_id`
- resolved `summary_id` if available
- user `question`
- assistant `answer`
- serialized `sources`
- lightweight `chat_meta`

Persistence should happen **after** a successful answer is available.

If persistence fails:

- log it
- still return the answer to the user (don't throw away an expensive LLM response)
- include a `persisted: false` flag in the response so the frontend can fall back to in-memory/localStorage
- the next thread load simply won't show that turn

Recommendation:

- persistence should be best-effort, not request-blocking
- return the answer regardless; the `persisted` flag lets the frontend decide how to handle it

### 5. Thread endpoint hydration

Update:

- `get_follow_up_thread_endpoint`

So it also loads persisted chat turns for the active run.

Recommended first-pass response shape:

- existing `turns` for persisted research runs
- new `chat_turns` array for persisted follow-up chat exchanges

The frontend can then render:

- research runs
- followed by chat turns

If later you want a single merged timeline, you can add an `events` response in a second pass.

## Frontend Changes

### Editorial

Update:

- [dashboard16/static/editorial_dashboard.js](/Users/markdarby16/16projects/ytv2/dashboard16/static/editorial_dashboard.js)

Changes:

- stop treating in-memory chat turns as the source of truth
- load persisted `chat_turns` from thread response
- append optimistic pending UI locally while waiting
- replace optimistic turn with persisted response once the request resolves

Do not rely on localStorage for editorial once backend persistence exists.

### Classic

Classic currently uses localStorage for chat turns.

Recommendation:

- leave localStorage in place only as a temporary fallback if needed
- but switch classic thread hydration to prefer backend `chat_turns`

This avoids two dashboards drifting in behavior.

## Rendering Recommendation

First-pass thread rendering should be:

1. persisted research runs from `turns`
2. persisted chat exchanges from `chat_turns`

That is enough to make history survive.

Do not over-engineer event merging in the same change unless there is a UX need for perfect chronological interleaving.

If the backend stores `created_at` for chat turns and research runs, you can do merged ordering later.

## API Compatibility Strategy

Safest response evolution:

- keep existing `turns` untouched
- add optional `chat_turns`

This minimizes the chance of breaking classic or tests that expect the current thread contract.

## Tests To Add

### Backend store tests

Extend:

- `/Users/markdarby16/16projects/ytv2/backend/ytv2_api/tests/test_follow_up_store.py`

Add coverage for:

- storing a chat turn
- loading chat turns by run id
- cascade behavior when a research run is deleted

### Backend API tests

Extend:

- `/Users/markdarby16/16projects/ytv2/backend/ytv2_api/tests/test_follow_up_api.py`

Add coverage for:

- `answer_follow_up_chat_endpoint` persists the exchange
- `get_follow_up_thread_endpoint` returns `chat_turns`
- auth + missing run behavior remains correct

## Chat Persistence Modes

Not every chat exchange needs to be permanent. The system should support three modes:

### Mode: `persisted` (default)

Chat turns are written to `follow_up_chat_turns` and survive across sessions, browsers, and devices.

Use when: the user has an active research session and wants a research notebook they can return to.

### Mode: `temporary`

Chat turns exist only in browser memory for the current session (same as current behavior). No database write.

Use when: quick exploratory questions the user doesn't need to keep.

Implementation:

- add an optional `persist: bool = True` field to `FollowUpChatRequest`
- the frontend can pass `persist: false` to skip the database write
- the backend returns the answer without writing a row
- the `persisted` response flag is `false`

### Mode: `deleted`

Previously persisted turns can be soft-deleted by the user.

## Chat Turn Deletion

Users should be able to delete individual chat turns or clear all chat history for a research run.

### Backend endpoints

**Delete a single turn:**

- `DELETE /api/research/follow-up/chat-turns/{turn_id}`
- Validates the turn belongs to the requesting user's context
- Soft-deletes (sets `deleted_at`) or hard-deletes depending on preference
- Recommendation: hard-delete for simplicity; there is no audit requirement for chat turns

**Clear all chat for a run:**

- `DELETE /api/research/follow-up/chat-turns?follow_up_run_id={id}`
- Deletes all chat turns for a given research run
- Research run itself is NOT deleted — only the chat follow-ups

### Frontend

- Each rendered chat turn gets a small "..." menu or swipe action with "Delete"
- "Clear conversation" option in the composer area or reader admin menu
- Confirmation prompt before bulk delete
- After deletion, the turn is removed from the DOM and the thread is re-hydrated

### Store method

Add to `follow_up_store.py`:

- `delete_follow_up_chat_turn(turn_id, *, video_id=None)` — delete single turn
- `delete_follow_up_chat_turns_by_run(follow_up_run_id)` — clear all for a run

## Rollout Plan

### Phase 1 — Backend persistence

- add table migration (`002_add_follow_up_chat_turns.sql`)
- add store methods (`store_follow_up_chat_turn`, `get_follow_up_chat_turns`)
- add `persist` field to `FollowUpChatRequest`, `persisted` to `FollowUpChatResponse`
- persist chat answers in `answer_follow_up_chat_endpoint`
- extend thread endpoint to return `chat_turns`

### Phase 2 — Frontend hydration

- update editorial `_sendResearchChatWithToken` to use `chat_turns` from thread response
- remove dependence on transient in-memory chat state for persistence
- pass `persist: false` for temporary mode when user chooses "temporary chat"

### Phase 3 — Deletion

- add `DELETE /api/research/follow-up/chat-turns/{turn_id}`
- add `DELETE /api/research/follow-up/chat-turns?follow_up_run_id={id}` (clear all)
- add proxy routes in `server.py`
- add delete UI to editorial reader (per-turn "..." menu, "Clear conversation" action)

### Phase 4 — Optional

- update classic to prefer backend over localStorage
- merge research turns + chat turns into one ordered timeline
- temporary chat mode toggle in UI

## Acceptance Standard

This work is successful if:

- asking a follow-up question persists the exchange in PostgreSQL
- refreshing the page shows the same research chat history
- the same history appears across devices/browsers for authorized users
- individual chat turns and entire chat histories can be deleted
- temporary mode works without any database writes
- thread hydration works without localStorage
- deep-research runs and follow-up chat remain clearly separated in the data model

This work is not successful if chat persistence is still browser-local or buried inside `research_meta` blobs.
