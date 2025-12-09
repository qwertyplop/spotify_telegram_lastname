"""
Vercel Blob storage wrapper for persisting sync state.
Optimized to minimize API operations (2k advanced, 10k simple per month limit).

Strategy:
- Single blob file for all data to minimize operations
- Cache blob URL to avoid repeated list() calls
- Only write when data changes
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

# Single blob file for all data
BLOB_FILENAME = "spotify-telegram-state.json"

# Cache for blob URL (avoids repeated list() calls)
_blob_url_cache: Optional[str] = None
_cache_data: Optional[dict] = None
_cache_time: float = 0
CACHE_TTL = 30  # seconds


def _get_token() -> Optional[str]:
    """Get Blob read/write token from environment."""
    return os.environ.get("BLOB_READ_WRITE_TOKEN")


def _get_blob_url(token: str) -> Optional[str]:
    """Get blob URL, using cache if available."""
    global _blob_url_cache

    if _blob_url_cache:
        return _blob_url_cache

    try:
        result = vercel_blob.list(options={'token': token, 'prefix': BLOB_FILENAME, 'limit': 1})
        blobs = result.get('blobs', [])

        for blob in blobs:
            if blob.get('pathname') == BLOB_FILENAME:
                _blob_url_cache = blob.get('url')
                return _blob_url_cache
    except Exception as e:
        print(f"Blob list error: {e}")

    return None


def _load_all_data() -> dict:
    """Load all data from blob (cached)."""
    global _cache_data, _cache_time

    # Return cached data if fresh
    if _cache_data and (time.time() - _cache_time) < CACHE_TTL:
        return _cache_data

    if not BLOB_AVAILABLE:
        return {}

    token = _get_token()
    if not token:
        return {}

    try:
        blob_url = _get_blob_url(token)
        if not blob_url:
            return {}

        # Download blob content (simple operation if cache hit)
        import urllib.request
        with urllib.request.urlopen(blob_url, timeout=10) as resp:
            content = resp.read().decode('utf-8')
            _cache_data = json.loads(content)
            _cache_time = time.time()
            return _cache_data
    except Exception as e:
        print(f"Blob load error: {e}")
        return {}


def _save_all_data(data: dict) -> bool:
    """Save all data to blob."""
    global _blob_url_cache, _cache_data, _cache_time

    if not BLOB_AVAILABLE:
        return False

    token = _get_token()
    if not token:
        return False

    try:
        payload = json.dumps(data).encode('utf-8')
        resp = vercel_blob.put(
            BLOB_FILENAME,
            payload,
            options={'token': token, 'addRandomSuffix': False}
        )
        if resp and 'url' in resp:
            _blob_url_cache = resp['url']
            _cache_data = data
            _cache_time = time.time()
            return True
        return False
    except Exception as e:
        print(f"Blob save error: {e}")
        return False


def _get_data_section(section: str, default: Any = None) -> Any:
    """Get a section of data."""
    data = _load_all_data()
    return data.get(section, default)


def _set_data_section(section: str, value: Any) -> bool:
    """Set a section of data."""
    data = _load_all_data()
    data[section] = value
    return _save_all_data(data)


# Public API - same interface as before

def get_session() -> Optional[str]:
    """Get Telegram StringSession from storage."""
    session = _get_data_section('telegram_session')
    if session:
        return session
    return os.environ.get('TELEGRAM_STRING_SESSION')


def save_session(session: str) -> bool:
    """Save Telegram StringSession to storage."""
    return _set_data_section('telegram_session', session)


def get_tokens() -> Optional[dict]:
    """Get Spotify tokens from storage."""
    return _get_data_section('spotify_tokens')


def save_tokens(access_token: str, refresh_token: str, expires_at: float) -> bool:
    """Save Spotify tokens to storage."""
    return _set_data_section('spotify_tokens', {
        'access_token': access_token,
        'refresh_token': refresh_token,
        'expires_at': expires_at,
    })


def get_state() -> dict:
    """Get sync state from storage."""
    state = _get_data_section('sync_state')
    return state or {
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
    return _set_data_section('sync_state', state)


def get_current_track() -> Optional[dict]:
    """Get current track info from storage."""
    return _get_data_section('current_track')


def save_current_track(track: Optional[dict]) -> bool:
    """Save current track info to storage."""
    if track:
        track['timestamp'] = time.time()
    return _set_data_section('current_track', track or {'is_playing': False, 'timestamp': time.time()})


def get_errors() -> list:
    """Get error log from storage."""
    return _get_data_section('errors', [])


def log_error(error: str, context: str) -> bool:
    """Add error to error log (keeps last 10)."""
    errors = get_errors()
    errors.insert(0, {
        'timestamp': time.time(),
        'error': str(error),
        'context': context,
    })
    errors = errors[:10]
    return _set_data_section('errors', errors)


def get_flood_wait_until() -> float:
    """Get Telegram flood wait expiry time."""
    return _get_data_section('flood_wait_until', 0)


def set_flood_wait_until(until: float) -> bool:
    """Set Telegram flood wait expiry time."""
    return _set_data_section('flood_wait_until', until)


# Batch update function to minimize writes
def batch_update(**kwargs) -> bool:
    """Update multiple sections at once (single write operation)."""
    data = _load_all_data()
    for key, value in kwargs.items():
        data[key] = value
    return _save_all_data(data)


# For compatibility
def put_json(key: str, data: Any) -> bool:
    return _set_data_section(key, data)


def get_json(key: str) -> Optional[Any]:
    return _get_data_section(key)


def delete_blob(key: str) -> bool:
    """Delete a key from data."""
    data = _load_all_data()
    if key in data:
        del data[key]
        return _save_all_data(data)
    return True
