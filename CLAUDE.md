# CLAUDE.md - YTV2-Dashboard Web Interface

This is the **dashboard component** of the YTV2 hybrid architecture - it serves the web interface with audio playback and receives synced content from the NAS processing component.

## Project Architecture

This is the **dashboard/web interface component** of YTV2 that:
- Serves the beautiful web dashboard interface
- Provides JSON report endpoints for individual summaries
- Handles audio file streaming and playback
- Receives file uploads from the NAS component via API
- Operates in dashboard-only mode (no processing)

## YTV2 Hybrid System
- **NAS Component**: /Volumes/Docker/YTV2/ - Telegram bot + YouTube processing
- **Dashboard Component**: This project - Web interface + audio playback

## Dashboard Server Architecture

### `telegram_bot.py` - Dashboard Server (Not Telegram!)
- HTTP server that serves the dashboard interface
- Handles JSON report endpoints (`/<stem>.json`)
- Serves audio files via `/exports/<filename>`
- Receives uploads from NAS via `/api/upload-report`
- **Dashboard-only mode** - No Telegram bot functionality

### Key HTTP Routes
- **`/`** - Main dashboard interface (HTML)
- **`/<stem>.json`** - Individual report data (JSON API)
- **`/exports/<filename>`** - Audio file streaming
- **`/api/upload-report`** - Receive files from NAS (POST)
- **`/health`** - Health check endpoint for monitoring
- **`/delete-reports`** - Bulk report management interface

## Data Flow

1. **NAS Processing** → YouTube videos processed with AI summaries
2. **NAS Sync** → Reports and audio uploaded via `/api/upload-report`
3. **Dashboard Serving** → Web interface displays reports with audio playback
4. **User Access** → Beautiful web interface for browsing and listening

## Technology Stack

### Backend
- **Database**: SQLite (`ytv2_content.db`) with enhanced multi-category structure
- **Content Management**: `modules/sqlite_content_index.py` (SQLiteContentIndex)
- **Server**: Flask/HTTP server in dashboard-only mode
- **Deployment**: Render with MCP access for database operations

### Frontend
- **Template**: `dashboard_template.html` with glass morphism UI
- **Styling**: `static/dashboard.css` - Modern responsive design
- **Interactivity**: `static/dashboard.js` - Audio player and filtering
- **Audio Integration**: Embedded player with metadata display

## Database Structure (SQLite)

### Enhanced Multi-Category System
Recent backfill work (September 2025) enhanced the database with:
- **Multiple categories per video**: e.g., "AI Software Development" + "Technology" + "Business"
- **Multiple subcategories per category**: Each category has its own subcategories array
- **Structured format**: `{categories: [{category: "X", subcategories: ["Y", "Z"]}]}`
- **Language tracking**: Separate `video_language` and `summary_language` fields
- **Complexity levels**: Beginner/Intermediate/Advanced classification

### Content Processing Pipeline
1. **Primary AI**: OpenAI for text summaries and TTS
2. **Backfill Enhancement**: Gemma 3:12b (via Ollama) for category classification
3. **Storage**: All data stored in SQLite with JSON fields for complex structures

## Current Challenge

