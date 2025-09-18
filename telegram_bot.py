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
import sqlite3

# PostgreSQL support for migration
try:
    import psycopg2
    import psycopg2.extras
    from psycopg2 import pool
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    psycopg2 = None

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
    ALLOWED_TAGS = ['p','ul','ol','li','strong','em','br','h3','h4','blockquote','code','pre','a','div']
    ALLOWED_ATTRS = {
        'a': ['href','title','rel','target'],
        'div': ['class'],
        'ul': ['class'],
        'li': ['class']
    }
    
except ImportError as e:
    JINJA2_AVAILABLE = False
    BLEACH_AVAILABLE = False
    jinja_env = None
    logger.warning(f"V2 dependencies not available: {e}")

# Import dashboard components only
from modules.report_generator import JSONReportGenerator

# Check environment to determine database backend
READ_FROM_POSTGRES = os.getenv('READ_FROM_POSTGRES', 'false').lower() == 'true'

print(f"🔍 DB mode: READ_FROM_POSTGRES={READ_FROM_POSTGRES}, PSYCOPG2_AVAILABLE={PSYCOPG2_AVAILABLE}")
print(f"🔍 DATABASE_URL_POSTGRES_NEW set? {bool(os.getenv('DATABASE_URL_POSTGRES_NEW'))}")

# Startup sanity log for debugging after compaction (using print since logger not yet initialized)
print(
    f"🔍 Startup: READ_FROM_POSTGRES={READ_FROM_POSTGRES}, "
    f"PSYCOPG2_AVAILABLE={PSYCOPG2_AVAILABLE}, "
    f"DATABASE_URL_POSTGRES_NEW set? {bool(os.getenv('DATABASE_URL_POSTGRES_NEW'))}"
)

if READ_FROM_POSTGRES and PSYCOPG2_AVAILABLE:
    # Use PostgreSQL backend
    try:
        from modules.postgres_content_index import PostgreSQLContentIndex as ContentIndex
        USING_SQLITE = False
        print("✅ Using PostgreSQL content index")
    except Exception as e:
        print(f"❌ Failed to initialize PostgreSQL content index; falling back to SQLite: {e}")
        import traceback
        traceback.print_exc()
        from modules.sqlite_content_index import SQLiteContentIndex as ContentIndex
        USING_SQLITE = True
else:
    # Fallback to SQLite backend
    try:
        from modules.sqlite_content_index import SQLiteContentIndex as ContentIndex
        USING_SQLITE = True
        print("Using SQLite content index")
    except ImportError:
        from modules.content_index import ContentIndex
        USING_SQLITE = False
        print("Using legacy JSON content index")

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

def get_postgres_connection():
    """Get a PostgreSQL connection for health checks and database operations."""
    if not PSYCOPG2_AVAILABLE:
        raise ImportError("psycopg2 not available - PostgreSQL support disabled")

    database_url = os.getenv('DATABASE_URL_POSTGRES_NEW') or os.getenv('DATABASE_URL')
    if not database_url:
        raise ValueError("No PostgreSQL DATABASE_URL configured")

    try:
        conn = psycopg2.connect(
            database_url,
            connect_timeout=5,
            cursor_factory=psycopg2.extras.RealDictCursor
        )
        return conn
    except Exception as e:
        logger.error(f"PostgreSQL connection failed: {e}")
        raise

def test_postgres_health():
    """Test PostgreSQL connection health."""
    try:
        with get_postgres_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                result = cur.fetchone()
                return result is not None
    except Exception as e:
        logger.error(f"PostgreSQL health check failed: {e}")
        return False

def create_empty_ytv2_database(db_path: Path):
    """Create empty YTV2 database with proper schema."""
    logger.info(f"🗄️ Creating database schema at: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create content table with universal schema
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS content (
            id TEXT PRIMARY KEY,
            title TEXT,
            canonical_url TEXT,
            thumbnail_url TEXT,
            published_at TEXT,
            indexed_at TEXT,
            duration_seconds INTEGER DEFAULT 0,
            word_count INTEGER DEFAULT 0,
            has_audio BOOLEAN DEFAULT 0,
            audio_duration_seconds INTEGER DEFAULT 0,
            has_transcript BOOLEAN DEFAULT 0,
            transcript_chars INTEGER DEFAULT 0,
            video_id TEXT,
            channel_name TEXT,
            channel_id TEXT,
            view_count INTEGER DEFAULT 0,
            like_count INTEGER DEFAULT 0,
            comment_count INTEGER DEFAULT 0,
            category TEXT,
            content_type TEXT,
            complexity_level TEXT,
            language TEXT DEFAULT 'en',
            key_topics TEXT,
            named_entities TEXT,
            format_source TEXT DEFAULT 'api',
            processing_status TEXT DEFAULT 'completed',
            created_at TEXT,
            updated_at TEXT
        )
    ''')
    
    # Create summaries table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS content_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content_id TEXT UNIQUE,
            summary_text TEXT,
            summary_type TEXT DEFAULT 'comprehensive',
            created_at TEXT,
            FOREIGN KEY (content_id) REFERENCES content (id)
        )
    ''')
    
    # Add subcategory column if it doesn't exist (migration for hierarchical categories)
    try:
        cursor.execute('ALTER TABLE content ADD COLUMN subcategory TEXT')
        logger.info("✅ Added subcategory column to content table")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            logger.info("ℹ️ Subcategory column already exists")
        else:
            logger.warning(f"Could not add subcategory column: {e}")
    
    # Create indexes for performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_content_video_id ON content (video_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_content_indexed_at ON content (indexed_at)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_summaries_content_id ON content_summaries (content_id)')
    
    conn.commit()
    conn.close()
    logger.info(f"✅ Empty database created with YTV2 schema")

# Initialize global content index for Phase 2 API
logger.info(f"🔍 Backend available: SQLite={USING_SQLITE}")

try:
    if USING_SQLITE:
        # Check multiple possible database locations on Render
        # Prioritize persistent disk if it exists
        db_paths = [
            Path('/app/data/ytv2_content.db'), # Render persistent disk mount
            Path('./data/ytv2_content.db'),    # Local data subdirectory
            Path('/app/ytv2_content.db'),      # Root app directory
            Path('./ytv2_content.db')          # Current directory (fallback)
        ]
        
        database_found = False
        for db_path in db_paths:
            if db_path.exists():
                content_index = ContentIndex(str(db_path))
                logger.info(f"✅ SQLiteContentIndex initialized with database: {db_path}")
                database_found = True
                break
        
        if not database_found:
            logger.warning(f"⚠️ No SQLite database found in paths: {[str(p) for p in db_paths]}")
            # Try to create empty database with proper schema
            logger.info("🗄️ Creating empty database with YTV2 schema...")
            try:
                # Use the first path that exists or can be created
                target_path = None
                for db_path in db_paths:
                    try:
                        db_path.parent.mkdir(parents=True, exist_ok=True)
                        target_path = db_path
                        break
                    except:
                        continue
                
                if target_path:
                    create_empty_ytv2_database(target_path)
                    content_index = ContentIndex(str(target_path))
                    logger.info(f"✅ Created and initialized empty database: {target_path}")
                    database_found = True
                else:
                    raise Exception("Could not create database in any path")
                    
            except Exception as e:
                logger.error(f"❌ Failed to create database: {e}")
                # Fallback to JSON backend
                USING_SQLITE = False
                logger.info("🔄 Falling back to JSON backend")
    
    if not USING_SQLITE:
        # Check if we're using PostgreSQL or JSON backend
        if READ_FROM_POSTGRES and PSYCOPG2_AVAILABLE:
            # PostgreSQL backend - use named parameter to avoid confusion
            content_index = ContentIndex(postgres_url=os.getenv('DATABASE_URL_POSTGRES_NEW'))
            logger.info("📊 PostgreSQL ContentIndex initialized (singleton)")
        else:
            # JSON-based index as fallback
            if Path('/app/data/reports').exists():
                content_index = ContentIndex('/app/data/reports')
                logger.info("📊 JSON ContentIndex initialized with Render data directory")
            else:
                content_index = ContentIndex('./data/reports')
                logger.info("📊 JSON ContentIndex initialized with local data directory")
            
except Exception as e:
    logger.error(f"❌ ContentIndex initialization failed: {e}")
    content_index = None

# Debug logging for future troubleshooting
if content_index:
    logger.info(
        "🔍 ContentIndex ready: READ_FROM_POSTGRES=%s, index=%s, dsn_set=%s",
        READ_FROM_POSTGRES, type(content_index).__name__,
        bool(os.getenv("DATABASE_URL_POSTGRES_NEW"))
    )

