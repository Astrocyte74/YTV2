#!/usr/bin/env python3
"""
Command Line Interface for YouTube Video Summarizer
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import List, Optional

from youtube_summarizer import YouTubeSummarizer
from export_utils import SummaryExporter
from llm_config import llm_config

def print_banner():
    """Print application banner"""
    banner = """
╔══════════════════════════════════════════════════════════════════════════╗
║                        YouTube Video Summarizer                         ║
║                     Powered by MCP-Use & AI Models                      ║
╚══════════════════════════════════════════════════════════════════════════╝
"""
    print(banner)

def print_video_info(data: dict):
    """Print formatted video information"""
    metadata = data.get('metadata', {})
    
    print(f"\n📺 Video Information:")
    print(f"   Title: {metadata.get('title', 'Unknown')}")
    print(f"   Channel: {metadata.get('uploader', 'Unknown')}")
    print(f"   Duration: {format_duration(metadata.get('duration', 0))}")
    print(f"   Views: {metadata.get('view_count', 0):,}")
    print(f"   Upload Date: {metadata.get('upload_date', 'Unknown')}")

def print_summary(data: dict):
    """Print formatted summary"""
    summary = data.get('summary', {})
    
    print(f"\n📝 Summary:")
    print(f"   Headline: {summary.get('headline', 'No headline available')}")
    print(f"\n   Full Summary:")
    summary_text = summary.get('summary', 'No summary available')
    for line in summary_text.split('\n'):
        if line.strip():
            print(f"   {line.strip()}")

def print_analysis(data: dict):
    """Print formatted content analysis"""
    analysis = data.get('analysis', {})
    
    print(f"\n🔍 Content Analysis:")
    print(f"   Category: {', '.join(analysis.get('category', ['Unknown']))}")
    print(f"   Sentiment: {analysis.get('sentiment', 'Unknown')}")
    print(f"   Target Audience: {analysis.get('target_audience', 'Unknown')}")
    print(f"   Complexity: {analysis.get('complexity_level', 'Unknown')}")
    print(f"   Content Type: {analysis.get('content_type', 'Unknown')}")
    print(f"   Educational Value: {analysis.get('educational_value', 'Unknown')}")
    print(f"   Entertainment Value: {analysis.get('entertainment_value', 'Unknown')}")
    print(f"   Key Topics: {', '.join(analysis.get('key_topics', ['None']))}")

def format_duration(seconds: int) -> str:
    """Format duration from seconds to readable format"""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        minutes = seconds // 60
        remaining_seconds = seconds % 60
        return f"{minutes}m {remaining_seconds}s"
    else:
        hours = seconds // 3600
        remaining_minutes = (seconds % 3600) // 60
        remaining_seconds = seconds % 60
        return f"{hours}h {remaining_minutes}m {remaining_seconds}s"

def validate_youtube_url(url: str) -> bool:
    """Validate if URL is a YouTube video URL"""
    youtube_patterns = [
        'youtube.com/watch?v=',
        'youtu.be/',
        'youtube.com/embed/',
        'youtube.com/v/'
    ]
    return any(pattern in url for pattern in youtube_patterns)

async def process_single_video(args):
    """Process a single YouTube video"""
    if not validate_youtube_url(args.url):
        print("❌ Error: Invalid YouTube URL")
        print("   Please provide a valid YouTube video URL")
        return False
    
    try:
        # Initialize summarizer
        summarizer = YouTubeSummarizer(
            llm_provider=args.provider,
            model=args.model
        )
        
        print(f"🔄 Processing video: {args.url}")
        print(f"   Using {args.provider} with model: {args.model or 'default'}")
        print(f"   Summary type: {args.summary_type}")
        
        # Process video
        result = await summarizer.process_video(args.url, args.summary_type)
        
        if 'error' in result:
            print(f"❌ Error processing video: {result['error']}")
            return False
        
        # Display results
        print_video_info(result)
        print_summary(result)
        
        if args.analysis:
            print_analysis(result)
        
        # Export if requested
        if args.export:
            exporter = SummaryExporter(args.output_dir)
            
            if args.export == 'all':
                print(f"\n💾 Exporting to all formats...")
                exported_files = exporter.export_all_formats(result)
                
                print("   Exported files:")
                for format_name, filepath in exported_files.items():
                    if not filepath.startswith("Error"):
                        print(f"     ✅ {format_name.upper()}: {filepath}")
                    else:
                        print(f"     ❌ {format_name.upper()}: {filepath}")
            else:
                print(f"\n💾 Exporting to {args.export.upper()} format...")
                if args.export == 'json':
                    filepath = exporter.export_to_json(result)
                elif args.export == 'markdown':
                    filepath = exporter.export_to_markdown(result)
                elif args.export == 'html':
                    filepath = exporter.export_to_html(result)
                elif args.export == 'pdf':
                    filepath = exporter.export_to_pdf(result)
                
                print(f"   ✅ Exported: {filepath}")
        
        return True
        
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        return False

async def process_batch_videos(args):
    """Process multiple videos from a file"""
    try:
        with open(args.batch_file, 'r') as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        
        if not urls:
            print("❌ Error: No valid URLs found in batch file")
            return False
        
        print(f"🔄 Processing {len(urls)} videos from batch file...")
        
        # Initialize summarizer
        summarizer = YouTubeSummarizer(
            llm_provider=args.provider,
            model=args.model
        )
        
        exporter = SummaryExporter(args.output_dir) if args.export else None
        results = []
        
        for i, url in enumerate(urls, 1):
            if not validate_youtube_url(url):
                print(f"⚠️  Skipping invalid URL ({i}/{len(urls)}): {url}")
                continue
            
            print(f"\n🔄 Processing video {i}/{len(urls)}: {url}")
            
            try:
                result = await summarizer.process_video(url, args.summary_type)
                
                if 'error' in result:
                    print(f"   ❌ Error: {result['error']}")
                    continue
                
                print(f"   ✅ Processed: {result['metadata']['title']}")
                results.append(result)
                
                # Export individual results if requested
                if exporter and args.export != 'batch':
                    if args.export == 'all':
                        exporter.export_all_formats(result)
                    else:
                        getattr(exporter, f'export_to_{args.export}')(result)
                
            except Exception as e:
                print(f"   ❌ Error processing {url}: {str(e)}")
                continue
        
        # Export batch results
        if exporter and args.export == 'batch':
            batch_data = {
                'batch_info': {
                    'total_videos': len(results),
                    'processed_at': results[0]['processed_at'] if results else None,
                    'processor_info': results[0]['processor_info'] if results else None
                },
                'videos': results
            }
            
            batch_file = exporter.export_to_json(batch_data, f"batch_summary_{len(results)}_videos.json")
            print(f"\n💾 Batch summary exported: {batch_file}")
        
        print(f"\n✅ Batch processing complete: {len(results)}/{len(urls)} videos processed successfully")
        return True
        
    except FileNotFoundError:
        print(f"❌ Error: Batch file not found: {args.batch_file}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        return False

def main():
    """Main CLI function"""
    parser = argparse.ArgumentParser(
        description="YouTube Video Summarizer - Generate AI-powered summaries of YouTube videos",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Summarize a single video
  python cli.py https://www.youtube.com/watch?v=example
  
  # Use Claude with specific summary type
  python cli.py https://youtu.be/example --provider anthropic --summary-type bullet-points
  
  # Export to all formats
  python cli.py https://youtu.be/example --export all
  
  # Process multiple videos from file
  python cli.py --batch urls.txt --export json
  
  # Show detailed analysis
  python cli.py https://youtu.be/example --analysis --export pdf
        """
    )
    
    # Main arguments
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument('url', nargs='?', help='YouTube video URL to summarize')
    group.add_argument('--batch', dest='batch_file', help='File containing YouTube URLs (one per line)')
    
    # LLM Configuration  
    parser.add_argument('--provider', choices=['openai', 'anthropic', 'openrouter', 'ollama'],
                       help='LLM provider to use (default: auto-detected from mkpy config)')
    parser.add_argument('--model', help='Specific model to use (e.g., gpt-4, claude-3-sonnet-20240229)')
    parser.add_argument('--shortlist', choices=['research', 'budget', 'fast', 'creative', 'coding', 'local'],
                       help='Use mkpy model shortlist (overrides provider/model)')
    parser.add_argument('--config-status', action='store_true',
                       help='Show LLM configuration status and exit')
    
    # Summary options
    parser.add_argument('--summary-type', choices=['comprehensive', 'bullet-points', 'key-insights'],
                       default='comprehensive', help='Type of summary to generate (default: comprehensive)')
    parser.add_argument('--analysis', action='store_true',
                       help='Include detailed content analysis (sentiment, topics, etc.)')
    
    # Export options
    parser.add_argument('--export', choices=['json', 'markdown', 'html', 'pdf', 'all', 'batch'],
                       help='Export format (batch only for --batch mode)')
    parser.add_argument('--output-dir', default='./exports',
                       help='Output directory for exported files (default: ./exports)')
    
    # Other options
    parser.add_argument('--quiet', action='store_true',
                       help='Minimize output (only show results)')
    parser.add_argument('--version', action='version', version='YouTube Summarizer 1.0.0')
    
    args = parser.parse_args()
    
    # Handle config status request
    if args.config_status:
        llm_config.print_status()
        return 0
    
    # Validate that we have either URL or batch file
    if not args.url and not args.batch_file:
        parser.error("Must provide either a URL or --batch file (or use --config-status)")
        return 1
    
    # Handle shortlist override
    if args.shortlist:
        import os
        os.environ['LLM_SHORTLIST'] = args.shortlist
        llm_config.llm_shortlist = args.shortlist
        llm_config.load_environment()  # Reload with new shortlist
    
    # Print banner unless quiet mode
    if not args.quiet:
        print_banner()
        
        # Show current LLM configuration
        try:
            provider, model, _ = llm_config.get_model_config(args.provider, args.model)
            print(f"🤖 Using {provider}/{model} (shortlist: {llm_config.llm_shortlist})")
        except ValueError as e:
            print(f"⚠️  {e}")
            return 1
    
    # Process videos
    try:
        if args.batch_file:
            success = asyncio.run(process_batch_videos(args))
        else:
            success = asyncio.run(process_single_video(args))
        
        return 0 if success else 1
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Operation cancelled by user")
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())