**Issue**: Dashboard cards on Render (https://ytv2-vy9k.onrender.com/) only display:
- First 2 categories (out of potentially 3)
- First 1 subcategory (out of multiple per category)

**Expected**: Full display of all categories and subcategories like:
- "Tesla Autopilot" → **AI Software Development** + **Technology** + **Business**
- Each category showing its own subcategories: ['Security & Safety'] + ['Tech Reviews'] + ['Industry Analysis']

## Environment Configuration

### Required Variables
```bash
# Dashboard-only mode (leave empty!)
TELEGRAM_BOT_TOKEN=""

# Sync security - must match NAS setting
SYNC_SECRET=your_secure_random_string_here
```

### Auto-Configured by Render
```bash
# Port configuration (handled by Render)
PORT=10000

# Dashboard URL (auto-set by Render)
RENDER_DASHBOARD_URL=https://your-app.onrender.com
```

## File Structure

### Essential Dashboard Files
```
YTV2-Dashboard/
├── telegram_bot.py          # Web server (dashboard-only mode)
├── dashboard_template.html  # Main UI template
├── modules/                 # Dashboard utilities
│   └── sqlite_content_index.py # SQLite database interface
├── static/                  # Frontend assets
│   ├── dashboard.css       # UI styling
│   └── dashboard.js        # Interactive features
├── data/                   # Local data (if any)
├── exports/               # Audio files
└── requirements.txt       # Python dependencies
```

### Key Modules
- **`modules/sqlite_content_index.py`**: SQLiteContentIndex class for database queries
- **`modules/report_generator.py`**: Report processing utilities (legacy)

## Deployment

### Render Configuration
- **Environment**: Python web service
- **Database**: SQLite file uploaded via sync API
- **Build**: Automatic from git push
- **Domain**: https://ytv2-vy9k.onrender.com/
- **MCP Access**: Available for database operations

## Important Implementation Notes

- This is **dashboard-only** - no YouTube processing happens here
- **Receives content** via sync rather than generating locally
- **SQLite backend** - NOT JSON files (critical for context)
- **No AI dependencies** - just web serving and file handling
- **Public accessibility** - shareable URL for viewing summaries
- **Secure uploads only** - authenticated NAS sync required

## Development Commands

### Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Run dashboard server locally
python telegram_bot.py
```

### Database Operations
```bash
# Access SQLite database (if present locally)
sqlite3 ytv2_content.db

# Sync database to/from Render (via NAS component)
# Done through /api/upload-report endpoint
```

## Recent Work (September 2025)

### Backfill Enhancement
- Used Gemma 3:12b via Ollama for enhanced categorization
- Processed 55 records with multi-category assignments
- Enhanced prompt with specialized WWII detection rules
- Perfect JSON output with categories→subcategories structure
- Successfully uploaded enhanced database to Render

### Architecture Status
- ✅ NAS processing pipeline working
- ✅ SQLite database enhanced with multi-categories
- ✅ Dashboard backend serving data correctly
- ✅ Dashboard cards showing all subcategories (FIXED September 13, 2025)
- ✅ Individual report pages showing subcategories (FIXED September 13, 2025)

## Context Preservation Tips for Future Claude Sessions

### Critical Architecture Files
- **Main Template**: `dashboard_v3_template.html` (loads dashboard_v3.js)
- **Main JavaScript**: `static/dashboard_v3.js` (the ONLY dashboard JS file)
- **Main Server**: `telegram_bot.py` (dashboard-only mode, no Telegram)
- **Database**: SQLite via `modules/sqlite_content_index.py`

### Debugging Quick Reference
```bash
# Check which template is being used
grep -r "dashboard_v3_template\|dashboard_template" telegram_bot.py

# Check what JavaScript is loaded
grep "dashboard.*js" dashboard_v3_template.html

# Verify data format being sent to dashboard
curl "https://ytv2-vy9k.onrender.com/api/reports?size=1" | jq '.reports[0].analysis'

# Check console for debug logs
# Search for: "Multi-category Debug:" in browser dev tools
```

### Common Pitfalls Avoided
1. ❌ **Wrong File**: Don't edit `dashboard.js` - it's not loaded
2. ❌ **Wrong Template**: Dashboard uses `dashboard_v3_template.html`
3. ❌ **Data Format**: SQLite uses `analysis.category` (array), `analysis.subcategory` (string)
4. ❌ **File Paths**: CSS/JS served without `static/` prefix in template URLs

**Last Safe Commit**: 79c0223 (September 13, 2025) - Dashboard cards subcategory display fixed

### Latest Work (September 13, 2025)
- ✅ **Individual Report Pages**: Added subcategory display to report_v2.html template
- ✅ **Backend Enhancement**: Modified to_report_v2_dict() to extract subcategory_pairs
- ✅ **Template Integration**: Added purple subcategory badges between Categories and Key Topics sections