# Editorial Reader Advanced Modes Brief

This brief covers the next evolution of the editorial reader: restoring the most valuable capabilities from the classic reader without bringing back the old dense, tool-like visual language.

Applies to:

- `/Users/markdarby16/16projects/ytv2/dashboard16/static/editorial_dashboard.js`
- `/Users/markdarby16/16projects/ytv2/dashboard16/static/editorial_dashboard.css`
- `/Users/markdarby16/16projects/ytv2/dashboard16/dashboard_editorial_template.html`

## Goal

Keep the editorial reader aesthetic, but reintroduce the best high-value reader capabilities from the classic experience:

- alternate summary versions when available
- transcript/research/discussion-style content modes when available
- audio actions
- clean access to the full report page

Do not turn the reader back into a mini dashboard.

## Core Principle

Separate:

- capability
- presentation

The old reader had useful capabilities, but too much dense utility chrome. The new reader should preserve the capabilities while presenting them with calmer hierarchy and more selective UI.

## What To Bring Back

Priority order:

1. Summary version switching
2. Content-mode tabs that only appear when real content exists
3. Audio/version actions grouped cleanly near the top

## 1. Content Modes

Recommended modes:

- `Summary`
- `Transcript`
- `Research`
- `Discussion`

Rules:

- only show a mode if the current item actually has content for it
- if only `Summary` exists, do not show an empty tab bar
- do not show placeholder tabs

Presentation:

- use a restrained segmented control or quiet tab row
- keep the row visually lighter than the old classic reader
- avoid equal visual weight for too many actions and tabs

Placement:

- below the title/actions block
- above the main content body

## 2. Summary Version Switching

This is one of the most important classic-reader capabilities to preserve.

Recommended presentation:

- a compact secondary control such as:
  - `Version: Standard ▾`
  - or `Summary style ▾`

Avoid:

- making version switching a primary top-level tab if it is just a variant of the same summary mode
- exposing too many version names at once if they are confusing or internal-sounding

Behavior:

- default to the best general-purpose summary version
- when the user switches versions, preserve the current reader item and mode
- if possible, keep the change local to the current reader session

## 3. Actions

Keep actions near the top, but grouped clearly:

Primary:

- `Open full report`

Secondary:

- `Watch source`
- `Listen`
- maybe `Copy link` later if useful

Version switching should sit near these controls, but visually secondary to the primary action.

## 4. Reader Hierarchy

Target structure:

1. metadata row
2. title
3. top action row
4. mode switcher row
5. media block if present
6. active content view

This should feel like one coherent reading surface, not stacked tools.

## 5. Styling Guidance

The advanced-mode UI should feel:

- editorial
- restrained
- selective
- content-first

Avoid:

- dense icon clusters
- heavy outlines around every control
- too many control rows with equal emphasis
- bringing back the old “reader command center” feel

Desired visual behavior:

- tabs/mode switches are present when useful, absent when not
- secondary controls step back visually
- active mode is clear but not bright or flashy

## 6. Data / Capability Mapping

When integrating classic-reader capabilities, reuse data sources and capabilities where possible, but do not port the old DOM structure.

Implementation guidance:

- inspect the current report payload and/or full report page data to identify:
  - available summary variants
  - transcript content
  - research/discussion content
  - audio presence
- normalize these into a clean reader state object in the editorial JS
- render only what the current item actually supports

## 7. Suggested Rollout

Do this in phases:

### Phase A

- Add content-mode switcher
- Add version dropdown
- Wire `Summary` plus one or two additional available modes

### Phase B

- Improve action grouping
- Refine tab styling and transitions

### Phase C

- Optional extras such as related items, copy/share, or focus mode

## Acceptance Standard

This pass is successful if:

- the reader gains back high-value classic capabilities
- the UI remains visibly editorial and calm
- empty or unsupported modes do not appear
- version switching and content-mode switching feel useful, not busy

This pass is not a restoration of the old reader. It is a selective rebuild of its best capabilities inside the new editorial system.
