"""
YTV2-Dashboard Modules Package

This package contains components for the dashboard/web interface portion of YTV2.
This is dashboard-only code - no Telegram bot or processing logic.
"""

from .report_generator import JSONReportGenerator, create_report_from_youtube_summarizer

__all__ = ['JSONReportGenerator', 'create_report_from_youtube_summarizer']