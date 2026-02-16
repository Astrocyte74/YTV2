# YTV2 Architecture Overview

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         YTV2 LOCAL DEPLOYMENT                               │
│                     i9 Mac (Docker) + M4 Mac (Tailscale)                    │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                          EXTERNAL SERVICES                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐         ┌──────────────┐         ┌──────────────┐       │
│  │  Telegram    │         │  OpenRouter  │         │  Flux.2 API  │       │
│  │     Bot      │         │     API      │         │  (Optional)  │       │
│  │  (@Astro74)  │         │   (Gemini)   │         │              │       │
│  └──────┬───────┘         └──────┬───────┘         └──────┬───────┘       │
│         │                        │                        │               │
│         └────────────────────────┴────────────────────────┘               │
│                                  │                                        │
└──────────────────────────────────┼──────────────────────────────────────────┘
                                   │ HTTPS API Calls
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              i9 MAC (LOCAL HOST)                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                  DOCKER CONTAINERS                                    │  │
│  │                                                                       │  │
│  │  ┌─────────────────────────┐    ┌─────────────────────────────────┐  │  │
│  │  │  Backend Bot            │    │  Dashboard                       │  │  │
│  │  │  youtube-summarizer-bot │    │  ytv2-dashboard                  │  │  │
│  │  ├─────────────────────────┤    ├─────────────────────────────────┤  │  │
│  │  │  • Telegram Bot         │    │  • Web Interface (Port 10000)   │  │  │
│  │  │  • Video Processing     │    │  • Content Index & Search       │  │  │
│  │  │  • AI Summarization     │    │  • Audio Playback               │  │  │
│  │  │  • Queue Management     │    │  • Quiz Interface               │  │  │
│  │  │                         │    │                                 │  │  │
│  │  │  Ports: 6452, 6453      │    │  Port: 10000                    │  │  │
│  │  └───────────┬─────────────┘    └───────────────┬─────────────────┘  │  │
│  │              │                                  │                    │  │
│  │              └────────────────┬─────────────────┘                    │  │
│  │                               │                                      │  │
│  │                    host.docker.internal                              │  │
│  └───────────────────────────────┼──────────────────────────────────────┘  │
│                                  │                                        │
│  ┌───────────────────────────────┴──────────────────────────────────────┐  │
│  │                  POSTGRESQL (Homebrew)                                │  │
│  │                                                                       │  │
│  │  • Content Metadata        • Summary Variants                        │  │
│  │  • User Data               • Quiz Data                               │  │
│  │                                                                       │  │
│  │  Port: 5432                Database: ytv2                            │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│                    ┌──────────────────┐                                     │
│                    │    Tailscale     │                                     │
│                    │  (VPN Gateway)   │                                     │
│                    └────────┬─────────┘                                     │
└─────────────────────────────┼───────────────────────────────────────────────┘
                              │
                    ┌─────────┴─────────┐
                    │   Tailscale VPN   │
                    └─────────┬─────────┘
                              │
┌─────────────────────────────┼───────────────────────────────────────────────┐
│                     M4 MAC (REMOTE via Tailscale)                           │
│                            IP: 100.101.80.13                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                     TTSHUB API (Port 7860)                             │  │
│  │                                                                        │  │
│  │  ┌─────────────────────────┐    ┌─────────────────────────────────┐   │  │
│  │  │  DrawThings             │    │  TTS Services                    │   │  │
│  │  │  • Flux.1 Schnell       │    │  • Audio Generation              │   │  │
│  │  │  • Image Generation     │    │  • Voice Synthesis               │   │  │
│  │  │  • 384x384, 6 steps     │    │                                  │   │  │
│  │  │  • Excellent Quality    │    │                                  │   │  │
│  │  └─────────────────────────┘    └─────────────────────────────────┘   │  │
│  │                                                                        │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DATA FLOW                                         │
└─────────────────────────────────────────────────────────────────────────────┘

USER INPUT (YouTube URL via Telegram)
   │
   ▼
┌─────────────────────────┐
│  i9 MAC - BACKEND       │
│  (youtube-summarizer)   │
├─────────────────────────┤
│ 1. Download Video       │
│ 2. Extract Transcript   │
│ 3. Generate Summaries   │  ◄──── OpenRouter API (Gemini 2.5 Flash Lite)
│ 4. Create Audio (TTS)   │  ◄──── M4 Mac TTSHUB (Port 7860)
│ 5. Generate Images      │  ◄──── M4 Mac DrawThings (Flux.1 Schnell)
│ 6. Store Metadata       │
└─────────────────────────┘
   │
   │ Direct Write (PostgreSQL)
   ▼
