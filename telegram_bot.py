#!/usr/bin/env python3
"""
Telegram Bot for YouTube Video Summarizer
Integrates with existing YouTubeSummarizer class to provide video summaries via Telegram
"""

import asyncio
import os
import re
import sys
import logging
import time
import hashlib
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
import socket
import json

# Load environment variables from .env file and stack.env
load_dotenv()

# Try to load .env.nas first (for NAS deployment)
nas_env_path = Path('./.env.nas')
if nas_env_path.exists():
    load_dotenv(nas_env_path)
    print(f"📁 Loaded NAS environment from {nas_env_path}")

# Also try to load from stack.env in parent directories for API keys
stack_env_paths = [
    Path('./stack.env'),
    Path('../stack.env'), 
    Path('../../stack.env'),
    Path('/Users/markdarby/projects/YTv3/stack.env')  # Explicit path for production
]

for env_path in stack_env_paths:
    if env_path.exists():
        load_dotenv(env_path)
        print(f"📁 Loaded environment from {env_path}")
        break

# Also try to source .envrc for project-specific overrides
try:
    import subprocess
    result = subprocess.run(['bash', '-c', 'source .envrc 2>/dev/null && env'], 
                          capture_output=True, text=True, cwd='.')
    if result.returncode == 0:
        for line in result.stdout.splitlines():
            if '=' in line:
                key, value = line.split('=', 1)
                if key.startswith(('LLM_', 'OPENAI_', 'ANTHROPIC_', 'OPENROUTER_')):
                    os.environ[key] = value
except Exception:
    pass  # Fallback to regular .env loading

# Debug: Print if OpenAI API key is loaded (for TTS)
openai_key = os.getenv('OPENAI_API_KEY')
if openai_key:
    print(f"✅ OPENAI_API_KEY loaded for TTS: {openai_key[:7]}...")
else:
    print("❌ OPENAI_API_KEY not found in environment")

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.constants import ParseMode, ChatAction

# Import existing classes
from youtube_summarizer import YouTubeSummarizer
from llm_config import llm_config

