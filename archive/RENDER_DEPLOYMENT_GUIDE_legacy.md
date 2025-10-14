# (Legacy) YTV2 YouTube Summarizer - RENDER Deployment Guide

This guide will help you deploy your YTV2 YouTube Summarizer to RENDER.com.

> Archived. See docs/DEPLOY_RENDER.md for the current dashboard deployment guide.

1. A RENDER.com account (free tier available)
2. A GitHub repository with your YTV2 code
3. API keys for AI services (OpenAI, Anthropic, or OpenRouter)
4. A Telegram bot token and user ID

## Step 1: Prepare Your Repository

1. Push your YTV2 code to a GitHub repository
2. Update the `render.yaml` file to point to your repository:
   ```yaml
   repo: https://github.com/YOUR_USERNAME/YOUR_REPO_NAME
   branch: main
   ```

## Step 2: Deploy to RENDER

### Option A: Using render.yaml (Blueprint)
1. Go to RENDER dashboard: https://dashboard.render.com
2. Click "New" → "Blueprint"
3. Connect your GitHub repository
4. RENDER will automatically detect the `render.yaml` file
5. Review the configuration and click "Apply"

### Option B: Manual Deployment
1. Go to RENDER dashboard: https://dashboard.render.com
2. Click "New" → "Web Service"
3. Connect your GitHub repository
4. Configure the following settings:
   - **Name**: `ytv2-telegram-bot`
   - **Environment**: `Docker`
   - **Branch**: `main`
   - **Dockerfile Path**: `./Dockerfile`
   - **Health Check Path**: `/health`

## Step 3: Configure Environment Variables

In the RENDER dashboard, go to your service → Environment tab and add:

### Required API Keys
```bash
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_USER_ID=your_telegram_user_id_here

# Choose one or more AI providers:
OPENAI_API_KEY=your_openai_key_here
ANTHROPIC_API_KEY=your_anthropic_key_here
OPENROUTER_API_KEY=your_openrouter_key_here
```

### Optional Configuration
```bash
LLM_SHORTLIST=fast
DEFAULT_SUMMARY_TYPE=comprehensive
MAX_TRANSCRIPT_LENGTH=50000
HTML_REPORT_RETENTION_HOURS=168
EXPORT_ENABLED=true
WEB_DASHBOARD_ENABLED=true
DEBUG_MODE=false
```

### Auto-configured Variables
These are set automatically by RENDER:
- `WEB_PORT=10000`
- `WEB_BASE_URL` (auto-generated from your service URL)
- `PYTHONUNBUFFERED=1`
- `PYTHONDONTWRITEBYTECODE=1`

## Step 4: Add Persistent Storage

1. In your service settings, go to the "Disks" tab
2. Add a disk with:
   - **Name**: `ytv2-storage`
   - **Mount Path**: `/app/data`
   - **Size**: `2GB` (or more if needed)

## Step 5: Deploy and Test

1. Click "Deploy" to start the deployment
2. Monitor the build logs for any errors
3. Once deployed, test your service:
   - Health check: `https://your-service-url.onrender.com/health`
   - Status check: `https://your-service-url.onrender.com/status`
   - Dashboard: `https://your-service-url.onrender.com/`

## Step 6: Configure Your Telegram Bot

Update your Telegram bot with the new webhook URL:
```
https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook?url=https://your-service-url.onrender.com/webhook
```

## Features Available

- **Telegram Bot**: Send YouTube URLs to get AI-powered summaries
- **Web Dashboard**: View and manage your video summaries at your service URL
- **Multiple AI Providers**: Support for OpenAI, Anthropic, and OpenRouter
- **Export Options**: JSON, HTML, PDF, and Markdown exports
- **Persistent Storage**: Reports and cache stored on persistent disk
- **Health Monitoring**: Built-in health checks for RENDER monitoring

## Troubleshooting

### Common Issues

1. **Build Fails**: Check the build logs in RENDER dashboard
2. **Health Check Fails**: Verify the `/health` endpoint is accessible
3. **Telegram Bot Not Responding**: Check environment variables and webhook URL
4. **AI Summarization Fails**: Verify API keys are correct and have sufficient credits

### Viewing Logs
- Go to your service in RENDER dashboard
- Click on "Logs" tab to view real-time application logs
- Use these logs to debug any issues

### Scaling
- RENDER free tier has limitations (750 hours/month)
- For production use, consider upgrading to a paid plan
- The app supports vertical scaling (more CPU/memory) automatically

## Cost Optimization

- **Free Tier**: Use RENDER's free tier (sleeps after 15 minutes of inactivity)
- **Paid Plans**: Start at $7/month for always-on services
- **Storage**: Additional disk space costs extra
- **Bandwidth**: No limits on RENDER (unlike NGROK)

## Security Notes

- All environment variables are encrypted in RENDER
- HTTPS is provided automatically with SSL certificates
- The application runs in a sandboxed Docker container
- No sensitive data is logged or exposed in the dashboard

## Next Steps

1. Monitor your service performance in RENDER dashboard
2. Set up monitoring alerts (optional)
3. Consider adding a custom domain (paid feature)
4. Scale resources as needed based on usage
