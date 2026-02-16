# Technology Stack

**Analysis Date:** 2026-02-15

## Languages

**Primary:**
- Python 3.x - Core application logic, API endpoints, all business logic

**Secondary:**
- HTML/CSS/JavaScript - Dashboard UI (embedded in `api/index.py`)

## Runtime

**Environment:**
- Vercel Serverless Functions (Python runtime)
- Flask as WSGI framework

**Package Manager:**
- pip (via `requirements.txt`)

## Frameworks

**Core:**
- Flask >= 3.0.0 - Web framework for API endpoints
- Telethon >= 1.33.1 - Telegram client library (async)
- requests >= 2.31.0 - HTTP client for Spotify API calls
- upstash-redis >= 1.0.0 - Redis client for Upstash REST API

**Build/Dev:**
- Vercel - Deployment platform
- vercel.json - Build and route configuration

## Key Dependencies

**Critical:**
- Flask - HTTP routing, request handling, response generation
- Telethon - Telegram StringSession management, profile updates
- upstash-redis - State persistence in serverless environment
- requests - Spotify Web API communication

**Infrastructure:**
- Upstash Redis - Primary data store (10k commands/day free tier)
- Vercel - Serverless hosting platform

## Configuration

**Environment:**
- Configuration via `os.environ.get()`
- Required variables:
  - `TELEGRAM_API_ID` - Telegram API application ID
  - `TELEGRAM_API_HASH` - Telegram API application hash
  - `TELEGRAM_STRING_SESSION` - Telethon StringSession string
  - `SPOTIFY_CLIENT_ID` - Spotify application client ID
  - `SPOTIFY_CLIENT_SECRET` - Spotify application client secret
  - `SPOTIFY_REFRESH_TOKEN` - Long-lived Spotify refresh token (optional, can be stored in Redis)
  - `UPSTASH_REDIS_REST_URL` - Upstash Redis REST URL
  - `UPSTASH_REDIS_REST_TOKEN` - Upstash Redis REST token

**Optional variables:**
- `NAME_TEMPLATE` - Format template for last name (default: `"| {artist_first} - {title}"`)
- `TRUNCATE_LENGTH` - Max length for last name (default: 64)

**Build:**
- `vercel.json` - Routes all requests to `api/index.py`

## Platform Requirements

**Development:**
- Python 3.x
- Telegram account with API credentials (from my.telegram.org)
- Spotify developer account (from developer.spotify.com)
- Upstash account for Redis

**Production:**
- Vercel deployment
- External cron job service to trigger `/api/sync` (e.g., Vercel Cron, EasyCron)

---

*Stack analysis: 2026-02-15*
