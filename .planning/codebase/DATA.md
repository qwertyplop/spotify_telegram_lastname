# Data Models and Storage

**Analysis Date:** 2026-02-15

## Storage Backend

**Provider:** Upstash Redis (Serverless Redis with REST API)
- **Connection:** REST URL + token from environment variables
- **Client:** `upstash_redis` Python library
- **Key Prefix:** `spotify-telegram:`

## Data Models

### 1. Telegram Session (`spotify-telegram:session`)

**Type:** String (Telethon StringSession)

**Storage Location:** `lib/storage.py` lines 120-130

```python
# Access
storage.get_session() -> Optional[str]

# Save
storage.save_session(session: str) -> bool
```

**Source:** Either from Redis or falls back to `TELEGRAM_STRING_SESSION` environment variable.

---

### 2. Spotify Tokens (`spotify-telegram:tokens`)

**Type:** JSON object

```json
{
  "access_token": "string",
  "refresh_token": "string", 
  "expires_at": 1234567890.123
}
```

**Storage Location:** `lib/storage.py` lines 133-144

**Access:**
```python
storage.get_tokens() -> Optional[dict]
storage.save_tokens(access_token, refresh_token, expires_at) -> bool
```

**Lifecycle:**
1. Initial OAuth flow generates access + refresh tokens
2. Access token expires (typically 1 hour)
3. System auto-refreshes using refresh token before expiration (5-minute buffer)
4. New refresh token saved if Spotify provides one (rotation)

---

### 3. Sync State (`spotify-telegram:state`)

**Type:** JSON object

```json
{
  "original_last_name": "Doe",
  "current_last_name": "| Artist - Song Title",
  "last_track_key": "track:normalized title",
  "last_update": 1234567890,
  "last_sync": 1234567890,
  "update_count": 42,
  "status": "active"
}
```

**Storage Location:** `lib/storage.py` lines 147-164

**Fields:**
- `original_last_name` - User's original last name (captured at init)
- `current_last_name` - Last name currently set on Telegram
- `last_track_key` - Generated key for change detection
- `last_update` - Unix timestamp of last Telegram update
- `last_sync` - Unix timestamp of last sync attempt
- `update_count` - Total number of successful updates
- `status` - State machine: `initialized`, `active`, `error`

---

### 4. Current Track (`spotify-telegram:track`)

**Type:** JSON object

```json
{
  "title": "Song Title",
  "artist": "Artist Name",
  "album": "Album Name",
  "is_playing": true,
  "timestamp": 1234567890
}
```

**Storage Location:** `lib/storage.py` lines 167-176

**Access:**
```python
storage.get_current_track() -> Optional[dict]
storage.save_current_track(track: Optional[dict]) -> bool
```

---

### 5. Error Log (`spotify-telegram:errors`)

**Type:** Array of error objects (max 10)

```json
[
  {
    "timestamp": 1234567890,
    "error": "Error message",
    "context": "Operation context"
  }
]
```

**Storage Location:** `lib/storage.py` lines 179-194

**Behavior:**
- New errors added to front of array
- Kept to most recent 10 entries
- Displayed in dashboard

---

### 6. Flood Wait (`spotify-telegram:flood_wait`)

**Type:** Unix timestamp (float)

**Storage Location:** `lib/storage.py` lines 197-205

**Purpose:** Track Telegram API rate limit cooldown

**Behavior:**
- Set when Telegram returns FloodWaitError
- Value = current time + wait seconds + 10 second buffer
- Sync endpoint checks this before attempting updates

---

## In-Memory Caching

**Implementation:** `lib/storage.py` lines 20-23

```python
_cache: dict = {}
_cache_time: float = 0
CACHE_TTL = 30  # seconds
```

**Purpose:** Reduce Redis calls within same serverless function invocation

---

## Batch Operations

**Implementation:** `lib/storage.py` lines 209-233

```python
storage.batch_update(**kwargs) -> bool
```

**Purpose:** Minimize Redis round-trips by combining multiple writes into single pipeline execution

---

## Dataclasses (Runtime)

### SpotifyToken (`lib/spotify.py` lines 18-27)

```python
@dataclass
class SpotifyToken:
    access_token: str
    refresh_token: str
    expires_at: float
    
    def is_expired(self, buffer_seconds: int = 300) -> bool:
        return time.time() >= (self.expires_at - buffer_seconds)
```

### TrackInfo (`lib/spotify.py` lines 30-49)

```python
@dataclass
class TrackInfo:
    title: str
    artist: str
    album: Optional[str] = None
    is_playing: bool = True
    
    def to_dict(self) -> dict:
        return {...}
```

---

## Data Flow Summary

```
External Cron
    │
    ▼
/api/sync endpoint
    │
    ├─► Load all data (storage._load_all_data())
    │       ├─► telegram_session (Redis or env)
    │       ├─► spotify_tokens (Redis)
    │       ├─► sync_state (Redis)
    │       ├─► current_track (Redis)
    │       └─► flood_wait_until (Redis)
    │
    ├─► Refresh Spotify token if needed
    │
    ├─► Fetch current track from Spotify API
    │
    ├─► Determine if update needed (should_update logic)
    │
    ├─► Format new last name (formatting.py)
    │
    ├─► Update Telegram profile (if changed)
    │
    └─► Batch save to Redis (storage.batch_update())
            └─► Invalidate cache
```

---

*Data models and storage: 2026-02-15*
