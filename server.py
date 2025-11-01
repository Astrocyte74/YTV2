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
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
import threading
import queue
from socketserver import ThreadingMixIn
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, unquote, quote
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import socket
import mimetypes
import requests
from requests.exceptions import RequestException
from bs4 import BeautifulSoup
try:
    from google.oauth2 import id_token as google_id_token
    from google.auth.transport import requests as google_requests
    GOOGLE_AUTH_AVAILABLE = True
except Exception:
    GOOGLE_AUTH_AVAILABLE = False

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
# Legacy JSON report generator no longer used

# Use PostgreSQL backend
from modules.postgres_content_index import PostgreSQLContentIndex as ContentIndex
print("✅ Using PostgreSQL content index")

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

# --------------------------
# Auth and Rate Limiting
# --------------------------

ALLOWED_ORIGINS_ENV = os.getenv('ALLOWED_ORIGINS', '')
GOOGLE_CLIENT_IDS_ENV = os.getenv('GOOGLE_CLIENT_IDS', '')

def _parse_csv_env(value: str) -> list[str]:
    items = []
    for part in (value or '').split(','):
        v = part.strip()
        # Strip wrapping quotes if provided in env (Render UI sometimes encourages quotes)
        if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
            v = v[1:-1].strip()
        if v:
            # Normalize origin: drop trailing slash
            if v.endswith('/') and v.startswith('http'):
                v = v.rstrip('/')
            items.append(v)
    return items

ALLOWED_ORIGINS_CFG = _parse_csv_env(ALLOWED_ORIGINS_ENV)
GOOGLE_CLIENT_IDS = _parse_csv_env(GOOGLE_CLIENT_IDS_ENV)

RL_USER_PER_MIN = int(os.getenv('RL_USER_PER_MIN', '5'))
RL_IP_PER_MIN = int(os.getenv('RL_IP_PER_MIN', '10'))
RL_USER_PER_DAY = int(os.getenv('RL_USER_PER_DAY', '50'))
MAX_QUIZ_KB = int(os.getenv('MAX_QUIZ_KB', '128'))

_TOKEN_CACHE: dict[str, dict] = {}
_RL_IP_MIN: dict[str, list[float]] = {}
_RL_USER_MIN: dict[str, list[float]] = {}
_RL_USER_DAY: dict[str, list[float]] = {}

def _now() -> float:
    return time.time()

def _client_ip(handler: SimpleHTTPRequestHandler) -> str:
    xfwd = handler.headers.get('X-Forwarded-For', '')
    if xfwd:
        return xfwd.split(',')[0].strip()
    try:
        return handler.client_address[0]
    except Exception:
        return 'unknown'

def _prune(series: list[float], window_s: int) -> None:
    cutoff = _now() - window_s
    while series and series[0] < cutoff:
        series.pop(0)

def _rate_limit(series_map: dict[str, list[float]], key: str, limit: int, window_s: int) -> bool:
    arr = series_map.setdefault(key, [])
    _prune(arr, window_s)
    if len(arr) >= limit:
        return False
    arr.append(_now())
    return True

def check_ip_minute(handler: SimpleHTTPRequestHandler) -> bool:
    key = _client_ip(handler)
    return _rate_limit(_RL_IP_MIN, key, RL_IP_PER_MIN, 60)

def check_user_minute(user_id: str) -> bool:
    return _rate_limit(_RL_USER_MIN, user_id, RL_USER_PER_MIN, 60)

def check_user_daily(user_id: str) -> bool:
    return _rate_limit(_RL_USER_DAY, user_id, RL_USER_PER_DAY, 24 * 3600)

ALLOWED_ISS = {'https://accounts.google.com', 'accounts.google.com'}

def verify_google_bearer(auth_header: str) -> dict:
    if not GOOGLE_AUTH_AVAILABLE:
        raise PermissionError('Google auth library not available')
    if not auth_header or not auth_header.startswith('Bearer '):
        raise PermissionError('Missing bearer token')
    token = auth_header.split(' ', 1)[1].strip()

    cached = _TOKEN_CACHE.get(token)
    if cached and cached.get('exp', 0) > _now():
        return cached

    last_err = None
    for aud in GOOGLE_CLIENT_IDS or [None]:
        try:
            info = google_id_token.verify_oauth2_token(token, google_requests.Request(), audience=aud)
            iss = info.get('iss')
            if iss not in ALLOWED_ISS:
                raise PermissionError('Invalid issuer')
            # Compute cache expiry from token 'exp' or default short TTL
            exp_ts = float(info.get('exp', 0))
            user = {
                'user_id': info.get('sub'),
                'email': info.get('email'),
                'aud': info.get('aud'),
                'iss': iss,
                'exp': exp_ts or (_now() + 300)
            }
            if not user['user_id']:
                raise PermissionError('Invalid token payload')
            _TOKEN_CACHE[token] = user
            return user
        except Exception as e:
            last_err = e
            continue
    raise PermissionError('Invalid token')

class SSEClient:
    """Lightweight holder for per-connection event queues."""

    def __init__(self, handler: SimpleHTTPRequestHandler):
        self.handler = handler
        self.queue: "queue.Queue[str]" = queue.Queue(maxsize=64)
        self.alive = True

    def enqueue(self, message: str) -> None:
        """Attempt to queue a message, dropping the oldest on overflow."""
        if not self.alive:
            return
        try:
            self.queue.put_nowait(message)
        except queue.Full:
            try:
                _ = self.queue.get_nowait()
            except queue.Empty:
                pass
            try:
                self.queue.put_nowait(message)
            except queue.Full:
                # Give up if we still cannot enqueue
                logger.debug("SSE queue overflow; dropping event")


class ReportEventStream:
    """Simple server-sent events broadcaster shared across handlers."""

    def __init__(self) -> None:
        self._clients: set[SSEClient] = set()
        self._lock = threading.Lock()

    def register(self, handler: SimpleHTTPRequestHandler) -> SSEClient:
        client = SSEClient(handler)
        with self._lock:
            self._clients.add(client)
        logger.debug("SSE client registered; total=%s", len(self._clients))
        return client

    def unregister(self, client: SSEClient) -> None:
        client.alive = False
        with self._lock:
            self._clients.discard(client)
        logger.debug("SSE client unregistered; total=%s", len(self._clients))

    def broadcast(self, event_name: str, payload: Dict[str, Any]) -> int:
        if not event_name:
            return 0
        message = self._format_message(event_name, payload)
        stale: list[SSEClient] = []
        delivered = 0
        with self._lock:
            clients = list(self._clients)
        for client in clients:
            try:
                client.enqueue(message)
                delivered += 1
            except Exception:
                logger.exception("Failed to enqueue SSE message; marking client stale")
                stale.append(client)
        if stale:
            for client in stale:
                self.unregister(client)
        return delivered

    @staticmethod
    def _format_message(event_name: str, payload: Dict[str, Any]) -> str:
        try:
            data = json.dumps(payload or {}, ensure_ascii=False)
        except TypeError:
            logger.exception("Failed to serialize SSE payload for %s", event_name)
            data = "{}"
        return f"event: {event_name}\ndata: {data}\n\n"


report_event_stream = ReportEventStream()


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """HTTP server that handles each request in its own thread."""

    daemon_threads = True
    allow_reuse_address = True


# Limits and headers for article fetching endpoint
FETCH_ARTICLE_MAX_BYTES = 500_000
FETCH_ARTICLE_MAX_TEXT_CHARS = 100_000
FETCH_ARTICLE_HEADERS = {
    "User-Agent": "Quizzernator/1.0 (+https://quizzernator.app)"
}


def clip_article_text(text: str, limit: int):
    """Clip text to limit, preferring paragraph or sentence boundaries when possible."""
    if len(text) <= limit:
        return text, False

    candidate = text[:limit]

    # Prefer breaking at paragraph boundaries
    for separator in ("\n\n", "\n"):
        idx = candidate.rfind(separator)
        if idx >= int(limit * 0.6):
            return candidate[:idx].rstrip(), True

    # Next, look for the last sentence ending near the limit
    sentence_end = None
    for match in re.finditer(r"[.!?](?=[\"'\)\]]?\s)", candidate):
        sentence_end = match.end()
    if sentence_end and sentence_end >= int(limit * 0.6):
        return candidate[:sentence_end].rstrip(), True

    # Fallback to the last whitespace to avoid cutting in the middle of a word
    last_space = candidate.rfind(' ')
    if last_space >= int(limit * 0.6):
        return candidate[:last_space].rstrip(), True

    # Worst case: hard cut at the limit
    return candidate.rstrip(), True


def _normalize_heading(text: str) -> str:
    normalized = re.sub(r'[^a-z0-9]+', ' ', text.lower()).strip()
    return normalized


def build_paragraph_text(raw_text: str) -> str:
    lines = [line.strip() for line in raw_text.splitlines()]

    paragraphs = []
    current = []
    total_chars = 0
    for line in lines:
        if line:
            current.append(line)
            continue

        if not current:
            continue

        paragraph = ' '.join(current)
        normalized = _normalize_heading(paragraph)
        if normalized == 'references' and total_chars > 2000:
            break

        paragraphs.append(paragraph)
        total_chars += len(paragraph)
        current = []

    if current:
        paragraph = ' '.join(current)
        normalized = _normalize_heading(paragraph)
        if normalized != 'references' or total_chars > 2000:
            paragraphs.append(paragraph)

    return '\n\n'.join(paragraphs)


def fetch_wikipedia_article(parsed_url):
    path = parsed_url.path or ''
    if not path.startswith('/wiki/'):
        return None

    title_part = path[len('/wiki/'):]
    if not title_part:
        return None

    title = unquote(title_part)
    api_title = quote(title, safe='')

    subdomain = parsed_url.netloc.split('.')[0].lower()
    if subdomain in ('www', 'm'):
        lang = 'en'
    else:
        lang = subdomain

    api_url = f"https://{lang}.wikipedia.org/w/api.php"
    params = {
        "action": "query",
        "prop": "extracts",
        "explaintext": 1,
        "exsectionformat": "plain",
        "redirects": 1,
        "titles": title,
        "format": "json"
    }

    try:
        response = requests.get(
            api_url,
            params=params,
            headers={**FETCH_ARTICLE_HEADERS, "Accept": "application/json"},
            timeout=10
        )
    except RequestException as exc:
        logger.warning(f"Wikipedia API request failed: {exc}")
        return None

    if response.status_code != 200:
        logger.warning(
            "Wikipedia API returned %s for %s",
            response.status_code,
            api_url
        )
        return None

    try:
        data = response.json()
    except ValueError as exc:
        logger.warning(f"Failed to parse Wikipedia API response: {exc}")
        return None

    pages = data.get("query", {}).get("pages", {})
    if not pages:
        return None

    page = next(iter(pages.values()))
    extract = page.get("extract")
    if not extract:
        return None

    return extract, False

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

