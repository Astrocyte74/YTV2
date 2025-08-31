# YouTube Video Summarizer CLI

A simple, powerful command-line tool that extracts transcripts from YouTube videos and generates AI-powered summaries using multiple AI providers. Clean, focused, and reliable.

## 🌟 Features

- **Smart Summarization**: Generate comprehensive, bullet-point, or key-insights summaries
- **Content Analysis**: Automatic categorization, sentiment analysis, and topic extraction
- **Multiple Export Formats**: JSON, Markdown, HTML, and PDF outputs
- **Batch Processing**: Process multiple videos from a file
- **Multiple AI Providers**: Support for OpenAI GPT, Anthropic Claude, and OpenRouter models
- **Transcript Extraction**: Automatic extraction using yt-dlp with fallback to video descriptions

## 🚀 Quick Start

### Prerequisites

- Python 3.10 or higher
- OpenAI API Key or Anthropic API Key (or OpenRouter API Key)

### Installation

1. Clone or download this project
2. Create a virtual environment and install dependencies:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. Set up your API keys:

```bash
cp .env.template .env
# Edit .env and add your API keys
```

### Basic Usage

```bash
# Summarize a single video
python main.py "https://www.youtube.com/watch?v=your-video-id"

# Use Claude with bullet-point summary
python main.py "https://youtu.be/video-id" --provider anthropic --summary-type bullet-points

# Export to all formats
python main.py "https://youtu.be/video-id" --export all

# Include detailed analysis
python main.py "https://youtu.be/video-id" --analysis --export pdf
```

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