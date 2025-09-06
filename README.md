# YTV2-Dashboard - Web Interface & Audio Player

**The dashboard component** of the YTV2 hybrid architecture. This deploys to Render and serves the web interface with audio playback for YouTube video summaries.

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/Astrocyte74/YTV2)

## 🏗️ Architecture Overview

YTV2 uses a **hybrid architecture** with separated concerns:

- **🔧 NAS Component**: YouTube processing + Telegram bot (runs on your NAS)
- **🌐 Dashboard Component** (This project): Web interface + audio playback (deployed to Render)

### How It Works

1. **🔧 NAS Processing** generates reports and audio files
2. **🔄 Auto-Sync** uploads content to this Dashboard
3. **🌐 Web Interface** serves reports with rich formatting  
4. **🎵 Audio Playback** streams audio files with metadata
5. **📱 Responsive Design** works on desktop and mobile
6. **🔗 Public Access** shareable URL for viewing summaries

## ✨ Features

- **🌐 Beautiful Web Dashboard**: Glass morphism UI with responsive design
- **🎵 Integrated Audio Player**: Play generated audio with video metadata
- **📊 Rich Report Display**: Formatted JSON reports with syntax highlighting
- **🔄 Auto-Sync**: Receives content from NAS component automatically
- **📱 Mobile Responsive**: Works perfectly on phones and tablets
- **🔗 Public Sharing**: Share dashboard URL for easy access
- **⚡ Fast Loading**: Optimized for quick report browsing
- **🔒 Secure Sync**: Authenticated uploads from NAS only

## 🚀 Quick Deploy to Render

### One-Click Deployment

1. **Fork this repository** to your GitHub account
2. **Click the Deploy to Render button** above  
3. **Configure environment variables** in Render dashboard:
   ```bash
   # Leave empty for dashboard-only mode
   TELEGRAM_BOT_TOKEN=""
   
   # Sync security (set same value on NAS)
   SYNC_SECRET=your_secure_random_string_here
   ```
4. **Deploy and get your URL!** Dashboard will be live in minutes

### Manual Render Setup

1. **Create new Web Service** on Render
2. **Connect GitHub repository**
3. **Configure build settings**:
   - **Environment**: Docker
   - **Dockerfile Path**: ./Dockerfile  
   - **Build Command**: (automatic)
   - **Start Command**: python telegram_bot.py
4. **Add environment variables** (see above)
5. **Deploy!**

## 🔧 Configuration

### Environment Variables

#### Required Settings
```bash
# Dashboard-only mode (leave Telegram token empty)
TELEGRAM_BOT_TOKEN=""

# Sync security - must match NAS configuration
SYNC_SECRET=your_secure_random_string_here
```

#### Optional Settings  
```bash
# Custom port (Render handles this automatically)
PORT=10000

# Dashboard URL (auto-configured by Render)
RENDER_DASHBOARD_URL=https://your-app.onrender.com
```

### NAS Integration Setup

Configure your NAS component to sync with this dashboard:

1. **Get your Render URL** from the Render dashboard
2. **Set NAS environment variables**:
   ```bash
   # In your NAS .env.nas file
   RENDER_DASHBOARD_URL=https://your-dashboard.onrender.com
   SYNC_SECRET=same_secret_as_dashboard_here
   ```
3. **Restart NAS bot** to begin syncing

## 📁 Project Structure

### Essential Files
```
YTV2-Dashboard/
├── telegram_bot.py          # Dashboard server (not Telegram bot!)
├── dashboard_template.html  # Main web interface
├── Dockerfile              # Render deployment configuration
├── render.yaml             # Render service configuration  
├── modules/                # Dashboard utilities
│   └── report_generator.py # JSON report handling
├── static/                 # CSS and JavaScript
│   ├── dashboard.css      # Styling and animations
│   └── dashboard.js       # Interactive functionality
├── data/                  # Synced JSON reports
└── exports/              # Synced audio files
```

### Archived Content
- `archive_render/old_*` - Previous versions and unused components

## 🔄 Usage Workflow

1. **NAS Processing** creates reports and audio
2. **Auto-Sync** uploads to Dashboard  
3. **Web Access** via Render URL shows:
   - List of all processed videos
   - Rich formatting of summaries
   - Audio playback with metadata
   - Mobile-responsive interface

## 📱 Dashboard Features

### Report Display
- **JSON formatting** with syntax highlighting
- **Metadata extraction** shows video info, duration, thumbnails
- **Summary sections** clearly organized and readable
- **Search/filter** functionality for large collections

### Audio Integration  
- **Embedded player** for each video's audio
- **Metadata display** shows title, duration, channel info
- **Playback controls** with progress tracking
- **Mobile optimization** for touch interfaces

### Interface Design
- **Glass morphism UI** with modern visual effects
- **Dark/light themes** with system preference detection
- **Responsive layout** adapts to any screen size
- **Fast loading** with optimized assets

## 🛠️ Development

### Local Testing
```bash
# Install dependencies
pip install -r requirements.txt

# Run dashboard locally  
python telegram_bot.py

# Access at http://localhost:10000
```

### File Upload Testing
```bash
# Test sync endpoint
curl -X POST http://localhost:10000/api/upload-report \
  -H "Authorization: Bearer your_sync_secret" \
  -F "file=@test_report.json"
```

## 🔒 Security

### Sync Authentication
- **Shared secret** authentication for NAS uploads
- **HTTPS only** for all Render deployments
- **No API keys** stored (dashboard-only mode)
- **Limited endpoints** only for receiving uploads

### Access Control
- **Public dashboard** (no login required for viewing)
- **Protected uploads** (only authenticated NAS can upload)  
- **No processing** (read-only for security)

## ⚡ Performance

### Optimized for Speed
- **Static serving** of reports and audio
- **Compressed assets** for faster loading
- **CDN integration** via Render
- **Minimal resource usage** (dashboard-only)

### Render Benefits
- **Global CDN** for fast worldwide access
- **Auto-scaling** handles traffic spikes  
- **HTTPS** included by default
- **Custom domains** supported

## 🚀 Deployment Options

### Render (Recommended)
- ✅ **One-click deployment** 
- ✅ **Auto-scaling and CDN**
- ✅ **HTTPS and custom domains**
- ✅ **Git-based deployments**

### Other Platforms
- **Heroku**: Similar Docker deployment
- **Railway**: One-click from GitHub
- **DigitalOcean App Platform**: Docker container support
- **AWS/GCP**: Container deployment options

## 🛠️ Troubleshooting

### Common Issues

**Dashboard not loading:**
- Check Render deployment logs
- Verify environment variables are set
- Ensure PORT is configured correctly

**NAS sync failing:**  
- Verify SYNC_SECRET matches on both sides
- Check Dashboard URL accessibility
- Monitor upload endpoint for errors

**Audio files not playing:**
- Confirm exports/ directory has content
- Check file permissions and accessibility
- Verify audio file formats are supported

### Debug Information
- **Render Logs**: Available in Render dashboard
- **Health Check**: `/health` endpoint for status
- **Sync Status**: Monitor for upload success/failures

---

**Part of YTV2 Hybrid Architecture**  
🔗 **Processing Component**: See YTV2-NAS project for video processing and Telegram bot