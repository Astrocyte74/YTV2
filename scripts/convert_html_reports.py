#!/usr/bin/env python3
"""
Convert legacy HTML reports in ./exports to JSON schema used by data/reports.

For each *.html in exports (excluding obvious templates/tests), parse key fields
and emit data/reports/<stem>.json so the server renders them dynamically.
"""

import re
import json
import hashlib
from datetime import datetime
from pathlib import Path
from html import unescape

EXPORTS_DIR = Path('./exports')
OUTPUT_DIR = Path('./data/reports')


def parse_between(pattern: str, text: str, flags=0) -> str:
    m = re.search(pattern, text, flags)
    return m.group(1).strip() if m else ''


def to_duration_seconds(duration_str: str) -> int:
    if not duration_str:
        return 0
    parts = duration_str.split(':')
    try:
        parts = [int(p) for p in parts]
        if len(parts) == 3:
            h, m, s = parts
        elif len(parts) == 2:
            h, m, s = 0, parts[0], parts[1]
        else:
            return 0
        return h * 3600 + m * 60 + s
    except Exception:
        return 0


def parse_upload_date(date_str: str) -> str:
    """Convert 'September 03, 2025' -> '20250903'"""
    if not date_str:
        return ''
    try:
        dt = datetime.strptime(date_str, '%B %d, %Y')
        return dt.strftime('%Y%m%d')
    except Exception:
        return ''


def extract_summary_text(html: str) -> str:
    # Grab the summary content block
    block = parse_between(r'<div class="summary-content">(.*?)</div>', html, flags=re.DOTALL)
    if not block:
        return ''
    # Replace <br> with newlines
    block = re.sub(r'<br\s*/?>', '\n\n', block, flags=re.IGNORECASE)
    # Replace paragraph tags with newlines
    block = re.sub(r'</p\s*>', '\n\n', block, flags=re.IGNORECASE)
    block = re.sub(r'<p[^>]*>', '', block, flags=re.IGNORECASE)
    # Strip all other tags
    block = re.sub(r'<[^>]+>', '', block)
    # Unescape HTML entities
    block = unescape(block)
    # Normalize whitespace
    block = '\n'.join([line.strip() for line in block.splitlines()]).strip()
    # Collapse excessive blank lines
    block = re.sub(r'\n{3,}', '\n\n', block)
    return block


def extract_video_url(html: str) -> str:
    # Prefer the explicit Video URL anchor
    url = parse_between(r'<div class="info-item"[^>]*data-type="url"[\s\S]*?<a href="([^"]+)"', html)
    if url:
        return url
    # Fallback to any YouTube link in the page
    url = parse_between(r'href="(https?://www\.youtube\.com/watch\?v=[^"]+)"', html)
    return url


def video_id_from_url(url: str) -> str:
    m = re.search(r'[?&]v=([A-Za-z0-9_-]{6,})', url)
    return m.group(1) if m else ''


def provider_from_badge(html: str) -> str:
    # model-badge <div class="model-badge openai">GPT-5</div>
    cls = parse_between(r'<div class="model-badge ([^"]+)">', html)
    for candidate in ['openai', 'anthropic', 'deepseek', 'gemma', 'llama']:
        if candidate in cls:
            return candidate
    return 'openai' if cls else ''


def info_value_for(html: str, data_type: str) -> str:
    """Extract the .info-value for a given info-item data-type."""
    pattern = rf'<div class="info-item"[^>]*data-type="{re.escape(data_type)}"[\s\S]*?<div class="info-value">([^<]+)</div>'
    return parse_between(pattern, html)