┌─────────────────────────┐
│  POSTGRESQL (Homebrew)  │
├─────────────────────────┤
│ • content table         │
│ • summaries table       │
│ • analysis data         │
│ • quiz data             │
└─────────────────────────┘
   │
   │ Read Query
   ▼
┌─────────────────────────┐
│  i9 MAC - DASHBOARD     │
│  (web interface)        │
├─────────────────────────┤
│ • Display Content       │
│ • Serve Audio Files     │
│ • Search & Filter       │
│ • Quiz Interface        │
└─────────────────────────┘
   │
   │ HTTP Response
   ▼
USER VIEW (Web Browser - Tailscale)
```

---

## Image Generation Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      IMAGE GENERATION PIPELINE                              │
└─────────────────────────────────────────────────────────────────────────────┘

                     ┌─────────────────────┐
                     │  Summary Complete   │
                     │  (needs thumbnail)  │
                     └──────────┬──────────┘
                                │
                                ▼
              ┌─────────────────────────────────┐
              │  SUMMARY_IMAGE_PROVIDERS        │
              │  Priority: drawthings, zimage   │
              └─────────────────────────────────┘
                                │
         ┌──────────────────────┼──────────────────────┐
         │                      │                      │
         ▼                      ▼                      ▼
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│  DrawThings     │   │  Z-Image        │   │  Flux.2 Klein   │
│  (Primary)      │   │  (Backup)       │   │  (Disabled)     │
├─────────────────┤   ├─────────────────┤   ├─────────────────┤
│ M4 Mac          │   │ Remote API      │   │ OpenRouter API  │
│ Flux.1 Schnell  │   │ Free            │   │ $0.014/image    │
│ Free            │   │                 │   │                 │
│ ~5-10 seconds   │   │ Varies          │   │ ~5 seconds      │
│ Quality: 9/10   │   │ Quality: 7/10   │   │ Quality: 8/10   │
│                 │   │                 │   │                 │
│ ALWAYS ON       │   │ FALLBACK        │   │ FLUX2_ENABLED=0 │
└────────┬────────┘   └────────┬────────┘   └────────┬────────┘
         │                     │                     │
         │    ┌────────────────┘                     │
         │    │                                      │
         ▼    ▼                                      ▼
    ┌─────────────────┐                    ┌─────────────────┐
    │  Image Ready    │                    │  (Gated - Off)  │
    │  Store to DB    │                    │                 │
    └─────────────────┘                    └─────────────────┘
```

---

## Network Connectivity

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         NETWORK CONNECTIVITY                                │
└─────────────────────────────────────────────────────────────────────────────┘

INTERNET
   │
   │ HTTPS (APIs)
   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              i9 MAC                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│  Tailscale: marks-macbook-pro-2.tail9e123c.ts.net                           │
│  Local IP: 192.168.x.x                                                      │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │  Docker Network (Bridge)                                              │  │
│  │                                                                       │  │
│  │  ┌─────────────┐  ┌─────────────┐                                    │  │
│  │  │ Backend Bot │  │  Dashboard  │                                    │  │
│  │  │ Port 6452   │  │ Port 10000  │                                    │  │
│  │  │ Port 6453   │  │             │                                    │  │
│  │  └──────┬──────┘  └──────┬──────┘                                    │  │
│  │         │                │                                            │  │
│  │         └───────┬────────┘                                            │  │
│  │                 │                                                     │  │
│  │     host.docker.internal:5432                         │  │
│  └─────────────────┼─────────────────────────────────────────────────────┘  │
│                    │                                                        │
│  ┌─────────────────┴─────────────────────────────────────────────────────┐  │
│  │  PostgreSQL (Homebrew) - Port 5432                                    │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
                          Tailscale VPN
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              M4 MAC                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│  Tailscale IP: 100.101.80.13                                                │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  TTSHUB API - Port 7860                                              │   │
│  │  • DrawThings (Flux.1 Schnell)                                       │   │
│  │  • TTS Services                                                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

External Access (via Tailscale):
   • Dashboard: http://marks-macbook-pro-2.tail9e123c.ts.net:10000
   • M4 Mac TTSHUB: http://100.101.80.13:7860/api (internal only)

Docker Internal Communication:
   • Backend → PostgreSQL: host.docker.internal:5432
   • Dashboard → PostgreSQL: host.docker.internal:5432
   • Backend → M4 Mac TTSHUB: 100.101.80.13:7860/api