# Log final backend status
if content_index:
    backend_type = "SQLite" if USING_SQLITE else "JSON"
    logger.info(f"🎯 Using {backend_type} backend for content management")

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
    def _maybe_parse_dict_string(value):
        """Parse dict-as-string format from chunked processing (JSON or Python literal)"""
        if isinstance(value, str) and value.strip().startswith("{"):
            import json
            import ast
            try:
                # Try JSON format first: {"comprehensive": "..."}
                return json.loads(value)
            except Exception:
                try:
                    # Fallback to Python literal: {'comprehensive': '...'}
                    return ast.literal_eval(value)
                except Exception:
                    return value
        return value

    @staticmethod
    def normalize_summary_content(summary_content, summary_type: str = None) -> str:
        """Normalize summary content - handle strings, dicts, and nested dict values"""
        # 1) Strings pass through
        if isinstance(summary_content, str):
            return summary_content

        # 2) If we got a dict, pick sensibly (and recurse on dict candidates)
        if isinstance(summary_content, dict):
            stype = (summary_type or '').lower().replace('-', '').replace('_', '').replace(' ', '')

            def as_text(val):
                """Recurse into nested dicts/containers until we get a string (or '')"""
                if isinstance(val, str):
                    return val
                if isinstance(val, dict):
                    # Prefer comprehensive → bullet_points → key_points → summary
                    for k in ('comprehensive', 'bullet_points', 'key_points', 'summary'):
                        if k in val:
                            t = as_text(val[k])
                            if t:
                                return t
                if isinstance(val, (list, tuple)):
                    # Join any strings we can find
                    parts = [as_text(x) for x in val]
                    parts = [p for p in parts if isinstance(p, str) and p.strip()]
                    if parts:
                        return '\n'.join(parts)
                return ''

            # Primary pick order by type
            if stype in ('keypoints', 'bulletpoints'):
                candidates = (
                    summary_content.get('bullet_points'),
                    summary_content.get('key_points'),
                    summary_content.get('comprehensive'),
                    summary_content.get('summary'),
                )
            elif stype == 'comprehensive':
                candidates = (
                    summary_content.get('comprehensive'),
                    summary_content.get('bullet_points'),
                    summary_content.get('key_points'),
                    summary_content.get('summary'),
                )
            elif stype == 'audio':
                candidates = (
                    summary_content.get('summary'),        # may be a dict → recurse
                    summary_content.get('comprehensive'),
                    summary_content.get('bullet_points'),
                    summary_content.get('key_points'),
                )
            else:
                candidates = (
                    summary_content.get('bullet_points'),
                    summary_content.get('key_points'),
                    summary_content.get('comprehensive'),
                    summary_content.get('summary'),
                )

            for c in candidates:
                txt = as_text(c)
                if isinstance(txt, str) and txt.strip():
                    return txt

            # Last-resort: search any nested values
            for v in summary_content.values():
                txt = as_text(v)
                if isinstance(txt, str) and txt.strip():
                    return txt

        # 3) Fallback
        return str(summary_content or '')

    @staticmethod
    def format_key_points(raw_text: str) -> str:
        """Format Key Points with structured markers if present, fallback to normal formatting"""
        import re
        import html
        
        if not raw_text or not isinstance(raw_text, str):
            return '<p class="mb-6 leading-relaxed">No summary available.</p>'
        
        # Normalize line breaks and trim
        text = raw_text.replace('\r\n', '\n').replace('\r', '\n').strip()
        
        # Check for structured markers
        has_main_topic = bool(re.search(r'^(?:•\s*)?\*\*Main topic:\*\*\s*.+$', text, re.MULTILINE | re.IGNORECASE))
        has_key_points = bool(re.search(r'\*\*Key points:\*\*', text, re.IGNORECASE))
        
        # Check for comprehensive summary structure
        has_comprehensive_structure = ModernDashboardHTTPRequestHandler._has_comprehensive_structure(text)
        
        # If we have structured markers, use special formatting
        if has_main_topic or has_key_points:
            return ModernDashboardHTTPRequestHandler._render_structured_key_points(text)
        # If we have comprehensive structure, format it nicely
        elif has_comprehensive_structure:
            return ModernDashboardHTTPRequestHandler._render_comprehensive_content(text)
        
        # Fallback to normal paragraph formatting
        paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
        if not paragraphs:
            return '<p class="mb-6 leading-relaxed">No summary available.</p>'
        
        return ''.join(f'<p class="mb-6 leading-relaxed">{html.escape(p)}</p>' for p in paragraphs)
    
    @staticmethod
    def _render_structured_key_points(text: str) -> str:
        """Render structured Key Points with proper formatting"""
        import re
        import html
        
        parts = []
        
        # 1) Extract main topic
        main_topic_match = re.search(r'^(?:•\s*)?\*\*Main topic:\*\*\s*(.+)$', text, re.MULTILINE | re.IGNORECASE)
        main_topic = main_topic_match.group(1).strip() if main_topic_match else None
        
        # 2) Extract takeaway if present
        takeaway_match = re.search(r'\*\*Takeaway:\*\*\s*(.+?)(?=\*\*|$)', text, re.IGNORECASE | re.DOTALL)
        takeaway = takeaway_match.group(1).strip() if takeaway_match else None
        
        # 3) Find content after "**Key points:**" marker, before takeaway
        key_start_match = re.search(r'\*\*Key points:\*\*', text, re.IGNORECASE)
        bullet_block = ''
        
        if key_start_match:
            # Take everything after the "Key points:" marker
            bullet_text = text[key_start_match.end():].strip()
            # Stop at takeaway marker if present
            if takeaway_match:
                bullet_text = bullet_text[:takeaway_match.start() - key_start_match.end()].strip()
            bullet_block = bullet_text
        elif main_topic_match:
            # No "Key points:" marker, use everything except main topic and takeaway
            bullet_block = text.replace(main_topic_match.group(0), '').strip()
            if takeaway_match:
                bullet_block = bullet_block.replace(takeaway_match.group(0), '').strip()
        else:
            bullet_block = text
            if takeaway_match:
                bullet_block = bullet_block.replace(takeaway_match.group(0), '').strip()
        
        # Strip any leftover takeaway lines from bullet block (belt-and-suspenders)
        bullet_block = re.sub(r'^\s*(?:[•\-–—]\s*)?\*\*takeaway:\*\*.*$', '', bullet_block, 
                             flags=re.IGNORECASE | re.MULTILINE).strip()
        
        # 3) Process bullet points
        lines = [line.strip() for line in bullet_block.split('\n') if line.strip()]
        
        # Precompile takeaway detection regex
        takeaway_bullet_re = re.compile(r'^\s*(?:[•\-–—]\s*)?\*\*takeaway:\*\*', re.IGNORECASE)
        
        bullets = []
        for line in lines:
            # Match lines starting with • - – — (bullet points, including Unicode dashes)
            if re.match(r'^(?:•|-|–|—)\s+', line):
                bullet_content = re.sub(r'^(?:•|-|–|—)\s+', '', line).strip()
                # Skip any bullet that is actually a Takeaway marker
                if not takeaway_bullet_re.match(bullet_content):
                    bullets.append(bullet_content)
        
        # 4) Build HTML
        if main_topic:
            parts.append(f'<div class="kp-heading">{html.escape(main_topic)}</div>')
        
        if bullets:
            bullet_html = ''.join(f'<li>{html.escape(bullet)}</li>' for bullet in bullets)
            parts.append(f'<ul class="kp-list">{bullet_html}</ul>')
        elif bullet_block:
            # No clear bullets found, but we have content - preserve with line breaks
            escaped_content = html.escape(bullet_block).replace('\n', '<br>')
            parts.append(f'<div class="kp-fallback">{escaped_content}</div>')
        
        # Add takeaway as bold concluding statement
        if takeaway:
            parts.append(f'<div class="kp-takeaway"><strong>{html.escape(takeaway)}</strong></div>')
        
        return ''.join(parts) if parts else '<p class="mb-6 leading-relaxed">No summary available.</p>'
    
    @staticmethod
    def _has_comprehensive_structure(text: str) -> bool:
        """Detect comprehensive summary structure (headers + organized content)"""
        import re
        
        # Look for patterns that indicate structured comprehensive summaries
        has_headers = bool(re.search(r'^[A-Z][^.\n]*\s*$', text, re.MULTILINE))  # Lines that look like headers
        has_bullets = bool(re.search(r'^(?:\s*[-•*]\s+)', text, re.MULTILINE))  # Bullet points
        has_structured_sections = bool(re.search(r'^(?:Overview|What\'s New|Key|Main|Summary|Takeaway|Cameras?|Processing|Workflow)[\s:]', text, re.MULTILINE | re.IGNORECASE))
        
        return (has_headers and has_bullets) or has_structured_sections
    
    @staticmethod
    def _render_comprehensive_content(text: str) -> str:
        """Render comprehensive content with proper structure"""
        import re
        import html
        
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        parts = []
        current_bullets = []
        
        for line in lines:
            # Remove "Comprehensive Summary:" prefix if present
            if re.match(r'^Comprehensive Summary:\s*', line, re.IGNORECASE):
                continue
            
            # Check if this is a header
            is_header = (
                (len(line) < 80 and not line.endswith('.') and not line.startswith('-') and not line.startswith('•')) or
                bool(re.match(r'^[A-Z][^.]*:?\s*$', line)) or
                bool(re.match(r'^(?:Overview|What\'s New|Key|Main|Summary|Takeaway|Cameras?|Processing|Workflow)', line, re.IGNORECASE))
            )
            
            is_bullet = bool(re.match(r'^\s*[-•*]\s+', line))
            
            if is_header:
                # Flush any pending bullets
                if current_bullets:
                    bullet_html = ''.join(f'<li>{html.escape(bullet)}</li>' for bullet in current_bullets)
                    parts.append(f'<ul class="kp-list">{bullet_html}</ul>')
                    current_bullets = []
                
                # Add header
                clean_header = re.sub(r':\s*$', '', line)
                parts.append(f'<div class="kp-heading">{html.escape(clean_header)}</div>')
                
            elif is_bullet:
                # Extract bullet content
                bullet_content = re.sub(r'^\s*[-•*]\s+', '', line).strip()
                current_bullets.append(bullet_content)
                
            elif line.strip():
                # Flush any pending bullets
                if current_bullets:
                    bullet_html = ''.join(f'<li>{html.escape(bullet)}</li>' for bullet in current_bullets)
                    parts.append(f'<ul class="kp-list">{bullet_html}</ul>')
                    current_bullets = []
                
                # Add as paragraph
                parts.append(f'<p class="mb-3">{html.escape(line)}</p>')
        
        # Flush any remaining bullets
        if current_bullets:
            bullet_html = ''.join(f'<li>{html.escape(bullet)}</li>' for bullet in current_bullets)
            parts.append(f'<ul class="kp-list">{bullet_html}</ul>')
        
        return ''.join(parts) if parts else '<p class="mb-6 leading-relaxed">No summary available.</p>'
    
    @staticmethod
    def to_report_v2_dict(report_data: dict, audio_url: str = "") -> dict:
        """Convert report data to V2 template format with robust fallbacks"""
        # Enhanced metadata (optional)
        youtube_meta = (report_data.get('source_metadata') or {}).get('youtube', {})
        # Primary video block (YTV2 schema)
        video = report_data.get('video', {}) or {}
        summary = report_data.get('summary', {}) or {}
        processing = report_data.get('processing', {}) or {}
        
        # Enhanced metadata extraction
        video_id = youtube_meta.get('video_id') or video.get('video_id', '')
        title = (report_data.get('title') or video.get('title') or youtube_meta.get('title') or '').strip()
        
        # Channel - prioritize uploader_id over channel_name
        channel = (video.get('channel') or youtube_meta.get('channel_name') or (youtube_meta.get('uploader_id') or '').replace('@','') or '').strip()
        if channel == 'Unknown':
            channel = youtube_meta.get('uploader_id', '').replace('@', '')
        
        # Thumbnail - generate from video_id if not available
        thumbnail = (
            report_data.get('thumbnail_url') or
            report_data.get('thumbnail') or
            video.get('thumbnail') or
            (f"https://img.youtube.com/vi/{video_id}/mqdefault.jpg" if video_id else "")
        )
        
        # Duration - support both video and audio durations from multiple sources
        video_duration_seconds = (
            report_data.get('duration_seconds') or
            report_data.get('duration') or
            video.get('duration') or
            youtube_meta.get('duration') or 0
        )
        
        # Get precise audio duration from media_metadata first, then fallback
        media_metadata = report_data.get('media_metadata', {})
        audio_duration_seconds = (
            media_metadata.get('mp3_duration_seconds') or
            report_data.get('media', {}).get('audio_duration_seconds', 0)
        )
        
        # Format video duration
        if video_duration_seconds:
            hours = video_duration_seconds // 3600
            minutes = (video_duration_seconds % 3600) // 60
            seconds = video_duration_seconds % 60
            if hours:
                video_duration_str = f"{hours}:{minutes:02d}:{seconds:02d}"
            else:
                video_duration_str = f"{minutes}:{seconds:02d}"
        else:
            video_duration_str = ""
        
        # Format audio duration - prioritize precise media_metadata
        if audio_duration_seconds and audio_duration_seconds > 0:
            audio_minutes = audio_duration_seconds // 60
            audio_seconds = audio_duration_seconds % 60
            audio_dur_pretty = f"{audio_minutes}:{audio_seconds:02d}"
        elif video_duration_seconds and video_duration_seconds > 0:
            # Fallback: estimate ~40% of video duration for audio summary
            # This works whether audio_url exists or not
            estimated_audio_seconds = int(video_duration_seconds * 0.4)
            audio_dur_pretty = f"{estimated_audio_seconds // 60}:{estimated_audio_seconds % 60:02d}"
        else:
            audio_dur_pretty = ""
        
        # Format views with enhanced metadata
        view_count = youtube_meta.get('view_count') or report_data.get('view_count') or 0
        if view_count >= 1000000:
            views_pretty = f"{view_count/1000000:.1f}M views"
        elif view_count >= 1000:
            views_pretty = f"{view_count/1000:.1f}K views"
        else:
            views_pretty = f"{view_count:,} views" if view_count else ""
        
        # Format date
        upload_date = video.get('upload_date') or report_data.get('upload_date') or youtube_meta.get('upload_date', '')
        if upload_date and len(upload_date) == 8:
            uploaded_pretty = f"{upload_date[4:6]}/{upload_date[6:8]}/{upload_date[:4]}"
        else:
            uploaded_pretty = upload_date
        
        # Extract engagement metrics
        like_count = youtube_meta.get('like_count', 0)
        like_count_pretty = f"{like_count:,}" if like_count else ""
        
        comment_count = youtube_meta.get('comment_count', 0)
        comment_count_pretty = f"{comment_count:,}" if comment_count else ""
        
        follower_count = youtube_meta.get('channel_follower_count', 0)
        if follower_count >= 1000000:
            follower_count_pretty = f"{follower_count/1000000:.1f}M subscribers"
        elif follower_count >= 1000:
            follower_count_pretty = f"{follower_count/1000:.1f}K subscribers"
        else:
            follower_count_pretty = f"{follower_count:,} subscribers" if follower_count else ""
        
        # Technical specs
        resolution = youtube_meta.get('resolution', '')
        fps = youtube_meta.get('fps', '')
        fps_pretty = f"{fps} fps" if fps else ""
        
        # Categories and key_topics from enhanced metadata - match ContentIndex logic 
        # Prioritize SQLite format first (report_data['analysis']), then summary.analysis (JSON format)
        analysis = report_data.get('analysis', {})
        summary_analysis = report_data.get('summary', {}).get('analysis', {})
        
        # Extract subcategories using same logic as dashboard
        # Rich format: analysis.categories array with subcategories
        rich_cats = analysis.get('categories', [])
        if not rich_cats:
            rich_cats = summary_analysis.get('categories', [])
        
        # If we have structured categories, extract categories from them
        categories = []
        if isinstance(rich_cats, list) and rich_cats:
            categories = [cat_obj.get('category') for cat_obj in rich_cats if isinstance(cat_obj, dict) and cat_obj.get('category')]
        
        # Fallback to legacy categories if no structured ones
        if not categories:
            categories = analysis.get('category') or summary_analysis.get('category', ['General'])
            if isinstance(categories, str):
                categories = [categories]
        
        subcategory_pairs = []
        if isinstance(rich_cats, list):
            for cat_obj in rich_cats:
                if isinstance(cat_obj, dict):
                    parent = cat_obj.get('category')
                    subcats = cat_obj.get('subcategories', [])
                    if parent and subcats:
                        for subcat in subcats:
                            if subcat:
                                subcategory_pairs.append([parent, subcat])
        
        # Legacy fallback: attach subcategory to all categories (only if no structured data)
        if not rich_cats:
            legacy_subcats = analysis.get('subcategory') or summary_analysis.get('subcategory', [])
            if isinstance(legacy_subcats, str):
                legacy_subcats = [legacy_subcats]
            elif not isinstance(legacy_subcats, list):
                legacy_subcats = []
                
            if categories and legacy_subcats:
                for category in categories:
                    for subcategory in legacy_subcats:
                        if subcategory and subcategory not in categories:
                            subcategory_pairs.append([category, subcategory])
            
        # Extract key topics for additional tagging - prioritize SQLite format
        key_topics = analysis.get('key_topics') or summary_analysis.get('key_topics', [])
        if isinstance(key_topics, str):
            key_topics = [key_topics]
        
        # Extract vocabulary
        vocabulary = []
        if isinstance(summary.get('content'), dict):
            vocab = summary['content'].get('vocabulary', [])
            vocabulary = [{"term": item.get("word", item.get("term", "")), 
                          "definition": item.get("definition", "")} 
                         for item in vocab if item.get("word") or item.get("term")]
        
        # Get summary HTML using new normalization method with dict-as-string support
        summary_html = ""
        summary_type = summary.get('type', '') if isinstance(summary, dict) else ""
        
        # Handle dict-as-string format from chunked processing
        summary_payload = summary
        if isinstance(summary, dict):
            if 'content' in summary:
                summary_payload = summary['content']
            elif 'text' in summary:
                summary_payload = summary['text']
        
        # Parse dict-as-string at nested levels
        if isinstance(summary_payload, dict) and 'summary' in summary_payload:
            summary_payload['summary'] = ModernDashboardHTTPRequestHandler._maybe_parse_dict_string(
                summary_payload['summary']
            )
        summary_payload = ModernDashboardHTTPRequestHandler._maybe_parse_dict_string(summary_payload)
        
        # Normalize to the best text field
        summary_html = ModernDashboardHTTPRequestHandler.normalize_summary_content(
            summary_payload, summary_type
        )
        
        # Unescape escaped newlines so formatter can see bullets/headers
        if isinstance(summary_html, str) and '\\n' in summary_html and '\n' not in summary_html:
            summary_html = summary_html.replace('\\n', '\n')
        
        # Debug logging to help diagnose normalization issues
        logger.info(f"Summary after normalization: len={len(summary_html or '')}, preview={repr((summary_html or '')[:120])}")
        
        # Format summary for better readability using Key Points formatter
        if summary_html and not summary_html.startswith('<'):
            # Use the new Key Points formatter for structured content
            summary_html = ModernDashboardHTTPRequestHandler.format_key_points(summary_html)
        
        # Sanitize HTML for security (only if bleach is available)
        if BLEACH_AVAILABLE and summary_html:
            summary_html = bleach.clean(summary_html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)
        
        # Create AI model string
        model = processing.get('model', '')
        provider = processing.get('llm_provider', '')
        ai_model = f"{model} ({provider})" if model and provider else model or provider or ""
        
        # Create cache bust string from available data
        cache_bust_parts = [uploaded_pretty, views_pretty, ai_model]
        cache_bust = hash("".join(filter(None, cache_bust_parts))) % 10000
        
        return {
            "title": title,
            "thumbnail": thumbnail,
            "channel": channel,
            "duration_str": video_duration_str,
            "video_duration_str": video_duration_str,
            "audio_dur_pretty": audio_dur_pretty,
            "views_pretty": views_pretty,
            "uploaded_pretty": uploaded_pretty,
            "like_count_pretty": like_count_pretty,
            "comment_count_pretty": comment_count_pretty,
            "follower_count_pretty": follower_count_pretty,
            "resolution": resolution,
            "fps_pretty": fps_pretty,
            "categories": categories,
            "subcategory_pairs": subcategory_pairs,
            "key_topics": key_topics,
            "ai_model": ai_model,
            "audio_mp3": audio_url,
            "summary_html": summary_html,
            "vocabulary": vocabulary,
            "back_url": "/",
            "youtube_url": video.get("url") or report_data.get("url") or report_data.get("canonical_url", ""),
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
        elif path == '/health/db':
            self.serve_health_db()
        elif path == '/api/db-status':
            self.serve_db_status()
        elif path == '/api/db-reset':
            self.serve_db_reset()
        elif path == '/api/migrate-audio':
            self.serve_audio_migration()
        elif path.startswith('/api/'):
            self.serve_api()
        elif path.endswith('.css'):
            self.serve_css()
        elif path.endswith('.js'):
            self.serve_js(path)
        elif path.startswith('/images/'):
            self.serve_images()
        elif path.endswith('.html') and path != '/':
            self.serve_report(path, self._query_params)
        elif path.endswith('.json') and path != '/':
            self.serve_report(path, self._query_params)
        elif path.startswith('/exports/by_video/'):
            self.serve_audio_by_video()
        elif path.startswith('/exports/'):
            self.serve_audio_file()
        else:
            super().do_GET()
    
    def do_POST(self):
        if self.path == '/delete-reports':
            self.handle_delete_reports()
        elif self.path == '/api/upload-report':
            self.handle_upload_report()
        elif self.path == '/api/upload-database':
            self.handle_upload_database()
        elif self.path == '/api/download-database':
            self.handle_download_database()
        elif self.path == '/api/upload-audio':
            self.handle_upload_audio()
        elif self.path == '/api/content':
            self.handle_content_api()
        elif self.path.startswith('/api/content/'):
            self.handle_content_update_api()
        elif self.path.startswith('/api/delete'):
            self.handle_delete_request()
        else:
            self.send_error(404, "Endpoint not found")
    
    def do_DELETE(self):
        """Handle DELETE requests for the new delete API endpoint"""
        if self.path.startswith('/api/delete/'):
            self.handle_delete_request()
        else:
            self.send_error(404, "DELETE endpoint not found")
    
    def serve_dashboard(self):
        """Serve the modern dashboard using templates"""
        try:
            # Use SQLite data when available (for proper category structure)
            reports_data = []
            
            if content_index and USING_SQLITE:
                # Get reports from SQLite with proper category structure
                try:
                    sqlite_results = content_index.search_reports(
                        filters=None,
                        query=None,
                        sort='indexed_at',  # Sort by most recent
                        page=1,
                        size=100  # Get first 100 reports
                    )
                    
                    # Convert SQLite data to format expected by dashboard_v3.js
                    for item in sqlite_results.get('reports', []):
                        # The dashboard_v3.js expects this structure
                        report_data = {
                            'file_stem': item.get('file_stem', item.get('id', '')),
                            'title': item.get('title', 'Unknown Title'),
                            'channel': item.get('channel_name', 'Unknown Channel'),
                            'thumbnail_url': item.get('thumbnail_url', ''),
                            'duration_seconds': item.get('duration_seconds', 0),
                            'video_id': item.get('video_id', ''),
                            'analysis': item.get('analysis', {}),  # This contains the categories structure
                            'media': item.get('media', {}),
                            'media_metadata': item.get('media_metadata', {}),
                            'created_date': item.get('indexed_at', '')[:10] if item.get('indexed_at') else '',
                            'created_time': item.get('indexed_at', '')[11:16] if item.get('indexed_at') else ''
                        }
                        reports_data.append(report_data)
                    
                    logger.info(f"✅ Dashboard using SQLite data: {len(reports_data)} reports")
                    
                except Exception as e:
                    logger.error(f"❌ SQLite dashboard data failed: {e}")
                    # Fall back to file-based approach
                    reports_data = []
            
            # Fallback to file-based approach if SQLite unavailable or failed
            if not reports_data:
                logger.info("🔄 Dashboard falling back to file-based data")
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
            # Remove 'static/' prefix if present to avoid static/static/ duplication
            if filename.startswith('static/'):
                filename = filename[7:]  # Remove 'static/' prefix
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

    def serve_images(self):
        """Serve images from a local images/ folder if present"""
        try:
            img_path = Path(self.path.lstrip('/'))  # e.g., images/icon.png
            if not img_path.parts or img_path.parts[0] != 'images':
                self.send_error(404, 'Not found')
                return
            fs_path = Path('.') / img_path
            if fs_path.exists() and fs_path.is_file():
                # Basic content type detection
                ext = fs_path.suffix.lower()
                ctype = 'image/png' if ext == '.png' else 'image/jpeg' if ext in ('.jpg', '.jpeg') else 'image/svg+xml' if ext == '.svg' else 'application/octet-stream'
                self.send_response(200)
                self.send_header('Content-type', ctype)
                self.send_header('Cache-Control', 'public, max-age=3600')
                self.end_headers()
                self.wfile.write(fs_path.read_bytes())
            else:
                self.send_error(404, 'Image not found')
        except Exception as e:
            logger.error(f"Error serving image {self.path}: {e}")
            self.send_error(500, "Error serving image")
    
    def serve_report(self, path: str, qs: dict = None):
        """
        Serve individual report pages
        path: normalized URL path (no query string), e.g. "/_id.json"
        qs: parsed query params (from do_GET)
        """
        try:
            # Extract report ID from path
            filename = Path(path.lstrip('/'))               # "_id.json"
            report_id = filename.stem                       # "_id"
            
            # Check SQLite database first (for new records)
            if content_index and filename.suffix == '.json':
                report_data = content_index.get_report_by_id(report_id)
                if report_data:
                    return self.serve_sqlite_report(report_data, qs)
            
            # Fallback to JSON file (legacy)
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
            
            # Extract video_id from the correct location (YouTube metadata)
            youtube_meta = (report_data.get('source_metadata') or {}).get('youtube', {})
            video_id = youtube_meta.get('video_id', '') or video_info.get('video_id', '')
            
            # Create proper video_info with video_id for audio discovery
            enhanced_video_info = dict(video_info)  # Copy existing video_info
            if video_id:
                enhanced_video_info['video_id'] = video_id
            
            # Discover audio file with enhanced video_info
            logger.info(f"🎬 original video_info keys: {list(video_info.keys()) if video_info else 'None'}")
            logger.info(f"🆔 extracted video_id from youtube_meta: '{video_id}'")
            logger.info(f"🎬 enhanced_video_info: {enhanced_video_info}")
            audio_url = self._discover_audio_file(enhanced_video_info)
            
            # Generate HTML content
            if use_v2 and JINJA2_AVAILABLE:
                # V2 Tailwind Template Path
                logger.info("🚀 Rendering V2 Tailwind template")
                
                ctx = self.to_report_v2_dict(report_data, audio_url)
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
    
    def serve_sqlite_report(self, report_data: dict, qs: dict = None):
        """Serve a report from SQLite data with template support"""
        try:
            qs = qs or {}
            v_param = qs.get('v', [''])[0]
            use_v2 = v_param == '2'

            # For JSON requests without v=2, return JSON data instead of HTML
            # We're in serve_sqlite_report, which is only called for database records
            # If v param is not '2', and we're here, it should be a JSON request
            if v_param != '2':
                return self.serve_sqlite_report_json(report_data)

            
            # Extract video info and summary from SQLite data
            video_info = {
                'video_id': report_data.get('video_id', ''),
                'title': report_data.get('title', 'Untitled'),
                'channel_name': report_data.get('channel', ''),
                'published_at': report_data.get('published_at', ''),
                'duration_seconds': report_data.get('duration_seconds', 0),
                'thumbnail_url': report_data.get('thumbnail_url', ''),
                'canonical_url': report_data.get('canonical_url', '')
            }
            
            # Handle both SQLite and PostgreSQL data formats
            if 'summary_text' in report_data:
                # PostgreSQL format: summary_text, summary_html directly available
                summary = report_data.get('summary_text', 'No summary available.')
            else:
                # SQLite format: nested summary.text structure
                summary = report_data.get('summary', {}).get('text', 'No summary available.')
            processing = report_data.get('processor_info', {})
            
            # Discover audio file
            logger.info(f"🆔 extracted video_id from SQLite: '{video_info['video_id']}'")
            enhanced_video_info = {**video_info, **report_data}
            audio_url = self._discover_audio_file(enhanced_video_info)
            
            # Generate HTML content
            if use_v2 and JINJA2_AVAILABLE:
                # V2 Tailwind Template Path
                logger.info("🚀 Rendering V2 Tailwind template from SQLite data")

                # Transform PostgreSQL data to match expected format
                if 'summary_text' in report_data:
                    # PostgreSQL format - create nested summary structure
                    transformed_data = report_data.copy()
                    transformed_data['summary'] = {
                        'text': report_data.get('summary_text', ''),
                        'html': report_data.get('summary_html', ''),  # Already formatted HTML
                        'type': report_data.get('summary_variant', 'comprehensive')
                    }
                    # Also copy video fields for compatibility
                    transformed_data['video'] = {
                        'video_id': report_data.get('video_id', ''),
                        'title': report_data.get('title', ''),
                        'channel': report_data.get('channel_name', ''),
                        'url': report_data.get('canonical_url', '')
                    }
                    # Get the context but override summary_html with our pre-formatted version
                    ctx = self.to_report_v2_dict(transformed_data, audio_url)
                    ctx['summary_html'] = report_data.get('summary_html', '')  # Use pre-formatted HTML
                else:
                    # SQLite format - use as-is
                    ctx = self.to_report_v2_dict(report_data, audio_url)
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
            logger.error(f"Error serving SQLite report: {e}")
            self.send_error(500, "Error serving SQLite report")

    def serve_sqlite_report_json(self, report_data: dict):
        """Serve a JSON response from PostgreSQL/SQLite data"""
        try:
            # Transform PostgreSQL data to the expected JSON format
            if 'summary_text' in report_data:
                # PostgreSQL format - extract summary data directly
                summary_text = report_data.get('summary_text', '')
                summary_html = report_data.get('summary_html', '')
                summary_variant = report_data.get('summary_variant', 'comprehensive')
            else:
                # SQLite format - extract from nested structure
                summary_data = report_data.get('summary', {})
                summary_text = summary_data.get('text', '')
                summary_html = summary_data.get('html', '')
                summary_variant = summary_data.get('type', 'comprehensive')

            # Create JSON response in the format expected by dashboard
            json_response = {
                "video": {
                    "video_id": report_data.get('video_id', ''),
                    "title": report_data.get('title', ''),
                    "channel": report_data.get('channel_name', ''),
                    "url": report_data.get('canonical_url', ''),
                    "duration_seconds": report_data.get('duration_seconds', 0),
                    "published_at": report_data.get('published_at', '')
                },
                "summary": {
                    "text": summary_text,
                    "html": summary_html,
                    "type": summary_variant
                },
                "thumbnail_url": report_data.get('thumbnail_url', ''),
                "analysis": report_data.get('analysis_json') or report_data.get('analysis', {}),
                "subcategories_json": report_data.get('subcategories_json'),
                "has_audio": report_data.get('has_audio', False)
            }

            # Send JSON response
            self.send_response(200)
            self.send_header('Content-type', 'application/json; charset=utf-8')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()

            import json
            json_data = json.dumps(json_response, ensure_ascii=False, indent=2)
            self.wfile.write(json_data.encode('utf-8'))

        except Exception as e:
            logger.error(f"Error serving SQLite JSON report: {e}")
            self.send_error(500, "Error serving JSON report")

    def _discover_audio_file(self, video_info: dict) -> str:
        """Discover audio file for a video (extracted from legacy method)"""
        logger.info(f"🔍 _discover_audio_file called with video_info: {video_info}")
        audio_url = ''
        try:
            video_id = video_info.get('video_id', '')
            logger.info(f"🆔 Extracted video_id: '{video_id}'")
            if video_id:
                candidates = []
                # Check both local exports and uploaded files directory
                search_dirs = [Path('./exports')]
                if Path('/app/data/exports').exists():
                    search_dirs.append(Path('/app/data/exports'))
                
                logger.info(f"🔍 Looking for audio: video_id={video_id}")
                for search_dir in search_dirs:
                    # List all MP3 files for debugging
                    if search_dir.exists():
                        all_mp3s = list(search_dir.glob('*.mp3'))
                        logger.info(f"🗂️ {search_dir} contains {len(all_mp3s)} MP3 files total")
                        for mp3 in all_mp3s[:3]:  # Show first 3 for debugging
                            logger.info(f"🎵 Available MP3: {mp3.name}")
                    
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
            else:
                logger.warning(f"❌ No video_id found in video_info: {video_info}")
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
        
        # Check if this is NEW format (summary directly at top level)
        if not summary_content and 'summary' in summary:
            # NEW format: summary.summary, summary.headline
            summary_text = summary.get('summary', 'No summary available')
            headline = summary.get('headline', '')
            vocabulary = []  # NEW format doesn't have vocabulary in same location
            glossary = []    # NEW format doesn't have glossary in same location
        elif not summary_content and ('comprehensive' in summary or 'audio' in summary):
            # NEW format: summary.comprehensive, summary.audio
            summary_text = (summary.get('comprehensive') or 
                           summary.get('audio') or 'No summary available')
            headline = summary.get('headline', '')
            vocabulary = []  # NEW format doesn't have vocabulary in same location  
            glossary = []    # NEW format doesn't have glossary in same location
        elif isinstance(summary_content, dict):
            # OLD format: summary.content.summary, summary.content.headline  
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
            
            # Look for audio file in persistent storage ONLY
            audio_path = Path('/app/data/exports') / audio_filename
                
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

    def serve_audio_by_video(self):
        """Resolve and stream the most recent audio file for a given video_id.

        Route: /exports/by_video/<video_id>.mp3 (extension optional)
        """
        try:
            # Extract video_id from path
            parts = self.path.split('/')
            if len(parts) < 4:
                self.send_error(400, "Invalid by_video path")
                return
            video_id_with_ext = parts[-1]
            video_id = video_id_with_ext.replace('.mp3', '')

            # Search for candidate files in common locations
            search_dirs = [Path('/app/data/exports')]
            patterns = [
                f'audio_{video_id}_*.mp3',   # standard new pattern
                f'{video_id}_*.mp3',         # legacy pattern
                f'*{video_id}*.mp3',         # fallback
            ]

            best_match = None
            best_mtime = -1

            for d in search_dirs:
                if not d.exists():
                    continue
                for pat in patterns:
                    for p in d.glob(pat):
                        try:
                            mtime = p.stat().st_mtime
                            if mtime > best_mtime:
                                best_mtime = mtime
                                best_match = p
                        except OSError:
                            continue

            if not best_match:
                self.send_error(404, f"Audio not found for video_id {video_id}")
                return

            # Stream the resolved file
            self.send_response(200)
            self.send_header('Content-type', 'audio/mpeg')
            self.send_header('Content-Length', str(best_match.stat().st_size))
            self.send_header('Cache-Control', 'public, max-age=600')
            self.end_headers()
            with open(best_match, 'rb') as f:
                self.wfile.write(f.read())
        except Exception as e:
            logger.error(f"Error serving by_video audio {self.path}: {e}")
            self.send_error(500, "Error resolving audio by video id")
    
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

    def serve_health_db(self):
        """Serve database health check endpoint with PostgreSQL connectivity test"""
        try:
            # Check if PostgreSQL is enabled
            read_from_postgres = os.getenv('READ_FROM_POSTGRES', 'false').lower() == 'true'

            if read_from_postgres and PSYCOPG2_AVAILABLE:
                # Test PostgreSQL connection
                start_time = datetime.now()
                postgres_healthy = test_postgres_health()
                end_time = datetime.now()
                latency_ms = (end_time - start_time).total_seconds() * 1000

                if postgres_healthy:
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    health_data = {
                        "db": "ok",
                        "type": "postgresql",
                        "latency_ms": round(latency_ms, 2),
                        "timestamp": datetime.now().isoformat()
                    }
                    self.wfile.write(json.dumps(health_data).encode())
                else:
                    raise Exception("PostgreSQL health check failed")
            else:
                # Fallback to SQLite health check
                db_path = Path('ytv2_content.db')
                if db_path.exists():
                    start_time = datetime.now()
                    conn = sqlite3.connect(db_path)
                    cur = conn.cursor()
                    cur.execute("SELECT 1;")
                    cur.fetchone()
                    conn.close()
                    end_time = datetime.now()
                    latency_ms = (end_time - start_time).total_seconds() * 1000

                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    health_data = {
                        "db": "ok",
                        "type": "sqlite",
                        "latency_ms": round(latency_ms, 2),
                        "timestamp": datetime.now().isoformat()
                    }
                    self.wfile.write(json.dumps(health_data).encode())
                else:
                    raise Exception("Database file not found")

        except Exception as e:
            logger.error(f"Error serving database health check: {e}")
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            error_data = {
                "db": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
            self.wfile.write(json.dumps(error_data).encode())
    
    def serve_db_status(self):
        """Serve database status endpoint for diagnostics"""
        try:
            # Check all possible database locations
            db_paths = [
                Path('/app/data/ytv2_content.db'),      # Render persistent disk mount
                Path('./data/ytv2_content.db'),         # Data subdirectory
                Path('/app/ytv2_content.db'),           # Root app directory
                Path('./ytv2_content.db')               # Current directory
            ]
            
            db_info = {
                "database_backend": "SQLite" if USING_SQLITE else "JSON",
                "current_database": str(getattr(content_index, 'db_path', 'unknown')) if 'content_index' in globals() else None,
                "searched_paths": [],
                "found_databases": [],
                "persistent_disk_mount": "/opt/render/project/src/data",
                "environment": {
                    "PWD": os.getcwd(),
                    "RENDER_INSTANCE_ID": os.getenv('RENDER_INSTANCE_ID', 'not-set'),
                    "RENDER_SERVICE_ID": os.getenv('RENDER_SERVICE_ID', 'not-set')
                }
            }
            
            # Check each path
            for db_path in db_paths:
                path_info = {
                    "path": str(db_path),
                    "exists": db_path.exists(),
                    "size_bytes": db_path.stat().st_size if db_path.exists() else 0,
                    "readable": False,
                    "record_count": 0
                }
                
                if db_path.exists():
                    try:
                        # Try to connect and get record count
                        import sqlite3
                        conn = sqlite3.connect(str(db_path))
                        cursor = conn.execute("SELECT COUNT(*) FROM content")
                        path_info["record_count"] = cursor.fetchone()[0]
                        cursor = conn.execute("SELECT COUNT(*) FROM content_summaries") 
                        path_info["summary_count"] = cursor.fetchone()[0]
                        conn.close()
                        path_info["readable"] = True
                        db_info["found_databases"].append(path_info)
                    except Exception as e:
                        path_info["error"] = str(e)
                        
                db_info["searched_paths"].append(path_info)
            
            # Get current index status
            if 'content_index' in globals():
                try:
                    if hasattr(content_index, 'get_report_count'):
                        db_info["active_index_count"] = content_index.get_report_count()
                except Exception as e:
                    db_info["active_index_error"] = str(e)
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            self.wfile.write(json.dumps(db_info, indent=2).encode())
            
        except Exception as e:
            logger.error(f"Error serving database status: {e}")
            error_data = {"error": "Database status check failed", "message": str(e)}
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(error_data).encode())
    
    def serve_db_reset(self):
        """Reset database with correct schema (emergency recovery)"""
        try:
            # Find database paths
            db_paths = [
                Path('/app/data/ytv2_content.db'), # Render persistent disk mount
                Path('./data/ytv2_content.db'),    # Local data subdirectory
                Path('/app/ytv2_content.db'),      # Root app directory
                Path('./ytv2_content.db')          # Current directory
            ]
            
            db_path = None
            for path in db_paths:
                if path.parent.exists():
                    db_path = path
                    break
                    
            if not db_path:
                self.send_error(500, "Cannot find suitable database location")
                return
                
            # Backup existing database if it exists
            if db_path.exists():
                backup_path = Path(str(db_path) + '.backup.' + str(int(time.time())))
                db_path.rename(backup_path)
                logger.info(f"🔄 Backed up existing database to: {backup_path}")
                
            # Create new database with correct schema
            create_empty_ytv2_database(db_path)
            logger.info(f"✅ Database reset with correct schema: {db_path}")
            
            response = {
                "status": "success",
                "message": "Database reset with correct schema",
                "database_path": str(db_path),
                "backup_created": str(backup_path) if 'backup_path' in locals() else None
            }
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response, indent=2).encode())
            
        except Exception as e:
            logger.error(f"Database reset error: {e}")
            error_data = {"error": "Database reset failed", "message": str(e)}
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(error_data).encode())
    
    def serve_audio_migration(self):
        """Migrate audio files from ephemeral to persistent storage"""
        try:
            ephemeral_exports = Path('./exports')
            persistent_exports = Path('/app/data/exports')
            
            if not ephemeral_exports.exists():
                response = {"status": "info", "message": "No ephemeral exports directory found"}
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
                return
            
            # Create persistent directory
            persistent_exports.mkdir(parents=True, exist_ok=True)
            
            # Find all audio files in ephemeral storage
            audio_files = list(ephemeral_exports.glob('*.mp3'))
            migrated = []
            errors = []
            
            for audio_file in audio_files:
                try:
                    dest_path = persistent_exports / audio_file.name
                    
                    # Copy file to persistent storage
                    import shutil
                    shutil.copy2(audio_file, dest_path)
                    
                    # Verify the copy worked
                    if dest_path.exists() and dest_path.stat().st_size == audio_file.stat().st_size:
                        migrated.append(audio_file.name)
                        logger.info(f"✅ Migrated audio: {audio_file.name}")
                    else:
                        errors.append(f"Copy verification failed for {audio_file.name}")
                        
                except Exception as e:
                    errors.append(f"Failed to migrate {audio_file.name}: {str(e)}")
                    
            response = {
                "status": "success" if not errors else "partial",
                "message": f"Audio migration completed",
                "migrated_count": len(migrated),
                "error_count": len(errors),
                "migrated_files": migrated[:10],  # Show first 10
                "errors": errors[:5] if errors else [],  # Show first 5 errors
                "persistent_path": str(persistent_exports),
                "ephemeral_path": str(ephemeral_exports)
            }
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response, indent=2).encode())
            
        except Exception as e:
            logger.error(f"Audio migration error: {e}")
            error_data = {"error": "Audio migration failed", "message": str(e)}
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
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
            elif path == '/api/refresh':
                self.serve_api_refresh()
            elif path == '/api/backup':
                self.serve_api_backup()
            elif path.startswith('/api/backup/'):
                self.serve_backup_file()
            elif path == '/api/download-database':
                self.handle_download_database()
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
            if 'channel' in query_params:
                active_filters['channel'] = query_params['channel']
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
            # Return JSON error instead of HTML (per OpenAI recommendation)
            error_data = {"error": "Filters API error", "message": str(e), "status": "error"}
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(error_data, indent=2).encode())
    
    def serve_api_reports_v2(self, query_params: Dict[str, List[str]]):
        """Serve Phase 2 reports API endpoint with filtering, search, and pagination"""
        try:
            if not content_index:
                # Fallback to legacy method
                return self.serve_api_reports()
            
            # Parse query parameters
            filters = {}
            
            # Filter parameters with validation (CRITICAL: include subcategory and parentCategory per OpenAI recommendation)
            for param in ['source', 'language', 'category', 'subcategory', 'parentCategory', 'channel', 'content_type', 'complexity']:
                if param in query_params:
                    # Limit array size and sanitize/normalize strings (per OpenAI recommendation)
                    values = query_params[param][:10]  # Max 10 items
                    normalized_values = []
                    for v in values:
                        if v and str(v).strip():
                            # Normalize: strip whitespace, collapse spaces, en-dash → hyphen
                            normalized = ' '.join(str(v).strip().replace('–', '-').split())[:50]
                            if normalized:
                                normalized_values.append(normalized)
                    filters[param] = normalized_values
            
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
            valid_sorts = [
                'newest', 'oldest', 'title', 'title_asc', 'title_desc', 
                'duration', 'duration_desc', 'duration_asc',
                # SQLite backend specific sorts
                'added_desc', 'added_asc', 'video_newest', 'video_oldest',
                'title_az', 'title_za'
            ]
            original_sort = sort
            if sort not in valid_sorts:
                sort = 'newest'
            
            # Debug logging for sort validation
            logger.info(f"🔍 Sort validation: requested='{original_sort}', validated='{sort}', valid_sorts={valid_sorts}")
            
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
            
            # Add deployment verification flag  
            results['deployment_version'] = 'v2025-09-11-sorting-fix'
            
            # Send response
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Cache-Control', 'no-cache')  # Don't cache filtered results
            self.end_headers()
            
            self.wfile.write(json.dumps(results, ensure_ascii=False, indent=2).encode())
            
        except Exception as e:
            logger.error(f"Error serving reports API v2: {e}")
            # Return JSON error instead of HTML (per OpenAI recommendation)
            error_data = {"error": "Reports API error", "message": str(e), "status": "error"}
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(error_data, indent=2).encode())
    
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
            # Check SQLite database first (for new records)
            if content_index:
                report_data = content_index.get_report_by_id(report_id)
                if report_data:
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps(report_data, ensure_ascii=False, indent=2).encode())
                    return
            
            # Look for JSON report (legacy fallback)
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
    
    def serve_api_refresh(self):
        """Force refresh the content index"""
        try:
            if not content_index:
                self.send_error(500, "Content index not available")
                return
            
            # Force immediate refresh
            count = content_index.force_refresh()
            
            result = {
                "status": "success",
                "message": f"Content index refreshed - {count} reports loaded",
                "reports_count": count,
                "timestamp": datetime.now().isoformat()
            }
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            self.wfile.write(json.dumps(result, indent=2).encode())
            
        except Exception as e:
            logger.error(f"Error refreshing content index: {e}")
            error_data = {"error": "Failed to refresh index", "message": str(e)}
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(error_data).encode())
    
    def serve_api_backup(self):
        """Create and serve database backup"""
        try:
            # Import the backup functionality
            import importlib.util
            spec = importlib.util.spec_from_file_location("backup_database", "backup_database.py")
            backup_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(backup_module)
            
            # Create backup
            result = backup_module.create_database_backup()
            
            if result['success']:
                # Return backup info with download links
                backup_path = Path(result['backup_path'])
                info_path = Path(result['info_path'])
                
                response_data = {
                    "status": "success",
                    "message": "Database backup created successfully",
                    "backup_info": result['statistics'],
                    "downloads": {
                        "database": f"/api/backup/{backup_path.name}",
                        "metadata": f"/api/backup/{info_path.name}"
                    },
                    "timestamp": datetime.now().isoformat()
                }
            else:
                response_data = {
                    "status": "error",
                    "message": "Backup creation failed",
                    "error": result.get('error', 'Unknown error'),
                    "timestamp": datetime.now().isoformat()
                }
            
            self.send_response(200 if result['success'] else 500)
            self.send_header('Content-type', 'application/json')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            self.wfile.write(json.dumps(response_data, indent=2).encode())
            
        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            error_data = {"error": "Failed to create backup", "message": str(e)}
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(error_data).encode())
    
    def serve_backup_file(self):
        """Serve backup files for download"""
        try:
            # Extract filename from path
            path_parts = self.path.split('/')
            if len(path_parts) < 4:
                self.send_error(404, "Invalid backup file path")
                return
                
            filename = path_parts[-1]
            file_path = Path("data") / filename
            
            # Security check - only allow backup files
            if not (filename.startswith(('ytv2_backup_', 'backup_info_')) and 
                   filename.endswith(('.db', '.json'))):
                self.send_error(403, "Access denied")
                return
            
            if not file_path.exists():
                self.send_error(404, "Backup file not found")
                return
            
            # Serve the file
            content_type = 'application/octet-stream' if filename.endswith('.db') else 'application/json'
            
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
            self.send_header('Content-Length', str(file_path.stat().st_size))
            self.end_headers()
            
            with open(file_path, 'rb') as f:
                self.wfile.write(f.read())
                
        except Exception as e:
            logger.error(f"Error serving backup file: {e}")
            self.send_error(500, "Failed to serve backup file")
    
    def handle_delete_reports(self):
        """Handle POST request to delete selected reports"""
        try:
            # Optional auth (can be disabled for single-user deployments)
            disable_auth = os.getenv('DISABLE_DELETE_AUTH', '1') == '1'
            if not disable_auth:
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
            delete_audio = bool(request_data.get('delete_audio', True))
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
                video_id_for_audio = None
                for search_dir in search_dirs:
                    if search_dir.exists():
                        # Try different extensions
                        for ext in ['.json', '.html', '']:
                            file_path = search_dir / (filename + ext if not filename.endswith(ext) else filename)
                            if file_path.exists():
                                try:
                                    # If JSON, try to extract video_id for audio cleanup
                                    if file_path.suffix == '.json':
                                        try:
                                            data = json.loads(file_path.read_text(encoding='utf-8'))
                                            video_id_for_audio = (data.get('video') or {}).get('video_id', None)
                                        except Exception:
                                            video_id_for_audio = None
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
                
                # Delete audio files if requested and video id is known
                if delete_audio and video_id_for_audio:
                    for d in [Path('/app/data/exports'), Path('./exports')]:
                        if not d.exists():
                            continue
                        try:
                            patterns = [
                                f'audio_{video_id_for_audio}_*.mp3',
                                f'{video_id_for_audio}_*.mp3',
                                f'*{video_id_for_audio}*.mp3'
                            ]
                            for pat in patterns:
                                for p in d.glob(pat):
                                    try:
                                        p.unlink()
                                        logger.info(f"Deleted audio: {p}")
                                    except Exception as e:
                                        errors.append(f"Failed to delete audio {p}: {e}")
                        except Exception as e:
                            errors.append(f"Audio cleanup error for {video_id_for_audio}: {e}")
            
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
            
            auth_header = self.headers.get('Authorization', '')
            if not auth_header.startswith('Bearer ') or auth_header[7:] != sync_secret:
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
    
    def _auth_ok(self) -> bool:
        """Check bearer token authentication for delete operations"""
        # For personal use - no authentication required
        # This is your personal dashboard, no need for complex auth
        return True
    
    def _delete_one(self, report_id: str) -> dict:
        """Delete a single report by ID (idempotent)
        
        Args:
            report_id: The report ID (without extension)
            
        Returns:
            dict: Status information about the deletion
        """
        deleted_files = []
        errors = []
        
        # Search for report files in multiple directories
        search_dirs = [
            Path('./data/reports'),  # JSON reports (primary)
            Path('./exports'),       # HTML reports (legacy)
            Path('.')               # Current directory (legacy)
        ]
        
        video_id_for_audio = None
        
        # Delete report files
        for search_dir in search_dirs:
            if not search_dir.exists():
                continue
                
            for ext in ['.json', '.html']:
                file_path = search_dir / f"{report_id}{ext}"
                if file_path.exists():
                    try:
                        # Extract video_id from JSON files for audio cleanup
                        if ext == '.json':
                            try:
                                with open(file_path, 'r', encoding='utf-8') as f:
                                    data = json.load(f)
                                # Look in multiple possible locations for video_id
                                video_info = data.get('video', {})
                                youtube_meta = (data.get('source_metadata', {}) or {}).get('youtube', {})
                                video_id_for_audio = (
                                    video_info.get('video_id') or 
                                    youtube_meta.get('video_id') or
                                    None
                                )
                            except Exception as e:
                                logger.warning(f"Could not extract video_id from {file_path}: {e}")
                                video_id_for_audio = None
                        
                        file_path.unlink()
                        deleted_files.append(str(file_path))
                        logger.info(f"Deleted report: {file_path}")
                    except Exception as e:
                        errors.append(f"Failed to delete {file_path}: {e}")
        
        # Delete associated audio files if video_id was found
        if video_id_for_audio:
            audio_dirs = [
                Path('/app/data/exports'),  # Render deployment
                Path('./exports')           # Local development
            ]
            
            for audio_dir in audio_dirs:
                if not audio_dir.exists():
                    continue
                    
                # Search for audio files with different patterns
                patterns = [
                    f'audio_{video_id_for_audio}_*.mp3',  # Standard pattern
                    f'{video_id_for_audio}_*.mp3',        # Legacy pattern  
                    f'*{video_id_for_audio}*.mp3'         # Flexible pattern
                ]
                
                for pattern in patterns:
                    for audio_path in audio_dir.glob(pattern):
                        try:
                            audio_path.unlink()
                            deleted_files.append(str(audio_path))
                            logger.info(f"Deleted audio: {audio_path}")
                        except Exception as e:
                            errors.append(f"Failed to delete audio {audio_path}: {e}")
        
        # Delete from SQLite database if using SQLite backend
        if content_index and hasattr(content_index, 'db_path'):
            try:
                import sqlite3
                conn = sqlite3.connect(content_index.db_path)
                cursor = conn.cursor()
                
                # Delete from content_summaries first (foreign key constraint)
                cursor.execute("DELETE FROM content_summaries WHERE content_id = ? OR content_id LIKE ?", 
                             (report_id, f"%{report_id}%"))
                summary_deleted = cursor.rowcount
                
                # Delete from content table
                cursor.execute("DELETE FROM content WHERE id = ? OR video_id = ? OR id LIKE ?", 
                             (report_id, report_id, f"%{report_id}%"))
                content_deleted = cursor.rowcount
                
                conn.commit()
                conn.close()
                
                if content_deleted > 0 or summary_deleted > 0:
                    deleted_files.append(f"SQLite: {content_deleted} content, {summary_deleted} summaries")
                    logger.info(f"Deleted from SQLite: {content_deleted} content records, {summary_deleted} summaries")
                else:
                    logger.info(f"No SQLite records found for {report_id}")
                    
            except Exception as e:
                errors.append(f"Failed to delete from SQLite database: {e}")
                logger.error(f"SQLite deletion error for {report_id}: {e}")
        
        return {
            'report_id': report_id,
            'deleted_files': deleted_files,
            'errors': errors,
            'found_video_id': video_id_for_audio,
            'success': len(deleted_files) > 0 or len(errors) == 0  # Success if we deleted something OR no errors (idempotent)
        }
    
    def handle_upload_database(self):
        """Handle POST request to upload SQLite database from NAS"""
        try:
            # Check sync secret for authentication
            sync_secret = os.getenv('SYNC_SECRET')
            if not sync_secret:
                self.send_error(500, "Sync not configured")
                return
            
            auth_header = self.headers.get('Authorization', '')
            if not auth_header.startswith('Bearer ') or auth_header[7:] != sync_secret:
                logger.warning(f"Database upload rejected: Invalid auth from {self.client_address[0]}")
                self.send_error(401, "Unauthorized")
                return
            
            # Parse multipart form data
            content_type = self.headers.get('Content-Type', '')
            if not content_type.startswith('multipart/form-data'):
                self.send_error(400, "Expected multipart/form-data")
                return
            
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self.send_error(400, "No data received")
                return
            if content_length > 50 * 1024 * 1024:  # 50MB limit for database
                self.send_error(413, "Database too large")
                return
            
            post_data = self.rfile.read(content_length)
            
            # Parse form data
            import cgi
            import io
            
            form_data = cgi.FieldStorage(
                fp=io.BytesIO(post_data),
                headers=self.headers,
                environ={'REQUEST_METHOD': 'POST'}
            )
            
            if 'database' not in form_data:
                self.send_error(400, "No database file provided")
                return
            
            database_field = form_data['database']
            if not hasattr(database_field, 'file') or not database_field.file:
                self.send_error(400, "Invalid database file")
                return
            
            # Save database file to persistent disk
            # Try persistent disk locations first, fallback to current directory
            persistent_locations = [
                Path('/app/data/ytv2_content.db'),  # Render persistent disk mount
                Path('./data/ytv2_content.db'),     # Local data subdirectory  
                Path('./ytv2_content.db')           # Current directory (fallback)
            ]
            
            db_path = None
            for location in persistent_locations:
                try:
                    # Ensure parent directory exists
                    location.parent.mkdir(parents=True, exist_ok=True)
                    # Test write access
                    test_file = location.parent / '.write_test'
                    test_file.write_text('test')
                    test_file.unlink()
                    db_path = location
                    break
                except (OSError, PermissionError):
                    continue
            
            if not db_path:
                logger.error("No writable location found for database")
                self.send_error(500, "Cannot save database - no writable location")
                return
                
            backup_path = db_path.parent / f"{db_path.stem}.backup{db_path.suffix}"
            logger.info(f"Saving database to: {db_path}")
            
            # Create backup of existing database
            if db_path.exists():
                import shutil
                shutil.copy2(db_path, backup_path)
                logger.info(f"Created database backup: {backup_path}")
            
            # Write new database
            with open(db_path, 'wb') as f:
                database_field.file.seek(0)
                f.write(database_field.file.read())
            
            logger.info(f"✅ SQLite database updated: {db_path}")
            
            # Reinitialize content index with new database
            global content_index, USING_SQLITE
            try:
                if USING_SQLITE:
                    content_index = ContentIndex(str(db_path))
                    logger.info(f"🔄 Content index reinitialized with new database")
                else:
                    logger.warning("⚠️ SQLite backend not available, cannot reinitialize")
            except Exception as reinit_error:
                logger.error(f"❌ Failed to reinitialize content index: {reinit_error}")
            
            # Send success response
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                'success': True,
                'message': 'Database updated successfully',
                'size': db_path.stat().st_size
            }).encode())
            
        except Exception as e:
            logger.error(f"Database upload error: {e}")
            self.send_error(500, f"Database upload failed: {str(e)}")

    def handle_download_database(self):
        """Handle GET request to download SQLite database"""
        try:
            # Check sync secret for authentication
            sync_secret = os.getenv('SYNC_SECRET')
            if not sync_secret:
                self.send_error(500, "Sync not configured")
                return
            
            auth_header = self.headers.get('Authorization', '')
            if not auth_header.startswith('Bearer ') or auth_header[7:] != sync_secret:
                logger.warning(f"Database download rejected: Invalid auth from {self.client_address[0]}")
                self.send_error(401, "Unauthorized")
                return
            
            # Find database file
            db_paths = [
                Path('/app/data/ytv2_content.db'),  # Render persistent disk mount
                Path('./data/ytv2_content.db'),     # Local data subdirectory
                Path('/app/ytv2_content.db'),       # Root app directory
                Path('./ytv2_content.db')           # Current directory (fallback)
            ]
            
            db_path = None
            for path in db_paths:
                if path.exists():
                    db_path = path
                    break
            
            if not db_path:
                logger.error("Database file not found")
                self.send_error(404, "Database not found")
                return
            
            logger.info(f"Downloading database from: {db_path}")
            
            # Send database file
            self.send_response(200)
            self.send_header('Content-Type', 'application/octet-stream')
            self.send_header('Content-Disposition', 'attachment; filename="ytv2_content.db"')
            self.send_header('Content-Length', str(db_path.stat().st_size))
            self.end_headers()
            
            with open(db_path, 'rb') as f:
                while True:
                    data = f.read(8192)
                    if not data:
                        break
                    self.wfile.write(data)
            
            logger.info(f"✅ Database download completed: {db_path.stat().st_size} bytes")
            
        except Exception as e:
            logger.error(f"Database download error: {e}")
            self.send_error(500, f"Database download failed: {str(e)}")
    
    def handle_upload_audio(self):
        """Handle POST request to upload audio files from NAS"""
        try:
            # Check sync secret for authentication
            sync_secret = os.getenv('SYNC_SECRET')
            if not sync_secret:
                self.send_error(500, "Sync not configured")
                return
            
            auth_header = self.headers.get('Authorization', '')
            if not auth_header.startswith('Bearer ') or auth_header[7:] != sync_secret:
                logger.warning(f"Audio upload rejected: Invalid auth from {self.client_address[0]}")
                self.send_error(401, "Unauthorized")
                return
            
            # Parse multipart form data
            content_type = self.headers.get('Content-Type', '')
            if not content_type.startswith('multipart/form-data'):
                self.send_error(400, "Expected multipart/form-data")
                return
            
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self.send_error(400, "No data received")
                return
            if content_length > 25 * 1024 * 1024:  # 25MB limit for audio
                self.send_error(413, "Audio file too large")
                return
            
            post_data = self.rfile.read(content_length)
            
            # Parse form data
            import cgi
            import io
            
            form_data = cgi.FieldStorage(
                fp=io.BytesIO(post_data),
                headers=self.headers,
                environ={'REQUEST_METHOD': 'POST'}
            )
            
            if 'audio' not in form_data:
                self.send_error(400, "No audio file provided")
                return
            
            audio_field = form_data['audio']
            if not audio_field.filename:
                self.send_error(400, "No audio filename provided")
                return
            
            # Save audio file to persistent storage
            exports_dir = Path('/app/data/exports') if Path('/app/data').exists() else Path('./exports')
            exports_dir.mkdir(parents=True, exist_ok=True)
            
            audio_path = exports_dir / audio_field.filename
            with open(audio_path, 'wb') as f:
                audio_field.file.seek(0)
                f.write(audio_field.file.read())
            
            logger.info(f"✅ Audio file uploaded: {audio_field.filename}")
            
            # Send success response
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                'success': True,
                'message': 'Audio uploaded successfully',
                'filename': audio_field.filename,
                'size': audio_path.stat().st_size
            }).encode())
            
        except Exception as e:
            logger.error(f"Audio upload error: {e}")
            self.send_error(500, f"Audio upload failed: {str(e)}")
    
    def handle_content_api(self):
        """Handle POST /api/content - Create or update content with UPSERT logic"""
        try:
            # Check sync secret for authentication
            sync_secret = os.getenv('SYNC_SECRET')
            if not sync_secret:
                self.send_error(500, "Sync not configured")
                return
            
            auth_header = self.headers.get('Authorization', '')
            if not auth_header.startswith('Bearer ') or auth_header[7:] != sync_secret:
                logger.warning(f"Content API rejected: Invalid auth from {self.client_address[0]}")
                self.send_error(401, "Unauthorized")
                return
            
            # Read JSON payload
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self.send_error(400, "No data provided")
                return
            
            post_data = self.rfile.read(content_length)
            try:
                content_data = json.loads(post_data.decode('utf-8'))
            except json.JSONDecodeError as e:
                self.send_error(400, f"Invalid JSON: {e}")
                return
            
            # Validate required fields
            required_fields = ['id', 'title']
            for field in required_fields:
                if field not in content_data:
                    self.send_error(400, f"Missing required field: {field}")
                    return
            
            # UPSERT into SQLite database - find database path
            db_paths = [
                Path('/app/data/ytv2_content.db'), # Render persistent disk mount 
                Path('./data/ytv2_content.db'),    # Local data subdirectory
                Path('/app/ytv2_content.db'),      # Root app directory
                Path('./ytv2_content.db')          # Current directory (fallback)
            ]
            
            db_path = None
            for path in db_paths:
                if path.exists():
                    db_path = path
                    break
                    
            if not db_path:
                # Create database in persistent disk location if possible
                for path in db_paths:
                    try:
                        path.parent.mkdir(parents=True, exist_ok=True)
                        create_empty_ytv2_database(path)
                        db_path = path
                        break
                    except:
                        continue
                        
            if not db_path:
                self.send_error(500, "Cannot create or find SQLite database")
                return
            
            import sqlite3
            conn = None
            try:
                conn = sqlite3.connect(str(db_path))
                cursor = conn.cursor()
                
                # Check if record exists first to determine action
                check_cursor = conn.cursor()
                check_cursor.execute("SELECT id FROM content WHERE id = ?", (content_data.get('id'),))
                existing_record = check_cursor.fetchone()
                action = "updated" if existing_record else "created"
                
                # UPSERT content record
                cursor.execute("""
                    INSERT INTO content (
                        id, title, canonical_url, thumbnail_url, published_at, indexed_at,
                        duration_seconds, word_count, has_audio, audio_duration_seconds,
                        has_transcript, transcript_chars, video_id, channel_name, channel_id,
                        view_count, like_count, comment_count, category, subcategory, subcategories_json, 
                        content_type, complexity_level, language, key_topics, named_entities, analysis,
                        format_source, processing_status, created_at, updated_at
                    ) VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                    )
                    ON CONFLICT(id) DO UPDATE SET
                        title = excluded.title,
                        canonical_url = excluded.canonical_url,
                        thumbnail_url = excluded.thumbnail_url,
                        published_at = excluded.published_at,
                        duration_seconds = excluded.duration_seconds,
                        word_count = excluded.word_count,
                        has_audio = excluded.has_audio,
                        audio_duration_seconds = excluded.audio_duration_seconds,
                        has_transcript = excluded.has_transcript,
                        transcript_chars = excluded.transcript_chars,
                        video_id = excluded.video_id,
                        channel_name = excluded.channel_name,
                        channel_id = excluded.channel_id,
                        view_count = excluded.view_count,
                        like_count = excluded.like_count,
                        comment_count = excluded.comment_count,
                        category = excluded.category,
                        subcategory = excluded.subcategory,
                        subcategories_json = excluded.subcategories_json,
                        content_type = excluded.content_type,
                        complexity_level = excluded.complexity_level,
                        language = excluded.language,
                        key_topics = excluded.key_topics,
                        named_entities = excluded.named_entities,
                        analysis = excluded.analysis,
                        format_source = excluded.format_source,
                        processing_status = excluded.processing_status,
                        updated_at = excluded.updated_at
                """, (
                    content_data.get('id'),
                    content_data.get('title'),
                    content_data.get('canonical_url', ''),
                    content_data.get('thumbnail_url', ''),
                    content_data.get('published_at', ''),
                    content_data.get('indexed_at', ''),
                    content_data.get('duration_seconds', 0),
                    content_data.get('word_count', 0),
                    content_data.get('has_audio', False),
                    content_data.get('audio_duration_seconds', 0),
                    content_data.get('has_transcript', False),
                    content_data.get('transcript_chars', 0),
                    content_data.get('video_id', ''),
                    content_data.get('channel_name', ''),
                    content_data.get('channel_id', ''),
                    content_data.get('view_count', 0),
                    content_data.get('like_count', 0),
                    content_data.get('comment_count', 0),
                    json.dumps(content_data.get('category', [])),
                    content_data.get('subcategory'),
                    content_data.get('subcategories_json'),
                    content_data.get('content_type', ''),
                    content_data.get('complexity_level', ''),
                    content_data.get('language', 'en'),
                    json.dumps(content_data.get('key_topics', [])),
                    json.dumps(content_data.get('named_entities', [])),
                    json.dumps(content_data.get('analysis', {})) if content_data.get('analysis') else None,
                    content_data.get('format_source', 'api'),
                    content_data.get('processing_status', 'complete'),
                    content_data.get('created_at', ''),
                    content_data.get('updated_at', '')
                ))
                
                # UPSERT summary if provided
                summary_text = content_data.get('summary_text', '')
                if summary_text:
                    cursor.execute("""
                        INSERT INTO content_summaries (content_id, summary_text, summary_type)
                        VALUES (?, ?, ?)
                        ON CONFLICT(content_id) DO UPDATE SET
                            summary_text = excluded.summary_text,
                            summary_type = excluded.summary_type
                    """, (
                        content_data.get('id'),
                        summary_text,
                        content_data.get('summary_type', 'audio')
                    ))
            
                conn.commit()
                
                logger.info(f"✅ Content upserted: {content_data.get('id')}")
                
                # Send success response
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'success': True,
                    'message': 'Content saved successfully',
                    'id': content_data.get('id'),
                    'action': action,
                    'upserted': True,
                    'synced_at': datetime.now().isoformat()
                }).encode())
                
            except Exception as e:
                logger.error(f"Content API error: {e}")
                self.send_error(500, f"Content API failed: {str(e)}")
            finally:
                # Always close the database connection
                if conn:
                    conn.close()
                    
        except Exception as e:
            logger.error(f"Content API outer error: {e}")
            self.send_error(500, f"Content API failed: {str(e)}")
    
    def handle_content_update_api(self):
        """Handle PUT /api/content/{id} - Update specific content fields"""
        try:
            # Check authentication
            sync_secret = os.getenv('SYNC_SECRET')
            if not sync_secret:
                self.send_error(500, "Sync not configured")
                return
            
            auth_header = self.headers.get('Authorization', '')
            if not auth_header.startswith('Bearer ') or auth_header[7:] != sync_secret:
                logger.warning(f"Content update rejected: Invalid auth from {self.client_address[0]}")
                self.send_error(401, "Unauthorized")
                return
            
            # Extract content ID from path
            content_id = self.path.split('/api/content/')[-1]
            if not content_id:
                self.send_error(400, "No content ID provided")
                return
            
            # Read JSON payload
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self.send_error(400, "No update data provided")
                return
            
            post_data = self.rfile.read(content_length)
            try:
                update_data = json.loads(post_data.decode('utf-8'))
            except json.JSONDecodeError as e:
                self.send_error(400, f"Invalid JSON: {e}")
                return
            
            # Update content in database
            if not content_index or not hasattr(content_index, 'db_path'):
                self.send_error(500, "SQLite database not available")
                return
            
            import sqlite3
            from datetime import datetime
            conn = sqlite3.connect(content_index.db_path)
            cursor = conn.cursor()
            
            # Build dynamic UPDATE query based on provided fields
            update_fields = []
            update_values = []
            
            updatable_fields = {
                'has_audio': 'has_audio',
                'audio_duration_seconds': 'audio_duration_seconds', 
                'title': 'title',
                'duration_seconds': 'duration_seconds',
                'word_count': 'word_count'
            }
            
            for field, column in updatable_fields.items():
                if field in update_data:
                    update_fields.append(f"{column} = ?")
                    update_values.append(update_data[field])
            
            if not update_fields:
                self.send_error(400, "No valid update fields provided")
                return
            
            # Add updated_at timestamp
            update_fields.append("updated_at = ?")
            update_values.append(datetime.now().isoformat())
            update_values.extend([content_id, content_id])
            
            cursor.execute(f"""
                UPDATE content 
                SET {', '.join(update_fields)}
                WHERE id = ? OR video_id = ?
            """, update_values)
            
            rows_affected = cursor.rowcount
            conn.commit()
            conn.close()
            
            if rows_affected > 0:
                logger.info(f"✅ Content updated: {content_id}")
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'success': True,
                    'message': 'Content updated successfully',
                    'id': content_id,
                    'rows_affected': rows_affected
                }).encode())
            else:
                self.send_error(404, f"Content not found: {content_id}")
            
        except Exception as e:
            logger.error(f"Content update error: {e}")
            self.send_error(500, f"Content update failed: {str(e)}")
    
    def handle_delete_request(self):
        """Handle DELETE requests for /api/delete/:id endpoint"""
        try:
            # Check authentication
            if not self._auth_ok():
                self.send_error(401, "Unauthorized")
                return
            
            # Extract report ID from URL path
            # Supports both /api/delete/:id and /api/delete?id=:id patterns
            if '/api/delete/' in self.path:
                # DELETE /api/delete/:id
                report_id = self.path.split('/api/delete/')[-1]
            else:
                # POST /api/delete or DELETE /api/delete?id=:id
                parsed_url = urlparse(self.path)
                query_params = parse_qs(parsed_url.query)
                
                if 'id' in query_params:
                    report_id = query_params['id'][0]
                else:
                    # Try reading from request body for POST requests
                    if self.command == 'POST':
                        content_length = int(self.headers.get('Content-Length', 0))
                        if content_length > 0:
                            post_data = self.rfile.read(content_length)
                            try:
                                request_data = json.loads(post_data.decode('utf-8'))
                                report_id = request_data.get('id', '')
                            except json.JSONDecodeError:
                                report_id = ''
                        else:
                            report_id = ''
                    else:
                        report_id = ''
            
            if not report_id:
                self.send_error(400, "Missing report ID")
                return
            
            # URL decode the report_id to handle special characters
            import urllib.parse
            report_id = urllib.parse.unquote(report_id)
            
            # Perform deletion
            result = self._delete_one(report_id)
            
            # Return response
            if result['success'] or len(result['deleted_files']) > 0:
                response_data = {
                    'status': 'success',
                    'message': f"Successfully processed delete request for '{report_id}'",
                    'deleted_files': len(result['deleted_files']),
                    'errors': result['errors'],
                    'idempotent': len(result['deleted_files']) == 0 and len(result['errors']) == 0
                }
                self.send_response(200)
                logger.info(f"✅ Delete successful for {report_id}: {len(result['deleted_files'])} files deleted")
            else:
                response_data = {
                    'status': 'error',
                    'message': f"Could not delete '{report_id}'",
                    'errors': result['errors']
                }
                self.send_response(404 if 'not found' in str(result['errors']).lower() else 500)
                logger.warning(f"❌ Delete failed for {report_id}: {result['errors']}")
            
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response_data, indent=2).encode())
            
        except Exception as e:
            logger.error(f"Error handling delete request: {e}")
            error_response = {
                'status': 'error',
                'message': 'Delete request failed',
                'error': str(e)
            }
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(error_response, indent=2).encode())

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
