# Spotify-Telegram Sync

Automatically update your Telegram profile's last name with your currently playing Spotify track.

Deployed as a serverless application on Vercel with a web dashboard to monitor sync status.

## Features

- Real-time Spotify track detection
- Automatic Telegram last name updates
- Web dashboard showing current status
- Built-in Spotify OAuth flow (no manual token setup)
- Automatic token refresh
- Rate limit handling with automatic backoff
- Customizable name template

## Architecture

- **Backend**: Flask serverless function on Vercel
- **Storage**: Upstash Redis (10k free commands/day)
- **Scheduling**: External cron (QStash, cron-job.org, etc.)
- **Frontend**: Embedded HTML dashboard

## Prerequisites

1. **Telegram API credentials**
   - Go to [my.telegram.org](https://my.telegram.org)
   - Create an application to get `API_ID` and `API_HASH`

2. **Spotify API credentials**
   - Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
   - Create an application to get `CLIENT_ID` and `CLIENT_SECRET`

3. **Upstash Redis database**
   - Go to [console.upstash.com](https://console.upstash.com)
   - Create a free Redis database
   - Copy the REST URL and REST Token

4. **Vercel account**
   - Sign up at [vercel.com](https://vercel.com)

## Setup

### 1. Generate Telegram StringSession

Run locally to authenticate with Telegram:

```bash
pip install telethon

python scripts/generate_session.py
```

Save the output StringSession for later.

### 2. Deploy to Vercel

1. Fork/push this repo to GitHub
2. Go to [vercel.com/new](https://vercel.com/new)
3. Import your repository
4. Add environment variables (see below)
5. Deploy

### 3. Configure Environment Variables

In Vercel Dashboard > Project Settings > Environment Variables:

| Variable | Description |
|----------|-------------|
| `TELEGRAM_API_ID` | Your Telegram API ID |
| `TELEGRAM_API_HASH` | Your Telegram API Hash |
| `TELEGRAM_STRING_SESSION` | StringSession from step 1 |
| `SPOTIFY_CLIENT_ID` | Spotify app client ID |
| `SPOTIFY_CLIENT_SECRET` | Spotify app client secret |
| `UPSTASH_REDIS_REST_URL` | Upstash Redis REST URL |
| `UPSTASH_REDIS_REST_TOKEN` | Upstash Redis REST Token |

Optional:

| Variable | Default | Description |
|----------|---------|-------------|
| `NAME_TEMPLATE` | `\| {artist_first} - {title}` | Last name format |
| `TRUNCATE_LENGTH` | `64` | Max name length |

### 4. Connect Spotify

1. Add callback URL to your Spotify app:
   - Go to Spotify Developer Dashboard > Your App > Settings
   - Add `https://your-app.vercel.app/api/spotify/callback` to Redirect URIs

2. Visit your dashboard: `https://your-app.vercel.app/`
3. Click "Connect Spotify" and authorize
4. Click "Initialize" to set up

### 5. Set Up External Cron

Vercel Hobby plan doesn't support 1-minute cron. Use an external service:

**Option A: Upstash QStash** (recommended)
- Go to [console.upstash.com](https://console.upstash.com) > QStash
- Create scheduled job to `https://your-app.vercel.app/api/sync`
- Set interval: every 1 minute

**Option B: cron-job.org** (free)
- Create account at [cron-job.org](https://cron-job.org)
- Add job with URL: `https://your-app.vercel.app/api/sync`
- Schedule: every 1 minute

### 6. Done!

- Dashboard: `https://your-app.vercel.app/`
- Sync runs automatically via your cron service
- Tokens refresh automatically, no maintenance needed

## Template Placeholders

Use these in `NAME_TEMPLATE`:

| Placeholder | Description |
|-------------|-------------|
| `{title}` | Track title (cleaned) |
| `{artist}` | All artists |
| `{artist_first}` | First artist only |
| `{album}` | Album name |

Examples:
- `| {artist_first} - {title}` → `| Taylor Swift - Anti-Hero`
- `listening to {title}` → `listening to Anti-Hero`

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `/` | Dashboard UI |
| `/api/status` | Current sync status (JSON) |
| `/api/sync` | Trigger sync (called by cron) |
| `/api/init` | Initialize storage |
| `/api/spotify/auth` | Start Spotify OAuth |
| `/api/spotify/callback` | OAuth callback |

## Project Structure

```
├── api/
│   └── index.py         # Flask app with all routes
├── lib/
│   ├── storage.py       # Upstash Redis wrapper
│   ├── spotify.py       # Spotify API helpers
│   ├── telegram.py      # Telegram API helpers
│   └── formatting.py    # Track formatting
├── scripts/
│   ├── generate_session.py  # Generate new StringSession
│   └── convert_session.py   # Convert existing .session file
├── vercel.json          # Vercel configuration
└── requirements.txt     # Python dependencies
```

## Troubleshooting

### Rate Limited
Telegram has strict rate limits for profile updates. The app handles this automatically with backoff. Check the dashboard for rate limit status.

### Session Expired
If your Telegram session expires, regenerate the StringSession and update the environment variable.

### Sync Not Running
Make sure your external cron service is configured and running. Check cron-job.org or QStash dashboard for execution logs.

### Spotify Disconnected
Visit the dashboard and click "Connect Spotify" to re-authorize. Tokens refresh automatically as long as the connection isn't revoked.

## License

MIT
