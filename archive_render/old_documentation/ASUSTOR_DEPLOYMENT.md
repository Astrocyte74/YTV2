# ASUSTOR NAS + Portainer Deployment Guide

This guide provides step-by-step instructions for deploying the YouTube Summarizer Telegram Bot on an ASUSTOR NAS using Portainer.

## Prerequisites

### ASUSTOR NAS Requirements
- ASUSTOR NAS with ARM64 or x86_64 architecture
- ADM 4.0 or later
- At least 2GB RAM (4GB+ recommended)
- 10GB+ free storage space
- Internet connection

### External Services Setup
1. **Telegram Bot Token**: Create a bot via [@BotFather](https://t.me/botfather)
2. **LLM API Key**: Choose one:
   - OpenAI API key (recommended)
   - Anthropic Claude API key
   - OpenRouter API key
3. **Admin User ID**: Get your Telegram user ID from [@userinfobot](https://t.me/userinfobot)

## Step 1: Install Docker and Portainer on ASUSTOR

### 1.1 Install Docker
1. Open **App Central** on your ASUSTOR NAS
2. Search for "**Docker CE**"
3. Install **Docker CE** (Community Edition)
4. Wait for installation to complete
5. Enable Docker service in **Services** > **Docker**

### 1.2 Install Portainer
1. In App Central, search for "**Portainer CE**"
2. Install **Portainer CE**
3. Launch Portainer from App Central or navigate to `http://your-nas-ip:9000`
4. Create an admin account when prompted
5. Select "Docker" as the environment to manage

## Step 2: Prepare Deployment Files

### 2.1 Create Project Directory
1. Access your NAS via **File Explorer** or SSH
2. Create directory: `/volume1/docker/youtube-summarizer-bot/`
3. Upload the following files to this directory:
   - `docker-compose.yml`
   - `Dockerfile`
   - All Python source files
   - `requirements.txt`

### 2.2 Create Environment File
1. Copy `.env.nas.template` to `.env.nas`
2. Edit `.env.nas` with your actual values:

```bash
# Required settings
TELEGRAM_BOT_TOKEN=1234567890:ABCDEF1234567890abcdef1234567890ABC
TELEGRAM_ADMIN_USER_ID=123456789
OPENAI_API_KEY=sk-1234567890abcdef...

# Optional settings
TZ=America/New_York
LLM_PROVIDER=openai
LLM_MODEL=gpt-4
```

## Step 3: Deploy via Portainer

### 3.1 Access Portainer
1. Open web browser and go to `http://your-nas-ip:9000`
2. Login with your Portainer admin credentials
3. Select your Docker environment

### 3.2 Create the Stack
1. Click **"Stacks"** in the left sidebar
2. Click **"+ Add stack"**
3. Enter stack name: `youtube-summarizer-bot`

### 3.3 Upload Docker Compose
1. Select **"Upload"** method
2. Upload your `docker-compose.yml` file
3. Or copy/paste the contents into the editor

### 3.4 Configure Environment Variables
1. Scroll down to **"Environment variables"**
2. Click **"Load variables from .env file"**
3. Upload your `.env.nas` file
4. Review all variables are loaded correctly

### 3.5 Deploy the Stack
1. Click **"Deploy the stack"**
2. Wait for deployment to complete
3. Check the **"Containers"** section to verify the bot is running

## Step 4: Build the Docker Image

### 4.1 Option A: Build via Portainer (Recommended)
The stack will automatically build the image when deployed.

### 4.2 Option B: Build via SSH (Advanced)
```bash
# SSH into your NAS
ssh admin@your-nas-ip

# Navigate to project directory
cd /volume1/docker/youtube-summarizer-bot/

# Build the image
docker build -t youtube-summarizer-bot:latest .
```

## Step 5: Verify Deployment

### 5.1 Check Container Status
1. In Portainer, go to **"Containers"**
2. Verify `youtube-summarizer-bot` is **"Running"**
3. Click on container name to view details

### 5.2 View Logs
1. Click on the container name
2. Select **"Logs"** tab
3. Look for successful startup messages:
   ```
   INFO - Bot started successfully
   INFO - Listening for messages...
   ```

### 5.3 Test the Bot
1. Open Telegram and find your bot
2. Send `/start` command
3. Try sending a YouTube URL
4. Verify the bot responds with a summary

## Step 6: Configure Automatic Startup

### 6.1 ASUSTOR Boot Sequence
1. Go to **ADM** > **Services** > **Auto Run**
2. Enable **Docker** service
3. Enable **Portainer** service

### 6.2 Portainer Auto-Start
The stack is configured with `restart: unless-stopped` policy, so it will:
- Start automatically when Docker starts
- Restart if the container crashes
- Not restart if manually stopped

## Step 7: Monitoring and Maintenance

### 7.1 Resource Monitoring
1. In Portainer, select your container
2. Click **"Stats"** tab
3. Monitor CPU, RAM, and network usage

### 7.2 View Logs
```bash
# Via Portainer: Container > Logs tab
# Via SSH:
docker logs youtube-summarizer-bot
```

### 7.3 Update the Bot
1. Stop the stack in Portainer
2. Upload new source files
3. Rebuild and redeploy the stack

### 7.4 Backup Configuration
Backup these important directories:
- `/volume1/docker/youtube-summarizer-bot/` (source code)
- Docker volumes (downloads, cache, logs)

## Troubleshooting

### Common Issues

#### Container Won't Start
1. Check environment variables in `.env.nas`
2. Verify all required API keys are valid
3. Check container logs for error messages

#### Bot Not Responding
1. Verify Telegram bot token is correct
2. Check internet connectivity on NAS
3. Confirm admin user ID is correct

#### Permission Errors
1. Ensure Docker service is running
2. Check file permissions in project directory
3. Verify user `1000:1000` exists or adjust in docker-compose.yml

#### Out of Memory
1. Increase NAS RAM if possible
2. Reduce resource limits in docker-compose.yml
3. Monitor memory usage in Portainer

### Useful Commands

```bash
# View container status
docker ps

# View logs
docker logs youtube-summarizer-bot

# Restart container
docker restart youtube-summarizer-bot

# Update environment variables
docker-compose up -d

# Clean up unused images
docker system prune
```

### Performance Optimization

#### For Low-RAM NAS (2GB)
```yaml
deploy:
  resources:
    limits:
      cpus: '1.0'
      memory: 1G
    reservations:
      cpus: '0.25'
      memory: 256M
```

#### For High-Performance NAS (8GB+)
```yaml
deploy:
  resources:
    limits:
      cpus: '4.0'
      memory: 4G
    reservations:
      cpus: '1.0'
      memory: 1G
```

## Security Best Practices

1. **Environment Variables**: Never commit API keys to version control
2. **Network Access**: Bot only needs outbound HTTPS (443) access
3. **User Permissions**: Container runs as non-root user (1000:1000)
4. **Regular Updates**: Keep base image and dependencies updated
5. **Log Rotation**: Configured automatically with 10MB max size
6. **Read-Only Filesystem**: Enabled where possible for security

## Support

For issues specific to:
- **ASUSTOR NAS**: Check ASUSTOR documentation and forums
- **Portainer**: Visit [Portainer documentation](https://docs.portainer.io/)
- **Bot Functionality**: Check application logs and verify API keys
- **Docker Issues**: Consult Docker documentation

Remember to check the container logs first when troubleshooting issues.