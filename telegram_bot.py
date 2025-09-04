#!/usr/bin/env python3
"""
YouTube Video Summarizer Bot - Main Orchestrator
Integrates Telegram bot, web dashboard, and modular processing components
Runs both Telegram bot service and web dashboard HTTP server
"""

import asyncio
import os
import re
import sys
import logging
import time
import hashlib
import json
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
import socket

# Import our modular components
from modules.telegram_handler import YouTubeTelegramBot
from modules.report_generator import JSONReportGenerator
from youtube_summarizer import YouTubeSummarizer

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
        for line in result.stdout.split('\n'):
            if '=' in line and not line.startswith('_'):
                key, value = line.split('=', 1)
                os.environ[key] = value
        print(f"📁 Loaded environment from .envrc")
except Exception as e:
    pass  # Continue if .envrc sourcing fails

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Template loading utility
def load_template(template_name: str) -> Optional[str]:
    """Load HTML template from file"""
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

# Extract report metadata utility
def extract_report_metadata(file_path: Path) -> Dict:
    """Extract metadata from HTML or JSON report file"""
    try:
        # Skip hidden files
        if file_path.name.startswith('.') or file_path.name.startswith('._'):
            raise ValueError(f"Skipping hidden file: {file_path.name}")
            
        # Handle JSON reports (preferred)
        if file_path.suffix == '.json':
            return extract_json_report_metadata(file_path)
        
        # Handle HTML reports (legacy)
        elif file_path.suffix == '.html':
            return extract_html_report_metadata(file_path)
        
        else:
            raise ValueError(f"Unsupported file type: {file_path.suffix}")
            
    except Exception as e:
        logger.warning(f"Error processing report {file_path.name}: {e}")
        return {
            'filename': file_path.name,
            'title': file_path.stem,
            'channel': 'Unknown Channel',
            'model': 'Unknown',
            'summary_preview': 'Error loading preview',
            'thumbnail_url': '',
            'created_date': 'Unknown',
            'created_time': 'Unknown',
            'timestamp': 0,
            'url': '',
            'video_id': '',
            'duration': 0
        }

