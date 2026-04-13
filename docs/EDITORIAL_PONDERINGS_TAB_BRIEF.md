# Editorial Ponderings Tab Brief

## Goal

Replace the current `Research` tab + modal flow with a more native editorial experience:

- Rename the tab to `Ponderings`
- Keep quick grounded chat in the tab
- Surface suggested deep-research questions inline instead of in a popup
- Preserve visibility of research options even after several chat turns

This should feel like a built-in thinking workspace for the current story, not a separate tool.

## Product Recommendation

The overall direction is good, with two important adjustments:

1. Do **not** auto-run full deep research when a summary is created.
   Full research is still too expensive and too slow to run by default for every item.

2. Separate the work into:
   - **Phase 1:** UI redesign + inline suggestions + no modal
   - **Phase 2:** background pre-generation/persistence of suggested questions

The existing plan treats this as frontend-only, but that is only true if suggestions are still fetched lazily when the tab opens. If the goal is to have suggestions already available when the summary is created, that requires backend orchestration and persistence.

## Naming

`Ponderings` is workable and more inviting than `Research`.

Recommendation:

- Use `Ponderings` in the UI label only
- Keep internal code names and API routes as `research` / `follow-up`

Do not rename backend concepts, DB structures, or endpoint paths just to match the tab label.

## Recommended UX Model

### Tab Structure

The tab should have two clear sections:

1. `Dig Deeper`
   - Shows suggested research questions as clickable cards/chips
   - Lives at the top of the tab
   - Always remains discoverable

2. `Conversation`
   - Existing grounded chat / follow-up thread area
   - Includes deep-research output turns when a question is run
   - Includes lightweight report Q&A chat turns

This is better than making suggestions and chat compete inside one undifferentiated feed.

### Layout Behavior

Default state:

- `Dig Deeper` expanded
- Conversation area below
- Composer visible at bottom

After the user has a few chat turns:

- Auto-collapse `Dig Deeper` into a slim summary row
- Example: `3 research questions available`
- Allow manual expand/collapse

Important: auto-collapse should happen gently and only after the user has clearly entered chat mode. Do not collapse immediately after one message.

Recommended threshold:

- Collapse after **2 completed user/assistant chat pairs**
- Not after a single question

### Suggested Question Cards

Each suggestion should be a compact editorial card, not a plain button list.

Card states:

- `available`
- `running`
- `completed`
- `failed`

Behavior:

- Clicking a suggestion starts inline deep research immediately
- The clicked suggestion shows a spinner / running state
- When complete, a research result appears in the conversation area
- The suggestion becomes completed and can offer `View result` rather than encouraging accidental re-runs

Do not automatically re-run the same suggestion every time it is clicked once a result already exists.

### Composer Actions

Avoid two equal-weight primary actions fighting each other in the composer.

Current model:

- `Ask`
- `Run Research`

Better model:

- Primary action: `Ask`
- Secondary action: `Research this`

Only show `Research this` when the composer has text.

This makes the intent clearer:

- normal question => chat answer
- deliberate escalation => deeper research run

If you keep both buttons always visible, the UI will keep feeling ambiguous.

### Existing Deep Research Report

If a deep-research report already exists:

- Keep the existing rich report visible in the conversation section as the first major artifact
- Then show follow-up research turns and chat below it

Do not bury or replace the already-generated report just because the tab has been redesigned.

## Pushbacks / Corrections To The Current Plan

### 1. "No server-side changes needed" is only partially true

That is true for the inline modal-removal redesign **if suggestions are still fetched lazily** via:

- `POST /api/research/follow-up/suggestions`

It is **not** true if suggested questions should already exist when the summary is created.

If pre-generation is required, backend work is needed to:

- trigger suggestion generation during or after summary creation
- persist suggestion results
- return them with the report/reader payload or via a cheap cached endpoint

### 2. Do not block summary creation on suggestions

If suggestions are generated automatically, do it asynchronously.

Good:

- summary appears immediately
- suggestions arrive later / are cached in background

