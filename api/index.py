"""
Flask API for Spotify-Telegram Sync.
Deployed as a Vercel serverless function.
"""

import os
import sys
import time
import json

from flask import Flask, jsonify, request

# Add parent directory to path for lib imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from lib import storage, spotify, telegram, formatting

app = Flask(__name__)

# Constants
MIN_UPDATE_INTERVAL = 180  # 3 minutes for same track
TRACK_CHANGE_INTERVAL = 60  # 1 minute for different track


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


@app.route('/')
def home():
    """Health check."""
    return jsonify({
        'status': 'ok',
        'service': 'spotify-telegram-sync',
        'timestamp': time.time()
    })


@app.route('/api/status')
def status():
    """Get current sync status."""
    state = storage.get_state()
    track = storage.get_current_track()
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
        'track': track,
        'sync': {
            'status': state.get('status', 'unknown'),
            'last_sync': last_sync,
            'last_sync_ago': int(now - last_sync) if last_sync else None,
            'last_update': last_update,
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


@app.route('/api/sync')
def sync():
    """Cron-triggered sync function."""
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
            return jsonify(result)

        # Get Telegram session
        session = storage.get_session()
        if not session:
            result['message'] = 'No Telegram session configured'
            storage.log_error('No Telegram session', 'sync')
            return jsonify(result)

        # Get/refresh Spotify tokens
        tokens = storage.get_tokens()
        if not tokens:
            refresh_token = os.environ.get('SPOTIFY_REFRESH_TOKEN')
            if not refresh_token:
                result['message'] = 'No Spotify tokens configured'
                storage.log_error('No Spotify tokens', 'sync')
                return jsonify(result)

            token = spotify.refresh_access_token(refresh_token)
            storage.save_tokens(token.access_token, token.refresh_token, token.expires_at)
            access_token = token.access_token
        else:
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
                return jsonify(result)

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
            return jsonify(result)

        # Check if name actually changed
        if desired_name == state.get('current_last_name'):
            result['success'] = True
            result['action'] = 'skipped'
            result['message'] = 'Name unchanged'
            storage.save_state(state)
            return jsonify(result)

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
            wait_until = time.time() + flood_wait + 10
            storage.set_flood_wait_until(wait_until)
            storage.log_error(f'FloodWaitError: {flood_wait}s', 'telegram_update')

            result['action'] = 'rate_limited'
            result['message'] = f'Rate limited for {flood_wait}s'
        else:
            storage.log_error('Unknown update error', 'telegram_update')
            result['message'] = 'Update failed'

        return jsonify(result)

    except Exception as e:
        result['message'] = str(e)
        storage.log_error(str(e), 'sync')
        return jsonify(result)


@app.route('/api/init')
def init():
    """Initialize storage with credentials from environment."""
    result = {
        'success': False,
        'steps': [],
        'errors': [],
    }

    # Step 1: Store Telegram session
    session = os.environ.get('TELEGRAM_STRING_SESSION')
    if session:
        if storage.save_session(session):
            result['steps'].append('Telegram session stored')
        else:
            result['errors'].append('Failed to store Telegram session')
    else:
        result['errors'].append('TELEGRAM_STRING_SESSION not set')

    # Step 2: Initialize Spotify tokens
    refresh_token = os.environ.get('SPOTIFY_REFRESH_TOKEN')
    if refresh_token:
        try:
            token = spotify.refresh_access_token(refresh_token)
            if storage.save_tokens(token.access_token, token.refresh_token, token.expires_at):
                result['steps'].append('Spotify tokens stored')
            else:
                result['errors'].append('Failed to store Spotify tokens')
        except Exception as e:
            result['errors'].append(f'Spotify token error: {e}')
    else:
        result['errors'].append('SPOTIFY_REFRESH_TOKEN not set')

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


# Vercel requires this
if __name__ == '__main__':
    app.run(debug=True)
