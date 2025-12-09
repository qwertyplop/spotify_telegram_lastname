"""
Status API endpoint for dashboard.
Returns current sync status and track info.
"""

import os
import sys
import time
import json
from http.server import BaseHTTPRequestHandler

# Add lib to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from lib import storage


def get_status() -> dict:
    """
    Get current sync status.

    Returns:
        Dict with full status information
    """
    state = storage.get_state()
    track = storage.get_current_track()
    tokens = storage.get_tokens()
    errors = storage.get_errors()
    flood_until = storage.get_flood_wait_until()
    session_exists = bool(storage.get_session())

    # Calculate relative times
    now = time.time()
    last_sync = state.get('last_sync', 0)
    last_update = state.get('last_update', 0)

    # Token status
    token_expires_at = tokens.get('expires_at', 0) if tokens else 0
    token_valid = token_expires_at > now if tokens else False

    # Rate limit status
    rate_limited = flood_until > now if flood_until else False
    rate_limit_remaining = int(flood_until - now) if rate_limited else 0

    return {
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
        'errors': errors[:5],  # Last 5 errors
        'timestamp': now,
    }


class handler(BaseHTTPRequestHandler):
    """Vercel serverless function handler."""

    def do_GET(self):
        status = get_status()

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(status, indent=2).encode())

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def log_message(self, format, *args):
        """Suppress HTTP server logging."""
        pass
