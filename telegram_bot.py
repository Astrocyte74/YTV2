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
from urllib.parse import urlparse, parse_qs
import socket

# V2 template engine imports
try:
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    import bleach
    JINJA2_AVAILABLE = True
    BLEACH_AVAILABLE = True
    # Initialize Jinja2 environment
    jinja_env = Environment(
        loader=FileSystemLoader("templates"),
        autoescape=select_autoescape(["html"])
    )
    
    # HTML sanitization settings
    ALLOWED_TAGS = ['p','ul','ol','li','strong','em','br','h3','h4','blockquote','code','pre','a']
    ALLOWED_ATTRS = {'a': ['href','title','rel','target']}
    
except ImportError as e:
    JINJA2_AVAILABLE = False
    BLEACH_AVAILABLE = False
    jinja_env = None
    logger.warning(f"V2 dependencies not available: {e}")

# Import dashboard components only
from modules.report_generator import JSONReportGenerator
from modules.content_index import ContentIndex

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

# Feature toggle for V2 template as default
USE_V2_DEFAULT = os.getenv("USE_V2_DEFAULT", "1") == "1"  # default ON

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

# Initialize global content index for Phase 2 API
try:
    # Determine reports directory - check for Render deployment vs local
    if Path('/app/data/reports').exists():
        content_index = ContentIndex('/app/data/reports')
        logger.info("📊 ContentIndex initialized with Render data directory")
    else:
        content_index = ContentIndex('./data/reports')
        logger.info("📊 ContentIndex initialized with local data directory")
