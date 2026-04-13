# Audio On-Demand Corrective Brief

## Current State

Audio on-demand is mostly wired through, but the live system is still inconsistent for cached artifacts.

- `audio_current` is working on the live dashboard.
- `audio_briefing` is still serving stale metadata in at least one known case.

This is not a design problem anymore. It is a storage/path/cache cleanup problem.

## Verified Live Findings

Checked against:

- Dashboard: `http://marks-macbook-pro-2:10000/editorial`
- Options API: `http://marks-macbook-pro-2:10000/api/audio/options`
- Repo paths:
  - dashboard: `/Volumes/markdarby16/16projects/ytv2/dashboard16`
  - backend: `/Volumes/markdarby16/16projects/ytv2/backend`

Known test video:

- `video_id=40e0b77c9f2b2e408f13d880`
- active variant: `key-insights`

Live API response showed:

- `audio_current.audio_url = /exports/audio/audio_40e0b77c9f2b2e408f13d880_audio_current_ed0690a1.mp3`
- `audio_briefing.audio_url = /exports/audio_40e0b77c9f2b2e408f13d880_audio_briefing_3ab20f9c.mp3`

Live URL checks showed:

- `GET /exports/audio/audio_40e0b77c9f2b2e408f13d880_audio_current_ed0690a1.mp3` -> `200`
- `GET /exports/audio_40e0b77c9f2b2e408f13d880_audio_briefing_3ab20f9c.mp3` -> `404`

Disk checks showed:

- current file exists at:
  `/Volumes/markdarby16/16projects/ytv2/backend/data/exports/audio/audio_40e0b77c9f2b2e408f13d880_audio_current_ed0690a1.mp3`
- briefing file exists at:
  `/Volumes/markdarby16/16projects/ytv2/backend/exports/audio_40e0b77c9f2b2e408f13d880_audio_briefing_3ab20f9c.mp3`

That means the new storage contract is only partially reflected in existing artifact rows / files.

## What The Code Now Does

Backend generation now writes new files to:

- [`ytv2_api/main.py`](/Volumes/markdarby16/16projects/ytv2/backend/ytv2_api/main.py:1431)
  `data/exports/audio/`

Backend now returns public URLs as:

- [`ytv2_api/main.py`](/Volumes/markdarby16/16projects/ytv2/backend/ytv2_api/main.py:1441)
  `/exports/audio/<filename>`

Dashboard export serving now has backend-data fallback:

- [`server.py`](/Volumes/markdarby16/16projects/ytv2/dashboard16/server.py:2888)
  `/app/backend-data/exports/audio`

So the new path is correct for newly generated artifacts.

## Actual Remaining Problem

Old cached rows and/or old generated files still exist under the previous flat path contract:

- file under backend `exports/`
- artifact URL still pointing to `/exports/<filename>`

This is why `audio_briefing` still looks `ready` in the options API while playback can fail.

## Required Fix

Pick one of these approaches and do it fully:

1. Preferred: migrate stale artifact rows and files
   - move or copy old backend flat files into `backend/data/exports/audio/`
   - update `audio_artifacts.audio_url` from `/exports/<filename>` to `/exports/audio/<filename>`

2. Acceptable: invalidate old rows
   - mark old flat-path artifacts stale/failed/missing
   - force regeneration under the new storage contract

3. Temporary compatibility fallback
   - teach dashboard serving to also resolve backend flat files from the old location
   - this is weaker because it preserves mixed contracts

## Important Constraint

Do not trust summary messages from the previous agent.

Validate with live commands after every change:

```bash
curl -s 'http://marks-macbook-pro-2:10000/api/audio/options?video_id=40e0b77c9f2b2e408f13d880&variant_slug=key-insights' | jq .
curl -I 'http://marks-macbook-pro-2:10000/exports/audio/audio_40e0b77c9f2b2e408f13d880_audio_current_ed0690a1.mp3'
curl -I 'http://marks-macbook-pro-2:10000/exports/audio/audio_40e0b77c9f2b2e408f13d880_audio_briefing_3ab20f9c.mp3'
```

Also inspect both directories:

```bash
ls -l /Volumes/markdarby16/16projects/ytv2/backend/data/exports/audio | rg '40e0b77c9f2b2e408f13d880'
ls -l /Volumes/markdarby16/16projects/ytv2/backend/exports | rg '40e0b77c9f2b2e408f13d880'
```

## Done Means

For the known test video:

- `audio_current.audio_url` uses `/exports/audio/...`
- `audio_briefing.audio_url` also uses `/exports/audio/...`
- both returned URLs give `200`
- both files live under `backend/data/exports/audio/` or another single consistent served location
- options API no longer reports stale legacy path metadata

## Minor Follow-Up

`audio_current.source_label` has also regressed to `Summary` in one live response where it previously showed `Key Insights`.

That is secondary to the playback bug, but worth cleaning up while touching artifact metadata.
