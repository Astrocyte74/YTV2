# Audio On Demand - Design Plan

## Problem

Audio summaries are currently treated as summary variants. They move through the same mental and technical pipeline as text variants such as `comprehensive`, `bullet-points`, and `key-insights`.

That creates several product problems:

- Audio is only available when someone generated an audio variant ahead of time.
- The user has to notice an `Audio` badge or a `Listen` button on the card.
- `Listen` on a card opens the full reader and starts playback, which is surprising if the user only wanted to browse while listening.
- The reader's `Listen` button is small and tied to whatever existing audio variant happened to be found.
- Point-form summaries are not good listening material.
- Ponderings/research has no obvious audio path.
- The bottom audio bar is useful, but visually disconnected from the content that produced the audio.

## Product Direction

Treat audio as a reader-level consumption mode, not as another summary variant.

The reader should answer three user intents:

1. `Read this aloud`
2. `Create audio version of this`
3. `Create full briefing`

These intents should be available from the reader regardless of the active tab. Summary, Ponderings, and Transcript can all expose audio without each tab owning its own audio UI.

## Important Distinction

Do not collapse all audio into one technical category.

There are at least three different kinds of audio:

- **Device read-aloud:** browser/device TTS over visible text. Instant, free, not necessarily saved, and not always compatible with seeking or background playback.
- **Existing generated audio:** the current MP3-style audio already discovered through `has_audio`, `media.audio_url`, and `summary_variants[].audio_url`.
- **On-demand generated audio artifact:** a saved MP3 created from a source context and content hash.

The UX can present these together under one audio button, but the backend should not force them back into `summary_variants`.

## UX Design

### Reader Audio Button

Add one audio button to the reader header, near the close/admin controls.

The button should be visible on:

- Summary variants
- Ponderings
- Transcript

It should be a small reader-level control, not a new tab-specific button.

### Menu Labels

Use user-facing labels, not internal pipeline names:

```text
Read this aloud
Create audio version of this
Create full briefing
```

Avoid labels like `Summarize for Audio` in the UI. That can remain an internal mode name.

### Popover / Mobile Sheet

Desktop can use a compact popover:

```text
Read this aloud              Instant
Create audio version of this Cached / Generate
Create full briefing         Cached / Generate
```

Mobile should use the same content but may render as a small bottom sheet if the header popover is cramped.

Each row should communicate:

- Availability: instant, cached, generated, or generating
- Estimated or known duration
- Whether the option uses the device voice or creates a saved audio file

Example copy:

- `Read this aloud` - `Device voice`
- `Create audio version of this` - `Saved audio`
- `Create full briefing` - `Summary + research`

## Audio Modes

### Mode 1: Read This Aloud

Purpose: immediate listening for the text currently in view.

Behavior:

- Uses browser/device TTS first.
- Does not create a saved MP3.
- Does not require backend changes.
- Should not be represented as cached audio.
- Should be cancellable from the reader/audio UI.

Source context:

- Summary tab: active visible summary variant.
- Ponderings tab: visible research report or visible Ponderings content.
- Transcript tab: transcript text.

Constraints:

- Browser TTS voice quality varies.
- Seeking/duration may be limited.
- Mobile lock-screen/background behavior may be inconsistent.

This mode is useful because it makes audio feel always available, but it should not be oversold as a polished audio summary.

### Mode 2: Create Audio Version of This

Purpose: turn the current visible content into a better listening artifact.

Behavior:

- Takes the active source context.
- Runs an LLM transform that converts visual/point-form text into spoken narrative.
- Removes or rewrites tables, bullets, headings, repeated labels, and UI-ish text.
- Generates server-side TTS.
- Saves the audio as an artifact keyed by source hash.
- Reuses cached output when the same source content is requested again.

Internal mode name:

```text
audio_current
```

Examples:

- Active `Key Insights` summary -> concise narrative audio.
- Active Ponderings report -> research-note audio.
- Transcript -> compressed spoken recap, not a full transcript readout unless explicitly chosen later.

### Mode 3: Create Full Briefing

Purpose: produce a cohesive briefing from all useful content for the current report.

Behavior:

- Gathers main summaries, active/generated research when available, and selected analysis metadata.
- Synthesizes a coherent audio script.
- Generates server-side TTS.
- Saves the audio as an artifact keyed by a combined source hash.
- Uses background generation, because this can be slower and more expensive.

Internal mode name:

```text
audio_briefing
```

The briefing should not simply concatenate every text variant. It should deduplicate and produce one coherent spoken piece.

## Source Context Contract

The most important frontend/backend contract is the source context.

Suggested shape:

```json
{
  "video_id": "abc123",
  "scope": "summary_active",
  "label": "Key Insights",
  "source_hash": "sha256...",
  "source_text": "canonical text used to generate or read",
  "source_parts": [
    {
      "kind": "summary_variant",
      "label": "Key Insights",
      "hash": "sha256..."
    }
  ]
}
```

Suggested scopes:

- `summary_active`
- `ponderings_visible`
- `transcript_visible`
- `full_briefing`

For Phase 1, `source_text` can remain client-side for read-aloud only. For generated modes, the backend should either reconstruct trusted source text from `video_id` and `scope` or validate client-provided text carefully.

## Artifact Model

On-demand generated audio should use an artifact/cache model rather than `summary_variants`.

Suggested artifact fields:

```json
{
  "id": "uuid-or-derived-key",
  "video_id": "abc123",
  "mode": "audio_current",
  "scope": "summary_active",
  "source_hash": "sha256...",
  "status": "ready",
  "audio_url": "/exports/audio/audio_abc123_audio_current_ab12cd34.mp3",
  "duration_seconds": 314,
  "provider": "openai_tts",
  "created_at": "2026-04-10T12:00:00Z",
  "source_label": "Key Insights"
}
```

