# Spotify-Telegram Sync

## What This Is

A serverless app that syncs the user's currently playing Spotify track to their Telegram display name. Built with Flask on Vercel, uses Upstash Redis for storage, and Telethon for Telegram updates.

## Core Value

Automatically update Telegram last name to show current Spotify track - so friends see what you're listening to.

## Requirements

### Validated

- ✓ Spotify authentication via OAuth — existing
- ✓ Track polling from Spotify API — existing  
- ✓ Telegram name update via Telethon — existing
- ✓ Upstash Redis storage for state — existing
- ✓ Dashboard UI showing sync status — existing

### Active

- [ ] Remove "Now Playing" field from dashboard UI
- [ ] Fix "Last Sync" timestamp - should update every sync run
- [ ] Fix "Last Update" timestamp - should update when track changes
- [ ] Add comprehensive logging to diagnose why sync stops working

### Out of Scope

- Real-time push notifications — not needed
- Multiple Telegram accounts — single user only
- Webhook-based sync — polling is sufficient

## Context

Existing codebase:
- `api/index.py` - Flask app with sync endpoint, OAuth, dashboard
- `lib/spotify.py` - Spotify API client
- `lib/telegram.py` - Telegram client
- `lib/storage.py` - Upstash Redis wrapper
- `lib/formatting.py` - Track key generation

Deployed on Vercel as serverless functions. Sync triggered via cron.

Current issues:
1. Dashboard shows "Now Playing: Nothing playing" always - user doesn't need this
2. Dashboard shows "Last Sync: Never" and "Last Update: Never" - timestamps never saved
3. System stops working after weeks - no logs to diagnose

## Constraints

- **Platform**: Vercel serverless — logging must work within serverless constraints
- **Redis**: Upstash — already configured
- **Telegram**: Rate limited — must handle flood waits

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Polling over webhooks | Simpler, Spotify webhooks require premium | — Pending |
| Upstash for storage | Already using, serverless-friendly | — Pending |

---
*Last updated: 2026-02-15 after initialization*
