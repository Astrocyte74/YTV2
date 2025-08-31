# 🎥 YTV2 - AI-Powered YouTube Summarizer

AI-powered YouTube video summarizer with Telegram bot interface. Features multi-provider LLM support, transcript extraction, and web-based summary viewing.

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/Astrocyte74/YTV2)

## ✨ Features

- 🤖 **Multi-AI Provider Support**: OpenAI, Anthropic Claude, OpenRouter, and more
- 📱 **Telegram Bot Interface**: Easy-to-use bot with web-based summary viewing
- 🎵 **Audio Support**: Extracts and processes video transcripts + audio content
- 📊 **Multiple Summary Types**: Comprehensive, bullet points, key insights
- 🌐 **Web Dashboard**: Beautiful HTML reports with media player integration
- 🐳 **Docker Ready**: One-click deployment to any cloud platform

## 🚀 Quick Deploy to Render

1. **Fork this repository** to your GitHub account
2. **Click the Deploy to Render button** above
3. **Set environment variables** in Render dashboard:
   ```
   TELEGRAM_BOT_TOKEN=your_bot_token
   TELEGRAM_USER_ID=your_user_id  
   OPENAI_API_KEY=your_openai_key
   ```
4. **Deploy and enjoy!** Your bot will be live in minutes

## 📱 Local Development

### Prerequisites
- Python 3.11+
- Docker (optional)
- Telegram Bot Token ([get one from @BotFather](https://t.me/botfather))
- AI API Keys (OpenAI, Anthropic, etc.)

### Installation
```bash
# Clone the repository
git clone https://github.com/Astrocyte74/YTV2.git
cd YTV2

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your API keys

# Run the bot
python telegram_bot.py
```

### Docker Development
```bash
# Build and run
docker build -t ytv2 .
docker run --env-file .env -p 6452:6452 ytv2
```

## 🔧 Configuration

### Required Environment Variables
```bash
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_USER_ID=your_telegram_user_id
OPENAI_API_KEY=your_openai_api_key  # At least one AI provider required
```

### Optional Environment Variables
```bash
# AI Provider Settings
ANTHROPIC_API_KEY=your_anthropic_key
OPENROUTER_API_KEY=your_openrouter_key
LLM_SHORTLIST=fast  # Options: fast, research, budget, creative

# Bot Behavior
DEFAULT_SUMMARY_TYPE=comprehensive  # comprehensive, bullet-points, key-insights
MAX_TRANSCRIPT_LENGTH=50000
HTML_REPORT_RETENTION_HOURS=168  # 7 days

# Web Server
WEB_PORT=6452  # Port for web interface
WEB_BASE_URL=https://your-app.onrender.com
```

## 🎯 Usage

### Telegram Bot Commands
- Send any YouTube URL to get a summary
- `/start` - Welcome message and instructions
- `/help` - Show available commands
- `/stats` - Show usage statistics

### Web Interface
- Access your deployed URL to view summaries
- Interactive media player for audio content
- Mobile-responsive design
- Automatic cleanup of old reports

## 🏗️ Architecture

- **Core Engine**: `youtube_summarizer.py` - Handles video processing and AI integration
- **Bot Interface**: `telegram_bot.py` - Telegram bot with web server
- **AI Models**: `llm_config.py` - Multi-provider LLM configuration
- **Export Tools**: `export_utils.py` - HTML, JSON, PDF report generation

## 🔐 Security Features

- Environment-based configuration
- Non-root Docker container
- Input sanitization and validation
- Rate limiting and error handling
- Secure file handling

## 📊 Supported Platforms

- ✅ **Render** - One-click deployment (recommended)
- ✅ **Railway** - Git-based deployment
- ✅ **Fly.io** - Global edge deployment  
- ✅ **DigitalOcean App Platform** - Managed containers
- ✅ **Any Docker-compatible platform**

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🆘 Support

- 📚 Check the [deployment guides](./docs/) for platform-specific instructions
- 🐛 Report issues on [GitHub Issues](https://github.com/Astrocyte74/YTV2/issues)
- 💬 Join discussions in [GitHub Discussions](https://github.com/Astrocyte74/YTV2/discussions)

---

**Made with ❤️ for the YouTube summarization community**