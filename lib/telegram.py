"""
Telegram API helpers for updating user profile.
"""

import os
import asyncio
from typing import Optional

from telethon import TelegramClient, functions
from telethon.sessions import StringSession
from telethon.errors import FloodWaitError, SessionExpiredError, AuthKeyError


def get_credentials() -> tuple:
    """Get Telegram credentials from environment."""
    api_id = os.environ.get('TELEGRAM_API_ID')
    api_hash = os.environ.get('TELEGRAM_API_HASH')

    if not api_id or not api_hash:
        raise RuntimeError("TELEGRAM_API_ID and TELEGRAM_API_HASH required")

    return int(api_id), api_hash


async def get_client(session_string: str) -> TelegramClient:
    """
    Create and connect a Telegram client using StringSession.

    Args:
        session_string: Telethon StringSession string

    Returns:
        Connected TelegramClient

    Raises:
        RuntimeError: If session is invalid
    """
    api_id, api_hash = get_credentials()

    client = TelegramClient(
        StringSession(session_string),
        api_id,
        api_hash,
    )

    await client.connect()

    if not await client.is_user_authorized():
        await client.disconnect()
        raise RuntimeError("Telegram session expired or invalid")

    return client


async def get_last_name(session_string: str) -> str:
    """
    Get current user's last name.

    Args:
        session_string: Telethon StringSession string

    Returns:
        Current last name
    """
    client = await get_client(session_string)
    try:
        me = await client.get_me()
        return me.last_name or ""
    finally:
        await client.disconnect()


async def set_last_name(session_string: str, last_name: str) -> None:
    """
    Update user's last name.

    Args:
        session_string: Telethon StringSession string
        last_name: New last name to set

    Raises:
        FloodWaitError: If rate limited (with .seconds attribute)
        RuntimeError: If session is invalid
    """
    client = await get_client(session_string)
    try:
        await client(functions.account.UpdateProfileRequest(last_name=last_name))
    finally:
        await client.disconnect()


async def update_last_name_safe(
    session_string: str,
    last_name: str,
) -> tuple[bool, Optional[int]]:
    """
    Safely update Telegram last name with error handling.

    Args:
        session_string: Telethon StringSession string
        last_name: New last name to set

    Returns:
        Tuple of (success, flood_wait_seconds)
        - (True, None) on success
        - (False, seconds) if rate limited
        - (False, None) on other errors
    """
    try:
        await set_last_name(session_string, last_name)
        return True, None
    except FloodWaitError as e:
        wait_seconds = getattr(e, 'seconds', 300)
        print(f"Telegram rate limit: {wait_seconds}s")
        return False, wait_seconds
    except (SessionExpiredError, AuthKeyError) as e:
        print(f"Telegram session error: {e}")
        raise RuntimeError("Telegram session expired")
    except Exception as e:
        print(f"Telegram update error: {e}")
        return False, None


def run_async(coro):
    """Run async function in sync context."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(coro)
