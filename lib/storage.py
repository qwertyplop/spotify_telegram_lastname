"""
Vercel Blob storage wrapper for persisting sync state.
Uses the vercel_blob package.
"""

import json
import os
import time
from typing import Optional, Any

try:
    import vercel_blob
    BLOB_AVAILABLE = True
except ImportError:
    BLOB_AVAILABLE = False


def _get_token() -> Optional[str]:
    """Get Blob read/write token from environment."""
    return os.environ.get("BLOB_READ_WRITE_TOKEN")


def put_json(key: str, data: Any) -> bool:
    """
    Store JSON data in Vercel Blob.
    """
    if not BLOB_AVAILABLE:
        print("vercel_blob not available")
        return False

    token = _get_token()
    if not token:
        print("BLOB_READ_WRITE_TOKEN not set")
        return False

    try:
        payload = json.dumps(data).encode('utf-8')
        resp = vercel_blob.put(
            key,
            payload,
            options={'token': token, 'addRandomSuffix': False}
        )
        return resp is not None and 'url' in resp
    except Exception as e:
        print(f"Blob put error: {e}")
        return False


def get_json(key: str) -> Optional[Any]:
    """
    Retrieve JSON data from Vercel Blob.
    """
    if not BLOB_AVAILABLE:
        return None

    token = _get_token()
    if not token:
        return None

    try:
        # List blobs to find the URL for our key
        result = vercel_blob.list(options={'token': token, 'prefix': key})
        blobs = result.get('blobs', [])

        if not blobs:
            return None

        # Find exact match
        blob_url = None
        for blob in blobs:
            if blob.get('pathname') == key:
                blob_url = blob.get('url')
                break

        if not blob_url:
            return None

        # Download the blob content
        import urllib.request
        with urllib.request.urlopen(blob_url, timeout=10) as resp:
            content = resp.read().decode('utf-8')
            return json.loads(content)
    except Exception as e:
        print(f"Blob get error: {e}")
        return None


def delete_blob(key: str) -> bool:
    """
    Delete a blob from Vercel Blob storage.
    """
    if not BLOB_AVAILABLE:
        return False

    token = _get_token()
    if not token:
        return False

    try:
        # First find the blob URL
        result = vercel_blob.list(options={'token': token, 'prefix': key})
        blobs = result.get('blobs', [])

        for blob in blobs:
            if blob.get('pathname') == key:
                vercel_blob.delete(blob.get('url'), options={'token': token})
                return True
        return False
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
