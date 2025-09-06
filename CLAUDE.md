# CLAUDE.md - YTV2 Dashboard Project

This is the **Render Dashboard component** of the YTV2 system - it serves the web dashboard and handles audio playback.

## Project Structure

This is the dashboard/web interface portion of YTV2 that:
- Serves the HTML dashboard at the root URL
- Provides JSON report endpoints  
- Handles audio file playback via `/exports/` route
- Receives file uploads from the NAS via `/api/upload-report`

## Development Commands

### Setup and Installation
```bash
# Create virtual environment and install dependencies
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Running the Dashboard Server
```bash
# Run the dashboard server locally
python telegram_bot.py

# Or using Render deployment
# (deploys automatically via render.yaml)
```

## Architecture Overview

This is the **dashboard/web interface** component of the YTV2 hybrid architecture:

### YTV2 Hybrid System
- **NAS Component**: `/Volumes/Docker/YTV2-NAS` - Telegram bot + YouTube processing
- **Dashboard Component**: This project - Web dashboard + audio playback

### Dashboard Server Components

#### `telegram_bot.py` - Dashboard Server
- HTTP server that serves the dashboard interface
- Handles JSON report endpoints (`/<stem>.json`)
- Serves audio files via `/exports/<filename>`
- Receives uploads from NAS via `/api/upload-report`
- **Dashboard-only mode** - No Telegram bot functionality on Render

#### Key Routes
- `/` - Main dashboard interface
- `/<stem>.json` - Individual report data
- `/exports/<filename>` - Audio file serving
- `/api/upload-report` - Receive files from NAS
- `/delete-reports` - Bulk report management

### Data Flow

1. **NAS processes** YouTube videos and generates reports + audio
2. **NAS syncs** files to this dashboard via `/api/upload-report`  
3. **Dashboard serves** the web interface with reports and audio playback
4. **Users access** dashboard to view summaries and play audio

### File Structure

#### Active Files
- `telegram_bot.py` - Main dashboard server
- `nas_sync.py` - Sync utilities (for reference)
- `modules/` - Report generation and handling utilities
- `data/` - JSON reports (synced from NAS)
- `exports/` - Audio files (synced from NAS)
- `render.yaml` - Render deployment configuration
- `requirements.txt` - Python dependencies

#### Archived Files
- `archive_render/old_telegram_versions/` - Old Telegram bot iterations
- `archive_render/unused_processing/` - YouTube processing code (moved to NAS)
- `archive_render/old_configs/` - Old configuration files
- `archive_render/old_docker/` - Old Docker configurations

### Configuration

#### Environment Variables
- `RENDER_DASHBOARD_URL` - Dashboard URL for NAS sync
- `SYNC_SECRET` - Shared secret for NAS-Dashboard communication
- `TELEGRAM_BOT_TOKEN` - **Leave empty** for dashboard-only mode

### Deployment

This component deploys to **Render** via `render.yaml`:
- Automatic deployments on git push
- Persistent storage via Render disk
- Dashboard accessible via Render URL

## Important Implementation Notes

- This is **dashboard-only** - all YouTube processing happens on NAS
- Receives files via sync rather than generating them locally
- Designed for hybrid architecture with separate processing and serving
- Audio playback requires files to be synced from NAS first
- No local processing dependencies (OpenAI, LLM configs, etc.)