def build_report_json(html_path: Path) -> dict:
    html = html_path.read_text(encoding='utf-8', errors='ignore')

    title = parse_between(r'<h1[^>]*>([^<]+)</h1>', html)
    channel = parse_between(r'<div class="channel">([^<]+)</div>', html)
    duration_str = info_value_for(html, 'duration')
    upload_date_human = info_value_for(html, 'date')
    upload_date = parse_upload_date(upload_date_human)
    views_txt = info_value_for(html, 'views')
    try:
        views = int(views_txt.replace(',', '').strip()) if views_txt else 0
    except Exception:
        views = 0
    model = info_value_for(html, 'provider')
    provider = provider_from_badge(html)
    summary_type = (info_value_for(html, 'type') or '').lower()
    video_url = extract_video_url(html)
    vid = video_id_from_url(video_url)

    # Thumbnail: prefer standard YouTube thumbnail if video_id exists
    thumbnail = f"https://i.ytimg.com/vi_webp/{vid}/maxresdefault.webp" if vid else ''

    # Summary text
    summary_text = extract_summary_text(html)

    # Duration seconds
    duration_seconds = to_duration_seconds(duration_str)

    # Timestamps
    mtime = datetime.fromtimestamp(html_path.stat().st_mtime)
    generated_at = mtime.isoformat()

    # Deterministic report_id based on stem
    stem = html_path.stem
    short_hash = hashlib.md5(stem.encode('utf-8')).hexdigest()[:6]
    report_id = f"{vid}_{short_hash}" if vid else f"{stem}_{short_hash}"

    report = {
        "metadata": {
            "schema_version": "1.0.0",
            "generated_at": generated_at,
            "report_id": report_id
        },
        "video": {
            "url": video_url,
            "video_id": vid,
            "title": title or html_path.stem,
            "channel": channel or "",
            "channel_id": "",
            "duration": duration_seconds,
            "duration_string": duration_str,
            "view_count": views,
            "like_count": 0,
            "upload_date": upload_date,
            "description": "",
            "tags": [],
            "categories": [],
            "thumbnail": thumbnail,
            "language": "",
            "subtitles_available": False
        },
        "summary": {
            "content": {
                "summary": summary_text,
                "headline": "",
                "summary_type": summary_type or "comprehensive",
                "generated_at": generated_at
            },
            "type": summary_type or "comprehensive",
            "analysis": {
                "category": [],
                "sentiment": "",
                "target_audience": "",
                "complexity_level": "",
                "key_topics": [],
                "content_type": "",
                "educational_value": "",
                "entertainment_value": ""
            },
            "key_points": [],
            "topics": [],
            "sentiment": {},
            "quality_score": 0,
            "word_count": len(summary_text.split()) if summary_text else 0
        },
        "processing": {
            "llm_provider": provider or "",
            "model": model or ""
        },
        "stats": {
            "video_length_seconds": duration_seconds,
            "video_length_minutes": round(duration_seconds / 60.0, 2) if duration_seconds else 0,
            "summary_word_count": len(summary_text.split()) if summary_text else 0,
            "summary_character_count": len(summary_text) if summary_text else 0,
            "compression_ratio": 0,
            "has_analysis": False,
            "has_key_points": False,
            "topic_count": 0
        }
    }

    return report


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    html_files = []
    if EXPORTS_DIR.exists():
        html_files.extend([p for p in EXPORTS_DIR.glob('*.html')])

    # Also check project root for any stray legacy HTML files (excluding templates)
    html_files.extend([p for p in Path('.').glob('*.html')])

    skip_names = {
        'dashboard_template.html',
        'report_template.html',
        'test_report.html'
    }
    html_files = [p for p in html_files if p.name not in skip_names and not p.name.startswith('._')]

    if not html_files:
        print('No legacy HTML reports found to convert.')
        return

    converted = 0
    for html_path in html_files:
        try:
            report = build_report_json(html_path)
            out_path = OUTPUT_DIR / f"{html_path.stem}.json"
            out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            converted += 1
            print(f"Converted: {html_path} -> {out_path}")
        except Exception as e:
            print(f"Failed to convert {html_path.name}: {e}")

    print(f"Done. Converted {converted} HTML reports to JSON in {OUTPUT_DIR}.")


if __name__ == '__main__':
    main()

