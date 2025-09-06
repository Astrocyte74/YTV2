# CLAUDE.md - YTV2-Dashboard Web Interface

This is the **dashboard component** of the YTV2 hybrid architecture - it serves the web interface with audio playback and receives synced content from the NAS processing component.

## Project Architecture

This is the **dashboard/web interface component** of YTV2 that:
- Serves the beautiful web dashboard interface
- Provides JSON report endpoints for individual summaries
- Handles audio file streaming and playback
- Receives file uploads from the NAS component via API
- Operates in dashboard-only mode (no processing)

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

# Access dashboard at http://localhost:10000
```

### Testing
```bash
# Test API upload endpoint
curl -X POST http://localhost:10000/api/upload-report \
  -H "Authorization: Bearer your_sync_secret" \
  -F "file=@test_report.json"

# Test health endpoint
curl http://localhost:10000/health
```

## Architecture Overview

This is the **web interface** component of the YTV2 hybrid architecture:

### YTV2 Hybrid System
- **NAS Component**: YTV2-NAS - Telegram bot + YouTube processing
- **Dashboard Component**: This project - Web interface + audio playback

### Dashboard Server Architecture

#### `telegram_bot.py` - Dashboard Server (Not Telegram!)
- HTTP server that serves the dashboard interface
- Handles JSON report endpoints (`/<stem>.json`)
- Serves audio files via `/exports/<filename>`
- Receives uploads from NAS via `/api/upload-report`
- **Dashboard-only mode** - No Telegram bot functionality

#### Key HTTP Routes
- **`/`** - Main dashboard interface (HTML)
- **`/<stem>.json`** - Individual report data (JSON API)
- **`/exports/<filename>`** - Audio file streaming
- **`/api/upload-report`** - Receive files from NAS (POST)
- **`/health`** - Health check endpoint for monitoring
- **`/delete-reports`** - Bulk report management interface

### Data Flow

1. **NAS Processing** → YouTube videos processed with AI summaries
2. **NAS Sync** → Reports and audio uploaded via `/api/upload-report`
3. **Dashboard Serving** → Web interface displays reports with audio playback
4. **User Access** → Beautiful web interface for browsing and listening

### Key Components

#### `telegram_bot.py` - Web Server
- **Not a Telegram bot!** - Confusing name, but it's the web server
- Flask/HTTP server handling all dashboard routes
- Dashboard-only mode detection (empty TELEGRAM_BOT_TOKEN)
- File serving for reports and audio content
- API endpoints for NAS synchronization

#### `dashboard_template.html` - Main Interface
- Glass morphism UI with responsive design
- Interactive report browsing with filtering
- Integrated audio player with metadata display
- Mobile-optimized touch interfaces
- Dark/light theme support

#### `static/` - Frontend Assets
- **`dashboard.css`** - Modern styling with glass morphism effects
- **`dashboard.js`** - Interactive functionality and audio player controls

#### `modules/report_generator.py` - Report Handling
- JSON report parsing and validation
- Template processing for web display
- Metadata extraction for audio integration

### File Structure

#### Essential Dashboard Files
```
YTV2-Dashboard/
├── telegram_bot.py          # Web server (dashboard-only mode)
├── dashboard_template.html  # Main UI template
├── Dockerfile              # Render deployment
├── render.yaml             # Render configuration
├── modules/                # Dashboard utilities
│   └── report_generator.py # Report processing
├── static/                 # Frontend assets
│   ├── dashboard.css      # UI styling
│   └── dashboard.js       # Interactive features
├── data/                  # Synced JSON reports
├── exports/              # Synced audio files
└── requirements.txt      # Python dependencies
```

#### Archived Content
- `archive_render/old_*` - Previous versions and unused components
- `archive_render/unused_processing/` - Processing code moved to NAS
- `archive_render/old_configs/` - Old deployment configurations

### Environment Configuration

#### Required Variables
```bash
# Dashboard-only mode (leave empty!)
TELEGRAM_BOT_TOKEN=""

# Sync security - must match NAS setting
SYNC_SECRET=your_secure_random_string_here
```

#### Auto-Configured by Render
```bash
# Port configuration (handled by Render)
PORT=10000

# Dashboard URL (auto-set by Render)
RENDER_DASHBOARD_URL=https://your-app.onrender.com
```

### NAS Integration

The dashboard receives content from the NAS component via:

#### Upload API
- **Endpoint**: `POST /api/upload-report`
- **Authentication**: Bearer token using SYNC_SECRET
- **Content**: JSON reports and audio files
- **Response**: Success/error status for sync monitoring

#### Sync Process
1. **NAS generates** reports and audio files
2. **NAS uploads** via authenticated API calls
3. **Dashboard stores** in data/ and exports/ directories
4. **Web interface** immediately shows new content

### Deployment

This component deploys to **Render** using Docker:

#### Render Configuration
- **Environment**: Docker
- **Dockerfile**: Optimized for dashboard serving
- **Build**: Automatic from git push
- **Domain**: Custom Render subdomain provided
- **HTTPS**: Included by default

#### Render Benefits
- **Auto-scaling** handles traffic variations
- **Global CDN** for fast worldwide access  
- **Zero-downtime deployments** with health checks
- **Persistent storage** for synced content

### Dashboard Features

#### Web Interface
- **Glass morphism design** with modern visual effects
- **Responsive layout** works on desktop, tablet, mobile
- **Fast loading** with optimized static assets
- **Intuitive navigation** through report collections

#### Audio Integration
- **Embedded audio player** with full controls
- **Metadata display** shows video info and thumbnails
- **Progress tracking** and seeking within audio
- **Mobile-optimized** touch controls

#### Report Display
- **Syntax highlighting** for JSON content
- **Collapsible sections** for easy navigation
- **Search and filtering** across report collections
- **Direct linking** to individual reports

## Important Implementation Notes

- This is **dashboard-only** - no YouTube processing happens here
- **Receives content** via sync rather than generating locally
- **Designed for hybrid architecture** with separate concerns
- **No AI dependencies** - just web serving and file handling
- **Public accessibility** - shareable URL for viewing summaries
- **Secure uploads only** - authenticated NAS sync required
- **Docker deployment** optimized for Render platform
- **Mobile-first design** ensures accessibility across devices