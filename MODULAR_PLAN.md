# 🎯 YTV2 Modular Architecture Implementation Plan

**Status**: In Progress  
**Started**: 2025-09-03  
**Goal**: Replace monolithic telegram_bot.py with clean modular architecture

## ✅ COMPLETED
- [x] Clean telegram_bot.py with pure Python (no embedded HTML/CSS)
- [x] Beautiful 2025 glass morphism dashboard working
- [x] Template system (dashboard_template.html, dashboard.css, dashboard.js)
- [x] Filter drawer styling fixed
- [x] Reports loading from exports folder
- [x] HTTP server with CSS/JS serving

## 📋 APPROVED ARCHITECTURE

```
YTV2/
├── telegram_bot.py          # Main orchestrator (current clean file)
├── config/
│   ├── settings.json        # User-editable settings
│   ├── prompts.json         # Customizable AI prompts  
│   └── voices.json          # TTS voice configurations
├── modules/
│   ├── telegram_handler.py  # Telegram bot logic
│   ├── youtube_processor.py # YouTube download/transcript
│   ├── report_generator.py  # HTML/JSON report creation
│   └── audio_handler.py     # TTS and mini-player logic
├── data/
│   └── reports/             # JSON storage for reports
│       └── {video_id}.json  # Individual report data
├── templates/               # HTML templates (existing)
├── static/                  # CSS/JS files (existing)  
└── exports/                 # Legacy HTML reports (existing)
```

## 🎯 NEXT IMPLEMENTATION STEPS

### Phase 1: Directory Structure
- [ ] Create config/, modules/, data/reports/ directories
- [ ] Create default JSON config files
- [ ] Document config options

### Phase 2: Extract Core Functionality  
- [ ] Extract `YouTubeTelegramBot` class → `modules/telegram_handler.py`
- [ ] Extract YouTube processing → `modules/youtube_processor.py`
- [ ] Create JSON report generator → `modules/report_generator.py`
- [ ] Update main telegram_bot.py to orchestrate

### Phase 3: Enhanced Features
- [ ] Fix mini-player functionality in dashboard.js
- [ ] Add audio/TTS handler → `modules/audio_handler.py`
- [ ] Update dashboard to read JSON reports dynamically
- [ ] Implement user customization through JSON configs

### Phase 4: Testing & Integration
- [ ] Test Telegram bot functionality
- [ ] Test report generation
- [ ] Test dashboard with JSON reports
- [ ] Performance optimization

## 🔧 KEY MISSING FEATURES FROM OLD telegram_bot.py

### Critical Missing:
1. **Telegram Bot Handlers** (`YouTubeTelegramBot` class)
   - Message handling for YouTube URLs
   - User authorization
   - Model switching interface
   - Status updates

2. **YouTube Processing** 
   - Video transcript extraction
   - Metadata collection
   - Integration with YouTubeSummarizer

3. **Report Generation**
   - HTML report creation (currently hardcoded)
   - JSON report storage (new)
   - File management and cleanup

4. **Mini-Player Backend**
   - Audio file serving
   - Playlist management
   - TTS integration

## 📊 JSON REPORT STRUCTURE (New)
```json
{
  "video_id": "abc123",
  "metadata": {
    "title": "Video Title",
    "channel": "Channel Name", 
    "duration": 3600,
    "upload_date": "2024-01-01",
    "thumbnail_url": "https://..."
  },
  "summary": {
    "type": "comprehensive",
    "content": "Summary text...",
    "key_points": ["point1", "point2"],
    "model_used": "gpt-4"
  },
  "transcript": {
    "source": "youtube-api",
    "text": "Full transcript...",
    "segments": []
  },
  "audio": {
    "tts_file": "path/to/audio.mp3", 
    "voice": "en-US-Standard-A"
  },
  "created_at": "2024-01-01T12:00:00Z"
}
```

## 🎨 UI IMPROVEMENTS NEEDED
- [ ] Mini-player controls (currently placeholder)
- [ ] Filter drawer Apply/Clear buttons functionality
- [ ] Report card click handlers
- [ ] Search functionality
- [ ] Delete functionality

## 📝 COMMIT STRATEGY
- Commit after each major module extraction
- Document progress in commit messages
- Keep MODULAR_PLAN.md updated

## 🤖 SUBAGENT USAGE
- **file-refactorer**: For extracting classes from monolithic file
- **project-organizer**: For directory structure decisions
- **code-finder**: For locating specific functionality to extract

---

**Last Updated**: 2025-09-03  
**Context Length**: This plan survives auto-compact