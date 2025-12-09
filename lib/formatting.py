"""
Track formatting utilities for generating Telegram last name.
"""

import os
import re
from typing import Optional

from .spotify import TrackInfo


DEFAULT_TEMPLATE = "| {artist_first} - {title}"
DEFAULT_TRUNCATE = 64


def get_template() -> str:
    """Get name template from environment or default."""
    return os.environ.get('NAME_TEMPLATE', DEFAULT_TEMPLATE)


def get_truncate_length() -> int:
    """Get truncate length from environment or default."""
    try:
        return int(os.environ.get('TRUNCATE_LENGTH', DEFAULT_TRUNCATE))
    except ValueError:
        return DEFAULT_TRUNCATE


def generate_track_key(track: Optional[TrackInfo]) -> str:
    """
    Generate a unique key for a track to detect changes.

    This is used to determine if the track has changed from the last update.
    We normalize the title by removing parenthetical segments (feat., remix, etc).

    Args:
        track: TrackInfo or None

    Returns:
        Unique key string for the track
    """
    if not track:
        return "stopped"

    # Remove parenthetical segments: "(feat. Artist)", "(Remix)", etc.
    cleaned = re.sub(r"\s*\([^)]*\)", "", track.title or "")
    normalized = cleaned.strip().lower()
    return f"track:{normalized}"


def format_last_name(
    track: Optional[TrackInfo],
    fallback: str,
    template: Optional[str] = None,
    truncate: Optional[int] = None,
) -> str:
    """
    Format track info into a Telegram last name using a template.

    Template placeholders:
      {title}        - Track title (cleaned)
      {artist}       - All artists
      {artist_first} - First artist only
      {album}        - Album name

    Args:
        track: TrackInfo or None (if nothing playing)
        fallback: Last name to use if nothing playing
        template: Format template string (default from env)
        truncate: Max length for result (default from env, 0 = no truncation)

    Returns:
        Formatted last name string
    """
    if template is None:
        template = get_template()
    if truncate is None:
        truncate = get_truncate_length()

    if not track:
        result = fallback
    else:
        # Clean title by removing parenthetical segments
        cleaned_title = re.sub(r"\s*\([^)]*\)", "", track.title or "").strip()

        # Extract first artist (with special handling)
        artists_str = (track.artist or "").strip()
        if artists_str.lower().startswith("tyler, the creator"):
            first_artist = "Tyler, The Creator"
        else:
            first_artist = artists_str.split(",")[0].strip()

        try:
            result = template.format(
                title=cleaned_title,
                artist=track.artist or "",
                artist_first=first_artist,
                album=track.album or "",
            )
        except KeyError:
            # Invalid template placeholder, fall back to simple format
            result = f"| {first_artist} - {cleaned_title}"

    # Truncate with ellipsis if needed
    if truncate > 0 and len(result) > truncate:
        ellipsis = "..."
        result = result[: max(0, truncate - len(ellipsis))] + ellipsis

    return result
