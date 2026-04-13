# Editorial Ponderings Corrective Brief

## Purpose

The new `Ponderings` redesign is directionally right, but there are a few UX and state-management regressions that should be corrected before further polish work.

This brief is focused on fixing those regressions, not redesigning the feature again.

## Summary

Keep:

- `Ponderings` tab label
- inline `Dig Deeper` section
- inline suggested-question cards
- inline custom research launch from the composer

Fix:

- auth prompt appears too early
- typed custom research question is lost on auth prompt / failure
- suggested-question state is not actually preserved across tab switches
- custom research is incorrectly marked as `suggested`

## Required Corrections

### 1. Do not prompt for admin token when Ponderings opens

Current issue:

- Opening `Ponderings` immediately calls suggestions loading
- Suggestions loading currently uses `requireAdminToken(...)`
- That means the token modal appears before the user has chosen an action

Why this is wrong:

- It recreates the same “popup friction” the redesign was meant to remove
- It makes the tab feel gated instead of exploratory

Required behavior:

- Opening `Ponderings` should not force auth
- The tab should render cleanly without interruption
- Auth should only be required when the user explicitly does something privileged:
  - click a suggested deep-research question
  - click `Research this`
  - possibly chat, if chat still requires auth in current architecture

Recommended implementation:

- Use `getAdminToken()` in the suggestions loader instead of `requireAdminToken()`
- If token exists, fetch suggestions normally
- If token does not exist, show a soft inline state instead of a modal prompt

Suggested inline copy:

- `Sign in to load suggested research prompts.`

Optional CTA:

- small inline `Sign in` button in the Dig Deeper area

This preserves the new inline interaction model.

### 2. Do not clear typed custom research input before auth succeeds

Current issue:

- Composer text is cleared immediately when `Research this` is clicked
- The actual request is deferred until after `requireAdminToken(...)`
- If the user cancels auth or the request fails, the typed question is lost

Why this is wrong:

- It destroys user input before the action actually succeeds
- It makes the feature feel brittle and unsafe

Required behavior:

- Keep the composer text intact until:
  - auth succeeds
  - request is accepted successfully

Recommended implementation:

- Move composer clearing into the success path of inline custom research
- Do not clear on click
- Do not clear on token prompt open
- Do not clear on request failure

### 3. Preserve Dig Deeper card state across tab switches

Current issue:

- Suggested cards are re-rendered from raw suggestions when the tab reopens
- `running` / `done` states are applied directly to DOM nodes only
- That means state disappears after tab switch or re-render

Why this is wrong:

- The implementation summary says state is preserved, but it currently is not
- Users lose context about which question they already ran

Required behavior:

- Suggestion card state must live in JS state, not only in the DOM

Recommended state model:

- `_ponderingsSuggestions`
- `_ponderingsSuggestionsVideoId`
- `_ponderingsSuggestionStateByQuestion`

Where `_ponderingsSuggestionStateByQuestion[question]` is one of:

- `available`
- `running`
- `done`
- `failed`

Required rendering behavior:

- `_renderDigDeeperCards()` should render from both:
  - suggestion list
  - per-question state

Result:

- reopening the tab shows the same card states
- collapse/expand does not reset state
- re-render after thread refresh does not reset state

### 4. Mark custom composer research as `custom`, not `suggested`

Current issue:

- Composer-driven custom research is sent with `question_provenance: ['suggested']`

Why this is wrong:

- It pollutes provenance tracking
- It makes analytics and later product decisions less trustworthy

Required behavior:

- Suggested card click => `question_provenance: ['suggested']`
- Typed custom composer research => `question_provenance: ['custom']`

Recommended implementation:

- Let `_executeInlineResearch()` accept a small option or provenance flag
- Do not infer provenance from whether a card element exists unless that is guaranteed

## Optional Improvements

These are not blockers, but they would improve the UX.

### Inline signed-out state for Dig Deeper

If no token exists:

- keep `Dig Deeper` visible
- show a calm signed-out helper row
- do not turn the whole section into an error state

Example:

- `Sign in to load suggested prompts and run deeper research.`

### Smarter collapse copy

Current collapsed text:

- `3 research questions available`

Better:

- `3 prompts available`
- or `Dig Deeper: 3 prompts`

This feels more aligned with the `Ponderings` tone.

### Preserve completed card affordance

When a suggested question has already been run:

- keep the checkmark
- optionally allow a softer secondary click behavior such as `Run again`

But do not silently reset it to available just because the tab re-rendered.

## Implementation Notes

Files:

- `/Volumes/markdarby16/16projects/ytv2/dashboard16/static/editorial_dashboard.js`
- `/Volumes/markdarby16/16projects/ytv2/dashboard16/static/editorial_dashboard.css`

Prefer a focused correction over more redesign churn.

Do not bring back the modal flow.

Do not add more buttons or more top-level sections.

## Verification

1. Open `Ponderings` with no saved admin token
2. Confirm the tab opens without forcing the token modal
3. Confirm Dig Deeper shows an inline signed-out state or equivalent non-blocking state
4. Type a custom research question and click `Research this`
5. Cancel auth prompt
6. Confirm the typed question is still in the composer
7. Complete auth and run custom research
8. Confirm the composer clears only after successful request submission
9. Click a suggested prompt and confirm it enters `running` then `done`
10. Switch away from `Ponderings` and back
11. Confirm the card state remains accurate
12. Confirm suggested prompt runs are marked `suggested`
13. Confirm typed composer runs are marked `custom`
14. Hard refresh browser and retest JS behavior

