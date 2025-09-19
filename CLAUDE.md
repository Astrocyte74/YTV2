# CLAUDE.md - YTV2-Dashboard Web Interface

**🚨 CRITICAL: This deploys to Render automatically on git push!**  
**⚠️ ALWAYS commit and push changes for them to appear on live site:**
```bash
git add [files]
git commit -m "message"
git push origin main  # Triggers automatic Render deployment
```

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
- **Template**: `dashboard_v3_template.html` with glass morphism UI (ACTIVE VERSION)
- **Styling**: `static/dashboard_v3.css` - Modern responsive design
- **Interactivity**: `static/dashboard_v3.js` - Audio player and filtering (ONLY JS FILE LOADED)
- **Audio Integration**: Embedded player with metadata display
- **Legacy Files**: `dashboard_template.html` and `static/dashboard.js` were removed to prevent confusion

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

## Dashboard Features (Completed)

**Multi-Category & Subcategory Display**: ✅ FULLY IMPLEMENTED
- Dashboard cards show ALL categories (up to 3) for each video
- Each category displays its own subcategories as separate chips
- Individual report pages show subcategories as purple badges
- Consistent display across list view, grid view, and report pages

**Advanced Filtering System**: ✅ FULLY IMPLEMENTED  
- **Categories**: Hierarchical with subcategory support, show more toggle
- **Channels**: Clickable channel names, sorted by frequency, show more toggle
- **Content Types**: Tutorial, Discussion, Review, etc.
- **Complexity**: Beginner, Intermediate, Advanced
- **Languages**: Multi-language support
- **Sort Options**: Recently Added, Video Newest (default), with show more for advanced sorting

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
├── telegram_bot.py              # Web server (dashboard-only mode)
├── dashboard_v3_template.html   # Main UI template (ACTIVE VERSION)
├── templates/                   # Report templates
│   └── report_v2.html          # Individual report page template
├── modules/                     # Dashboard utilities
│   └── sqlite_content_index.py # SQLite database interface (WITH CHANNEL SUPPORT)
├── static/                      # Frontend assets
│   ├── dashboard_v3.css        # UI styling (ACTIVE VERSION)
│   └── dashboard_v3.js         # Interactive features (ONLY JS FILE LOADED)
├── data/                       # Local data (if any)  
├── exports/                    # Audio files
└── requirements.txt            # Python dependencies
```

**CRITICAL**: Only the `_v3` versions of files are active. Legacy files were removed to prevent confusion.

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

### Architecture Status (Updated September 13, 2025)
- ✅ NAS processing pipeline working
- ✅ SQLite database enhanced with multi-categories  
- ✅ Dashboard backend serving data correctly
- ✅ Dashboard cards showing all subcategories (FIXED)
- ✅ Individual report pages showing subcategories (FIXED) 
- ✅ Channel filtering system implemented (NEW)
- ✅ Clickable channel names for instant filtering (NEW)
- ✅ Reorganized Sort section with show more functionality (NEW)
- ✅ Grid view error fixed (subcatPairs undefined) (FIXED)

## Context Preservation Tips for Future Claude Sessions

### Critical Architecture Files
- **Main Template**: `dashboard_v3_template.html` (loads dashboard_v3.js)
- **Main JavaScript**: `static/dashboard_v3.js` (the ONLY dashboard JS file)
- **Main Server**: `telegram_bot.py` (dashboard-only mode, no Telegram)
- **Database**: SQLite via `modules/sqlite_content_index.py`

### Content Formatting Architecture
- **Inline Reader**: `dashboard_v3.js` formatKeyPoints() method (line ~2835)
- **Detail Pages**: `telegram_bot.py` format_key_points() method (line ~395)
- **Shared CSS**: `/static/shared.css` (common styles across both templates)
- **Template-specific CSS**: Inline `<style>` blocks in respective templates
- **HTML Security**: Update `ALLOWED_TAGS`/`ALLOWED_ATTRS` in `telegram_bot.py` for new elements

#### 🚨 CRITICAL: Dual Formatter Pattern
**Both inline cards AND individual pages must use identical formatting logic to prevent drift:**
- **Inline cards**: Use `dashboard_v3.js` formatKeyPoints() → renderStructuredKeyPoints()
- **Individual pages**: Use `telegram_bot.py` format_key_points() → _render_structured_key_points()
- **Template data flow**: `{{ summary_html | safe }}` in `report_v2.html` comes from format_key_points()
- **Key insight**: Any formatting changes must be applied to BOTH formatters identically

#### Static File Serving Architecture
- **CSS serving**: Custom `serve_css()` method in `telegram_bot.py` (line ~921)
- **Path handling bug pattern**: Watch for `/static/file.css` → `static/static/file.css` duplication
- **Fix pattern**: Strip `static/` prefix before joining with `Path('static')`
- **Alternative**: Use Flask's built-in static serving instead of custom handler

### CSS Architecture (Updated September 14, 2025)
- **Shared styles** → `/static/shared.css` (Key Points formatting, future common styles)
- **Dashboard-specific** → `dashboard_v3_template.html` inline `<style>` (waveform, layout offsets)  
- **Report-specific** → `templates/report_v2.html` inline `<style>` (iOS safe areas, audio controls)
- **⚠️ CRITICAL**: When adding new common styles, use `/static/shared.css` to avoid duplication

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

#### Multi-Category Subcategory System (Session 1)
- ✅ **Dashboard Cards**: Fixed extractCatsAndSubcats() in dashboard_v3.js to show subcategories for ALL categories
- ✅ **Individual Report Pages**: Added subcategory display to report_v2.html template  
- ✅ **Backend Enhancement**: Modified to_report_v2_dict() to extract subcategory_pairs
- ✅ **Template Integration**: Added purple subcategory badges between Categories and Key Topics sections
- ✅ **Grid View Fix**: Added missing extractCatsAndSubcats() call to createGridCard() function

#### Channel Filtering & UI Improvements (Session 2)
- ✅ **Channel Filter Sidebar**: Added between Categories and Content Type with All/Clear buttons
- ✅ **Clickable Channel Names**: Both list and grid cards have clickable channel filter buttons
- ✅ **Backend API Support**: Added channel parameter to /api/filters and /api/reports endpoints
- ✅ **Database Integration**: Extended SQLiteContentIndex with channel filtering and facet generation  
- ✅ **Sort Section Cleanup**: Reorganized to show only "Recently Added" and "Video Newest" by default
- ✅ **Show More Consistency**: Applied show more pattern to additional sort options

#### AI Processing Enhancement (NAS Component)
- ✅ **Multi-Category Prompt**: Enhanced AI categorization prompt to encourage multiple categories
- ✅ **Better Instructions**: Changed from "Choose 1-3 categories" to "Choose the 1-3 BEST categories that pertain to this summary"
- ✅ **Preference for Multiple**: Added "When content covers multiple distinct areas, PREFER using multiple categories"

**Last Safe Commit**: 5927206 (September 13, 2025) - Channel filtering and sort reorganization complete

## Development Workflow & Architecture Deep Dive

### 🚨 CRITICAL: Git Workflow & Repository Separation
```bash
# ALWAYS work from the correct directory 
cd /Users/markdarby/projects/YTV2-Dashboard