## Removed: SQLite bootstrap utilities (Postgres-only)

logger.info("🔍 Backend: PostgreSQL")
try:
    content_index = ContentIndex(postgres_url=os.getenv('DATABASE_URL_POSTGRES_NEW'))
    logger.info("📊 PostgreSQL ContentIndex initialized (singleton)")
except Exception as e:
    logger.error(f"❌ ContentIndex initialization failed: {e}")
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
        # Also filter out incomplete markers like **T, **Ta, etc.
        incomplete_marker_re = re.compile(r'^\s*\*\*[A-Za-z]*\s*$', re.IGNORECASE)

        bullets = []
        for line in lines:
            # Match lines starting with • - – — (bullet points, including Unicode dashes)
            if re.match(r'^(?:•|-|–|—)\s+', line):
                bullet_content = re.sub(r'^(?:•|-|–|—)\s+', '', line).strip()
                # Skip takeaway markers and incomplete markers
                if not takeaway_bullet_re.match(bullet_content) and not incomplete_marker_re.match(bullet_content):
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
            "summary_variants": report_data.get('summary_variants') or summary.get('variants') or [],
            "summary_variant_default": summary_type or report_data.get('summary_type_latest') or report_data.get('summary_variant') or 'comprehensive'
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
        elif path == '/health/backend':
            self.serve_health_backend()
        elif path == '/health/ingest':
            self.serve_health_ingest()
        elif path in ('/api/db-status', '/api/db-reset'):
            self.send_error(410, "Endpoint removed (SQLite diagnostics)")
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
        path = self.path.split('?', 1)[0]
        if path == "/api/telemetry":
            try:
                length = int(self.headers.get('Content-Length', 0))
                if length: _ = self.rfile.read(length)  # drain body
            except Exception:
                pass
            self.send_response(204)
            self.end_headers()
            return
        elif self.path == '/delete-reports':
            self.handle_delete_reports()
        elif self.path == '/api/upload-audio':
            self.handle_upload_audio()
        elif self.path == '/api/upload-image':
            self.handle_upload_image()
        elif self.path in ('/api/upload-report', '/api/upload-database', '/api/download-database'):
            # Legacy endpoints removed in Postgres-only mode
            self.send_error(410, "Endpoint removed")
        elif self.path == '/api/content' or self.path.startswith('/api/content/'):
            # Legacy SQLite content endpoints removed
            self.send_error(410, "Endpoint removed (use /ingest/* with PostgreSQL)")
        elif self.path.startswith('/api/delete'):
            self.handle_delete_request()
        # New ingest endpoints for NAS sync (T-Y020C)
        elif self.path == '/ingest/report':
            self.handle_ingest_report()
        elif self.path == '/ingest/audio':
            self.handle_ingest_audio()
        elif self.path.startswith('/api/debug/content'):
            self.handle_debug_content()
        elif self.path == '/api/fetch-article':
            self.handle_fetch_article()
        elif self.path == '/api/generate-quiz':
            # Per-IP rate limit for public generation
            if not check_ip_minute(self):
                self.send_response(429)
                self.set_cors_headers()
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": "Rate limit exceeded"}).encode())
                return
            self.handle_generate_quiz()
        elif self.path == '/api/save-quiz':
            self.handle_save_quiz()
        elif self.path == '/api/categorize-quiz':
            if not check_ip_minute(self):
                self.send_response(429)
                self.set_cors_headers()
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"success": False, "error": "Rate limit exceeded"}).encode())
                return
            self.handle_categorize_quiz()
        elif self.path == '/api/my/save-quiz':
            self.handle_my_save_quiz()
        else:
            self.send_error(404, "Endpoint not found")
    
    def do_DELETE(self):
        """Handle DELETE requests for the new delete API endpoint"""
        if self.path.startswith('/api/delete/'):
            self.handle_delete_request()
        elif self.path.startswith('/api/quiz/'):
            self.handle_delete_quiz()
        elif self.path.startswith('/api/my/quiz/'):
            self.handle_my_delete_quiz()
        else:
            self.send_error(404, "DELETE endpoint not found")
    
    def serve_dashboard(self):
        """Serve the modern dashboard using templates"""
        try:
            # Use SQLite data when available (for proper category structure)
            reports_data = []
            
            if content_index:
                # Get reports from database (PostgreSQL or SQLite)
                try:
                    db_results = content_index.search_reports(
                        filters=None,
                        query=None,
                        sort='indexed_at',  # Sort by most recent
                        page=1,
                        size=100  # Get first 100 reports
                    )

                    # Handle both PostgreSQL tuple format and SQLite dict format
                    if isinstance(db_results, tuple):
                        # PostgreSQL format: (items, total_count)
                        items, total_count = db_results
                        reports_list = items
                    else:
                        # SQLite format: dict with 'reports' key
                        reports_list = db_results.get('reports', [])

                    # Convert database data to format expected by dashboard_v3.js
                    for item in reports_list:
                        # Handle datetime conversion for PostgreSQL
                        indexed_at = item.get('indexed_at', '')
                        if hasattr(indexed_at, 'isoformat'):  # datetime object
                            indexed_at_str = indexed_at.isoformat()
                        else:
                            indexed_at_str = str(indexed_at) if indexed_at else ''

                        # The dashboard_v3.js expects this structure
                        report_data = {
                            'file_stem': item.get('file_stem', item.get('id', item.get('video_id', ''))),
                            'title': item.get('title', 'Unknown Title'),
                            'channel': item.get('channel_name', item.get('channel', 'Unknown Channel')),
                            'thumbnail_url': item.get('thumbnail_url', ''),
                            'duration_seconds': item.get('duration_seconds', 0),
                            'video_id': item.get('video_id', ''),
                            'analysis': item.get('analysis', item.get('analysis_json', {})),  # Categories structure
                            'media': item.get('media', {}),
                            'media_metadata': item.get('media_metadata', {}),
                            'created_date': indexed_at_str[:10] if indexed_at_str else '',
                            'created_time': indexed_at_str[11:16] if len(indexed_at_str) > 16 else ''
                        }
                        reports_data.append(report_data)

                    backend_type = "PostgreSQL"
                    logger.info(f"✅ Dashboard using {backend_type} data: {len(reports_data)} reports")

                except Exception as e:
                    backend_type = "PostgreSQL"
                    logger.error(f"❌ {backend_type} dashboard data failed: {e}")
                    # Fall back to file-based approach
                    reports_data = []
            
            # Fallback to file-based approach if database unavailable or failed
            if not reports_data:
                logger.info("🔄 Dashboard falling back to file-based data (no database available)")
                # Get report files from multiple directories (JSON preferred, HTML legacy)
                report_dirs = [
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
                nas_config = {
                    "base_url": os.getenv('NGROK_BASE_URL') or os.getenv('NGROK_URL') or '',
                    "basic_user": os.getenv('NGROK_BASIC_USER', ''),
                    "basic_pass": os.getenv('NGROK_BASIC_PASS', ''),
                }

                # Replace template placeholders (safe replacement for templates with {})
                dashboard_html = template_content.replace(
                    '{reports_data}', json.dumps(reports_data, ensure_ascii=False)
                ).replace(
                    '{nas_config}', json.dumps(nas_config)
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
            # Strip query string (e.g., dashboard.css?v=123)
            if '?' in filename:
                filename = filename.split('?', 1)[0]
            if '#' in filename:
                filename = filename.split('#', 1)[0]
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
            
            # Legacy JSON file fallback removed (Postgres-only mode)
                
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
                    # Get the context and format the summary_text for proper display
                    ctx = self.to_report_v2_dict(transformed_data, audio_url)
                    # Format the raw summary_text instead of using pre-formatted HTML
                    raw_summary = report_data.get('summary_text', '')
                    if raw_summary and not raw_summary.startswith('<'):
                        ctx['summary_html'] = ModernDashboardHTTPRequestHandler.format_key_points(raw_summary)
                    else:
                        ctx['summary_html'] = report_data.get('summary_html', '')
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
                "has_audio": report_data.get('has_audio', False),
                "summary_type": report_data.get('summary_type_latest', 'unknown')
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
                # CRITICAL: Also check the audio subdirectory where PostgreSQL uploads are stored
                if Path('/app/data/exports/audio').exists():
                    search_dirs.append(Path('/app/data/exports/audio'))
                
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
                    # Generate correct URL based on file location
                    if '/app/data/exports/audio' in str(latest):
                        audio_url = f"/exports/audio/{latest.name}"
                    else:
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
        """Serve files from /exports/ route (audio/images/etc.).

        Backed by /app/data/exports. Supports nested paths like /exports/audio/ and
        direct files under /exports/*. Sets Content-Type via mimetypes.
        """
        try:
            from pathlib import Path

            # e.g. self.path == "/exports/audio/s_cD7g74kFE.mp3" or "/exports/s_cD7g74kFE.mp3"
            if not self.path.startswith('/exports/'):
                self.send_error(404, "Not found")
                return

            root = Path("/app/data/exports").resolve()

            # strip leading prefix and build filesystem path
            rel = self.path[len("/exports/"):].lstrip("/")  # "audio/s_cD7g74kFE.mp3" or "s_cD7g74kFE.mp3"
            fs_path = (root / rel).resolve()

            # path traversal guard
            if not str(fs_path).startswith(str(root)):
                logger.warning(f"🚫 Path traversal attempt blocked: {self.path}")
                self.send_error(403, "Forbidden")
                return

            # If the direct path is missing, try the persistent audio/ subdir for legacy mp3 paths
            if not fs_path.is_file():
                rel_norm = rel.replace("\\", "/").lstrip("/")
                # Legacy flat path: /exports/<id>.mp3 → /app/data/exports/audio/<id>.mp3
                if "/" not in rel_norm:
                    alt = (root / "audio" / rel_norm).resolve()
                    if str(alt).startswith(str(root)) and alt.is_file():
                        fs_path = alt
                        logger.info(f"🎧 Fallback found: {fs_path}")

                # Also try yt:-prefixed leftover for older uploads
                if not fs_path.is_file():
                    alt2 = (root / "audio" / f"yt:{rel_norm}").resolve()
                    if str(alt2).startswith(str(root)) and alt2.is_file():
                        fs_path = alt2
                        logger.info(f"🎧 Legacy yt: fallback found: {fs_path}")

            if fs_path.is_file():
                # Guess Content-Type (default octet-stream)
                ctype, _ = mimetypes.guess_type(str(fs_path))
                ctype = ctype or 'application/octet-stream'
                logger.info(f"📦 Serving export: {fs_path} ({ctype})")
                self.send_response(200)
                self.send_header('Content-type', ctype)
                self.send_header('Content-Length', str(fs_path.stat().st_size))
                self.send_header('Cache-Control', 'public, max-age=3600')  # Cache for 1 hour
                self.end_headers()
                with open(fs_path, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                logger.info(f"📦 MISS export: {rel} (full path: {fs_path})")
                self.send_error(404, f"Export not found: {rel}")

        except Exception as e:
            logger.error(f"Error serving export {self.path}: {e}")
            self.send_error(500, "Error serving export")

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
            # Sanitized form used by /ingest/audio file naming
            clean_id = video_id.replace('yt:', '').replace(':', '')

            # Search for candidate files in common locations
            search_dirs = [Path('/app/data/exports')]
            audio_subdir = Path('/app/data/exports/audio')
            if audio_subdir.exists():
                search_dirs.append(audio_subdir)
            patterns = [
                f'{clean_id}.mp3',           # exact sanitized filename saved by /ingest/audio
                f'audio_{video_id}_*.mp3',   # standard new pattern
                f'{video_id}_*.mp3',         # legacy pattern
                f'*{video_id}*.mp3',         # fallback containing original id
                f'*{clean_id}*.mp3',         # fallback containing sanitized id
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
            
            # Count reports from PostgreSQL
            try:
                total_reports = content_index.get_report_count() if content_index else 0
            except Exception:
                total_reports = 0
            
            status_data = {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "services": {
                    "dashboard": "running",
                    "telegram_bot": "configured" if telegram_configured and users_configured else "not_configured"
                },
                "reports": {
                    "total_reports": total_reports
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


    def serve_health_backend(self):
        """Serve backend health endpoint - prevents wrong-URL/wrong-backend debugging rabbit holes"""
        try:
            # Get backend information
            backend_info = {
                "backend": type(content_index).__name__ if content_index else "None",
                "dsn_set": bool(os.getenv("DATABASE_URL_POSTGRES_NEW")),
                "psycopg2_available": PSYCOPG2_AVAILABLE,
                "timestamp": datetime.now().isoformat()
            }

            # Add record counts if content_index is available
            if content_index:
                try:
                    # Try to get a quick count
                    if hasattr(content_index, 'search_reports'):
                        search_result = content_index.search_reports(page=1, size=1)
                        if isinstance(search_result, tuple):
                            # PostgreSQL format: (items, total_count)
                            _, total_count = search_result
                            backend_info["record_count"] = total_count
                        else:
                            # SQLite format: dict with pagination
                            backend_info["record_count"] = search_result.get('pagination', {}).get('total_count', 0)
                except Exception as e:
                    backend_info["record_count_error"] = str(e)

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            self.wfile.write(json.dumps(backend_info, indent=2).encode())

        except Exception as e:
            logger.error(f"Error serving backend health check: {e}")
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            error_data = {
                "error": "Backend health check failed",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }
            self.wfile.write(json.dumps(error_data).encode())

    def serve_health_ingest(self):
        """Serve ingest health endpoint for testing curl locally."""
        try:
            ingest_health = {
                "status": "ok",
                "auth_required": True,
                "token_set": bool(os.getenv("INGEST_TOKEN")),
                "pg_dsn_set": bool(os.getenv("DATABASE_URL_POSTGRES_NEW")),
                "timestamp": datetime.now().isoformat()
            }

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(ingest_health).encode())

        except Exception as e:
            logger.error(f"Error serving ingest health check: {e}")
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            error_data = {
                "error": "Ingest health check failed",
                "message": str(e),
                "timestamp": datetime.now().isoformat()
            }
            self.wfile.write(json.dumps(error_data).encode())

    def serve_health_db(self):
        """Serve database health endpoint with latency timing"""
        start_time = time.time()

        try:
            # Test database connectivity and performance
            db_health = {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "database_type": None,
                "latency_ms": None,
                "record_count": None,
                "connection_test": "passed"
            }

            if content_index:
                # Test actual database query performance
                query_start = time.time()

                if hasattr(content_index, 'search_reports'):
                    # Test with a small query
                    result = content_index.search_reports(page=1, size=1)

                    if isinstance(result, tuple):
                        # PostgreSQL format
                        items, total_count = result
                        db_health["database_type"] = "postgresql"
                        db_health["record_count"] = total_count
                    else:
                        # SQLite format
                        db_health["database_type"] = "sqlite"
                        db_health["record_count"] = result.get('pagination', {}).get('total_count', 0)

                query_end = time.time()
                db_health["latency_ms"] = round((query_end - query_start) * 1000, 2)

                # Health check passes if latency is reasonable
                if db_health["latency_ms"] > 1000:  # 1 second threshold
                    db_health["status"] = "degraded"
                    db_health["warning"] = "High latency detected"

            else:
                db_health["status"] = "error"
                db_health["error"] = "No database connection available"

            total_time = time.time() - start_time
            db_health["total_response_time_ms"] = round(total_time * 1000, 2)

            # Send response with appropriate status code
            status_code = 200 if db_health["status"] in ["healthy", "degraded"] else 503

            self.send_response(status_code)
            self.send_header('Content-type', 'application/json')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            self.wfile.write(json.dumps(db_health, indent=2).encode())

        except Exception as e:
            total_time = time.time() - start_time
            error_response = {
                "status": "error",
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "total_response_time_ms": round(total_time * 1000, 2)
            }

            self.send_response(503)
            self.send_header('Content-type', 'application/json')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            self.wfile.write(json.dumps(error_response, indent=2).encode())

    # Removed SQLite diagnostics endpoints (db-status, db-reset) in Postgres-only mode
    
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
            elif path == '/api/health':
                self.serve_api_health()
            elif path == '/api/health/auth':
                self.serve_api_health_auth()
            elif path == '/api/config':
                self.serve_api_config()
            elif path == '/api/refresh':
                self.serve_api_refresh()
            elif path == '/api/backup':
                self.send_error(410, "Endpoint removed")
            elif path == '/api/report-events':
                self.serve_api_report_events()
            elif path == '/api/metrics':
                self.serve_api_metrics()
            elif path.startswith('/api/backup/'):
                self.send_error(410, "Endpoint removed")
            elif path == '/api/download-database':
                self.send_error(410, "Endpoint removed")
            elif path == '/api/list-quizzes':
                self.handle_list_quizzes()
            elif path.startswith('/api/quiz/'):
                self.handle_get_quiz()
            elif path == '/api/my/list-quizzes':
                self.handle_my_list_quizzes()
            elif path.startswith('/api/my/quiz/'):
                self.handle_my_get_quiz()
            else:
                self.send_error(404, "API endpoint not found")
        except Exception as e:
            logger.error(f"Error serving API {self.path}: {e}")
            self.send_error(500, "API error")

    def serve_api_report_events(self):
        """Stream report ingest events to the frontend via Server-Sent Events."""
        self.send_response(200)
        self.send_header('Content-type', 'text/event-stream')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'keep-alive')
        self.send_header('X-Accel-Buffering', 'no')
        self.end_headers()

        client = report_event_stream.register(self)
        self.close_connection = False

        try:
            try:
                self.wfile.write(b": connected\n\n")
                self.wfile.flush()
            except Exception:
                logger.debug("Failed to send SSE handshake; closing connection")
                return

            while True:
                try:
                    message = client.queue.get(timeout=15)
                except queue.Empty:
                    try:
                        self.wfile.write(b": keep-alive\n\n")
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
                        break
                    continue

                try:
                    self.wfile.write(message.encode('utf-8'))
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
                    break
        finally:
            report_event_stream.unregister(client)
            self.close_connection = True

    def serve_api_metrics(self):
        """Proxy NAS metrics to avoid browser CORS issues."""
        try:
            base_url = os.getenv('NGROK_BASE_URL') or os.getenv('NGROK_URL') or ''
            if not base_url:
                # No NAS configured; hide metrics panel
                self.send_response(404)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "nas not configured"}).encode())
                return

            # Compose target URL
            target = base_url.rstrip('/') + '/api/metrics'

            headers = {
                'ngrok-skip-browser-warning': 'true'
            }
            user = os.getenv('NGROK_BASIC_USER', '')
            pwd = os.getenv('NGROK_BASIC_PASS', '')

            auth = (user, pwd) if (user or pwd) else None

            try:
                resp = requests.get(target, headers=headers, auth=auth, timeout=5)
            except RequestException as e:
                logger.warning(f"Metrics proxy request failed: {e}")
                self.send_response(502)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "metrics upstream unavailable"}).encode())
                return

            # Forward JSON payload
            self.send_response(resp.status_code)
            self.send_header('Content-type', 'application/json')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            try:
                data = resp.json()
                self.wfile.write(json.dumps(data).encode())
            except ValueError:
                self.wfile.write(resp.content)
        except Exception as e:
            logger.error(f"Error proxying metrics: {e}")
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "metrics proxy error", "message": str(e)}).encode())

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
            logger.exception("Error serving filters API")  # logs stacktrace
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
                # Backend not available
                self.send_error(503, "Content index not available")
                return

            latest_only = query_params.get('latest', ['false'])[0].lower() == 'true'
            if latest_only:
                latest_report = None
                if hasattr(content_index, 'get_latest_report_metadata'):
                    try:
                        latest_report = content_index.get_latest_report_metadata()
                    except Exception:
                        logger.exception("Failed to fetch latest report metadata")
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Cache-Control', 'no-cache')
                self.end_headers()
                self.wfile.write(json.dumps({'report': latest_report}, ensure_ascii=False).encode())
                return

            # Parse query parameters
            filters = {}
            
            # Filter parameters with validation (CRITICAL: include subcategory and parentCategory per OpenAI recommendation)
            for param in ['source', 'language', 'category', 'subcategory', 'parentCategory', 'channel', 'content_type', 'complexity', 'summary_type']:
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
            
            # Execute search - unpack tuple returned by PostgreSQL
            search_result = content_index.search_reports(
                filters=filters if filters else None,
                query=query if query else None,
                sort=sort,
                page=page,
                size=size
            )

            # Handle both tuple (PostgreSQL) and dict (SQLite) return formats
            if isinstance(search_result, tuple):
                # PostgreSQL format: (items, total_count)
                items, total_count = search_result
                import math

                # Convert datetime objects to strings for JSON serialization
                serializable_items = []
                for item in items:
                    serializable_item = {}
                    for key, value in item.items():
                        if hasattr(value, 'isoformat'):  # datetime object
                            serializable_item[key] = value.isoformat()
                        else:
                            serializable_item[key] = value

                    # Add summary_type field from summary_type_latest (memo requirement)
                    serializable_item["summary_type"] = item.get("summary_type_latest") or "unknown"

                    serializable_items.append(serializable_item)

                total_pages = math.ceil(total_count / size) if size else 0
                results = {
                    "reports": serializable_items,
                    "pagination": {
                        "page": page,
                        "size": size,
                        "total": total_count,
                        "total_count": total_count,
                        "pages": total_pages,
                        "total_pages": total_pages,
                        "has_next": page * size < total_count,
                        "has_prev": page > 1,
                    },
                    "sort": sort,
                    "filters": filters,
                    # Top-level pagination fields for UI compatibility
                    "total_count": int(total_count or 0),
                    "page": int(page or 1),
                    "total_pages": int(total_pages or 0),
                }
            else:
                # SQLite format: already a dict
                results = search_result

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
            # Legacy endpoint removed in Postgres-only mode
            self.send_error(410, "Endpoint removed")
            
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
            
            # Legacy JSON file fallback removed in Postgres-only mode
            
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
                    "exports": str((Path('/app/data/exports') if Path('/app/data').exists() else Path('./exports')).absolute())
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
        # PostgreSQL path: nothing to refresh server-side; return success so UI doesn't error
        result = {
            "status": "success",
            "message": "no-op (postgres)",
            "timestamp": datetime.now().isoformat()
        }

        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        self.wfile.write(json.dumps(result, indent=2).encode())
    
    def serve_api_backup(self):
        self.send_error(410, "Endpoint removed")
    
    def serve_backup_file(self):
        self.send_error(410, "Endpoint removed")
    
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
            
            # Delete files from possible locations (HTML legacy only)
            search_dirs = [
                Path('./exports'),       # HTML reports
                Path('.')               # Legacy location
            ]
            
            for filename in filenames:
                deleted = False
                video_id_for_audio = None
                for search_dir in search_dirs:
                    if search_dir.exists():
                        # Try different extensions (JSON removed)
                        for ext in ['.html', '']:
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
    
        self.send_error(410, "Endpoint removed (legacy JSON upload)")
        return
    
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
            Path('./exports'),       # HTML reports (legacy)
            Path('.')               # Current directory (legacy)
        ]
        
        video_id_for_audio = None
        
        # Delete report files
        for search_dir in search_dirs:
            if not search_dir.exists():
                continue
                
            for ext in ['.html']:
                file_path = search_dir / f"{report_id}{ext}"
                if file_path.exists():
                    try:
                        # JSON-based deletion removed (Postgres-only mode)
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
        
        # (SQLite deletion removed in Postgres-only mode)

        # Delete from PostgreSQL database if using PostgreSQL backend
        video_id = (report_id or "").replace("yt:", "").strip()

        if content_index and hasattr(content_index, "delete_content"):
            try:
                result = content_index.delete_content(video_id)
                if result.get("success"):
                    deleted_files.append(
                        f"PostgreSQL: {result['content_deleted']} content, {result['summaries_deleted']} summaries"
                    )

                    # Clean up MP3 files if present
                    audio_root = Path("/app/data/exports/audio")
                    for name in (f"{video_id}.mp3", f"yt:{video_id}.mp3"):
                        p = audio_root / name
                        if p.is_file():
                            try:
                                p.unlink()
                                deleted_files.append(f"Audio: {name}")
                            except Exception as e:
                                logger.warning(f"Could not remove {p}: {e}")

                else:
                    errors.append(f"PostgreSQL deletion failed: {result.get('error','Unknown')}")
            except Exception as e:
                errors.append(f"Failed to delete in PostgreSQL: {e}")

        return {
            'report_id': report_id,
            'deleted_files': deleted_files,
            'errors': errors,
            'found_video_id': video_id_for_audio,
            'success': len(deleted_files) > 0 or len(errors) == 0  # Success if we deleted something OR no errors (idempotent)
        }
    
    def handle_upload_database(self):
        """Removed: legacy SQLite upload."""
        self.send_error(410, "Endpoint removed (legacy SQLite upload)")
        return
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
            # Postgres-only: no SQLite reinitialization in this build
            
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
        """Removed: legacy SQLite download."""
        self.send_error(410, "Endpoint removed (legacy SQLite download)")
        return
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
        """Upload audio files from NAS (legacy compatibility)."""
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
            exports_root = Path('/app/data/exports') if Path('/app/data').exists() else Path('./exports')
            audio_dir = exports_root / 'audio'
            audio_dir.mkdir(parents=True, exist_ok=True)

            audio_path = audio_dir / audio_field.filename
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

    def handle_upload_image(self):
        """Upload summary images from NAS with the same auth as audio uploads.

        Expects multipart/form-data with field name 'image'. Saves to
        /app/data/exports/images/<filename> (or ./exports/images in local dev) and
        returns JSON with a public_url under /exports/images/...
        """
        try:
            # Check sync secret for authentication (same as audio)
            sync_secret = os.getenv('SYNC_SECRET')
            if not sync_secret:
                self.send_error(500, "Sync not configured")
                return

            auth_header = self.headers.get('Authorization', '')
            if not auth_header.startswith('Bearer ') or auth_header[7:] != sync_secret:
                logger.warning(f"Image upload rejected: Invalid auth from {self.client_address[0]}")
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
            if content_length > 10 * 1024 * 1024:  # 10MB limit for images
                self.send_error(413, "Image file too large")
                return

            post_data = self.rfile.read(content_length)

            # Parse form data
            import cgi
            import io
            from os.path import basename

            form_data = cgi.FieldStorage(
                fp=io.BytesIO(post_data),
                headers=self.headers,
                environ={'REQUEST_METHOD': 'POST'}
            )

            if 'image' not in form_data:
                self.send_error(400, "No image file provided")
                return

            img_field = form_data['image']
            if not getattr(img_field, 'filename', None):
                self.send_error(400, "No image filename provided")
                return

            # Save image file
            exports_root = Path('/app/data/exports') if Path('/app/data').exists() else Path('./exports')
            images_dir = exports_root / 'images'
            images_dir.mkdir(parents=True, exist_ok=True)

            filename = basename(img_field.filename)
            img_path = images_dir / filename
            with open(img_path, 'wb') as f:
                img_field.file.seek(0)
                f.write(img_field.file.read())

            public_url = f"/exports/images/{filename}"
            logger.info(f"🖼️ Image file uploaded: {filename} -> {public_url}")

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                'success': True,
                'message': 'Image uploaded successfully',
                'filename': filename,
                'size': img_path.stat().st_size,
                'public_url': public_url
            }).encode())

        except Exception as e:
            logger.error(f"Image upload error: {e}")
            self.send_error(500, f"Image upload failed: {str(e)}")
    
    def handle_content_api(self):
        """Removed: legacy SQLite content API (use /ingest/report)."""
        self.send_error(410, "Endpoint removed (legacy content API)")
        return
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
        """Removed: legacy SQLite content update API."""
        self.send_error(410, "Endpoint removed (legacy content update)")
        return
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

    # ------------------------------------------------------------------
    # Ingest endpoints for NAS sync (T-Y020C)
    # ------------------------------------------------------------------

    def _verify_ingest(self) -> bool:
        """Verify ingest token authentication."""
        token = os.getenv("INGEST_TOKEN", "")
        if not token:
            return False
        return self.headers.get("X-INGEST-TOKEN") == token

    def handle_ingest_report(self):
        """Handle POST /ingest/report - Content upsert from NAS."""
        try:
            # Authentication
            if not self._verify_ingest():
                self.send_response(401)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "unauthorized"}).encode())
                return

            # Read JSON payload
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "no data received"}).encode())
                return

            post_data = self.rfile.read(content_length)
            try:
                payload = json.loads(post_data.decode('utf-8'))
            except json.JSONDecodeError as e:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": f"invalid JSON: {str(e)}"}).encode())
                return

            # Validate required fields
            video_id = payload.get("video_id")
            if not video_id:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "video_id required"}).encode())
                return

            # Normalize JSON fields if they came as strings
            def as_json(v):
                if v is None:
                    return None
                if isinstance(v, (dict, list)):
                    return v
                try:
                    return json.loads(v)
                except:
                    return None

            payload["subcategories_json"] = as_json(payload.get("subcategories_json"))
            payload["analysis_json"] = as_json(payload.get("analysis_json"))
            payload["topics_json"] = as_json(payload.get("topics_json"))

            # Use PostgreSQL content index for upserts
            if content_index and hasattr(content_index, 'upsert_content'):
                verify_row = None  # Initialize here for proper scope
                try:
                    upserted = content_index.upsert_content(payload)

                    # Read-back verification for response
                    try:
                        if video_id and hasattr(content_index, 'get_by_video_id'):
                            row = content_index.get_by_video_id(video_id)
                            if row:
                                verify_row = {"video_id": row.get("video_id"), "title": row.get("title")}
                    except Exception:
                        logger.exception("Verify read failed for %s", video_id)

                except Exception as upsert_error:
                    # TEMP: Expose the real error for debugging
                    self.send_response(500)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    error_response = {
                        "error": "upsert_failed",
                        "exception": str(upsert_error),
                        "payload_keys": list(payload.keys()),
                        "video_id": payload.get("video_id"),
                        "debug": True
                    }
                    self.wfile.write(json.dumps(error_response).encode())
                    return

                # Check if upsert actually worked
                if not upserted:
                    # TEMP: Show what we tried to upsert when it fails silently
                    self.send_response(500)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    debug_response = {
                        "error": "upsert_returned_false",
                        "payload_sample": {
                            "video_id": payload.get("video_id"),
                            "title": payload.get("title"),
                            "channel_name": payload.get("channel_name"),
                            "has_keys": list(payload.keys())[:10]  # First 10 keys
                        },
                        "debug": True
                    }
                    self.wfile.write(json.dumps(debug_response).encode())
                    return

                # Handle summary variants if present
                summaries = payload.get("summary_variants") or []
                summaries_upserted = 0
                if summaries and hasattr(content_index, 'upsert_summaries'):
                    summaries_upserted = content_index.upsert_summaries(video_id, summaries)

                # Prepare realtime event broadcast before responding
                summary_types: List[str] = []
                for summary in summaries or []:
                    if isinstance(summary, dict):
                        st = summary.get('summary_type') or summary.get('summaryType') or summary.get('variant')
                        if st:
                            summary_types.append(str(st))
                for key in ('summary_type', 'summary_type_latest'):
                    st_val = payload.get(key)
                    if st_val:
                        summary_types.append(str(st_val))
                # Deduplicate while preserving order
                seen = set()
                summary_types = [s for s in summary_types if not (s in seen or seen.add(s))]

                event_payload = {
                    "video_id": video_id,
                    "summary_types": summary_types,
                    "timestamp": payload.get("indexed_at") or datetime.utcnow().isoformat() + "Z"
                }
                try:
                    listeners = report_event_stream.broadcast('report-added', event_payload)
                    logger.debug("Broadcast report-added for %s to %s listeners", video_id, listeners)
                except Exception:
                    logger.exception("Failed to broadcast ingest event for %s", video_id)

                # Success response
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                response = {
                    "upserted": int(bool(upserted)),
                    "summaries_upserted": summaries_upserted,
                    "verify_row": verify_row  # TEMP: remove once stable
                }
                self.wfile.write(json.dumps(response).encode())
            else:
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "content index not available"}).encode())

        except Exception as e:
            logger.error(f"Error in ingest_report: {e}")
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": f"internal error: {str(e)}"}).encode())

    def handle_debug_content(self):
        """Handle GET /api/debug/content?video_id=X - Direct video lookup for debugging."""
        try:
            # Parse query parameters
            import urllib.parse
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            video_id = (qs.get('video_id') or [None])[0]

            if not video_id:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "video_id required"}).encode())
                return

            # Get content index and look up the record
            content_index = getattr(self.server, 'content_index', None)
            if not content_index or not hasattr(content_index, 'get_by_video_id'):
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "content index not available"}).encode())
                return

            row = content_index.get_by_video_id(video_id)

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"row": row}).encode())

        except Exception as e:
            logger.error(f"Error in debug_content: {e}")
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": f"internal error: {str(e)}"}).encode())

    def handle_ingest_audio(self):
        """Handle POST /ingest/audio - Audio file upload from NAS."""
        try:
            # Authentication
            if not self._verify_ingest():
                self.send_response(401)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "unauthorized"}).encode())
                return

            # Parse multipart form data
            content_type = self.headers.get('Content-Type', '')
            if not content_type.startswith('multipart/form-data'):
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "expected multipart/form-data"}).encode())
                return

            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "no data received"}).encode())
                return

            # Read multipart data
            post_data = self.rfile.read(content_length)

            # Parse multipart form - simplified parsing
            import email
            from email.message import EmailMessage

            # Create email message for parsing
            msg = EmailMessage()
            msg['content-type'] = content_type
            msg.set_payload(post_data)

            # Extract form fields and files
            import cgi
            import io

            # Use cgi.FieldStorage for multipart parsing
            environ = {
                'REQUEST_METHOD': 'POST',
                'CONTENT_TYPE': content_type,
                'CONTENT_LENGTH': str(content_length)
            }

            fs = cgi.FieldStorage(
                fp=io.BytesIO(post_data),
                environ=environ,
                keep_blank_values=True
            )

            # Extract video_id and audio file with explicit checks to avoid boolean conversion errors
            video_id = None
            audio_file = None

            for field in fs.list:
                if field.name == 'video_id':
                    video_id = field.value
                elif field.name == 'audio':
                    # Explicit checks to avoid "Cannot be converted to bool" error with Werkzeug 3+
                    if field.filename is not None and field.filename != "":
                        audio_file = field

            # Explicit None checks instead of truthiness to avoid FileStorage boolean conversion
            if video_id is None or audio_file is None:
                self.send_response(400)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "video_id and audio required"}).encode())
                return

            # Keep the original video_id for database updates, but sanitize only for filename
            original_video_id = video_id.strip()
            clean_video_id = original_video_id.replace("yt:", "").replace(":", "")

            # Ensure audio directory exists
            from pathlib import Path
            audio_dir = Path("/app/data/exports/audio")
            audio_dir.mkdir(parents=True, exist_ok=True)

            # Save audio file with clean filename
            dest = audio_dir / f"{clean_video_id}.mp3"
            with open(dest, 'wb') as f:
                f.write(audio_file.file.read())

            # Update content.media.audio_url in PostgreSQL using the original video_id
            audio_url = f"/exports/audio/{clean_video_id}.mp3"
            if content_index and hasattr(content_index, 'update_media_audio_url'):
                logger.info(f"🔄 Updating has_audio flag for {original_video_id}")
                content_index.update_media_audio_url(original_video_id, audio_url)
                logger.info(f"✅ Updated has_audio flag for {original_video_id}")
            else:
                logger.error(f"❌ No content_index or no update_media_audio_url method available")

            # Success response
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {
                "saved": True,
                "public_url": audio_url
            }
            self.wfile.write(json.dumps(response).encode())

        except Exception as e:
            logger.error(f"Error in ingest_audio: {e}")
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": f"internal error: {str(e)}"}).encode())

    def set_cors_headers(self, allow_all_origins=False):
        """Set CORS headers for cross-origin requests"""
        origin = self.headers.get('Origin', '')

        # Start with env-configured allowlist
        origins = set(ALLOWED_ORIGINS_CFG)
        # Also include self render url if provided
        render_url = os.getenv('RENDER_DASHBOARD_URL', '').rstrip('/')
        if render_url:
            origins.add(render_url)
        # If none configured, fall back to defaults
        if not origins:
            origins = {
                'https://quizzernator.onrender.com',
                'http://localhost:3000',
                'http://localhost:8080',
                'http://127.0.0.1:3000',
                'http://127.0.0.1:8080',
            }

        if allow_all_origins:
            self.send_header('Access-Control-Allow-Origin', '*')
        elif origin in origins:
            self.send_header('Access-Control-Allow-Origin', origin)
        else:
            self.send_header('Access-Control-Allow-Origin', '*')

        self.send_header('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.send_header('Access-Control-Max-Age', '86400')
        self.send_header('Vary', 'Origin')

    def do_OPTIONS(self):
        """Handle preflight CORS requests"""
        origin = self.headers.get('Origin', 'unknown')
        logger.info(f"🌐 CORS preflight request from origin: {origin} for path: {self.path}")

        self.send_response(200)
        self.set_cors_headers()
        self.end_headers()

    def serve_api_health(self):
        """GET /api/health - public JSON health endpoint"""
        try:
            self.send_response(200)
            self.set_cors_headers()
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                'status': 'ok',
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }).encode())
        except Exception as e:
            logger.error(f"Error serving /api/health: {e}")
            self.send_response(500)
            self.set_cors_headers()
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'error'}).encode())

    def serve_api_health_auth(self):
        """GET /api/health/auth - requires valid Google bearer token"""
        try:
            user = verify_google_bearer(self.headers.get('Authorization', ''))
            self.send_response(200)
            self.set_cors_headers()
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                'status': 'ok',
                'user_id': user.get('user_id'),
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }).encode())
        except PermissionError:
            self.send_response(401)
            self.set_cors_headers()
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'success': False, 'error': 'Unauthorized'}).encode())
        except Exception as e:
            logger.error(f"Error serving /api/health/auth: {e}")
            self.send_response(500)
            self.set_cors_headers()
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'success': False, 'error': 'Internal error'}).encode())

    def handle_fetch_article(self):
        """Handle POST /api/fetch-article - Fetch external article content"""
        try:
            origin = self.headers.get('Origin', 'unknown')
            logger.info(f"📰 Fetch article request from origin: {origin}")

            content_length = int(self.headers.get('Content-Length', 0))
            if content_length <= 0:
                self.send_response(400)
                self.set_cors_headers()
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "success": False,
                    "error": "Request body is required",
                    "reason": "missing_body"
                }).encode())
                return

            body = self.rfile.read(content_length).decode('utf-8')
            try:
                request_data = json.loads(body)
            except json.JSONDecodeError:
                self.send_response(400)
                self.set_cors_headers()
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "success": False,
                    "error": "Invalid JSON in request body",
                    "reason": "invalid_json"
                }).encode())
                return

            raw_url = request_data.get('url')
            url = str(raw_url).strip() if raw_url else ''
            if not url:
                self.send_response(400)
                self.set_cors_headers()
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "success": False,
                    "error": "URL is required",
                    "reason": "missing_url"
                }).encode())
                return

            parsed = urlparse(url)
            if parsed.scheme not in ('http', 'https') or not parsed.netloc:
                self.send_response(400)
                self.set_cors_headers()
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "success": False,
                    "error": "URL must be an absolute http(s) address",
                    "reason": "invalid_url"
                }).encode())
                return

            truncated_bytes = False
            text_content = None

            wiki_result = None
            if parsed.netloc.lower().endswith('wikipedia.org'):
                wiki_result = fetch_wikipedia_article(parsed)
                if wiki_result:
                    wiki_text, truncated_bytes = wiki_result
                    text_content = build_paragraph_text(wiki_text)

            if text_content is None:
                try:
                    with requests.get(
                        url,
                        headers=FETCH_ARTICLE_HEADERS,
                        timeout=10,
                        stream=True
                    ) as response:
                        status_code = response.status_code
                        if status_code != 200:
                            self.send_response(status_code)
                            self.set_cors_headers()
                            self.send_header('Content-type', 'application/json')
                            self.end_headers()
                            self.wfile.write(json.dumps({
                                "success": False,
                                "error": "Failed to fetch URL",
                                "status": status_code,
                                "reason": "http_error"
                            }).encode())
                            return

                        content_type = response.headers.get('Content-Type', '')
                        if content_type and 'text' not in content_type.lower():
                            self.send_response(415)
                            self.set_cors_headers()
                            self.send_header('Content-type', 'application/json')
                            self.end_headers()
                            self.wfile.write(json.dumps({
                                "success": False,
                                "error": "URL is not text/HTML",
                                "reason": "unsupported_content_type"
                            }).encode())
                            return

                        buffer = bytearray()
                        for chunk in response.iter_content(chunk_size=16384, decode_unicode=False):
                            if not chunk:
                                continue

                            remaining = FETCH_ARTICLE_MAX_BYTES - len(buffer)
                            if remaining <= 0:
                                truncated_bytes = True
                                break

                            if len(chunk) > remaining:
                                buffer.extend(chunk[:remaining])
                                truncated_bytes = True
                                break

                            buffer.extend(chunk)

                        encoding = response.encoding or 'utf-8'

                except RequestException as e:
                    logger.error(f"Failed to fetch article: {e}")
                    self.send_response(502)
                    self.set_cors_headers()
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        "success": False,
                        "error": "Unable to reach URL",
                        "reason": "network_error"
                    }).encode())
                    return

                try:
                    raw_text = buffer.decode(encoding, errors='ignore')
                except Exception:
                    raw_text = buffer.decode('utf-8', errors='ignore')

                soup = BeautifulSoup(raw_text, 'html.parser')
                for element in soup(['script', 'style', 'noscript']):
                    element.decompose()

                extracted_text = soup.get_text(separator='\n')
                text_content = build_paragraph_text(extracted_text)
            if not text_content:
                self.send_response(422)
                self.set_cors_headers()
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "success": False,
                    "error": "No readable text extracted",
                    "reason": "empty_content"
                }).encode())
                return

            clipped_text, truncated_text = clip_article_text(
                text_content,
                FETCH_ARTICLE_MAX_TEXT_CHARS
            )

            self.send_response(200)
            self.set_cors_headers()
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "success": True,
                "text": clipped_text,
                "truncated": truncated_bytes or truncated_text
            }).encode())

        except Exception as e:
            logger.error(f"Unexpected error during fetch-article: {e}")
            self.send_response(500)
            self.set_cors_headers()
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
                "success": False,
                "error": "Failed to process request",
                "reason": "internal_error"
            }).encode())

    def handle_generate_quiz(self):
        """Handle POST /api/generate-quiz - AI quiz generation endpoint"""
        try:
            # Log CORS info for debugging
            origin = self.headers.get('Origin', 'unknown')
            logger.info(f"🤖 Quiz generation request from origin: {origin}")
            # Get request body
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self.send_response(400)
                self.set_cors_headers()
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Request body is required"}).encode())
                return

            body = self.rfile.read(content_length).decode('utf-8')

            try:
                request_data = json.loads(body)
            except json.JSONDecodeError:
                self.send_response(400)
                self.set_cors_headers()
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Invalid JSON in request body"}).encode())
                return

            # Extract parameters
            prompt = request_data.get('prompt')
            if not prompt:
                self.send_response(400)
                self.set_cors_headers()
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Prompt is required"}).encode())
                return

            primary_model = request_data.get('model', 'google/gemini-2.5-flash-lite')
            fallback_model = request_data.get('fallback_model', 'deepseek/deepseek-v3.1-terminus')
            max_tokens = request_data.get('max_tokens', 1800)
            temperature = request_data.get('temperature', 0.7)

            # Check for OpenRouter API key
            openrouter_key = os.getenv('OPENROUTER_API_KEY')
            if not openrouter_key:
                self.send_response(500)
                self.set_cors_headers()
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "OpenRouter API key not configured"}).encode())
                return

            def build_payload(model_id):
                payload = {
                    "model": model_id,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a quiz question generator. Always respond with valid JSON only, no additional text or formatting."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "max_tokens": max_tokens,
                    "response_format": {"type": "json_object"}
                }
                if temperature is not None:
                    payload["temperature"] = temperature
                return payload

            def invoke_model(model_id):
                payload = build_payload(model_id)
                req = Request(
                    'https://openrouter.ai/api/v1/chat/completions',
                    data=json.dumps(payload).encode('utf-8'),
                    headers={
                        'Authorization': f'Bearer {openrouter_key}',
                        'Content-Type': 'application/json',
                        'HTTP-Referer': 'https://quizzernator.onrender.com',
                        'X-Title': 'Quizzernator Generator'
                    }
                )
                return req

            last_error = None
            for model_id in (primary_model, fallback_model):
                request = invoke_model(model_id)
                try:
                    with urlopen(request, timeout=45) as response:
                        raw_payload = response.read().decode('utf-8')
                        try:
                            response_data = json.loads(raw_payload)
                        except json.JSONDecodeError:
                            logger.error("OpenRouter response was not valid JSON (model=%s): %s", model_id, raw_payload[:500])
                            last_error = {"error": "OpenRouter returned unreadable response", "model": model_id}
                            continue

                        choices = response_data.get('choices') or []
                        if not choices:
                            logger.error("OpenRouter response missing choices (model=%s): %s", model_id, raw_payload[:500])
                            last_error = {"error": "AI did not return any quiz content", "model": model_id}
                            continue

                        first_choice = choices[0]
                        finish_reason = first_choice.get('finish_reason')
                        message = first_choice.get('message') or {}
                        content = message.get('content', '')
                        usage = response_data.get('usage', {})

                        if not content.strip():
                            logger.warning(
                                "OpenRouter returned empty content (model=%s, finish_reason=%s, usage=%s, prompt_preview=%s, raw_preview=%s)",
                                model_id,
                                finish_reason,
                                usage,
                                prompt[:200].replace('\n', ' ') if isinstance(prompt, str) else str(prompt),
                                raw_payload[:500]
                            )
                            last_error = {"error": "AI returned empty content", "model": model_id}
                            continue

                        preview = content[:240].replace('\n', ' ')
                        logger.info(
                            "✅ Quiz generated via %s (finish_reason=%s, prompt_tokens=%s, completion_tokens=%s, total_tokens=%s, preview=%s)",
                            model_id,
                            finish_reason,
                            usage.get('prompt_tokens'),
                            usage.get('completion_tokens'),
                            usage.get('total_tokens'),
                            preview
                        )

                        self.send_response(200)
                        self.set_cors_headers()
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()

                        result = {
                            "success": True,
                            "content": content,
                            "usage": usage,
                            "model": model_id
                        }
                        self.wfile.write(json.dumps(result).encode())
                        return

                except HTTPError as e:
                    error_data = e.read().decode('utf-8')
                    logger.error("OpenRouter HTTP error (model=%s): %s", model_id, error_data[:500])
                    try:
                        last_error = json.loads(error_data)
                    except json.JSONDecodeError:
                        last_error = {"error": f"OpenRouter HTTP error {e.code}", "model": model_id}
                except URLError as e:
                    logger.error("OpenRouter network error (model=%s): %s", model_id, str(e))
                    last_error = {"error": f"Network error: {str(e)}", "model": model_id}

            self.send_response(502 if last_error else 500)
            self.set_cors_headers()
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            failure = {
                "error": last_error.get("error") if last_error else "Failed to generate quiz",
                "model": last_error.get("model") if last_error else None,
                "success": False
            }
            self.wfile.write(json.dumps(failure).encode())
            return

        except Exception as e:
            logger.error(f"Quiz generation error: {e}")
            self.send_response(500)
            self.set_cors_headers()
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Failed to generate quiz"}).encode())

    def _get_quiz_storage_path(self):
        """Get the quiz storage directory path"""
        quiz_dir = Path('data/quiz')
        quiz_dir.mkdir(parents=True, exist_ok=True)
        return quiz_dir

    def _get_user_quiz_storage_path(self, user_id: str) -> Path:
        """Get per-user quiz storage directory path"""
        safe_user = re.sub(r'[^A-Za-z0-9_.\-]', '_', user_id or '')
        if not safe_user:
            safe_user = 'unknown'
        base = self._get_quiz_storage_path()
        user_dir = base / safe_user
        user_dir.mkdir(parents=True, exist_ok=True)
        return user_dir

    def _sanitize_filename(self, filename):
        """Sanitize filename to prevent path traversal and invalid characters"""
        import re
        if not filename:
            return None

        # Remove any path separators and dangerous characters
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        filename = re.sub(r'\.\.+', '_', filename)  # Remove .. patterns
        filename = filename.strip()

        # Ensure .json extension
        if not filename.endswith('.json'):
            filename += '.json'

        return filename

    def _json_body(self) -> Optional[dict]:
        try:
            length = int(self.headers.get('Content-Length', 0))
            if length <= 0:
                return None
            raw = self.rfile.read(length)
            try:
                return json.loads(raw.decode('utf-8'))
            except Exception:
                return None
        except Exception:
            return None

    def _enforce_quiz_size(self, payload: dict) -> bool:
        try:
            b = json.dumps(payload, ensure_ascii=False).encode('utf-8')
            kb = len(b) / 1024.0
            return kb <= MAX_QUIZ_KB
        except Exception:
            return False

    def _respond_json(self, code: int, obj: dict) -> None:
        self.send_response(code)
        self.set_cors_headers()
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(obj).encode())

    # ------------------
    # My-scoped handlers
    # ------------------

    def handle_my_list_quizzes(self):
        try:
            user = verify_google_bearer(self.headers.get('Authorization', ''))
            user_dir = self._get_user_quiz_storage_path(user.get('user_id'))
            quizzes = []
            for quiz_file in user_dir.glob('*.json'):
                try:
                    with open(quiz_file, 'r', encoding='utf-8') as f:
                        quiz_data = json.load(f)
                    meta = quiz_data.get('meta', {})
                    metadata = quiz_data.get('metadata', {})
                    created = metadata.get('created')
                    if not created:
                        ts = quiz_file.stat().st_mtime
                        created = datetime.utcfromtimestamp(ts).isoformat() + 'Z'
                    quizzes.append({
                        'filename': quiz_file.name,
                        'topic': meta.get('topic', 'Unknown'),
                        'count': quiz_data.get('count', len(quiz_data.get('items', []))),
                        'difficulty': meta.get('difficulty', 'Unknown'),
                        'created': created
                    })
                except Exception:
                    continue
            quizzes.sort(key=lambda x: x['created'], reverse=True)
            self._respond_json(200, { 'success': True, 'quizzes': quizzes })
        except PermissionError:
            self._respond_json(401, { 'success': False, 'error': 'Unauthorized' })
        except Exception as e:
            logger.error(f"List my quizzes error: {e}")
            self._respond_json(500, { 'success': False, 'error': 'Failed to list quizzes' })

    def handle_my_get_quiz(self):
        try:
            user = verify_google_bearer(self.headers.get('Authorization', ''))
            filename = self.path.split('/api/my/quiz/')[-1]
            filename = self._sanitize_filename(filename)
            if not filename:
                self._respond_json(400, { 'success': False, 'error': 'Invalid filename' })
                return
            quiz_path = self._get_user_quiz_storage_path(user.get('user_id')) / filename
            if not quiz_path.exists():
                self._respond_json(404, { 'success': False, 'error': 'Not found' })
                return
            with open(quiz_path, 'r', encoding='utf-8') as f:
                quiz_data = json.load(f)
            self._respond_json(200, { 'success': True, 'quiz': quiz_data })
        except PermissionError:
            self._respond_json(401, { 'success': False, 'error': 'Unauthorized' })
        except Exception as e:
            logger.error(f"Get my quiz error: {e}")
            self._respond_json(500, { 'success': False, 'error': 'Failed to load quiz' })

    def handle_my_save_quiz(self):
        try:
            # Per-IP RL (fallback) and auth
            if not check_ip_minute(self):
                self._respond_json(429, { 'success': False, 'error': 'Rate limit exceeded' })
                return
            user = verify_google_bearer(self.headers.get('Authorization', ''))
            uid = user.get('user_id')
            if not check_user_minute(uid) or not check_user_daily(uid):
                self._respond_json(429, { 'success': False, 'error': 'Rate limit exceeded' })
                return

            data = self._json_body()
            if not data or 'quiz' not in data:
                self._respond_json(400, { 'success': False, 'error': 'Quiz data is required' })
                return
            quiz_data = data['quiz']
            overwrite = bool(data.get('overwrite'))
            if not self._enforce_quiz_size(quiz_data):
                self._respond_json(413, { 'success': False, 'error': 'Payload too large' })
                return

            filename = data.get('filename')
            if filename:
                filename = self._sanitize_filename(filename)
            else:
                meta = quiz_data.get('meta', {})
                topic = meta.get('topic', 'quiz')
                ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = self._sanitize_filename(f"{topic.lower().replace(' ', '_')}_{ts}.json")
            if not filename:
                self._respond_json(400, { 'success': False, 'error': 'Invalid filename' })
                return

            user_dir = self._get_user_quiz_storage_path(uid)
            quiz_path = user_dir / filename
            if quiz_path.exists() and not overwrite:
                self._respond_json(409, { 'success': False, 'error': 'Duplicate filename', 'code': 'DUPLICATE', 'filename': filename })
                return

            # Add metadata
            quiz_data.setdefault('metadata', {})
            quiz_data['metadata'].update({
                'created': datetime.utcnow().isoformat() + 'Z',
                'filename': filename,
                'owner': uid
            })
            with open(quiz_path, 'w', encoding='utf-8') as f:
                json.dump(quiz_data, f, indent=2, ensure_ascii=False)

            meta = quiz_data.get('meta', {})
            result = {
                'success': True,
                'filename': filename,
                'topic': meta.get('topic', 'Unknown'),
                'count': quiz_data.get('count', len(quiz_data.get('items', []))),
                'difficulty': meta.get('difficulty', 'Unknown'),
                'created': quiz_data['metadata']['created']
            }
            self._respond_json(200, result)
        except PermissionError:
            self._respond_json(401, { 'success': False, 'error': 'Unauthorized' })
        except Exception as e:
            logger.error(f"Save my quiz error: {e}")
            self._respond_json(500, { 'success': False, 'error': 'Failed to save quiz' })

    def handle_my_delete_quiz(self):
        try:
            user = verify_google_bearer(self.headers.get('Authorization', ''))
            filename = self.path.split('/api/my/quiz/')[-1]
            filename = self._sanitize_filename(filename)
            if not filename:
                self._respond_json(400, { 'success': False, 'error': 'Invalid filename' })
                return
            quiz_path = self._get_user_quiz_storage_path(user.get('user_id')) / filename
            if not quiz_path.exists():
                self._respond_json(404, { 'success': False, 'error': 'Not found' })
                return
            try:
                quiz_path.unlink()
            except Exception:
                self._respond_json(500, { 'success': False, 'error': 'Failed to delete quiz' })
                return
            self._respond_json(200, { 'success': True, 'deleted': True })
        except PermissionError:
            self._respond_json(401, { 'success': False, 'error': 'Unauthorized' })
        except Exception as e:
            logger.error(f"Delete my quiz error: {e}")
            self._respond_json(500, { 'success': False, 'error': 'Failed to delete quiz' })

    def handle_save_quiz(self):
        """Handle POST /api/save-quiz - Save generated quiz to storage"""
        try:
            origin = self.headers.get('Origin', 'unknown')
            logger.info(f"💾 Save quiz request from origin: {origin}")

            # Get request body
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self.send_response(400)
                self.set_cors_headers()
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Request body is required"}).encode())
                return

            body = self.rfile.read(content_length).decode('utf-8')

            try:
                request_data = json.loads(body)
            except json.JSONDecodeError:
                self.send_response(400)
                self.set_cors_headers()
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Invalid JSON in request body"}).encode())
                return

            quiz_data = request_data.get('quiz')
            if not quiz_data:
                self.send_response(400)
                self.set_cors_headers()
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Quiz data is required"}).encode())
                return

            # Get or generate filename
            filename = request_data.get('filename')
            if filename:
                filename = self._sanitize_filename(filename)
            else:
                # Auto-generate filename from quiz metadata
                meta = quiz_data.get('meta', {})
                topic = meta.get('topic', 'quiz')
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"{topic.lower().replace(' ', '_')}_{timestamp}.json"
                filename = self._sanitize_filename(filename)

            if not filename:
                self.send_response(400)
                self.set_cors_headers()
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Invalid filename"}).encode())
                return

            # Save quiz to storage
            quiz_dir = self._get_quiz_storage_path()
            quiz_path = quiz_dir / filename

            # Add metadata
            quiz_data['metadata'] = {
                'created': datetime.now().isoformat(),
                'filename': filename,
                'origin': origin
            }

            with open(quiz_path, 'w', encoding='utf-8') as f:
                json.dump(quiz_data, f, indent=2, ensure_ascii=False)

            # Send successful response
            self.send_response(200)
            self.set_cors_headers()
            self.send_header('Content-type', 'application/json')
            self.end_headers()

            result = {
                "success": True,
                "filename": filename,
                "path": str(quiz_path)
            }
            self.wfile.write(json.dumps(result).encode())

        except Exception as e:
            logger.error(f"Save quiz error: {e}")
            self.send_response(500)
            self.set_cors_headers()
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Failed to save quiz"}).encode())

    def handle_list_quizzes(self):
        """Handle GET /api/list-quizzes - List all saved quizzes"""
        try:
            logger.info(f"📋 List quizzes request")

            quiz_dir = self._get_quiz_storage_path()
            quizzes = []

            for quiz_file in quiz_dir.glob('*.json'):
                try:
                    with open(quiz_file, 'r', encoding='utf-8') as f:
                        quiz_data = json.load(f)

                    meta = quiz_data.get('meta', {})
                    metadata = quiz_data.get('metadata', {})

                    quiz_info = {
                        'filename': quiz_file.name,
                        'topic': meta.get('topic', 'Unknown'),
                        'count': quiz_data.get('count', len(quiz_data.get('items', []))),
                        'difficulty': meta.get('difficulty', 'Unknown'),
                        'created': metadata.get('created', quiz_file.stat().st_mtime)
                    }
                    quizzes.append(quiz_info)

                except Exception as e:
                    logger.warning(f"Error reading quiz file {quiz_file}: {e}")
                    continue

            # Sort by creation date (newest first)
            quizzes.sort(key=lambda x: x['created'], reverse=True)

            # Send successful response
            self.send_response(200)
            self.set_cors_headers()
            self.send_header('Content-type', 'application/json')
            self.end_headers()

            result = {
                "success": True,
                "quizzes": quizzes
            }
            self.wfile.write(json.dumps(result).encode())

        except Exception as e:
            logger.error(f"List quizzes error: {e}")
            self.send_response(500)
            self.set_cors_headers()
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Failed to list quizzes"}).encode())

    def handle_get_quiz(self):
        """Handle GET /api/quiz/:filename - Load specific quiz"""
        try:
            # Extract filename from path
            filename = self.path.split('/api/quiz/')[-1]
            filename = self._sanitize_filename(filename)

            if not filename:
                self.send_response(400)
                self.set_cors_headers()
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Invalid filename"}).encode())
                return

            logger.info(f"📖 Get quiz request for: {filename}")

            quiz_dir = self._get_quiz_storage_path()
            quiz_path = quiz_dir / filename

            if not quiz_path.exists():
                self.send_response(404)
                self.set_cors_headers()
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Quiz not found"}).encode())
                return

            with open(quiz_path, 'r', encoding='utf-8') as f:
                quiz_data = json.load(f)

            # Send successful response
            self.send_response(200)
            self.set_cors_headers()
            self.send_header('Content-type', 'application/json')
            self.end_headers()

            result = {
                "success": True,
                "quiz": quiz_data
            }
            self.wfile.write(json.dumps(result).encode())

        except Exception as e:
            logger.error(f"Get quiz error: {e}")
            self.send_response(500)
            self.set_cors_headers()
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Failed to load quiz"}).encode())

    def handle_delete_quiz(self):
        """Handle DELETE /api/quiz/:filename - Delete specific quiz"""
        try:
            # Extract filename from path
            filename = self.path.split('/api/quiz/')[-1]
            filename = self._sanitize_filename(filename)

            if not filename:
                self.send_response(400)
                self.set_cors_headers()
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Invalid filename"}).encode())
                return

            logger.info(f"🗑️ Delete quiz request for: {filename}")

            quiz_dir = self._get_quiz_storage_path()
            quiz_path = quiz_dir / filename

            if not quiz_path.exists():
                self.send_response(404)
                self.set_cors_headers()
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Quiz not found"}).encode())
                return

            quiz_path.unlink()  # Delete the file

            # Send successful response
            self.send_response(200)
            self.set_cors_headers()
            self.send_header('Content-type', 'application/json')
            self.end_headers()

            result = {
                "success": True,
                "message": "Quiz deleted successfully"
            }
            self.wfile.write(json.dumps(result).encode())

        except Exception as e:
            logger.error(f"Delete quiz error: {e}")
            self.send_response(500)
            self.set_cors_headers()
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Failed to delete quiz"}).encode())


    def _categorize_by_ai(self, topic, quiz_content=""):
        """Categorize quiz using OpenAI GPT-3.5-turbo with structured JSON output"""
        try:
            import openai
        except ImportError:
            print("⚠️ OpenAI not available, returning fallback")
            return "General", "Mixed Content", 0.3

        # Build category structure for prompt (simplified structure without keywords)
        categories_structure = {
            "Technology": ["Software Tutorials", "Tech Reviews & Comparisons", "Tech News & Trends", "Programming & Software Development", "Mobile Development", "Web Development", "DevOps & Infrastructure", "Cybersecurity", "Databases & Data Science"],
            "AI Software Development": ["Agents & MCP/Orchestration", "APIs & SDKs", "Model Selection & Evaluation", "Deployment & Serving", "Cost Optimisation", "Security & Safety", "Prompt Engineering & RAG", "Data Engineering & ETL", "Training & Fine-Tuning"],
            "History": ["Modern History", "Historical Analysis", "Cultural Heritage", "Ancient Civilizations"],
            "Education": ["Tutorials & Courses", "Teaching Methods", "Academic Subjects"],
            "Business": ["Industry Analysis", "Finance & Investing", "Career Development", "Marketing & Sales", "Leadership & Management"],
            "World War II (WWII)": ["European Theatre", "Aftermath & Reconstruction", "Technology & Weapons", "Causes & Prelude", "Biographies & Commanders", "Home Front & Society", "Pacific Theatre", "Holocaust & War Crimes", "Intelligence & Codebreaking"],
            "Hobbies & Special Interests": ["Automotive"],
            "Science & Nature": ["Physics & Chemistry"],
            "News & Politics": ["Political Analysis", "Government & Policy", "Current Events", "International Affairs"],
            "Entertainment": ["Comedy & Humor", "Music & Performance", "Reaction Content", "Movies & TV"],
            "Reviews & Products": ["Comparisons & Tests", "Product Reviews", "Buying Guides"],
            "General": ["Mixed Content"],
            "Computer Hardware": ["Networking & NAS", "Cooling & Thermals"],
            "Astronomy": ["Space Missions & Exploration", "Solar System & Planets", "Space News & Discoveries"],
            "Sports": ["Equipment & Gear"],
            "News": ["General News"],
            "World War I (WWI)": ["Aftermath & Interwar"]
        }

        # Construct AI prompt for structured output
        prompt = f"""You are a content categorization expert. Categorize the following quiz topic into the most appropriate category and subcategory.

TOPIC: {topic}
CONTENT: {quiz_content or "No additional content provided"}

AVAILABLE CATEGORIES AND SUBCATEGORIES:
{json.dumps(categories_structure, indent=2)}

INSTRUCTIONS:
- Choose the SINGLE most appropriate category and subcategory
- Base your decision on the topic content and context
- If the topic doesn't clearly fit any category, use "General" → "Mixed Content"
- Provide a confidence score from 0.0 to 1.0

REQUIRED OUTPUT FORMAT (JSON only, no explanation):
{{
  "category": "Category Name",
  "subcategory": "Subcategory Name",
  "confidence": 0.85,
  "reasoning": "Brief one-sentence explanation"
}}"""

        try:
            # Make OpenAI API call
            response = openai.chat.completions.create(
                model="gpt-5-nano",  # Ultra cost-effective model with JSON mode
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_completion_tokens=1000,  # Higher limit needed for reasoning model
                # Note: temperature not supported by GPT-5-nano (uses default 1)
                response_format={"type": "json_object"}  # Force JSON output
            )

            # Parse response
            result_text = response.choices[0].message.content.strip()
            result = json.loads(result_text)

            # Validate response structure
            category = result.get("category", "General")
            subcategory = result.get("subcategory", "Mixed Content")
            confidence = float(result.get("confidence", 0.5))
            reasoning = result.get("reasoning", "AI categorization")

            # Validate category exists in our mapping
            if category not in categories_structure:
                category = "General"
                subcategory = "Mixed Content"
                confidence = 0.3

            # Validate subcategory exists for the category
            elif subcategory not in categories_structure[category]:
                # Use first available subcategory for this category
                subcategory = categories_structure[category][0]
                confidence = max(0.3, confidence - 0.2)  # Reduce confidence for subcategory fallback

            return category, subcategory, confidence

        except Exception as e:
            print(f"⚠️ AI categorization failed: {e}")
            return "General", "Mixed Content", 0.3


    def handle_categorize_quiz(self):
        """Handle POST /api/categorize-quiz - Auto-categorize quiz topic"""
        try:
            origin = self.headers.get('Origin', 'unknown')
            logger.info(f"🏷️ Quiz categorization request from origin: {origin}")

            # Get request body
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self.send_response(400)
                self.set_cors_headers()
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Request body is required"}).encode())
                return

            body = self.rfile.read(content_length).decode('utf-8')

            try:
                request_data = json.loads(body)
            except json.JSONDecodeError:
                self.send_response(400)
                self.set_cors_headers()
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Invalid JSON in request body"}).encode())
                return

            topic = request_data.get('topic', '').strip()
            if not topic:
                self.send_response(400)
                self.set_cors_headers()
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"error": "Topic is required"}).encode())
                return

            quiz_content = request_data.get('quiz_content', '')

            # Use AI-based categorization (more accurate)
            category, subcategory, confidence = self._categorize_by_ai(topic, quiz_content)

            # Generate simple alternatives (no longer need complex scoring)
            alternatives = [
                {"category": "Technology", "subcategory": "Software Tutorials", "confidence": 0.2},
                {"category": "AI Software Development", "subcategory": "Agents & MCP/Orchestration", "confidence": 0.2}
            ]

            # Send successful response
            self.send_response(200)
            self.set_cors_headers()
            self.send_header('Content-type', 'application/json')
            self.end_headers()

            result = {
                "success": True,
                "category": category,
                "subcategory": subcategory or "General",
                "confidence": round(confidence, 2),
                "alternatives": alternatives[:2],  # Limit to 2 alternatives
                "available_categories": ["Technology", "AI Software Development", "History", "Education", "Business", "World War II (WWII)", "Hobbies & Special Interests", "Science & Nature", "News & Politics", "Entertainment", "Reviews & Products", "General", "Computer Hardware", "Astronomy", "Sports", "News", "World War I (WWI)"],
                "available_subcategories": {
                    "Technology": ["Software Tutorials", "Tech Reviews & Comparisons", "Tech News & Trends", "Programming & Software Development", "Mobile Development", "Web Development", "DevOps & Infrastructure", "Cybersecurity", "Databases & Data Science"],
                    "AI Software Development": ["Agents & MCP/Orchestration", "APIs & SDKs", "Model Selection & Evaluation", "Deployment & Serving", "Cost Optimisation", "Security & Safety", "Prompt Engineering & RAG", "Data Engineering & ETL", "Training & Fine-Tuning"],
                    "History": ["Modern History", "Historical Analysis", "Cultural Heritage", "Ancient Civilizations"],
                    "Education": ["Tutorials & Courses", "Teaching Methods", "Academic Subjects"],
                    "Business": ["Industry Analysis", "Finance & Investing", "Career Development", "Marketing & Sales", "Leadership & Management"],
                    "World War II (WWII)": ["European Theatre", "Aftermath & Reconstruction", "Technology & Weapons", "Causes & Prelude", "Biographies & Commanders", "Home Front & Society", "Pacific Theatre", "Holocaust & War Crimes", "Intelligence & Codebreaking"],
                    "Hobbies & Special Interests": ["Automotive"],
                    "Science & Nature": ["Physics & Chemistry"],
                    "News & Politics": ["Political Analysis", "Government & Policy", "Current Events", "International Affairs"],
                    "Entertainment": ["Comedy & Humor", "Music & Performance", "Reaction Content", "Movies & TV"],
                    "Reviews & Products": ["Comparisons & Tests", "Product Reviews", "Buying Guides"],
                    "General": ["Mixed Content"],
                    "Computer Hardware": ["Networking & NAS", "Cooling & Thermals"],
                    "Astronomy": ["Space Missions & Exploration", "Solar System & Planets", "Space News & Discoveries"],
                    "Sports": ["Equipment & Gear"],
                    "News": ["General News"],
                    "World War I (WWI)": ["Aftermath & Interwar"]
                }
            }
            self.wfile.write(json.dumps(result).encode())

        except Exception as e:
            logger.error(f"Quiz categorization error: {e}")
            self.send_response(500)
            self.set_cors_headers()
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Failed to categorize quiz"}).encode())

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
        httpd = ThreadedHTTPServer(server_address, ModernDashboardHTTPRequestHandler)
        setattr(httpd, 'content_index', content_index)
        
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