Bad:

- summary waits on extra LLM work
- editor perceives the whole pipeline as slower

### 3. Do not promise streaming/diffusing in this redesign

Current editorial chat code explicitly disables the streaming path because the dashboard proxy buffers SSE.

See the comment in [editorial_dashboard.js](/Volumes/markdarby16/16projects/ytv2/dashboard16/static/editorial_dashboard.js#L2452).

So this redesign should assume:

- non-stream chat for now
- inline research execution
- future streaming as a separate infrastructure upgrade

### 4. Do not fully remove manual custom research

Eliminating the modal is good.
Eliminating custom research is not.

The user still needs:

- suggested question clicks
- custom typed research question

Both should exist in the inline Ponderings experience.

## Recommended Implementation Plan

## Phase 1: Ponderings UI Redesign

Files:

- `/Volumes/markdarby16/16projects/ytv2/dashboard16/static/editorial_dashboard.js`
- `/Volumes/markdarby16/16projects/ytv2/dashboard16/static/editorial_dashboard.css`

Changes:

- Rename tab label from `Research` to `Ponderings`
- Replace modal-first flow with inline `Dig Deeper` section
- Keep existing conversation/thread rendering below
- Keep composer pinned at bottom of Ponderings panel
- Add expand/collapse behavior for suggested questions
- Clicking a suggestion runs research inline
- `Run Research` modal path removed from normal UX

Notes:

- Keep legacy helper methods only if needed during transition
- Prefer a clean replacement over layering new UI on top of old modal assumptions

## Phase 2: Suggestion Persistence / Background Generation

Goal:

- Suggested questions should already exist for many items before the user opens Ponderings

Recommended backend behavior:

- Generate suggestions asynchronously after summary creation
- Store suggestions in PostgreSQL keyed to summary/video
- Return cached suggestions to the editorial reader
- Fall back to on-demand suggestion generation if no cached suggestions exist

This should be treated as a separate implementation task from the UI redesign.

## Specific UI Notes For The Agent

### Visual Direction

Keep the tone editorial and calm, not chat-app-like.

Suggestions should look like:

- notebook prompts
- annotated lines of inquiry
- subtle cards with arrow/check/spinner states

Avoid:

- loud blue action cards
- generic chatbot bubbles for everything
- a busy control bar with too many equal buttons

### Section Order

Recommended order inside Ponderings:

1. `Dig Deeper`
2. Existing report if present
3. Research/chat turns
4. Composer

This gives immediate discovery while preserving the current report context.

### Empty / Sparse State

If there are no cached/generated suggestions yet:

- show a soft loading/skeleton state first
- then either render suggestions or a fallback small message

Fallback message:

- `No prompts yet. Ask about this report or start a custom research run.`

Do not revert to the old modal-like empty state language.

## Suggested Data / State Model

Frontend state should distinguish between:

- `suggestions`
- `suggestionsLoading`
- `suggestionsExpanded`
- `suggestionRunStateByQuestion`
- `threadData`
- `chatTurns`

Do not overload `_researchModalState` to power the new inline flow.

If needed, create a new inline state object rather than dragging modal assumptions forward.

## Verification

1. Open an editorial item and open `Ponderings`
2. Confirm suggested questions appear inline without opening a modal
3. Confirm custom `Ask` still works
4. Confirm typed custom research can be run inline
5. Confirm a clicked suggested question shows running state and then completed state
6. Confirm generated research output appears in the conversation area
7. Confirm after multiple chat turns the `Dig Deeper` section collapses to a slim expandable row
8. Confirm switching away and back preserves current tab state appropriately
9. Hard refresh the browser after JS/CSS changes and retest

## Bottom Line

This is a good redesign if it is framed as:

- inline suggestions
- grounded chat
- no modal
- deeper research available without leaving context

It becomes weaker if it turns into:

- another generic chat tab
- auto-running full research on every summary
- a frontend-only implementation that pretends suggestion pre-generation needs no backend support

