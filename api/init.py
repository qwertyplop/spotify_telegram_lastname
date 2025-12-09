"""
Initialization endpoint for first-time setup.
Stores credentials in Vercel Blob from environment variables.
"""

import os
import sys
import json
from http.server import BaseHTTPRequestHandler

# Add lib to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from lib import storage, spotify, telegram


def initialize() -> dict:
    """
    Initialize storage with credentials from environment.

    Returns:
        Dict with initialization result
    """
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

    # Determine success
    result['success'] = len(result['errors']) == 0

    return result


class handler(BaseHTTPRequestHandler):
    """Vercel serverless function handler."""

    def do_POST(self):
        result = initialize()

        status_code = 200 if result['success'] else 500
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(result, indent=2).encode())

    def do_GET(self):
        """Also allow GET for easy browser testing."""
        self.do_POST()

    def log_message(self, format, *args):
        """Suppress HTTP server logging."""
        pass
