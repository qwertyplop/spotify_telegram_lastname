# Logging Stack for Python Flask on Vercel Serverless

**Project:** Spotify-Telegram Sync App  
**Researched:** February 15, 2026  
**Confidence:** HIGH

## Summary

For a Flask app on Vercel serverless with Upstash Redis, the recommended logging stack combines **structured JSON logging** for machine-parseable output with **Vercel's native log system** for immediate visibility, and **Redis-backed log persistence** for long-term debugging.

**Key insight:** Vercel serverless functions have ephemeral logs (max 256 lines per request, logs disappear after function execution). To debug "sync stops working after weeks," you need persistent logging.

---

## Recommended Stack

### Core Logging Library

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| **python-json-logger** | 4.0.0+ | JSON structured logging | Actively maintained (nhairs fork), supports orjson/msgspec for performance, integrates with stdlib logging |
| **structlog** (optional) | 24.0.0+ | Advanced structured logging | More powerful but adds complexity; skip for MVP |

**Confidence:** HIGH  
**Source:** PyPI downloads (88M+ last month), GitHub maintenance (nhairs fork is active as of 2025)

### Recommended: python-json-logger

```bash
pip install python-json-logger
# Optional: faster JSON encoding
pip install orjson
```

**Why python-json-logger over alternatives:**
- Integrates with Python's stdlib `logging` module (works with Flask's `app.logger`)
- Supports custom fields (request_id, function_name, etc.)
- Optional orjson/msgspec backends for 10x faster JSON encoding
- Zero external dependencies (just needs typing_extensions)

---

## Vercel-Specific Configuration

### How Vercel Captures Logs

Vercel captures **stdout and stderr** from serverless functions. Your logs appear in:
1. Vercel Dashboard → Deployments → Function → "Logs" tab
2. `vercel logs <deployment-url>` CLI command
3. Log Drains (Pro/Enterprise) for external persistence

**Critical constraint:** Vercel limits logs to **256 lines per request**. For a sync that runs as a cron job, this is usually sufficient—but it means you cannot accumulate logs across multiple function invocations.

### Logging Configuration for Flask

```python
# api/logging_config.py
import logging
import sys
from pythonjsonlogger.json import JsonFormatter
import os

def configure_logging():
    """Configure structured JSON logging for Vercel."""
    
    # Create formatter with custom fields
    formatter = JsonFormatter(
        fmt='%(asctime)s %(levelname)s %(name)s %(message)s',
        style='%',
        json_default=str,  # Handle non-JSON-serializable objects
    )
    
    # Get the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Remove existing handlers and add JSON handler
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    
    # Suppress noisy third-party loggers
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    
    return root_logger
```

Then in your Flask app:

```python
# api/index.py
import logging
from api.logging_config import configure_logging

# Configure logging early
configure_logging()
logger = logging.getLogger(__name__)

# Use throughout your code
logger.info("sync_started", extra={"track": track_key, "desired_name": desired_name})
logger.error("sync_failed", extra={"error": str(e), "error_type": type(e).__name__})
```

---

## Log Persistence Options

Since Vercel serverless logs are ephemeral, you need external persistence to debug "sync stops working after weeks."

### Option 1: Store Logs in Upstash Redis (Recommended for This Project)

Since you already use Upstash Redis, store logs there—no new service needed.

```python
# api/logger.py
import logging
import json
import time
from upstash_redis import Redis
import os

class RedisHandler(logging.Handler):
    """Custom handler that stores logs in Redis."""
    
    def __init__(self, redis_client, max_logs=1000):
        super().__init__()
        self.redis = redis_client
        self.max_logs = max_logs
        self.log_key = "app:logs"
    
    def emit(self, record):
        try:
            log_entry = {
                "timestamp": time.time(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }
            
            # Add extra fields
            if hasattr(record, "track"):
                log_entry["track"] = record.track
            if hasattr(record, "error"):
                log_entry["error"] = record.error
            
            # Push to Redis list (LPUSH adds to front)
            self.redis.lpush(self.log_key, json.dumps(log_entry))
            
            # Trim to keep only last N logs
            self.redis.ltrim(self.log_key, 0, self.max_logs - 1)
            
        except Exception:
            self.handleError(record)


def get_redis_logger():
    """Get a logger that persists to Redis."""
    redis = Redis.from_env()
    
    handler = RedisHandler(redis, max_logs=500)
    handler.setLevel(logging.INFO)
    
    logger = logging.getLogger("sync")
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    
    return logger
```

**Usage in your sync function:**

