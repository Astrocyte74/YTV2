#!/usr/bin/env python3
"""
YouTube Video Summarizer CLI
Simple, clean command-line tool for AI-powered YouTube video summarization
"""

import sys
import os

def main():
    """Main entry point that determines whether to run CLI or Telegram bot"""
    # Check if we should run the Telegram bot instead of CLI
    if os.getenv('RUN_TELEGRAM_BOT', '').lower() in ('true', '1', 'yes'):
        from telegram_bot import main as telegram_main
        return telegram_main()
    else:
        # Run the CLI version
        from cli import main as cli_main
        return cli_main()

if __name__ == "__main__":
    sys.exit(main())