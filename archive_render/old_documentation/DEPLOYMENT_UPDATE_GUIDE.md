# 🚀 YTV2 Deployment Update Guide

## Web Server & NGROK Integration Updates

This guide covers updating your NAS deployment with the new HTML export and web server functionality, plus NGROK integration for worldwide access.

## 📋 Files to Update on Your NAS

### 1. Core Application Files
Copy these files from your local YTV2 project to `/volume1/Docker/YTV2/` on your NAS:

```bash
# Updated core files
server.py (formerly telegram_bot.py)          # ✅ Web server integration added
docker-compose.simple.yml # ✅ Port 8080 exposed
```

### 2. Optional Files (if you want the latest)
```bash
youtube_summarizer.py    # ✅ Latest prompt improvements
prepare_nas_deployment.sh # ✅ Deployment helper script
DEPLOYMENT_UPDATE_GUIDE.md # ✅ This guide
```

## 🔧 Environment Configuration Updates

### Update `.env.nas` File

Add this new environment variable to your `.env.nas` file:

```bash
# Web Server Configuration
WEB_BASE_URL=localhost:8080
```

**For NGROK (recommended):** Update to your NGROK URL after setting up the tunnel:
```bash
# Web Server Configuration  
WEB_BASE_URL=https://chief-inspired-lab.ngrok-free.app
```

## 🌍 NGROK Setup for Worldwide Access

### Step 1: Set Up NGROK on Your Mac

1. **Open MKPY**: Run `mkpy` in terminal
2. **Select Option 30**: "YouTube Summarizer reports (port 8080)"
3. **Confirm**: Type `y` to start the tunnel
4. **Note the URL**: MKPY will show you the tunnel URL (e.g., `https://chief-inspired-lab.ngrok-free.app`)

### Step 2: Update Your NAS Configuration

1. **SSH/Edit .env.nas** on your NAS:
   ```bash
   WEB_BASE_URL=https://chief-inspired-lab.ngrok-free.app
   ```

2. **Restart Container** in Portainer:
   - Go to Containers
   - Stop `youtube-summarizer-bot`
   - Start `youtube-summarizer-bot`

### Step 3: Verify Setup

1. **Generate a Summary** via Telegram bot
2. **Click "View Report"** button
3. **Report should open** in your browser accessible from anywhere!

## 📁 Manual File Update Process

### Option A: Via SMB/Network Drive
1. **Connect to NAS**: `smb://YOUR_NAS_IP/Docker/YTV2`
2. **Copy files**: Drag updated files from your local project
3. **Replace existing**: Overwrite when prompted

### Option B: Via Command Line (if you have SSH access)
```bash
# Copy to NAS (adjust IP address)
scp server.py admin@YOUR_NAS_IP:/volume1/Docker/YTV2/
scp docker-compose.simple.yml admin@YOUR_NAS_IP:/volume1/Docker/YTV2/
```

## 🔄 Restart Process in Portainer

1. **Access Portainer**: `http://YOUR_NAS_IP:9000`
2. **Go to Containers**
3. **Find**: `youtube-summarizer-bot`
4. **Actions**: Stop → Start (or click Restart)
5. **Check Logs**: Verify web server starts on port 8080

## ✅ Verification Checklist

- [ ] Files copied to NAS successfully
- [ ] `.env.nas` updated with `WEB_BASE_URL`
- [ ] Container restarted in Portainer
- [ ] Bot responds to Telegram messages
- [ ] "View Report" button appears in summaries
- [ ] HTML reports are accessible via the URL
- [ ] (Optional) NGROK tunnel provides worldwide access

## 🆘 Troubleshooting

### Container Won't Start
```bash
# Check logs in Portainer for errors
# Common issues:
# - Missing environment variables
# - Port conflicts
# - File permission issues
```

### Web Server Not Accessible
```bash
# Check if port 8080 is exposed in docker-compose.simple.yml:
# ports:
#   - "8080:8080"
```

### NGROK Issues
```bash
# In MKPY, check ngrok status:
# mkpy → option 31 → Show ngrok configuration
# Verify tunnel is running and pointed to port 8080
```

### HTML Reports Not Generating
```bash
# Check bot logs for errors
# Verify exports directory has write permissions
# Ensure web server started successfully
```

## 🎯 What's New

- **HTML Export**: Beautiful, responsive HTML reports
- **Web Server**: Built-in HTTP server on port 8080
- **View Report Button**: Direct links from Telegram
- **Auto-Cleanup**: Reports expire after 24 hours
- **NGROK Support**: Worldwide access via MKPY integration
- **Mobile Friendly**: Reports optimized for mobile viewing

## 💡 Pro Tips

1. **Keep NGROK Running**: Use MKPY's auto-start feature for persistent tunnels
2. **Bookmark Reports**: Save important analysis for later reference  
3. **Share Safely**: NGROK URLs can be shared with colleagues
4. **Monitor Logs**: Check container logs if something seems off
5. **Regular Updates**: Keep your local project synced for latest features

## 🔗 Related Documentation

- `ASUSTOR_DEPLOYMENT.md` - Original deployment guide
- `SECURITY_CONSIDERATIONS.md` - Security best practices
- MKPY NGROK documentation - Run `mkpy` → option 31 for configuration help

---

**Questions?** Check container logs in Portainer or refer to the troubleshooting section above.