# This is the Dashboard component that deploys to Render
# The NAS component is at /Volumes/Docker/YTV2/ (separate git repo)

# Standard workflow:
git add [specific files]
git commit -m "message"  
git push origin main  # Triggers automatic Render deployment
```

**🚨 CRITICAL WARNING - NEVER PUSH FROM NAS TO RENDER:**
- **NEVER** run git commands from `/Volumes/Docker/YTV2/` directory
- **NEVER** push changes from the NAS component to the Dashboard repository
- The NAS component (`/Volumes/Docker/YTV2/`) is a separate git repository
- Only the Dashboard component (`/Users/markdarby/projects/YTV2-Dashboard/`) should deploy to Render
- If you accidentally work in the NAS directory, copy files to Dashboard directory before committing

#### 🚨 CRITICAL: File Location Clarification (PostgreSQL Migration)
**During PostgreSQL migration, there are TWO `telegram_bot.py` files - DO NOT MIX THEM UP:**

- **NAS Side**: `/Users/markdarby/projects/YTV_temp_NAS_files/telegram_bot.py`
  - Telegram bot interface, YouTube processing, summary creation
  - Works with `youtube_summarizer.py` for AI processing
  - Will be modified for T-Y020A (dual-sync) to SEND data to Render
  - Modified files uploaded manually to NAS via ASUSTOR web portal

- **Render Side**: `/Users/markdarby/projects/YTV2-Dashboard/telegram_bot.py`
  - **Dashboard HTTP server** (NOT Telegram bot despite filename!)
  - Serves web interface, handles API endpoints, audio streaming
  - Modified for T-Y020C (ingest endpoints) to RECEIVE data from NAS
  - Deployed automatically via git push to Render

**Data Flow**: NAS `telegram_bot.py` → POST data → Render `telegram_bot.py` → PostgreSQL

### Core Data Flow Architecture

#### 1. SQLite Database Schema (Critical for Understanding)
```sql
-- Core content table 
CREATE TABLE content (
    video_id TEXT PRIMARY KEY,
    title TEXT,
    channel_name TEXT,  -- ⭐ NEW: Used for channel filtering
    category TEXT,      -- JSON array: ["AI Software Development", "Technology"] 
    subcategory TEXT,   -- Legacy single string
    analysis TEXT,      -- ⭐ JSON: {categories: [{category: "X", subcategories: ["Y"]}]}
    content_type TEXT,  -- Tutorial, Review, Discussion, etc.
    complexity_level TEXT, -- Beginner, Intermediate, Advanced
    language TEXT,
    -- ... other fields
);
```

#### 2. Multi-Category Data Format (Essential Understanding)
```json
// Rich format (NEW) - stored in analysis.categories
{
  "categories": [
    {
      "category": "AI Software Development", 
      "subcategories": ["Security & Safety", "Testing"]
    },
    {
      "category": "Technology",
      "subcategories": ["Tech Reviews"]  
    }
  ]
}

