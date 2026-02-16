"""
Structured JSON logging infrastructure for Spotify-Telegram Sync.
Provides correlation IDs, JSON formatting, and optional Redis log persistence.
"""

import logging
import json
import os
import time
import uuid
import threading
from datetime import datetime, timezone
from contextlib import contextmanager
from typing import Optional, Any

# python-json-logger for JSON formatting
try:
    from pythonjsonlogger import jsonlogger
    JSON_LOGGER_AVAILABLE = True
except ImportError:
    JSON_LOGGER_AVAILABLE = False

# Thread-local storage for correlation IDs
_correlation_ctx = threading.local()


# ==================== Correlation ID Management ====================

def set_correlation_id(cid: str) -> None:
    """Set correlation ID for current context."""
    _correlation_ctx.cid = cid


def get_correlation_id() -> str:
    """Get current correlation ID or generate UUID if not set."""
    cid = getattr(_correlation_ctx, 'cid', None)
    if cid is None:
        cid = str(uuid.uuid4())[:8]
        _correlation_ctx.cid = cid
    return cid


def clear_correlation_id() -> None:
    """Clear current correlation ID."""
    if hasattr(_correlation_ctx, 'cid'):
        delattr(_correlation_ctx, 'cid')


@contextmanager
def correlation_scope(cid: Optional[str] = None):
    """
    Context manager for correlation ID scope.
    
    Usage:
        with correlation_scope():
            logger.info("test")  # Uses auto-generated or existing CID
            
        with correlation_scope("my-custom-id"):
            logger.info("test")  # Uses custom CID
            
    The correlation ID is cleared when exiting the context.
    """
    previous_cid = getattr(_correlation_ctx, 'cid', None)
    try:
        if cid is None:
            cid = str(uuid.uuid4())[:8]
        set_correlation_id(cid)
        yield cid
    finally:
        if previous_cid is not None:
            _correlation_ctx.cid = previous_cid
        else:
            clear_correlation_id()


# Alias for backwards compatibility
correlation_id = correlation_scope


# ==================== Custom JSON Formatter ====================