def extract_json_report_metadata(file_path: Path) -> Dict:
    """Extract metadata from JSON report file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            report = json.load(f)
        
        # Extract data from JSON structure
        video_info = report.get('video', {})
        summary_info = report.get('summary', {})
        processing_info = report.get('processing', {})
        metadata = report.get('metadata', {})
        
        # Get file modification time for fallback
        mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
        
        # Try to parse generated_at timestamp
        generated_at = metadata.get('generated_at', '')
        try:
            if generated_at:
                report_time = datetime.fromisoformat(generated_at.replace('Z', '+00:00'))
            else:
                report_time = mtime
        except:
            report_time = mtime
        
        return {
            'filename': file_path.name,
            'title': video_info.get('title', 'Unknown Title'),
            'channel': video_info.get('channel', 'Unknown Channel'),
            'model': processing_info.get('model', 'Unknown Model'),
            'summary_preview': (summary_info.get('content', {}).get('summary', '')[:150] + "...") if summary_info.get('content', {}).get('summary') else "No preview available",
            'thumbnail_url': video_info.get('thumbnail', ''),
            'created_date': report_time.strftime('%B %d, %Y'),
            'created_time': report_time.strftime('%H:%M'),
            'timestamp': report_time.timestamp(),
            'url': video_info.get('url', ''),
            'video_id': video_info.get('video_id', ''),
            'duration': video_info.get('duration', 0)
        }
        
    except Exception as e:
        logger.error(f"Error extracting JSON metadata from {file_path.name}: {e}")
        raise

def extract_html_report_metadata(file_path: Path) -> Dict:
    """Extract metadata from HTML report file (legacy support)"""
    try:
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
        
        return {
            'filename': file_path.name,
            'title': title,
            'channel': channel,
            'model': model,
            'summary_preview': summary_preview,
            'thumbnail_url': thumbnail_url,
            'created_date': mtime.strftime('%B %d, %Y'),
            'created_time': mtime.strftime('%H:%M'),
            'timestamp': mtime.timestamp(),
            'url': '',  # HTML reports don't typically store the original URL
            'video_id': '',
            'duration': 0
        }
        
    except Exception as e:
        logger.error(f"Error extracting HTML metadata from {file_path.name}: {e}")
        raise

class ModernDashboardHTTPRequestHandler(SimpleHTTPRequestHandler):
    """HTTP request handler with modern template system"""
    
    def do_GET(self):
        if self.path == '/':
            self.serve_dashboard()
        elif self.path == '/status':
            self.serve_status()
        elif self.path.startswith('/api/'):
            self.serve_api()
        elif self.path.endswith('.css'):
            self.serve_css()
        elif self.path.endswith('.js'):
            self.serve_js()
        elif self.path.endswith('.html') and self.path != '/':
            self.serve_report()
        elif self.path.endswith('.json') and self.path != '/':
            self.serve_report()
        else:
            super().do_GET()
    
    def do_POST(self):
        if self.path == '/delete-reports':
            self.handle_delete_reports()
        else:
            self.send_error(404, "Endpoint not found")
    
    def serve_dashboard(self):
        """Serve the modern dashboard using templates"""
        try:
            # Get report files from multiple directories (JSON preferred, HTML legacy)
            report_dirs = [
                Path('./data/reports'),  # JSON reports (primary)
                Path('./exports'),       # HTML reports (legacy)
                Path('.')               # Current directory (legacy)
            ]
            
            all_report_files = []
            
            for report_dir in report_dirs:
                if report_dir.exists():
                    # Get JSON reports (preferred)
                    json_files = [f for f in report_dir.glob('*.json') 
                                   if not f.name.startswith('._')
                                   and not f.name.startswith('.')]
                    all_report_files.extend(json_files)
                    
                    # Get HTML reports (legacy support)
                    html_files = [f for f in report_dir.glob('*.html') 
                                   if f.name not in ['dashboard_template.html', 'report_template.html']
                                   and not f.name.startswith('._')
                                   and not f.name.startswith('.')]
                    all_report_files.extend(html_files)
            
            # Remove duplicates and sort by modification time (newest first)
            unique_files = list(set(all_report_files))
            sorted_files = sorted(unique_files, key=lambda f: f.stat().st_mtime, reverse=True)
            
            # Extract metadata from all reports
            reports_data = []
            for file_path in sorted_files:
                try:
                    metadata = extract_report_metadata(file_path)
                    reports_data.append(metadata)
                except Exception as e:
                    logger.warning(f"Skipping file {file_path.name}: {e}")
                    continue
            
            # Load dashboard template
            template_content = load_template('dashboard_template.html')
            
            if template_content:
                # Get base URL
                base_url = os.getenv('NGROK_URL', 'https://chief-inspired-lab.ngrok-free.app')
                
                # Replace template placeholders
                dashboard_html = template_content.format(
                    reports_data=json.dumps(reports_data, ensure_ascii=False),
                    base_url=base_url
                )
                
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.send_header('Cache-Control', 'no-cache')
                self.end_headers()
                self.wfile.write(dashboard_html.encode('utf-8'))
            else:
                # Fallback error page
                error_html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Template Error</title>
    <style>
        body {{ font-family: Arial, sans-serif; padding: 2rem; }}
        .error {{ color: #dc2626; background: #fef2f2; padding: 1rem; border-radius: 0.5rem; margin: 1rem 0; }}
        .report-list {{ margin: 1rem 0; }}
        .report-item {{ margin: 0.5rem 0; }}
    </style>
</head>
<body>
    <h1>🚨 Dashboard Template Error</h1>
    <div class="error">
        <p><strong>Could not load dashboard_template.html</strong></p>
        <p>Please ensure the template file exists in the project directory.</p>
    </div>
    
    <h2>📊 Available Reports ({len(html_files)})</h2>
    <div class="report-list">"""
                
                for file_path in html_files[:20]:  # Show first 20
                    metadata = extract_report_metadata(file_path)
                    error_html += f"""
        <div class="report-item">
            <a href="/{file_path.name}">{metadata['title']}</a>
            <small> - {metadata['channel']} ({metadata['model']})</small>
        </div>"""
                
                if len(html_files) > 20:
                    error_html += f"<p><em>... and {len(html_files) - 20} more reports</em></p>"
                
                error_html += """
    </div>
</body>
</html>"""
                
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(error_html.encode('utf-8'))
                
        except Exception as e:
            logger.error(f"Error serving dashboard: {e}")
            self.send_error(500, "Internal server error")
    
    def serve_css(self):
        """Serve CSS files"""
        try:
            filename = self.path[1:]  # Remove leading slash
            css_file = Path('static') / filename
            if css_file.exists():
                self.send_response(200)
                self.send_header('Content-type', 'text/css')
                self.send_header('Cache-Control', 'public, max-age=3600')
                self.end_headers()
                self.wfile.write(css_file.read_bytes())
            else:
                self.send_error(404, "CSS file not found")
        except Exception as e:
            logger.error(f"Error serving CSS {self.path}: {e}")
            self.send_error(500, "Error serving CSS")
    
    def serve_js(self):
        """Serve JavaScript files"""
        try:
            filename = self.path[1:]  # Remove leading slash
            js_file = Path('static') / filename
            if js_file.exists():
                self.send_response(200)
                self.send_header('Content-type', 'application/javascript')
                self.send_header('Cache-Control', 'public, max-age=3600')
                self.end_headers()
                self.wfile.write(js_file.read_bytes())
            else:
                self.send_error(404, "JavaScript file not found")
        except Exception as e:
            logger.error(f"Error serving JS {self.path}: {e}")
            self.send_error(500, "Error serving JavaScript")
    
    def serve_report(self):
        """Serve individual report pages"""
        try:
            filename = self.path[1:]  # Remove leading slash
            
            # Look for HTML files first (legacy)
            html_paths = [Path(filename), Path('./exports') / filename]
            for path in html_paths:
                if path.exists() and path.suffix == '.html':
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html; charset=utf-8')
                    self.send_header('Cache-Control', 'no-cache')
                    self.end_headers()
                    self.wfile.write(path.read_bytes())
                    return
            
            # Look for JSON files in data/reports
            if filename.endswith('.json'):
                json_path = Path('./data/reports') / filename
                if json_path.exists():
                    self.serve_json_report(json_path)
                    return
            else:
                # Try adding .json extension if not present
                json_filename = filename + '.json'
                json_path = Path('./data/reports') / json_filename
                if json_path.exists():
                    self.serve_json_report(json_path)
                    return
            
            self.send_error(404, "Report not found")
        except Exception as e:
            logger.error(f"Error serving report {self.path}: {e}")
            self.send_error(500, "Error serving report")
    
    def serve_json_report(self, json_path: Path):
        """Serve a JSON report wrapped in professional HTML template"""
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                report_data = json.load(f)
            
            # Extract data for display
            video_info = report_data.get('video', {})
            summary = report_data.get('summary', {})
            processing = report_data.get('processing', {})
            stats = report_data.get('stats', {})
            metadata = report_data.get('metadata', {})
            
            title = video_info.get('title', 'Unknown Video')
            channel = video_info.get('channel', 'Unknown Channel')
            duration_str = video_info.get('duration_string', '')
            url = video_info.get('url', '')
            thumbnail = video_info.get('thumbnail', '')
            view_count = video_info.get('view_count', 0)
            upload_date = video_info.get('upload_date', '')
            
            # Properly extract summary content
            summary_content = summary.get('content', {})
            if isinstance(summary_content, dict):
                summary_text = summary_content.get('summary', 'No summary available')
                headline = summary_content.get('headline', '')
                summary_type = summary_content.get('summary_type', 'comprehensive')
            else:
                summary_text = str(summary_content) if summary_content else 'No summary available'
                headline = ''
                summary_type = summary.get('type', 'comprehensive')
            
            # Get analysis data
            analysis = summary.get('analysis', {})
            categories = analysis.get('category', [])
            target_audience = analysis.get('target_audience', '')
            
            # Get processing info
            model = processing.get('model', 'Unknown')
            provider = processing.get('llm_provider', 'Unknown')
            
            # Format dates
            try:
                if upload_date and len(upload_date) == 8:
                    formatted_date = f"{upload_date[4:6]}/{upload_date[6:8]}/{upload_date[:4]}"
                else:
                    formatted_date = upload_date or 'Unknown'
            except:
                formatted_date = 'Unknown'
            
            # Format view count
            if view_count:
                if view_count >= 1000000:
                    formatted_views = f"{view_count/1000000:.1f}M views"
                elif view_count >= 1000:
                    formatted_views = f"{view_count/1000:.1f}K views"
                else:
                    formatted_views = f"{view_count:,} views"
            else:
                formatted_views = 'Views unknown'
            
            # Create professional HTML template
            html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - YTV2 Report</title>
    <style>
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0; padding: 0; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh; color: #333;
        }}
        .container {{ max-width: 1000px; margin: 0 auto; padding: 20px; }}
        .back-button {{ 
            display: inline-flex; align-items: center; gap: 8px; 
            background: rgba(255,255,255,0.9); padding: 12px 20px; 
            border-radius: 25px; text-decoration: none; color: #2563eb;
            font-weight: 500; margin-bottom: 30px; backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.2); transition: all 0.3s ease;
        }}
        .back-button:hover {{ background: rgba(255,255,255,1); transform: translateY(-2px); }}
        
        .video-header {{
            background: rgba(255,255,255,0.95); backdrop-filter: blur(20px);
            border-radius: 20px; padding: 30px; margin-bottom: 30px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1); border: 1px solid rgba(255,255,255,0.2);
        }}
        
        .video-thumbnail {{
            width: 100%; max-width: 500px; border-radius: 15px; margin-bottom: 20px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.15);
        }}
        
        .video-title {{ 
            font-size: 2em; font-weight: 700; color: #1a365d; margin: 0 0 15px 0; 
            line-height: 1.3;
        }}
        
        .video-meta {{
            display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px; margin-top: 25px;
        }}
        
        .meta-item {{
            background: rgba(59,130,246,0.1); padding: 15px; border-radius: 12px;
            border-left: 4px solid #3b82f6;
        }}
        
        .meta-label {{ font-weight: 600; color: #1e40af; font-size: 0.9em; }}
        .meta-value {{ color: #374151; margin-top: 5px; }}
        
        .content-sections {{
            display: grid; gap: 30px; margin-top: 30px;
        }}
        
        .section {{
            background: rgba(255,255,255,0.95); backdrop-filter: blur(20px);
            border-radius: 20px; padding: 30px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1); border: 1px solid rgba(255,255,255,0.2);
        }}
        
        .section-title {{
            font-size: 1.5em; font-weight: 600; color: #1a365d; margin: 0 0 20px 0;
            display: flex; align-items: center; gap: 10px;
        }}
        
        .section-icon {{ font-size: 1.2em; }}
        
        .summary-text {{
            line-height: 1.8; color: #374151; font-size: 1.1em;
            white-space: pre-line; background: rgba(249,250,251,0.8);
            padding: 20px; border-radius: 12px; border: 1px solid #e5e7eb;
        }}
        
        .headline {{ 
            background: linear-gradient(135deg, #3b82f6, #1d4ed8);
            color: white; padding: 20px; border-radius: 12px; margin-bottom: 20px;
            font-size: 1.2em; font-weight: 500; text-align: center;
        }}
        
        .tags {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 15px; }}
        .tag {{ 
            background: #dbeafe; color: #1e40af; padding: 6px 12px; 
            border-radius: 20px; font-size: 0.85em; font-weight: 500;
        }}
        
        .youtube-link {{
            display: inline-flex; align-items: center; gap: 8px;
            background: #ff0000; color: white; padding: 12px 20px;
            border-radius: 25px; text-decoration: none; font-weight: 500;
            transition: all 0.3s ease;
        }}
        .youtube-link:hover {{ background: #cc0000; transform: translateY(-2px); }}
        
        @media (max-width: 768px) {{
            .container {{ padding: 15px; }}
            .video-meta {{ grid-template-columns: 1fr; }}
            .video-title {{ font-size: 1.5em; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <a href="/" class="back-button">
            <span>←</span> Back to Dashboard
        </a>
        
        <div class="video-header">
            {f'<img src="{thumbnail}" alt="Video thumbnail" class="video-thumbnail">' if thumbnail else ''}
            <h1 class="video-title">{title}</h1>
            
            <div class="video-meta">
                <div class="meta-item">
                    <div class="meta-label">📺 Channel</div>
                    <div class="meta-value">{channel}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">⏱️ Duration</div>
                    <div class="meta-value">{duration_str}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">👀 Views</div>
                    <div class="meta-value">{formatted_views}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">📅 Upload Date</div>
                    <div class="meta-value">{formatted_date}</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">🤖 AI Model</div>
                    <div class="meta-value">{model} ({provider})</div>
                </div>
                <div class="meta-item">
                    <div class="meta-label">📝 Summary Type</div>
                    <div class="meta-value">{summary_type.title()}</div>
                </div>
            </div>
        </div>
        
        <div class="content-sections">
            <div class="section">
                <h2 class="section-title">
                    <span class="section-icon">📋</span>
                    Summary
                </h2>
                {f'<div class="headline">{headline}</div>' if headline else ''}
                <div class="summary-text">{summary_text}</div>
                
                {'<div class="tags">' + " ".join([f'<span class="tag">{cat}</span>' for cat in categories]) + '</div>' if categories else ''}
            </div>
            
            {f'''<div class="section">
                <h2 class="section-title">
                    <span class="section-icon">🎯</span>
                    Target Audience
                </h2>
                <p style="color: #374151; line-height: 1.6; font-size: 1.1em;">{target_audience}</p>
            </div>''' if target_audience else ''}
            
            {f'''<div class="section" style="text-align: center;">
                <a href="{url}" target="_blank" class="youtube-link">
                    <span>▶️</span> Watch on YouTube
                </a>
            </div>''' if url else ''}
        </div>
    </div>
</body>
</html>"""
            
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            self.wfile.write(html_content.encode('utf-8'))
            
        except Exception as e:
            logger.error(f"Error serving JSON report {json_path}: {e}")
            self.send_error(500, "Error serving JSON report")
    
    def serve_status(self):
        """Serve system status endpoint"""
        try:
            # Check if Telegram bot is configured
            telegram_configured = bool(os.getenv('TELEGRAM_BOT_TOKEN'))
            users_configured = bool(os.getenv('TELEGRAM_ALLOWED_USERS'))
            
            # Count reports
            report_generator = JSONReportGenerator()
            json_reports = len(report_generator.list_reports())
            
            html_reports = 0
            for report_dir in [Path('./exports'), Path('.')]:
                if report_dir.exists():
                    html_reports += len([f for f in report_dir.glob('*.html') 
                                       if f.name not in ['dashboard_template.html', 'report_template.html']
                                       and not f.name.startswith('._')])
            
            status_data = {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "services": {
                    "dashboard": "running",
                    "telegram_bot": "configured" if telegram_configured and users_configured else "not_configured"
                },
                "reports": {
                    "json_reports": json_reports,
                    "html_reports": html_reports,
                    "total_reports": json_reports + html_reports
                },
                "configuration": {
                    "telegram_configured": telegram_configured,
                    "users_configured": users_configured,
                    "web_port": os.getenv('WEB_PORT', 6452)
                }
            }
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            self.wfile.write(json.dumps(status_data, indent=2).encode())
            
        except Exception as e:
            logger.error(f"Error serving status: {e}")
            error_data = {"status": "error", "message": str(e)}
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(error_data).encode())
    
    def serve_api(self):
        """Serve API endpoints"""
        try:
            if self.path == '/api/reports':
                self.serve_api_reports()
            elif self.path.startswith('/api/reports/'):
                self.serve_api_report_detail()
            elif self.path == '/api/config':
                self.serve_api_config()
            else:
                self.send_error(404, "API endpoint not found")
        except Exception as e:
            logger.error(f"Error serving API {self.path}: {e}")
            self.send_error(500, "API error")
    
    def serve_api_reports(self):
        """Serve reports list API endpoint"""
        try:
            # Get all reports (JSON preferred, HTML legacy)
            report_generator = JSONReportGenerator()
            json_reports = report_generator.list_reports()
            
            # Convert to API format
            api_reports = []
            for report in json_reports:
                api_reports.append({
                    "id": report.get('filename', '').replace('.json', ''),
                    "filename": report['filename'],
                    "title": report['title'],
                    "channel": report['channel'],
                    "duration": report.get('duration', 0),
                    "created_date": report.get('created_date', ''),
                    "created_time": report.get('created_time', ''),
                    "timestamp": report.get('timestamp', ''),
                    "type": "json",
                    "url": report.get('url', ''),
                    "video_id": report.get('video_id', ''),
                    "thumbnail_url": report.get('thumbnail', ''),
                    "model": report.get('model', 'Unknown'),
                    "summary_preview": report.get('summary_preview', '')
                })
            
            # Add HTML reports for legacy support
            html_dirs = [Path('./exports'), Path('.')]
            for report_dir in html_dirs:
                if report_dir.exists():
                    html_files = [f for f in report_dir.glob('*.html') 
                                if f.name not in ['dashboard_template.html', 'report_template.html']
                                and not f.name.startswith('._')]
                    
                    for html_file in html_files:
                        try:
                            metadata = extract_html_report_metadata(html_file)
                            api_reports.append({
                                "id": html_file.stem,
                                "filename": metadata['filename'],
                                "title": metadata['title'],
                                "channel": metadata['channel'],
                                "duration": 0,
                                "created_date": metadata['created_date'],
                                "created_time": metadata['created_time'],
                                "timestamp": metadata['timestamp'],
                                "type": "html",
                                "url": "",
                                "video_id": ""
                            })
                        except Exception:
                            continue
            
            # Sort by timestamp (newest first)
            api_reports.sort(key=lambda x: x['timestamp'], reverse=True)
            
            response_data = {
                "reports": api_reports,
                "total": len(api_reports),
                "json_count": len(json_reports),
                "html_count": len(api_reports) - len(json_reports)
            }
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            self.wfile.write(json.dumps(response_data, ensure_ascii=False, indent=2).encode())
            
        except Exception as e:
            logger.error(f"Error serving reports API: {e}")
            error_data = {"error": "Failed to load reports", "message": str(e)}
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(error_data).encode())
    
    def serve_api_report_detail(self):
        """Serve individual report API endpoint"""
        # Extract report ID from path
        report_id = self.path.split('/')[-1]
        
        try:
            # Look for JSON report first
            json_file = Path('./data/reports') / f"{report_id}.json"
            if json_file.exists():
                report_data = json.loads(json_file.read_text())
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(report_data, ensure_ascii=False, indent=2).encode())
                return
            
            # Look for HTML report (legacy)
            html_dirs = [Path('./exports'), Path('.')]
            for html_dir in html_dirs:
                html_file = html_dir / f"{report_id}.html"
                if html_file.exists():
                    metadata = extract_html_report_metadata(html_file)
                    # For HTML reports, we return limited metadata
                    response_data = {
                        "type": "html",
                        "metadata": metadata,
                        "message": "HTML report - limited API data available"
                    }
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps(response_data, ensure_ascii=False, indent=2).encode())
                    return
            
            # Report not found
            self.send_error(404, "Report not found")
            
        except Exception as e:
            logger.error(f"Error serving report detail API: {e}")
            error_data = {"error": "Failed to load report", "message": str(e)}
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(error_data).encode())
    
    def serve_api_config(self):
        """Serve configuration API endpoint"""
        try:
            config_data = {
                "telegram": {
                    "bot_configured": bool(os.getenv('TELEGRAM_BOT_TOKEN')),
                    "users_configured": bool(os.getenv('TELEGRAM_ALLOWED_USERS'))
                },
                "web": {
                    "port": int(os.getenv('WEB_PORT', 6452)),
                    "ngrok_url": os.getenv('NGROK_URL', '')
                },
                "directories": {
                    "json_reports": str(Path('./data/reports').absolute()),
                    "html_reports": str(Path('./exports').absolute())
                },
                "version": "1.0.0"
            }
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Cache-Control', 'public, max-age=300')  # Cache for 5 minutes
            self.end_headers()
            self.wfile.write(json.dumps(config_data, indent=2).encode())
            
        except Exception as e:
            logger.error(f"Error serving config API: {e}")
            error_data = {"error": "Failed to load configuration", "message": str(e)}
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(error_data).encode())
    
    def handle_delete_reports(self):
        """Handle POST request to delete selected reports"""
        try:
            # Read request body
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            request_data = json.loads(post_data.decode('utf-8'))
            
            filenames = request_data.get('files', [])
            if not filenames:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "No files specified"}).encode())
                return
            
            deleted_count = 0
            errors = []
            
            # Delete files from all possible locations
            search_dirs = [
                Path('./data/reports'),  # JSON reports
                Path('./exports'),       # HTML reports
                Path('.')               # Legacy location
            ]
            
            for filename in filenames:
                deleted = False
                for search_dir in search_dirs:
                    if search_dir.exists():
                        # Try different extensions
                        for ext in ['.json', '.html', '']:
                            file_path = search_dir / (filename + ext if not filename.endswith(ext) else filename)
                            if file_path.exists():
                                try:
                                    file_path.unlink()
                                    deleted = True
                                    deleted_count += 1
                                    logger.info(f"Deleted report: {file_path}")
                                    break
                                except Exception as e:
                                    errors.append(f"Failed to delete {file_path}: {e}")
                    if deleted:
                        break
                
                if not deleted:
                    errors.append(f"File not found: {filename}")
            
            # Send response
            response_data = {
                "deleted": deleted_count,
                "errors": errors,
                "message": f"Successfully deleted {deleted_count} reports"
            }
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response_data).encode())
            
        except Exception as e:
            logger.error(f"Error handling delete request: {e}")
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

def start_http_server():
    """Start the HTTP server for dashboard access"""
    port = int(os.getenv('WEB_PORT', 6452))
    
    # Find available port if the default is taken
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(('localhost', port)) == 0:
            logger.info(f"Port {port} is busy, using port {port + 1}")
            port = port + 1
    
    try:
        server_address = ('', port)
        httpd = HTTPServer(server_address, ModernDashboardHTTPRequestHandler)
        
        logger.info(f"🌐 HTTP Server started on port {port}")
        logger.info(f"📊 Dashboard available at: http://localhost:{port}")
        
        def run_server():
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                logger.info("HTTP Server stopped")
                httpd.shutdown()
        
        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()
        
        return httpd, port
        
    except Exception as e:
        logger.error(f"Failed to start HTTP server: {e}")
        return None, None

async def main():
    """Main async function to run both Telegram bot and HTTP server"""
    logger.info("🤖 Starting YouTube Summarizer Bot with Modern Dashboard")
    
    # Start HTTP server in a separate thread
    httpd, port = start_http_server()
    
    if httpd:
        logger.info(f"🌐 Dashboard server running at: http://localhost:{port}")
    else:
        logger.error("❌ Failed to start HTTP server")
        return
    
    # Initialize and start Telegram bot
    telegram_token = os.getenv('TELEGRAM_BOT_TOKEN')
    allowed_users_env = os.getenv('TELEGRAM_ALLOWED_USERS', '')
    
    if not telegram_token:
        logger.warning("⚠️  TELEGRAM_BOT_TOKEN not found. Running dashboard-only mode.")
        logger.info(f"✅ Dashboard-only mode ready at: http://localhost:{port}")
        
        try:
            # Keep dashboard server running
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("🛑 Shutting down dashboard...")
            if httpd:
                httpd.shutdown()
        return
    
    # Parse allowed users
    allowed_user_ids = []
    if allowed_users_env:
        try:
            allowed_user_ids = [int(user_id.strip()) for user_id in allowed_users_env.split(',') if user_id.strip()]
        except ValueError as e:
            logger.warning(f"Error parsing TELEGRAM_ALLOWED_USERS: {e}")
    
    if not allowed_user_ids:
        logger.warning("⚠️  No allowed users configured. Set TELEGRAM_ALLOWED_USERS environment variable.")
        logger.info(f"✅ Dashboard-only mode ready at: http://localhost:{port}")
        
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("🛑 Shutting down dashboard...")
            if httpd:
                httpd.shutdown()
        return
    
    logger.info(f"👥 Telegram bot authorized for {len(allowed_user_ids)} users")
    
    # Create and start Telegram bot
    try:
        telegram_bot = YouTubeTelegramBot(telegram_token, allowed_user_ids)
        
        logger.info("🚀 Starting Telegram bot...")
        
        # Run both services concurrently
        await asyncio.gather(
            telegram_bot.run(),
            run_dashboard_monitor(httpd)
        )
        
    except Exception as e:
        logger.error(f"Error running Telegram bot: {e}")
        if httpd:
            httpd.shutdown()
        raise

async def run_dashboard_monitor(httpd):
    """Monitor the dashboard server"""
    try:
        while True:
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        logger.info("🛑 Shutting down dashboard monitor...")
        if httpd:
            httpd.shutdown()

# Main execution
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Received shutdown signal")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)