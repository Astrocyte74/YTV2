# Editorial Related Mode UX Corrective Brief

Date: April 5, 2026
Target route: `/editorial`

This brief captures the current UX awkwardness in Phase A of editorial related mode and recommends the next interaction model before additional implementation work continues.

## Context

Phase A introduced:

- selectable support/feed cards
- a contextual `Related` toggle in the topbar
- a related-mode banner with `Back to Recent`
- static re-ranking with the selected story promoted to hero

The feature works mechanically, but the interaction model is not yet intuitive.

## Current UX Problem

Right now the page has two competing concepts:

- selected story for related mode
- open story in the reader

Those are being managed separately, and that separation is what makes the experience feel awkward.

Example of the current confusion:

1. A story is open in the reader.
2. The user clicks another card.
3. That card only highlights or unhighlights.
4. The reader does not switch.
5. Related mode does not automatically re-anchor to the newly clicked story.

This creates an unnatural workflow where the user has to:

1. exit related mode
2. reselect a card
3. re-enter related mode
4. click again to open the reader

That is too many steps for what should feel like one continuous browsing action.

## Root Cause In Current Implementation

### 1. Card clicks now stop at selection

Support/feed card clicks are intercepted here:

- [editorial_dashboard.js](/Volumes/markdarby16/16projects/ytv2/dashboard16/static/editorial_dashboard.js#L1168)

That handler calls `_selectItem(cardId)` and returns early.

But the old general card-open behavior still exists later:

- [editorial_dashboard.js](/Volumes/markdarby16/16projects/ytv2/dashboard16/static/editorial_dashboard.js#L1606)

So the card surface now has two conflicting jobs:

- select for related mode
- open the reader

The earlier selection handler wins, which makes clicks feel broken from the user's perspective.

### 2. Related mode and reader state are split

Related mode is driven by:

- `_selectedItemId` in [editorial_dashboard.js](/Volumes/markdarby16/16projects/ytv2/dashboard16/static/editorial_dashboard.js#L285)
- related toggle rendering in [editorial_dashboard.js](/Volumes/markdarby16/16projects/ytv2/dashboard16/static/editorial_dashboard.js#L823)

Reader state is tracked separately by:

- `openReader()` and `_activeReaderId` in [editorial_dashboard.js](/Volumes/markdarby16/16projects/ytv2/dashboard16/static/editorial_dashboard.js#L1647)
- `_currentReaderData` in [editorial_dashboard.js](/Volumes/markdarby16/16projects/ytv2/dashboard16/static/editorial_dashboard.js#L1658)

This split is the wrong mental model for the feature.

From the user’s perspective, the story they are reading should already be the story that `Related` uses.

### 3. Exiting related mode clears too much context

The current topbar toggle and banner exit paths clear `_selectedItemId`:

- [editorial_dashboard.js](/Volumes/markdarby16/16projects/ytv2/dashboard16/static/editorial_dashboard.js#L1146)
- [editorial_dashboard.js](/Volumes/markdarby16/16projects/ytv2/dashboard16/static/editorial_dashboard.js#L1159)

That makes `Back to Recent` feel destructive instead of reversible.

The user expects:

- layout resets to recent order
- current story context remains intact

Not:

- layout resets
- current anchor vanishes
- selection is lost

### 4. Selection state may outlive the current result set

`loadContent()` resets related mode state, but does not clear `_selectedItemId`:

- [editorial_dashboard.js](/Volumes/markdarby16/16projects/ytv2/dashboard16/static/editorial_dashboard.js#L334)

That can leave the topbar offering `Related` for a story that may no longer be visible after search, filter, or sort changes.

## Recommended Mental Model

Stop treating `selected story` and `reader story` as separate primary states.

Use one concept:

- `active story`

The active story should be the story the user most recently opened or intentionally focused.

`Related` should always anchor to that active story.

## Recommended Interaction Model

### Card click

Clicking a support/feed card should:

1. open the reader for that story
2. make that story the active story

Do not make a standard card click only toggle a highlight state.

### Related toggle on

When `Related` is toggled on:

1. use the current active story as the anchor
2. promote that story to the hero slot
3. re-rank all other loaded items beneath it

If no active story exists, then and only then should the user need to select one first.

### Click another card while related mode is on

When related mode is active and the user clicks another card:

1. open that story in the reader
2. switch the active anchor to that story
3. re-rank related mode around the new anchor

This should feel like fluid exploration, not mode management.

### Back to Recent

`Back to Recent` should:

1. restore recent-order layout
2. keep the current reader story open
3. keep current story context if possible

It should not wipe out the user’s story context unless there is a strong reason to do so.

## Behavioral Recommendation

Recommended behavior table:

- Click card in normal mode: open reader and set active story
- Toggle `Related`: re-rank around active story
- Click card in related mode: open reader and re-anchor related mode to that story
- Click `Back to Recent`: restore chronology, keep reader context

## Implementation Direction

The next pass should refactor related mode around active reader state instead of separate selection state.

Recommended direction:

- make the reader item the canonical anchor source
- keep any visual selection styling secondary, not primary
- only show explicit selection UI if there is a distinct multi-step mode that truly needs it

If a highlight remains, it should indicate:

- this is the current active story

It should not indicate:

- this card is selected for some other hidden workflow

## What Not To Do

Avoid these patterns in the next iteration:

- requiring separate select and open gestures for ordinary browsing
- clearing story context when exiting related mode
- keeping `Related` dependent on a hidden state the reader does not reflect
- making users guess whether clicking a card will select, open, deselect, or re-anchor

## Acceptance Standard For The Next Pass

This UX correction is successful if:

- clicking a card always produces an obvious primary result
- the reader and related anchor feel like the same story context
- users can move from one story to another without leaving related mode
- returning to recent order feels reversible and safe
- the page no longer teaches a multi-step ritual just to inspect related stories

## Files To Review

Primary implementation file:

- [editorial_dashboard.js](/Volumes/markdarby16/16projects/ytv2/dashboard16/static/editorial_dashboard.js)

Related styling:

- [editorial_dashboard.css](/Volumes/markdarby16/16projects/ytv2/dashboard16/static/editorial_dashboard.css)

Companion planning brief:

- [EDITORIAL_RELATED_MODE_ANIMATION_BRIEF.md](/Volumes/markdarby16/16projects/ytv2/dashboard16/docs/EDITORIAL_RELATED_MODE_ANIMATION_BRIEF.md)
