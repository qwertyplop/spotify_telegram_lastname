# Architecture

**Analysis Date:** 2026-02-15

## Pattern Overview

**Overall:** Flask Serverless Application with Event-Driven Sync

**Key Characteristics:**
- Serverless deployment on Vercel using Python runtime
- Event-driven architecture triggered by cron jobs (external scheduler)
- Redis-backed persistent state with in-memory caching
- Separation between API layer (`api/index.py`), business logic (`lib/`), and utility scripts (`scripts/`)

## Layers

### API Layer (`api/index.py`)
- Purpose: HTTP endpoints and request handling
- Location: `api/index.py`
- Contains: Flask routes, OAuth flows, dashboard HTML, sync logic
- Depends on: `lib/storage`, `lib/spotify`, `lib/telegram`, `lib/formatting`
- Used by: Vercel serverless functions, cron jobs

### Business Logic Layer (`lib/`)
- Purpose: Core functionality without framework coupling
- Contains:
  - `spotify.py` - Spotify API client (token refresh, track fetching)
  - `telegram.py` - Telegram API client (profile updates via Telethon)
  - `formatting.py` - Track-to-last-name formatting with templates
  - `storage.py` - Upstash Redis persistence layer

### Scripts Layer (`scripts/`)
- Purpose: One-time setup and migration utilities
- Contains:
  - `generate_session.py` - Interactive Telegram authentication
  - `convert_session.py` - Convert .session files to StringSession

### Presentation Layer (`api/index.py` - embedded HTML)
- Purpose: Dashboard UI for status monitoring
- Contains: Embedded HTML/CSS/JS in `DASHBOARD_HTML` constant

## Data Flow

### Spotify OAuth Flow:
1. User clicks `/api/spotify/auth` → redirects to Spotify authorize page
2. Spotify calls back to `/api/spotify/callback` with auth code
3. API exchanges code for tokens (access + refresh)
4. Tokens saved to Redis via `storage.save_tokens()`

### Sync Flow (triggered by cron):
1. External cron hits `/api/sync`
2. Load all data from Redis (`storage._load_all_data()`)
3. Refresh Spotify token if expired
4. Fetch currently playing track from Spotify API
5. Generate track key to detect changes
6. Format new last name using template
7. If changed and not rate-limited, update Telegram profile
8. Batch-save updated state to Redis

### Dashboard Flow:
1. User visits `/` → serves embedded HTML dashboard
2. JavaScript fetches `/api/status`
3. Status endpoint aggregates: state, track, tokens, errors, flood status
4. Dashboard renders real-time status with auto-refresh (30s)

## Key Abstractions

### SpotifyToken (dataclass in `lib/spotify.py`)
- Purpose: Represents Spotify OAuth token with expiration
- Examples: `lib/spotify.py` lines 18-27
- Pattern: dataclass with `is_expired()` method

### TrackInfo (dataclass in `lib/spotify.py`)
- Purpose: Currently playing track representation
- Examples: `lib/spotify.py` lines 30-49
- Pattern: dataclass with `to_dict()` for serialization

### Storage Keys (`lib/storage.py`)
- Purpose: Redis key namespace management
- Keys: `spotify-telegram:session`, `spotify-telegram:tokens`, `spotify-telegram:state`, `spotify-telegram:track`, `spotify-telegram:errors`, `spotify-telegram:flood_wait`
- Pattern: Prefix + key name with `_key()` function

## Entry Points

### `/api/sync`
- Location: `api/index.py` lines 377-532
- Triggers: External cron job
- Responsibilities: Main sync logic - check track, format name, update Telegram, handle rate limiting

### `/api/spotify/auth` and `/api/spotify/callback`
- Location: `api/index.py` lines 279-374
- Triggers: User browser navigation
- Responsibilities: OAuth flow initiation and callback handling

### `/api/status`
- Location: `api/index.py` lines 229-276
- Triggers: Dashboard polling (30s interval)
- Responsibilities: Aggregate and return current system state

### `/api/init`
- Location: `api/index.py` lines 535-587
- Triggers: Manual or setup flow
- Responsibilities: Initialize storage from environment variables

## Error Handling

**Strategy:** Graceful degradation with error logging

**Patterns:**
- Token expiration: Auto-refresh before requests (5-minute buffer)
- Flood wait: Track Telegram rate limits, pause updates until cleared
- Redis unavailable: Fall back to environment variables for critical configs
- API failures: Log errors, continue operation, surface in dashboard

## Cross-Cutting Concerns

**Logging:** `print()` statements to stdout (Vercel captures)

**Validation:** Environment variable checks before operations (e.g., `SPOTIFY_CLIENT_ID` required)

**Authentication:**
- Spotify: OAuth 2.0 with PKCE-like state cookie
- Telegram: StringSession-based authentication
- Rate limiting: Flood wait tracking for Telegram API limits

---

*Architecture analysis: 2026-02-15*
