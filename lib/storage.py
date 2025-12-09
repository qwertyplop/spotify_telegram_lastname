"""
Upstash Redis storage wrapper for persisting sync state.
Uses REST API - perfect for serverless with generous free tier (10k commands/day).
"""

import json
import os
import time
from typing import Optional, Any

try:
    from upstash_redis import Redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

# Redis key prefix
KEY_PREFIX = "spotify-telegram:"

# In-memory cache to reduce Redis calls within same request
_cache: dict = {}
_cache_time: float = 0
CACHE_TTL = 30  # seconds


def _get_redis() -> Optional['Redis']:
    """Get Redis client."""
    if not REDIS_AVAILABLE:
        return None

    url = os.environ.get("UPSTASH_REDIS_REST_URL")
    token = os.environ.get("UPSTASH_REDIS_REST_TOKEN")

    if not url or not token:
        return None

    return Redis(url=url, token=token)


def _key(name: str) -> str:
    """Get prefixed key."""
    return f"{KEY_PREFIX}{name}"


def get_value(key: str) -> Optional[Any]:
    """Get a value from Redis."""
    global _cache, _cache_time

    full_key = _key(key)

    # Check cache first
    if full_key in _cache and (time.time() - _cache_time) < CACHE_TTL:
        return _cache[full_key]

    redis = _get_redis()
    if not redis:
        return None

    try:
        value = redis.get(full_key)
        if value:
            # Redis returns string, parse JSON if needed
            if isinstance(value, str) and value.startswith('{'):
                value = json.loads(value)
            _cache[full_key] = value
            _cache_time = time.time()
        return value
    except Exception as e:
        print(f"Redis get error: {e}")
        return None


def set_value(key: str, value: Any, ex: int = None) -> bool:
    """Set a value in Redis."""
    global _cache, _cache_time

    full_key = _key(key)

    redis = _get_redis()
    if not redis:
        return False

    try:
        # Serialize dicts/lists to JSON
        if isinstance(value, (dict, list)):
            value = json.dumps(value)

        if ex:
            redis.set(full_key, value, ex=ex)
        else:
            redis.set(full_key, value)

        # Update cache
        _cache[full_key] = value if not isinstance(value, str) else json.loads(value) if value.startswith('{') else value
        _cache_time = time.time()
        return True
    except Exception as e:
        print(f"Redis set error: {e}")
        return False


def delete_key(key: str) -> bool:
    """Delete a key from Redis."""
    redis = _get_redis()
    if not redis:
        return False

    try:
        redis.delete(_key(key))
        if _key(key) in _cache:
            del _cache[_key(key)]
        return True
    except Exception as e:
        print(f"Redis delete error: {e}")
        return False


# Public API

def get_session() -> Optional[str]:
    """Get Telegram StringSession from storage."""
    session = get_value('session')
    if session:
        return session
    return os.environ.get('TELEGRAM_STRING_SESSION')


def save_session(session: str) -> bool:
    """Save Telegram StringSession to storage."""
    return set_value('session', session)


def get_tokens() -> Optional[dict]:
    """Get Spotify tokens from storage."""
    return get_value('tokens')


def save_tokens(access_token: str, refresh_token: str, expires_at: float) -> bool:
    """Save Spotify tokens to storage."""
    return set_value('tokens', {
        'access_token': access_token,
        'refresh_token': refresh_token,
        'expires_at': expires_at,
    })


def get_state() -> dict:
    """Get sync state from storage."""
    state = get_value('state')
    return state if isinstance(state, dict) else {
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
    return set_value('state', state)


def get_current_track() -> Optional[dict]:
    """Get current track info from storage."""
    return get_value('track')


def save_current_track(track: Optional[dict]) -> bool:
    """Save current track info to storage."""
    if track:
        track['timestamp'] = time.time()
    return set_value('track', track or {'is_playing': False, 'timestamp': time.time()})


def get_errors() -> list:
    """Get error log from storage."""
    errors = get_value('errors')
    return errors if isinstance(errors, list) else []


def log_error(error: str, context: str) -> bool:
    """Add error to error log (keeps last 10)."""
    errors = get_errors()
    errors.insert(0, {
        'timestamp': time.time(),
        'error': str(error),
        'context': context,
    })
    errors = errors[:10]
    return set_value('errors', errors)


def get_flood_wait_until() -> float:
    """Get Telegram flood wait expiry time."""
    value = get_value('flood_wait')
    return float(value) if value else 0


def set_flood_wait_until(until: float) -> bool:
    """Set Telegram flood wait expiry time."""
    return set_value('flood_wait', until)


# Batch operations for efficiency
def batch_update(**kwargs) -> bool:
    """Update multiple keys at once using pipeline."""
    redis = _get_redis()
    if not redis:
        return False

    try:
        pipe = redis.pipeline()
        for key, value in kwargs.items():
            full_key = _key(key)
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            pipe.set(full_key, value)
        pipe.exec()

        # Update cache
        global _cache, _cache_time
        for key, value in kwargs.items():
            _cache[_key(key)] = value
        _cache_time = time.time()

        return True
    except Exception as e:
        print(f"Redis batch error: {e}")
        return False


# Legacy compatibility
def put_json(key: str, data: Any) -> bool:
    return set_value(key, data)


def get_json(key: str) -> Optional[Any]:
    return get_value(key)


def _load_all_data() -> dict:
    """Load all data for sync optimization."""
    return {
        'telegram_session': get_session(),
        'spotify_tokens': get_tokens(),
        'sync_state': get_state(),
        'current_track': get_current_track(),
        'flood_wait_until': get_flood_wait_until(),
        'errors': get_errors(),
    }