class ReportsHTTPHandler(SimpleHTTPRequestHandler):
    """Custom HTTP handler for serving HTML reports"""
    
    def __init__(self, *args, exports_dir=None, bot_instance=None, **kwargs):
        self.exports_dir = exports_dir
        self.bot_instance = bot_instance
        super().__init__(*args, **kwargs)
    
    def extract_video_id(self, url):
        """Extract YouTube video ID from various URL formats"""
        if not url:
            return None
            
        patterns = [
            r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
            r'(?:embed\/)([0-9A-Za-z_-]{11})',
            r'(?:v\/|v=|\/v\/|youtu\.be\/|\/embed\/)([0-9A-Za-z_-]{11})'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    def get_thumbnail_url(self, video_id):
        """Get YouTube thumbnail URL with fallbacks"""
        if video_id:
            # Use medium quality thumbnail (320x180)
            return f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg"
        return None
    
    def get_model_badge(self, model_text):
        """Convert model text to styled badge name"""
        if not model_text or model_text == "Unknown":
            return "Unknown"
        
        # Handle the case where we get just provider name (like "Openai")
        if model_text.lower() in ['openai', 'anthropic', 'deepseek', 'gemma', 'llama']:
            return model_text.upper()
        
        # Extract core model name
        model_mapping = {
            'gpt-4o': 'GPT-4o',
            'gpt-4o-mini': 'GPT-4o-mini',
            'gpt-5': 'GPT-5',
            'gpt-5-nano': 'GPT-5-nano',
            'claude-3-sonnet': 'Claude-3',
            'claude-3-haiku': 'Claude-3',
            'claude-3-opus': 'Claude-3',
            'deepseek-r1': 'DeepSeek',
            'deepseek': 'DeepSeek',
            'gemma-3': 'Gemma-3',
            'gemma': 'Gemma',
            'llama-3': 'Llama-3',
            'llama': 'Llama'
        }
        
        # Try to find exact match first
        model_lower = model_text.lower()
        for key, display in model_mapping.items():
            if key in model_lower:
                return display
        
        # Fallback - extract first meaningful part
        # Handle openrouter format like "openrouter/deepseek/deepseek-r1-distill-qwen-32b"
        if '/' in model_text:
            parts = model_text.split('/')
            if len(parts) >= 3:  # openrouter format
                model_name = parts[-1]  # Last part is usually the model
            else:
                model_name = parts[-1]  # Take last part
        else:
            model_name = model_text
        
        # Clean up and truncate
        clean_name = model_name.split('-')[0].upper()[:8]
        return clean_name if clean_name else "Unknown"
    
    def get_model_badge_class(self, model_text):
        """Get CSS class for model badge styling"""
        model_lower = model_text.lower()
        if 'claude' in model_lower or 'anthropic' in model_lower:
            return 'anthropic'
        elif 'gpt' in model_lower or 'openai' in model_lower:
            return 'openai'
        elif 'deepseek' in model_lower:
            return 'deepseek'
        elif 'gemma' in model_lower:
            return 'gemma'
        elif 'llama' in model_lower:
            return 'llama'
        else:
            return 'default'
    
    def do_GET(self):
        """Handle GET requests for HTML reports"""
        try:
            # Remove leading slash and get filename
            filename = self.path.lstrip('/')
            logger.info(f"🌐 Web request: {self.path} -> filename: '{filename}'")
            logger.info(f"🌐 Exports dir: {self.exports_dir}")
            
            # Handle favicon and other browser requests gracefully
            if filename in ['favicon.ico', 'robots.txt']:
                logger.info(f"🌐 Ignoring browser request for: {filename}")
                self.send_error(404, "Not found")
                return
            
            if not filename:
                # Serve index page
                logger.info("🌐 Serving index page")
                self.send_index_page()
                return
            
            # Handle exports subdirectory requests (e.g., /exports/file.mp3)
            if filename.startswith('exports/'):
                filename = filename[8:]  # Remove 'exports/' prefix
                logger.info(f"🌐 Handling exports request for: {filename}")
            
            # Security check - only allow .html and .mp3 files, no subdirectories except 'exports'
            if not (filename.endswith('.html') or filename.endswith('.mp3')) or '/' in filename or '..' in filename:
                logger.info(f"🌐 Security check failed for: {filename}")
                self.send_error(404, "File not found")
                return
            
            filepath = self.exports_dir / filename
            logger.info(f"🌐 Looking for file: {filepath}")
            logger.info(f"🌐 File exists: {filepath.exists()}")
            
            if not filepath.exists():
                logger.info(f"🌐 File not found: {filepath}")
                self.send_error(404, "Report not found or expired")
                return
            
            # Serve the file with appropriate content type
            logger.info(f"🌐 Serving file: {filepath}")
            self.send_response(200)
            
            # Set content type based on file extension
            if filename.endswith('.html'):
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.send_header('Cache-Control', 'no-cache')
            elif filename.endswith('.mp3'):
                self.send_header('Content-type', 'audio/mpeg')
                self.send_header('Cache-Control', 'public, max-age=3600')  # Cache audio files for 1 hour
                self.send_header('Accept-Ranges', 'bytes')  # Enable range requests for audio seeking
                
                # Get file size for Content-Length header
                file_size = filepath.stat().st_size
                self.send_header('Content-Length', str(file_size))
            
            self.end_headers()
            
            with open(filepath, 'rb') as f:
                content = f.read()
                logger.info(f"🌐 File size: {len(content)} bytes")
                logger.info(f"🌐 Content preview: {content[:200].decode('utf-8', errors='ignore')}")
                self.wfile.write(content)
                
        except Exception as e:
            logger.error(f"Error serving file {self.path}: {e}")
            logger.error(f"Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            self.send_error(500, "Internal server error")
    
    def do_POST(self):
        """Handle POST requests for delete operations"""
        try:
            import json
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            if data.get('action') == 'delete' and 'files' in data:
                deleted_files = []
                failed_files = []
                
                for filename in data['files']:
                    # Security check - only allow .html files, no path traversal
                    if not filename.endswith('.html') or '/' in filename or '..' in filename:
                        logger.warning(f"🚨 Security: Rejecting delete request for: {filename}")
                        failed_files.append(filename)
                        continue
                    
                    filepath = self.exports_dir / filename
                    
                    if filepath.exists():
                        try:
                            filepath.unlink()  # Delete the file
                            logger.info(f"🗑️ Deleted file: {filepath}")
                            deleted_files.append(filename)
                        except Exception as e:
                            logger.error(f"Failed to delete {filepath}: {e}")
                            failed_files.append(filename)
                    else:
                        logger.warning(f"File not found for deletion: {filepath}")
                        failed_files.append(filename)
                
                # Send response
                response_data = {
                    'success': len(failed_files) == 0,
                    'deleted': deleted_files,
                    'failed': failed_files,
                    'message': f"Deleted {len(deleted_files)} file(s)" + 
                              (f", {len(failed_files)} failed" if failed_files else "")
                }
                
                self.send_response(200 if response_data['success'] else 207)  # 207 = Multi-Status
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(response_data).encode('utf-8'))
                
            else:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': 'Invalid request'}).encode('utf-8'))
                
        except Exception as e:
            logger.error(f"Error handling POST request: {e}")
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': 'Server error'}).encode('utf-8'))
    
    def send_index_page(self):
        """Send an enhanced index page listing available reports"""
        try:
            html_files = list(self.exports_dir.glob("*.html"))
            html_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            logger.info(f"📊 Dashboard: Found {len(html_files)} HTML files in {self.exports_dir}")
            
            # Analyze model usage and channels from HTML files
            model_usage = {}
            all_models = set()
            channel_usage = {}
            all_channels = set()
            
            for html_file in html_files:
                try:
                    content = html_file.read_text(encoding='utf-8')
                    
                    # Extract model from content - try multiple patterns (same as card generation)
                    model_patterns = [
                        # New info-grid pattern (most recent format)
                        r'<div class="info-label">AI Model</div>\s*<div class="info-value">([^<]+)</div>',
                        # Also try AI Provider pattern for older reports
                        r'<div class="info-label">AI Provider</div>\s*<div class="info-value">([^<]+)</div>',
                        # Legacy patterns for backward compatibility
                        r'Model:\s*</strong>\s*([^<]+)',  # Original pattern
                        r'Model:\s*([^<\n]+)',           # Without </strong>
                        r'<strong>Model:</strong>\s*([^<\n]+)',  # With strong tags
                        r'Model:\s*<strong>([^<]+)</strong>',    # Model in strong
                    ]
                    
                    model_found = False
                    for pattern in model_patterns:
                        import re
                        model_match = re.search(pattern, content, re.IGNORECASE)
                        if model_match:
                            model = model_match.group(1).strip()
                            if model and model != "Unknown":
                                model_usage[model] = model_usage.get(model, 0) + 1
                                all_models.add(model)
                                logger.debug(f"🔍 Dashboard extracted model '{model}' from {html_file.name}")
                                model_found = True
                                break
                    
                    if not model_found:
                        logger.debug(f"🔍 No model found in {html_file.name}")
                    
                    # Extract channel from content
                    channel_patterns = [
                        # Look for channel name in header section
                        r'<div class="channel">([^<]+)</div>',
                        # Look for "uploader" metadata
                        r'"uploader":\s*"([^"]+)"',
                        # Look for uploader in older formats
                        r'Channel:\s*([^<\n]+)',
                        r'Uploader:\s*([^<\n]+)',
                    ]
                    
                    channel_found = False
                    for pattern in channel_patterns:
                        channel_match = re.search(pattern, content, re.IGNORECASE)
                        if channel_match:
                            channel = channel_match.group(1).strip()
                            if channel and channel != "Unknown Channel" and channel != "Unknown":
                                channel_usage[channel] = channel_usage.get(channel, 0) + 1
                                all_channels.add(channel)
                                logger.debug(f"🔍 Dashboard extracted channel '{channel}' from {html_file.name}")
                                channel_found = True
                                break
                    
                    if not channel_found:
                        logger.debug(f"🔍 No channel found in {html_file.name}")
                        
                except Exception as e:
                    logger.warning(f"Could not extract model from {html_file.name}: {e}")
            
            # Get top 3 models for display
            top_models = sorted(model_usage.items(), key=lambda x: x[1], reverse=True)[:3]
            models_text = ", ".join([f"{model} ({count})" for model, count in top_models]) if top_models else "Mixed Models"
            
            total_reports = len(html_files)
            total_size = sum(f.stat().st_size for f in html_files) / (1024 * 1024)  # MB
            
            # Load dashboard template and generate modern HTML
            def load_template(template_name):
                try:
                    template_path = Path(template_name)
                    if template_path.exists():
                        return template_path.read_text(encoding='utf-8')
                    else:
                        logger.error(f"Template not found: {template_name}")
                        return None
                except Exception as e:
                    logger.error(f"Error loading template {template_name}: {e}")
                    return None
            
            # Generate reports data for template
            reports_data = []
            for file_path in html_files:
                try:
                    # Extract metadata from each report
                    content = file_path.read_text(encoding='utf-8')
                    
                    # Extract title
                    title_match = re.search(r'<h1[^>]*>([^<]+)</h1>', content)
                    title = title_match.group(1).strip() if title_match else file_path.stem
                    
                    # Extract channel
                    channel_match = re.search(r'<div class="channel">([^<]+)</div>', content)
                    channel = channel_match.group(1).strip() if channel_match else "Unknown Channel"
                    
                    # Extract model
                    model_match = re.search(r'<div class="model-badge[^"]*">([^<]+)</div>', content)
                    model = model_match.group(1).strip() if model_match else "GPT-4"
                    
                    # Extract summary preview
                    summary_match = re.search(r'<div class="content">.*?<p[^>]*>([^<]{0,200})', content, re.DOTALL)
                    summary_preview = summary_match.group(1).strip()[:150] + "..." if summary_match else "No preview available"
                    
                    # Extract thumbnail URL
                    thumbnail_match = re.search(r'<img[^>]+src="([^"]+)"[^>]*alt="Video thumbnail"', content)
                    thumbnail_url = thumbnail_match.group(1) if thumbnail_match else ""
                    
                    # Get file info
                    mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    
                    reports_data.append({
                        'filename': file_path.name,
                        'title': title,
                        'channel': channel,
                        'model': model,
                        'summary_preview': summary_preview,
                        'thumbnail_url': thumbnail_url,
                        'created_date': mtime.strftime('%B %d, %Y'),
                        'created_time': mtime.strftime('%H:%M'),
                        'timestamp': mtime.timestamp()
                    })
                except Exception as e:
                    logger.warning(f"Error processing report {file_path.name}: {e}")
            
            # Load and populate template
            template_content = load_template('dashboard_template.html')
            if template_content:
                # Replace template placeholders
                index_html = template_content.format(
                    reports_data=json.dumps(reports_data, ensure_ascii=False),
                    base_url=base_url or 'https://chief-inspired-lab.ngrok-free.app'
                )
            else:
                # Fallback to simple HTML if template fails  
                index_html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Template Loading Error</title>
    <style>
        body {{ font-family: Arial, sans-serif; padding: 2rem; }}
        .error {{ color: #dc2626; background: #fef2f2; padding: 1rem; border-radius: 0.5rem; }}
    </style>
</head>
<body>
    <h1>🚨 Template Loading Error</h1>
    <div class="error">
        <p><strong>Could not load dashboard template.</strong></p>
        <p>Please ensure 'dashboard_template.html' exists in the project directory.</p>
        <p>Using fallback display - found {len(html_files)} reports.</p>
    </div>
    
    <h2>📊 Available Reports</h2>
    <ul>"""
                
                # Add basic report list as fallback
                for report in reports_data[:10]:  # Show first 10 only
                    index_html += f"""
        <li><a href="/{report['filename']}">{report['title']}</a> - {report['channel']} ({report['model']})</li>"""
                
                if len(reports_data) > 10:
                    index_html += f"""
        <li><em>... and {len(reports_data) - 10} more reports</em></li>"""
                
                index_html += """
    </ul>
</body>
</html>"""
            
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            self.wfile.write(index_html.encode('utf-8'))
        
        except Exception as e:
            logger.error(f"Error generating index page: {e}")
            self.send_error(500, "Internal server error")
    
    def generate_individual_report_page(self):
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>YouTube Summary Reports Dashboard</title>
    <style>
        /* Root Variables - Clean Professional Colors */
        :root {{
            --primary-blue: #0066cc;
            --secondary-gray: #6b7280;
            --text-dark: #1f2937;
            --text-medium: #4b5563;
            --text-light: #9ca3af;
            --border-light: #e5e7eb;
            --border-medium: #d1d5db;
            --background-white: #ffffff;
            --background-gray: #f8fafc;
            --background-light: #f1f5f9;
            --success-green: #10b981;
            --danger-red: #ef4444;
            --warning-orange: #f59e0b;
        }}
        
        /* Base Styles */
        * {{
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 0;
            background: var(--background-light);
            color: var(--text-dark);
            line-height: 1.6;
        }}
        
        /* ==========================================
           COMPACT HEADER - 40% Smaller
           ========================================== */
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: var(--background-white);
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            min-height: 100vh;
            overflow-x: hidden;
        }}
        
        .header {{
            background: var(--background-white);
            border-bottom: 1px solid var(--border-light);
            padding: 16px 24px; /* Reduced from 25px 30px */
            position: sticky;
            top: 0;
            z-index: 100;
        }}
        
        .header-content {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 20px;
            max-width: 1400px;
            margin: 0 auto;
        }}
        
        .header-text {{
            text-align: left; /* Changed from center */
        }}
        
        .header h1 {{
            font-size: 1.5rem; /* Reduced from 2em */
            margin: 0 0 4px 0; /* Reduced margin */
            font-weight: 600; /* Reduced from 700 */
            color: var(--text-dark);
        }}
        
        .header p {{
            font-size: 0.875rem; /* Reduced from 1.1em */
            color: var(--text-medium);
            margin: 0;
        }}
        
        /* Hide mini player from header - will be moved to footer */
        .mini-player-header {{
            display: none !important;
        }}
        
        /* ==========================================
           INTEGRATED SEARCH & CONTROLS BAR
           ========================================== */
        .controls-bar {{
            background: var(--background-white);
            border-bottom: 1px solid var(--border-light);
            padding: 12px 24px; /* Reduced padding */
            position: sticky;
            top: 73px; /* Adjust based on header height */
            z-index: 99;
        }}
        
        .controls-row {{
            display: flex;
            align-items: center;
            gap: 16px;
            max-width: 1400px;
            margin: 0 auto;
        }}
        
        .search-wrapper {{
            flex: 1;
            max-width: 400px;
        }}
        
        .search-container {{
            position: relative;
        }}
        
        .search-input {{
            width: 100%;
            padding: 8px 12px 8px 36px; /* Reduced padding */
            border: 1px solid var(--border-medium);
            border-radius: 6px; /* Reduced from 10px */
            font-size: 14px; /* Reduced font size */
            background: var(--background-white);
            transition: all 0.2s ease;
        }}
        
        .search-input:focus {{
            outline: none;
            border-color: var(--primary-blue);
            box-shadow: 0 0 0 3px rgba(0, 102, 204, 0.1);
        }}
        
        .search-icon {{
            position: absolute;
            left: 12px;
            top: 50%;
            transform: translateY(-50%);
            color: var(--text-light);
            font-size: 14px;
        }}
        
        .controls-group {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        
        .control-select {{
            padding: 6px 12px; /* Reduced padding */
            border: 1px solid var(--border-medium);
            border-radius: 6px;
            background: var(--background-white);
            font-size: 13px; /* Reduced font size */
            color: var(--text-dark);
            cursor: pointer;
        }}
        
        .btn {{
            padding: 6px 12px; /* Reduced padding */
            border-radius: 6px;
            font-size: 13px; /* Reduced font size */
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s ease;
            border: none;
        }}
        
        .btn-outline {{
            background: var(--background-white);
            color: var(--text-dark);
            border: 1px solid var(--border-medium);
        }}
        
        .btn-outline:hover {{
            background: var(--background-gray);
            border-color: var(--primary-blue);
        }}
        
        .btn-danger {{
            background: var(--danger-red);
            color: white;
        }}
        
        .btn-danger:hover {{
            background: #dc2626;
        }}
        
        .btn-danger:disabled {{
            background: var(--text-light);
            cursor: not-allowed;
        }}
        
        /* ==========================================
           IMPROVED GRID LAYOUT - 2-3 Cards Per Row
           ========================================== */
        .content {{
            padding: 20px 24px 120px 24px; /* Added bottom padding for footer player */
            max-width: 1400px;
            margin: 0 auto;
        }}
        
        .reports-container {{
            margin-top: 0;
        }}
        
        .section-title {{
            font-size: 1.25rem; /* Reduced from 1.4em */
            color: var(--text-dark);
            margin-bottom: 16px; /* Reduced from 20px */
            font-weight: 600;
        }}
        
        .report-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); /* Fixed auto-fit and reduced min-width */
            gap: 16px;
            margin-top: 0;
            width: 100%;
        }}
        
        /* ==========================================
           CLEAN CARD DESIGN - No Gradients
           ========================================== */
        .report-card {{
            background: var(--background-white);
            border: 1px solid var(--border-light);
            border-radius: 12px; /* Reduced from 16px */
            overflow: hidden;
            transition: all 0.3s ease;
            position: relative;
            display: flex;
            flex-direction: column;
            height: 320px; /* Fixed height for consistency */
        }}
        
        .report-card:hover {{
            transform: translateY(-4px); /* Reduced from -10px */
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12); /* Reduced shadow */
            border-color: var(--border-medium);
        }}
        
        /* Remove the gradient accent bar */
        .report-card::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px; /* Reduced from 4px */
            background: var(--primary-blue); /* Single color, no gradient */
            transform: translateY(-3px);
            transition: transform 0.3s ease;
        }}
        
        .report-card:hover::before {{
            transform: translateY(0);
        }}
        
        .card-thumbnail {{
            width: 100%;
            height: 140px; /* Increased from 120px */
            background: var(--background-gray);
            display: flex;
            align-items: center;
            justify-content: center;
            position: relative;
            overflow: hidden;
        }}
        
        .card-thumbnail img {{
            width: 100%;
            height: 100%;
            object-fit: cover;
            transition: transform 0.3s ease;
        }}
        
        .report-card:hover .card-thumbnail img {{
            transform: scale(1.03); /* Reduced from 1.05 */
        }}
        
        .thumbnail-fallback {{
            color: var(--text-light);
            font-size: 2em;
            cursor: pointer;
        }}
        
        /* Card Controls */
        .report-checkbox {{
            position: absolute;
            top: 12px;
            left: 12px;
            z-index: 10;
            transform: scale(1.1);
        }}
        
        .card-delete-btn {{
            position: absolute;
            top: 12px;
            right: 12px;
            z-index: 10;
            background: rgba(239, 68, 68, 0.9);
            color: white;
            border: none;
            width: 28px; /* Reduced from larger */
            height: 28px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            opacity: 0;
            transition: all 0.2s ease;
        }}
        
        .report-card:hover .card-delete-btn {{
            opacity: 1;
        }}
        
        .card-delete-btn:hover {{
            background: var(--danger-red);
            transform: scale(1.1);
        }}
        
        /* Card Content */
        .card-content {{
            padding: 16px;
            flex: 1;
            display: flex;
            flex-direction: column;
        }}
        
        .model-badge {{
            display: inline-block;
            background: var(--background-light);
            color: var(--text-dark);
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 500;
            margin-bottom: 8px;
            border: 1px solid var(--border-light);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            align-self: flex-start;
        }}
        
        /* Model badge color variations - subtle, professional */
        .model-badge.anthropic {{ 
            background: #fef3c7; 
            color: #92400e; 
            border-color: #fcd34d; 
        }}
        .model-badge.openai {{ 
            background: #dbeafe; 
            color: #1d4ed8; 
            border-color: #93c5fd; 
        }}
        .model-badge.deepseek {{ 
            background: #d1fae5; 
            color: #047857; 
            border-color: #86efac; 
        }}
        .model-badge.gemma {{ 
            background: #e9d5ff; 
            color: #7c2d12; 
            border-color: #c4b5fd; 
        }}
        
        .report-title {{
            font-size: 1rem;
            font-weight: 600;
            color: var(--text-dark);
            margin-bottom: 8px;
            line-height: 1.4;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
            flex: 1;
        }}
        
        .report-meta {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-top: auto;
            padding-top: 12px;
            border-top: 1px solid var(--border-light);
        }}
        
        .report-channel {{
            font-size: 0.875rem;
            color: var(--text-medium);
            font-weight: 500;
        }}
        
        .report-time {{
            font-size: 0.75rem;
            color: var(--text-light);
        }}
        
        .report-actions {{
            display: flex;
            gap: 8px;
            margin-top: 12px;
        }}
        
        .action-btn {{
            padding: 6px 12px;
            font-size: 0.75rem;
            border-radius: 4px;
            border: 1px solid var(--border-medium);
            background: var(--background-white);
            color: var(--text-dark);
            cursor: pointer;
            transition: all 0.2s ease;
            text-decoration: none;
        }}
        
        .action-btn:hover {{
            background: var(--background-gray);
            border-color: var(--primary-blue);
            color: var(--primary-blue);
        }}
        
        .action-btn.primary {{
            background: var(--primary-blue);
            color: white;
            border-color: var(--primary-blue);
        }}
        
        .action-btn.primary:hover {{
            background: #0056b3;
            border-color: #0056b3;
        }}
        
        /* Audio indicator */
        .audio-indicator {{
            position: absolute;
            bottom: 12px;
            left: 12px;
            background: var(--success-green);
            color: white;
            padding: 4px 6px;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 500;
        }}
        
        /* Card Selection State */
        .report-card.selected {{
            border-color: var(--primary-blue);
            box-shadow: 0 0 0 2px rgba(0, 102, 204, 0.1);
            background: rgba(0, 102, 204, 0.02);
        }}
        
        /* ==========================================
           FOOTER MINI-PLAYER (SPOTIFY-STYLE)
           ========================================== */
        .mini-player-footer {{
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: var(--background-white);
            border-top: 1px solid var(--border-light);
            padding: 12px 24px;
            z-index: 200;
            backdrop-filter: blur(8px);
            background: rgba(255, 255, 255, 0.95);
        }}
        
        .mini-player-container {{
            max-width: 1400px;
            margin: 0 auto;
            display: grid;
            grid-template-columns: 1fr auto auto;
            align-items: center;
            gap: 20px;
        }}
        
        .mini-player-info {{
            min-width: 0; /* Allow shrinking */
        }}
        
        .mini-player-title {{
            font-size: 0.875rem;
            font-weight: 500;
            color: var(--text-dark);
            margin: 0 0 4px 0;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        
        .mini-player-meta {{
            font-size: 0.75rem;
            color: var(--text-medium);
            margin: 0;
        }}
        
        .mini-player-controls {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        
        .mini-player-progress {{
            display: flex;
            align-items: center;
            gap: 12px;
            min-width: 200px;
        }}
        
        .mini-timeline {{
            flex: 1;
            height: 4px;
            background: var(--border-light);
            border-radius: 2px;
            cursor: pointer;
            appearance: none;
            outline: none;
        }}
        
        .mini-timeline::-webkit-slider-thumb {{
            appearance: none;
            width: 12px;
            height: 12px;
            border-radius: 6px;
            background: var(--primary-blue);
            cursor: pointer;
        }}
        
        .mini-time-display {{
            font-size: 0.75rem;
            color: var(--text-medium);
            min-width: 80px;
            text-align: center;
        }}
        
        .mini-btn {{
            background: none;
            border: 1px solid var(--border-medium);
            color: var(--text-dark);
            padding: 6px 8px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.875rem;
            transition: all 0.2s ease;
        }}
        
        .mini-btn:hover {{
            background: var(--background-gray);
            border-color: var(--primary-blue);
        }}
        
        .mini-btn.primary {{
            background: var(--primary-blue);
            color: white;
            border-color: var(--primary-blue);
        }}
        
        .mini-btn.primary:hover {{
            background: #0056b3;
        }}
        
        .mini-btn.close {{
            background: none;
            border: none;
            color: var(--text-light);
            padding: 4px;
        }}
        
        .mini-btn.close:hover {{
            color: var(--text-dark);
        }}
        
        /* Hide mini player when not active */
        .mini-player-footer[hidden] {{
            display: none;
        }}
        
        /* ==========================================
           BULK ACTIONS (SHOW ONLY WHEN ITEMS SELECTED)
           ========================================== */
        .bulk-actions {{
            position: fixed;
            bottom: 80px; /* Above mini player */
            right: 24px;
            background: var(--background-white);
            border: 1px solid var(--border-medium);
            border-radius: 8px;
            padding: 12px;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12);
            display: none; /* Hidden by default */
            gap: 8px;
            z-index: 150;
        }}
        
        .bulk-actions.show {{
            display: flex;
        }}
        
        .bulk-actions .btn {{
            font-size: 0.875rem;
            padding: 8px 16px;
        }}
        
        /* ==========================================
           IMPROVED FILTER DRAWER
           ========================================== */
        .toolbar {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 20px;
            padding: 12px 0;
        }}
        
        .toolbar-left {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        
        #btnFilters {{
            background: var(--primary-blue);
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            font-weight: 500;
            cursor: pointer;
            font-size: 0.875rem;
        }}
        
        #btnFilters:hover {{
            background: #0056b3;
        }}
        
        .filter-badge {{
            position: absolute;
            top: -6px;
            right: -6px;
            background: var(--danger-red);
            color: white;
            border-radius: 10px;
            padding: 2px 6px;
            font-size: 0.7em;
            font-weight: 600;
        }}
        
        .chips {{
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
            align-items: center;
        }}
        
        .chip {{
            background: var(--background-light);
            border: 1px solid var(--border-medium);
            border-radius: 16px;
            padding: 4px 8px;
            display: inline-flex;
            gap: 6px;
            align-items: center;
            font-size: 0.75rem;
            color: var(--text-dark);
        }}
        
        .chip button {{
            background: none;
            border: none;
            color: var(--text-light);
            cursor: pointer;
            padding: 0;
            margin: 0;
            font-size: 1em;
        }}
        
        .chip button:hover {{
            color: var(--danger-red);
        }}
        
        /* ==========================================
           RESPONSIVE DESIGN
           ========================================== */
        @media (max-width: 1200px) {{
            .report-grid {{
                grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            }}
        }}
        
        @media (max-width: 768px) {{
            .header-content {{
                flex-direction: column;
                gap: 12px;
                text-align: center;
            }}
            
            .controls-row {{
                flex-direction: column;
                gap: 12px;
            }}
            
            .search-wrapper {{
                max-width: none;
                width: 100%;
            }}
            
            .controls-group {{
                width: 100%;
                justify-content: center;
            }}
            
            .report-grid {{
                grid-template-columns: 1fr;
                gap: 12px;
            }}
            
            .report-card {{
                height: auto;
            }}
            
            .mini-player-footer {{
                padding: 8px 16px;
            }}
            
            .mini-player-container {{
                grid-template-columns: 1fr;
                gap: 12px;
                text-align: center;
            }}
            
            .mini-player-progress {{
                order: -1;
                min-width: auto;
            }}
            
            .bulk-actions {{
                position: static;
                margin: 20px 0;
                justify-content: center;
            }}
        }}
        
        @media (max-width: 480px) {{
            .content {{
                padding: 16px 16px 100px 16px;
            }}
            
            .header {{
                padding: 12px 16px;
            }}
            
            .controls-bar {{
                padding: 8px 16px;
            }}
            
            .report-card {{
                height: 280px;
            }}
            
            .card-content {{
                padding: 12px;
            }}
        }}
        
        /* ==========================================
           CLEAN INFO TILES (NO GRADIENTS)
           ========================================== */
        .info-tiles {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            padding: 20px 24px;
            background: var(--background-gray);
            border-bottom: 1px solid var(--border-light);
        }}
        
        .info-tile {{
            background: var(--background-white);
            padding: 16px;
            border-radius: 8px;
            display: flex;
            align-items: center;
            gap: 12px;
            box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);
            border: 1px solid var(--border-light);
        }}
        
        .info-tile-icon {{
            font-size: 1.25rem;
            min-width: 24px;
            text-align: center;
        }}
        
        .info-tile-content {{
            display: flex;
            flex-direction: column;
        }}
        
        .info-tile-value {{
            font-size: 1.25rem;
            font-weight: 600;
            color: var(--text-dark);
            line-height: 1.2;
        }}
        
        .info-tile-label {{
            color: var(--text-medium);
            font-size: 0.875rem;
            font-weight: 500;
        }}
        
        /* ==========================================
           CLEAN DRAWER STYLES
           ========================================== */
        .drawer {{
            position: fixed;
            top: 0;
            left: 0;
            bottom: 0;
            width: 400px;
            max-width: 90vw;
            background: var(--background-white);
            border-right: 1px solid var(--border-light);
            box-shadow: 6px 0 24px rgba(0, 0, 0, 0.12);
            transform: translateX(-100%);
            transition: transform 0.3s ease;
            z-index: 1000;
            display: flex;
            flex-direction: column;
        }}
        
        .drawer.open {{
            transform: translateX(0);
        }}
        
        .drawer__header {{
            background: var(--primary-blue);
            color: white;
            padding: 20px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }}
        
        .drawer__title {{
            font-size: 1.125rem;
            font-weight: 600;
            margin: 0;
        }}
        
        .drawer__actions {{
            display: flex;
            gap: 8px;
        }}
        
        .drawer__actions button {{
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
            color: white;
            padding: 6px 12px;
            border-radius: 4px;
            font-size: 0.875rem;
            cursor: pointer;
        }}
        
        .drawer__actions button:hover {{
            background: rgba(255, 255, 255, 0.2);
        }}
        
        .drawer__sections {{
            flex: 1;
            overflow-y: auto;
            padding: 20px;
        }}

        /* Backdrop for drawer overlay */
        .backdrop {{
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0, 0, 0, 0.5);
            z-index: 999;
            opacity: 0;
            transition: opacity 0.3s ease;
        }}

        .backdrop.visible {{
            opacity: 1;
        }}
        
        /* ==========================================
           MODAL IMPROVEMENTS
           ========================================== */
        .modal {{
            display: none;
            position: fixed;
            z-index: 2000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0, 0, 0, 0.5);
            backdrop-filter: blur(4px);
        }}
        
        .modal-content {{
            background: var(--background-white);
            margin: 20% auto;
            padding: 24px;
            border-radius: 8px;
            width: 90%;
            max-width: 400px;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.15);
        }}
        
        .modal h2 {{
            margin: 0 0 16px 0;
            color: var(--text-dark);
            font-size: 1.25rem;
        }}
        
        .modal p {{
            margin: 0 0 20px 0;
            color: var(--text-medium);
        }}
        
        .modal-actions {{
            display: flex;
            gap: 12px;
            justify-content: flex-end;
        }}
        
        /* ==========================================
           UTILITY CLASSES
           ========================================== */
        .hidden {{ display: none !important; }}
        .visible {{ display: block !important; }}
        
        .text-center {{ text-align: center; }}
        .text-left {{ text-align: left; }}
        .text-right {{ text-align: right; }}
        
        .mt-0 {{ margin-top: 0; }}
        .mt-1 {{ margin-top: 0.25rem; }}
        .mt-2 {{ margin-top: 0.5rem; }}
        .mt-4 {{ margin-top: 1rem; }}
        
        .mb-0 {{ margin-bottom: 0; }}
        .mb-1 {{ margin-bottom: 0.25rem; }}
        .mb-2 {{ margin-bottom: 0.5rem; }}
        .mb-4 {{ margin-bottom: 1rem; }}
        
        .p-0 {{ padding: 0; }}
        .p-1 {{ padding: 0.25rem; }}
        .p-2 {{ padding: 0.5rem; }}
        .p-4 {{ padding: 1rem; }}
        
        /* ==========================================
           PERFORMANCE OPTIMIZATIONS
           ========================================== */
        .report-card,
        .info-tile,
        .mini-player-footer {{
            will-change: transform;
        }}
        
        .report-card:hover {{
            will-change: auto;
        }}
        
        /* Smooth scrolling */
        html {{
            scroll-behavior: smooth;
        }}
        
        /* Focus management */
        .btn:focus,
        .search-input:focus,
        .control-select:focus {{
            outline: 2px solid var(--primary-blue);
            outline-offset: 2px;
        }}
        
        /* High contrast mode support */
        @media (prefers-contrast: high) {{
            :root {{
                --border-light: #000000;
                --border-medium: #000000;
                --text-light: #000000;
            }}
        }}
        
        /* Reduced motion support */
        @media (prefers-reduced-motion: reduce) {{
            *,
            *::before,
            *::after {{
                animation-duration: 0.01ms !important;
                animation-iteration-count: 1 !important;
                transition-duration: 0.01ms !important;
                scroll-behavior: auto !important;
            }}
        }}    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="header-content">
                <div class="header-text">
                    <h1>📺 YouTube Summary Reports</h1>
                    <p>AI-powered video analysis dashboard</p>
                </div>
                
            </div>
        </div>
        
        
        <div class="controls-bar">
                <div class="controls-row">
                    <div class="search-wrapper">
                        <span class="search-icon">🔍</span>
                        <div class="search-container">
                            <input type="text" id="searchInput" class="search-input" placeholder="Search by title, keyword, or model..." onkeyup="filterReports()">
                            <button class="search-clear" onclick="clearSearch()" style="display: none;" title="Clear search">×</button>
                        </div>
                    </div>
                    <div class="controls-group">
                        <select id="sortBy" class="control-select" onchange="sortReports()">
                            <option value="newest">🔄 Newest</option>
                            <option value="oldest">🔄 Oldest</option>
                            <option value="title">🔤 Title A-Z</option>
                            <option value="size">📏 Size</option>
                        </select>
                        <button onclick="selectAll()" class="btn btn-outline" id="selectAllBtn">Select All</button>
                        <button onclick="deleteSelected()" class="btn btn-danger" id="deleteBtn" disabled>🗑️ Delete</button>
                        <!-- Export button removed - not implemented -->
                    </div>
                </div>
            </div>
            
        <div class="content">
            <!-- Toolbar with Filter Button and Active Chips -->
            <div class="toolbar">
                <div class="toolbar-left">
                    <button id="btnFilters" aria-controls="filtersDrawer" aria-expanded="false">
                        🔎 Filters
                        <span class="filter-badge" id="filterBadge" style="display: none;">0</span>
                    </button>
                </div>
                <div id="activeFilters" class="chips">
                    <!-- Active filter chips will be rendered here -->
                </div>
            </div>
            
            <!-- Off-canvas Filter Drawer -->
            <aside id="filtersDrawer" class="drawer" role="dialog" aria-labelledby="filtersTitle" aria-modal="true" hidden>
                <header class="drawer__header">
                    <h2 id="filtersTitle" class="drawer__title">Filters</h2>
                    <div class="drawer__actions">
                        <button id="applyFilters">Apply</button>
                        <button id="clearAllFilters">Clear All</button>
                        <button id="closeFilters">✕</button>
                    </div>
                </header>

                <div class="drawer__sections">
                    <!-- Models Section -->
                    <details open>
                        <summary>
                            <span>AI Models</span>
                            <span class="count" data-count-for="models">({len(model_usage)})</span>
                            <span class="group-actions">
                                <button type="button" data-select-all="models">Select all</button>
                                <button type="button" data-clear="models">Clear All</button>
                            </span>
                        </summary>
                        <div class="group">
                            <input type="search" placeholder="Filter models…" class="mini-search" data-filter-list="#modelsList">
                            <ul id="modelsList" class="checklist">"""
                            
            # Add model filter checkboxes
            for model, count in sorted(model_usage.items()):
                # Get cleaner display name for model
                display_name = self.get_model_badge(model)
                model_id = model.replace('/', '_').replace(' ', '_').replace('-', '_').replace(':', '_')
                index_html += f"""
                                <li class="checkbox-item" data-value="{model.lower()}">
                                    <label>
                                        <input type="checkbox" value="{model}" checked>
                                        <span class="label-text">{display_name}</span>
                                        <span class="item-count">({count})</span>
                                    </label>
                                </li>"""
                                
            index_html += """
                            </ul>
                        </div>
                    </details>
                    
                    <!-- Channels Section -->
                    <details open>
                        <summary>
                            <span>Channels</span>
                            <span class="count" data-count-for="channels">({len(channel_usage)})</span>
                            <span class="group-actions">
                                <button type="button" data-select-all="channels">Select all</button>
                                <button type="button" data-clear="channels">Clear All</button>
                            </span>
                        </summary>
                        <div class="group">
                            <input type="search" placeholder="Filter channels…" class="mini-search" data-filter-list="#channelsList">
                            <ul id="channelsList" class="checklist">"""
                            
            # Add channel filter checkboxes
            for channel, count in sorted(channel_usage.items()):
                # Truncate long channel names for display
                display_channel = channel if len(channel) <= 25 else channel[:22] + "..."
                index_html += f"""
                                <li class="checkbox-item" data-value="{channel.lower()}">
                                    <label>
                                        <input type="checkbox" value="{channel}" checked>
                                        <span class="label-text" title="{channel}">{display_channel}</span>
                                        <span class="item-count">({count})</span>
                                    </label>
                                </li>"""
                                
            index_html += """
                            </ul>
                        </div>
                    </details>
                </div>
                
                <!-- Drawer Footer -->
                <footer class="drawer__footer">
                    <div class="footer-info">
                        <span id="selectedCount">All items selected</span>
                    </div>
                </footer>
            </aside>
            
            <!-- Off-canvas Playlist Drawer -->
            <aside id="playlistDrawer" class="drawer" role="dialog" aria-labelledby="playlistTitle" aria-modal="true" hidden>
                <header class="drawer__header">
                    <h2 id="playlistTitle" class="drawer__title">🎵 Audio Playlist</h2>
                    <div class="drawer__actions">
                        <button id="playlistPlayAll">Play All</button>
                        <button id="playlistShuffle">Shuffle</button>
                        <button id="playlistStop" style="display: none;">Stop</button>
                        <button id="closePlaylist">✕</button>
                    </div>
                </header>
                
                <div class="playlist-content">
                    <div class="playlist-info-bar" id="playlistInfoBar" style="display: none;">
                        <div class="now-playing-info">
                            <span id="drawerNowPlaying">♪ Ready to play</span>
                            <span id="drawerTrackCounter"></span>
                        </div>
                        <div class="playlist-progress">
                            <div class="progress-bar" id="progressBar"></div>
                        </div>
                    </div>
                    
                    <div class="playlist-tracks" id="playlistTracks">
                        <!-- Audio tracks will be dynamically populated here -->
                    </div>
                </div>
            </aside>
            
            <!-- Backdrop -->
            <div id="backdrop" class="backdrop" hidden></div>
            
            
            <!-- Track Selector Dropdown -->
            <div id="trackSelectorModal" class="track-selector-modal" hidden style="display: none;">
                <div class="track-selector-content">
                    <div class="track-selector-header">
                        <h3>🎵 Select Audio Track</h3>
                        <button id="closeTrackSelector" class="close-btn">✕</button>
                    </div>
                    <div class="track-selector-list" id="trackSelectorList">
                        <!-- Tracks will be populated here -->
                    </div>
                </div>
            </div>
                
                <!-- Reports Container -->
                <div class="reports-container">
                    <div class="section-title">
                        📊 Available Reports
                    </div>
"""
            
            if html_files:
                index_html += '<div class="report-grid" id="reportGrid">'
                for file_path in html_files:
                    mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    time_str = mtime.strftime('%B %d, %Y at %H:%M')
                    time_ago = self._time_ago(mtime)
                    file_size = file_path.stat().st_size / 1024  # KB
                    
                    # Try to extract video ID and title from filename and HTML content
                    display_name = file_path.stem
                    video_id = None
                    youtube_url = None
                    actual_title = None
                    
                    # Try to extract title, URL, model, channel, and summary type from HTML file content
                    used_model = "Unknown"
                    used_channel = "Unknown"
                    summary_type = "Unknown"
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            html_content = f.read()
                            
                        # Extract video title from HTML <title> tag
                        import re
                        title_match = re.search(r'<title>(.*?)</title>', html_content, re.IGNORECASE)
                        if title_match:
                            actual_title = title_match.group(1).strip()
                            
                        # Extract YouTube URL from HTML content
                        url_match = re.search(r'https://www\.youtube\.com/watch\?v=([a-zA-Z0-9_-]+)', html_content)
                        if url_match:
                            video_id = url_match.group(1)
                            youtube_url = f"https://www.youtube.com/watch?v={video_id}"
                            
                        # Extract model from HTML content - try multiple patterns
                        model_patterns = [
                            # Current format with emoji
                            r'<div class="info-label">🤖 Model:</div>\s*<div class="info-value">([^<]+)</div>',
                            # New info-grid pattern (most recent format)
                            r'<div class="info-label">AI Model</div>\s*<div class="info-value">([^<]+)</div>',
                            # Also try AI Provider pattern for older reports
                            r'<div class="info-label">AI Provider</div>\s*<div class="info-value">([^<]+)</div>',
                            # Legacy patterns for backward compatibility
                            r'Model:\s*</strong>\s*([^<]+)',  # Original pattern
                            r'Model:\s*([^<\n]+)',           # Without </strong>
                            r'<strong>Model:</strong>\s*([^<\n]+)',  # With strong tags
                            r'Model:\s*<strong>([^<]+)</strong>',    # Model in strong
                        ]
                        
                        for pattern in model_patterns:
                            model_match = re.search(pattern, html_content, re.IGNORECASE)
                            if model_match:
                                used_model = model_match.group(1).strip()
                                logger.debug(f"🔍 Extracted model '{used_model}' from {file_path.name}")
                                break
                        
                        # Extract channel from HTML content  
                        channel_patterns = [
                            # Look for channel name in header section
                            r'<div class="channel">([^<]+)</div>',
                            # Look for "uploader" metadata
                            r'"uploader":\s*"([^"]+)"',
                            # Look for uploader in older formats
                            r'Channel:\s*([^<\n]+)',
                            r'Uploader:\s*([^<\n]+)',
                        ]
                        
                        for pattern in channel_patterns:
                            channel_match = re.search(pattern, html_content, re.IGNORECASE)
                            if channel_match:
                                used_channel = channel_match.group(1).strip()
                                logger.debug(f"🔍 Extracted channel '{used_channel}' from {file_path.name}")
                                break
                        
                        # Extract summary type from HTML content - look for "Summary (Type)" in h2 tags
                        summary_patterns = [
                            r'📝 Summary \(([^)]+)\)',  # "📝 Summary (Comprehensive)"
                            r'Summary \(([^)]+)\)',    # "Summary (Audio)"
                        ]
                        
                        for pattern in summary_patterns:
                            summary_match = re.search(pattern, html_content, re.IGNORECASE)
                            if summary_match:
                                summary_type = summary_match.group(1).strip().title()
                                logger.debug(f"🔍 Extracted summary type '{summary_type}' from {file_path.name}")
                                break
                        
                        # Extract summary preview (first meaningful paragraph)
                        summary_preview = ""
                        preview_patterns = [
                            # Look for content in summary sections
                            r'<div class="summary-content">(.*?)</div>',
                            # Look for first paragraph with substantial content
                            r'<p>([^<]{50,200})</p>'
                        ]
                        
                        for pattern in preview_patterns:
                            matches = re.findall(pattern, html_content, re.IGNORECASE | re.DOTALL)
                            for match in matches:
                                # Clean HTML tags and get first meaningful text
                                clean_text = re.sub(r'<[^>]+>', '', match)
                                clean_text = re.sub(r'\s+', ' ', clean_text).strip()
                                if len(clean_text) > 30 and not clean_text.startswith('**') and 'generated' not in clean_text.lower():
                                    summary_preview = clean_text[:120] + "..." if len(clean_text) > 120 else clean_text
                                    break
                            if summary_preview:
                                break
                        
                        if not summary_preview:
                            summary_preview = "AI-generated summary available..."

                        if used_model == "Unknown":
                            logger.warning(f"🔍 Could not extract model from {file_path.name}")
                        if summary_type == "Unknown":
                            logger.warning(f"🔍 Could not extract summary type from {file_path.name}")
                    except Exception as e:
                        logger.warning(f"Could not extract info from {file_path.name}: {e}")
                    
                    # Use actual title if found, otherwise fall back to filename parsing
                    if actual_title:
                        display_name = actual_title
                    elif '_' in display_name:
                        parts = display_name.split('_')
                        if len(parts) >= 2:
                            # First part is video ID, last part is timestamp
                            video_id = parts[0]
                            if not youtube_url:  # Only create URL if not already found
                                youtube_url = f"https://www.youtube.com/watch?v={video_id}"
                            # Try to create a readable title from video ID
                            if len(video_id) > 3:
                                display_name = f"Video {video_id[:8]}..." if len(video_id) > 8 else video_id
                    
                    # Extract video ID for thumbnail if not already found
                    if not video_id and youtube_url:
                        video_id = self.extract_video_id(youtube_url)
                    
                    # Get thumbnail URL and model badge info
                    thumbnail_url = self.get_thumbnail_url(video_id) if video_id else None
                    model_badge_text = self.get_model_badge(used_model)
                    model_badge_class = self.get_model_badge_class(used_model)
                    
                    # Generate thumbnail HTML with click handlers
                    thumbnail_html = ""
                    if thumbnail_url:
                        thumbnail_html = f'''
                        <img src="{thumbnail_url}" alt="Video thumbnail" 
                             onclick="openSummary('{file_path.name}')"
                             onerror="this.style.display='none'; this.nextElementSibling.style.display='flex';">
                        <div class="thumbnail-fallback" style="display: none;" onclick="openSummary('{file_path.name}')">📺</div>'''
                    else:
                        thumbnail_html = f'<div class="thumbnail-fallback" onclick="openSummary(\'{file_path.name}\')">📺</div>'
                    
                    index_html += f"""
                <div class="report-card" data-title="{display_name}" data-time="{mtime.timestamp()}" data-filename="{file_path.name}" data-model="{used_model}" data-channel="{used_channel}" data-summary-type="{summary_type}">
                    <div class="card-thumbnail">
                        <input type="checkbox" class="report-checkbox" onchange="toggleDeleteButton()" style="position: absolute; top: 12px; left: 12px; z-index: 10;">
                        <button class="card-delete-btn" onclick="deleteSingleCard('{file_path.name}')" title="Delete this report" style="position: absolute; top: 12px; right: 12px; z-index: 10;">🗑️</button>
                        {thumbnail_html}
                    </div>
                    <div class="card-content">
                        <div class="model-badge {model_badge_class}">{model_badge_text}</div>
                        <div class="report-title" onclick="openSummary('{file_path.name}')">{display_name}</div>
                        <div class="report-metadata">
                            <span>📅 {time_ago}</span>
                            <span>📝 {summary_type}</span>
                        </div>
                        <div class="report-preview">
                            {summary_preview}
                        </div>
                        <div class="report-actions">
                            <a href="/{file_path.name}" class="btn btn-primary">📄 View Summary</a>"""
                    
                    if youtube_url:
                        index_html += f"""
                            <a href="{youtube_url}" class="btn btn-secondary" target="_blank">▶️ Watch</a>"""
                    else:
                        index_html += """
                            <button class="btn btn-outline btn-sm" disabled>🔗 No Link</button>"""
                    
                    index_html += """
                        </div>
                    </div>
                </div>"""
                index_html += '</div>' # Close report-grid
            else:
                index_html += """
                <div class="empty-state">
                    <div class="empty-state-icon">📭</div>
                    <h3>No Reports Available</h3>
                    <p>Generate your first YouTube summary using the Telegram bot!</p>
                    <p style="margin-top: 15px; color: #9ca3af;">Send a YouTube URL to the bot to get started.</p>
                </div>"""
            
            index_html += """
                </div> <!-- End reports-container -->
            </div> <!-- End main-content -->
        </div>
        
        <div class="footer">
            <p><strong>YouTube Summarizer Bot</strong> • Powered by AI • """ + models_text + """</p>
            <p style="margin-top: 10px;">🔄 Last updated: """ + datetime.now().strftime('%B %d, %Y at %H:%M:%S') + """</p>
        </div>
    </div>
    
    <!-- Custom Delete Confirmation Modal -->
    <div id="deleteModal" class="modal">
        <div class="modal-content">
            <h3>🗑️ Delete Reports</h3>
            <p id="deleteMessage"></p>
            <div class="modal-buttons">
                <button class="modal-btn modal-btn-cancel" onclick="closeModal()">Cancel</button>
                <button class="modal-btn modal-btn-confirm" onclick="confirmDelete()">Delete</button>
            </div>
        </div>
    </div>
    
    <!-- Success Modal -->
    <div id="successModal" class="modal success-modal">
        <div class="modal-content">
            <h3>✅ Success</h3>
            <p>Reports have been deleted successfully!</p>
            <div class="modal-buttons">
                <button class="modal-btn modal-btn-confirm" onclick="reloadPage()">OK</button>
            </div>
        </div>
    </div>
    
    <button class="refresh-btn" onclick="location.reload();" title="Refresh Reports">
        🔄
    </button>
    
    <script>
        // Auto-refresh every 30 seconds - but only when no drawers are open
        function scheduleRefresh() {
            setTimeout(() => {
                // Don't refresh if any drawer is open or playlist is playing
                const filtersDrawer = document.getElementById('filtersDrawer');
                const playlistDrawer = document.getElementById('playlistDrawer');
                const isFiltersOpen = filtersDrawer && !filtersDrawer.hidden;
                const isPlaylistOpen = playlistDrawer && !playlistDrawer.hidden;
                const isPlaylistPlaying = window.playlist && window.playlist.isPlaying;
                
                if (isFiltersOpen || isPlaylistOpen || isPlaylistPlaying) {
                    console.log('⏸️ Skipping auto-refresh - drawer open or playlist playing');
                    // Schedule next check in 10 seconds
                    setTimeout(scheduleRefresh, 10000);
                    return;
                }
                
                // Try to preserve current state by doing a soft refresh
                try {
                    // Clear any problematic URL params before reload
                    const cleanUrl = window.location.origin + window.location.pathname;
                    window.history.replaceState({}, '', cleanUrl);
                    location.reload();
                } catch (error) {
                    // Fallback to clean reload
                    window.location.href = window.location.origin + window.location.pathname;
                }
            }, 30000);
        }
        
        // Start the refresh cycle
        scheduleRefresh();
        
        // Management functions
        function filterReports() {
            var searchInput = document.getElementById('searchInput');
            var searchTerm = searchInput.value.toLowerCase();
            var clearBtn = document.querySelector('.search-clear');
            
            // Show/hide clear button
            clearBtn.style.display = searchTerm ? 'flex' : 'none';
            
            var cards = document.querySelectorAll('.report-card');
            cards.forEach(function(card) {
                var title = card.dataset.title.toLowerCase();
                var filename = card.dataset.filename.toLowerCase();
                var visible = title.includes(searchTerm) || filename.includes(searchTerm);
                card.style.display = visible ? 'block' : 'none';
            });
        }
        
        function clearSearch() {
            var searchInput = document.getElementById('searchInput');
            var clearBtn = document.querySelector('.search-clear');
            
            searchInput.value = '';
            clearBtn.style.display = 'none';
            
            // Show all cards
            var cards = document.querySelectorAll('.report-card');
            cards.forEach(function(card) {
                card.style.display = 'block';
            });
            
            searchInput.focus();
        }
        
        function sortReports() {
            var sortBy = document.getElementById('sortBy').value;
            var grid = document.getElementById('reportGrid');
            var cards = Array.from(document.querySelectorAll('.report-card'));
            
            cards.sort(function(a, b) {
                switch(sortBy) {
                    case 'newest':
                        return parseFloat(b.dataset.time) - parseFloat(a.dataset.time);
                    case 'oldest':
                        return parseFloat(a.dataset.time) - parseFloat(b.dataset.time);
                    case 'title':
                        return a.dataset.title.localeCompare(b.dataset.title);
                    case 'size':
                        return parseFloat(b.dataset.size) - parseFloat(a.dataset.size);
                    default:
                        return 0;
                }
            });
            
            cards.forEach(function(card) { grid.appendChild(card); });
        }
        
        function filterByChip(chipElement, filterValue) {
            // Update chip active states
            document.querySelectorAll('.filter-chip').forEach(function(chip) {
                chip.classList.remove('active');
            });
            chipElement.classList.add('active');
            
            // Filter cards
            var cards = document.querySelectorAll('.report-card');
            console.log('Selected filter:', filterValue);
            
            cards.forEach(function(card) {
                var cardModel = card.dataset.model;
                var visible = filterValue === 'all' || cardModel === filterValue;
                card.style.display = visible ? 'block' : 'none';
            });
            
            // Update visible count and clear selections when filtering
            clearAllSelections();
            var visibleCards = document.querySelectorAll('.report-card[style="display: block"], .report-card:not([style*="display: none"])');
            console.log('Visible cards after filter:', visibleCards.length);
        }
        
        // Legacy function for backward compatibility
        function filterByModel() {
            // This function is kept for any remaining references but chips are now used
            filterByChip(document.querySelector('.filter-chip.active'), 'all');
        }
        
        function selectAll() {
            var checkboxes = document.querySelectorAll('.report-checkbox');
            var allChecked = Array.from(checkboxes).every(function(cb) { return cb.checked; });
            checkboxes.forEach(function(cb) { cb.checked = !allChecked; });
            toggleDeleteButton();
        }
        
        function toggleDeleteButton() {
            var checkboxes = document.querySelectorAll('.report-checkbox');
            var deleteBtn = document.getElementById('deleteBtn');
            var selectAllBtn = document.getElementById('selectAllBtn');
            var anyChecked = Array.from(checkboxes).some(function(cb) { return cb.checked; });
            
            // Update button states
            deleteBtn.disabled = !anyChecked;
            
            // Update card highlighting
            checkboxes.forEach(function(cb) {
                var card = cb.closest('.report-card');
                if (cb.checked) {
                    card.classList.add('selected');
                } else {
                    card.classList.remove('selected');
                }
            });
            
            // Update select all button text
            var allChecked = Array.from(checkboxes).every(function(cb) { return cb.checked; });
            selectAllBtn.textContent = allChecked ? 'Deselect All' : 'Select All';
        }
        
        function clearAllSelections() {
            var checkboxes = document.querySelectorAll('.report-checkbox');
            checkboxes.forEach(function(cb) { 
                cb.checked = false;
                cb.closest('.report-card').classList.remove('selected');
            });
            toggleDeleteButton();
        }
        
        function exportReports(format) {
            var checkedCards = Array.from(document.querySelectorAll('.report-checkbox:checked'));
            if (checkedCards.length === 0) {
                alert('Please select reports to export');
                return;
            }
            
            var filenames = checkedCards.map(function(cb) {
                return cb.closest('.report-card').dataset.filename;
            });
            
            console.log('Exporting', filenames.length, 'reports in', format, 'format');
            // TODO: Implement actual export functionality
            alert('Export feature coming soon! Selected ' + filenames.length + ' reports for ' + format.toUpperCase() + ' export.');
        }
        
        function openSummary(filename) {
            // Navigate to the summary page
            window.location.href = '/' + filename;
        }
        
        var selectedFiles = []; // Store selected files for deletion
        
        function deleteSingleCard(filename) {
            // Show confirmation modal for single card deletion
            selectedFiles = [filename];
            document.getElementById('deleteMessage').textContent = 
                'Are you sure you want to delete this report?';
            document.getElementById('deleteModal').style.display = 'block';
        }
        
        function deleteSelected() {
            var checkboxes = document.querySelectorAll('.report-checkbox:checked');
            if (checkboxes.length === 0) return;
            
            selectedFiles = Array.from(checkboxes).map(function(cb) {
                return cb.closest('.report-card').dataset.filename;
            });
            
            // Show custom confirmation modal
            document.getElementById('deleteMessage').textContent = 
                'Are you sure you want to delete ' + selectedFiles.length + ' selected report(s)?';
            document.getElementById('deleteModal').style.display = 'block';
        }
        
        function closeModal() {
            document.getElementById('deleteModal').style.display = 'none';
            document.getElementById('successModal').style.display = 'none';
        }
        
        function confirmDelete() {
            // Send delete request to server
            fetch('/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    action: 'delete',
                    files: selectedFiles
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Hide selected cards with animation only after successful server deletion
                    selectedFiles.forEach(function(filename) {
                        var card = document.querySelector('[data-filename="' + filename + '"]');
                        if (card) {
                            card.style.transition = 'all 0.5s ease';
                            card.style.opacity = '0';
                            card.style.transform = 'scale(0.8)';
                            setTimeout(function() {
                                card.style.display = 'none';
                            }, 500);
                        }
                    });
                    
                    // Close delete modal and show success modal
                    document.getElementById('deleteModal').style.display = 'none';
                    document.getElementById('successModal').style.display = 'block';
                    
                    // Update button state
                    toggleDeleteButton();
                } else {
                    // Show error message
                    alert('Error deleting files: ' + (data.message || 'Unknown error'));
                    document.getElementById('deleteModal').style.display = 'none';
                }
            })
            .catch(error => {
                console.error('Delete request failed:', error);
                alert('Failed to delete files. Please try again.');
                document.getElementById('deleteModal').style.display = 'none';
            });
        }
        
        function reloadPage() {
            location.reload();
        }
        
        // Add subtle animations and modal event handlers
        document.addEventListener('DOMContentLoaded', function() {
            const cards = document.querySelectorAll('.report-card, .stat-card');
            cards.forEach((card, index) => {
                card.style.opacity = '0';
                card.style.transform = 'translateY(20px)';
                setTimeout(() => {
                    card.style.transition = 'all 0.5s ease';
                    card.style.opacity = '1';
                    card.style.transform = 'translateY(0)';
                }, index * 100);
            });
            
            // Floating controls scroll detection
            const controlsBar = document.querySelector('.controls-bar');
            let lastScrollY = window.scrollY;
            
            function handleScroll() {
                const currentScrollY = window.scrollY;
                
                if (currentScrollY > 100) {
                    controlsBar.classList.add('scrolled');
                } else {
                    controlsBar.classList.remove('scrolled');
                }
                
                lastScrollY = currentScrollY;
            }
            
            window.addEventListener('scroll', handleScroll);
            
            // Close modal when clicking outside
            document.getElementById('deleteModal').addEventListener('click', function(e) {
                if (e.target === this) closeModal();
            });
            document.getElementById('successModal').addEventListener('click', function(e) {
                if (e.target === this) closeModal();
            });
            
            // Initialize filter system
            initializeFilterSystem();
        });
        
        // ===== OFF-CANVAS DRAWER FILTER SYSTEM =====
        
        // Global filter state
        const filterState = {
            models: new Set(),
            channels: new Set(),
            initialized: false
        };
        
        // Debounce timer for auto-apply
        let autoApplyTimer = null;
        
        // Slug mapping for URL persistence 
        const slugMaps = {
            models: new Map(),
            channels: new Map(),
            modelSlugs: new Map(), // reverse lookup
            channelSlugs: new Map() // reverse lookup
        };
        
        // Create safe URL slugs
        function createSlug(text) {
            return text.toLowerCase().trim()
                .replace(/[:/\(\)\[\]{}]/g, '-') // Replace problematic chars
                .replace(/[^a-z0-9- ]/g, '')     // Remove non-alphanumeric
                .replace(/\s+/g, '-')            // Spaces to dashes
                .replace(/--+/g, '-')            // Multiple dashes to single
                .replace(/^-+|-+$/g, '')         // Trim dashes
                .substring(0, 20);               // Limit length
        }
        
        // Initialize slug mappings with collision detection
        function initializeSlugs() {
            // Clear existing mappings
            slugMaps.models.clear();
            slugMaps.channels.clear(); 
            slugMaps.modelSlugs.clear();
            slugMaps.channelSlugs.clear();
            
            const usedSlugs = new Set();
            
            // Helper function to create unique slug
            function createUniqueSlug(text, type) {
                let baseSlug = createSlug(text);
                let finalSlug = baseSlug;
                let counter = 1;
                
                // Handle collisions
                while (usedSlugs.has(finalSlug)) {
                    finalSlug = `${baseSlug}-${counter}`;
                    counter++;
                }
                
                usedSlugs.add(finalSlug);
                return finalSlug;
            }
            
            // Map models with unique slugs
            document.querySelectorAll('#modelsList input[type="checkbox"]').forEach(cb => {
                const original = cb.value;
                const slug = createUniqueSlug(original, 'model');
                slugMaps.models.set(original, slug);
                slugMaps.modelSlugs.set(slug, original);
            });
            
            // Map channels with unique slugs
            document.querySelectorAll('#channelsList input[type="checkbox"]').forEach(cb => {
                const original = cb.value;
                const slug = createUniqueSlug(original, 'channel');
                slugMaps.channels.set(original, slug);
                slugMaps.channelSlugs.set(slug, original);
            });
            
            console.log('Initialized slugs:', { 
                models: slugMaps.models.size, 
                channels: slugMaps.channels.size 
            });
        }
        
        // Initialize filter system on page load
        function initializeFilterSystem() {
            if (filterState.initialized) return;
            
            const drawer = document.getElementById('filtersDrawer');
            const backdrop = document.getElementById('backdrop');
            const btnFilters = document.getElementById('btnFilters');
            const closeFilters = document.getElementById('closeFilters');
            const applyFilters = document.getElementById('applyFilters');
            const clearAllFilters = document.getElementById('clearAllFilters');
            
            // Initialize slug mappings
            initializeSlugs();
            
            // Initialize all checkboxes as checked (show all)
            document.querySelectorAll('#modelsList input[type="checkbox"], #channelsList input[type="checkbox"]').forEach(cb => {
                cb.checked = true;
                if (cb.closest('#modelsList')) {
                    filterState.models.add(cb.value);
                } else {
                    filterState.channels.add(cb.value);
                }
            });
            
            // Drawer controls
            btnFilters.addEventListener('click', openDrawer);
            closeFilters.addEventListener('click', closeDrawer);
            backdrop.addEventListener('click', (e) => {
                // Close whichever drawer is currently open
                const filtersDrawer = document.getElementById('filtersDrawer');
                const playlistDrawer = document.getElementById('playlistDrawer');
                
                if (filtersDrawer && !filtersDrawer.hidden && filtersDrawer.classList.contains('open')) {
                    closeDrawer();
                } else if (playlistDrawer && !playlistDrawer.hidden && playlistDrawer.classList.contains('open')) {
                    playlist.closeDrawer();
                }
            });
            applyFilters.addEventListener('click', applyFiltersAndClose);
            clearAllFilters.addEventListener('click', clearAllFiltersAction);
            
            // Group actions (Select All / Clear) with multiple event handling approaches
            // Method 1: Direct delegation
            drawer.addEventListener('click', (e) => {
                // Handle Select All buttons
                if (e.target.matches('[data-select-all]') || e.target.closest('[data-select-all]')) {
                    e.preventDefault();
                    e.stopPropagation();
                    const button = e.target.matches('[data-select-all]') ? e.target : e.target.closest('[data-select-all]');
                    const group = button.getAttribute('data-select-all');
                    console.log('Select All button clicked for group:', group);
                    selectAllInGroup(group);
                    return;
                }
                
                // Handle Clear buttons
                if (e.target.matches('[data-clear]') || e.target.closest('[data-clear]')) {
                    e.preventDefault();
                    e.stopPropagation();
                    const button = e.target.matches('[data-clear]') ? e.target : e.target.closest('[data-clear]');
                    const group = button.getAttribute('data-clear');
                    console.log('Clear button clicked for group:', group);
                    clearGroup(group);
                    return;
                }
            });
            
            // Method 2: Direct button binding as backup
            setTimeout(() => {
                document.querySelectorAll('[data-select-all]').forEach(btn => {
                    btn.onclick = (e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        const group = btn.getAttribute('data-select-all');
                        console.log('Direct Select All clicked:', group);
                        selectAllInGroup(group);
                    };
                });
                
                document.querySelectorAll('[data-clear]').forEach(btn => {
                    btn.onclick = (e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        const group = btn.getAttribute('data-clear');
                        console.log('Direct Clear clicked:', group);
                        clearGroup(group);
                    };
                });
            }, 100);
            
            // Auto-apply filter changes with debounce
            drawer.addEventListener('change', (e) => {
                if (e.target.matches('input[type="checkbox"]')) {
                    const isModel = e.target.closest('#modelsList');
                    const type = isModel ? 'models' : 'channels';
                    updateFilterState(type, e.target.value, e.target.checked);
                    
                    // Auto-apply with debounce
                    clearTimeout(autoApplyTimer);
                    autoApplyTimer = setTimeout(() => {
                        autoApplyFilters();
                    }, 250);
                }
            });
            
            // Mini-search functionality
            document.querySelectorAll('.mini-search').forEach(input => {
                input.addEventListener('input', (e) => {
                    const listId = e.target.getAttribute('data-filter-list');
                    filterCheckboxList(listId, e.target.value);
                });
            });
            
            // Keyboard support
            drawer.addEventListener('keydown', handleDrawerKeydown);
            
            // Load state from URL/localStorage
            loadFilterStateFromURL();
            
            // Initial filter application
            applyCurrentFilters();
            updateUI();
            
            filterState.initialized = true;
        }
        
        // Drawer open/close functions
        function openDrawer() {
            const drawer = document.getElementById('filtersDrawer');
            const backdrop = document.getElementById('backdrop');
            const btnFilters = document.getElementById('btnFilters');
            
            drawer.hidden = false;
            backdrop.hidden = false;
            
            // Trigger reflow before adding classes for animation
            drawer.offsetHeight;
            
            drawer.classList.add('open');
            backdrop.classList.add('visible');
            btnFilters.setAttribute('aria-expanded', 'true');
            
            // Focus first focusable element
            const firstFocusable = drawer.querySelector('button, input, [tabindex]');
            if (firstFocusable) firstFocusable.focus();
        }
        
        function closeDrawer() {
            const drawer = document.getElementById('filtersDrawer');
            const backdrop = document.getElementById('backdrop');
            const btnFilters = document.getElementById('btnFilters');
            
            drawer.classList.remove('open');
            backdrop.classList.remove('visible');
            btnFilters.setAttribute('aria-expanded', 'false');
            
            setTimeout(() => {
                drawer.hidden = true;
                backdrop.hidden = true;
            }, 220); // Match CSS transition duration
            
            btnFilters.focus(); // Return focus to trigger button
        }
        
        // Filter state management
        function updateFilterState(type, value, checked) {
            if (checked) {
                filterState[type].add(value);
            } else {
                filterState[type].delete(value);
            }
            updateUI();
        }
        
        function selectAllInGroup(group) {
            console.log('selectAllInGroup called with:', group);
            const listId = group === 'models' ? '#modelsList' : '#channelsList';
            const checkboxes = document.querySelectorAll(`${listId} input[type="checkbox"]`);
            console.log(`Found ${checkboxes.length} checkboxes to select in ${listId}`);
            
            // Clear and repopulate the filter state efficiently
            if (group === 'models') {
                filterState.models.clear();
            } else {
                filterState.channels.clear();
            }
            
            // Check all checkboxes and add to state
            checkboxes.forEach(cb => {
                cb.checked = true;
                if (group === 'models') {
                    filterState.models.add(cb.value);
                } else {
                    filterState.channels.add(cb.value);
                }
            });
            
            console.log(`After selecting all ${group}:`, {
                models: filterState.models.size,
                channels: filterState.channels.size
            });
            
            updateUI();
            
            // Auto-apply the change
            clearTimeout(autoApplyTimer);
            autoApplyTimer = setTimeout(() => {
                autoApplyFilters();
            }, 250);
        }
        
        function clearGroup(group) {
            console.log('clearGroup called with:', group);
            const listId = group === 'models' ? '#modelsList' : '#channelsList';
            const checkboxes = document.querySelectorAll(`${listId} input[type="checkbox"]`);
            console.log(`Found ${checkboxes.length} checkboxes to clear in ${listId}`);
            
            // Clear the filter state efficiently
            if (group === 'models') {
                filterState.models.clear();
            } else {
                filterState.channels.clear();
            }
            
            // Uncheck all checkboxes
            checkboxes.forEach(cb => {
                cb.checked = false;
            });
            
            console.log(`After clearing ${group}:`, {
                models: filterState.models.size,
                channels: filterState.channels.size
            });
            
            updateUI();
            
            // Auto-apply the change
            clearTimeout(autoApplyTimer);
            autoApplyTimer = setTimeout(() => {
                autoApplyFilters();
            }, 250);
        }
        
        function clearAllFiltersAction() {
            selectAllInGroup('models');
            selectAllInGroup('channels');
        }
        
        // Apply filters and update display
        function applyCurrentFilters() {
            const cards = document.querySelectorAll('.report-card');
            let visibleCount = 0;
            
            cards.forEach(card => {
                const cardModel = card.dataset.model;
                const cardChannel = card.dataset.channel || 'Unknown';
                
                const modelMatch = filterState.models.size === 0 || filterState.models.has(cardModel);
                const channelMatch = filterState.channels.size === 0 || filterState.channels.has(cardChannel);
                
                const visible = modelMatch && channelMatch;
                card.style.display = visible ? 'block' : 'none';
                
                if (visible) visibleCount++;
            });
            
            console.log(`Applied filters: ${visibleCount} cards visible`);
        }
        
        function applyFiltersAndClose() {
            applyCurrentFilters();
            updateActiveFilterChips();
            saveFilterStateToURL();
            closeDrawer();
        }
        
        // Auto-apply filters without closing drawer
        function autoApplyFilters() {
            applyCurrentFilters();
            updateActiveFilterChips();
            saveFilterStateToURL();
            showAutoApplyFeedback();
        }
        
        // Show subtle feedback for auto-apply
        function showAutoApplyFeedback() {
            const toolbar = document.querySelector('.toolbar');
            if (!toolbar) return;
            
            // Add a subtle loading indicator
            const indicator = document.createElement('div');
            indicator.className = 'auto-apply-indicator';
            indicator.textContent = '✓ Filters applied';
            indicator.style.cssText = `
                position: absolute;
                top: -30px;
                left: 50%;
                transform: translateX(-50%);
                background: #10b981;
                color: white;
                padding: 4px 12px;
                border-radius: 12px;
                font-size: 0.8em;
                opacity: 0;
                transition: all 0.3s ease;
                z-index: 1100;
            `;
            
            toolbar.style.position = 'relative';
            toolbar.appendChild(indicator);
            
            // Show and hide the indicator
            requestAnimationFrame(() => {
                indicator.style.opacity = '1';
                indicator.style.top = '-25px';
            });
            
            setTimeout(() => {
                indicator.style.opacity = '0';
                indicator.style.top = '-35px';
                setTimeout(() => {
                    if (indicator.parentNode) {
                        indicator.parentNode.removeChild(indicator);
                    }
                }, 300);
            }, 1500);
        }
        
        // UI Updates
        function updateUI() {
            updateGroupCounts();
            updateFilterBadge();
            updateSelectedCount();
        }
        
        function updateGroupCounts() {
            document.querySelector('[data-count-for="models"]').textContent = 
                `(${document.querySelectorAll('#modelsList input:checked').length}/${document.querySelectorAll('#modelsList input').length})`;
                
            document.querySelector('[data-count-for="channels"]').textContent = 
                `(${document.querySelectorAll('#channelsList input:checked').length}/${document.querySelectorAll('#channelsList input').length})`;
        }
        
        function updateFilterBadge() {
            const badge = document.getElementById('filterBadge');
            const btnFilters = document.getElementById('btnFilters');
            const totalModels = document.querySelectorAll('#modelsList input').length;
            const totalChannels = document.querySelectorAll('#channelsList input').length;
            const selectedModels = filterState.models.size;
            const selectedChannels = filterState.channels.size;
            
            const activeFilters = (totalModels - selectedModels) + (totalChannels - selectedChannels);
            
            if (activeFilters > 0) {
                badge.textContent = activeFilters;
                badge.style.display = 'inline-flex';
                btnFilters.textContent = `🔎 Filters • ${activeFilters}`;
            } else {
                badge.style.display = 'none';
                btnFilters.textContent = '🔎 Filters';
            }
        }
        
        function updateSelectedCount() {
            const totalModels = document.querySelectorAll('#modelsList input').length;
            const totalChannels = document.querySelectorAll('#channelsList input').length;
            const selectedModels = filterState.models.size;
            const selectedChannels = filterState.channels.size;
            
            const selectedCount = document.getElementById('selectedCount');
            if (selectedModels === totalModels && selectedChannels === totalChannels) {
                selectedCount.textContent = 'All items selected';
            } else {
                selectedCount.textContent = `${selectedModels + selectedChannels} items selected`;
            }
        }
        
        function updateActiveFilterChips() {
            const container = document.getElementById('activeFilters');
            container.innerHTML = '';
            
            // Add model filter chips
            const totalModels = document.querySelectorAll('#modelsList input').length;
            if (filterState.models.size > 0 && filterState.models.size < totalModels) {
                filterState.models.forEach(model => {
                    const displayName = getModelDisplayName(model);
                    container.innerHTML += `
                        <div class="chip">
                            <span class="chip-label">${displayName}</span>
                            <button class="chip-remove" onclick="removeFilter('models', '${model}')">×</button>
                        </div>
                    `;
                });
            }
            
            // Add channel filter chips  
            const totalChannels = document.querySelectorAll('#channelsList input').length;
            if (filterState.channels.size > 0 && filterState.channels.size < totalChannels) {
                filterState.channels.forEach(channel => {
                    const displayName = channel.length > 20 ? channel.substring(0, 17) + '...' : channel;
                    container.innerHTML += `
                        <div class="chip">
                            <span class="chip-label">${displayName}</span>
                            <button class="chip-remove" onclick="removeFilter('channels', '${channel}')">×</button>
                        </div>
                    `;
                });
            }
        }
        
        function removeFilter(type, value) {
            filterState[type].delete(value);
            
            // Update corresponding checkbox
            const listId = type === 'models' ? '#modelsList' : '#channelsList';
            const checkbox = document.querySelector(`${listId} input[value="${value}"]`);
            if (checkbox) checkbox.checked = false;
            
            updateUI();
            applyCurrentFilters();
            updateActiveFilterChips();
            saveFilterStateToURL();
        }
        
        function getModelDisplayName(model) {
            // Reuse existing model badge function for consistent display
            return model.split('/').pop().split('-')[0].toUpperCase().substring(0, 8);
        }
        
        // Mini-search functionality
        function filterCheckboxList(listSelector, query) {
            const items = document.querySelectorAll(`${listSelector} .checkbox-item`);
            const lowerQuery = query.toLowerCase();
            
            items.forEach(item => {
                const labelText = item.querySelector('.label-text').textContent.toLowerCase();
                const matches = labelText.includes(lowerQuery);
                item.style.display = matches ? 'block' : 'none';
            });
        }
        
        // URL State persistence with short slugs - conservative approach
        function saveFilterStateToURL() {
            try {
                const totalModels = document.querySelectorAll('#modelsList input').length;
                const totalChannels = document.querySelectorAll('#channelsList input').length;
                
                // Always save to localStorage first
                localStorage.setItem('yt-summary-filters', JSON.stringify({
                    models: Array.from(filterState.models),
                    channels: Array.from(filterState.channels)
                }));
                
                // Only update URL if we have active filters (not showing all)
                const hasActiveFilters = (filterState.models.size < totalModels) || 
                                       (filterState.channels.size < totalChannels);
                
                if (!hasActiveFilters) {
                    // If showing all items, use clean URL
                    const cleanUrl = window.location.origin + window.location.pathname;
                    window.history.replaceState({}, '', cleanUrl);
                    return;
                }
                
                // Convert to safe slugs for URL
                const modelSlugs = Array.from(filterState.models)
                    .map(model => slugMaps.models.get(model))
                    .filter(Boolean)
                    .slice(0, 10); // Limit to prevent long URLs
                
                const channelSlugs = Array.from(filterState.channels)
                    .map(channel => slugMaps.channels.get(channel))
                    .filter(Boolean)
                    .slice(0, 10); // Limit to prevent long URLs
                
                // Conservative URL building with length checks
                const baseUrl = window.location.origin + window.location.pathname;
                let urlParams = [];
                
                if (modelSlugs.length > 0 && modelSlugs.length < totalModels) {
                    const paramValue = modelSlugs.join(',');
                    if (paramValue.length < 200) { // Conservative length limit
                        urlParams.push(`m=${encodeURIComponent(paramValue)}`);
                    }
                }
                
                if (channelSlugs.length > 0 && channelSlugs.length < totalChannels) {
                    const paramValue = channelSlugs.join(',');
                    if (paramValue.length < 200) { // Conservative length limit
                        urlParams.push(`c=${encodeURIComponent(paramValue)}`);
                    }
                }
                
                const finalUrl = urlParams.length > 0 
                    ? `${baseUrl}?${urlParams.join('&')}`
                    : baseUrl;
                
                // Final safety check
                if (finalUrl.length < 1500) {
                    window.history.replaceState({}, '', finalUrl);
                } else {
                    // If still too long, just use clean URL and rely on localStorage
                    console.log('URL too long, using localStorage only');
                    window.history.replaceState({}, '', baseUrl);
                }
                
            } catch (error) {
                console.warn('Failed to save filter state to URL:', error);
                // Fallback to clean URL
                const cleanUrl = window.location.origin + window.location.pathname;
                window.history.replaceState({}, '', cleanUrl);
            }
        }
        
        function loadFilterStateFromURL() {
            try {
                let state = {};
                
                // 1) Try localStorage first (most reliable)
                try {
                    const stored = JSON.parse(localStorage.getItem('yt-summary-filters') || '{}');
                    if (stored.models || stored.channels) {
                        state.models = stored.models || [];
                        state.channels = stored.channels || [];
                        console.log('Loaded state from localStorage');
                    }
                } catch (e) {
                    console.warn('Failed to load from localStorage:', e);
                }
                
                // 2) Try query params (only if localStorage empty)
                if ((!state.models || state.models.length === 0) && (!state.channels || state.channels.length === 0)) {
                    const params = new URLSearchParams(window.location.search);
                    
                    if (params.has('m')) {
                        try {
                            const modelSlugs = decodeURIComponent(params.get('m')).split(',').filter(Boolean);
                            const modelValues = modelSlugs
                                .map(slug => slugMaps.modelSlugs.get(slug))
                                .filter(Boolean);
                            if (modelValues.length > 0) {
                                state.models = modelValues;
                                console.log('Loaded models from URL:', modelValues.length);
                            }
                        } catch (e) {
                            console.warn('Failed to parse model params:', e);
                        }
                    }
                    
                    if (params.has('c')) {
                        try {
                            const channelSlugs = decodeURIComponent(params.get('c')).split(',').filter(Boolean);
                            const channelValues = channelSlugs
                                .map(slug => slugMaps.channelSlugs.get(slug))
                                .filter(Boolean);
                            if (channelValues.length > 0) {
                                state.channels = channelValues;
                                console.log('Loaded channels from URL:', channelValues.length);
                            }
                        } catch (e) {
                            console.warn('Failed to parse channel params:', e);
                        }
                    }
                }
                
                // Apply loaded state or default to all selected
                if (state.models && state.models.length > 0) {
                    // Clear and set specific models
                    filterState.models.clear();
                    state.models.forEach(model => {
                        if (model && typeof model === 'string') {
                            filterState.models.add(model);
                        }
                    });
                    
                    // Get all available models from DOM
                    const allAvailableModels = new Set();
                    document.querySelectorAll('#modelsList input').forEach(cb => {
                        allAvailableModels.add(cb.value);
                    });
                    
                    // Add any NEW models that weren't in the saved state (auto-select new models)
                    allAvailableModels.forEach(model => {
                        if (!state.models.includes(model)) {
                            filterState.models.add(model);
                            console.log(`Auto-selecting new model: ${model}`);
                        }
                    });
                    
                    // Update checkboxes
                    document.querySelectorAll('#modelsList input').forEach(cb => {
                        cb.checked = filterState.models.has(cb.value);
                    });
                } else {
                    // Default: select all models
                    document.querySelectorAll('#modelsList input').forEach(cb => {
                        cb.checked = true;
                        filterState.models.add(cb.value);
                    });
                }
                
                if (state.channels && state.channels.length > 0) {
                    // Clear and set specific channels
                    filterState.channels.clear();
                    state.channels.forEach(channel => {
                        if (channel && typeof channel === 'string') {
                            filterState.channels.add(channel);
                        }
                    });
                    
                    // Get all available channels from DOM
                    const allAvailableChannels = new Set();
                    document.querySelectorAll('#channelsList input').forEach(cb => {
                        allAvailableChannels.add(cb.value);
                    });
                    
                    // Add any NEW channels that weren't in the saved state (auto-select new channels)
                    allAvailableChannels.forEach(channel => {
                        if (!state.channels.includes(channel)) {
                            filterState.channels.add(channel);
                            console.log(`🔥 AUTO-SELECTING NEW CHANNEL: ${channel}`);
                        }
                    });
                    console.log(`📊 Channel filter state - Saved: [${state.channels.join(', ')}], Available: [${Array.from(allAvailableChannels).join(', ')}], Final: [${Array.from(filterState.channels).join(', ')}]`);
                    
                    // Update checkboxes
                    document.querySelectorAll('#channelsList input').forEach(cb => {
                        cb.checked = filterState.channels.has(cb.value);
                    });
                } else {
                    // Default: select all channels
                    document.querySelectorAll('#channelsList input').forEach(cb => {
                        cb.checked = true;
                        filterState.channels.add(cb.value);
                    });
                }
                
            } catch (error) {
                console.warn('Failed to load filter state:', error);
                // Ultimate fallback: select all items
                document.querySelectorAll('#modelsList input, #channelsList input').forEach(cb => {
                    cb.checked = true;
                    const isModel = cb.closest('#modelsList');
                    if (isModel) {
                        filterState.models.add(cb.value);
                    } else {
                        filterState.channels.add(cb.value);
                    }
                });
            }
        }
        
        // Keyboard support
        function handleDrawerKeydown(e) {
            if (e.key === 'Escape') {
                closeDrawer();
                e.preventDefault();
            }
        }
        
        // Legacy compatibility functions
        function applyFilters() {
            applyCurrentFilters();
        }
        
        function clearAllFilters() {
            clearAllFiltersAction();
        }
        
        function filterByChip(chipElement, filterValue) {
            // Deprecated - drawer system handles filtering now
            console.log('Chip filtering deprecated, using drawer system');
        }
        
        // Playlist functionality
        const playlist = {
            tracks: [],
            currentIndex: 0,
            isPlaying: false,
            isShuffled: false,
            currentAudio: null,
            hasStartedPlaying: false,
            
            async init() {
                // Initialize playlist drawer controls
                const btnPlaylist = document.getElementById('btnPlaylist');
                const closePlaylist = document.getElementById('closePlaylist');
                const playAllBtn = document.getElementById('playlistPlayAll');
                const shuffleBtn = document.getElementById('playlistShuffle');
                const stopBtn = document.getElementById('playlistStop');
                
                if (btnPlaylist) btnPlaylist.addEventListener('click', () => this.openDrawer());
                if (closePlaylist) closePlaylist.addEventListener('click', () => this.closeDrawer());
                if (playAllBtn) playAllBtn.addEventListener('click', () => this.playAll());
                
                // Initialize mini player controls
                this.initMiniPlayerControls();
                if (shuffleBtn) shuffleBtn.addEventListener('click', () => this.shuffle());
                if (stopBtn) stopBtn.addEventListener('click', () => this.stop());
                
                // Initialize track selector
                this.initTrackSelector();
                
                await this.discoverTracks();
                this.populateDrawer();
                this.updateMiniPlayer(); // Pre-load mini player with most recent audio
            },
            
            async discoverTracks() {
                // Find audio summaries from report cards
                const reportCards = document.querySelectorAll('.report-card');
                const audioTracks = [];
                
                for (const card of reportCards) {
                    if (card.dataset.summaryType === 'Audio') {
                        const filename = card.dataset.filename;
                        if (filename) {
                            // Extract video ID from filename to find corresponding MP3
                            const videoId = filename.match(/([a-zA-Z0-9_-]{11})/);
                            if (videoId) {
                                // Try to find the MP3 file with this video ID
                                const mp3Url = await this.findMp3File(videoId[1]);
                                if (mp3Url) {
                                    const track = {
                                        card: card,
                                        title: card.dataset.title || `Audio Summary ${audioTracks.length + 1}`,
                                        filename: card.dataset.filename || '',
                                        audioUrl: mp3Url,
                                        duration: 0, // Will be updated when audio loads
                                        model: card.dataset.model || 'Unknown',
                                        channel: card.dataset.channel || 'Unknown',
                                        element: null // Will be created dynamically
                                    };
                                    
                                    // Load audio metadata to get duration
                                    const audio = new Audio(mp3Url);
                                    audio.addEventListener('loadedmetadata', () => {
                                        track.duration = audio.duration || 0;
                                        console.log(`✅ Track duration loaded: ${track.title} = ${this.formatTime(track.duration)}`);
                                        
                                        // Update track selector if it's currently open
                                        const trackSelectorModal = document.getElementById('trackSelectorModal');
                                        if (trackSelectorModal && !trackSelectorModal.hidden) {
                                            this.populateTrackSelector();
                                        }
                                    });
                                    audio.addEventListener('error', (e) => {
                                        console.warn(`⚠️ Failed to load metadata for: ${track.title}`);
                                    });
                                    
                                    audioTracks.push(track);
                                }
                            }
                        }
                    }
                }
                
                this.tracks = audioTracks;
                console.log(`📋 Discovered ${this.tracks.length} audio tracks`);
                this.updatePlaylistBadge();
            },
            
            async findMp3File(videoId) {
                console.log(`🔍 Searching for MP3 file with video ID: ${videoId}`);
                
                // Best approach: Extract MP3 filename from the HTML report content
                // Find the HTML report for this video ID
                const reportCards = document.querySelectorAll('.report-card');
                for (const card of reportCards) {
                    if (card.dataset.summaryType === 'Audio') {
                        const filename = card.dataset.filename;
                        if (filename && filename.includes(videoId)) {
                            console.log(`📄 Found HTML file: ${filename}`);
                            
                            try {
                                // Fetch the HTML content and look for the audio source
                                const response = await fetch(`/${filename}`);
                                if (response.ok) {
                                    const html = await response.text();
                                    
                                    // Look for audio player source - could be like:
                                    // src="exports/X-_rG6OtgfU_20250826_014434.mp3" or
                                    // src="https://chief-inspired-lab.ngrok-free.app/exports/X-_rG6OtgfU_20250826_014434.mp3"
                                    const audioMatch = html.match(/src="([^"]*\.mp3)"/);
                                    if (audioMatch) {
                                        let mp3Path = audioMatch[1];
                                        console.log(`🎵 Found MP3 reference in HTML: ${mp3Path}`);
                                        
                                        // If it's a full URL, extract just the path part
                                        if (mp3Path.includes('://')) {
                                            try {
                                                const url = new URL(mp3Path);
                                                mp3Path = url.pathname;
                                            } catch (e) {
                                                console.log(`❌ Could not parse MP3 URL: ${mp3Path}`);
                                                continue;
                                            }
                                        }
                                        
                                        // Ensure path starts with slash
                                        const mp3Url = mp3Path.startsWith('/') ? mp3Path : `/${mp3Path}`;
                                        
                                        // Verify the file exists
                                        const testResponse = await fetch(mp3Url, { method: 'HEAD' });
                                        if (testResponse.ok) {
                                            console.log(`✅ Verified MP3 exists: ${mp3Url}`);
                                            return mp3Url;
                                        } else {
                                            console.log(`❌ MP3 URL not accessible: ${mp3Url}`);
                                        }
                                    } else {
                                        console.log(`❌ No audio src found in HTML`);
                                    }
                                } else {
                                    console.log(`❌ Could not fetch HTML: ${filename}`);
                                }
                            } catch (e) {
                                console.error(`❌ Error processing HTML: ${e}`);
                            }
                        }
                    }
                }
                
                console.log(`❌ No MP3 file found for video ID: ${videoId}`);
                return null;
            },
            
            updatePlaylistBadge() {
                const badge = document.getElementById('playlistBadge');
                const btnPlaylist = document.getElementById('btnPlaylist');
                
                if (this.tracks.length > 0) {
                    if (badge) {
                        badge.textContent = this.tracks.length;
                        badge.style.display = 'inline-flex';
                    }
                } else {
                    if (badge) badge.style.display = 'none';
                }
            },
            
            populateDrawer() {
                const tracksContainer = document.getElementById('playlistTracks');
                if (!tracksContainer || this.tracks.length === 0) {
                    if (tracksContainer) {
                        tracksContainer.innerHTML = '<div style="text-align: center; color: #6c757d; padding: 40px;">No audio summaries found</div>';
                    }
                    return;
                }
                
                tracksContainer.innerHTML = this.tracks.map((track, index) => `
                    <div class="playlist-track" data-index="${index}">
                        <div class="track-header">
                            <div class="track-title">${track.title}</div>
                            <div class="track-duration">🎵</div>
                        </div>
                        <div class="track-meta">
                            <span class="track-model">${track.model}</span>
                            <span class="track-time">Audio Summary</span>
                        </div>
                        <div class="track-controls">
                            <button class="track-play-btn" onclick="playlist.toggleTrack(${index})">
                                ▶ Play
                            </button>
                        </div>
                    </div>
                `).join('');
                
                // Add click handlers for track selection
                tracksContainer.querySelectorAll('.playlist-track').forEach((trackEl, index) => {
                    trackEl.addEventListener('click', (e) => {
                        if (!e.target.classList.contains('track-play-btn')) {
                            this.playTrack(index);
                        }
                    });
                });
            },
            
            async openDrawer() {
                const drawer = document.getElementById('playlistDrawer');
                const backdrop = document.getElementById('backdrop');
                const btnPlaylist = document.getElementById('btnPlaylist');
                
                if (drawer && backdrop && btnPlaylist) {
                    drawer.hidden = false;
                    backdrop.hidden = false;
                    
                    // Trigger reflow before adding classes
                    drawer.offsetHeight;
                    
                    drawer.classList.add('open');
                    backdrop.classList.add('visible');
                    btnPlaylist.setAttribute('aria-expanded', 'true');
                    
                    // Refresh tracks and drawer content
                    await this.discoverTracks();
                    this.populateDrawer();
                }
            },
            
            closeDrawer() {
                const drawer = document.getElementById('playlistDrawer');
                const backdrop = document.getElementById('backdrop');
                const btnPlaylist = document.getElementById('btnPlaylist');
                
                if (drawer && backdrop && btnPlaylist) {
                    drawer.classList.remove('open');
                    backdrop.classList.remove('visible');
                    btnPlaylist.setAttribute('aria-expanded', 'false');
                    
                    setTimeout(() => {
                        drawer.hidden = true;
                        backdrop.hidden = true;
                    }, 220);
                }
            },
            
            playAll() {
                if (this.tracks.length === 0) {
                    alert('No audio summaries found to play');
                    return;
                }
                
                this.isShuffled = false;
                this.currentIndex = 0;
                this.playTrack(0);
            },
            
            shuffle() {
                if (this.tracks.length === 0) {
                    alert('No audio summaries found to shuffle');
                    return;
                }
                
                // Fisher-Yates shuffle
                const shuffled = [...this.tracks];
                for (let i = shuffled.length - 1; i > 0; i--) {
                    const j = Math.floor(Math.random() * (i + 1));
                    [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
                }
                
                this.tracks = shuffled;
                this.isShuffled = true;
                this.currentIndex = 0;
                this.playTrack(0);
            },
            
            playTrack(index) {
                if (index < 0 || index >= this.tracks.length) return;
                
                // Stop current track
                if (this.currentAudio) {
                    this.currentAudio.pause();
                    this.currentAudio.currentTime = 0;
                }
                
                this.currentIndex = index;
                const track = this.tracks[index];
                
                // Create audio element if it doesn't exist
                if (!track.element) {
                    track.element = new Audio(track.audioUrl);
                    track.element.preload = 'metadata';
                }
                
                // Update UI
                this.updatePlaylistUI();
                this.highlightCurrentTrack();
                
                // Setup and play audio
                this.currentAudio = track.element;
                
                // Add event listener for track end
                this.currentAudio.addEventListener('ended', () => this.playNext(), { once: true });
                
                // Play the track
                this.currentAudio.play().then(() => {
                    this.isPlaying = true;
                    this.hasStartedPlaying = true; // Flag that we've started playing audio
                    this.updatePlaylistUI();
                    this.updateMiniPlayer();
                    console.log(`🎵 Playing: ${track.title}`);
                }).catch(err => {
                    console.error('Failed to play track:', err);
                    alert(`Failed to play: ${track.title}`);
                });
            },
            
            toggleTrack(index) {
                // If this track is currently playing, pause/resume
                if (this.currentIndex === index && this.currentAudio) {
                    if (this.isPlaying) {
                        this.pause();
                    } else {
                        this.resume();
                    }
                } else {
                    // Play different track
                    this.playTrack(index);
                }
            },
            
            pause() {
                if (this.currentAudio && this.isPlaying) {
                    this.currentAudio.pause();
                    this.isPlaying = false;
                    this.updatePlaylistUI();
                    this.updateMiniPlayer();
                    console.log('⏸️ Paused');
                }
            },
            
            resume() {
                if (this.currentAudio && !this.isPlaying) {
                    console.log('🎵 Attempting to play audio:', this.currentAudio.src);
                    this.currentAudio.play().then(() => {
                        this.isPlaying = true;
                        this.updatePlaylistUI();
                        this.updateMiniPlayer();
                        console.log('▶️ Resumed playing');
                    }).catch(err => {
                        console.error('Failed to resume:', err);
                        alert(`Failed to play audio: ${err.message}`);
                    });
                } else if (!this.currentAudio) {
                    console.log('❌ No audio loaded');
                } else if (this.isPlaying) {
                    console.log('⚠️ Audio is already playing');
                }
            },
            
            playNext() {
                if (this.currentIndex < this.tracks.length - 1) {
                    this.playTrack(this.currentIndex + 1);
                } else {
                    // Playlist finished
                    this.stop();
                    alert('🎉 Playlist completed!');
                }
            },
            
            playPrevious() {
                if (this.currentIndex > 0) {
                    this.playTrack(this.currentIndex - 1);
                } else {
                    // Go to first track
                    this.playTrack(0);
                }
            },
            
            stop() {
                if (this.currentAudio) {
                    this.currentAudio.pause();
                    this.currentAudio.currentTime = 0;
                }
                
                this.isPlaying = false;
                this.currentAudio = null;
                this.currentIndex = -1;
                this.hasStartedPlaying = false; // Reset the flag when stopping
                
                // Clear progress interval
                if (this.progressInterval) {
                    clearInterval(this.progressInterval);
                    this.progressInterval = null;
                }
                
                // Update UI
                this.updatePlaylistUI();
                this.updateMiniPlayer();
                this.clearHighlights();
                
                console.log('⏹️ Playlist stopped');
            },
            
            updatePlaylistUI() {
                const playlistInfoBar = document.getElementById('playlistInfoBar');
                const stopBtn = document.getElementById('playlistStop');
                const nowPlaying = document.getElementById('drawerNowPlaying');
                const trackCounter = document.getElementById('drawerTrackCounter');
                
                if (this.isPlaying && this.tracks.length > 0) {
                    const track = this.tracks[this.currentIndex];
                    
                    if (playlistInfoBar) playlistInfoBar.style.display = 'block';
                    if (stopBtn) stopBtn.style.display = 'inline-block';
                    if (nowPlaying) nowPlaying.textContent = `♪ ${track.title}`;
                    if (trackCounter) trackCounter.textContent = `${this.currentIndex + 1} / ${this.tracks.length}`;
                    
                    // Update play button states
                    document.querySelectorAll('.track-play-btn').forEach((btn, index) => {
                        if (index === this.currentIndex) {
                            if (this.isPlaying) {
                                btn.textContent = '⏸ Pause';
                                btn.classList.add('playing');
                            } else {
                                btn.textContent = '▶ Resume';
                                btn.classList.add('paused');
                                btn.classList.remove('playing');
                            }
                        } else {
                            btn.textContent = '▶ Play';
                            btn.classList.remove('playing', 'paused');
                        }
                    });
                } else {
                    if (playlistInfoBar) playlistInfoBar.style.display = 'none';
                    if (stopBtn) stopBtn.style.display = 'none';
                    if (nowPlaying) nowPlaying.textContent = '♪ Ready to play';
                    if (trackCounter) trackCounter.textContent = '';
                    
                    // Reset all play buttons
                    document.querySelectorAll('.track-play-btn').forEach(btn => {
                        btn.textContent = '▶ Play';
                        btn.classList.remove('playing');
                    });
                }
            },
            
            highlightCurrentTrack() {
                // Clear existing highlights
                this.clearHighlights();
                
                if (this.currentIndex >= 0 && this.currentIndex < this.tracks.length) {
                    const trackElement = document.querySelector(`.playlist-track[data-index="${this.currentIndex}"]`);
                    if (trackElement) {
                        trackElement.classList.add('current');
                    }
                    
                    // Also highlight on main dashboard if card exists
                    const track = this.tracks[this.currentIndex];
                    if (track.card) {
                        track.card.classList.add('now-playing');
                    }
                }
            },
            
            clearHighlights() {
                document.querySelectorAll('.playlist-track.current').forEach(el => {
                    el.classList.remove('current');
                });
                document.querySelectorAll('.report-card.now-playing').forEach(el => {
                    el.classList.remove('now-playing');
                });
            },
            
            updateMiniPlayer() {
                const miniPlayer = document.getElementById('miniPlayer');
                const miniPlayerTitle = document.getElementById('miniPlayerTitle');
                const miniPlayerCurrentTime = document.getElementById('miniPlayerCurrentTime');
                const miniPlayerDuration = document.getElementById('miniPlayerDuration');
                const miniPlayerRange = document.getElementById('miniPlayerRange');
                const miniTimelineProgress = document.getElementById('miniTimelineProgress');
                const miniPlayerPlay = document.getElementById('miniPlayerPlay');
                
                if (!miniPlayer) return;
                
                // Show mini player if we have tracks available (always visible now)
                if (this.tracks.length > 0) {
                    miniPlayer.hidden = false;
                    
                    // If no current track is selected, pre-load the most recent one
                    if (this.currentIndex < 0 || this.currentIndex >= this.tracks.length) {
                        const track = this.tracks[0]; // Most recent track
                        
                        // Set this as the current track (but don't start playing)
                        this.currentIndex = 0;
                        
                        // Pre-load the audio
                        if (!this.currentAudio || this.currentAudio.src !== track.audioUrl) {
                            if (this.currentAudio) {
                                this.currentAudio.pause();
                            }
                            console.log('🔄 Pre-loading audio:', track.audioUrl);
                            this.currentAudio = new Audio(track.audioUrl);
                            
                            // Set up audio event listeners
                            this.currentAudio.addEventListener('loadedmetadata', () => {
                                console.log('✅ Audio metadata loaded, duration:', this.currentAudio.duration);
                                if (miniPlayerDuration) {
                                    miniPlayerDuration.textContent = this.formatTime(this.currentAudio.duration || 0);
                                }
                            });
                            
                            this.currentAudio.addEventListener('error', (e) => {
                                console.error('❌ Audio loading error:', e);
                            });
                        } else {
                            console.log('♻️ Audio already loaded:', track.audioUrl);
                        }
                        
                        if (miniPlayerTitle) {
                            miniPlayerTitle.textContent = `♪ ${track.title}`;
                        }
                        
                        // Set initial times
                        if (miniPlayerCurrentTime) miniPlayerCurrentTime.textContent = '0:00';
                        if (miniPlayerRange) miniPlayerRange.value = 0;
                        if (miniTimelineProgress) miniTimelineProgress.style.width = '0%';
                        
                        // Set play button to ready state
                        if (miniPlayerPlay) {
                            miniPlayerPlay.textContent = '▶';
                            miniPlayerPlay.title = 'Play';
                        }
                        
                        return;
                    }
                    
                    // Update with current playing track
                    const track = this.tracks[this.currentIndex];
                    const audio = this.currentAudio;
                    
                    // Update title
                    if (miniPlayerTitle) {
                        miniPlayerTitle.textContent = `♪ ${track.title}`;
                    }
                    
                    // Update play/pause button
                    if (miniPlayerPlay) {
                        if (this.isPlaying) {
                            miniPlayerPlay.textContent = '⏸';
                            miniPlayerPlay.title = 'Pause';
                        } else {
                            miniPlayerPlay.textContent = '▶';
                            miniPlayerPlay.title = 'Resume';
                        }
                    }
                    
                    // Update timeline
                    if (audio) {
                        const currentTime = audio.currentTime || 0;
                        const duration = audio.duration || 0;
                        
                        if (miniPlayerCurrentTime) {
                            miniPlayerCurrentTime.textContent = this.formatTime(currentTime);
                        }
                        
                        if (miniPlayerDuration) {
                            miniPlayerDuration.textContent = this.formatTime(duration);
                        }
                        
                        if (miniPlayerRange && duration > 0) {
                            const progress = (currentTime / duration) * 100;
                            miniPlayerRange.value = progress;
                        }
                        
                        if (miniTimelineProgress && duration > 0) {
                            const progress = (currentTime / duration) * 100;
                            miniTimelineProgress.style.width = `${progress}%`;
                        }
                    }
                } else {
                    // Hide mini player if no tracks
                    miniPlayer.hidden = true;
                }
            },
            
            formatTime(seconds) {
                if (isNaN(seconds)) return '0:00';
                const mins = Math.floor(seconds / 60);
                const secs = Math.floor(seconds % 60);
                return `${mins}:${secs.toString().padStart(2, '0')}`;
            },
            
            initMiniPlayerControls() {
                const miniPlayerPrev = document.getElementById('miniPlayerPrev');
                const miniPlayerPlay = document.getElementById('miniPlayerPlay');
                const miniPlayerNext = document.getElementById('miniPlayerNext');
                const miniPlayerClose = document.getElementById('miniPlayerClose');
                const miniPlayerRange = document.getElementById('miniPlayerRange');
                
                if (miniPlayerPrev) {
                    miniPlayerPrev.addEventListener('click', () => this.playPrevious());
                }
                
                if (miniPlayerPlay) {
                    miniPlayerPlay.addEventListener('click', () => {
                        if (this.isPlaying) {
                            this.pause();
                        } else {
                            // If we have a current audio loaded but not playing, resume it
                            // If we have a current index but no audio, start playing that track
                            if (this.currentAudio) {
                                this.resume();
                            } else if (this.currentIndex >= 0 && this.currentIndex < this.tracks.length) {
                                this.playTrack(this.currentIndex);
                            }
                        }
                    });
                }
                
                if (miniPlayerNext) {
                    miniPlayerNext.addEventListener('click', () => this.playNext());
                }
                
                if (miniPlayerClose) {
                    miniPlayerClose.addEventListener('click', () => this.stop());
                }
                
                // Timeline seeking
                if (miniPlayerRange) {
                    miniPlayerRange.addEventListener('input', (e) => {
                        if (this.currentAudio && this.currentAudio.duration) {
                            const seekTime = (e.target.value / 100) * this.currentAudio.duration;
                            this.currentAudio.currentTime = seekTime;
                            this.updateMiniPlayer();
                        }
                    });
                }
                
                // Update progress every second
                this.progressInterval = setInterval(() => {
                    if (this.currentAudio && this.isPlaying) {
                        this.updateMiniPlayer();
                    }
                }, 1000);
            },
            
            initTrackSelector() {
                const trackSelectorModal = document.getElementById('trackSelectorModal');
                const closeTrackSelector = document.getElementById('closeTrackSelector');
                const miniPlayerTitle = document.getElementById('miniPlayerTitle');
                const miniPlayerDropdown = document.getElementById('miniPlayerDropdown');
                
                // Ensure modal is hidden on initialization
                if (trackSelectorModal) {
                    trackSelectorModal.hidden = true;
                    trackSelectorModal.style.display = 'none';
                }
                
                // Make mini player title clickable
                if (miniPlayerTitle) {
                    miniPlayerTitle.addEventListener('click', () => this.openTrackSelector());
                }
                
                // Make dropdown button clickable
                if (miniPlayerDropdown) {
                    miniPlayerDropdown.addEventListener('click', () => this.openTrackSelector());
                }
                
                // Close track selector
                if (closeTrackSelector) {
                    closeTrackSelector.addEventListener('click', () => this.closeTrackSelector());
                }
                
                // Close on click outside modal
                if (trackSelectorModal) {
                    trackSelectorModal.addEventListener('click', (e) => {
                        if (e.target === trackSelectorModal) {
                            this.closeTrackSelector();
                        }
                    });
                }
            },
            
            openTrackSelector() {
                const trackSelectorModal = document.getElementById('trackSelectorModal');
                const trackSelectorList = document.getElementById('trackSelectorList');
                
                if (!trackSelectorModal || !trackSelectorList) return;
                
                // Don't open if no tracks are available
                if (this.tracks.length === 0) {
                    console.log('No tracks available for selector');
                    return;
                }
                
                // Populate track list
                this.populateTrackSelector();
                
                // Show modal
                trackSelectorModal.hidden = false;
                trackSelectorModal.style.display = 'flex';
            },
            
            closeTrackSelector() {
                const trackSelectorModal = document.getElementById('trackSelectorModal');
                if (trackSelectorModal) {
                    trackSelectorModal.hidden = true;
                    trackSelectorModal.style.display = 'none';
                }
            },
            
            populateTrackSelector() {
                const trackSelectorList = document.getElementById('trackSelectorList');
                if (!trackSelectorList) return;
                
                // Clear existing tracks
                trackSelectorList.innerHTML = '';
                
                // Add Play All option
                const playAllOption = document.createElement('div');
                playAllOption.className = 'track-selector-item';
                playAllOption.innerHTML = `
                    <div class="track-info">
                        <div class="track-title">🎵 Play All Tracks</div>
                        <div class="track-subtitle">${this.tracks.length} tracks available</div>
                    </div>
                `;
                playAllOption.addEventListener('click', () => {
                    this.closeTrackSelector();
                    this.playAll();
                });
                trackSelectorList.appendChild(playAllOption);
                
                // Add Shuffle option
                const shuffleOption = document.createElement('div');
                shuffleOption.className = 'track-selector-item';
                shuffleOption.innerHTML = `
                    <div class="track-info">
                        <div class="track-title">🔀 Shuffle All</div>
                        <div class="track-subtitle">Play tracks in random order</div>
                    </div>
                `;
                shuffleOption.addEventListener('click', () => {
                    this.closeTrackSelector();
                    this.shuffle();
                });
                trackSelectorList.appendChild(shuffleOption);
                
                // Add separator
                const separator = document.createElement('div');
                separator.className = 'track-selector-separator';
                trackSelectorList.appendChild(separator);
                
                // Add individual tracks
                this.tracks.forEach((track, index) => {
                    const trackItem = document.createElement('div');
                    trackItem.className = 'track-selector-item';
                    
                    // Highlight currently playing track
                    if (index === this.currentIndex) {
                        trackItem.classList.add('active');
                    }
                    
                    trackItem.innerHTML = `
                        <div class="track-info">
                            <div class="track-title">${track.title}</div>
                            <div class="track-subtitle">${this.formatTime(track.duration || 0)}</div>
                        </div>
                        <div class="track-status">
                            ${index === this.currentIndex && this.isPlaying ? '▶' : ''}
                        </div>
                    `;
                    
                    trackItem.addEventListener('click', () => {
                        this.closeTrackSelector();
                        this.playTrack(index);
                    });
                    
                    trackSelectorList.appendChild(trackItem);
                });
            }
        };
        
        // Make playlist globally available
        window.playlist = playlist;
        
        // Initialize playlist when DOM is ready
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', () => playlist.init().catch(console.error));
        } else {
            playlist.init().catch(console.error);
        }
    </script>

    <!-- Footer Mini-Player (Spotify-Style) -->
    <div id="miniPlayer" class="mini-player-footer" hidden>
        <div class="mini-player-container">
            <div class="mini-player-info">
                <div id="miniPlayerTitle" class="mini-player-title clickable-title" title="Click to select track">♪ Ready to play</div>
                <div class="mini-player-meta">
                    <span id="miniPlayerCurrentTime">0:00</span> / <span id="miniPlayerDuration">0:00</span>
                </div>
            </div>
            <div class="mini-player-progress">
                <input type="range" id="miniPlayerRange" class="mini-timeline" min="0" max="100" value="0" step="0.1">
                <div class="mini-time-display">
                    <span id="miniPlayerCurrentTime2">0:00</span> / <span id="miniPlayerDuration2">0:00</span>
                </div>
            </div>
            <div class="mini-player-controls">
                <button id="miniPlayerPrev" class="mini-btn" title="Previous">⏮</button>
                <button id="miniPlayerPlay" class="mini-btn primary" title="Play/Pause">▶</button>
                <button id="miniPlayerNext" class="mini-btn" title="Next">⏭</button>
                <button id="miniPlayerDropdown" class="mini-btn" title="Select track">⌄</button>
                <button id="miniPlayerClose" class="mini-btn close" title="Close">✕</button>
            </div>
        </div>
    </div>

</body>
</html>"""
            
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            self.wfile.write(index_html.encode('utf-8'))
            
        except Exception as e:
            logger.error(f"Error generating index page: {e}")
            self.send_error(500, "Internal server error")
    
    def _time_ago(self, dt):
        """Calculate time ago string from datetime"""
        now = datetime.now()
        diff = now - dt
        
        if diff.days > 0:
            return f"{diff.days} day{'s' if diff.days != 1 else ''} ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
        else:
            return "just now"
    
    def log_message(self, format, *args):
        """Override to use our logger"""
        logger.info(f"HTTP: {format % args}")

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class YouTubeTelegramBot:
    """Telegram bot for YouTube video summarization"""
    
    def __init__(self, token: str, allowed_user_ids: List[int]):
        """
        Initialize the Telegram bot
        
        Args:
            token: Telegram bot token
            allowed_user_ids: List of Telegram user IDs allowed to use the bot
        """
        self.token = token
        self.allowed_user_ids = set(allowed_user_ids)
        self.summarizer = None
        self.application = None
        self.last_video_url = None  # Store last processed video URL for model switching
        
        # YouTube URL regex pattern
        self.youtube_url_pattern = re.compile(
            r'(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/|youtube\.com/v/)([a-zA-Z0-9_-]{11})'
        )
        
        # Telegram message length limit
        self.MAX_MESSAGE_LENGTH = 4096
        
        # Cache for URLs that can't be encoded as video IDs (fallback)
        # Format: {short_id: {'url': str, 'timestamp': float}}
        self.url_cache = {}
        self.CACHE_TTL = 3600  # 1 hour TTL for cached URLs
        
        # HTML export settings
        self.exports_dir = Path("/app/exports")
        self.exports_dir.mkdir(exist_ok=True)
        # Configurable HTML report retention (default 7 days, minimum 1 hour)
        # Parse HTML_REPORT_RETENTION_HOURS and strip any comments
        html_ttl_raw = os.getenv('HTML_REPORT_RETENTION_HOURS', '168').split('#')[0].strip()
        html_ttl_hours = max(1, int(html_ttl_raw))  # 168 hours = 7 days
        self.HTML_TTL = html_ttl_hours * 3600
        
        # Web server settings
        self.web_server = None
        self.web_server_thread = None
        # Use environment variable for port, default to 6452
        default_port = int(os.getenv('WEB_PORT', '6452'))
        
        # Try to force use the default port (6452) for consistent NGROK tunneling
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', default_port))
                self.web_port = default_port
                logger.info(f"🌐 Successfully claimed port {default_port}")
        except OSError as e:
            logger.warning(f"⚠️ Port {default_port} is busy, finding alternative...")
            self.web_port = self._find_available_port(default_port + 1)
            logger.warning(f"⚠️ Using alternative port {self.web_port} - NGROK tunnel may need updating!")
        
    def initialize_summarizer(self):
        """Initialize the YouTube summarizer with error handling"""
        try:
            # Reload llm_config to pick up any environment changes
            llm_config.load_environment()
            # Initialize with default configuration from llm_config
            self.summarizer = YouTubeSummarizer()
            logger.info(f"✅ YouTube summarizer initialized with {self.summarizer.llm_provider}/{self.summarizer.model}")
            logger.info(f"🎯 Using {llm_config.llm_shortlist} shortlist")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to initialize YouTube summarizer: {e}")
            return False
    
    def _is_authorized_user(self, user_id: int) -> bool:
        """Check if user is authorized to use the bot"""
        return user_id in self.allowed_user_ids
    
    def _extract_youtube_url(self, text: str) -> Optional[str]:
        """Extract YouTube URL from message text"""
        match = self.youtube_url_pattern.search(text)
        if match:
            video_id = match.group(1)
            return f"https://www.youtube.com/watch?v={video_id}"
        return None
    
    def _extract_youtube_id(self, url: str) -> Optional[str]:
        """Extract YouTube video ID from URL"""
        match = self.youtube_url_pattern.search(url)
        if match:
            return match.group(1)
        return None
    
    def _generate_short_id(self, url: str) -> str:
        """Generate a short ID for URL caching"""
        # Create a hash-based short ID
        hash_object = hashlib.md5(f"{url}{time.time()}".encode())
        return hash_object.hexdigest()[:8]
    
    def _cleanup_url_cache(self):
        """Remove expired entries from URL cache"""
        current_time = time.time()
        expired_keys = [
            key for key, value in self.url_cache.items()
            if current_time - value['timestamp'] > self.CACHE_TTL
        ]
        for key in expired_keys:
            del self.url_cache[key]
    
    def _create_safe_callback_data(self, action: str, url: str) -> str:
        """Create callback data that fits within Telegram's 64-byte limit"""
        # First, try to extract video ID
        video_id = self._extract_youtube_id(url)
        if video_id:
            callback_data = f"{action}_{video_id}"
            # Check if it fits in 64 bytes
            byte_length = len(callback_data.encode('utf-8'))
            logger.debug(f"Callback data with video ID: '{callback_data}' ({byte_length} bytes)")
            if byte_length <= 64:
                return callback_data
            else:
                logger.warning(f"Callback data too long with video ID: {byte_length} bytes")
        
        # Fallback: use cache with short ID
        self._cleanup_url_cache()  # Clean up expired entries
        short_id = self._generate_short_id(url)
        self.url_cache[short_id] = {
            'url': url,
            'timestamp': time.time()
        }
        callback_data = f"{action}_{short_id}"
        
        # Final safety check
        byte_length = len(callback_data.encode('utf-8'))
        if byte_length > 64:
            # Use even shorter action name if needed
            action_short = action[:10] if len(action) > 10 else action
            callback_data = f"{action_short}_{short_id}"
            byte_length = len(callback_data.encode('utf-8'))
            logger.warning(f"Using shortened callback data: '{callback_data}' ({byte_length} bytes)")
        
        logger.debug(f"Final callback data: '{callback_data}' ({byte_length} bytes)")
        
        # Validate final result
        if byte_length > 64:
            raise ValueError(f"Callback data still too long: {byte_length} bytes")
        
        return callback_data
    
    def _resolve_callback_url(self, identifier: str) -> Optional[str]:
        """Resolve URL from either video ID or cached short ID"""
        logger.debug(f"Resolving callback URL for identifier: '{identifier}'")
        
        # First, assume it's a video ID and construct URL
        # YouTube video IDs are 11 characters long and contain only alphanumeric chars, hyphens, and underscores
        if (len(identifier) == 11 and 
            all(c.isalnum() or c in '-_' for c in identifier) and
            not identifier.isdigit()):  # Avoid false positives with numeric IDs
            # Looks like a YouTube video ID
            logger.debug(f"Treating '{identifier}' as YouTube video ID")
            return f"https://www.youtube.com/watch?v={identifier}"
        
        # Otherwise, try to resolve from cache
        if identifier in self.url_cache:
            entry = self.url_cache[identifier]
            # Check if not expired
            if time.time() - entry['timestamp'] <= self.CACHE_TTL:
                logger.debug(f"Found cached URL for '{identifier}': {entry['url']}")
                return entry['url']
            else:
                # Remove expired entry
                logger.debug(f"Removing expired cache entry for '{identifier}'")
                del self.url_cache[identifier]
        
        logger.warning(f"Could not resolve URL for identifier: '{identifier}'")
        return None
    
    def _validate_callback_data_creation(self):
        """Test and validate callback data creation with common YouTube URLs"""
        test_urls = [
            'https://www.youtube.com/watch?v=dQw4w9WgXcQ',
            'https://youtu.be/dQw4w9WgXcQ',
            'https://youtube.com/embed/dQw4w9WgXcQ',
            'https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=30s'
        ]
        
        logger.info("🧪 Testing callback data creation...")
        for url in test_urls:
            try:
                comprehensive_callback = self._create_safe_callback_data("process_comprehensive", url)
                audio_callback = self._create_safe_callback_data("process_audio", url)
                
                logger.info(f"  ✅ {url[:40]}... -> '{comprehensive_callback}' ({len(comprehensive_callback)} chars)")
                logger.info(f"     Audio: '{audio_callback}' ({len(audio_callback)} chars)")
                
                # Test resolution
                parts = comprehensive_callback.split("_", 2)
                if len(parts) == 3:
                    resolved_url = self._resolve_callback_url(parts[2])
                    if resolved_url:
                        logger.info(f"     ✅ Resolution test passed: {resolved_url}")
                    else:
                        logger.warning(f"     ❌ Resolution test failed for: {parts[2]}")
                        
            except Exception as e:
                logger.error(f"  ❌ {url[:40]}... -> Error: {e}")
        
        logger.info("🧪 Callback data testing complete")
    
    def _split_long_message(self, text: str, max_length: int = None) -> List[str]:
        """Split long messages into chunks that fit Telegram's limits"""
        if max_length is None:
            max_length = self.MAX_MESSAGE_LENGTH - 100  # Leave some buffer
        
        if len(text) <= max_length:
            return [text]
        
        chunks = []
        current_chunk = ""
        
        # Split by paragraphs first
        paragraphs = text.split('\n\n')
        
        for paragraph in paragraphs:
            if len(current_chunk) + len(paragraph) + 2 <= max_length:
                if current_chunk:
                    current_chunk += '\n\n'
                current_chunk += paragraph
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = ""
                
                # If single paragraph is too long, split by sentences
                if len(paragraph) > max_length:
                    sentences = paragraph.split('. ')
                    for sentence in sentences:
                        if len(current_chunk) + len(sentence) + 2 <= max_length:
                            if current_chunk:
                                current_chunk += '. '
                            current_chunk += sentence
                        else:
                            if current_chunk:
                                chunks.append(current_chunk)
                            current_chunk = sentence
                else:
                    current_chunk = paragraph
        
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks
    
    def _format_video_info(self, metadata: Dict) -> str:
        """Format video metadata for display"""
        title = metadata.get('title', 'Unknown Title')
        uploader = metadata.get('uploader', 'Unknown Channel')
        duration = metadata.get('duration', 0)
        view_count = metadata.get('view_count', 0)
        upload_date = metadata.get('upload_date', '')
        
        # Format duration
        if duration:
            hours = duration // 3600
            minutes = (duration % 3600) // 60
            seconds = duration % 60
            if hours > 0:
                duration_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            else:
                duration_str = f"{minutes:02d}:{seconds:02d}"
        else:
            duration_str = "Unknown"
        
        # Format view count
        if view_count:
            if view_count >= 1_000_000:
                view_str = f"{view_count / 1_000_000:.1f}M views"
            elif view_count >= 1_000:
                view_str = f"{view_count / 1_000:.1f}K views"
            else:
                view_str = f"{view_count:,} views"
        else:
            view_str = "Unknown views"
        
        # Format upload date
        if upload_date and len(upload_date) >= 8:
            try:
                # Parse upload date in YYYYMMDD format
                date_obj = datetime.strptime(upload_date, '%Y%m%d')
                date_str = date_obj.strftime('%B %d, %Y')
            except (ValueError, TypeError):
                # If parsing fails, show the raw date
                date_str = f"Uploaded: {upload_date}" if upload_date else "Unknown date"
        else:
            date_str = "Unknown date"
        
        return f"""🎥 **VIDEO INFO**
─────────────────────
**{title}**
📺 {uploader}
⏱️ {duration_str} • 👀 {view_str}
📅 {date_str}"""
    
    def _format_summary_message(self, result: Dict, summary_type: str = "comprehensive") -> List[str]:
        """Format the complete summary result for Telegram"""
        messages = []
        
        # Video info
        video_info = self._format_video_info(result['metadata'])
        messages.append(video_info)
        
        # Summary with headline
        summary_data = result.get('summary', {})
        headline = summary_data.get('headline', '')
        summary_text = summary_data.get('summary', '')
        summary_type_used = summary_data.get('summary_type', 'comprehensive')
        
        if headline and summary_text:
            # Choose formatting based on summary type
            if summary_type_used == "audio":
                summary_message = f"""🎙️ **AUDIO SUMMARY**
──────────────────

✨ **{headline}**

{summary_text}"""
            elif summary_type_used == "adaptive":
                summary_message = f"""🎯 **AI ADAPTIVE SUMMARY**
──────────────────

✨ **{headline}**

{summary_text}"""
            else:
                summary_message = f"""📝 **DETAILED SUMMARY**
──────────────────

✨ **{headline}**

{summary_text}"""
            
            # Split summary if too long
            summary_chunks = self._split_long_message(summary_message)
            messages.extend(summary_chunks)
        
        # Analysis data (only for comprehensive summaries)
        if summary_type == "comprehensive":
            analysis = result.get('analysis', {})
            if analysis and not analysis.get('error'):
                analysis_text = f"""📊 **CONTENT DETAILS**
──────────────────

🏷️ **Category**
{', '.join(analysis.get('category', ['Unknown']))}

📈 **Complexity**
{analysis.get('complexity_level', 'Unknown')}

🔍 **Key Topics**
{', '.join(analysis.get('key_topics', ['Unknown']))}

💭 **Sentiment:** {analysis.get('sentiment', 'Unknown')}
📚 **Educational:** {analysis.get('educational_value', 'Unknown')}
🎭 **Entertainment:** {analysis.get('entertainment_value', 'Unknown')}"""
                
                messages.append(analysis_text)
        
        # Processing info (only for comprehensive)
        if summary_type == "comprehensive":
            processor_info = result.get('processor_info', {})
            if processor_info:
                processing_text = f"""⚙️ **PROCESSING INFO**
──────────────────

🤖 {processor_info.get('llm_provider', 'Unknown')}/{processor_info.get('model', 'Unknown')}
🎯 {llm_config.llm_shortlist} shortlist
⏰ {datetime.now().strftime('%H:%M')}"""
                messages.append(processing_text)
        
        return messages
    
    def _get_model_badge_for_summary(self, model_text):
        """Convert model text to styled badge name for summary pages"""
        if not model_text or model_text == "Unknown":
            return "Unknown"
        
        # Handle the case where we get just provider name (like "Openai")
        if model_text.lower() in ['openai', 'anthropic', 'deepseek', 'gemma', 'llama']:
            return model_text.upper()
        
        # Extract core model name (same logic as dashboard)
        model_mapping = {
            'gpt-4o': 'GPT-4o',
            'gpt-4o-mini': 'GPT-4o-mini',
            'gpt-5': 'GPT-5',
            'gpt-5-nano': 'GPT-5-nano',
            'claude-3-sonnet': 'Claude-3',
            'claude-3-haiku': 'Claude-3',
            'claude-3-opus': 'Claude-3',
            'deepseek-r1': 'DeepSeek',
            'deepseek': 'DeepSeek',
            'gemma-3': 'Gemma-3',
            'gemma': 'Gemma',
            'llama-3': 'Llama-3',
            'llama': 'Llama'
        }
        
        # Try to find exact match first
        model_lower = model_text.lower()
        for key, display in model_mapping.items():
            if key in model_lower:
                return display
        
        # Fallback - extract first meaningful part
        if '/' in model_text:
            parts = model_text.split('/')
            if len(parts) >= 3:  # openrouter format
                model_name = parts[-1]  # Last part is usually the model
            else:
                model_name = parts[-1]  # Take last part
        else:
            model_name = model_text
        
        # Clean up and truncate
        clean_name = model_name.split('-')[0].upper()[:8]
        return clean_name if clean_name else "Unknown"
    
    def _get_model_badge_class_for_summary(self, model_text):
        """Get CSS class for model badge styling in summary pages"""
        model_lower = model_text.lower()
        if 'claude' in model_lower or 'anthropic' in model_lower:
            return 'anthropic'
        elif 'gpt' in model_lower or 'openai' in model_lower:
            return 'openai'
        elif 'deepseek' in model_lower:
            return 'deepseek'
        elif 'gemma' in model_lower:
            return 'gemma'
        elif 'llama' in model_lower:
            return 'llama'
        else:
            return 'default'
    
    def _generate_html_report(self, result: Dict, summary_type: str = "comprehensive", audio_filepath: str = None) -> str:
        """Generate HTML report and return the file path"""
        try:
            metadata = result['metadata']
            summary_data = result.get('summary', {})
            analysis = result.get('analysis', {})
            
            # Create filename based on video ID and timestamp
            video_id = metadata.get('video_id', 'unknown')
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{video_id}_{timestamp}.html"
            filepath = self.exports_dir / filename
            
            # Get YouTube thumbnail URL
            youtube_url = metadata.get('url', '')
            thumbnail_url = None
            if video_id and video_id != 'unknown':
                thumbnail_url = f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg"
            
            # Format duration
            duration = metadata.get('duration', 0)
            if duration:
                hours = duration // 3600
                minutes = (duration % 3600) // 60
                seconds = duration % 60
                if hours > 0:
                    duration_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                else:
                    duration_str = f"{minutes:02d}:{seconds:02d}"
            else:
                duration_str = "Unknown"
            
            # Format upload date
            upload_date = metadata.get('upload_date', '')
            if upload_date and len(upload_date) >= 8:
                try:
                    date_obj = datetime.strptime(upload_date, '%Y%m%d')
                    formatted_date = date_obj.strftime('%B %d, %Y')
                except:
                    formatted_date = upload_date
            else:
                formatted_date = "Unknown"
            
            # Get model information
            processor_info = result.get('processor_info', {})
            model = f"{processor_info.get('llm_provider', 'Unknown')}/{processor_info.get('model', 'Unknown')}"
            
            # Get model badge info (reuse dashboard helper logic)
            model_badge_text = self._get_model_badge_for_summary(model)
            model_badge_class = self._get_model_badge_class_for_summary(model)
            
            # Get base URL for navigation
            base_url = os.getenv('WEB_BASE_URL', 'https://chief-inspired-lab.ngrok-free.app')
            if base_url and not base_url.startswith('http'):
                base_url = f'https://{base_url}'
            if 'ngrok-free.app' not in base_url:
                base_url = 'https://chief-inspired-lab.ngrok-free.app'
            
            # Generate HTML content
            html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{metadata.get('title', 'YouTube Summary')}</title>
    <style>
        :root {{
            --primary-color: #1a73e8;
            --secondary-color: #34a853;
            --text-color: #202124;
            --text-secondary: #5f6368;
            --background: #ffffff;
            --surface: #f8f9fa;
            --border: #dadce0;
        }}
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: var(--text-color);
            background: var(--background);
            padding: 20px;
        }}
        
        .container {{
            max-width: 1100px;
            margin: 0 auto;
            background: var(--background);
            border-radius: 12px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        
        .header {{
            background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
            color: white;
            padding: 30px;
            text-align: center;
        }}
        
        .header h1 {{
            font-size: 1.8em;
            margin-bottom: 10px;
            font-weight: 600;
        }}
        
        .header .channel {{
            opacity: 0.9;
            font-size: 1.1em;
        }}
        
        .content {{
            padding: 30px;
        }}
        
        /* Enhanced layout for desktop - wider content utilization */
        @media (min-width: 900px) {{
            .content {{
                display: flex;
                flex-direction: column;
                gap: 25px;
            }}
            
            .video-info {{
                margin-bottom: 20px;
            }}
            
            .info-grid {{
                grid-template-columns: repeat(6, 1fr);
                gap: 15px 25px;
            }}
        }}
        
        .video-info {{
            background: var(--surface);
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 25px;
            border-left: 4px solid var(--primary-color);
        }}
        
        .video-info h2 {{
            color: var(--primary-color);
            margin-bottom: 12px;
            font-size: 1.2em;
        }}
        
        .info-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
            gap: 12px 20px;
        }}
        
        .info-item {{
            display: flex;
            flex-direction: column;
            min-height: 50px;
        }}
        
        .info-label {{
            font-weight: 600;
            color: var(--text-secondary);
            font-size: 0.85em;
            margin-bottom: 4px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        
        .info-value {{
            color: var(--text-color);
            font-size: 0.95em;
            line-height: 1.3;
        }}
        
        .summary-section {{
            margin-bottom: 30px;
        }}
        
        .summary-section h2 {{
            color: var(--primary-color);
            margin-bottom: 20px;
            font-size: 1.4em;
            border-bottom: 2px solid var(--border);
            padding-bottom: 10px;
        }}
        
        .summary-content {{
            background: var(--surface);
            padding: 25px;
            border-radius: 8px;
            border-left: 4px solid var(--secondary-color);
        }}
        
        .summary-content h3 {{
            color: var(--primary-color);
            margin: 20px 0 10px 0;
            font-size: 1.2em;
        }}
        
        .summary-content h3:first-child {{
            margin-top: 0;
        }}
        
        .summary-content ul {{
            margin-left: 20px;
            margin-bottom: 15px;
        }}
        
        .summary-content li {{
            margin-bottom: 8px;
        }}
        
        .analysis-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }}
        
        .analysis-card {{
            background: var(--surface);
            padding: 20px;
            border-radius: 8px;
            border: 1px solid var(--border);
        }}
        
        .analysis-card h3 {{
            color: var(--primary-color);
            margin-bottom: 10px;
            font-size: 1.1em;
        }}
        
        .footer {{
            background: var(--surface);
            padding: 20px 30px;
            border-top: 1px solid var(--border);
            text-align: center;
            color: var(--text-secondary);
            font-size: 0.9em;
        }}
        
        .url-link {{
            color: var(--primary-color);
            text-decoration: none;
            word-break: break-all;
        }}
        
        .url-link:hover {{
            text-decoration: underline;
        }}
        
        .navigation {{
            background: #f8f9fa;
            padding: 30px;
            border-top: 1px solid #e9ecef;
            margin-top: 30px;
        }}
        
        .nav-buttons {{
            display: flex;
            gap: 15px;
            justify-content: center;
            flex-wrap: wrap;
        }}
        
        .nav-btn {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 12px 24px;
            border-radius: 8px;
            text-decoration: none;
            font-weight: 500;
            transition: all 0.2s ease;
            cursor: pointer;
        }}
        
        .nav-btn-primary {{
            background: var(--primary-color);
            color: white;
        }}
        
        .nav-btn-primary:hover {{
            background: #1557b0;
            transform: translateY(-1px);
        }}
        
        .nav-btn-secondary {{
            background: #ff0000;
            color: white;
        }}
        
        .nav-btn-secondary:hover {{
            background: #cc0000;
            transform: translateY(-1px);
        }}
        
        @media (max-width: 600px) {{
            body {{
                padding: 10px;
            }}
            
            .container {{
                max-width: none;
                margin: 10px;
                border-radius: 8px;
            }}
            
            .header {{
                padding: 20px;
            }}
            
            .content {{
                padding: 20px;
            }}
            
            .header h1 {{
                font-size: 1.5em;
            }}
            
            .video-info {{
                padding: 15px;
                margin-bottom: 20px;
            }}
            
            .info-grid {{
                grid-template-columns: repeat(2, 1fr);
                gap: 10px 15px;
            }}
            
            .info-item {{
                min-height: 45px;
            }}
            
            .navigation {{
                padding: 20px;
            }}
            
            .nav-buttons {{
                flex-direction: column;
                gap: 10px;
            }}
            
            .nav-btn {{
                justify-content: center;
                padding: 15px 20px;
            }}
            
            .report-actions {{
                gap: 8px;
            }}
            
            .btn {{
                font-size: 0.8em;
                padding: 8px 12px;
                flex: 1;
                min-width: 0;
                text-align: center;
            }}
        }}
        
        /* Enhanced Header Styles */
        .header {{
            background: linear-gradient(135deg, var(--primary-color), var(--secondary-color));
            color: white;
            padding: 0;
            text-align: center;
            border-radius: 12px 12px 0 0;
            overflow: hidden;
            position: relative;
            min-height: 200px;
            display: flex;
            flex-direction: column;
            justify-content: flex-end;
        }}
        
        .header-thumbnail {{
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            object-fit: cover;
            opacity: 0.3;
        }}
        
        .header-content {{
            position: relative;
            z-index: 2;
            background: linear-gradient(transparent, rgba(0,0,0,0.7));
            padding: 40px 30px 30px;
        }}
        
        .header h1 {{
            font-size: 2.2em;
            margin-bottom: 10px;
            font-weight: 700;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }}
        
        .header .channel {{
            opacity: 0.95;
            font-size: 1.2em;
            font-weight: 500;
        }}
        
        /* Model Badge Styles */
        .model-badge {{
            display: inline-block;
            background: rgba(255, 255, 255, 0.9);
            color: #1a73e8;
            padding: 6px 12px;
            border-radius: 16px;
            font-size: 0.8em;
            font-weight: 600;
            margin: 0 8px 0 0;
            border: 2px solid rgba(255, 255, 255, 0.3);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            backdrop-filter: blur(4px);
        }}
        .model-badge.anthropic {{ background: rgba(255, 242, 230, 0.9); color: #d2691e; border-color: rgba(244, 164, 96, 0.5); }}
        .model-badge.openai {{ background: rgba(230, 247, 255, 0.9); color: #1890ff; border-color: rgba(145, 213, 255, 0.5); }}
        .model-badge.deepseek {{ background: rgba(246, 255, 237, 0.9); color: #52c41a; border-color: rgba(183, 235, 143, 0.5); }}
        .model-badge.gemma {{ background: rgba(249, 240, 255, 0.9); color: #722ed1; border-color: rgba(211, 173, 247, 0.5); }}
        .model-badge.llama {{ background: rgba(255, 247, 230, 0.9); color: #fa8c16; border-color: rgba(255, 213, 145, 0.5); }}
        .model-badge.default {{ background: rgba(245, 245, 245, 0.9); color: #666; border-color: rgba(217, 217, 217, 0.5); }}
        
        /* Enhanced Info Grid - Card-style tiles */
        .info-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 16px;
            margin: 20px 0;
        }}
        
        .info-item {{
            display: flex;
            flex-direction: column;
            padding: 18px;
            background: var(--surface);
            border-radius: 12px;
            border: 1px solid var(--border);
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }}
        
        .info-item::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 3px;
            background: linear-gradient(90deg, var(--primary-color), var(--secondary-color));
            opacity: 0;
            transition: opacity 0.3s ease;
        }}
        
        .info-item:hover {{
            transform: translateY(-4px);
            box-shadow: 0 8px 25px rgba(0,0,0,0.12);
            border-color: rgba(26, 115, 232, 0.3);
        }}
        
        .info-item:hover::before {{
            opacity: 1;
        }}
        
        .info-label {{
            font-size: 0.8em;
            font-weight: 600;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        
        .info-value {{
            font-size: 1em;
            font-weight: 500;
            color: var(--text-color);
            line-height: 1.4;
        }}
        
        /* Special styling for specific info items */
        .info-item[data-type="duration"] .info-label::before {{
            content: "⏱️";
        }}
        
        .info-item[data-type="date"] .info-label::before {{
            content: "📅";
        }}
        
        .info-item[data-type="views"] .info-label::before {{
            content: "👁️";
        }}
        
        .info-item[data-type="provider"] .info-label::before {{
            content: "🤖";
        }}
        
        .info-item[data-type="type"] .info-label::before {{
            content: "📋";
        }}
        
        .info-item[data-type="url"] .info-label::before {{
            content: "🔗";
        }}
        
        /* Top Navigation Bar Styles */
        .top-nav {{
            position: sticky;
            top: 0;
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-bottom: 1px solid var(--border);
            padding: 12px 20px;
            z-index: 1000;
            margin-bottom: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        
        .nav-container {{
            max-width: 1100px;
            margin: 0 auto;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 15px;
        }}
        
        .nav-left {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        
        .nav-back-btn {{
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 8px 12px;
            background: var(--primary-color);
            color: white;
            border: none;
            border-radius: 6px;
            font-size: 0.9em;
            font-weight: 500;
            text-decoration: none;
            cursor: pointer;
            transition: all 0.2s ease;
        }}
        
        .nav-back-btn:hover {{
            background: #1557b0;
            transform: translateY(-1px);
        }}
        
        .nav-breadcrumb {{
            color: var(--text-secondary);
            font-size: 0.9em;
            display: flex;
            align-items: center;
            gap: 6px;
        }}
        
        .nav-breadcrumb .separator {{
            color: var(--border);
            font-weight: bold;
        }}
        
        .nav-actions {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        .nav-action-btn {{
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 6px 10px;
            background: var(--surface);
            color: var(--text-color);
            border: 1px solid var(--border);
            border-radius: 6px;
            font-size: 0.8em;
            font-weight: 500;
            text-decoration: none;
            cursor: pointer;
            transition: all 0.2s ease;
        }}
        
        .nav-action-btn:hover {{
            background: #e8eaed;
            transform: translateY(-1px);
        }}
        
        .nav-action-btn.share {{
            background: #34a853;
            color: white;
            border-color: #34a853;
        }}
        
        .nav-action-btn.share:hover {{
            background: #2d8f47;
        }}
        
        @media (max-width: 600px) {{
            .top-nav {{
                padding: 10px 15px;
                margin-bottom: 10px;
            }}
            
            .nav-container {{
                max-width: none;
                margin: 10px;
                gap: 10px;
                flex-direction: column;
                text-align: center;
            }}
            
            .nav-breadcrumb {{
                display: none; /* Hide breadcrumb on mobile */
            }}
            
            .nav-actions {{
                gap: 6px;
            }}
            
            .nav-action-btn {{
                padding: 6px 8px;
                font-size: 0.7em;
            }}
        }}
        
        /* Audio Player Styles */
        .audio-section {{
            background: var(--surface);
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 25px;
            border-left: 4px solid #34a853;
        }}
        
        .audio-section h2 {{
            color: #34a853;
            margin-bottom: 12px;
            font-size: 1.2em;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        .audio-player {{
            width: 100%;
            margin-bottom: 15px;
        }}
        
        .audio-controls {{
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            align-items: center;
        }}
        
        .audio-btn {{
            background: #34a853;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 20px;
            cursor: pointer;
            font-size: 0.9em;
            transition: all 0.2s;
        }}
        
        .audio-btn:hover {{
            background: #2d8f47;
            transform: translateY(-1px);
        }}
        
        .audio-info {{
            color: var(--text-secondary);
            font-size: 0.85em;
            margin-top: 8px;
        }}
        
        @media (max-width: 600px) {{
            .audio-section {{
                padding: 15px;
            }}
            
            .audio-controls {{
                justify-content: center;
            }}
        }}
    </style>
</head>
<body>
    <!-- Top Navigation Bar -->
    <div class="top-nav">
        <div class="nav-container">
            <div class="nav-left">
                <a href="{base_url}" class="nav-back-btn">
                    ← Dashboard
                </a>
            </div>
            <div class="nav-actions">
                <button class="nav-action-btn" onclick="navigator.clipboard.writeText('{metadata.get('url', '')}')" title="Copy Video URL">
                    📋 Copy URL
                </button>
                <a href="{metadata.get('url', '#')}" class="nav-action-btn share" target="_blank" title="Open on YouTube">
                    ▶️ YouTube
                </a>
            </div>
        </div>
    </div>
    
    <div class="container">
        <div class="header">"""
            
            # Add thumbnail image if available (avoid f-string backslash issue)
            if thumbnail_url:
                html_content += f'<img src="{thumbnail_url}" alt="Video thumbnail" class="header-thumbnail" onerror="this.style.display=' + "'none'" + ';">'
                
            html_content += f"""
            <div class="header-content">
                <div class="model-badge {model_badge_class}">{model_badge_text}</div>
                <h1>{metadata.get('title', 'YouTube Video Summary')}</h1>
                <div class="channel">{metadata.get('uploader', 'Unknown Channel')}</div>
            </div>
        </div>
        
        <div class="content">
            <div class="video-info">
                <h2>📹 Video Information</h2>
                <div class="info-grid">
                    <div class="info-item" data-type="duration">
                        <div class="info-label">Duration</div>
                        <div class="info-value">{duration_str}</div>
                    </div>
                    <div class="info-item" data-type="date">
                        <div class="info-label">Upload Date</div>
                        <div class="info-value">{formatted_date}</div>
                    </div>
                    <div class="info-item" data-type="views">
                        <div class="info-label">Views</div>
                        <div class="info-value">{metadata.get('view_count', 0):,}</div>
                    </div>
                    <div class="info-item" data-type="provider">
                        <div class="info-label">AI Model</div>
                        <div class="info-value">{processor_info.get('model', 'Unknown')}</div>
                    </div>
                    <div class="info-item" data-type="type">
                        <div class="info-label">Summary Type</div>
                        <div class="info-value">{summary_type.title()}</div>
                    </div>
                    <div class="info-item" data-type="url">
                        <div class="info-label">Video URL</div>
                        <div class="info-value">
                            <a href="{metadata.get('url', '#')}" class="url-link" target="_blank">
                                Watch on YouTube
                            </a>
                        </div>
                    </div>
                </div>
            </div>
            """
            
            # Add audio player section for audio summaries
            if summary_type == "audio":
                if audio_filepath:
                    # Audio file is available - show full player
                    audio_filename = Path(audio_filepath).name
                    audio_url = f"{base_url}/exports/{audio_filename}"
                    
                    html_content += f"""
            <div class="audio-section">
                <h2>🎙️ Audio Summary</h2>
                <audio class="audio-player" controls preload="metadata">
                    <source src="{audio_url}" type="audio/mpeg">
                    Your browser does not support the audio element.
                </audio>
                <div class="audio-controls">
                    <button class="audio-btn" onclick="document.querySelector('.audio-player').play()">▶️ Play</button>
                    <button class="audio-btn" onclick="document.querySelector('.audio-player').pause()">⏸️ Pause</button>
                    <button class="audio-btn" onclick="document.querySelector('.audio-player').currentTime = 0">⏪ Restart</button>
                    <a href="{audio_url}" download class="audio-btn" style="text-decoration: none;">💾 Download MP3</a>
                </div>
                <div class="audio-info">
                    🎵 Generated with OpenAI TTS • Perfect for listening on-the-go
                </div>
            </div>
            """
                else:
                    # Audio generation failed - show message
                    html_content += """
            <div class="audio-section">
                <h2>🎙️ Audio Summary</h2>
                <div class="audio-info" style="color: #d93025;">
                    ⚠️ Audio generation failed. Please check TTS API configuration.
                </div>
            </div>
            """
            
            html_content += f"""
            <div class="summary-section">
                <h2>📝 Summary ({summary_type.title()})</h2>
                <div class="summary-content">
                    {self._format_html_content(summary_data.get('summary', 'No summary available'))}
                </div>
            </div>"""
            
            # Add analysis section for comprehensive summaries
            if summary_type == "comprehensive" and analysis and not analysis.get('error'):
                html_content += f"""
            <div class="summary-section">
                <h2>📊 Content Analysis</h2>
                <div class="analysis-grid">
                    <div class="analysis-card">
                        <h3>🏷️ Category</h3>
                        <p>{', '.join(analysis.get('category', ['Unknown']))}</p>
                    </div>
                    <div class="analysis-card">
                        <h3>📈 Complexity</h3>
                        <p>{analysis.get('complexity_level', 'Unknown')}</p>
                    </div>
                    <div class="analysis-card">
                        <h3>🔍 Key Topics</h3>
                        <p>{', '.join(analysis.get('key_topics', ['Unknown']))}</p>
                    </div>
                    <div class="analysis-card">
                        <h3>💭 Sentiment</h3>
                        <p>{analysis.get('sentiment', 'Unknown')}</p>
                    </div>
                    <div class="analysis-card">
                        <h3>📚 Educational Value</h3>
                        <p>{analysis.get('educational_value', 'Unknown')}</p>
                    </div>
                    <div class="analysis-card">
                        <h3>🎭 Entertainment Value</h3>
                        <p>{analysis.get('entertainment_value', 'Unknown')}</p>
                    </div>
                </div>
            </div>"""
            
            # Get processor info for footer
            processor_info = result.get('processor_info', {})
            
            html_content += f"""
            <div class="navigation">
                <div class="nav-buttons">
                    <a href="{base_url}" class="nav-btn nav-btn-primary">
                        🏠 Dashboard
                    </a>
                    <a href="{metadata.get('url', '#')}" class="nav-btn nav-btn-secondary" target="_blank">
                        ▶️ Watch Video
                    </a>
                </div>
            </div>
        </div>
        
        <div class="footer">
            <p>Generated by YouTube Summarizer Bot • {datetime.now().strftime('%B %d, %Y at %H:%M')}</p>
        </div>
    </div>
</body>
</html>"""
            
            # Write HTML file
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            logger.info(f"✅ Generated HTML report: {filename}")
            logger.info(f"📂 Full path: {filepath}")
            logger.info(f"📏 File size: {filepath.stat().st_size} bytes")
            return str(filepath)
            
        except Exception as e:
            logger.error(f"Error generating HTML report: {e}")
            return None
    
    def _format_html_content(self, content: str) -> str:
        """Convert markdown-like content to HTML"""
        if not content:
            return "<p>No content available</p>"
        
        # Convert markdown headers to HTML
        content = re.sub(r'^## (.*$)', r'<h3>\1</h3>', content, flags=re.MULTILINE)
        content = re.sub(r'^# (.*$)', r'<h3>\1</h3>', content, flags=re.MULTILINE)
        
        # Convert bullet points to HTML lists
        lines = content.split('\n')
        in_list = False
        html_lines = []
        
        for line in lines:
            line = line.strip()
            if line.startswith('•') or line.startswith('-'):
                if not in_list:
                    html_lines.append('<ul>')
                    in_list = True
                html_lines.append(f'<li>{line[1:].strip()}</li>')
            else:
                if in_list:
                    html_lines.append('</ul>')
                    in_list = False
                if line:
                    html_lines.append(f'<p>{line}</p>')
                else:
                    html_lines.append('<br>')
        
        if in_list:
            html_lines.append('</ul>')
        
        return '\n'.join(html_lines)
    
    def _cleanup_expired_reports(self):
        """Disabled: Manual deletion now handled via dashboard"""
        # Auto-cleanup disabled - users can manually delete via dashboard
        pass
    
    def _find_available_port(self, start_port: int = 8080) -> int:
        """Find an available port starting from start_port"""
        for port in range(start_port, start_port + 10):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('', port))
                    return port
            except OSError:
                continue
        return start_port  # Fallback
    
    def _start_web_server(self):
        """Start the HTTP server for serving HTML reports"""
        try:
            # Create handler with exports directory and bot instance
            def handler(*args, **kwargs):
                return ReportsHTTPHandler(*args, exports_dir=self.exports_dir, bot_instance=self, **kwargs)
            
            # Create and start server in background thread
            self.web_server = HTTPServer(('', self.web_port), handler)
            logger.info(f"🌐 Starting web server on port {self.web_port}")
            
            # Start server in background thread so it doesn't block
            self.web_server_thread = threading.Thread(
                target=self.web_server.serve_forever,
                daemon=True,
                name="WebServerThread"
            )
            self.web_server_thread.start()
            logger.info(f"✅ Web server running in background on port {self.web_port}")
            
        except Exception as e:
            logger.error(f"Web server error: {e}")
    
    def _stop_web_server(self):
        """Stop the web server"""
        if self.web_server:
            logger.info("🛑 Stopping web server...")
            self.web_server.shutdown()
            self.web_server.server_close()
            self.web_server = None
        
        if self.web_server_thread and self.web_server_thread.is_alive():
            self.web_server_thread.join(timeout=5)
            self.web_server_thread = None
    
    def _get_report_url(self, filename: str) -> str:
        """Get the URL for accessing a report"""
        # Use NGROK URL for external access, fallback to environment variable, then NAS IP
        base_url = os.getenv('WEB_BASE_URL', 'https://chief-inspired-lab.ngrok-free.app')
        
        # If environment variable exists but doesn't have protocol, add https://
        if base_url and not base_url.startswith('http'):
            base_url = f'https://{base_url}'
        
        # Ensure we're using NGROK for external access
        if 'ngrok-free.app' not in base_url:
            base_url = 'https://chief-inspired-lab.ngrok-free.app'
            
        logger.info(f"🔍 DEBUG: Using report URL base = '{base_url}'")
        return f"{base_url.rstrip('/')}/{filename}"
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user_id = update.effective_user.id
        
        if not self._is_authorized_user(user_id):
            await update.message.reply_text(
                "❌ Sorry, you're not authorized to use this bot.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        welcome_message = """🤖 **YOUTUBE SUMMARIZER BOT**
─────────────────────
🎬 **Welcome to YouTube Summarizer!**

Send me a YouTube URL and choose from:
• 📝 **Full Summary** - Comprehensive analysis with structured sections
• 🎙️ **Audio Summary** - Optimized for text-to-speech (~180-250 words)
• 🎯 **AI Adaptive** - AI chooses optimal approach for the content

**Features:**
• 🧠 AI-powered summarization
• 📊 Content analysis & categorization
• 🎯 Interactive summary options
• ✅ Facts & terms, timeline/chapters when available

**Available commands:**
/start - Show this welcome message
/help - Get detailed help information
/status - Check bot status and configuration

Just paste any YouTube URL to get started! 🚀"""
        
        await update.message.reply_text(welcome_message, parse_mode=ParseMode.MARKDOWN)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        user_id = update.effective_user.id
        
        if not self._is_authorized_user(user_id):
            await update.message.reply_text("❌ Unauthorized access.")
            return
        
        help_message = """❓ **HELP GUIDE**
─────────────────────
**🚀 How to use:**
1. Send any YouTube URL in a message
2. Choose **📝 Full Summary** or **⚡ Quick Summary**
3. Wait for processing (usually 30-60 seconds)
4. Receive beautifully formatted results!

**📎 Supported URL formats:**
• `https://www.youtube.com/watch?v=VIDEO_ID`
• `https://youtu.be/VIDEO_ID`
• `https://youtube.com/embed/VIDEO_ID`

**✨ Summary Options:**
• **📝 Full Summary** - Complete analysis with:
  - Detailed content summary
  - Category & sentiment analysis
  - Facts/terms and optional timeline/chapters
  - Processing details
• **🎙️ Audio Summary** - Optimized for text-to-speech (~180-250 words)
• **🎯 AI Adaptive** - AI analyzes the content and chooses the most appropriate summary approach and length based on video complexity, topic, and educational value

**🛠️ Commands:**
/start - Welcome message with features
/help - This detailed help guide
/status - Bot status and AI model info

**⏱️ Note:** Processing may take up to 2 minutes for longer videos.
**🔄 Tip:** Use the action buttons after processing for quick next steps!"""
        
        await update.message.reply_text(help_message, parse_mode=ParseMode.MARKDOWN)
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        user_id = update.effective_user.id
        
        if not self._is_authorized_user(user_id):
            await update.message.reply_text("❌ Unauthorized access.")
            return
        
        # Check summarizer status
        if self.summarizer:
            provider = getattr(self.summarizer, 'llm_provider', 'Unknown')
            model = getattr(self.summarizer, 'model', 'Unknown')
            status_message = f"""✅ **BOT STATUS**
─────────────────────
**Status:** Online

🤖 **AI Model:** {provider}/{model}
🎯 **Shortlist:** {llm_config.llm_shortlist}
🔑 **Available Providers:** {', '.join([p for p, available in llm_config.get_available_providers().items() if available])}
📁 **Downloads Directory:** {self.summarizer.downloads_dir}
👥 **Authorized Users:** {len(self.allowed_user_ids)}

Everything is working normally! 🚀"""
        else:
            status_message = """❌ **BOT STATUS**
─────────────────────
**Status:** Error

The YouTube summarizer is not properly initialized.
Please contact the administrator."""
        
        await update.message.reply_text(status_message, parse_mode=ParseMode.MARKDOWN)
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming messages with YouTube URLs"""
        user_id = update.effective_user.id
        
        # Check authorization
        if not self._is_authorized_user(user_id):
            await update.message.reply_text(
                "❌ Sorry, you're not authorized to use this bot.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Check if summarizer is ready
        if not self.summarizer:
            await update.message.reply_text(
                "❌ Bot is not ready. The summarizer service is unavailable.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        message_text = update.message.text
        youtube_url = self._extract_youtube_url(message_text)
        
        if not youtube_url:
            await update.message.reply_text(
                "❌ Please send a valid YouTube URL.\n\n" +
                "Supported formats:\n" +
                "• https://www.youtube.com/watch?v=VIDEO_ID\n" +
                "• https://youtu.be/VIDEO_ID\n" +
                "• https://youtube.com/embed/VIDEO_ID",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Store the URL for potential model switching
        self.last_video_url = youtube_url
        
        # Create inline keyboard for summary options with safe callback data
        try:
            comprehensive_callback = self._create_safe_callback_data("process_comprehensive", youtube_url)
            audio_callback = self._create_safe_callback_data("process_audio", youtube_url)
            adaptive_callback = self._create_safe_callback_data("process_adaptive", youtube_url)
            
            # Log callback data for debugging
            logger.info(f"Created callback data - Comprehensive: '{comprehensive_callback}' ({len(comprehensive_callback)} chars)")
            logger.info(f"Created callback data - Audio: '{audio_callback}' ({len(audio_callback)} chars)")
            logger.info(f"Created callback data - Adaptive: '{adaptive_callback}' ({len(adaptive_callback)} chars)")
            
            keyboard = [
                [
                    InlineKeyboardButton("📝 Full Summary", callback_data=comprehensive_callback),
                    InlineKeyboardButton("🎙️ Audio Summary", callback_data=audio_callback)
                ],
                [
                    InlineKeyboardButton("🎯 AI Adaptive", callback_data=adaptive_callback)
                ],
                [
                    InlineKeyboardButton("⚙️ Change Model", callback_data="change_model")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
        except ValueError as e:
            logger.error(f"Callback data validation error: {e}")
            await update.message.reply_text(
                "❌ **Button Data Error**\n\n" +
                "The YouTube URL is causing issues with button creation. " +
                "This is likely due to an unusual URL format.\n\n" +
                "Please try with a standard YouTube URL format like:\n" +
                "`https://www.youtube.com/watch?v=VIDEO_ID`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        except Exception as e:
            logger.error(f"Unexpected error creating inline keyboard: {e}")
            await update.message.reply_text(
                "❌ **Unexpected Error**\n\n" +
                "An error occurred while creating the options menu. " +
                "Please try again or contact support if the issue persists.\n\n" +
                f"Error details: `{str(e)}`",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Send options message with current model info
        current_model_info = f"{self.summarizer.llm_provider}/{self.summarizer.model}" if hasattr(self.summarizer, 'llm_provider') and hasattr(self.summarizer, 'model') else "Unknown"
        
        await update.message.reply_text(
            "🎬 **YouTube Video Detected!**\n\n" +
            f"🤖 **Current AI Model:** {current_model_info}\n\n" +
            "Choose your summary preference:",
            reply_markup=reply_markup,
            parse_mode=ParseMode.MARKDOWN
        )
        
        # This will be handled by the callback handler now
        return
    
    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle callback queries from inline keyboards"""
        query = update.callback_query
        user_id = query.from_user.id
        
        # Check authorization
        if not self._is_authorized_user(user_id):
            await query.answer("❌ Unauthorized access.", show_alert=True)
            return
        
        # Parse callback data
        callback_data = query.data
        
        # Handle different types of callbacks
        if callback_data == "new_request":
            await query.answer("Send a new YouTube URL to process!")
            await query.edit_message_text(
                "📝 **Ready for new request**\n\n" +
                "Send me a YouTube URL to get started!",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        elif callback_data == "change_model":
            await query.answer("Choose a different AI model...")
            
            # Create model selection keyboard
            model_keyboard = []
            
            # Group models by category based on LLM config
            free_models = [
                ("🆓 FREE: DeepSeek R1", "model_openrouter_deepseek/deepseek-r1:free"),
                ("🆓 FREE: Gemma 3 27B", "model_openrouter_google/gemma-3-27b-it:free"),
                ("🆓 FREE: DeepSeek R1 Qwen", "model_openrouter_deepseek/deepseek-r1-distill-qwen-32b")
            ]
            
            fast_models = [
                ("⚡ GPT-5 Nano (Current)", "model_openai_gpt-5-nano"),
                ("⚡ Claude Haiku", "model_openrouter_anthropic/claude-3-haiku-20240307"),
                ("⚡ GPT-4o Mini", "model_openrouter_openai/gpt-4o-mini")
            ]
            
            balanced_models = [
                ("⚖️ GPT-4o", "model_openrouter_openai/gpt-4o"),
                ("⚖️ Claude Sonnet", "model_openrouter_anthropic/claude-3-5-sonnet-20241022"),
                ("⚖️ Gemini Flash", "model_openrouter_google/gemini-2.0-flash-exp")
            ]
            
            premium_models = [
                ("💎 Claude Opus 4", "model_openrouter_anthropic/claude-4-opus"),
                ("💎 GPT-5", "model_openai_gpt-5"),
                ("💎 DeepSeek R1", "model_openrouter_deepseek/deepseek-r1-0528")
            ]
            
            # Add models to keyboard (2 per row)
            all_models = free_models + fast_models + balanced_models + premium_models
            for i in range(0, len(all_models), 2):
                row = []
                for j in range(i, min(i + 2, len(all_models))):
                    name, callback = all_models[j]
                    # Highlight current model - handle both direct provider and openrouter formats
                    is_current = False
                    if hasattr(self, 'summarizer') and hasattr(self.summarizer, 'llm_provider'):
                        current_provider = self.summarizer.llm_provider
                        current_model = getattr(self.summarizer, 'model', '')
                        
                        if current_provider == "openai" and "openai_" in callback and current_model in callback:
                            is_current = True
                        elif current_provider == "openrouter" and "openrouter_" in callback and current_model in callback:
                            is_current = True
                    
                    if is_current:
                        name = f"✅ {name}"
                    row.append(InlineKeyboardButton(name, callback_data=callback))
                model_keyboard.append(row)
            
            # Add back button
            model_keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="back_to_main")])
            
            reply_markup = InlineKeyboardMarkup(model_keyboard)
            
            await query.edit_message_text(
                f"⚙️ **Choose AI Model**\n\n" +
                f"**Current:** {self.summarizer.llm_provider}/{self.summarizer.model}\n\n" +
                "🆓 **FREE MODELS** - No API costs!\n" +
                "⚡ **Fast & Affordable** - Low cost\n" +
                "⚖️ **Balanced Performance** - Mid cost\n" +
                "💎 **Premium Quality** - Higher cost\n\n" +
                "Select a model to switch:",
                reply_markup=reply_markup,
                parse_mode=ParseMode.MARKDOWN
            )
            return
        elif callback_data.startswith("model_"):
            # Handle model selection
            model_info = callback_data[6:]  # Remove "model_" prefix
            
            # Parse provider and model - handle OpenRouter format with slashes
            if model_info.startswith("openrouter_"):
                provider = "openrouter"
                model = model_info[11:]  # Remove "openrouter_" prefix
            else:
                model_parts = model_info.split("_", 1)
                if len(model_parts) == 2:
                    provider, model = model_parts
                else:
                    await query.answer("Invalid model format", show_alert=True)
                    return
            
            # Update the summarizer with new model
            try:
                from youtube_summarizer import YouTubeSummarizer
                self.summarizer = YouTubeSummarizer(llm_provider=provider, model=model)
                
                await query.answer(f"Switched to {provider}/{model}")
                
                # If we have a last video URL, automatically re-process it with the new model
                if self.last_video_url:
                    await query.edit_message_text(
                        f"✅ **Model Changed Successfully!**\n\n" +
                        f"**New Model:** {provider}/{model}\n\n" +
                        "🔄 **Re-processing your last video with the new model...**",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    
                    # Create callback for auto-processing with the new model
                    try:
                        # Create summary selection callbacks directly
                        comprehensive_callback = self._create_safe_callback_data("process_comprehensive", self.last_video_url)
                        audio_callback = self._create_safe_callback_data("process_audio", self.last_video_url) 
                        adaptive_callback = self._create_safe_callback_data("process_adaptive", self.last_video_url)
                        
                        # Create the summary selection keyboard directly
                        keyboard = [
                            [
                                InlineKeyboardButton("📝 Full Summary", callback_data=comprehensive_callback),
                                InlineKeyboardButton("🎙️ Audio Summary", callback_data=audio_callback)
                            ],
                            [
                                InlineKeyboardButton("🎯 AI Adaptive", callback_data=adaptive_callback)
                            ],
                            [
                                InlineKeyboardButton("⚙️ Change Model", callback_data="change_model")
                            ]
                        ]
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        
                        await query.edit_message_text(
                            f"✅ **Model Changed Successfully!**\n\n" +
                            f"**New Model:** {provider}/{model}\n\n" +
                            "Choose your summary preference:",
                            reply_markup=reply_markup,
                            parse_mode=ParseMode.MARKDOWN
                        )
                        
                        logger.info(f"Successfully switched to model {provider}/{model} for user {query.from_user.id}")
                        
                    except Exception as callback_error:
                        logger.error(f"Error creating auto-process callback: {callback_error}")
                        await query.edit_message_text(
                            f"✅ **Model Changed Successfully!**\n\n" +
                            f"**New Model:** {provider}/{model}\n\n" +
                            "Send a YouTube URL to test the new model!",
                            parse_mode=ParseMode.MARKDOWN
                        )
                else:
                    await query.edit_message_text(
                        f"✅ **Model Changed Successfully!**\n\n" +
                        f"**New Model:** {provider}/{model}\n\n" +
                        "Send a YouTube URL to test the new model!",
                        parse_mode=ParseMode.MARKDOWN
                    )
                
                logger.info(f"User {query.from_user.id} switched to model: {provider}/{model}")
                
            except Exception as e:
                await query.answer("Error switching model", show_alert=True)
                await query.edit_message_text(
                    f"❌ **Error Switching Model**\n\n" +
                    f"Could not switch to {provider}/{model}\n\n" +
                    f"Error: {str(e)}\n\n" +
                    "The current model remains active.",
                    parse_mode=ParseMode.MARKDOWN
                )
                logger.error(f"Error switching model for user {query.from_user.id}: {e}")
            return
        elif callback_data == "back_to_main":
            await query.answer("Back to main menu")
            await query.edit_message_text(
                "📝 **Ready for new request**\n\n" +
                "Send me a YouTube URL to get started!",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        elif callback_data.startswith("view_report_"):
            filename = callback_data[12:]  # Remove "view_report_" prefix
            
            # Check if file exists
            filepath = self.exports_dir / filename
            if not filepath.exists():
                await query.answer("Report not found or expired", show_alert=True)
                return
            
            # Get the report URL
            report_url = self._get_report_url(filename)
            
            await query.answer("Opening HTML report...")
            
            # Create clickable URL button for easy mobile access
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🌐 Open HTML Report", url=report_url)],
                [InlineKeyboardButton("🔄 Process Another", callback_data="new_request")]
            ])
            
            await query.edit_message_text(
                f"📄 **HTML Report Generated Successfully!**\n\n" +
                f"**📁 File:** `{filename}`\n\n" +
                f"**🔗 Direct URL:** `{report_url}`\n\n" +
                "**👆 Click the button above to open the report**",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
                disable_web_page_preview=True
            )
            return
        elif callback_data.startswith("download_mp3_"):
            mp3_filename = callback_data[13:]  # Remove "download_mp3_" prefix
            
            # Check if file exists
            mp3_filepath = self.exports_dir / mp3_filename
            if not mp3_filepath.exists():
                await query.answer("MP3 file not found or expired", show_alert=True)
                return
            
            await query.answer("Sending MP3 file...")
            
            try:
                with open(mp3_filepath, 'rb') as audio_file:
                    await context.bot.send_audio(
                        chat_id=query.message.chat_id,
                        audio=audio_file,
                        title="Audio Summary",
                        filename=mp3_filename,
                        caption="🎵 Your audio summary download"
                    )
                await query.edit_message_text(
                    f"✅ **MP3 File Sent Successfully!**\n\n" +
                    f"**📁 File:** `{mp3_filename}`\n\n" +
                    "The audio file has been sent above for download.",
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception as e:
                logger.error(f"Failed to send MP3 file: {e}")
                await query.answer("❌ Failed to send MP3 file", show_alert=True)
            return
        elif not callback_data.startswith("process_"):
            await query.answer("❌ Invalid action.", show_alert=True)
            return
        
        # Extract summary type and URL identifier
        parts = callback_data.split("_", 2)
        if len(parts) != 3:
            await query.answer("❌ Invalid action format.", show_alert=True)
            return
        
        summary_type = parts[1]  # comprehensive, brief, or adaptive
        url_identifier = parts[2]  # video ID or cached short ID
        
        # Resolve the actual URL
        youtube_url = self._resolve_callback_url(url_identifier)
        if not youtube_url:
            await query.answer("❌ Video URL expired or invalid.", show_alert=True)
            await query.edit_message_text(
                "❌ **Session Expired**\n\n" +
                "This video request has expired. Please send the YouTube URL again.",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        
        # Answer the callback query
        await query.answer(f"Processing {summary_type} summary...")
        
        # Edit the message to show processing status
        await query.edit_message_text(
            "🔄 **Processing YouTube video...**\n\n" +
            f"⏳ Generating {summary_type} summary...\n" +
            "This may take 1-2 minutes for longer videos.",
            parse_mode=ParseMode.MARKDOWN
        )
        
        try:
            # Process the video
            logger.info(f"Processing {summary_type} video for user {user_id}: {youtube_url}")
            result = await self.summarizer.process_video(youtube_url, summary_type=summary_type)
            
            # Check for errors
            if 'error' in result:
                error_text = result['error']
                
                # Special handling for transcript issues
                if 'No transcript available for this video' in error_text:
                    # Our new rejection for description-only videos
                    error_message = f"""🚫 **Cannot Summarize This Video**

This video only has a description/table of contents - no actual transcript or captions are available. I cannot create accurate summaries from limited descriptions.

💡 **Look for videos with:**
• The [CC] closed captions icon on YouTube
• Manual subtitles (usually educational content)
• Auto-generated captions (most talking videos)
• News channels, tutorials, podcasts, interviews

🔄 **Try another video!** Send me a different YouTube URL."""
                elif 'No usable transcript found' in error_text:
                    error_message = f"""📺 **No Transcript Available**

{error_text}

💡 **Tips for success:**
• Look for the [CC] icon on YouTube videos  
• Try videos from news channels, educational content, or popular YouTubers
• Avoid music videos, silent films, or videos without speech
• Podcasts and interview videos usually work great!

🔄 **Ready for another video!** Send me a different YouTube URL."""
                else:
                    # Generic error handling
                    error_message = f"""❌ **Processing Failed**

Error: {error_text}

Please try again with a different video or contact support if the issue persists."""
                
                await query.edit_message_text(error_message, parse_mode=ParseMode.MARKDOWN)
                return
            
            # Delete the processing message
            await query.delete_message()
            
            # Format and send results
            formatted_messages = self._format_summary_message(result, summary_type)
            
            for i, message_chunk in enumerate(formatted_messages):
                await context.bot.send_chat_action(chat_id=query.message.chat_id, action=ChatAction.TYPING)
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=message_chunk,
                    parse_mode=ParseMode.MARKDOWN
                )
                
                # Small delay between messages to avoid rate limiting
                if i < len(formatted_messages) - 1:
                    await asyncio.sleep(0.5)
            
            # Generate TTS audio for audio summaries
            audio_filepath = None
            if summary_type == "audio":
                summary_text = result.get('summary', {}).get('summary', '')
                if summary_text:
                    # Create audio filename based on video ID
                    video_id = result.get('metadata', {}).get('video_id', 'unknown')
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    audio_filename = f"{video_id}_{timestamp}.mp3"
                    
                    audio_filepath = await self.summarizer.generate_tts_audio(summary_text, audio_filename)
                    if audio_filepath:
                        logger.info(f"✅ Generated TTS audio: {audio_filepath}")
                        
                        # Send TTS audio as voice message to Telegram
                        try:
                            video_title = result.get('metadata', {}).get('title', 'Unknown Video')
                            duration = result.get('metadata', {}).get('duration', None)
                            
                            with open(audio_filepath, 'rb') as audio_file:
                                await context.bot.send_voice(
                                    chat_id=user_id,
                                    voice=audio_file,
                                    caption=f"🎧 Audio Summary: {video_title}",
                                    duration=duration
                                )
                                logger.info("✅ Sent TTS audio as voice message")
                        except Exception as e:
                            logger.error(f"❌ Failed to send voice message: {e}")
                    else:
                        logger.warning("⚠️ TTS generation failed")
            
            # Generate HTML report (after TTS so audio_filepath is available)
            html_filepath = self._generate_html_report(result, summary_type, audio_filepath)
            
            # Create regeneration buttons for different summary types using the same YouTube URL
            regen_buttons = []
            try:
                # Create new callback data for regeneration buttons
                regen_comprehensive_callback = self._create_safe_callback_data("process_comprehensive", youtube_url)
                regen_audio_callback = self._create_safe_callback_data("process_audio", youtube_url)
                regen_adaptive_callback = self._create_safe_callback_data("process_adaptive", youtube_url)
                
                if summary_type != "comprehensive":
                    regen_buttons.append(InlineKeyboardButton("📝 Full Summary", callback_data=regen_comprehensive_callback))
                if summary_type != "audio":
                    regen_buttons.append(InlineKeyboardButton("🎙️ Audio Summary", callback_data=regen_audio_callback))
                if summary_type != "adaptive":
                    regen_buttons.append(InlineKeyboardButton("🎯 AI Adaptive", callback_data=regen_adaptive_callback))
            except Exception as e:
                logger.warning(f"Could not create regeneration buttons: {e}")
                # Fallback: don't add regeneration buttons if callback creation fails
            
            # Add action buttons after sending the summary
            action_buttons = []
            
            # Add View Report button if HTML was generated successfully
            if html_filepath:
                filename = Path(html_filepath).name
                report_url = self._get_report_url(filename)
                action_buttons.append(InlineKeyboardButton("🌐 Open HTML Report", url=report_url))
                logger.info(f"✅ Added HTML report button for: {filename}")
            else:
                logger.warning("❌ No HTML filepath - HTML report button not added")
            
            # Add Download MP3 button for audio summaries
            if summary_type == "audio" and audio_filepath:
                try:
                    download_mp3_callback = self._create_safe_callback_data("download_mp3", Path(audio_filepath).name)
                    action_buttons.append(InlineKeyboardButton("⬇️ Download MP3", callback_data=download_mp3_callback))
                    logger.info(f"✅ Added Download MP3 button for: {Path(audio_filepath).name}")
                except Exception as e:
                    logger.warning(f"Could not create Download MP3 button: {e}")
            
            # Always add dashboard link for easy access to all summaries
            action_buttons.append(InlineKeyboardButton("📋 View Dashboard", 
                                                      url="https://chief-inspired-lab.ngrok-free.app"))
            
            # Arrange buttons in rows
            action_keyboard = []
            
            # Row 1: View Report and Dashboard buttons
            if action_buttons:
                action_keyboard.append(action_buttons)
            
            # Row 2-3: Regeneration buttons (max 2 per row for mobile)
            if regen_buttons:
                if len(regen_buttons) <= 2:
                    action_keyboard.append(regen_buttons)
                else:
                    action_keyboard.append(regen_buttons[:2])
                    action_keyboard.append(regen_buttons[2:])
            
            action_markup = InlineKeyboardMarkup(action_keyboard)
            
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text="**What would you like to do next?**",
                reply_markup=action_markup,
                parse_mode=ParseMode.MARKDOWN
            )
            
            logger.info(f"Successfully processed {summary_type} video for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error processing {summary_type} video for user {user_id}: {e}")
            
            error_message = f"""❌ **Unexpected Error**

An error occurred while processing your video:
`{str(e)}`

Please try again or contact support if the issue persists."""
            
            try:
                await query.edit_message_text(error_message, parse_mode=ParseMode.MARKDOWN)
            except:
                await context.bot.send_message(
                    chat_id=query.message.chat_id,
                    text=error_message,
                    parse_mode=ParseMode.MARKDOWN
                )
    
    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors in the bot"""
        logger.error(f"Exception while handling an update: {context.error}")
        
        # Try to inform the user about the error
        if update and hasattr(update, 'effective_chat') and update.effective_chat:
            try:
                await context.bot.send_message(
                    chat_id=update.effective_chat.id,
                    text="❌ An unexpected error occurred. Please try again later.",
                    parse_mode=ParseMode.MARKDOWN
                )
            except:
                pass
    
    def initialize_bot(self):
        """Initialize the bot application and handlers"""
        # Initialize summarizer
        if not self.initialize_summarizer():
            logger.error("Failed to initialize summarizer. Exiting.")
            return False

        # Validate callback data creation
        self._validate_callback_data_creation()
        
        # Cleanup expired HTML reports
        self._cleanup_expired_reports()

        # Create application
        self.application = Application.builder().token(self.token).build()

        # Add handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        self.application.add_handler(CallbackQueryHandler(self.handle_callback_query))

        # Add error handler
        self.application.add_error_handler(self.error_handler)

        # Start web server for HTML reports
        self._start_web_server()

        logger.info("🤖 YouTube Telegram Bot initialized...")
        logger.info(f"📝 Authorized users: {len(self.allowed_user_ids)}")
        logger.info(f"🧠 Using AI model: {self.summarizer.llm_provider}/{self.summarizer.model}")

        return True
    
    def start_polling(self):
        """Start the bot with polling (synchronous/blocking)"""
        if not self.initialize_bot():
            return

        logger.info("🚀 Starting bot polling...")
        # Use the synchronous runner provided by python-telegram-bot
        self.application.run_polling(drop_pending_updates=True)
    
    async def shutdown(self):
        """Gracefully shutdown the bot"""
        # Stop web server first
        self._stop_web_server()
        
        if self.application:
            logger.info("🔄 Shutting down bot...")
            await self.application.shutdown()
            logger.info("✅ Bot shutdown complete")
    
    def start_polling(self):
        """Start the bot with polling (synchronous/blocking)"""
        if not self.initialize_bot():
            return

        logger.info("🚀 Starting bot polling...")
        # Use the synchronous runner provided by python-telegram-bot
        self.application.run_polling(drop_pending_updates=True)
    
    async def shutdown(self):
        """Gracefully shutdown the bot"""
        # Stop web server first
        self._stop_web_server()
        
        if self.application:
            logger.info("🔄 Shutting down bot...")
            await self.application.shutdown()
            logger.info("✅ Bot shutdown complete")

    # The following methods are now removed:
    # - run_polling_sync
    # - async def run_simple_async(self)
    # - def run_simple(self)


def main():
    """Main function to run the Telegram bot (synchronous/blocking entrypoint)"""

    # Load environment variables
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    allowed_users_str = os.getenv('TELEGRAM_USER_ID', '')

    # Validate required environment variables
    if not bot_token:
        logger.error("❌ TELEGRAM_BOT_TOKEN environment variable is required")
        return 1

    if not allowed_users_str:
        logger.error("❌ TELEGRAM_USER_ID environment variable is required")
        return 1

    # Parse allowed user IDs
    try:
        allowed_user_ids = [int(uid.strip()) for uid in allowed_users_str.split(',') if uid.strip()]
        if not allowed_user_ids:
            raise ValueError("No valid user IDs found")
    except ValueError as e:
        logger.error(f"❌ Invalid TELEGRAM_USER_ID format: {e}")
        logger.error("Format should be: TELEGRAM_USER_ID=123456789,987654321")
        return 1

    # Create bot instance
    bot = YouTubeTelegramBot(bot_token, allowed_user_ids)

    try:
        logger.info("🤖 Starting YouTube Telegram Bot...")
        bot.start_polling()
        return 0
    except KeyboardInterrupt:
        logger.info("🛑 Bot stopped by user")
        bot._stop_web_server()
        return 0
    except Exception as e:
        logger.error(f"❌ Bot crashed: {e}")
        bot._stop_web_server()
        return 1


if __name__ == "__main__":
    sys.exit(main())