# Editorial Ponderings Polling Corrective Brief

## Status

This is a **revise before implementation** brief.

The proposed plan is close, but it should **not** be implemented exactly as written.

There are three required changes before proceeding:

1. Fix per-story Dig Deeper state scoping first
2. Use guarded `setTimeout` polling, not raw `setInterval`
3. Improve button labels themselves, not just hover tooltips

## Why The Current Plan Is Not Ready

### 1. Dig Deeper state still leaks across stories

There is already an open correctness issue:

- suggestion state is keyed only by question text
- it is not scoped per `videoId`

If polling and auto-refresh are added on top of that, the wrong story can inherit `running` / `done` prompt state.

This must be fixed before adding more status logic.

Required change:

- key suggestion state by `videoId + question`
- or nest state under `videoId`

Recommended structure:

- `_ponderingsSuggestionStateByVideo = { [videoId]: { [question]: state } }`

## Revised Plan

## Step 0: Fix per-video suggestion state

Before any polling work:

- replace the global per-question state map
- scope Dig Deeper state by `videoId`

Methods to update:

- `_setSuggestionState(...)`
- `_getSuggestionState(...)`
- any render path that reads suggestion state

Expected behavior:

- same question text in two different stories does not collide

## Step 1: Polling for research completion

### Do not use `setInterval`

Use a guarded `setTimeout` loop instead.

Why:

- prevents overlapping requests if one poll is slow
- makes cleanup easier
- reduces race-condition risk

Recommended state:

- `this._researchPollTimer = null`
- `this._researchPollInFlight = false`
- `this._researchPollingVideoId = null`

Recommended methods:

- `_startResearchPolling(videoId)`
- `_pollResearchThread()`
- `_stopResearchPolling()`

Behavior:

- start polling after research run starts successfully
- do an immediate first poll, then continue every ~8-10 seconds
- ignore stale responses if the active reader or active video changed
- stop polling when no thread turn has `status === 'running'`
- stop polling when reader closes or Ponderings hides

### Auto-refresh when complete

Required result:

- when research finishes, the thread should repaint automatically
- user should not need to leave and return to see results

Safe completion UI:

- refresh rendered thread
- stop polling
- show toast such as `Deep research complete`

## Step 2: Improve running-state feedback

Pushback:

Do not pretend to have detailed backend phase data unless the API actually exposes it.

If the backend only gives `running`, then the UI should stay honest.

Allowed dynamic feedback:

- spinner
- elapsed time since start
- `Last checked 12:41 PM`
- `Research running`

Do **not** fake steps like:

- searching web
- synthesizing answer
- validating sources

unless backend metadata is added for those phases.

Recommended running turn UI:

- small spinner
- `Research running`
- muted meta line with elapsed time and last-checked time

## Step 3: Fix Ask / Research action clarity

Tooltips alone are not sufficient.

Reason:

- desktop only helps on hover
- mobile/touch gets no benefit
- labels remain ambiguous even with hidden explanations

Required change:

- improve visible labels

Recommended options:

Option A:

- `Ask About Report`
- `Run Deep Research`

Option B:

- keep `Ask`
- keep `Research`
- add one-line helper text under composer:
  - `Ask uses the current report. Deep Research runs a broader web investigation.`

Recommendation:

- prefer Option A
- optionally keep `title` attributes too

## Step 4: Fix Clear Chat visual update

The current diagnosis is correct:

- DOM removal alone misses turns created dynamically outside persisted wrappers

Correct fix:

- clear `chat_turns` in state
- re-render via `_renderResearchTurns(...)`
- update any dependent UI state after re-render

Required follow-up:

- also call `_updateDigDeeperCollapse()`

That ensures the tab responds immediately without requiring navigation away and back.

## Recommended Implementation Order

1. Per-video Dig Deeper state scoping
2. Clear Chat re-render fix
3. Action-label improvement
4. Polling + running-state refresh

This order keeps correctness ahead of polish.

## Verification

1. Open story A, run a suggested prompt, confirm it becomes `running` / `done`
2. Open story B with similar prompt wording, confirm no state leaks from story A
3. Start deep research and stay in Ponderings
4. Confirm thread auto-refreshes when research completes
5. Confirm no duplicate polling requests overlap
6. Switch away from Ponderings during polling, confirm polling stops
7. Return to Ponderings while run is still active, confirm polling resumes
8. Confirm running UI shows only truthful status metadata
9. Confirm button labels are understandable without hover
10. Clear chat and confirm turns disappear immediately without tab navigation
11. Hard refresh browser after JS changes and retest

## Bottom Line

Proceed with this feature only after revising the plan to:

- fix per-video state leakage first
- use safe polling architecture
- improve visible action labels, not just tooltips
- re-render from state for Clear Chat

