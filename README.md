# Spotify-Telegram Sync

Automatically update your Telegram profile's last name with your currently playing Spotify track.

Deployed as a serverless application on Vercel with a web dashboard to monitor sync status.

## Features

- Real-time Spotify track detection (1-minute polling)
- Automatic Telegram last name updates
- Web dashboard showing current status
- Rate limit handling with automatic backoff
- Customizable name template

## Architecture

- **Backend**: Python serverless functions on Vercel
- **Storage**: Vercel Blob for session and state persistence
- **Scheduling**: Vercel Cron Jobs (1-minute intervals)
- **Frontend**: Simple HTML dashboard

## Prerequisites

1. **Telegram API credentials**
   - Go to [my.telegram.org](https://my.telegram.org)
   - Create an application to get `API_ID` and `API_HASH`

2. **Spotify API credentials**
   - Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
   - Create an application to get `CLIENT_ID` and `CLIENT_SECRET`
   - Add `http://localhost:8888/callback` to Redirect URIs

3. **Vercel account**
   - Sign up at [vercel.com](https://vercel.com)

## Setup

### 1. Generate Telegram StringSession

Run locally to authenticate with Telegram:

```bash
# Install dependencies
pip install telethon

# Generate session (interactive)
python scripts/generate_session.py
```

Save the output StringSession for later.

### 2. Get Spotify Refresh Token

You can use any Spotify OAuth tool or run:

```bash
# Set your Spotify credentials
export SPOTIFY_CLIENT_ID=your_client_id
export SPOTIFY_CLIENT_SECRET=your_client_secret

# Use the Spotify OAuth flow to get a refresh token
# (You'll need to implement this or use an existing tool)
```

### 3. Deploy to Vercel

#### Option A: Deploy from GitHub

1. Fork/push this repo to GitHub
2. Go to [vercel.com/new](https://vercel.com/new)
3. Import your repository
4. Add environment variables (see below)
5. Deploy

#### Option B: Deploy with Vercel CLI

```bash
# Install Vercel CLI
npm i -g vercel

# Deploy
vercel
```

### 4. Configure Environment Variables

In Vercel Dashboard > Project Settings > Environment Variables, add:

| Variable | Description |
|----------|-------------|
| `TELEGRAM_API_ID` | Your Telegram API ID |
| `TELEGRAM_API_HASH` | Your Telegram API Hash |
| `TELEGRAM_STRING_SESSION` | StringSession from step 1 |
| `SPOTIFY_CLIENT_ID` | Spotify app client ID |
| `SPOTIFY_CLIENT_SECRET` | Spotify app client secret |
| `SPOTIFY_REFRESH_TOKEN` | Spotify refresh token |

Optional variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `NAME_TEMPLATE` | `\| {artist_first} - {title}` | Last name format |
| `TRUNCATE_LENGTH` | `64` | Max name length |
| `CRON_SECRET` | (none) | Secret for cron endpoint protection |

### 5. Enable Vercel Blob Storage

1. Go to Vercel Dashboard > Storage
2. Create a new Blob store
3. Connect it to your project

### 6. Initialize

Visit `https://your-app.vercel.app/api/init` to initialize the storage with your credentials.

### 7. Done!

- Dashboard: `https://your-app.vercel.app/`
- The cron job will start syncing automatically every minute

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

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/sync` | GET | Cron-triggered sync (called every minute) |
| `/api/status` | GET | Returns current sync status (JSON) |
| `/api/init` | GET/POST | Initialize storage with credentials |

## Project Structure

```
├── api/
│   ├── sync.py          # Main sync function (cron)
│   ├── status.py        # Status API
│   └── init.py          # Initialization endpoint
├── lib/
│   ├── storage.py       # Vercel Blob wrapper
│   ├── spotify.py       # Spotify API helpers
│   ├── telegram.py      # Telegram API helpers
│   └── formatting.py    # Track formatting
├── public/
│   └── index.html       # Dashboard UI
├── scripts/
│   ├── generate_session.py  # Generate new StringSession
│   └── convert_session.py   # Convert existing session file
├── vercel.json          # Vercel configuration
└── requirements.txt     # Python dependencies
```

## Troubleshooting

### Rate Limited
Telegram has strict rate limits for profile updates. The app handles this automatically with exponential backoff. Check the dashboard for rate limit status.

### Session Expired
If your Telegram session expires, you'll need to regenerate the StringSession and update the environment variable.

### Cron Not Running
Vercel Hobby plan has limited cron frequency. For 1-minute intervals, you need Vercel Pro or use an external scheduler like [Upstash QStash](https://upstash.com/docs/qstash).

## License

MIT