```python
from api.logger import get_redis_logger

sync_logger = get_redis_logger()

# In sync function
sync_logger.info(
    "sync_cycle_start",
    extra={
        "track": track_key,
        "has_tokens": bool(access_token),
        "flood_wait": flood_until > time.time() if flood_until else False,
    }
)

sync_logger.error(
    "sync_error",
    extra={
        "error": str(e),
        "error_type": type(e).__name__,
    }
)
```

### Option 2: Vercel Log Drains (Pro/Enterprise Only)

If you're on Vercel Pro/Enterprise, configure a Log Drain to forward all logs to an external endpoint:

| Feature | Detail |
|---------|--------|
| **Cost** | Pro plan ($20/user/month) or Enterprise |
| **Log format** | JSON or NDJSON |
| **Sources** | lambda, edge, build, static |
| **Sampling** | Configurable (0-100%) |

**Setup:**
1. Vercel Dashboard → Team Settings → Log Drains → Add Drain
2. Choose "Custom endpoint" or Marketplace integration (e.g., Dash0)
3. Select "lambda" as the source

**Limitation:** Log Drains are for aggregating all Vercel logs—not specifically for application-level structured logs from your code.

### Option 3: Simple External Log Service

Services that accept HTTP log ingestion:

| Service | Free Tier | Notes |
|---------|-----------|-------|
| **Logtail** (formerly Papertrail) | 50MB/month | Simple HTTP endpoint, good UI |
| **Better Stack** | 1GB/month | Includes uptime monitoring |
| **Datadog** | Generous free tier | Enterprise-grade, complex setup |

---

## Request Tracing

To debug intermittent issues, add **request correlation IDs**:

```python
# api/tracing.py
import uuid
from flask import request
import logging

class CorrelationFilter(logging.Filter):
    """Add correlation ID to all log records."""
    
    def filter(self, record):
        record.correlation_id = request.headers.get('X-Request-ID', 'no-request-id')
        return True

# In logging_config.py
handler.addFilter(CorrelationFilter())
```

For the sync cron job, generate a correlation ID:

```python
import uuid

def sync():
    correlation_id = str(uuid.uuid4())[:8]
    logger.info("sync_started", extra={"correlation_id": correlation_id})
    # ... rest of sync logic
```

---

## Integration with Existing Code

Your current code uses `print()` statements. Here's how to migrate:

### Before (storage.py)
```python
print(f"Redis get error: {e}")
```

### After
```python
import logging
logger = logging.getLogger(__name__)

logger.error("redis_get_error", extra={"error": str(e)})
```

### For spotify.py and telegram.py
```python
# spotify.py
logger = logging.getLogger(__name__)
logger.warning("spotify_api_timeout")
logger.error("spotify_api_error", extra={"status_code": resp.status_code})

# telegram.py
logger.warning("telegram_rate_limit", extra={"wait_seconds": wait_seconds})
logger.error("telegram_session_error", extra={"error": str(e)})
```

---

## Recommended Implementation Priority

| Priority | Task | Effort | Impact |
|----------|------|--------|--------|
| 1 | Add python-json-logger with basic config | 30 min | HIGH |
| 2 | Add Redis log handler for persistence | 1 hour | HIGH |
| 3 | Add structured logging to sync function | 1 hour | HIGH |
| 4 | Add correlation IDs | 30 min | MEDIUM |
| 5 | Configure Vercel Log Drain | 1 hour | LOW (requires Pro) |

---

## Installation

```bash
# Core logging library
pip install python-json-logger

# Optional: faster JSON encoding (recommended for serverless)
pip install orjson

# Already installed (from your existing code)
# pip install upstash-redis
```

---

## Sources

- **python-json-logger:** PyPI (v4.0.0, October 2025), GitHub (nhairs fork)
- **Vercel Log Drains:** Vercel Documentation (November 2025)
- **Vercel Runtime Logs:** Vercel Documentation (October 2025)
- **Flask logging:** Flask Documentation, Stack Overflow community patterns

---

## Confidence Assessment

| Area | Level | Reason |
|------|-------|--------|
| Library choice (python-json-logger) | HIGH | Actively maintained, widely used, stdlib integration |
| Vercel log capture | HIGH | Official Vercel documentation |
| Redis persistence approach | HIGH | Uses existing infrastructure, straightforward implementation |
| Log Drain information | HIGH | Official Vercel docs |

---

## Open Questions

- **Q:** Is Redis log storage cost-effective for long-term retention?
- **A:** Yes. At 1KB per log entry, 1000 logs = 1MB. Even with daily syncs over months, you'll use minimal Redis storage.

- **Q:** Should I also log to stdout for Vercel's real-time logs?
- **A:** Yes. Keep both: stdout for real-time debugging via `vercel logs`, Redis for persistent debugging.
