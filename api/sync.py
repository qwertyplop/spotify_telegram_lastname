"""
Cron-triggered sync function.
Polls Spotify for current track and updates Telegram last name.
"""

import os
import sys
import time
import json
from http.server import BaseHTTPRequestHandler

# Add lib to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from lib import storage, spotify, telegram, formatting


MIN_UPDATE_INTERVAL = 180  # 3 minutes for same track
TRACK_CHANGE_INTERVAL = 60  # 1 minute for different track


def verify_cron_secret(headers) -> bool:
    """Verify cron request authenticity (optional)."""
    secret = os.environ.get('CRON_SECRET')
    if not secret:
        return True  # No secret configured, allow all

    auth_header = headers.get('Authorization', '')
    return auth_header == f'Bearer {secret}'


def should_update(state: dict, new_track_key: str, min_interval: int = MIN_UPDATE_INTERVAL) -> bool:
    """Determine if we should update Telegram."""
    last_key = state.get('last_track_key')
    last_update = state.get('last_update', 0)
    elapsed = time.time() - last_update

    if not last_key:
        # First update
        return True

    if last_key != new_track_key:
        # Track changed - can update more frequently
        return elapsed >= TRACK_CHANGE_INTERVAL

    # Same track - update less frequently
    return elapsed >= min_interval


def perform_sync() -> dict:
    """
    Main sync logic.

    Returns:
        Dict with sync result status
    """
    result = {
        'success': False,
        'action': 'none',
        'message': '',
        'timestamp': time.time(),
    }

    try:
        # Check flood wait
        flood_until = storage.get_flood_wait_until()
        if flood_until and time.time() < flood_until:
            wait_remaining = int(flood_until - time.time())
            result['action'] = 'rate_limited'
            result['message'] = f'Rate limited, {wait_remaining}s remaining'
            return result

        # Get Telegram session
        session = storage.get_session()
        if not session:
            result['message'] = 'No Telegram session configured'
            storage.log_error('No Telegram session', 'sync')
            return result

        # Get/refresh Spotify tokens
        tokens = storage.get_tokens()
        if not tokens:
            # Try from environment
            refresh_token = os.environ.get('SPOTIFY_REFRESH_TOKEN')
            if not refresh_token:
                result['message'] = 'No Spotify tokens configured'
                storage.log_error('No Spotify tokens', 'sync')
                return result

            # Get fresh tokens
            token = spotify.refresh_access_token(refresh_token)
            storage.save_tokens(token.access_token, token.refresh_token, token.expires_at)
            access_token = token.access_token
        else:
            # Check if token needs refresh
            if time.time() >= (tokens.get('expires_at', 0) - 300):
                token = spotify.refresh_access_token(tokens['refresh_token'])
                storage.save_tokens(token.access_token, token.refresh_token, token.expires_at)
                access_token = token.access_token
            else:
                access_token = tokens['access_token']

        # Get current track
        try:
            track = spotify.get_current_track(access_token)
        except RuntimeError:
            # Token expired mid-request, refresh and retry
            refresh_token = tokens.get('refresh_token') if tokens else os.environ.get('SPOTIFY_REFRESH_TOKEN')
            token = spotify.refresh_access_token(refresh_token)
            storage.save_tokens(token.access_token, token.refresh_token, token.expires_at)
            track = spotify.get_current_track(token.access_token)

        # Save track info
        storage.save_current_track(track.to_dict() if track else None)

        # Get current state
        state = storage.get_state()

        # Get original last name if not set
        if not state.get('original_last_name'):
            try:
                original = telegram.run_async(telegram.get_last_name(session))
                state['original_last_name'] = original
            except Exception as e:
                result['message'] = f'Failed to get original name: {e}'
                storage.log_error(str(e), 'get_original_name')
                return result

        # Generate track key and formatted name
        track_key = formatting.generate_track_key(track)
        desired_name = formatting.format_last_name(
            track,
            state.get('original_last_name', ''),
        )

        # Check if update is needed
        if not should_update(state, track_key):
            result['success'] = True
            result['action'] = 'skipped'
            result['message'] = 'No update needed'
            storage.save_state(state)
            return result

        # Check if name actually changed
        if desired_name == state.get('current_last_name'):
            result['success'] = True
            result['action'] = 'skipped'
            result['message'] = 'Name unchanged'
            storage.save_state(state)
            return result

        # Perform Telegram update
        success, flood_wait = telegram.run_async(
            telegram.update_last_name_safe(session, desired_name)
        )

        if success:
            state['current_last_name'] = desired_name
            state['last_track_key'] = track_key
            state['last_update'] = time.time()
            state['update_count'] = state.get('update_count', 0) + 1
            state['status'] = 'active'
            storage.save_state(state)

            result['success'] = True
            result['action'] = 'updated'
            result['message'] = f'Updated to: {desired_name}'
        elif flood_wait:
            # Set flood wait
            wait_until = time.time() + flood_wait + 10  # Buffer
            storage.set_flood_wait_until(wait_until)
            storage.log_error(f'FloodWaitError: {flood_wait}s', 'telegram_update')

            result['action'] = 'rate_limited'
            result['message'] = f'Rate limited for {flood_wait}s'
        else:
            storage.log_error('Unknown update error', 'telegram_update')
            result['message'] = 'Update failed'

        return result

    except Exception as e:
        result['message'] = str(e)
        storage.log_error(str(e), 'sync')
        return result


class handler(BaseHTTPRequestHandler):
    """Vercel serverless function handler."""

    def do_GET(self):
        # Optional: verify cron secret
        if not verify_cron_secret(self.headers):
            self.send_response(401)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': 'Unauthorized'}).encode())
            return

        # Perform sync
        result = perform_sync()

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(result).encode())

    def log_message(self, format, *args):
        """Suppress HTTP server logging."""
        pass