// Legacy format (OLD) - still supported for backwards compatibility  
{
  "category": ["AI Software Development", "Technology"],  // Array in category field
  "subcategory": "Security & Safety"  // Single string
}
```

#### 3. Frontend Data Processing (Critical Function)
```javascript
// dashboard_v3.js - extractCatsAndSubcats() function
// This function handles BOTH rich and legacy formats
// Returns: { categories, subcats, subcatPairs }
// subcatPairs format: [["AI Software Development", "Security & Safety"]]
```

### API Endpoints & Data Flow

#### Key API Endpoints
```bash
GET /api/filters              # Returns available filter options with counts
GET /api/reports?category=X&channel=Y&page=1&size=12  # Filtered reports
GET /<stem>.json?v=2          # Individual report data
POST /api/upload-database     # NAS sync endpoint  
```

#### Filter Parameter Support
- `category[]`: Multiple categories (e.g., ?category=Technology&category=Business)
- `channel[]`: Multiple channels (e.g., ?channel=WorldofAI&channel=TechReview)  
- `content_type[]`: Tutorial, Review, Discussion, etc.
- `complexity[]`: Beginner, Intermediate, Advanced
- `language[]`: en, fr, etc.
- `has_audio`: true/false
- `sort`: added_desc (default), video_newest, title_az, etc.

### Interactive Features Implementation

#### 1. Clickable Filter Chips  
```html
<!-- Channel name becomes clickable filter button -->
<button class="hover:text-audio-600" 
        data-filter-chip="channel" 
        data-value="WorldofAI" 
        title="Filter by WorldofAI">
  WorldofAI
