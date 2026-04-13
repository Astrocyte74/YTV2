# Editorial Markdown Normalization Corrective Brief

## Purpose

The switch to local vendored `markdown-it` is the right direction.

The remaining problem is not the parser choice. The problem is that some LLM outputs are still malformed before they reach the parser, and the current preprocessor is too narrow.

This brief is to stop speculative patching and move to a more reliable debug-and-normalize approach.

## Current Status

Good:

- `markdown-it` is now used locally
- core markdown parsing is no longer hand-rolled
- valid tables render correctly

Still broken:

- some malformed research “tables” still render as raw pipe-delimited text in Ponderings
- the MOVA example is the current known reproduction

## Main Diagnosis

The likely issue is that `_fixMalformedTables()` currently assumes one very specific packed-row pattern:

- `| |`

That is too narrow for real LLM output.

The actual runtime string may instead contain:

- multiple spaces
- tabs
- non-breaking spaces
- mixed inline row boundaries
- partial rows
- unusual separator/header structure

So the next step should **not** be “add one more guessy regex.”

The next step should be:

1. inspect the actual runtime string
2. normalize the full table block more systematically
3. then feed that normalized block into `markdown-it`

## Required Direction

## 1. Instrument the real input before changing logic again

Do this first.

Add temporary debug logging around the markdown render path for the specific failing answer.

Useful checkpoints:

- raw `answer` text
- preprocessed text returned by `_fixMalformedTables()`
- final HTML returned by `markdown-it`

At minimum, log:

- the first 500-1000 chars of the raw block
- the first 500-1000 chars after preprocessing
- character codes around the first suspicious `| ... | ... |` segment if needed

Important:

- inspect the actual string in the running UI path
- do not rely only on copied terminal text or paraphrased examples

## 2. Stop using a single literal split pattern

Current narrow approach:

- split only on literal `| |`

This is not robust enough.

The code should not assume exactly one ASCII space between row boundaries.

Minimum improvement:

- detect arbitrary whitespace boundaries, not just single-space boundaries

But even that should be done carefully so legitimate empty cells are not broken.

## 3. Normalize whole table-like blocks, not isolated tokens

Recommended strategy:

- detect a “table-like block” first
- normalize that block as a unit
- then send it to `markdown-it`

Suggested heuristic for a table-like block:

- line or paragraph contains many pipe characters
- includes a separator-like row
- includes repeated cell boundaries

Normalization goals:

- one logical row per line
- separator row on its own line
- synthetic header row inserted when needed
- preserve cell text content

## 4. Prefer a block parser over increasingly fragile regex patches

If the malformed-table problem keeps growing, the right solution is not more regex.

Recommended fallback approach:

- isolate suspicious pipe-heavy paragraphs
- parse them with a small custom normalizer
- reconstruct valid markdown table text

In plain terms:

- identify likely rows
- split rows safely
- rebuild a proper table block

That is more reliable than stacking more `replace(...)` calls.

## Recommended Implementation Strategy

## Phase A: Temporary Debugging

Add temporary logging to:

- `renderMarkdown(text)`
- `_fixMalformedTables(text)`

Goal:

- capture the real MOVA failing block exactly as the browser sees it

After diagnosis:

- remove or disable the debug logging

## Phase B: Broaden row-boundary normalization

Replace the current literal packed-row handling with a more tolerant boundary detector.

Examples of cases to support:

- `| row | | row |`
- `| row |  | row |`
- `| row |\t| row |`
- `| row | <nonbreaking-space>| row |`

But do this at the table-block level, not with a blind global replace across all markdown.

## Phase C: Rebuild malformed headerless tables

If a separator row exists without a valid header row above it:

- insert a synthetic empty header row

That part of the current logic is fine conceptually.

The problem is not that idea. The problem is that the rows are not always being split cleanly before that step.

## Concrete Pushback

Do **not** keep repeating this loop:

- guess one malformed pattern
- add one regex
- restart dashboard
- hope it catches the next example

That is exactly how the old hand-rolled renderer became fragile.

Now that `markdown-it` is in place, the normalization layer should be:

- small
- targeted
- debug-driven
- limited to malformed table repair only

## Likely Hotspot

The current likely weak point is the packed-row split logic in:

- `/Volumes/markdarby16/16projects/ytv2/dashboard16/static/editorial_dashboard.js`

It currently assumes a very literal row-boundary shape.

That logic should be made more tolerant after inspecting the real string.

## Verification

1. Reproduce the MOVA broken table in Ponderings
2. Capture raw text before preprocessing
3. Capture preprocessed text after normalization
4. Confirm the normalized text is valid markdown table syntax
5. Confirm `markdown-it` renders it into `<table ...>` HTML
6. Hard refresh browser and verify the actual UI shows a table, not raw pipes
7. Re-test a known good normal table to ensure no regression
8. Re-test non-table markdown to ensure it is unaffected

## Bottom Line

Greenlight on the `markdown-it` migration.

No greenlight on further “guessy” regex patches without first inspecting the exact runtime string.

The next correct move is:

- log the real malformed block
- normalize whole table-like blocks more systematically
- keep the repair layer small and specific

