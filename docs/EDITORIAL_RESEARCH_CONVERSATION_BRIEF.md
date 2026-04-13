# Editorial Research Conversation Brief

Date: April 6, 2026
Target route: `/editorial`

This brief defines the recommended direction for bringing research into the editorial reader.

The goal is not to bolt on a generic LLM chat tab. The goal is to bring the strongest parts of the classic dashboard’s research workflow into the editorial reader with better information architecture and better visual design.

## Executive Direction

Do **not** start by inventing a brand-new generic `/api/chat` feature.

Start by porting and redesigning the **existing deep-research conversation flow** that already exists in the classic dashboard:

- grounded Q&A about the current report
- deep research launcher
- deep research thread view
- follow-up questions within the same research context

The editorial version should feel like a premium, article-aware research workspace, not a general-purpose chatbot bolted onto the reader.

## Why This Direction Is Better

The classic dashboard already has the right product shape:

- ask questions about the current report
- continue an existing deep research run
- branch into a fresh deep research run when needed

That is much more valuable than a raw “Chat with model” surface.

It is also safer:

- grounded to current report content
- lower hallucination risk
- clearer user expectations

If a broader model chat is added later, it should be a second-phase enhancement, not the starting architecture.

## Existing Capability Already In Classic

The classic dashboard already contains the main research conversation flow in:

