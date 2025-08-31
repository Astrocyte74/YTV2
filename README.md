# 🎥 YTV2 - AI-Powered YouTube Summarizer

Transform YouTube videos into concise, intelligent summaries using cutting-edge AI models. Perfect for research, content curation, and staying informed efficiently.

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

## 📚 Detailed Usage

### Command Line Options

```bash
python main.py [URL] [OPTIONS]
```

#### Options

- `--provider`: Choose LLM provider (`openai`, `anthropic`, `openrouter`)
- `--model`: Specific model to use (e.g., `gpt-4`, `claude-3-sonnet-20240229`)
- `--summary-type`: Type of summary (`comprehensive`, `bullet-points`, `key-insights`)
- `--analysis`: Include detailed content analysis
- `--export`: Export format (`json`, `markdown`, `html`, `pdf`, `all`)
- `--output-dir`: Output directory for exported files
- `--batch`: Process multiple URLs from a file
- `--quiet`: Minimize output

### Batch Processing

Create a text file with YouTube URLs (one per line):

```text
# urls.txt
https://www.youtube.com/watch?v=video1
https://youtu.be/video2
https://www.youtube.com/watch?v=video3
```

Process the batch:

```bash
python main.py --batch urls.txt --export json
```

### Python API Usage

```python
import asyncio
from src.youtube_summarizer import YouTubeSummarizer
from src.export_utils import SummaryExporter

async def main():
    # Initialize summarizer
    summarizer = YouTubeSummarizer(llm_provider="openai", model="gpt-4")
    
    # Process video
    result = await summarizer.process_video(
        "https://www.youtube.com/watch?v=example",
        summary_type="comprehensive"
    )
    
    # Export results
    exporter = SummaryExporter()
    files = exporter.export_all_formats(result)
    
    print("Exported files:", files)

asyncio.run(main())
```

## 📋 Summary Types

1. **Comprehensive**: Detailed summary with main topics, key points, and takeaways
2. **Bullet Points**: Concise bullet-point format with clear structure
3. **Key Insights**: Focus on actionable insights and learnings

## 📊 Content Analysis

The tool provides detailed content analysis including:

- **Category**: Content categorization (Education, Technology, etc.)
- **Sentiment**: Overall tone analysis (Positive, Negative, Neutral)
- **Target Audience**: Intended audience identification
- **Complexity Level**: Beginner, Intermediate, or Advanced
- **Key Topics**: Main subjects discussed
- **Educational/Entertainment Value**: Content value assessment

## 📁 Export Formats

- **JSON**: Raw data for further processing
- **Markdown**: Clean, readable format
- **HTML**: Web-ready format with styling
- **PDF**: Professional report format

## 🔧 Configuration

### Environment Variables

Create a `.env` file with your API keys:

```bash
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here

# Anthropic Configuration  
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# OpenRouter Configuration (optional)
OPENROUTER_API_KEY=your_openrouter_api_key_here
```

### Supported Models

#### OpenAI Models
- `gpt-4o-mini` (default)
- `gpt-4`
- `gpt-4-turbo`
- `gpt-3.5-turbo`

#### Anthropic Models
- `claude-3-sonnet-20240229` (default)
- `claude-3-opus-20240229`
- `claude-3-haiku-20240307`

#### OpenRouter Models
- `openai/gpt-4o-mini` (default)
- Access to 200+ models through OpenRouter

## 📁 Project Structure

```
youtube-mcp-summarizer/
├── main.py                     # Main entry point
├── src/
│   ├── youtube_summarizer.py   # Core summarization logic
│   ├── export_utils.py         # Export functionality
│   ├── cli.py                  # Command-line interface
│   └── interactive_cli.py      # Interactive CLI (optional)
├── requirements.txt            # Python dependencies
├── .env.template              # Environment variables template
├── examples/                  # Example scripts and outputs
├── tests/                     # Test files
└── README.md                  # This guide
```

## 🔍 Example Output

```
📺 Video Information:
   Title: How to Build AI Applications in 2024
   Channel: Tech Tutorials
   Duration: 15m 30s
   Views: 125,847
   Upload Date: 20240115

📝 Summary:
   Headline: This video explains modern AI development practices and tools for building production-ready applications.

   Full Summary:
   A comprehensive guide covering the latest AI development frameworks, best practices for model integration,
   and real-world examples of successful AI applications. The presenter walks through setting up development
   environments, choosing the right models, and implementing proper testing strategies.

🔍 Content Analysis:
   Category: Technology, Education
   Sentiment: Positive
   Target Audience: Developers and AI enthusiasts
   Complexity: Intermediate
   Content Type: Tutorial
   Educational Value: High
   Entertainment Value: Medium
   Key Topics: AI Development, Programming, Machine Learning, Software Engineering
```

## 🚨 Troubleshooting

### Common Issues

1. **API Key Errors**: Ensure your API keys are correctly set in the `.env` file
2. **Transcript Extraction Fails**: Some videos don't have transcripts - the tool will use video descriptions as fallback
3. **Large Videos**: Very long videos may hit API token limits - consider using shorter videos
4. **Network Issues**: yt-dlp may fail on some videos due to YouTube restrictions

### Error Messages

- `Invalid YouTube URL`: Ensure you're using a valid YouTube video URL
- `No transcript available`: The video doesn't have captions/transcripts
- `API rate limit exceeded`: Wait before making more requests
- `Model not found`: Check your model name and API key

## 🤝 Contributing

Ideas for contributions:

1. **Additional AI Models**: Add support for more AI providers
2. **Enhanced Export Formats**: Create new output formats
3. **Better Error Handling**: Improve error messages and recovery
4. **Performance Optimization**: Speed up processing for large batches
5. **Advanced Analysis**: Add more content analysis features

## 📄 License

This project is open source. See the implementation details for building your own version.

## 🙏 Acknowledgments

- [yt-dlp](https://github.com/yt-dlp/yt-dlp) for video transcript extraction
- [LangChain](https://langchain.com/) for LLM integration
- [OpenAI](https://openai.com/) and [Anthropic](https://anthropic.com/) for AI models

---

**Simple, powerful, and reliable YouTube video summarization**