</button>
```

#### 2. Show More Toggle Pattern
```javascript
// Used for Categories, Channels, Content Types, Sort options
const toggle = document.getElementById('toggleMoreChannels');
const showMore = document.getElementById('showMoreChannels');
toggle.addEventListener('click', () => {
    const isHidden = showMore.classList.contains('hidden');
    showMore.classList.toggle('hidden');
    toggle.textContent = isHidden ? 'Show less' : 'Show more';
});
```

#### 3. Filter State Management
```javascript
// Filters are managed in this.currentFilters object
// Updated via this.computeFiltersFromDOM() 
// Applied via this.loadContent()
```

### Debugging & Troubleshooting Guide

#### Common Issues & Solutions
1. **"subcatPairs is not defined" error**: 
   - Missing `extractCatsAndSubcats()` call in card creation functions
   - Check both `createContentCard()` and `createGridCard()`

2. **Filters not working**:
   - Check that SQLiteContentIndex supports the filter parameter
   - Verify API endpoint includes the filter in allowed parameters
   - Ensure frontend sends correct parameter names

3. **Template not loading**:
   - Verify `dashboard_v3_template.html` is being served
   - Check that JavaScript loads `dashboard_v3.js` (not dashboard.js)

4. **Empty data on Render**:  
   - Database may not be synced from NAS component
   - Check `/api/reports?size=1` endpoint for data
   - Verify NAS sync process is working

#### Debug Commands  
```bash  
# Check template being used
grep -r "dashboard_v3_template" telegram_bot.py

# Check JavaScript file loaded
grep "dashboard.*js" dashboard_v3_template.html

# Test API endpoints
curl "https://ytv2-vy9k.onrender.com/api/filters" | jq .
curl "https://ytv2-vy9k.onrender.com/api/reports?size=1" | jq .

# Check database locally (if available)
sqlite3 ytv2_content.db "SELECT COUNT(*) FROM content;"
sqlite3 ytv2_content.db "SELECT DISTINCT channel_name FROM content LIMIT 10;"
```

### Performance & Optimization Notes

- **Database Indexing**: Indexes on `video_id`, `indexed_at`, `channel_name`  
- **API Caching**: Filters API cached for 60 seconds
- **Frontend Optimizations**: Debounced search (500ms), efficient DOM updates
- **Audio Streaming**: Progressive loading, media metadata optimization

## Advanced Filtering System & Clickable Chips (Updated September 13, 2025)

### Clickable Filter Chips Implementation

**How It Works**: Cards display clickable channel names, category chips, and subcategory chips that automatically apply filters when clicked.

#### Channel Filter Chips
```html
<button data-filter-chip="channel" data-filter-value="WorldofAI">WorldofAI</button>
```
- **Location**: In both list and grid card channel names
- **Behavior**: Only clears other channel filters, preserves categories
- **Implementation**: `dashboard_v3.js` lines ~1490, ~1588

#### Category Filter Chips  
```html
<button data-filter-chip="category" data-filter-value="Technology">Technology</button>
```
- **Generated by**: `renderChip()` method in `dashboard_v3.js`
- **Behavior**: Clears all category/subcategory filters, preserves channels
- **Color**: Audio theme colors (`bg-audio-100`)

#### Subcategory Filter Chips
```html
<button data-filter-chip="subcategory" data-filter-value="AI Software Development" data-parent-category="Technology">AI Software Development</button>
```
- **Generated by**: `renderChip(sc, 'subcategory', false, parent)` 
- **Behavior**: Clears all category/subcategory filters, selects subcategory + parent category, preserves channels
- **Color**: Blue theme (`bg-blue-100`)
- **Parent tracking**: Uses `data-parent-category` attribute

### Smart Filter Clearing Logic (`applyFilterFromChip`)

**Critical Method**: `dashboard_v3.js:2315` - Controls what gets cleared when filter chips are clicked

```javascript
applyFilterFromChip(filterType, filterValue, parentCategory = null) {
    // Smart clearing based on filter type:
    if (filterType === 'channel') {
        // Only clear other channels (preserve categories, etc.)
        document.querySelectorAll('input[data-filter="channel"]').forEach(cb => cb.checked = false);
    } else if (filterType === 'category' || filterType === 'subcategory') {
        // Clear all category-related filters (preserve channels, etc.)
        document.querySelectorAll('input[data-filter="category"], input[data-filter="subcategory"]').forEach(cb => cb.checked = false);
    } else {
        // Other types only clear their own type
        document.querySelectorAll(`input[data-filter="${filterType}"]`).forEach(cb => cb.checked = false);
    }
    // Then select the clicked filter...
}
```

**Key Insight**: Never use `clearAllFilters()` - it nukes everything. Use selective clearing instead.

### Filter Interaction Rules

1. **Channel Clicks**: Keep categories selected, change channel selection
2. **Category Clicks**: Keep channels selected, change category selection  
3. **Subcategory Clicks**: Keep channels selected, select subcategory + parent category
4. **Independent Filtering**: Categories + Channels work together (intersection, not union)
5. **Empty Filter Behavior**: No categories OR no channels = no results shown

### Database Management & Live Updates

#### Downloading Current Database from Render
```bash
# Download current live database
curl -H "Authorization: Bearer 5397064f171ce0db328066d2ac52022b" \
     "https://ytv2-vy9k.onrender.com/api/download-database" \
     -o ytv2_content.db