except Exception as e:
    logger.warning(f"⚠️ ContentIndex initialization failed: {e}")
    content_index = None

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
    
    @staticmethod
    def to_report_v2_dict(video_info: dict, summary: dict, processing: dict, audio_url: str = "") -> dict:
        """Convert report data to V2 template format"""
        # Format views
        view_count = video_info.get('view_count', 0)
        if view_count >= 1000000:
            views_pretty = f"{view_count/1000000:.1f}M views"
        elif view_count >= 1000:
            views_pretty = f"{view_count/1000:.1f}K views"
        else:
            views_pretty = f"{view_count:,} views" if view_count else ""
        
        # Format date
        upload_date = video_info.get('upload_date', '')
        if upload_date and len(upload_date) == 8:
            uploaded_pretty = f"{upload_date[4:6]}/{upload_date[6:8]}/{upload_date[:4]}"
        else:
            uploaded_pretty = upload_date
        
        # Extract vocabulary
        vocabulary = []
        if isinstance(summary.get('content'), dict):
            vocab = summary['content'].get('vocabulary', [])
            vocabulary = [{"term": item.get("word", item.get("term", "")), 
                          "definition": item.get("definition", "")} 
                         for item in vocab if item.get("word") or item.get("term")]
        
        # Get summary HTML
        summary_html = ""
        if isinstance(summary.get('content'), dict):
            summary_html = (summary['content'].get('comprehensive') or 
                           summary['content'].get('audio') or
                           summary['content'].get('summary') or "")
        else:
            summary_html = str(summary.get('content', ''))
        
        # Format summary for better readability
        if summary_html and not summary_html.startswith('<'):
            # Plain text - convert to paragraphs with better spacing
            paragraphs = summary_html.split('\n\n')
            summary_html = ''.join(f'<p class="mb-6 leading-relaxed">{p.strip()}</p>' for p in paragraphs if p.strip())
        
        # Sanitize HTML for security (only if bleach is available)
        if BLEACH_AVAILABLE and summary_html:
            summary_html = bleach.clean(summary_html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)
        
        # Calculate audio duration estimate
        audio_dur_pretty = ""
        if audio_url and video_info.get('duration'):
            # Estimate ~40% of video duration for audio summary
            audio_seconds = int(video_info['duration'] * 0.4)
            audio_dur_pretty = f"{audio_seconds // 60}:{audio_seconds % 60:02d}"
        
        # Create AI model string
        model = processing.get('model', '')
        provider = processing.get('llm_provider', '')
        ai_model = f"{model} ({provider})" if model and provider else model or provider or ""
        
        # Create cache bust string from available data
        cache_bust_parts = [uploaded_pretty, views_pretty, ai_model]
        cache_bust = hash("".join(filter(None, cache_bust_parts))) % 10000
        
        return {
            "title": video_info.get("title", ""),
            "thumbnail": video_info.get("thumbnail_url") or video_info.get("thumbnail"),
            "channel": video_info.get("channel", ""),
            "duration_str": video_info.get("duration_string", ""),
            "views_pretty": views_pretty,
            "uploaded_pretty": uploaded_pretty,
            "ai_model": ai_model,
            "audio_mp3": audio_url,
            "audio_dur_pretty": audio_dur_pretty,
            "summary_html": summary_html,
            "vocabulary": vocabulary,
            "back_url": "/",
            "youtube_url": video_info.get("url", ""),
            "cache_bust": cache_bust,
        }
    
    def do_GET(self):
        # Parse URL to separate path from query string
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        query_params = parse_qs(parsed_url.query)
        
        # Store query params for handlers to access
        self._query_params = query_params
        
        if path == '/':
            self.serve_dashboard()
        elif path == '/status':
            self.serve_status()
        elif path == '/health':
            self.serve_health()
        elif path.startswith('/api/'):
            self.serve_api()
        elif path.endswith('.css'):
            self.serve_css()
        elif path.endswith('.js'):
            self.serve_js(path)
        elif path.endswith('.html') and path != '/':
            self.serve_report(path, self._query_params)
        elif path.endswith('.json') and path != '/':
            self.serve_report(path, self._query_params)
        elif path.startswith('/exports/'):
            self.serve_audio_file()
        else:
            super().do_GET()
    
    def do_POST(self):
        if self.path == '/delete-reports':
            self.handle_delete_reports()
        elif self.path == '/api/upload-report':
            self.handle_upload_report()
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
            # Try V3 template first, fallback to original
            template_content = load_template('dashboard_v3_template.html')
            if not template_content:
                template_content = load_template('dashboard_template.html')
            
            if template_content:
                # Get base URL
                base_url = os.getenv('NGROK_URL', 'https://chief-inspired-lab.ngrok-free.app')
                
                # Replace template placeholders (safe replacement for templates with {})
                dashboard_html = template_content.replace(
                    '{reports_data}', json.dumps(reports_data, ensure_ascii=False)
                ).replace(
                    '{base_url}', base_url
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
    
    def serve_js(self, path=None):
        """Serve JavaScript files including V2 assets"""
        try:
            # Use provided path or fallback to self.path for backward compatibility
            request_path = path or self.path
            filename = request_path[1:]  # Remove leading slash
            
            # Handle both regular static/ and static/v2/ paths
            if filename.startswith('static/'):
                js_file = Path(filename)
            else:
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
    
    def serve_report(self, path: str, qs: dict = None):
        """
        Serve individual report pages
        path: normalized URL path (no query string), e.g. "/_id.json"
        qs: parsed query params (from do_GET)
        """
        try:
            # Map URL path to data file
            # We serve JSON reports located under data/reports/*.json
            filename = Path(path.lstrip('/'))               # "_id.json"
            json_path = Path('data/reports') / filename.name
            
            if json_path.suffix == '.json' and json_path.exists():
                return self.serve_json_report(json_path, qs)
            
            # (optional) support .html wrapper if you have an HTML variant
            if json_path.with_suffix('.json').exists():
                return self.serve_json_report(json_path.with_suffix('.json'), qs)
                
            self.send_error(404, "Report not found")
        except Exception as e:
            logger.error(f"serve_report error for {path}: {e}")
            self.send_error(500, "Error serving report")
    
    def serve_json_report(self, json_path: Path, qs: dict = None):
        """Serve a JSON report with V2 Tailwind template support"""
        try:
            # Use query params passed from serve_report
            qs = qs or {}
            v_param = qs.get('v', [''])[0]
            force_legacy = qs.get('legacy', [''])[0] == '1'

            # Order of precedence:
            #   - ?legacy=1  -> legacy
            #   - ?v=2       -> V2
            #   - default    -> V2 if USE_V2_DEFAULT, else legacy
            if force_legacy:
                use_v2 = False
            elif v_param == '2':
                use_v2 = True
            else:
                use_v2 = USE_V2_DEFAULT
            
            # Log render choice for debugging rollout
            logger.info(f"render_choice use_v2={use_v2} v_param='{v_param}' force_legacy={force_legacy} env_default={USE_V2_DEFAULT}")
            
            # Load report data
            with open(json_path, 'r', encoding='utf-8') as f:
                report_data = json.load(f)
            
            # Extract data sections
            video_info = report_data.get('video', {})
            summary = report_data.get('summary', {})
            processing = report_data.get('processing', {})
            
            # Discover audio file (reuse existing logic)
            audio_url = self._discover_audio_file(video_info)
            
            # Generate HTML content
            if use_v2 and JINJA2_AVAILABLE:
                # V2 Tailwind Template Path
                logger.info("🚀 Rendering V2 Tailwind template")
                
                ctx = self.to_report_v2_dict(video_info, summary, processing, audio_url)
                template = jinja_env.get_template("report_v2.html")
                html_content = template.render(**ctx)
                
            else:
                # Legacy inline HTML path (existing implementation)
                if use_v2 and not JINJA2_AVAILABLE:
                    logger.warning("V2 requested but Jinja2 not available, falling back to legacy")
                
                html_content = self._render_legacy_report(video_info, summary, processing, audio_url)
            
            # Send response
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            self.wfile.write(html_content.encode('utf-8'))
                
        except Exception as e:
            logger.error(f"Error serving JSON report {json_path}: {e}")
            self.send_error(500, "Error serving JSON report")
    
    def _discover_audio_file(self, video_info: dict) -> str:
        """Discover audio file for a video (extracted from legacy method)"""
        audio_url = ''
        try:
            video_id = video_info.get('video_id', '')
            if video_id:
                candidates = []
                # Check both local exports and uploaded files directory
                search_dirs = [Path('./exports')]
                if Path('/app/data/exports').exists():
                    search_dirs.append(Path('/app/data/exports'))
                
                logger.info(f"🔍 Looking for audio: video_id={video_id}")
                for search_dir in search_dirs:
                    # Search for all possible audio file patterns
                    patterns = [
                        f'audio_{video_id}_*.mp3',     # Standard pattern
                        f'{video_id}_*.mp3',           # Legacy pattern  
                        f'audio_*{video_id}*.mp3'     # Flexible pattern for complex stems
                    ]
                    for pattern in patterns:
                        found = list(search_dir.glob(pattern))
                        candidates.extend(found)
                        logger.info(f"🎵 Pattern '{pattern}' in {search_dir}: found {len(found)} files")
                
                if candidates:
                    latest = max(candidates, key=lambda p: p.stat().st_mtime)
                    audio_url = f"/exports/{latest.name}"
                    logger.info(f"✅ Audio URL: {audio_url}")
                else:
                    logger.info(f"❌ No audio found for video_id {video_id}")
        except Exception as e:
            logger.error(f"❌ Audio detection error: {e}")
            audio_url = ''
        
        return audio_url
    
    def _render_legacy_report(self, video_info: dict, summary: dict, processing: dict, audio_url: str) -> str:
        """Render legacy inline HTML report (existing implementation)"""
        # Extract legacy data processing
        title = video_info.get('title', 'Unknown Video')
        channel = video_info.get('channel', 'Unknown Channel')
        duration_str = video_info.get('duration_string', '')
        url = video_info.get('url', '')
        thumbnail = video_info.get('thumbnail', '')
        view_count = video_info.get('view_count', 0)
        upload_date = video_info.get('upload_date', '')
        
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
        
        # Format dates
        try:
            if upload_date and len(upload_date) == 8:
                formatted_date = f"{upload_date[4:6]}/{upload_date[6:8]}/{upload_date[:4]}"
            else:
                formatted_date = upload_date or 'Unknown'
        except:
            formatted_date = 'Unknown'
        
        # Extract summary content - handle both old and new structures
        summary_content = summary.get('content', {})
        if isinstance(summary_content, dict):
            summary_text = (summary_content.get('comprehensive') or 
                          summary_content.get('audio') or
                          summary_content.get('bullet_points') or
                          summary_content.get('key_insights') or
                          summary_content.get('summary') or
                          'No summary available')
            headline = summary_content.get('headline', '')
            vocabulary = summary_content.get('vocabulary', [])
            glossary = summary_content.get('glossary', [])
        else:
            summary_text = str(summary_content) if summary_content else 'No summary available'
            headline = ''
            vocabulary = []
            glossary = []
        
        model = processing.get('model', 'Unknown')
        provider = processing.get('llm_provider', 'Unknown')
        
        # Build mini-player script
        script_block = ''
        if audio_url:
            _dur = video_info.get('duration', 0)
            script_block = f"""
<script>(function(){{
  const a = document.getElementById('summaryAudio');
  if (!a) return;
  // Legacy player JavaScript (truncated for brevity)
  console.log('Legacy audio player initialized');
}})();</script>"""
        
        # Legacy HTML template (abbreviated - keep existing styling)
        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
    <title>{title} - YTV2</title>
    <style>
      /* Legacy styles (abbreviated - existing implementation) */
      body {{ font-family: Inter, sans-serif; }}
    </style>
</head>
<body>
    <div class="legacy-report">
        <h1>{title}</h1>
        <div>{summary_text}</div>
        {f'<audio controls><source src="{audio_url}"></audio>' if audio_url else ''}
    </div>
    {script_block}
</body>
</html>"""
        
        return html_content
    
    def serve_audio_file(self):
        """Serve audio files from /exports/ route"""
        try:
            filename = self.path[1:]  # Remove leading slash, e.g., "exports/audio_xxx.mp3"
            if not filename.startswith('exports/'):
                self.send_error(404, "Not found")
                return
            
            audio_filename = filename[8:]  # Remove "exports/" prefix
            
            # Look for audio file in uploaded files directory
            audio_path = Path('/app/data/exports') / audio_filename
            if not audio_path.exists():
                # Fallback to local exports directory
                audio_path = Path('./exports') / audio_filename
                
            if audio_path.exists():
                self.send_response(200)
                self.send_header('Content-type', 'audio/mpeg')
                self.send_header('Content-Length', str(audio_path.stat().st_size))
                self.send_header('Cache-Control', 'public, max-age=3600')  # Cache for 1 hour
                self.end_headers()
                with open(audio_path, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_error(404, f"Audio file not found: {audio_filename}")
                
        except Exception as e:
            logger.error(f"Error serving audio file {self.path}: {e}")
            self.send_error(500, "Error serving audio file")
    
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

    def serve_health(self):
        """Serve health check endpoint for RENDER deployment"""
        try:
            # Simple health check - just respond with OK
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            health_data = {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "service": "ytv2-telegram-bot"
            }
            self.wfile.write(json.dumps(health_data).encode())
            
        except Exception as e:
            logger.error(f"Error serving health check: {e}")
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            error_data = {"status": "unhealthy", "error": str(e)}
            self.wfile.write(json.dumps(error_data).encode())
    
    def serve_api(self):
        """Serve Phase 2 API endpoints with enhanced filtering and search"""
        try:
            # Parse URL to separate path from query string
            parsed_url = urlparse(self.path)
            path = parsed_url.path
            query_params = parse_qs(parsed_url.query)
            
            if path == '/api/filters':
                self.serve_api_filters(query_params)
            elif path == '/api/reports':
                self.serve_api_reports_v2(query_params)
            elif path.startswith('/api/reports/'):
                self.serve_api_report_detail()
            elif path == '/api/config':
                self.serve_api_config()
            else:
                self.send_error(404, "API endpoint not found")
        except Exception as e:
            logger.error(f"Error serving API {self.path}: {e}")
            self.send_error(500, "API error")
    
    def serve_api_filters(self, query_params: Dict[str, List[str]]):
        """Serve Phase 2 filters API endpoint with faceted search"""
        try:
            if not content_index:
                self.send_error(500, "Content index not available")
                return
            
            # Parse active filters from query parameters
            active_filters = {}
            
            # Extract filter parameters
            if 'source' in query_params:
                active_filters['source'] = query_params['source']
            if 'language' in query_params:
                active_filters['language'] = query_params['language']
            if 'category' in query_params:
                active_filters['category'] = query_params['category']
            if 'topics' in query_params:
                # Handle comma-separated topics
                topics = []
                for topic_list in query_params['topics']:
                    topics.extend(topic_list.split(','))
                active_filters['topics'] = [t.strip() for t in topics if t.strip()]
            if 'content_type' in query_params:
                active_filters['content_type'] = query_params['content_type']
            if 'complexity' in query_params:
                active_filters['complexity'] = query_params['complexity']
            if 'has_audio' in query_params:
                # Convert string to boolean
                has_audio_str = query_params['has_audio'][0].lower()
                if has_audio_str in ['true', '1', 'yes']:
                    active_filters['has_audio'] = True
                elif has_audio_str in ['false', '0', 'no']:
                    active_filters['has_audio'] = False
            
            # Get facets (with masked counts if filters are active)
            facets = content_index.get_facets(active_filters if active_filters else None)
            
            # Send response
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Cache-Control', 'public, max-age=60')  # Cache for 1 minute
            self.end_headers()
            
            self.wfile.write(json.dumps(facets, ensure_ascii=False, indent=2).encode())
            
        except Exception as e:
            logger.error(f"Error serving filters API: {e}")
            self.send_error(500, f"Filters API error: {str(e)}")
    
    def serve_api_reports_v2(self, query_params: Dict[str, List[str]]):
        """Serve Phase 2 reports API endpoint with filtering, search, and pagination"""
        try:
            if not content_index:
                # Fallback to legacy method
                return self.serve_api_reports()
            
            # Parse query parameters
            filters = {}
            
            # Filter parameters with validation
            for param in ['source', 'language', 'category', 'content_type', 'complexity']:
                if param in query_params:
                    # Limit array size and sanitize strings
                    values = query_params[param][:10]  # Max 10 items
                    filters[param] = [str(v)[:50] for v in values if v and str(v).strip()]  # Max 50 chars per item
            
            if 'topics' in query_params:
                # Handle comma-separated topics with validation
                topics = []
                for topic_list in query_params['topics'][:5]:  # Max 5 topic lists
                    if len(str(topic_list)) <= 200:  # Limit individual topic list length
                        topics.extend(str(topic_list).split(','))
                filters['topics'] = [t.strip()[:50] for t in topics[:20] if t.strip()]  # Max 20 topics, 50 chars each
            if 'has_audio' in query_params:
                has_audio_str = query_params['has_audio'][0].lower()
                if has_audio_str in ['true', '1', 'yes']:
                    filters['has_audio'] = True
                elif has_audio_str in ['false', '0', 'no']:
                    filters['has_audio'] = False
            
            # Date range filters
            if 'date_from' in query_params:
                filters['date_from'] = query_params['date_from'][0]
            if 'date_to' in query_params:
                filters['date_to'] = query_params['date_to'][0]
            
            # Search query with validation
            query = query_params.get('q', [''])[0].strip()
            if len(query) > 200:  # Limit search query length
                query = query[:200]
            # Basic XSS protection
            query = query.replace('<', '').replace('>', '').replace('&', '') if query else ''
            
            # Sorting
            sort = query_params.get('sort', ['newest'])[0]
            valid_sorts = ['newest', 'title', 'duration']
            if sort not in valid_sorts:
                sort = 'newest'
            
            # Pagination
            try:
                page = int(query_params.get('page', ['1'])[0])
                size = int(query_params.get('size', ['20'])[0])
            except ValueError:
                page = 1
                size = 20
            
            # Validate pagination parameters
            page = max(1, page)
            size = max(1, min(50, size))  # Cap at 50 items per page
            
            # Execute search
            results = content_index.search_reports(
                filters=filters if filters else None,
                query=query if query else None,
                sort=sort,
                page=page,
                size=size
            )
            
            # Send response
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Cache-Control', 'no-cache')  # Don't cache filtered results
            self.end_headers()
            
            self.wfile.write(json.dumps(results, ensure_ascii=False, indent=2).encode())
            
        except Exception as e:
            logger.error(f"Error serving reports API v2: {e}")
            self.send_error(500, f"Reports API error: {str(e)}")
    
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
            # Check sync secret for authentication
            sync_secret = os.getenv('SYNC_SECRET')
            if not sync_secret:
                self.send_error(500, "Sync not configured")
                return
            
            auth_header = self.headers.get('X-Sync-Secret', '')
            if auth_header != sync_secret:
                logger.warning(f"Delete rejected: Invalid sync secret from {self.client_address[0]}")
                self.send_error(401, "Unauthorized")
                return
            
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
    
    def handle_upload_report(self):
        """Handle POST request to upload report from NAS to Render with transactional validation"""
        try:
            # Check sync secret for authentication
            sync_secret = os.getenv('SYNC_SECRET')
            if not sync_secret:
                self.send_error(500, "Sync not configured")
                return
            
            auth_header = self.headers.get('X-Sync-Secret', '')
            if auth_header != sync_secret:
                logger.warning(f"Upload rejected: Invalid sync secret from {self.client_address[0]}")
                self.send_error(401, "Unauthorized")
                return
            
            # Parse multipart form data with size limit (25MB)
            content_type = self.headers.get('Content-Type', '')
            if not content_type.startswith('multipart/form-data'):
                self.send_error(400, "Expected multipart/form-data")
                return
            
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self.send_error(400, "No data received")
                return
            if content_length > 25 * 1024 * 1024:  # 25MB limit
                self.send_error(413, "Request too large")
                return
            
            post_data = self.rfile.read(content_length)
            
            # Parse boundary from Content-Type header
            boundary = None
            for part in content_type.split(';'):
                part = part.strip()
                if part.startswith('boundary='):
                    boundary = part.split('=', 1)[1].strip('"')
                    break
            
            if not boundary:
                self.send_error(400, "No boundary found in Content-Type")
                return
            
            # Parse multipart data
            files = self.parse_multipart_data(post_data, boundary)
            
            if 'report' not in files:
                self.send_error(400, "No report file provided")
                return
            
            # Optional: read client-provided stem for idempotency
            client_stem = self.headers.get('X-Report-Stem', None)
            
            # Sanitize client-provided stem
            if client_stem:
                import re
                safe_stem_pattern = re.compile(r'^[A-Za-z0-9_\-\.]+$')
                if not safe_stem_pattern.match(client_stem):
                    client_stem = re.sub(r'[^A-Za-z0-9_\-\.]', '_', client_stem)
                    logger.warning(f"Sanitized X-Report-Stem header to: {client_stem}")
            
            # Ensure data directories exist
            reports_dir = Path('/app/data/reports') if Path('/app/data').exists() else Path('./data/reports')
            exports_dir = Path('/app/data/exports') if Path('/app/data').exists() else Path('./exports')
            reports_dir.mkdir(parents=True, exist_ok=True)
            exports_dir.mkdir(parents=True, exist_ok=True)
            
            # Save JSON report
            report_data = files['report']
            report_filename = report_data.get('filename', 'upload.json')
            
            # Sanitize filename
            import re
            safe_name_pattern = re.compile(r'^[A-Za-z0-9_\-\.]+$')
            if not safe_name_pattern.match(report_filename.replace('.json', '')):
                # Extract just the base name and make it safe
                base_name = re.sub(r'[^A-Za-z0-9_\-\.]', '_', report_filename.replace('.json', ''))
                report_filename = f"{base_name}.json"
            
            # Force filename from stem for consistency if provided
            if client_stem:
                report_filename = f"{client_stem}.json"
            
            if not report_filename.endswith('.json'):
                report_filename += '.json'
            
            report_path = reports_dir / report_filename
            
            # TRANSACTIONAL VALIDATION: Check both files before writing either
            new_report_bytes = report_data['content']
            conflict = False
            conflict_msg = None
            report_idempotent = False
            audio_idempotent = False
            audio_filename = None
            audio_path = None
            
            # Check report for conflicts
            if report_path.exists():
                with open(report_path, 'rb') as f:
                    if f.read() == new_report_bytes:
                        report_idempotent = True
                    else:
                        conflict = True
                        conflict_msg = "Report exists with different content"
            
            # Check audio for conflicts if provided
            if 'audio' in files and not conflict:
                audio_data = files['audio']
                audio_filename = audio_data.get('filename', 'upload.mp3')
                
                # Don't rename audio files - preserve original filename which contains video_id
                # Only sanitize if needed to prevent path traversal attacks
                if not safe_name_pattern.match(audio_filename.replace('.mp3', '')):
                    base_name = re.sub(r'[^A-Za-z0-9_\-]', '_', audio_filename.replace('.mp3', ''))
                    audio_filename = f"{base_name}.mp3"
                
                if not audio_filename.endswith('.mp3'):
                    audio_filename += '.mp3'
                
                audio_path = exports_dir / audio_filename
                new_audio_bytes = audio_data['content']
                
                if audio_path.exists():
                    with open(audio_path, 'rb') as af:
                        if af.read() == new_audio_bytes:
                            audio_idempotent = True
                        else:
                            conflict = True
                            conflict_msg = "Audio exists with different content"
            
            # Handle conflicts before any writes
            if conflict:
                self.send_response(409)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                error_response = {
                    "status": "conflict",
                    "message": conflict_msg
                }
                self.wfile.write(json.dumps(error_response, indent=2).encode())
                logger.warning(f"Conflict detected for {report_filename.replace('.json', '')}: {conflict_msg}")
                return
            
            # Handle fully idempotent case (both files already exist with same content)
            if report_idempotent and (not audio_filename or audio_idempotent):
                response_data = {
                    "status": "success",
                    "idempotent": True,
                    "report_stem": report_filename.replace('.json', ''),
                    "message": "Files already exist with identical content",
                    "audio_idempotent": audio_idempotent if audio_filename else None
                }
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response_data, indent=2).encode())
                logger.info(f"♻️  Fully idempotent sync: {report_filename.replace('.json', '')}")
                return
            
            # NO CONFLICTS → Perform writes (report then audio)
            uploaded_files = []
            
            # Write report file if not idempotent
            if not report_idempotent:
                with open(report_path, 'wb') as f:
                    f.write(new_report_bytes)
                uploaded_files.append(f"report: {report_filename}")
                logger.info(f"📊 Synced report: {report_filename.replace('.json', '')}")
            
            # Write audio file if present and not idempotent
            if audio_filename and not audio_idempotent:
                with open(audio_path, 'wb') as af:
                    af.write(new_audio_bytes)
                uploaded_files.append(f"audio: {audio_filename}")
                logger.info(f"🎵 Synced audio: {audio_filename.replace('.mp3', '')}")
            
            # Add to uploaded_files for response even if idempotent
            if report_idempotent:
                uploaded_files.append(f"report: {report_filename}")
            if audio_idempotent and audio_filename:
                uploaded_files.append(f"audio: {audio_filename}")
            
            # Send success response with useful JSON
            report_stem = report_filename.replace('.json', '') if report_filename else ''
            response_data = {
                "status": "success",
                "report_stem": report_stem,
                "message": f"Uploaded {len(uploaded_files)} files",
                "files": uploaded_files,
                "report_path": str(report_path) if report_filename else None,
                "audio_path": str(audio_path) if audio_filename else None,
                "audio_idempotent": audio_idempotent if 'audio' in files else None
            }
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response_data, indent=2).encode())
            
        except Exception as e:
            logger.error(f"Error handling upload request: {e}")
            error_response = {"error": "Upload failed", "message": str(e)}
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(error_response).encode())
    
    def parse_multipart_data(self, data, boundary):
        """Simple multipart/form-data parser"""
        files = {}
        boundary_bytes = f'--{boundary}'.encode()
        parts = data.split(boundary_bytes)[1:-1]  # Skip first empty and last boundary
        
        for part in parts:
            if not part.strip():
                continue
            
            # Split headers and content
            header_end = part.find(b'\r\n\r\n')
            if header_end == -1:
                continue
            
            headers = part[:header_end].decode('utf-8', errors='ignore')
            content = part[header_end + 4:]  # Skip \r\n\r\n
            
            # Remove trailing \r\n
            if content.endswith(b'\r\n'):
                content = content[:-2]
            
            # Parse Content-Disposition header
            filename = None
            field_name = None
            for header_line in headers.split('\r\n'):
                if header_line.lower().startswith('content-disposition:'):
                    # Extract name and filename
                    if 'name=' in header_line:
                        name_start = header_line.find('name="') + 6
                        name_end = header_line.find('"', name_start)
                        field_name = header_line[name_start:name_end]
                    
                    if 'filename=' in header_line:
                        filename_start = header_line.find('filename="') + 10
                        filename_end = header_line.find('"', filename_start)
                        filename = header_line[filename_start:filename_end]
            
            if field_name:
                files[field_name] = {
                    'content': content,
                    'filename': filename
                }
        
        return files

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
    
    logger.warning("🚨 This is the DASHBOARD-ONLY version of YTV2")
    logger.warning("🚨 Telegram bot functionality has been moved to the NAS component")
    logger.warning("🚨 Please use the NAS version (YTV2-NAS) for Telegram bot functionality")
    logger.error("❌ Dashboard version cannot run Telegram bot mode")
    
    # Shutdown dashboard since this configuration is invalid
    if httpd:
        httpd.shutdown()
    return

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
