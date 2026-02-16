"""
Upstash Redis storage wrapper for persisting sync state.
Uses REST API - perfect for serverless with generous free tier (10k commands/day).
"""

import json
import os
import time
from typing import Optional, Any

from lib.logger import get_logger

# Get module logger
logger = get_logger('storage')

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
    logger.debug("Creating Redis client")
    
    if not REDIS_AVAILABLE:
        logger.warning("Redis not available (upstash_redis not installed)")
        return None

    url = os.environ.get("UPSTASH_REDIS_REST_URL")
    token = os.environ.get("UPSTASH_REDIS_REST_TOKEN")

    if not url or not token:
        logger.warning("Redis URL/token not configured")
        return None

    logger.debug("Redis client created successfully")
    return Redis(url=url, token=token)


def _key(name: str) -> str:
    """Get prefixed key."""
    return f"{KEY_PREFIX}{name}"


def get_value(key: str) -> Optional[Any]:
    """Get a value from Redis."""
    global _cache, _cache_time

    full_key = _key(key)
    logger.debug(f"Getting value for key: {key}")

    # Check cache first
    if full_key in _cache and (time.time() - _cache_time) < CACHE_TTL:
        logger.debug(f"Cache hit for key: {key}")
        return _cache[full_key]

    logger.debug(f"Cache miss for key: {key}")
    
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
            logger.debug(f"Value retrieved from Redis for key: {key}")
        else:
            logger.debug(f"No value found in Redis for key: {key}")
        return value
    except Exception as e:
        logger.error(f"Failed to get value for key {key}: {e}")
        return None


def set_value(key: str, value: Any, ex: int = None) -> bool:
    """Set a value in Redis."""
    global _cache, _cache_time

    full_key = _key(key)
    logger.debug(f"Setting value for key: {key}, TTL: {ex}")

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
        logger.debug(f"Value saved to Redis for key: {key}")
        return True
    except Exception as e:
        logger.error(f"Failed to set value for key {key}: {e}")
        return False


def delete_key(key: str) -> bool:
    """Delete a key from Redis."""
    logger.debug(f"Deleting key: {key}")
    
    redis = _get_redis()
    if not redis:
        return False

    try:
        redis.delete(_key(key))
        if _key(key) in _cache:
            del _cache[_key(key)]
        logger.debug(f"Key deleted: {key}")
        return True
    except Exception as e:
        logger.error(f"Failed to delete key {key}: {e}")
        return False


# Public API

def get_session() -> Optional[str]:
    """Get Telegram StringSession from storage."""
    logger.debug("Getting session")
    session = get_value('session')
    if session:
        logger.debug("Session found in storage")
        return session
    logger.debug("Session not found, falling back to environment")
    return os.environ.get('TELEGRAM_STRING_SESSION')


def save_session(session: str) -> bool:
    """Save Telegram StringSession to storage."""
    logger.debug("Saving session")
    result = set_value('session', session)
    if result:
        logger.debug("Session saved successfully")
    else:
        logger.error("Failed to save session")
    return result


def get_tokens() -> Optional[dict]:
    """Get Spotify tokens from storage."""
    logger.debug("Getting tokens")
    tokens = get_value('tokens')
    if tokens:
        logger.debug("Tokens found in storage")
    else:
        logger.debug("No tokens found in storage")
    return tokens


def save_tokens(access_token: str, refresh_token: str, expires_at: float) -> bool:
    """Save Spotify tokens to storage."""
    logger.debug("Saving tokens")
    result = set_value('tokens', {
        'access_token': access_token,
        'refresh_token': refresh_token,
        'expires_at': expires_at,
    })
    if result:
        logger.debug("Tokens saved successfully")
    else:
        logger.error("Failed to save tokens")
    return result


def get_state() -> dict:
    """Get sync state from storage."""
    logger.debug("Getting sync state")
    state = get_value('state')
    if state:
        logger.debug("State found in storage")
    else:
        logger.debug("No state found, returning default")
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
    logger.debug("Saving sync state")
    state['last_sync'] = time.time()
    result = set_value('state', state)
    if result:
        logger.debug("State saved successfully")
    else:
        logger.error("Failed to save state")
    return result


def get_current_track() -> Optional[dict]:
    """Get current track info from storage."""
    logger.debug("Getting current track")
    track = get_value('track')
    if track:
        logger.debug("Current track found")
    else:
        logger.debug("No current track found")
    return track