```

#### Database Location on Render
- **Persistent Storage**: `/app/data/ytv2_content.db` (1GB disk mounted)
- **Download Endpoint**: `/api/download-database` (GET, requires auth)
- **Upload Endpoint**: `/api/upload-database` (POST, requires auth)

#### Updating Database Records
```bash
# 1. Download current database
curl -H "Authorization: Bearer [SECRET]" [URL]/api/download-database -o ytv2_content.db

# 2. Make changes with SQLite
sqlite3 ytv2_content.db "UPDATE content SET channel_name = 'New Name' WHERE title LIKE '%pattern%';"

# 3. Sync back using NAS script  
cp ytv2_content.db /Volumes/Docker/YTV2/data/ytv2_content.db
cd /Volumes/Docker/YTV2
SYNC_SECRET=[SECRET] python sync_sqlite_db.py
```

#### Database Schema (Channel Updates)
```sql
-- Core fields for filtering
channel_name TEXT,     -- Used for channel filtering
category TEXT,         -- JSON array of categories  
analysis TEXT,         -- JSON with categories: [{category, subcategories}]
language TEXT,         -- 'en', 'fr', etc.
content_type TEXT,     -- Tutorial, Review, Discussion
complexity_level TEXT  -- Beginner, Intermediate, Advanced
```

### Recent Fixes & Architecture Updates (September 13, 2025)

#### Channel Filtering System ✅
- **Problem**: Channel filtering showed all cards when no channels selected
- **Fix**: Added independent channel requirement logic in `loadContent()`
- **Result**: No channels selected = no cards shown (consistent with categories)

#### Clickable Filter Chips ✅  
- **Problem**: All chips cleared ALL filters instead of being selective
- **Fix**: Implemented smart clearing in `applyFilterFromChip()` 
- **Result**: Chips preserve other filter types, work independently

#### Database Download/Upload System ✅
- **Added**: `/api/download-database` GET endpoint with auth
- **Purpose**: Enable live database updates without NAS access
- **Security**: Requires `SYNC_SECRET` bearer token authentication

#### Channel Data Cleanup ✅
- **Fixed**: 6 "Unknown" channel records updated with correct names:
  - "ShadCN Dropped Something..." → AI LABS
  - "Amazfit T Rex 3 Pro..." → The Quantified Scientist  
  - "How Good Is Grok 42..." → Ray Amjad
  - "Why Do Watches Have Jewels..." → Talking Time
  - "Why Do The French Always Complain..." → Français avec Nelly (+ lang: fr)
  - "That Time It Rained..." → PBS Eons

#### UI Polish ✅
- **Filter Spacing**: Changed from `space-y-2` to `space-y-1` for tighter layout
- **No Results Logic**: Improved messaging for empty filter states

### Critical Debugging Commands

```bash
# Check filter chip data attributes
grep -n "data-filter-chip\|data-filter-value" static/dashboard_v3.js

