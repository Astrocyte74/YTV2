# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Setup and Installation
```bash
# Create virtual environment and install dependencies
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Running the Application
```bash
# Basic usage - single video summarization
python main.py "https://www.youtube.com/watch?v=VIDEO_ID"

# Use specific AI provider and model
python main.py "https://youtu.be/VIDEO_ID" --provider anthropic --model claude-3-sonnet-20240229

# Generate different summary types
python main.py "https://youtu.be/VIDEO_ID" --summary-type bullet-points
python main.py "https://youtu.be/VIDEO_ID" --summary-type key-insights

# Include content analysis and export
python main.py "https://youtu.be/VIDEO_ID" --analysis --export pdf

# Batch processing
python main.py --batch urls.txt --export json

# Show configuration status
python main.py --config-status
```

### Testing
No specific test framework is currently configured. Test manually with sample YouTube URLs.

## Architecture Overview

This is a Python CLI application for AI-powered YouTube video summarization with the following key architectural components:

### Core Processing Pipeline
1. **Video Input**: YouTube URL validation and processing
2. **Transcript Extraction**: Uses yt-dlp to extract video transcripts/captions with multiple fallback strategies
3. **AI Summarization**: LangChain integration with multiple AI providers (OpenAI, Anthropic, OpenRouter, Ollama)
4. **Content Analysis**: Automated categorization, sentiment analysis, and topic extraction
5. **Multi-format Export**: JSON, Markdown, HTML, and PDF output formats

### Key Components

#### `youtube_summarizer.py` - Core Engine
- Main `YouTubeSummarizer` class handles the complete processing pipeline
- Robust transcript extraction with SRV3, JSON3, VTT, and TTML format parsing
- AI model integration via LangChain for summary generation and content analysis
- Fallback mechanisms for transcript failures (uses video description)

#### `llm_config.py` - AI Model Management  
- Centralized LLM configuration with mkpy integration support
- Model shortlists for different use cases (research, budget, fast, creative, coding, local)
- Automatic provider detection and API key management
- Fallback model selection when preferred models are unavailable

#### `cli.py` - Command Line Interface
- Comprehensive argument parsing for all application features
- Formatted output display with video metadata, summaries, and analysis
- Batch processing capabilities for multiple videos
- Export format selection and output directory management

#### `export_utils.py` - Output Generation
- `SummaryExporter` class supports JSON, Markdown, HTML, and PDF formats
- Uses ReportLab for professional PDF generation with tables and styling
- Markdown to HTML conversion with custom CSS styling
- Filename sanitization and timestamp-based naming

#### `main.py` - Entry Point
- Simple entry point that delegates to CLI module
- Maintains clean separation between CLI logic and main execution

### Configuration Management

The application uses a sophisticated configuration system:

- **Environment Variables**: Supports `.env` files for API keys
- **mkpy Integration**: Can integrate with mkpy LLM management system for centralized configuration
- **Model Shortlists**: Predefined model combinations optimized for different use cases
- **Provider Fallbacks**: Automatic fallback between OpenAI, Anthropic, OpenRouter, and Ollama

### Data Flow

1. URL validation and yt-dlp transcript extraction
2. AI model initialization based on configuration
3. Parallel summary generation and content analysis
4. Result aggregation with metadata
5. Optional export to selected formats
6. CLI output formatting and display

### Export Formats

- **JSON**: Complete structured data for programmatic use
- **Markdown**: Clean, readable format for documentation
- **HTML**: Web-ready format with custom styling  
- **PDF**: Professional report format with tables and formatting

### Error Handling

- Graceful degradation when transcripts are unavailable (uses video descriptions)
- API key validation and provider fallbacks
- Robust parsing for multiple transcript formats
- User-friendly error messages with troubleshooting guidance

## Important Implementation Notes

- The application prioritizes robustness with multiple fallback strategies for transcript extraction
- LangChain integration provides consistent interface across different AI providers
- Export utilities generate professional-quality outputs suitable for sharing
- Configuration system supports both standalone and integrated deployment scenarios
- Batch processing enables efficient handling of multiple videos with progress tracking