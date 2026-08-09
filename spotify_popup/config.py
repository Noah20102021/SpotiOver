"""Einstellungen (nicht geheim) als JSON in %APPDATA%\\SpotifyPopup\\settings.json."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, fields
from typing import Any

from .paths import settings_file

ANIMATION_MODES: tuple[str, ...] = ("classic", "smooth", "bounce", "pop", "slide_pop")

DEFAULT_HOTKEY = "<ctrl>+<226>"  # Strg + '<' (OEM_102) auf deutscher Tastatur


@dataclass
class Settings:
    # --- Allgemein ---
    language: str = ""  # "" = noch nicht gewaehlt -> Abfrage beim ersten Start

    # --- Verbindung ---
    redirect_port: int = 8888
    poll_interval_ms: int = 1000

    # --- Anzeige ---
    display_duration_ms: int = 6000
    margin_x: int = 20
    margin_y: int = 20
    hotkey: str = DEFAULT_HOTKEY
    show_tray_icon: bool = True

    # --- Experimentell ---
    experimental_progress_bar: bool = False
    experimental_animations: bool = False
    animation_mode: str = "classic"
    animation_duration_ms: int = 300

    # --- System ---
    autostart: bool = True  # standardmaessig an, abschaltbar im Tab "System"
    start_menu_entry: bool = False
    app_list_entry: bool = False
    notify_on_reauth: bool = True

    # --- interner Zustand ---
    auth_version: int = 0  # wird nach Login/Logout erhoeht -> Dienst laedt Token neu
    first_run_done: bool = False

    @classmethod
    def load(cls) -> "Settings":
        path = settings_file()
        if not path.exists():
            return cls()
        try:
            raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return cls()
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in raw.items() if k in known})

    def save(self) -> None:
        path = settings_file()
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        os.replace(tmp, path)

    # Bequemlichkeit ---------------------------------------------------
    @property
    def redirect_uri(self) -> str:
        # Wichtig: Spotify akzeptiert fuer http nur noch die Loopback-IP,
        # "http://localhost:8888/callback" wird abgelehnt.
        return f"http://127.0.0.1:{self.redirect_port}/callback"

    @property
    def effective_animation_mode(self) -> str:
        if not self.experimental_animations:
            return "classic"
        return self.animation_mode if self.animation_mode in ANIMATION_MODES else "classic"

    def apply_language(self) -> None:
        """Setzt die globale UI-Sprache passend zu dieser Einstellung."""
        from .i18n import DEFAULT_LANGUAGE, set_language

        set_language(self.language or DEFAULT_LANGUAGE)

    def bump_auth_version(self) -> None:
        self.auth_version += 1
        self.save()