# Test filter API
curl "https://ytv2-vy9k.onrender.com/api/filters" | jq .

# Check database content  
sqlite3 ytv2_content.db "SELECT channel_name, COUNT(*) FROM content GROUP BY channel_name ORDER BY COUNT(*) DESC;"

# Monitor filter clicks (browser console)
# Look for: "🔍 Filter chip clicked:" debug logs
```

### Common Issues & Solutions

**Filter Chips Not Working**:
- ❌ Check `data-filter-value` vs `data-value` (must be `data-filter-value`)
- ❌ Check if using `clearAllFilters()` (use selective clearing instead)
- ✅ Verify event handler binding in `bindFilterChipHandlers()`

**Database Updates Not Showing**:  
- ✅ Download current database first (don't use cached/NAS copy)
- ✅ Use correct sync script path: `/Volumes/Docker/YTV2/sync_sqlite_db.py`
- ✅ Ensure database copied to `data/ytv2_content.db` before sync

**Filter Logic Conflicts**:
- ✅ Categories + Channels = intersection (both must be satisfied)
- ✅ No categories OR no channels = no results (independent requirements)
- ✅ Filter chips preserve other filter types (don't clear unrelated filters)

### Key Points Formatting System (September 14, 2025)

**Smart Content Formatting**: Detects structured markers (`**Main topic:**`, `**Key points:**`, `**Takeaway:**`) and renders clean visual hierarchy:
- **Before**: `• **Main topic:** Topic text **Key points:** - Bullet 1 **Takeaway:** Summary` (ugly labels)
- **After**: **Topic text** as heading + clean bullet list + bold takeaway (no labels)

**Implementation Locations**:
- Frontend formatter: `dashboard_v3.js:2835` formatKeyPoints()
- Backend formatter: `telegram_bot.py:395` format_key_points()  
- Styling: `static/shared.css` `.kp-heading`, `.kp-list`, `.kp-takeaway`, `.kp-fallback`
- Security whitelist: `telegram_bot.py:39` ALLOWED_TAGS + ALLOWED_ATTRS

#### 🚨 CRITICAL: Robust Marker Processing Patterns
**Lessons learned from September 14, 2025 debugging:**
- **Dual filtering required**: Extract markers early AND filter from bullet processing
- **Unicode bullet support**: Use `[•\-–—]` pattern for all bullet types (regular dash, en-dash, em-dash)
- **Belt-and-suspenders approach**: Strip marker lines with regex BEFORE processing bullets
- **Precompiled regex**: Use compiled patterns for performance and consistency
- **Edge case handling**: Partial markers like "• **T" must be filtered out during bullet processing
- **Identical logic**: Backend Python and frontend JavaScript must use identical regex patterns

**Regex Patterns Used:**
```javascript
// Takeaway extraction
/\*\*Takeaway:\*\*\s*(.+?)(?=\*\*|$)/is

// Takeaway line stripping  
/^\s*(?:[•\-–—]\s*)?\*\*takeaway:\*\*.*$/gmi

// Takeaway bullet filtering
/^\s*(?:[•\-–—]\s*)?\*\*takeaway:\*\*/i
```

**Fallback Behavior**: Content without markers uses normal paragraph formatting

**Last Updated**: September 14, 2025 - Robust takeaway formatting with OpenAI feedback implemented.