Status values:

- `missing`
- `queued`
- `generating`
- `ready`
- `failed`

Store artifacts somewhere queryable by the dashboard. PostgreSQL is preferable for status and metadata. Files can still live under the existing exports/audio path.

Do not represent these artifacts as `summary_variants`. Existing batch audio variants can still be read and displayed as legacy/generated audio.

## Backend API

Prefer async generation from day one.

### `GET /api/audio/options`

Input:

```text
video_id
scope
source_hash
```

Returns menu state for the current reader context:

```json
{
  "read_aloud": {
    "available": true,
    "kind": "device_tts"
  },
  "audio_current": {
    "status": "ready",
    "audio_url": "/exports/audio/audio_abc123_audio_current_ab12cd34.mp3",
    "duration_seconds": 314,
    "cached": true
  },
  "audio_briefing": {
    "status": "missing",
    "estimated_seconds": 480
  },
  "legacy_audio": {
    "available": true,
    "audio_url": "/exports/audio/existing.mp3",
    "duration_seconds": 228
  }
}
```

### `POST /api/audio/generate`

Input:

```json
{
  "video_id": "abc123",
  "mode": "audio_current",
  "scope": "summary_active",
  "source_hash": "sha256..."
}
```

Response:

```json
{
  "job_id": "job_123",
  "status": "queued"
}
```

If cached:

```json
{
  "status": "ready",
  "cached": true,
  "audio_url": "/exports/audio/audio_abc123_audio_current_ab12cd34.mp3",
  "duration_seconds": 314
}
```

### `GET /api/audio/jobs/:job_id`

Returns:

```json
{
  "job_id": "job_123",
  "status": "ready",
  "audio_url": "/exports/audio/audio_abc123_audio_current_ab12cd34.mp3",
  "duration_seconds": 314
}
```

If the existing SSE channel is used, also emit an `audio-generated` event when generation completes.

## Cache Strategy

Cache by mode + scope + canonical source hash.

```text
source_hash = sha256(mode + scope + canonical_source_text)
```

For `audio_briefing`, include every input part in a stable order:

```text
source_hash = sha256(mode + summary_hashes + research_hash + selected_metadata_hash)
```

This prevents stale audio when the summary or research changes.

## Existing Audio Compatibility

Keep the existing pipeline working:

- Do not remove `audio`, `audio-fr`, or `audio-es` variants.
- Do not remove `has_audio` filtering.
- Do not remove the existing bottom audio bar.
- Continue to discover legacy audio from `media.audio_url` and `summary_variants[].audio_url`.

But in the new reader UI, present existing audio as an available option in the audio menu rather than making it the only visible audio path.

Possible menu behavior:

- If legacy audio exists, show `Play existing audio` or mark `Create audio version of this` as already available only if its source context actually matches.
- Do not pretend legacy audio is the same as an on-demand artifact unless it can be associated with a matching source hash.

## Implementation Phases

### Phase 1: Reader Audio Menu + Existing Audio Discovery

- Add reader audio button.
- Add popover/bottom-sheet menu.
- Show `Read this aloud` as available.
- Show existing generated audio when a legacy audio URL exists.
- Keep existing bottom player for MP3 playback.
- Do not add new backend generation yet.

This phase improves discoverability without changing the data model.

### Phase 2: Read This Aloud

- Implement browser/device TTS for the current visible context.
- Add stop/pause behavior that does not conflict with MP3 playback.
- Make the label clear: device voice, not saved audio.
- Confirm behavior on mobile browsers.

This can also be folded into Phase 1 if the implementation stays small.

### Phase 3: Artifact Metadata + Status API

- Add audio artifact metadata storage.
- Add `GET /api/audio/options`.
- Add cache lookup by source hash.
- Keep artifacts separate from `summary_variants`.

### Phase 4: Create Audio Version of This

- Add async `POST /api/audio/generate`.
- Implement LLM spoken-script transform.
- Generate server-side TTS.
- Store artifact metadata and file.
- Show generating/ready/failed state in the menu.

### Phase 5: Create Full Briefing

- Gather summary + research source parts.
- Deduplicate and synthesize a cohesive briefing script.
- Generate and cache the briefing artifact.
- Emit progress/completion via job polling or SSE.

## Open Questions

1. Should `Read this aloud` use browser TTS only, or should there also be a server-quality instant option later?
2. Which server TTS provider should be the default for generated artifacts?
3. What cost guardrails are needed for `audio_current` and `audio_briefing`?
4. Should generated audio artifacts expire, or should they persist until the source hash changes?
5. For Ponderings, should the first version read/generate from the visible research report only, or include chat turns too?
6. Should transcript audio be a full transcript readout, a recap, or hidden until there is a clearer use case?
7. Should the old card-level `Listen` action remain, or should it open the reader audio menu instead of auto-playing?

## Verification

1. Audio button is visible in the reader on Summary, Ponderings, and Transcript views.
2. Menu opens on desktop and mobile without layout overflow.
3. Existing generated audio is discoverable from the menu when available.
4. `Read this aloud` is clearly labeled as device/browser voice.
5. Browser TTS can start and stop without breaking MP3 playback.
6. Generated audio artifacts are not written into `summary_variants`.
7. Cached generated audio returns immediately for matching source hash.
8. Stale generated audio is invalidated when source content changes.
9. Async generation shows queued/generating/ready/failed states.
10. The existing bottom player still works for MP3 playback.

---

Draft plan. Do not implement until the source context and artifact model are agreed.
