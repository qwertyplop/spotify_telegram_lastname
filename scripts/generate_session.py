#!/usr/bin/env python3
"""
Generate Telegram StringSession for Vercel deployment.

Run this script LOCALLY before deploying to Vercel.
It requires interactive authentication (phone + code).

Usage:
    1. Set environment variables:
       export TELEGRAM_API_ID=your_api_id
       export TELEGRAM_API_HASH=your_api_hash

    2. Run this script:
       python scripts/generate_session.py

    3. Copy the output StringSession to Vercel environment variables.
"""

import os
import sys
from getpass import getpass

try:
    from telethon.sync import TelegramClient
    from telethon.sessions import StringSession
    from telethon.errors import SessionPasswordNeededError
except ImportError:
    print("Error: telethon is not installed.")
    print("Install it with: pip install telethon")
    sys.exit(1)


def main():
    print("=" * 60)
    print("Telegram StringSession Generator")
    print("=" * 60)
    print()

    # Get credentials
    api_id = os.environ.get('TELEGRAM_API_ID')
    api_hash = os.environ.get('TELEGRAM_API_HASH')

    if not api_id:
        api_id = input("Enter your Telegram API ID: ").strip()

    if not api_hash:
        api_hash = input("Enter your Telegram API Hash: ").strip()

    if not api_id or not api_hash:
        print("Error: API ID and API Hash are required.")
        print("Get them from https://my.telegram.org")
        sys.exit(1)

    try:
        api_id = int(api_id)
    except ValueError:
        print("Error: API ID must be a number.")
        sys.exit(1)

    print()
    print("Starting Telegram authentication...")
    print("You will need to enter your phone number and verification code.")
    print()

    try:
        # Create client with empty StringSession
        with TelegramClient(StringSession(), api_id, api_hash) as client:
            # Get user info to verify connection
            me = client.get_me()
            print()
            print(f"Logged in as: {me.first_name} {me.last_name or ''} (@{me.username or 'N/A'})")
            print()

            # Save and output the session string
            session_string = client.session.save()

            print("=" * 60)
            print("SUCCESS! Copy the following StringSession:")
            print("=" * 60)
            print()
            print(session_string)
            print()
            print("=" * 60)
            print()
            print("Add this to your Vercel environment variables as:")
            print("TELEGRAM_STRING_SESSION=<the string above>")
            print()
            print("IMPORTANT: Keep this string secret! It provides full")
            print("access to your Telegram account.")
            print()

    except SessionPasswordNeededError:
        print()
        print("Two-step verification is enabled.")
        password = getpass("Enter your 2FA password: ")

        with TelegramClient(StringSession(), api_id, api_hash) as client:
            client.sign_in(password=password)
            me = client.get_me()
            print()
            print(f"Logged in as: {me.first_name} {me.last_name or ''}")

            session_string = client.session.save()
            print()
            print("=" * 60)
            print("SUCCESS! Copy the following StringSession:")
            print("=" * 60)
            print()
            print(session_string)
            print()

    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
