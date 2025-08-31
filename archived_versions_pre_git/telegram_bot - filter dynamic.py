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

# Load environment variables from .env file and stack.env
load_dotenv()

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
            
            # Security check - only allow .html files in exports directory
            if not filename.endswith('.html') or '/' in filename or '..' in filename:
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
            
            # Serve the HTML file
            logger.info(f"🌐 Serving file: {filepath}")
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-cache')
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
    
    def send_index_page(self):
        """Send an enhanced index page listing available reports"""
        try:
            html_files = list(self.exports_dir.glob("*.html"))
            html_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            logger.info(f"📊 Dashboard: Found {len(html_files)} HTML files in {self.exports_dir}")
            
            # Analyze model usage from HTML files
            model_usage = {}
            all_models = set()
            
            for html_file in html_files:
                try:
                    content = html_file.read_text(encoding='utf-8')
                    
                    # Extract model from content - try multiple patterns (same as card generation)
                    model_patterns = [
                        # New info-grid pattern (most recent format)
                        r'<div class="info-label">AI Model</div>\s*<div class="info-value">([^<]+)</div>',
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
                        
                except Exception as e:
                    logger.warning(f"Could not extract model from {html_file.name}: {e}")
            
            # Get top 3 models for display
            top_models = sorted(model_usage.items(), key=lambda x: x[1], reverse=True)[:3]
            models_text = ", ".join([f"{model} ({count})" for model, count in top_models]) if top_models else "Mixed Models"
            
            total_reports = len(html_files)
            total_size = sum(f.stat().st_size for f in html_files) / (1024 * 1024)  # MB
            
            index_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>YouTube Summary Reports Dashboard</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{ 
            max-width: 1200px; 
            margin: 0 auto; 
            background: white; 
            border-radius: 20px; 
            box-shadow: 0 20px 40px rgba(0,0,0,0.15);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: white;
            padding: 25px 30px;
            text-align: center;
        }}
        .header h1 {{
            font-size: 2em;
            margin-bottom: 5px;
            font-weight: 700;
        }}
        .header p {{
            font-size: 1.1em;
            opacity: 0.9;
        }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
            gap: 15px;
            padding: 20px 30px;
            background: #f8f9fa;
            border-bottom: 1px solid #e9ecef;
        }}
        .stat-card {{
            background: white;
            padding: 18px 15px;
            border-radius: 10px;
            text-align: center;
            box-shadow: 0 4px 12px rgba(0,0,0,0.08);
            transition: transform 0.2s ease;
        }}
        .stat-card:hover {{
            transform: translateY(-2px);
        }}
        .stat-number {{
            font-size: 2em;
            font-weight: bold;
            color: #2a5298;
            margin-bottom: 5px;
        }}
        .stat-label {{
            color: #6c757d;
            font-size: 0.9em;
        }}
        .content {{
            padding: 25px 30px;
        }}
        .section-title {{
            font-size: 1.4em;
            color: #2a5298;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .management-controls {{
            padding: 15px 30px;
            background: #f8f9fa;
            border-bottom: 1px solid #e9ecef;
            margin-bottom: 15px;
        }}
        .search-bar {{
            margin-bottom: 15px;
        }}
        .search-bar input {{
            width: 100%;
            padding: 12px 16px;
            border: 2px solid #e9ecef;
            border-radius: 8px;
            font-size: 16px;
            transition: border-color 0.3s ease;
        }}
        .search-bar input:focus {{
            outline: none;
            border-color: #2a5298;
        }}
        .filter-controls {{
            display: flex;
            gap: 10px;
            align-items: center;
            flex-wrap: wrap;
        }}
        .filter-controls select {{
            padding: 8px 12px;
            border: 1px solid #e9ecef;
            border-radius: 6px;
            background: white;
        }}
        .btn-secondary {{
            background: #6c757d;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            cursor: pointer;
            transition: background 0.3s ease;
        }}
        .btn-secondary:hover {{
            background: #5a6268;
        }}
        .btn-danger {{
            background: #dc3545;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            cursor: pointer;
            transition: background 0.3s ease;
        }}
        .btn-danger:hover {{
            background: #c82333;
        }}
        .btn-danger:disabled {{
            background: #ccc;
            cursor: not-allowed;
        }}
        .report-grid {{
            display: grid;
            gap: 20px;
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
        }}
        .report-header {{
            display: flex;
            align-items: flex-start;
            gap: 10px;
            margin-bottom: 15px;
            position: relative;
            padding-right: 30px;
        }}
        .card-delete-btn {{
            position: absolute;
            top: -5px;
            right: -5px;
            background: #dc3545;
            color: white;
            border: none;
            border-radius: 50%;
            width: 24px;
            height: 24px;
            font-size: 12px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            opacity: 0;
            transition: all 0.3s ease;
            box-shadow: 0 2px 6px rgba(220, 53, 69, 0.3);
        }}
        .report-card:hover .card-delete-btn {{
            opacity: 1;
        }}
        .card-delete-btn:hover {{
            background: #c82333;
            transform: scale(1.1);
        }}
        .report-checkbox {{
            margin-top: 2px;
            transform: scale(1.2);
        }}
        .report-card {{
            background: white;
            border: 1px solid #e9ecef;
            border-radius: 12px;
            padding: 25px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.08);
            transition: all 0.3s ease;
            position: relative;
        }}
        .report-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 15px 35px rgba(0,0,0,0.15);
        }}
        .report-title {{
            font-size: 1.2em;
            font-weight: 600;
            color: #2a5298;
            margin-bottom: 15px;
            word-break: break-word;
        }}
        .report-meta {{
            display: flex;
            flex-direction: column;
            gap: 8px;
            margin-bottom: 20px;
            font-size: 0.9em;
            color: #6c757d;
        }}
        .report-meta-item {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .report-actions {{
            display: flex;
            gap: 10px;
            margin-top: auto;
            flex-wrap: wrap;
        }}
        .btn {{
            padding: 10px 20px;
            border: none;
            border-radius: 8px;
            text-decoration: none;
            font-weight: 500;
            transition: all 0.2s ease;
            cursor: pointer;
            font-size: 0.9em;
        }}
        .btn-primary {{
            background: #2a5298;
            color: white;
        }}
        .btn-primary:hover {{
            background: #1e3c72;
        }}
        .btn-secondary {{
            background: #e9ecef;
            color: #495057;
        }}
        .btn-secondary:hover {{
            background: #dee2e6;
        }}
        .empty-state {{
            text-align: center;
            padding: 60px 20px;
            color: #6c757d;
        }}
        .empty-state-icon {{
            font-size: 4em;
            margin-bottom: 20px;
        }}
        .footer {{
            background: #f8f9fa;
            padding: 30px 40px;
            text-align: center;
            border-top: 1px solid #e9ecef;
            color: #6c757d;
            font-size: 0.9em;
        }}
        .refresh-btn {{
            position: fixed;
            bottom: 30px;
            right: 30px;
            background: #2a5298;
            color: white;
            border: none;
            border-radius: 50%;
            width: 60px;
            height: 60px;
            font-size: 1.5em;
            cursor: pointer;
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
            transition: all 0.2s ease;
        }}
        .refresh-btn:hover {{
            background: #1e3c72;
            transform: scale(1.1);
        }}
        @media (max-width: 768px) {{
            .container {{ margin: 10px; }}
            .header {{ padding: 20px 15px; }}
            .header h1 {{ font-size: 1.8em; }}
            .content, .stats, .footer {{ padding: 15px; }}
            .management-controls {{ padding: 12px 15px; }}
            .report-grid {{ grid-template-columns: 1fr; }}
            .refresh-btn {{ bottom: 20px; right: 20px; }}
        }}
        
        /* Custom Modal Styles */
        .modal {{
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0, 0, 0, 0.6);
            backdrop-filter: blur(5px);
            animation: fadeIn 0.3s ease;
        }}
        
        .modal-content {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            margin: 20% auto;
            padding: 30px;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            width: 90%;
            max-width: 400px;
            text-align: center;
            color: white;
            animation: slideIn 0.3s ease;
        }}
        
        .modal h3 {{
            margin: 0 0 15px 0;
            font-size: 1.3em;
            font-weight: 600;
        }}
        
        .modal p {{
            margin: 0 0 25px 0;
            opacity: 0.9;
            line-height: 1.4;
        }}
        
        .modal-buttons {{
            display: flex;
            gap: 15px;
            justify-content: center;
        }}
        
        .modal-btn {{
            padding: 12px 25px;
            border: none;
            border-radius: 25px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            min-width: 80px;
        }}
        
        .modal-btn-confirm {{
            background: rgba(255, 255, 255, 0.2);
            color: white;
            border: 2px solid rgba(255, 255, 255, 0.3);
        }}
        
        .modal-btn-confirm:hover {{
            background: rgba(255, 255, 255, 0.3);
            transform: translateY(-2px);
        }}
        
        .modal-btn-cancel {{
            background: rgba(0, 0, 0, 0.2);
            color: rgba(255, 255, 255, 0.8);
            border: 2px solid transparent;
        }}
        
        .modal-btn-cancel:hover {{
            background: rgba(0, 0, 0, 0.3);
            transform: translateY(-2px);
        }}
        
        .success-modal .modal-content {{
            background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%);
        }}
        
        @keyframes fadeIn {{
            from {{ opacity: 0; }}
            to {{ opacity: 1; }}
        }}
        
        @keyframes slideIn {{
            from {{ transform: translateY(-50px); opacity: 0; }}
            to {{ transform: translateY(0); opacity: 1; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📺 YouTube Summary Reports</h1>
            <p>AI-powered video analysis dashboard</p>
        </div>
        
        <div class="stats">
            <div class="stat-card">
                <div class="stat-number">{total_reports}</div>
                <div class="stat-label">Total Reports</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{total_size:.1f} MB</div>
                <div class="stat-label">Storage Used</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{len(model_usage)}</div>
                <div class="stat-label">AI Models Used</div>
            </div>
        </div>
        
        <div class="content">
            <div class="section-title">
                📊 Available Reports
            </div>
            
            <div class="management-controls">
                <div class="search-bar">
                    <input type="text" id="searchInput" placeholder="🔍 Search reports by title or content..." onkeyup="filterReports()">
                </div>
                <div class="filter-controls">
                    <select id="sortBy" onchange="sortReports()">
                        <option value="newest">📅 Newest First</option>
                        <option value="oldest">📅 Oldest First</option>
                        <option value="title">🔤 Title A-Z</option>
                        <option value="size">📏 Size</option>
                    </select>
                    <select id="modelFilter" onchange="filterByModel()">
                        <option value="all">🤖 All Models</option>"""
                    
            # Add model filter options dynamically
            for model, count in sorted(model_usage.items()):
                index_html += f'<option value="{model}">🤖 {model} ({count})</option>'
                
            index_html += """</select>
                    <button onclick="selectAll()" class="btn-secondary">Select All</button>
                    <button onclick="deleteSelected()" class="btn-danger" id="deleteBtn" disabled>🗑️ Delete Selected</button>
                </div>
            </div>"""
            
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
                    
                    # Try to extract title, URL, model, and summary type from HTML file content
                    used_model = "Unknown"
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
                            # New info-grid pattern (most recent format)
                            r'<div class="info-label">AI Model</div>\s*<div class="info-value">([^<]+)</div>',
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
                                logger.info(f"🔍 Extracted model '{used_model}' from {file_path.name}")
                                break
                        
                        # Extract summary type from HTML content - look for "Summary (Type)" in h2 tags
                        summary_patterns = [
                            r'📝 Summary \(([^)]+)\)',  # "📝 Summary (Comprehensive)"
                            r'Summary \(([^)]+)\)',    # "Summary (Brief)"
                        ]
                        
                        for pattern in summary_patterns:
                            summary_match = re.search(pattern, html_content, re.IGNORECASE)
                            if summary_match:
                                summary_type = summary_match.group(1).strip().title()
                                logger.info(f"🔍 Extracted summary type '{summary_type}' from {file_path.name}")
                                break
                        
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
                    
                    index_html += f"""
                <div class="report-card" data-title="{display_name}" data-time="{mtime.timestamp()}" data-filename="{file_path.name}" data-model="{used_model}" data-summary-type="{summary_type}">
                    <div class="report-header">
                        <input type="checkbox" class="report-checkbox" onchange="toggleDeleteButton()">
                        <div class="report-title">{display_name}</div>
                        <button class="card-delete-btn" onclick="deleteSingleCard('{file_path.name}')" title="Delete this report">×</button>
                    </div>
                    <div class="report-meta">
                        <div class="report-meta-item">
                            <span>🕒</span> Generated {time_ago}
                        </div>
                        <div class="report-meta-item">
                            <span>📅</span> {time_str}
                        </div>
                        <div class="report-meta-item">
                            <span>🤖</span> {used_model}
                        </div>
                        <div class="report-meta-item">
                            <span>📝</span> {summary_type}
                        </div>"""
                    
                    if youtube_url:
                        index_html += f"""
                        <div class="report-meta-item">
                            <span>📺</span> <a href="{youtube_url}" target="_blank" style="color: #ff0000; text-decoration: none;">YouTube Video</a>
                        </div>"""
                    
                    index_html += f"""
                    </div>
                    <div class="report-actions">
                        <a href="/{file_path.name}" class="btn btn-primary">📖 View Report</a>"""
                    
                    if youtube_url:
                        index_html += f"""
                        <a href="{youtube_url}" class="btn" style="background: #ff0000; color: white;" target="_blank">▶️ Watch Video</a>"""
                    
                    index_html += f"""
                    </div>
                </div>"""
                index_html += '</div>'
            else:
                index_html += """
                <div class="empty-state">
                    <div class="empty-state-icon">📭</div>
                    <h3>No Reports Available</h3>
                    <p>Generate your first YouTube summary using the Telegram bot!</p>
                    <p style="margin-top: 15px; color: #9ca3af;">Send a YouTube URL to the bot to get started.</p>
                </div>"""
            
            index_html += """
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
        // Auto-refresh every 30 seconds
        setTimeout(() => location.reload(), 30000);
        
        // Management functions
        function filterReports() {
            var searchTerm = document.getElementById('searchInput').value.toLowerCase();
            var cards = document.querySelectorAll('.report-card');
            cards.forEach(function(card) {
                var title = card.dataset.title.toLowerCase();
                var filename = card.dataset.filename.toLowerCase();
                var visible = title.includes(searchTerm) || filename.includes(searchTerm);
                card.style.display = visible ? 'block' : 'none';
            });
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
        
        function filterByModel() {
            var selectedModel = document.getElementById('modelFilter').value;
            var cards = document.querySelectorAll('.report-card');
            console.log('Selected model:', selectedModel);
            
            cards.forEach(function(card) {
                var cardModel = card.dataset.model;
                console.log('Card model:', cardModel, 'Selected:', selectedModel);
                var visible = selectedModel === 'all' || cardModel === selectedModel;
                card.style.display = visible ? 'block' : 'none';
            });
            
            // Update visible count
            var visibleCards = document.querySelectorAll('.report-card[style="display: block"], .report-card:not([style*="display: none"])');
            console.log('Visible cards after filter:', visibleCards.length);
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
            var anyChecked = Array.from(checkboxes).some(function(cb) { return cb.checked; });
            deleteBtn.disabled = !anyChecked;
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
            // Hide selected cards with animation
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
            
            // Close modal when clicking outside
            document.getElementById('deleteModal').addEventListener('click', function(e) {
                if (e.target === this) closeModal();
            });
            document.getElementById('successModal').addEventListener('click', function(e) {
                if (e.target === this) closeModal();
            });
        });
    </script>
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
        html_ttl_hours = max(1, int(os.getenv('HTML_REPORT_RETENTION_HOURS', '168')))  # 168 hours = 7 days
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
                brief_callback = self._create_safe_callback_data("process_brief", url)
                
                logger.info(f"  ✅ {url[:40]}... -> '{comprehensive_callback}' ({len(comprehensive_callback)} chars)")
                logger.info(f"     Brief: '{brief_callback}' ({len(brief_callback)} chars)")
                
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
            if summary_type_used == "brief":
                summary_message = f"""⚡ **EXECUTIVE BRIEF**
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
    
    def _generate_html_report(self, result: Dict, summary_type: str = "comprehensive") -> str:
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
            max-width: 800px;
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
        
        .video-info {{
            background: var(--surface);
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 30px;
            border-left: 4px solid var(--primary-color);
        }}
        
        .video-info h2 {{
            color: var(--primary-color);
            margin-bottom: 15px;
            font-size: 1.3em;
        }}
        
        .info-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
        }}
        
        .info-item {{
            display: flex;
            flex-direction: column;
        }}
        
        .info-label {{
            font-weight: 600;
            color: var(--text-secondary);
            font-size: 0.9em;
            margin-bottom: 5px;
        }}
        
        .info-value {{
            color: var(--text-color);
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
            
            .header {{
                padding: 20px;
            }}
            
            .content {{
                padding: 20px;
            }}
            
            .header h1 {{
                font-size: 1.5em;
            }}
            
            .info-grid {{
                grid-template-columns: 1fr;
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
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{metadata.get('title', 'YouTube Video Summary')}</h1>
            <div class="channel">{metadata.get('uploader', 'Unknown Channel')}</div>
        </div>
        
        <div class="content">
            <div class="video-info">
                <h2>📹 Video Information</h2>
                <div class="info-grid">
                    <div class="info-item">
                        <div class="info-label">Duration</div>
                        <div class="info-value">{duration_str}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Upload Date</div>
                        <div class="info-value">{formatted_date}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Views</div>
                        <div class="info-value">{metadata.get('view_count', 0):,}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">AI Model</div>
                        <div class="info-value">{model}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Summary Type</div>
                        <div class="info-value">{summary_type.title()}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Video URL</div>
                        <div class="info-value">
                            <a href="{metadata.get('url', '#')}" class="url-link" target="_blank">
                                Watch on YouTube
                            </a>
                        </div>
                    </div>
                </div>
            </div>
            
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
            
            # Add navigation section - use NGROK URL for consistency
            base_url = os.getenv('WEB_BASE_URL', 'https://chief-inspired-lab.ngrok-free.app')
            
            # If environment variable exists but doesn't have protocol, add https://
            if base_url and not base_url.startswith('http'):
                base_url = f'https://{base_url}'
            
            # Ensure we're using NGROK for external access
            if 'ngrok-free.app' not in base_url:
                base_url = 'https://chief-inspired-lab.ngrok-free.app'
            
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
• ⚡ **Quick Summary** - Executive brief (~120–180 words)
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
• **⚡ Quick Summary** - Executive brief (~120–180 words)
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
            brief_callback = self._create_safe_callback_data("process_brief", youtube_url)
            adaptive_callback = self._create_safe_callback_data("process_adaptive", youtube_url)
            
            # Log callback data for debugging
            logger.info(f"Created callback data - Comprehensive: '{comprehensive_callback}' ({len(comprehensive_callback)} chars)")
            logger.info(f"Created callback data - Brief: '{brief_callback}' ({len(brief_callback)} chars)")
            logger.info(f"Created callback data - Adaptive: '{adaptive_callback}' ({len(adaptive_callback)} chars)")
            
            keyboard = [
                [
                    InlineKeyboardButton("📝 Full Summary", callback_data=comprehensive_callback),
                    InlineKeyboardButton("⚡ Quick Summary", callback_data=brief_callback)
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
                        brief_callback = self._create_safe_callback_data("process_brief", self.last_video_url) 
                        adaptive_callback = self._create_safe_callback_data("process_adaptive", self.last_video_url)
                        
                        # Create the summary selection keyboard directly
                        keyboard = [
                            [
                                InlineKeyboardButton("📝 Full Summary", callback_data=comprehensive_callback),
                                InlineKeyboardButton("⚡ Quick Summary", callback_data=brief_callback)
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
                f"**⏰ Note:** Reports expire after {max(1, int(os.getenv('HTML_REPORT_RETENTION_HOURS', '168')))} hours\n\n" +
                "**👆 Click the button above to open the report**",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard,
                disable_web_page_preview=True
            )
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
                error_message = f"""❌ **Processing Failed**

Error: {result['error']}

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
            
            # Generate HTML report
            html_filepath = self._generate_html_report(result, summary_type)
            
            # Create regeneration buttons for different summary types using the same YouTube URL
            regen_buttons = []
            try:
                # Create new callback data for regeneration buttons
                regen_comprehensive_callback = self._create_safe_callback_data("process_comprehensive", youtube_url)
                regen_brief_callback = self._create_safe_callback_data("process_brief", youtube_url)
                regen_adaptive_callback = self._create_safe_callback_data("process_adaptive", youtube_url)
                
                if summary_type != "comprehensive":
                    regen_buttons.append(InlineKeyboardButton("📝 Full Summary", callback_data=regen_comprehensive_callback))
                if summary_type != "brief":
                    regen_buttons.append(InlineKeyboardButton("⚡ Quick Summary", callback_data=regen_brief_callback))
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