class JSONFormatter(logging.Formatter):
    """
    Custom JSON formatter that adds correlation ID and extra fields.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._date_format = '%Y-%m-%dT%H:%S'
    
    def add_fields(self, log_record: dict, record: logging.LogRecord, message_dict: dict):
        """Add custom fields to log record."""
        # Timestamp in ISO8601 format
        log_record['timestamp'] = datetime.now(timezone.utc).isoformat()
        
        # Level
        log_record['level'] = record.levelname
        
        # Logger name
        log_record['name'] = record.name
        
        # Message
        log_record['message'] = record.getMessage()
        
        # Correlation ID
        log_record['correlation_id'] = get_correlation_id()
        
        # Function and line number for debugging
        log_record['function'] = record.funcName
        log_record['line'] = record.lineno
        
        # Module
        log_record['module'] = record.module
        
        # Include extra fields
        if hasattr(record, 'extra'):
            for key, value in record.extra.items():
                if key not in log_record:
                    log_record[key] = value
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_record = {}
        self.add_fields(log_record, record, {})
        
        # Include exception info if present
        if record.exc_info:
            log_record['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_record)


# ==================== Redis Log Handler ====================

class RedisLogHandler(logging.Handler):
    """
    Log handler that buffers logs in memory and flushes to Redis.
    Keeps last 500 entries in Redis list.
    """
    
    def __init__(self, max_buffer: int = 100, max_redis_logs: int = 500):
        super().__init__()
        self._buffer = []
        self._max_buffer = max_buffer
        self._max_redis_logs = max_redis_logs
        self._lock = threading.Lock()
        
        # Redis client (lazy loaded)
        self._redis = None
    
    def _get_redis(self):
        """Lazy load Redis client."""
        if self._redis is not None:
            return self._redis
        
        try:
            from upstash_redis import Redis
            url = os.environ.get("UPSTASH_REDIS_REST_URL")
            token = os.environ.get("UPSTASH_REDIS_REST_TOKEN")
            if url and token:
                self._redis = Redis(url=url, token=token)
                return self._redis
        except ImportError:
            pass
        except Exception:
            pass
        return None
    
    def emit(self, record: logging.LogRecord):
        """Emit a log record."""
        try:
            # Format the record
            log_entry = self.format(record)
            
            with self._lock:
                self._buffer.append(log_entry)
                
                # Flush if buffer is full
                if len(self._buffer) >= self._max_buffer:
                    self._flush()
        except Exception:
            self.handleError(record)
    
    def _flush(self):
        """Flush buffer to Redis."""
        if not self._buffer:
            return
        
        redis = self._get_redis()
        if not redis:
            # Redis not available, clear buffer
            self._buffer.clear()
            return
        
        try:
            key = "spotify-telegram:logs"
            
            # LPUSH all buffered entries
            for entry in self._buffer:
                redis.lpush(key, entry)
            
            # LTRIM to keep only last N entries
            redis.ltrim(key, 0, self._max_redis_logs - 1)
            
            self._buffer.clear()
        except Exception:
            # Silently fail - don't crash the app for logging issues
            self._buffer.clear()
    
    def flush(self):
        """Force flush of buffer."""
        with self._lock:
            self._flush()
    
    def close(self):
        """Close handler and flush buffer."""
        self.flush()
        super().close()


# ==================== Logger Factory ====================

def get_logger(name: str) -> logging.Logger:
    """
    Get a configured logger with JSON formatting.
    
    Args:
        name: Logger name (typically __name__)
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
    
    # Set level from environment
    if os.environ.get('FLASK_DEBUG'):
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)
    
    # Create JSON formatter
    if JSON_LOGGER_AVAILABLE:
        formatter = JSONFormatter()
    else:
        # Fallback to basic JSON if python-json-logger not available
        # Simple JSON format without external dependencies
        class SimpleJSONFormatter(logging.Formatter):
            def format(self, record):
                return json.dumps({
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                    'level': record.levelname,
                    'name': record.name,
                    'message': record.getMessage(),
                    'correlation_id': get_correlation_id(),
                })
        formatter = SimpleJSONFormatter()
    
    # Add stdout handler for Vercel logs
    stdout_handler = logging.StreamHandler()
    stdout_handler.setFormatter(formatter)
    logger.addHandler(stdout_handler)
    
    # Optionally add Redis handler if Redis is available
    # Commented out by default - enable via environment variable
    if os.environ.get('LOG_TO_REDIS', '').lower() in ('1', 'true', 'yes'):
        redis_handler = RedisLogHandler()
        redis_handler.setFormatter(formatter)
        logger.addHandler(redis_handler)
    
    return logger


# ==================== Convenience Functions ====================

def log_sync_start() -> str:
    """
    Log the start of a sync cycle.
    
    Returns:
        Correlation ID for this sync cycle
    """
    cid = str(uuid.uuid4())[:8]
    set_correlation_id(cid)
    
    logger = get_logger('spotify-telegram.sync')
    logger.info("Sync cycle started", extra={
        'event': 'sync_start',
        'correlation_id': cid
    })
    
    return cid


def log_sync_end(success: bool, message: str) -> None:
    """
    Log the end of a sync cycle.
    
    Args:
        success: Whether sync completed successfully
        message: Result message
    """
    logger = get_logger('spotify-telegram.sync')
    logger.info(message, extra={
        'event': 'sync_end',
        'success': success,
        'correlation_id': get_correlation_id()
    })


# ==================== Module Exports ====================

__all__ = [
    'get_logger',
    'correlation_id',
    'correlation_scope',
    'set_correlation_id',
    'get_correlation_id',
    'clear_correlation_id',
    'log_sync_start',
    'log_sync_end',
    'JSONFormatter',
    'RedisLogHandler',
]
