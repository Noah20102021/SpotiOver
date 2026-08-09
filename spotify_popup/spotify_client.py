"""Duenner Client fuer den einen Endpunkt, den wir brauchen: /me/player/currently-playing."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import requests

from .spotify_auth import AuthError, ReauthRequired, SpotifyAuth

API_BASE = "https://api.spotify.com/v1"
HTTP_TIMEOUT = 10


class TransientError(Exception):
    """Vorruebergehender Fehler (Netz, 5xx, Rate-Limit) - einfach beim naechsten Poll erneut."""


def _pick_cover(images: list[dict]) -> Optional[str]:
    """Kleinstes Bild, das fuer 64 px auch bei 150 % Windows-Skalierung noch scharf ist.

    Spotify liefert ueblicherweise 640/300/64. Das 64er wird auf skalierten Displays
    hochgerechnet und sieht matschig aus, deshalb mindestens 128 px.
    """
    if not images:
        return None
    usable = [img for img in images if (img.get("width") or 0) >= 128]
    if usable:
        return min(usable, key=lambda img: img.get("width") or 0)["url"]
    return images[0]["url"]


@dataclass
class Track:
    id: str
    title: str
    artists: str
    cover_url: Optional[str]
    duration_ms: int
    progress_ms: int
    is_playing: bool


class SpotifyClient:
    def __init__(self, auth: SpotifyAuth):
        self.auth = auth
        self._session = requests.Session()
        self._blocked_until = 0.0

    def currently_playing(self) -> Optional[Track]:
        if time.time() < self._blocked_until:
            raise TransientError("Rate-Limit aktiv, warte noch etwas.")

        payload = self._get("/me/player/currently-playing")
        if not payload:
            return None
        item = payload.get("item")
        if not item or item.get("type") != "track":
            return None  # Podcast-Episoden o.ae. ignorieren wir

        images = (item.get("album") or {}).get("images") or []
        return Track(
            id=item.get("id") or item.get("uri", ""),
            title=item.get("name", ""),
            artists=", ".join(a["name"] for a in item.get("artists", []) if a.get("name")),
            cover_url=_pick_cover(images),
            duration_ms=int(item.get("duration_ms") or 1),
            progress_ms=int(payload.get("progress_ms") or 0),
            is_playing=bool(payload.get("is_playing")),
        )

    # ------------------------------------------------------------------
    def _get(self, path: str, retry_on_401: bool = True) -> Optional[dict]:
        try:
            token = self.auth.get_access_token()
        except ReauthRequired:
            raise
        except AuthError as exc:
            raise TransientError(str(exc)) from exc

        try:
            response = self._session.get(
                f"{API_BASE}{path}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=HTTP_TIMEOUT,
            )
        except requests.RequestException as exc:
            raise TransientError(f"Netzwerkfehler: {exc}") from exc

        if response.status_code == 204:
            return None  # nichts laeuft gerade
        if response.status_code == 200:
            try:
                return response.json()
            except ValueError:
                return None
        if response.status_code == 401 and retry_on_401:
            self.auth.get_access_token(force_refresh=True)  # kann ReauthRequired werfen
            return self._get(path, retry_on_401=False)
        if response.status_code == 429:
            wait = int(response.headers.get("Retry-After", "5"))
            self._blocked_until = time.time() + wait + 1
            raise TransientError(f"Rate-Limit von Spotify, Pause {wait} s.")
        if response.status_code == 403:
            raise ReauthRequired(
                "Spotify verweigert den Zugriff (403). Moeglicherweise fehlt der Scope "
                "'user-read-currently-playing' - bitte neu anmelden."
            )
        raise TransientError(f"Unerwartete Antwort von Spotify: HTTP {response.status_code}")
