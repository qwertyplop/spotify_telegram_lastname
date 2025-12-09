#!/usr/bin/env python3
"""
Convert existing Telethon session file to StringSession.

This script reads your existing .session file and outputs
a StringSession string that can be used in serverless environments.

Usage:
    python scripts/convert_session.py [session_name]

    session_name: Name of the session file without .session extension
                  Default: spotify_persistent
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from telethon.sync import TelegramClient
    from telethon.sessions import StringSession
except ImportError:
    print("Error: telethon is not installed.")
    print("Install it with: pip install telethon")
    sys.exit(1)


def main():
    # Get session name from args or use default
    session_name = sys.argv[1] if len(sys.argv) > 1 else "spotify_persistent"

    # Check if session file exists
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    session_file = os.path.join(project_dir, f"{session_name}.session")

    if not os.path.exists(session_file):
        print(f"Error: Session file not found: {session_file}")
        print()
        print("Available session files:")
        for f in os.listdir(project_dir):
            if f.endswith('.session'):
                print(f"  - {f.replace('.session', '')}")
        sys.exit(1)

    print("=" * 60)
    print("Telethon Session Converter")
    print("=" * 60)
    print()
    print(f"Converting: {session_name}.session")
    print()

    # Get credentials from environment or ask
    api_id = os.environ.get('TELEGRAM_API_ID')
    api_hash = os.environ.get('TELEGRAM_API_HASH')

    if not api_id:
        api_id = input("Enter your Telegram API ID: ").strip()
    if not api_hash:
        api_hash = input("Enter your Telegram API Hash: ").strip()

    try:
        api_id = int(api_id)
    except ValueError:
        print("Error: API ID must be a number.")
        sys.exit(1)

    print()
    print("Connecting to Telegram...")

    try:
        # Connect using existing session file
        with TelegramClient(session_name, api_id, api_hash) as client:
            # Verify we're logged in
            if not client.is_user_authorized():
                print("Error: Session is not authorized. You may need to re-authenticate.")
                sys.exit(1)

            me = client.get_me()
            print(f"Logged in as: {me.first_name} {me.last_name or ''} (@{me.username or 'N/A'})")
            print()

            # Export to StringSession
            string_session = StringSession.save(client.session)

            print("=" * 60)
            print("SUCCESS! Your StringSession:")
            print("=" * 60)
            print()
            print(string_session)
            print()
            print("=" * 60)
            print()
            print("Add this to your Vercel environment variables as:")
            print("TELEGRAM_STRING_SESSION=<the string above>")
            print()
            print("Or save to .env file:")
            print(f'TELEGRAM_STRING_SESSION="{string_session}"')
            print()

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