def save_current_track(track: Optional[dict]) -> bool:
    """Save current track info to storage."""
    logger.debug("Saving current track")
    if track:
        track['timestamp'] = time.time()
    result = set_value('track', track or {'is_playing': False, 'timestamp': time.time()})
    if result:
        logger.debug("Current track saved successfully")
    else:
        logger.error("Failed to save current track")
    return result


def get_errors() -> list:
    """Get error log from storage."""
    logger.debug("Getting error log")
    errors = get_value('errors')
    return errors if isinstance(errors, list) else []


def log_error(error: str, context: str) -> bool:
    """Add error to error log (keeps last 10)."""
    logger.debug(f"Logging error: {context}")
    errors = get_errors()
    errors.insert(0, {
        'timestamp': time.time(),
        'error': str(error),
        'context': context,
    })
    errors = errors[:10]
    result = set_value('errors', errors)
    if result:
        logger.debug(f"Error logged: {error}")
    else:
        logger.error("Failed to log error")
    return result


def get_flood_wait_until() -> float:
    """Get Telegram flood wait expiry time."""
    logger.debug("Getting flood wait until")
    value = get_value('flood_wait')
    return float(value) if value else 0


def set_flood_wait_until(until: float) -> bool:
    """Set Telegram flood wait expiry time."""
    logger.debug(f"Setting flood wait until: {until}")
    result = set_value('flood_wait', until)
    if result:
        logger.debug("Flood wait set successfully")
    else:
        logger.error("Failed to set flood wait")
    return result


# Batch operations for efficiency
def batch_update(**kwargs) -> bool:
    """Update multiple keys at once using pipeline."""
    count = len(kwargs)
    keys = list(kwargs.keys())
    logger.info(f"Batch updating {count} keys")
    logger.debug(f"Keys in batch: {keys}")
    
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

        logger.info("Batch update successful")
        return True
    except Exception as e:
        logger.error(f"Batch update failed: {e}")
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


# ==================== Log Persistence ====================

# Log constants
LOG_KEY = 'logs'
MAX_LOG_ENTRIES = 500


def append_log(log_entry: dict) -> bool:
    """
    Append a log entry to Redis (keeps last 500).
    
    Args:
        log_entry: Dictionary with log data (timestamp, level, name, message, correlation_id, etc.)
    
    Returns:
        True if successful, False otherwise
    """
    logger.debug(f"Appending log entry: {log_entry.get('message', '')[:50]}")
    
    redis = _get_redis()
    if not redis:
        logger.debug("Redis not available, skipping log persistence")
        return False

    try:
        full_key = _key(LOG_KEY)
        # Serialize log entry to JSON
        log_json = json.dumps(log_entry)
        
        # LPUSH to add to beginning of list
        redis.lpush(full_key, log_json)
        
        # LTRIM to keep only last MAX_LOG_ENTRIES
        redis.ltrim(full_key, 0, MAX_LOG_ENTRIES - 1)
        
        logger.debug(f"Log entry persisted to Redis (key: {full_key})")
        return True
    except Exception as e:
        # Log error but don't fail - logging should never crash the app
        logger.error(f"Failed to append log to Redis: {e}")
        return False


def get_logs(count: int = 100) -> list:
    """
    Get recent log entries from Redis.
    
    Args:
        count: Number of log entries to retrieve (default 100)
    
    Returns:
        List of log entry dictionaries
    """
    logger.debug(f"Retrieving last {count} log entries from Redis")
    
    redis = _get_redis()
    if not redis:
        logger.debug("Redis not available, returning empty log list")
        return []

    try:
        full_key = _key(LOG_KEY)
        # LRANGE to get entries (0 to count-1)
        entries = redis.lrange(full_key, 0, count - 1)
        
        # Parse JSON strings back to dicts
        logs = []
        for entry in entries:
            if isinstance(entry, str):
                try:
                    logs.append(json.loads(entry))
                except json.JSONDecodeError:
                    # Handle non-JSON entries gracefully
                    logs.append({'message': entry, 'raw': True})
            else:
                logs.append(entry)
        
        logger.debug(f"Retrieved {len(logs)} log entries from Redis")
        return logs
    except Exception as e:
        logger.error(f"Failed to get logs from Redis: {e}")
        return []
