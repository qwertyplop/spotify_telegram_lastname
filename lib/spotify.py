"""
Spotify API helpers for token management and track fetching.
"""

import os
import time
from dataclasses import dataclass
from typing import Optional

import requests


SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_PLAYER_URL = "https://api.spotify.com/v1/me/player/currently-playing"
SPOTIFY_TIMEOUT = 15


@dataclass
class SpotifyToken:
    """Manages Spotify access token lifecycle."""
    access_token: str
    refresh_token: str
    expires_at: float

    def is_expired(self, buffer_seconds: int = 300) -> bool:
        """Check if token is expired (with buffer)."""
        return time.time() >= (self.expires_at - buffer_seconds)


@dataclass
class TrackInfo:
    """Information about a currently playing track."""
    title: str
    artist: str
    album: Optional[str] = None
    is_playing: bool = True

    def __bool__(self) -> bool:
        """Track is valid if it has title and artist."""
        return bool(self.title and self.artist)

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            'title': self.title,
            'artist': self.artist,
            'album': self.album,
            'is_playing': self.is_playing,
        }


def get_credentials() -> tuple:
    """Get Spotify credentials from environment."""
    client_id = os.environ.get('SPOTIFY_CLIENT_ID')
    client_secret = os.environ.get('SPOTIFY_CLIENT_SECRET')

    if not client_id or not client_secret:
        raise RuntimeError("SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET required")

    return client_id, client_secret


def refresh_access_token(refresh_token: str) -> SpotifyToken:
    """
    Refresh Spotify access token using a refresh token.

    Args:
        refresh_token: Long-lived refresh token

    Returns:
        SpotifyToken with new access token and expiration

    Raises:
        RuntimeError: If token refresh fails
    """
    client_id, client_secret = get_credentials()

    payload = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }

    try:
        resp = requests.post(
            SPOTIFY_TOKEN_URL,
            data=payload,
            auth=(client_id, client_secret),
            timeout=SPOTIFY_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        raise RuntimeError(f"Failed to refresh Spotify token: {e}")

    access_token = data["access_token"]
    # Use new refresh token if provided, otherwise keep the old one
    new_refresh_token = data.get("refresh_token", refresh_token)
    # Default to 3600s if not specified
    expires_in = int(data.get("expires_in", 3600))
    expires_at = time.time() + expires_in

    return SpotifyToken(
        access_token=access_token,
        refresh_token=new_refresh_token,
        expires_at=expires_at,
    )


def get_current_track(access_token: str) -> Optional[TrackInfo]:
    """
    Fetch currently playing track from Spotify.

    Args:
        access_token: Valid Spotify access token

    Returns:
        TrackInfo if track is playing, None otherwise

    Raises:
        RuntimeError: If token is expired (401 response)
    """
    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        resp = requests.get(
            SPOTIFY_PLAYER_URL,
            headers=headers,
            timeout=SPOTIFY_TIMEOUT,
        )
    except requests.exceptions.Timeout:
        print("Spotify API timeout")
        return None
    except Exception as e:
        print(f"Spotify API error: {e}")
        return None

    # 204: No content (nothing playing)
    if resp.status_code == 204:
        return None

    # 401: Token expired
    if resp.status_code == 401:
        raise RuntimeError("Spotify token expired")

    # Other errors
    if resp.status_code != 200:
        print(f"Spotify API error: {resp.status_code}")
        return None

    data = resp.json()
    if not data:
        return None

    is_playing = data.get("is_playing", False)
    if not is_playing:
        return None

    item = data.get("item") or {}
    title = (item.get("name") or "").strip()
    artist_list = item.get("artists") or []
    artists = ", ".join(a.get("name", "") for a in artist_list if a)
    album = (item.get("album") or {}).get("name") or ""

    if not title or not artists:
        return None

    return TrackInfo(
        title=title,
        artist=artists,
        album=album,
        is_playing=True,
    )
