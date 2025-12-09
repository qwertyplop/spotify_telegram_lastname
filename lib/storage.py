"""
Vercel Blob storage wrapper for persisting sync state.
"""

import json
import os
import time
from typing import Optional, Any
from urllib.request import Request, urlopen
from urllib.error import URLError


BLOB_BASE_URL = "https://blob.vercel-storage.com"
BLOB_PREFIX = "spotify-telegram"


def _get_token() -> str:
    """Get Blob read/write token from environment."""
    token = os.environ.get("BLOB_READ_WRITE_TOKEN")
    if not token:
        raise RuntimeError("BLOB_READ_WRITE_TOKEN not set")
    return token


def _blob_url(key: str) -> str:
    """Construct full blob URL for a key."""
    return f"{BLOB_BASE_URL}/{BLOB_PREFIX}/{key}"


def put_json(key: str, data: Any) -> bool:
    """
    Store JSON data in Vercel Blob.

    Args:
        key: Storage key (e.g., 'state.json')
        data: Data to serialize and store

    Returns:
        True if successful, False otherwise
    """
    try:
        token = _get_token()
        payload = json.dumps(data).encode('utf-8')

        req = Request(
            f"{BLOB_BASE_URL}",
            data=payload,
            method='PUT',
            headers={
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
                'x-api-version': '7',
                'x-content-type': 'application/json',
                'x-add-random-suffix': 'false',
                'x-pathname': f'{BLOB_PREFIX}/{key}',
            }
        )

        with urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"Blob put error: {e}")
        return False


def get_json(key: str) -> Optional[Any]:
    """
    Retrieve JSON data from Vercel Blob.

    Args:
        key: Storage key (e.g., 'state.json')

    Returns:
        Parsed JSON data or None if not found/error
    """
    try:
        token = _get_token()
        url = _blob_url(key)

        req = Request(
            url,
            method='GET',
            headers={
                'Authorization': f'Bearer {token}',
            }
        )

        with urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                return json.loads(resp.read().decode('utf-8'))
    except URLError as e:
        if hasattr(e, 'code') and e.code == 404:
            return None
        print(f"Blob get error: {e}")
    except Exception as e:
        print(f"Blob get error: {e}")

    return None


def delete_blob(key: str) -> bool:
    """
    Delete a blob from Vercel Blob storage.

    Args:
        key: Storage key to delete

    Returns:
        True if successful, False otherwise
    """
    try:
        token = _get_token()
        url = _blob_url(key)

        req = Request(
            url,
            method='DELETE',
            headers={
                'Authorization': f'Bearer {token}',
            }
        )

        with urlopen(req, timeout=10) as resp:
            return resp.status in (200, 204)
    except Exception as e:
        print(f"Blob delete error: {e}")
        return False


# Convenience functions for specific data types

def get_session() -> Optional[str]:
    """Get Telegram StringSession from storage."""
    data = get_json('session.json')
    if data:
        return data.get('telegram_session')
    # Fall back to environment variable
    return os.environ.get('TELEGRAM_STRING_SESSION')


def save_session(session: str) -> bool:
    """Save Telegram StringSession to storage."""
    return put_json('session.json', {'telegram_session': session})


def get_tokens() -> Optional[dict]:
    """Get Spotify tokens from storage."""
    return get_json('tokens.json')


def save_tokens(access_token: str, refresh_token: str, expires_at: float) -> bool:
    """Save Spotify tokens to storage."""
    return put_json('tokens.json', {
        'access_token': access_token,
        'refresh_token': refresh_token,
        'expires_at': expires_at,
    })


def get_state() -> dict:
    """Get sync state from storage."""
    data = get_json('state.json')
    return data or {
        'original_last_name': '',
        'current_last_name': '',
        'last_track_key': None,
        'last_update': 0,
        'update_count': 0,
        'last_sync': 0,
        'status': 'initialized',
    }


def save_state(state: dict) -> bool:
    """Save sync state to storage."""
    state['last_sync'] = time.time()
    return put_json('state.json', state)


def get_current_track() -> Optional[dict]:
    """Get current track info from storage."""
    return get_json('track.json')


def save_current_track(track: Optional[dict]) -> bool:
    """Save current track info to storage."""
    if track:
        track['timestamp'] = time.time()
    return put_json('track.json', track or {'is_playing': False, 'timestamp': time.time()})


def get_errors() -> list:
    """Get error log from storage."""
    return get_json('errors.json') or []


def log_error(error: str, context: str) -> bool:
    """Add error to error log (keeps last 10)."""
    errors = get_errors()
    errors.insert(0, {
        'timestamp': time.time(),
        'error': str(error),
        'context': context,
    })
    errors = errors[:10]  # Keep only last 10
    return put_json('errors.json', errors)


def get_flood_wait_until() -> float:
    """Get Telegram flood wait expiry time."""
    data = get_json('flood_wait.json')
    return data.get('until', 0) if data else 0


def set_flood_wait_until(until: float) -> bool:
    """Set Telegram flood wait expiry time."""
    return put_json('flood_wait.json', {'until': until})