```

---

## Port Summary

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          PORT USAGE SUMMARY                                 │
└─────────────────────────────────────────────────────────────────────────────┘

i9 MAC (Docker):
├─ 6452  → Backend web interface (debug)
├─ 6453  → YTV2 API server
├─ 10000 → Dashboard web server
└─ 5432  → PostgreSQL (Homebrew, external to Docker)

M4 MAC (Remote):
└─ 7860  → TTSHUB API (DrawThings + TTS)

EXTERNAL (HTTPS):
├─ 443   → OpenRouter API (Gemini 2.5 Flash Lite)
├─ 443   → Telegram Bot API
└─ 443   → Flux.2 API (optional, OpenRouter)

USER ACCESS (via Tailscale):
├─ Dashboard → marks-macbook-pro-2.tail9e123c.ts.net:10000
└─ Telegram  → @Astro74Bot
```

---

## Configuration Files

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        CONFIGURATION FILES                                  │
└─────────────────────────────────────────────────────────────────────────────┘

BACKEND (i9 Mac):
├─ /Users/markdarby16/16projects/ytv2/backend/.env.nas
├─ /Users/markdarby16/16projects/ytv2/backend/docker-compose.yml
└─ /Users/markdarby16/16projects/ytv2/backend/telegram_bot.py

DASHBOARD (i9 Mac):
├─ /Users/markdarby16/16projects/ytv2/dashboard16/.env
├─ /Users/markdarby16/16projects/ytv2/dashboard16/docker-compose.yml
└─ /Users/markdarby16/16projects/ytv2/dashboard16/server.py

DATABASE (i9 Mac Homebrew):
├─ /opt/homebrew/var/postgresql@14/ (data directory)
└─ postgresql.conf, pg_hba.conf (Homebrew locations)
```

---

## Key Environment Variables

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      KEY ENVIRONMENT VARIABLES                              │
└─────────────────────────────────────────────────────────────────────────────┘

BACKEND (.env.nas):
├─ DATABASE_URL=postgresql://ytv2:password@host.docker.internal:5432/ytv2
├─ POSTGRES_ONLY=true
├─ DASHBOARD_URL=http://marks-macbook-pro-2.tail9e123c.ts.net:10000
├─ TTSHUB_API_BASE=http://100.101.80.13:7860/api
├─ LLM_PROVIDER=openrouter
├─ LLM_MODEL=google/gemini-2.5-flash-lite
├─ SUMMARY_IMAGE_PROVIDERS=drawthings,zimage
├─ SUMMARY_IMAGE_ENABLED=1
└─ FLUX2_ENABLED=0

DASHBOARD (.env):
├─ DATABASE_URL=postgresql://...
└─ (serves static files, reads from DB)
```

---

## Image Generation Providers

| Provider | Location | Cost | Quality | Speed | Status |
|----------|----------|------|---------|-------|--------|
| **DrawThings** | M4 Mac | Free | Excellent (9/10) | ~5-10s | Primary |
| **Z-Image** | Remote | Free | Good (7/10) | Varies | Backup |
| **Flux.2 Klein** | OpenRouter | $0.014/img | Good (8/10) | ~5s | Disabled |
| ~~Auto1111~~ | ~~i9 Mac~~ | ~~Free~~ | ~~Poor (2/10)~~ | ~~6min~~ | Removed |

---

## Access URLs

| Service | URL |
|---------|-----|
| Dashboard (Tailscale) | http://marks-macbook-pro-2.tail9e123c.ts.net:10000 |
| Dashboard (Local) | http://localhost:10000 |
| Backend API (Local) | http://localhost:6453 |
| Telegram Bot | @Astro74Bot |
| M4 Mac TTSHUB (Internal) | http://100.101.80.13:7860/api |

---

## Quick Commands

```bash
# Start/Restart Backend
cd /Users/markdarby16/16projects/ytv2/backend
docker-compose down && docker-compose up -d

# Start/Restart Dashboard
cd /Users/markdarby16/16projects/ytv2/dashboard16
docker-compose down && docker-compose up -d

# View Logs
docker logs youtube-summarizer-bot --tail 50 -f
docker logs ytv2-dashboard --tail 50 -f

# Database
python tools/test_postgres_connect.py

# Status CLI
./ytv2 status
```

---

**Last Updated**: 2026-02-16
**Deployment**: Local Docker on i9 Mac + Remote M4 Mac via Tailscale
**Network**: Tailscale VPN + Docker Bridge Network
