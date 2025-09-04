"""
Telegram Bot Handler Module

This module contains the YouTubeTelegramBot class extracted from the monolithic file.
It handles all Telegram bot interactions without embedded HTML generation.
"""

import asyncio
import json
import logging
import os
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.constants import ParseMode

from export_utils import SummaryExporter
from modules.report_generator import JSONReportGenerator

from youtube_summarizer import YouTubeSummarizer
from llm_config import llm_config


class YouTubeTelegramBot:
    """Telegram bot for YouTube video summarization."""
    
    def __init__(self, token: str, allowed_user_ids: List[int]):
        """
        Initialize the Telegram bot.
        
        Args:
            token: Telegram bot token
            allowed_user_ids: List of user IDs allowed to use the bot
        """
        self.token = token
        self.allowed_user_ids = set(allowed_user_ids)
        self.application = None
        self.summarizer = None
        self.last_video_url = None
        
        # Initialize exporters
        self.html_exporter = SummaryExporter("./exports")
        self.json_exporter = JSONReportGenerator("./data/reports")
        
        # YouTube URL regex pattern
        self.youtube_url_pattern = re.compile(
            r'(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/|youtube\.com/v/)([a-zA-Z0-9_-]{11})'
        )
        
        # Telegram message length limit
        self.MAX_MESSAGE_LENGTH = 4096
        
        # Cache for URLs
        self.url_cache = {}
        self.CACHE_TTL = 3600  # 1 hour TTL for cached URLs
        
        # Initialize summarizer
        try:
            llm_config.load_environment()
            self.summarizer = YouTubeSummarizer()
            logging.info(f"✅ YouTube summarizer initialized with {self.summarizer.llm_provider}/{self.summarizer.model}")
        except Exception as e:
            logging.error(f"Failed to initialize YouTubeSummarizer: {e}")
    
    def setup_handlers(self):
        """Set up bot command and message handlers."""
        if not self.application:
            return
            
        # Command handlers
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        
        # Message handlers
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Callback query handler for inline keyboards
        self.application.add_handler(CallbackQueryHandler(self.handle_callback_query))
        
        # Error handler
        self.application.add_error_handler(self.error_handler)
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        user_id = update.effective_user.id
        user_name = update.effective_user.first_name or "Unknown"
        
        if not self._is_user_allowed(user_id):
            await update.message.reply_text("❌ You are not authorized to use this bot.")
            logging.warning(f"Unauthorized access attempt by user {user_id} ({user_name})")
            return
        
        welcome_message = (
            f"🎬 Welcome to the YouTube Summarizer Bot, {user_name}!\n\n"
            "Send me a YouTube URL and I'll provide:\n"
            "• 🤖 AI-powered summary\n"
            "• 🎯 Key insights and takeaways\n"
            "• 📊 Content analysis\n\n"
            "Use /help for more commands."
        )
        
        await update.message.reply_text(welcome_message)
        logging.info(f"User {user_id} ({user_name}) started the bot")
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        user_id = update.effective_user.id
        
        if not self._is_user_allowed(user_id):
            await update.message.reply_text("❌ You are not authorized to use this bot.")
            return
        
        help_message = (
            "🤖 YouTube Summarizer Bot Commands:\n\n"
            "/start - Start using the bot\n"
            "/help - Show this help message\n"
            "/status - Check bot and API status\n\n"
            "📝 How to use:\n"
            "1. Send a YouTube URL\n"
            "2. Choose summary type\n"
            "3. Get AI-powered insights\n\n"
            "Supported formats:\n"
            "• youtube.com/watch?v=...\n"
            "• youtu.be/...\n"
            "• m.youtube.com/..."
        )
        
        await update.message.reply_text(help_message)
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command."""
        user_id = update.effective_user.id
        
        if not self._is_user_allowed(user_id):
            await update.message.reply_text("❌ You are not authorized to use this bot.")
            return
        
        # Check summarizer status
        summarizer_status = "✅ Ready" if self.summarizer else "❌ Not initialized"
        
        # Check LLM configuration
        try:
            llm_status = f"✅ {self.summarizer.llm_provider}/{self.summarizer.model}" if self.summarizer else "❌ Not configured"
        except Exception:
            llm_status = "❌ LLM not configured"
        
        status_message = (
            "📊 Bot Status:\n\n"
            f"🤖 Telegram Bot: ✅ Running\n"
            f"🔍 Summarizer: {summarizer_status}\n"
            f"🧠 LLM: {llm_status}\n"
            f"👥 Authorized Users: {len(self.allowed_user_ids)}"
        )
        
        await update.message.reply_text(status_message)
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming messages with YouTube URLs."""
        user_id = update.effective_user.id
        user_name = update.effective_user.first_name or "Unknown"
        
        if not self._is_user_allowed(user_id):
            await update.message.reply_text("❌ You are not authorized to use this bot.")
            return
        
        message_text = update.message.text.strip()
        logging.info(f"Received message from {user_name} ({user_id}): {message_text[:100]}...")
        
        # Check if message contains YouTube URL
        youtube_match = self.youtube_url_pattern.search(message_text)
        
        if not youtube_match:
            await update.message.reply_text(
                "🔍 Please send a YouTube URL to get started.\n\n"
                "Supported formats:\n"
                "• https://youtube.com/watch?v=...\n"
                "• https://youtu.be/...\n"
                "• https://m.youtube.com/watch?v=..."
            )
            return
        
        # Extract and clean URL
        video_url = self._extract_youtube_url(message_text)
        if not video_url:
            await update.message.reply_text("❌ Could not extract a valid YouTube URL from your message.")
            return
        
        # Store the URL for potential model switching
        self.last_video_url = video_url
        
        # Send processing message with options
        keyboard = [
            [
                InlineKeyboardButton("📝 Comprehensive", callback_data="summarize_comprehensive"),
                InlineKeyboardButton("🎯 Key Points", callback_data="summarize_bullet-points")
            ],
            [
                InlineKeyboardButton("💡 Insights", callback_data="summarize_key-insights"),
                InlineKeyboardButton("🎙️ Audio Summary", callback_data="summarize_audio")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"🎬 Processing YouTube video...\n\n"
            f"Choose your summary type:",
            reply_markup=reply_markup
        )
    
    async def handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle callback queries from inline keyboards."""
        query = update.callback_query
        await query.answer()
        
        user_id = query.from_user.id
        user_name = query.from_user.first_name or "Unknown"
        
        if not self._is_user_allowed(user_id):
            await query.edit_message_text("❌ You are not authorized to use this bot.")
            return
        
        callback_data = query.data
        
        # Handle summary requests
        if callback_data.startswith("summarize_"):
            summary_type = callback_data.replace("summarize_", "")
            await self._process_video_summary(query, summary_type, user_name)
        else:
            await query.edit_message_text("❌ Unknown option selected.")
    
    async def _process_video_summary(self, query, summary_type: str, user_name: str):
        """Process video summarization request."""
        if not self.last_video_url:
            await query.edit_message_text("❌ No YouTube URL found. Please send a URL first.")
            return
        
        if not self.summarizer:
            await query.edit_message_text("❌ Summarizer not available. Please try /status for more info.")
            return
        
        # Update message to show processing
        await query.edit_message_text(f"🔄 Creating {summary_type} summary... This may take a moment.")
        
        try:
            # Process the video
            logging.info(f"Processing {self.last_video_url} with {summary_type} summary for {user_name}")
            
            result = await self.summarizer.process_video(
                self.last_video_url,
                summary_type=summary_type
            )
            
            if not result:
                await query.edit_message_text("❌ Failed to process video. Please check the URL and try again.")
                return
            
            # Export to JSON and HTML for dashboard
            export_info = {"html_path": None, "json_path": None}
            try:
                # Export to JSON (preferred format)
                json_path = self.json_exporter.save_report(result)
                export_info["json_path"] = Path(json_path).name
                logging.info(f"✅ Exported JSON report: {json_path}")
                
                # Export to HTML (for dashboard compatibility)  
                html_path = self.html_exporter.export_to_html(result)
                export_info["html_path"] = Path(html_path).name
                logging.info(f"✅ Exported HTML report: {html_path}")
                
            except Exception as e:
                logging.warning(f"⚠️ Export failed: {e}")
            
            # Format and send the response
            await self._send_formatted_response(query, result, summary_type, export_info)
            
        except Exception as e:
            logging.error(f"Error processing video {self.last_video_url}: {e}")
            await query.edit_message_text(f"❌ Error processing video: {str(e)[:100]}...")
    
    async def _send_formatted_response(self, query, result: Dict[str, Any], summary_type: str, export_info: Dict = None):
        """Send formatted summary response."""
        try:
            # Get video metadata
            video_info = result.get('metadata', {})
            title = video_info.get('title', 'Unknown Title')
            channel = video_info.get('uploader', 'Unknown Channel')
            duration_info = self._format_duration_and_savings(video_info)
            
            # Get summary content - extract the text from the summary dictionary
            summary_data = result.get('summary', {})
            if isinstance(summary_data, dict):
                summary = summary_data.get('summary', 'No summary available')
            else:
                summary = summary_data or 'No summary available'
            
            # Always send text summary first for better UX
            # (For audio summaries, TTS will be generated separately below)
            
            # Truncate if too long for Telegram
            if len(summary) > 1000:
                summary = summary[:1000] + "..."
            
            # Format response
            response_parts = [
                f"🎬 **{self._escape_markdown(title)}**",
                f"📺 {self._escape_markdown(channel)}",
                duration_info,
                "",
                f"📝 **{summary_type.replace('-', ' ').title()} Summary:**",
                summary
            ]
            
            # Add dashboard links if exports were successful
            if export_info and (export_info.get('html_path') or export_info.get('json_path')):
                web_port = os.getenv('WEB_PORT', '6452')
                base_url = f"http://localhost:{web_port}"
                
                links = []
                links.append(f"📊 [Dashboard]({base_url})")
                
                if export_info.get('html_path'):
                    html_filename = export_info['html_path']
                    links.append(f"🔗 [Full Report]({base_url}/exports/{html_filename})")
                
                response_parts.extend(["", "📱 **Links:**", " • ".join(links)])
            
            response_text = "\n".join(response_parts)
            
            # Send response
            await query.edit_message_text(response_text, parse_mode=ParseMode.MARKDOWN)
            
            logging.info(f"Successfully sent {summary_type} summary for {title}")
            
            # Generate TTS audio for audio summaries (after text is sent)
            if summary_type == "audio":
                await self._generate_and_send_tts(query, result, summary)
            
        except Exception as e:
            logging.error(f"Error sending formatted response: {e}")
            await query.edit_message_text("❌ Error formatting response. The summary was generated but couldn't be displayed properly.")
    
    async def _generate_and_send_tts(self, query, result: Dict[str, Any], summary_text: str):
        """Generate TTS audio and send as voice message (separate from text summary)."""
        try:
            # Get video metadata  
            video_info = result.get('metadata', {})
            title = video_info.get('title', 'Unknown Title')
            
            # Generate TTS audio
            from datetime import datetime
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            video_id = video_info.get('video_id', 'unknown')
            audio_filename = f"audio_{video_id}_{timestamp}.mp3"
            
            # Generate the audio file
            logging.info(f"🎙️ Generating TTS audio for: {title}")
            audio_filepath = await self.summarizer.generate_tts_audio(summary_text, audio_filename)
            
            if audio_filepath and Path(audio_filepath).exists():
                # Send the audio as a voice message
                try:
                    with open(audio_filepath, 'rb') as audio_file:
                        await query.message.reply_voice(
                            voice=audio_file,
                            caption=f"🎧 **Audio Summary**: {self._escape_markdown(title)}\n"
                                   f"🎵 Generated with OpenAI TTS",
                            parse_mode=ParseMode.MARKDOWN
                        )
                    logging.info(f"✅ Successfully sent audio summary for: {title}")
                    
                except Exception as e:
                    logging.error(f"❌ Failed to send voice message: {e}")
            else:
                logging.warning("⚠️ TTS generation failed")
                
        except Exception as e:
            logging.error(f"Error generating TTS audio: {e}")
    
    def _format_duration_and_savings(self, metadata: Dict) -> str:
        """Format video duration and calculate time savings from summary."""
        duration = metadata.get('duration', 0)
        
        if duration:
            # Format original duration
            hours = duration // 3600
            minutes = (duration % 3600) // 60
            seconds = duration % 60
            
            if hours > 0:
                duration_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            else:
                duration_str = f"{minutes:02d}:{seconds:02d}"
            
            # Calculate time savings (typical summary reading time is 2-3 minutes)
            reading_time_seconds = 180  # 3 minutes average
            if duration > reading_time_seconds:
                time_saved = duration - reading_time_seconds
                saved_hours = time_saved // 3600
                saved_minutes = (time_saved % 3600) // 60
                
                if saved_hours > 0:
                    savings_str = f"{saved_hours:02d}:{saved_minutes:02d}:00"
                else:
                    savings_str = f"{saved_minutes:02d}:{time_saved % 60:02d}"
                
                return f"⏱️ **Duration**: {duration_str} → ~3 min read (⏰ Saves {savings_str})"
            else:
                return f"⏱️ **Duration**: {duration_str}"
        else:
            return f"⏱️ **Duration**: Unknown"
    
    def _extract_youtube_url(self, text: str) -> Optional[str]:
        """Extract YouTube URL from text."""
        match = self.youtube_url_pattern.search(text)
        if match:
            video_id = match.group(1)
            return f"https://www.youtube.com/watch?v={video_id}"
        return None
    
    def _is_user_allowed(self, user_id: int) -> bool:
        """Check if user is allowed to use the bot."""
        return user_id in self.allowed_user_ids
    
    async def _handle_audio_summary(self, query, result: Dict[str, Any], summary_type: str):
        """Handle audio summary generation with TTS."""
        try:
            # Get video metadata
            video_info = result.get('metadata', {})
            title = video_info.get('title', 'Unknown Title')
            channel = video_info.get('uploader', 'Unknown Channel')
            
            # Get summary content - extract the text from the summary dictionary
            summary_data = result.get('summary', {})
            if isinstance(summary_data, dict):
                summary = summary_data.get('summary', 'No summary available')
            else:
                summary = summary_data or 'No summary available'
            
            # Update status to show TTS generation
            await query.edit_message_text(f"🎙️ Generating audio summary... Creating TTS audio file.")
            
            # Generate TTS audio
            from datetime import datetime
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            video_id = video_info.get('video_id', 'unknown')
            audio_filename = f"audio_{video_id}_{timestamp}.mp3"
            
            # Generate the audio file
            audio_filepath = await self.summarizer.generate_tts_audio(summary, audio_filename)
            
            if audio_filepath and Path(audio_filepath).exists():
                # Send the audio as a voice message
                try:
                    with open(audio_filepath, 'rb') as audio_file:
                        await query.message.reply_voice(
                            voice=audio_file,
                            caption=f"🎧 **Audio Summary**: {self._escape_markdown(title)}\n"
                                   f"📺 **Channel**: {self._escape_markdown(channel)}\n\n"
                                   f"🎵 Generated with OpenAI TTS",
                            parse_mode=ParseMode.MARKDOWN
                        )
                    
                    # Also send the text summary
                    text_summary = summary
                    if len(text_summary) > 1000:
                        text_summary = text_summary[:1000] + "..."
                    
                    response_text = f"🎙️ **Audio Summary Generated**\n\n" \
                                  f"📝 **Text Version:**\n{text_summary}\n\n" \
                                  f"✅ Voice message sent above!"
                    
                    await query.edit_message_text(
                        response_text,
                        parse_mode=ParseMode.MARKDOWN
                    )
                    
                    logging.info(f"✅ Successfully sent audio summary for: {title}")
                    
                except Exception as e:
                    logging.error(f"❌ Failed to send voice message: {e}")
                    # Ensure summary is a string for slicing
                    summary_text = str(summary) if summary else "No summary available"
                    await query.edit_message_text(
                        f"❌ Generated audio but failed to send voice message.\n\n"
                        f"**Text Summary:**\n{summary_text[:1000]}{'...' if len(summary_text) > 1000 else ''}"
                    )
            else:
                # TTS generation failed, send text only
                logging.warning("⚠️ TTS generation failed, sending text only")
                # Ensure summary is a string for slicing
                summary_text = str(summary) if summary else "No summary available"
                response_text = f"🎙️ **Audio Summary** (TTS failed)\n\n" \
                              f"🎬 **{self._escape_markdown(title)}**\n" \
                              f"📺 **Channel**: {self._escape_markdown(channel)}\n\n" \
                              f"📝 **Summary:**\n{summary_text[:1000]}{'...' if len(summary_text) > 1000 else ''}\n\n" \
                              f"⚠️ Audio generation failed. Check TTS configuration."
                
                await query.edit_message_text(
                    response_text,
                    parse_mode=ParseMode.MARKDOWN
                )
                
        except Exception as e:
            logging.error(f"Error handling audio summary: {e}")
            await query.edit_message_text(f"❌ Error generating audio summary: {str(e)[:100]}...")
    
    def _escape_markdown(self, text: str) -> str:
        """Escape special characters for Markdown V2."""
        if not text:
            return ""
        
        # For Markdown, we need to escape these characters
        escape_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        
        escaped_text = text
        for char in escape_chars:
            escaped_text = escaped_text.replace(char, f'\\{char}')
        
        return escaped_text
    
    async def error_handler(self, update: object, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors in the bot."""
        logging.error(f"Exception while handling an update: {context.error}")
        
        # Try to send error message to user if possible
        try:
            if isinstance(update, Update) and update.effective_message:
                await update.effective_message.reply_text(
                    "❌ An error occurred while processing your request. Please try again."
                )
        except Exception:
            pass  # Don't let error handling cause more errors
    
    async def run(self):
        """Start the bot."""
        try:
            self.application = Application.builder().token(self.token).build()
            self.setup_handlers()
            
            logging.info("🚀 Starting Telegram bot...")
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling()
            
            logging.info("✅ Telegram bot is running and listening for messages")
            
            # Keep the bot running
            try:
                import signal
                stop_event = asyncio.Event()
                
                def signal_handler(signum, frame):
                    stop_event.set()
                
                signal.signal(signal.SIGINT, signal_handler)
                signal.signal(signal.SIGTERM, signal_handler)
                
                await stop_event.wait()
            except KeyboardInterrupt:
                pass
            
        except Exception as e:
            logging.error(f"Error running bot: {e}")
            raise
        finally:
            if self.application:
                await self.application.stop()
    
    async def stop(self):
        """Stop the bot."""
        if self.application:
            logging.info("🛑 Stopping Telegram bot...")
            await self.application.stop()
            logging.info("✅ Telegram bot stopped")