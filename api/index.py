"""
Flask API for Spotify-Telegram Sync.
Deployed as a Vercel serverless function.
"""

import os
import sys
import time
import secrets
import urllib.parse
from datetime import datetime

from flask import Flask, jsonify, request, redirect, send_from_directory, make_response

# Add parent directory to path for lib imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from lib import storage, spotify, telegram, formatting
from lib.logger import get_logger, set_correlation_id, clear_correlation_id, get_correlation_id

# Module-level logger
logger = get_logger('api')


def format_gmt3(timestamp):
    """Format timestamp as absolute datetime in GMT+3 timezone."""
    if not timestamp:
        return "Never"
    try:
        dt = datetime.fromtimestamp(timestamp)
        # Format as "Feb 15, 2026 3:45 PM GMT+3"
        return dt.strftime("%b %d, %Y %I:%M %p") + " GMT+3"
    except (ValueError, OSError):
        return "Never"


app = Flask(__name__, static_folder='../static')

# Constants
MIN_UPDATE_INTERVAL = 180  # 3 minutes for same track
TRACK_CHANGE_INTERVAL = 60  # 1 minute for different track

# Spotify OAuth
SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_SCOPES = "user-read-currently-playing user-read-playback-state"


def get_base_url():
    """Get base URL from request or environment."""
    return os.environ.get('VERCEL_URL', request.host_url.rstrip('/'))


def should_update(state: dict, new_track_key: str) -> bool:
    """Determine if we should update Telegram."""
    last_key = state.get('last_track_key')
    last_update = state.get('last_update', 0)
    elapsed = time.time() - last_update

    if not last_key:
        return True
    if last_key != new_track_key:
        return elapsed >= TRACK_CHANGE_INTERVAL
    return elapsed >= MIN_UPDATE_INTERVAL


