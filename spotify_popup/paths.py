"""Pfade, Single-Instance-Handling und Prozess-Start-Helfer."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from . import APP_ICON_FILE, APP_NAME

IS_WINDOWS = sys.platform.startswith("win")
IS_FROZEN = getattr(sys, "frozen", False)

CREATE_NO_WINDOW = 0x08000000 if IS_WINDOWS else 0


def data_dir() -> Path:
    """Verzeichnis fuer Einstellungen / Secrets (%APPDATA%\\SpotifyPopup)."""
    if IS_WINDOWS:
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    else:  # nur fuer Entwicklung/Tests
        base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    path = Path(base) / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def settings_file() -> Path:
    return data_dir() / "settings.json"


def secrets_file() -> Path:
    return data_dir() / "secrets.dat"


def log_file() -> Path:
    return data_dir() / "app.log"


def app_dir() -> Path:
    """Ordner der exe bzw. des Projekts - Basis fuer relative Logo-Pfade."""
    if IS_FROZEN:
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def custom_icon_path() -> Path | None:
    """Vom Benutzer in __init__.py gesetztes Logo, falls vorhanden."""
    if not APP_ICON_FILE:
        return None
    candidate = Path(APP_ICON_FILE)
    if not candidate.is_absolute():
        candidate = app_dir() / candidate
    return candidate if candidate.exists() else None


def asset_path(name: str) -> Path | None:
    """Findet mitgelieferte Assets - sowohl im Quellcode als auch im PyInstaller-Bundle."""
    candidates = []
    if IS_FROZEN:
        candidates.append(Path(getattr(sys, "_MEIPASS", ".")) / "assets" / name)
    here = Path(__file__).resolve().parent
    candidates.append(here.parent / "assets" / name)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def launch_target() -> tuple[str, list[str]]:
    """(Programm, Basis-Argumente) um diese App erneut zu starten.

    Als kompilierte .exe ist das die exe selbst, im Quellcode-Betrieb pythonw -m spotify_popup.
    """
    if IS_FROZEN:
        return sys.executable, []
    python = sys.executable
    if IS_WINDOWS:
        pythonw = Path(python).with_name("pythonw.exe")
        if pythonw.exists():
            python = str(pythonw)
    return python, ["-m", "spotify_popup"]


DETACHED_PROCESS = 0x00000008


def spawn_self(extra_args: list[str] | None = None) -> None:
    """Startet eine weitere, vom aktuellen Prozess unabhaengige Instanz der App.

    Wird im Normalbetrieb nicht mehr gebraucht (Dienst und Einstellungen laufen im
    selben Prozess), bleibt aber fuer Sonderfaelle drin.
    """
    program, base_args = launch_target()
    args = [program, *base_args, *(extra_args or [])]
    kwargs: dict = {"close_fds": True}
    if IS_WINDOWS:
        # DETACHED_PROCESS und CREATE_NO_WINDOW schliessen sich gegenseitig aus -
        # zusammen scheitert CreateProcess mit ERROR_INVALID_PARAMETER.
        kwargs["creationflags"] = DETACHED_PROCESS
    # cwd NICHT auf das Interpreter-Verzeichnis setzen, sonst findet "-m spotify_popup"
    # das Paket nicht mehr.
    cwd = str(Path(__file__).resolve().parent.parent) if not IS_FROZEN else str(Path(program).parent)
    subprocess.Popen(args, cwd=cwd, **kwargs)


def ipc_name() -> str:
    """Name der lokalen Named Pipe fuer die Einzelinstanz-Kommunikation."""
    return f"{APP_NAME}_ipc_v1"


class SingleInstance:
    """Verhindert, dass der Hintergrund-Dienst mehrfach laeuft (Named Mutex)."""

    def __init__(self, name: str = f"Global\\{APP_NAME}_service"):
        self.name = name
        self._handle = None
        self.already_running = False

    def acquire(self) -> bool:
        if not IS_WINDOWS:
            return True
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        self._handle = kernel32.CreateMutexW(None, False, self.name)
        last_error = ctypes.get_last_error()
        self.already_running = last_error == 183  # ERROR_ALREADY_EXISTS
        return not self.already_running

    def release(self) -> None:
        if self._handle and IS_WINDOWS:
            import ctypes

            ctypes.WinDLL("kernel32").CloseHandle(self._handle)
            self._handle = None
