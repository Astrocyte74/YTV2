#!/usr/bin/env python3
"""
Helper script to get Telegram user IDs for YTV2 Bot configuration

This script provides instructions for finding Telegram user IDs
and shows how to configure them in the .env file.
"""

import os
from pathlib import Path


def main():
    print("=" * 60)
    print("🤖 YTV2 Telegram Bot - User ID Helper")
    print("=" * 60)
    print()
    
    print("📋 How to Get Your Telegram User ID:")
    print("   1. Open Telegram on your phone or computer")
    print("   2. Search for: @userinfobot")
    print("   3. Start a chat with @userinfobot")
    print("   4. Send any message (like 'hi')")
    print("   5. The bot will reply with your user information")
    print("   6. Copy the 'Id' number (e.g., 8350044022)")
    print()
    
    print("⚙️  Configuration:")
    print("   Your user ID is already configured: 8350044022")
    print()
    
    # Check if .env file exists
    env_file = Path(".env")
    if env_file.exists():
        print("✅ .env file found")
        try:
            with open(env_file) as f:
                content = f.read()
                if "TELEGRAM_ALLOWED_USERS" in content:
                    # Extract current users
                    for line in content.split('\n'):
                        if line.startswith('TELEGRAM_ALLOWED_USERS=') and not line.startswith('#'):
                            users = line.split('=')[1].strip()
                            if users and users != 'your-bot-token-here':
                                print(f"   Current allowed users: {users}")
                                break
                    else:
                        print("   ⚠️  No users configured yet")
                else:
                    print("   ⚠️  TELEGRAM_ALLOWED_USERS not found in .env")
        except Exception as e:
            print(f"   ⚠️  Error reading .env: {e}")
    else:
        print("❌ .env file not found")
        print("   Run: cp .env.template .env")
    
    print()
    print("📝 To Add More Users:")
    print("   Edit .env file and update TELEGRAM_ALLOWED_USERS:")
    print("   TELEGRAM_ALLOWED_USERS=8350044022,friend_id,another_id")
    print()
    
    print("🚀 Next Steps:")
    if not env_file.exists():
        print("   1. Copy template: cp .env.template .env")
        print("   2. Get bot token from @BotFather on Telegram")
        print("   3. Add your API keys (OpenAI/Anthropic)")
        print("   4. Run: python telegram_bot.py")
    else:
        print("   1. Get bot token from @BotFather (if not done)")
        print("   2. Add your API keys to .env (if not done)")
        print("   3. Run: python telegram_bot.py")
        print("   4. Send YouTube URLs to your bot!")
    
    print()
    print("🌐 Dashboard will be available at: http://localhost:6452")
    print("=" * 60)


if __name__ == "__main__":
    main()