# Dashboard HTML embedded
DASHBOARD_HTML = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Spotify-Telegram Sync</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            color: #e4e4e7;
            padding: 2rem;
        }
        .container { max-width: 600px; margin: 0 auto; }
        h1 { text-align: center; margin-bottom: 2rem; font-size: 1.75rem; color: #fff; }
        .card {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 1rem;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }
        .card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; }
        .card-title { font-size: 0.875rem; text-transform: uppercase; letter-spacing: 0.05em; color: #a1a1aa; }
        .status-dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
        .status-dot.green { background: #22c55e; box-shadow: 0 0 8px #22c55e; }
        .status-dot.red { background: #ef4444; box-shadow: 0 0 8px #ef4444; }
        .track-info { text-align: center; }
        .track-title { font-size: 1.5rem; font-weight: 600; color: #fff; margin-bottom: 0.5rem; }
        .track-artist { font-size: 1rem; color: #1db954; }
        .track-album { font-size: 0.875rem; color: #a1a1aa; margin-top: 0.25rem; }
        .not-playing { text-align: center; color: #71717a; font-style: italic; }
        .stat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
        .stat-item { text-align: center; }
        .stat-value { font-size: 1.25rem; font-weight: 600; color: #fff; }
        .stat-label { font-size: 0.75rem; color: #a1a1aa; margin-top: 0.25rem; }
        .current-name {
            background: rgba(29, 185, 84, 0.1);
            border: 1px solid rgba(29, 185, 84, 0.3);
            border-radius: 8px;
            padding: 1rem;
            text-align: center;
            margin-top: 1rem;
        }
        .current-name-label { font-size: 0.75rem; color: #a1a1aa; margin-bottom: 0.5rem; }
        .current-name-value { font-size: 1.125rem; color: #1db954; font-weight: 500; }
        .connection-status { display: flex; gap: 1.5rem; justify-content: center; flex-wrap: wrap; }
        .connection-item { display: flex; align-items: center; gap: 0.5rem; }
        .error-card { background: rgba(239, 68, 68, 0.1); border-color: rgba(239, 68, 68, 0.3); }
        .error-item { font-size: 0.875rem; padding: 0.5rem 0; border-bottom: 1px solid rgba(255, 255, 255, 0.05); }
        .error-item:last-child { border-bottom: none; }
        .error-time { font-size: 0.75rem; color: #a1a1aa; }
        .loading { text-align: center; padding: 3rem; color: #a1a1aa; }
        .refresh-info { text-align: center; font-size: 0.75rem; color: #71717a; margin-top: 1rem; }
        .rate-limit-banner {
            background: rgba(234, 179, 8, 0.1);
            border: 1px solid rgba(234, 179, 8, 0.3);
            border-radius: 8px;
            padding: 1rem;
            text-align: center;
            margin-bottom: 1rem;
            color: #eab308;
        }
        .btn {
            display: inline-block;
            padding: 0.75rem 1.5rem;
            border-radius: 8px;
            font-weight: 500;
            text-decoration: none;
            cursor: pointer;
            border: none;
            font-size: 1rem;
            transition: opacity 0.2s;
        }
        .btn:hover { opacity: 0.9; }
        .btn-spotify { background: #1db954; color: #fff; }
        .btn-init { background: #3b82f6; color: #fff; margin-left: 0.5rem; }
        .btn-sync { background: #8b5cf6; color: #fff; padding: 0.5rem 1rem; font-size: 0.875rem; }
        .btn-sync:disabled { background: #6b7280; cursor: not-allowed; }
        .syncing { color: #8b5cf6; font-style: italic; }
        .setup-card { text-align: center; }
        .setup-card p { margin-bottom: 1rem; color: #a1a1aa; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Spotify-Telegram Sync</h1>
        <div id="content"><div class="loading">Loading...</div></div>
        <div class="refresh-info">Auto-refreshes every 30 seconds</div>
    </div>
    <script>
        function formatTimeAgo(seconds) {
            if (!seconds) return 'Never';
            if (seconds < 60) return seconds + 's ago';
            if (seconds < 3600) return Math.floor(seconds / 60) + 'm ago';
            return Math.floor(seconds / 3600) + 'h ago';
        }
        function escapeHtml(text) {
            if (!text) return '';
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        function renderStatus(data) {
            const content = document.getElementById('content');
            const telegramOk = data.connected.telegram;
            const spotifyOk = data.connected.spotify;

            // Setup needed
            if (!telegramOk || !spotifyOk) {
                let setupHtml = '<div class="card setup-card"><div class="card-header"><span class="card-title">Setup Required</span></div>';
                if (!spotifyOk) {
                    setupHtml += '<p>Connect your Spotify account to get started.</p><a href="/api/spotify/auth" class="btn btn-spotify">Connect Spotify</a>';
                }
                if (!telegramOk) {
                    setupHtml += '<p style="margin-top:1rem;">Telegram session not configured. Set TELEGRAM_STRING_SESSION env var.</p>';
                }
                if (spotifyOk || telegramOk) {
                    setupHtml += '<a href="/api/init" class="btn btn-init">Initialize</a>';
                }
                setupHtml += '</div>';
                content.innerHTML = setupHtml;
                return;
            }

            let rateLimitHtml = data.rate_limit && data.rate_limit.active
                ? '<div class="rate-limit-banner">Rate limited - ' + data.rate_limit.remaining_seconds + 's remaining</div>'
                : '';

            let errorsHtml = '';
            if (data.errors && data.errors.length > 0) {
                errorsHtml = '<div class="card error-card"><div class="card-header"><span class="card-title">Recent Errors</span></div>' +
                    data.errors.slice(0, 3).map(function(err) {
                        return '<div class="error-item"><div>' + escapeHtml(err.error) + '</div><div class="error-time">' + err.context + '</div></div>';
                    }).join('') + '</div>';
            }

            content.innerHTML = rateLimitHtml +
                '<div class="card"><div class="card-header"><span class="card-title">Connection Status</span></div>' +
                '<div class="connection-status">' +
                '<div class="connection-item"><span class="status-dot green"></span><span>Telegram</span></div>' +
                '<div class="connection-item"><span class="status-dot green"></span><span>Spotify</span></div>' +
                '</div></div>' +
                '<div class="card"><div class="card-header"><span class="card-title">Sync Status</span><button class="btn-sync" onclick="triggerSync()" id="syncBtn">Sync Now</button></div>' +
                '<div id="syncStatus"></div>' +
                '<div class="stat-grid">' +
                '<div class="stat-item"><div class="stat-value">' + (data.sync.last_sync_formatted || 'Never') + '</div><div class="stat-label">Last Sync</div></div>' +
                '<div class="stat-item"><div class="stat-value">' + (data.sync.last_update_formatted || 'Never') + '</div><div class="stat-label">Last Update</div></div>' +
                '<div class="stat-item"><div class="stat-value">' + data.sync.update_count + '</div><div class="stat-label">Total Updates</div></div>' +
                '<div class="stat-item"><div class="stat-value">' + (data.spotify_token.valid ? Math.floor(data.spotify_token.expires_in / 60) + 'm' : 'Expired') + '</div><div class="stat-label">Token Expires</div></div>' +
                '</div>' +
                (data.sync.current_name ? '<div class="current-name"><div class="current-name-label">Current Telegram Name</div><div class="current-name-value">' + escapeHtml(data.sync.current_name) + '</div></div>' : '') +
                '</div>' + errorsHtml;
        }
        async function fetchStatus() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();
                renderStatus(data);
            } catch (error) {
                document.getElementById('content').innerHTML = '<div class="card error-card"><div class="card-header"><span class="card-title">Error</span></div><div>Failed to fetch status</div></div>';
            }
        }
        let isSyncing = false;
        async function triggerSync() {
            if (isSyncing) return;
            isSyncing = true;
            const syncBtn = document.getElementById('syncBtn');
            const syncStatus = document.getElementById('syncStatus');
            if (syncBtn) {
                syncBtn.disabled = true;
                syncBtn.textContent = 'Syncing...';
            }
            if (syncStatus) {
                syncStatus.innerHTML = '<div class="syncing">Syncing...</div>';
            }
            try {
                const response = await fetch('/api/sync');
                const result = await response.json();
                if (syncStatus) {
                    if (result.success) {
                        syncStatus.innerHTML = '<div style="color: #22c55e; margin-top: 0.5rem;">' + result.message + '</div>';
                    } else {
                        syncStatus.innerHTML = '<div style="color: #ef4444; margin-top: 0.5rem;">' + result.message + '</div>';
                    }
                }
                // Refresh status after sync
                await fetchStatus();
            } catch (error) {
                if (syncStatus) {
                    syncStatus.innerHTML = '<div style="color: #ef4444; margin-top: 0.5rem;">Sync failed</div>';
                }
            } finally {
                isSyncing = false;
                if (syncBtn) {
                    syncBtn.disabled = false;
                    syncBtn.textContent = 'Sync Now';
                }
            }
        }
        fetchStatus();
        setInterval(fetchStatus, 30000);
    </script>
</body>
</html>'''


@app.route('/')
def home():
    """Serve dashboard."""
    return DASHBOARD_HTML


@app.route('/api/status')
def status():
    """Get current sync status."""
    logger.debug("Status requested")
    
    state = storage.get_state()
    tokens = storage.get_tokens()
    errors = storage.get_errors()
    flood_until = storage.get_flood_wait_until()
    session_exists = bool(storage.get_session())

    now = time.time()
    last_sync = state.get('last_sync', 0)
    last_update = state.get('last_update', 0)

    token_expires_at = tokens.get('expires_at', 0) if tokens else 0
    token_valid = token_expires_at > now if tokens else False

    rate_limited = flood_until > now if flood_until else False
    rate_limit_remaining = int(flood_until - now) if rate_limited else 0

    return jsonify({
        'connected': {
            'telegram': session_exists,
            'spotify': token_valid,
        },
        'sync': {
            'status': state.get('status', 'unknown'),
            'last_sync': last_sync,
            'last_sync_formatted': format_gmt3(last_sync),
            'last_update': last_update,
            'last_update_formatted': format_gmt3(last_update),
            'last_sync_ago': int(now - last_sync) if last_sync else None,
            'last_update_ago': int(now - last_update) if last_update else None,
            'update_count': state.get('update_count', 0),
            'current_name': state.get('current_last_name', ''),
            'original_name': state.get('original_last_name', ''),
        },
        'rate_limit': {
            'active': rate_limited,
            'remaining_seconds': rate_limit_remaining,
        },
        'spotify_token': {
            'valid': token_valid,
            'expires_at': token_expires_at,
            'expires_in': int(token_expires_at - now) if token_valid else 0,
        },
        'errors': errors[:5],
        'timestamp': now,
    })


@app.route('/api/spotify/auth')
def spotify_auth():
    """Start Spotify OAuth flow."""
    logger.info("Spotify OAuth initiated")
    
    client_id = os.environ.get('SPOTIFY_CLIENT_ID')
    if not client_id:
        return jsonify({'error': 'SPOTIFY_CLIENT_ID not configured'}), 500

    # Generate state for CSRF protection
    state = secrets.token_urlsafe(16)

    # Build redirect URI
    base_url = request.host_url.rstrip('/')
    redirect_uri = f"{base_url}/api/spotify/callback"

    params = {
        'client_id': client_id,
        'response_type': 'code',
        'redirect_uri': redirect_uri,
        'scope': SPOTIFY_SCOPES,
        'state': state,
        'show_dialog': 'true',
    }

    auth_url = f"{SPOTIFY_AUTH_URL}?{urllib.parse.urlencode(params)}"

    # Store state in cookie
    response = make_response(redirect(auth_url))
    response.set_cookie('spotify_oauth_state', state, max_age=600, httponly=True, samesite='Lax')
    return response


@app.route('/api/spotify/callback')
def spotify_callback():
    """Handle Spotify OAuth callback."""
    import requests
    
    logger.info("Spotify OAuth callback received")
    
    error = request.args.get('error')
    if error:
        return f"<h1>Error</h1><p>{error}</p><a href='/'>Back to dashboard</a>"

    code = request.args.get('code')
    state = request.args.get('state')

    if not code:
        return "<h1>Error</h1><p>No authorization code received</p><a href='/'>Back</a>"

    # Verify state from cookie
    stored_state = request.cookies.get('spotify_oauth_state')
    if not stored_state or stored_state != state:
        return "<h1>Error</h1><p>Invalid state parameter. Please try again.</p><a href='/api/spotify/auth'>Retry</a>"

    # Exchange code for tokens
    client_id = os.environ.get('SPOTIFY_CLIENT_ID')
    client_secret = os.environ.get('SPOTIFY_CLIENT_SECRET')

    base_url = request.host_url.rstrip('/')
    redirect_uri = f"{base_url}/api/spotify/callback"

    try:
        resp = requests.post(
            SPOTIFY_TOKEN_URL,
            data={
                'grant_type': 'authorization_code',
                'code': code,
                'redirect_uri': redirect_uri,
            },
            auth=(client_id, client_secret),
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return f"<h1>Error</h1><p>Token exchange failed: {e}</p><a href='/'>Back</a>"

    # Save tokens
    access_token = data.get('access_token')
    refresh_token = data.get('refresh_token')
    expires_in = data.get('expires_in', 3600)
    expires_at = time.time() + expires_in

    if not refresh_token:
        return "<h1>Error</h1><p>No refresh token received</p><a href='/'>Back</a>"

    storage.save_tokens(access_token, refresh_token, expires_at)

    return """
    <html>
    <head><meta http-equiv="refresh" content="2;url=/"></head>
    <body style="background:#1a1a2e;color:#fff;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;">
    <div style="text-align:center;">
        <h1 style="color:#1db954;">Spotify Connected!</h1>
        <p>Redirecting to dashboard...</p>
    </div>
    </body>
    </html>
    """


@app.route('/api/sync')
def sync():
    """
    Cron-triggered sync function.
    Optimized to minimize blob operations (max 1 write per sync).
    """
    # Generate correlation ID for this sync cycle
    cid = get_correlation_id()
    set_correlation_id(cid)
    
    logger.info(f"=== Sync cycle started === (correlation_id={cid})")
    logger.debug(f"Environment: Vercel={bool(os.environ.get('VERCEL_URL'))}, Region={os.environ.get('VERCEL_REGION', 'local')}")
    
    result = {
        'success': False,
        'action': 'none',
        'message': '',
        'timestamp': time.time(),
    }

    # Track what needs to be saved (batch at end)
    updates = {}
    needs_save = False

    try:
        # Load all data once (1 list + 1 read = 1 advanced + 1 simple)
        logger.info("Loading state from storage")
        all_data = storage._load_all_data()
        
        state = all_data.get('sync_state') or {}
        logger.debug(f"Current state: last_sync={state.get('last_update', 0)}, last_key={state.get('last_track_key')}")

        # Check flood wait
        logger.info("Checking flood wait")
        flood_until = all_data.get('flood_wait_until', 0)
        if flood_until and time.time() < flood_until:
            wait_remaining = int(flood_until - time.time())
            logger.info(f"Rate limited, {wait_remaining}s remaining")
            result['action'] = 'rate_limited'
            result['message'] = f'Rate limited, {wait_remaining}s remaining'
            clear_correlation_id()
            return jsonify(result)

        # Get Telegram session
        session = all_data.get('telegram_session') or os.environ.get('TELEGRAM_STRING_SESSION')
        if not session:
            logger.warning("No Telegram session configured")
            result['message'] = 'No Telegram session configured'
            clear_correlation_id()
            return jsonify(result)

        # Get/refresh Spotify tokens
        logger.info("Checking Spotify tokens")
        tokens = all_data.get('spotify_tokens')
        if not tokens or not tokens.get('refresh_token'):
            refresh_token = os.environ.get('SPOTIFY_REFRESH_TOKEN')
            if not refresh_token:
                logger.warning("No Spotify tokens configured")
                result['message'] = 'No Spotify tokens configured'
                clear_correlation_id()
                return jsonify(result)
            tokens = {'refresh_token': refresh_token}

        # Check if token needs refresh
        access_token = tokens.get('access_token')
        if not access_token or time.time() >= (tokens.get('expires_at', 0) - 300):
            logger.info("Token refresh required")
            token = spotify.refresh_access_token(tokens['refresh_token'])
            updates['spotify_tokens'] = {
                'access_token': token.access_token,
                'refresh_token': token.refresh_token,
                'expires_at': token.expires_at,
            }
            access_token = token.access_token
            needs_save = True
            logger.info("Token refreshed successfully")

        # Get current track from Spotify
        logger.info("Fetching current track from Spotify")
        try:
            track = spotify.get_current_track(access_token)
        except RuntimeError:
            # Token expired mid-request
            logger.info("Token expired mid-request, refreshing")
            token = spotify.refresh_access_token(tokens['refresh_token'])
            updates['spotify_tokens'] = {
                'access_token': token.access_token,
                'refresh_token': token.refresh_token,
                'expires_at': token.expires_at,
            }
            track = spotify.get_current_track(token.access_token)
            needs_save = True
            logger.info("Token refreshed after expiry")

        logger.debug(f"Track info: {track.to_dict() if track else 'None'}")

        # Get current state
        state = all_data.get('sync_state') or {
            'original_last_name': '',
            'current_last_name': '',
            'last_track_key': None,
            'last_update': 0,
            'update_count': 0,
            'status': 'initialized',
        }

        # Get original last name if not set
        if not state.get('original_last_name'):
            logger.info("No original last name set, fetching from Telegram")
            try:
                original = telegram.run_async(telegram.get_last_name(session))
                state['original_last_name'] = original
                needs_save = True
                logger.info(f"Original name captured: {original}")
            except Exception as e:
                logger.error(f"Failed to get original name: {e}")
                result['message'] = f'Failed to get original name: {e}'
                clear_correlation_id()
                return jsonify(result)

        # Generate track key and formatted name
        track_key = formatting.generate_track_key(track)
        desired_name = formatting.format_last_name(
            track,
            state.get('original_last_name', ''),
        )

        # Check if update is needed
        logger.info("Checking update criteria")
        should_upd = should_update(state, track_key)
        last_key = state.get('last_track_key')
        elapsed = time.time() - state.get('last_update', 0)
        logger.debug(f"should_update: {should_upd}, last_key: {last_key}, elapsed: {elapsed:.0f}s")
        
        if not should_upd:
            result['success'] = True
            result['action'] = 'skipped'
            result['message'] = 'No update needed'
            logger.info(f"Update skipped: {result['message']}")
            # Always save last_sync timestamp and current_track
            state['last_sync'] = time.time()
            updates['sync_state'] = state
            updates['current_track'] = track.to_dict() if track else {'is_playing': False}
            storage.batch_update(**updates)
            clear_correlation_id()
            return jsonify(result)

        # Check if name actually changed
        if desired_name == state.get('current_last_name'):
            result['success'] = True
            result['action'] = 'skipped'
            result['message'] = 'Name unchanged'
            logger.info(f"Update skipped: {result['message']}")
            # Always save last_sync timestamp and current_track
            state['last_sync'] = time.time()
            updates['sync_state'] = state
            updates['current_track'] = track.to_dict() if track else {'is_playing': False}
            storage.batch_update(**updates)
            clear_correlation_id()
            return jsonify(result)

        # Perform Telegram update
        logger.info(f"Updating Telegram last name to: {desired_name}")
        success, flood_wait = telegram.run_async(
            telegram.update_last_name_safe(session, desired_name)
        )

        if success:
            state['current_last_name'] = desired_name
            state['last_track_key'] = track_key
            state['last_update'] = time.time()
            state['last_sync'] = time.time()
            state['update_count'] = state.get('update_count', 0) + 1
            state['status'] = 'active'
            updates['sync_state'] = state
            updates['current_track'] = track.to_dict() if track else {'is_playing': False}

            result['success'] = True
            result['action'] = 'updated'
            result['message'] = f'Updated to: {desired_name}'
            logger.info(f"Telegram update successful: {desired_name}")
        elif flood_wait:
            updates['flood_wait_until'] = time.time() + flood_wait + 10
            result['action'] = 'rate_limited'
            result['message'] = f'Rate limited for {flood_wait}s'
            logger.warning(f"Telegram rate limited for {flood_wait}s")
        else:
            result['message'] = 'Update failed'
            logger.error("Telegram update failed")

        # Single batch save at end (1 put = 1 advanced operation)
        logger.info("Saving state to storage")
        if updates:
            storage.batch_update(**updates)

        logger.info(f"=== Sync cycle completed: {result['action']} ===")
        clear_correlation_id()
        return jsonify(result)

    except Exception as e:
        import traceback
        logger.error(f"Sync failed: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        result['message'] = str(e)
        clear_correlation_id()
        return jsonify(result)


@app.route('/api/init')
def init():
    """Initialize storage with credentials from environment."""
    logger.info("Initialization requested")
    
    result = {
        'success': False,
        'steps': [],
        'errors': [],
        'warnings': [],
    }

    # Step 1: Check Telegram session
    session = storage.get_session()  # Checks blob first, then env var
    if session:
        result['steps'].append('Telegram session available')
        # Try to store in blob for persistence (optional)
        if storage.save_session(session):
            result['steps'].append('Telegram session stored in blob')
        else:
            result['warnings'].append('Blob storage not available - using env var only')
    else:
        result['errors'].append('TELEGRAM_STRING_SESSION not set in environment variables')

    # Step 2: Check Spotify tokens
    tokens = storage.get_tokens()
    if tokens and tokens.get('refresh_token'):
        result['steps'].append('Spotify tokens available')
    else:
        # Try to get from env var
        refresh_token = os.environ.get('SPOTIFY_REFRESH_TOKEN')
        if refresh_token:
            try:
                token = spotify.refresh_access_token(refresh_token)
                storage.save_tokens(token.access_token, token.refresh_token, token.expires_at)
                result['steps'].append('Spotify tokens initialized from env var')
            except Exception as e:
                result['errors'].append(f'Spotify token error: {e}')
        else:
            result['errors'].append('Spotify not connected. Click "Connect Spotify" button first.')

    # Step 3: Get original Telegram last name
    if session:
        try:
            original_name = telegram.run_async(telegram.get_last_name(session))
            state = storage.get_state()
            state['original_last_name'] = original_name
            state['status'] = 'initialized'
            storage.save_state(state)
            result['steps'].append(f'Original name captured: "{original_name}"')
        except Exception as e:
            result['errors'].append(f'Failed to get Telegram name: {e}')

    result['success'] = len(result['errors']) == 0
    return jsonify(result)


if __name__ == '__main__':
    app.run(debug=True)