- [dashboard_v3.js](/Users/markdarby16/16projects/ytv2/dashboard16/static/dashboard_v3.js#L11781)
- [dashboard_v3.js](/Users/markdarby16/16projects/ytv2/dashboard16/static/dashboard_v3.js#L11966)

That includes:

- fetching a deep research thread
- rendering a thread view
- asking grounded follow-up questions
- launching fresh deep research from the same surface
- opening the research setup modal

This means the editorial feature should be treated primarily as a **frontend redesign and selective port**, not a new product invented from scratch.

## Important Architectural Correction

The proposed plan to add a new `/api/chat` route is not the best first move.

Reason:

- the classic dashboard is already using dedicated research endpoints for thread and grounded follow-up chat
- these are a better fit than a generic chat endpoint

Classic calls include:

- `/api/research/follow-up/thread` at [dashboard_v3.js](/Users/markdarby16/16projects/ytv2/dashboard16/static/dashboard_v3.js#L11791) (GET)
- `/api/research/follow-up/chat` at [dashboard_v3.js](/Users/markdarby16/16projects/ytv2/dashboard16/static/dashboard_v3.js#L11870) (POST)
- `/api/research/follow-up/suggestions` at [dashboard_v3.js](/Users/markdarby16/16projects/ytv2/dashboard16/static/dashboard_v3.js#L12085)
- `/api/research/follow-up/run` at [dashboard_v3.js](/Users/markdarby16/16projects/ytv2/dashboard16/static/dashboard_v3.js#L12165)

## Proxy Gap To Verify

In this editorial server checkout, only the following proxy routes are currently visible:

- `/api/research/follow-up/suggestions` at [server.py](/Users/markdarby16/16projects/ytv2/dashboard16/server.py#L1885)
- `/api/research/follow-up/run` at [server.py](/Users/markdarby16/16projects/ytv2/dashboard16/server.py#L6145)

The classic conversation flow also expects:

- `/api/research/follow-up/thread` (GET)
- `/api/research/follow-up/chat` (POST)

**These endpoints ARE implemented in the backend FastAPI** (`backend/ytv2_api/main.py` lines 948 and 998) but are **NOT proxied** by `server.py`.

### Implementation Notes for Missing Proxies

1. **`/thread` is a GET request.** The existing `_proxy_follow_up_request()` (server.py line 6064) only does `requests.post()`. You need a new GET-proxy method (e.g., `_proxy_follow_up_get_request()`) that does `requests.get()` with the same auth/validation/URL-resolution logic.

2. **`/chat` is a POST request.** You can reuse `_proxy_follow_up_request()` — just add a `do_POST` route for `/api/research/follow-up/chat` that calls it.

3. **Additional endpoint:** The backend also has `/api/research/follow-up/cached` (GET, main.py line 1068). Neither classic nor editorial uses it yet, but it may be useful for loading cached research results. Consider proxying it alongside `/thread`.

**These proxy routes MUST be added to server.py and verified working before any editorial UI work begins.**

### Verification Steps

After adding proxy routes:

```bash
# 1. Restart the container
docker restart ytv2-dashboard

# 2. Test thread endpoint (replace VIDEO_ID and RUN_ID with real values)
curl -s -b "admin_token=YOUR_TOKEN" "http://localhost:10000/api/research/follow-up/thread?video_id=VIDEO_ID&follow_up_run_id=RUN_ID" | head -c 500

# 3. Test chat endpoint
curl -s -b "admin_token=YOUR_TOKEN" -X POST "http://localhost:10000/api/research/follow-up/chat" -H "Content-Type: application/json" -d '{"video_id":"VIDEO_ID","follow_up_run_id":"RUN_ID","question":"What are the main takeaways?"}' | head -c 500
```

## Product Recommendation

The editorial reader should get a `Research` mode, not a generic `Chat` tab.

Inside that mode, the interface can absolutely look conversational. But the mode should be framed around the report and research workflow, not around an abstract assistant identity.

Recommended naming:

- `Summary`
- `Transcript`
- `Research`

Not:

- `Summary`
- `Transcript`
- `Chat`

Reason:

- `Research` is task-oriented and grounded
- `Chat` suggests a broader capability than the system actually has
- keeping the mode name specific will prevent product drift

## Recommended Research Mode UX

### State A: No Deep Research Yet

Show a refined empty state:

- headline such as `Deep Research hasn’t been generated yet`
- short explanation of what it does
- primary CTA: `Start Research`
- optional secondary hint that the reader can answer grounded questions once research exists

This is already conceptually present in classic:

- [dashboard_v3.js](/Users/markdarby16/16projects/ytv2/dashboard16/static/dashboard_v3.js#L4904)

But the editorial version should be visually calmer and more premium.

### State B: Deep Research Exists

Show a research conversation surface:

- existing deep research result as the main report answer
- earlier turns if present
- composer for grounded follow-up questions
- explicit secondary action to run fresh research

This is the strongest part of the classic flow and should be preserved.

### Composer Actions

The composer should support two clearly different actions:

- `Ask about this report`
- `Run fresh research`

Those actions should not be visually equal.

Recommended hierarchy:

- primary: `Ask`
- secondary but prominent: `Run Research`

## Design Guidance

This should feel like an editorial research notebook inside the reader.

Desired characteristics:

- calm
- grounded
- article-aware
- evidence-oriented
- conversational without looking like a chatbot app

Avoid:

- generic chat bubbles with no relationship to the report
- loud “AI assistant” framing
- over-exposing provider/model details in the first pass
- turning the reader into a general LLM playground

## Mercury / Model Choice

Mercury can be a later enhancement, but it should not drive the first implementation.

First implementation priority:

- grounded report conversation
- deep research continuity
- editorial-quality UI

If Mercury is introduced later, it should probably appear as:

- an internal backend model choice
- or an advanced setting

Not as the main front-end concept.

The user should feel:

- “I’m researching this story”

Not:

- “I’m opening a random chatbot inside the reader”

## Context Strategy

The conversation should always be grounded to the current report context first.

Recommended context priority:

1. deep research report content if present
2. current summary variant text
3. source context metadata
4. transcript excerpts only when needed

The important principle is:

- keep the interaction report-centric
- do not make the first version a freeform long-context everything-chat

## Suggested Implementation Phases

### Phase 1: Port Existing Research Workflow

Goal:

- bring classic deep research launcher + modal + thread/chat flow into editorial

Scope:

- `Research` reader mode
- empty state launcher
- suggestions modal
- run deep research
- thread view
- grounded follow-up ask

This is the highest-value and lowest-risk phase.

### Phase 2: Editorial Redesign Pass

Goal:

- make the research mode feel native to the editorial reader

Scope:

- rewrite layout and CSS for calmer hierarchy
- align typography and spacing with the reader
- make thread cards/messages look like editorial note blocks, not generic app chat bubbles

### Phase 3: Optional Expansion

Only after the grounded research experience is solid:

- streaming
- model abstraction
- optional provider/model selector
- broader discussion mode
- Mercury as explicit advanced model choice if still desired

## Recommended File Focus

Primary editorial files:

- [editorial_dashboard.js](/Users/markdarby16/16projects/ytv2/dashboard16/static/editorial_dashboard.js)
- [editorial_dashboard.css](/Users/markdarby16/16projects/ytv2/dashboard16/static/editorial_dashboard.css)

Classic reference source:

- [dashboard_v3.js](/Users/markdarby16/16projects/ytv2/dashboard16/static/dashboard_v3.js)
- [report_v2.js](/Users/markdarby16/16projects/ytv2/dashboard16/static/v2/report_v2.js) (secondary — also has research endpoint calls)

Server verification point:

- [server.py](/Users/markdarby16/16projects/ytv2/dashboard16/server.py)
- [backend main.py](/Users/markdarby16/16projects/ytv2/backend/ytv2_api/main.py) (lines 704, 790, 948, 998, 1068 — all five follow-up endpoints)

Companion reader guidance:

- [EDITORIAL_READER_ADVANCED_MODES_BRIEF.md](/Users/markdarby16/16projects/ytv2/dashboard16/docs/EDITORIAL_READER_ADVANCED_MODES_BRIEF.md)

## What To Tell The Working Agent

Do this:

- port and redesign the classic deep research thread experience into editorial
- keep it grounded to the current article/report
- use `Research` as the mode name
- verify whether thread/chat proxy endpoints need to be added before UI work

Do not do this first:

- invent a new generic `/api/chat` route
- build an ungrounded Mercury chatbot tab
- lead the product with provider/model branding

## Acceptance Standard

This feature direction is successful if:

- editorial gains the best parts of classic deep research
- the research surface feels native to the editorial reader
- users can ask grounded follow-up questions about the current report
- users can launch fresh deep research from the same surface
- the UI feels premium and article-aware rather than chatbot-generic

This feature direction is not successful if it becomes “ChatGPT inside the reader.”
