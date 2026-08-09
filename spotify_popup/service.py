"""Hintergrund-Dienst: pollt Spotify, zeigt das Popup, haengt im Tray."""

from __future__ import annotations

import logging
from typing import Optional

from PyQt6.QtCore import QFileSystemWatcher, QObject, QTimer, pyqtSignal
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from . import APP_DISPLAY_NAME
from .config import Settings
from .hotkey import HotkeyListener
from .i18n import tr
from .icons import app_icon
from .paths import settings_file
from .popup import PopupWindow
from .spotify_auth import NoCredentials, ReauthRequired, SpotifyAuth
from .spotify_client import SpotifyClient, Track, TransientError

log = logging.getLogger(__name__)


class PopupService(QObject):
    """Laeuft im selben Prozess wie das Einstellungsfenster und bleibt bestehen,
    wenn dieses geschlossen wird."""

    settings_requested = pyqtSignal()

    def __init__(self, app: QApplication, settings: Settings):
        super().__init__()
        self.app = app
        self.settings = settings
        self.auth = SpotifyAuth(settings)
        self.client = SpotifyClient(self.auth)

        self.popup = PopupWindow(settings)
        self.last_track_id: Optional[str] = None
        self._needs_attention = False
        self._error_streak = 0

        self.hotkey = HotkeyListener(self)
        self.hotkey.triggered.connect(self.show_current_track)
        self.hotkey.failed.connect(lambda msg: log.warning(msg))
        self.hotkey.start(settings.hotkey)

        self.tray = QSystemTrayIcon(app_icon(), self)
        self._build_tray_menu()
        self.tray.activated.connect(self._on_tray_activated)
        if settings.show_tray_icon:
            self.tray.show()
        self._settings_opened_once = False

        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(self._poll)
        self.poll_timer.start(max(500, settings.poll_interval_ms))

        # Einstellungen live nachladen, wenn das Einstellungsfenster etwas aendert
        self._watcher = QFileSystemWatcher([str(settings_file().parent)], self)
        if settings_file().exists():
            self._watcher.addPath(str(settings_file()))
        self._watcher.fileChanged.connect(self._on_settings_changed)
        self._watcher.directoryChanged.connect(self._on_settings_changed)

        self._check_ready(initial=True)

    # ------------------------------------------------------------------
    # Tray
    # ------------------------------------------------------------------
    def _build_tray_menu(self) -> None:
        menu = QMenu()
        menu.addAction(tr("tray.show_now"), self.show_current_track)
        menu.addAction(tr("tray.settings"), self.open_settings)
        menu.addSeparator()
        menu.addAction(tr("tray.quit"), self.quit)
        self._menu = menu  # Referenz halten, sonst raeumt Qt das Menue ab
        self.tray.setContextMenu(menu)
        self.tray.setToolTip(APP_DISPLAY_NAME)

    def _on_tray_activated(self, reason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            if self._needs_attention:
                self.open_settings()
            else:
                self.show_current_track()

    def open_settings(self) -> None:
        """Loest das Oeffnen des Einstellungsfensters im selben Prozess aus."""
        self.settings_requested.emit()

    def pause_hotkey(self) -> None:
        """Waehrend der Hotkey-Aufnahme, damit die alte Kombination nicht dazwischenfunkt."""
        self.hotkey.stop()

    def resume_hotkey(self) -> None:
        self.hotkey.start(self.settings.hotkey)

    def apply_settings(self) -> None:
        """Wird nach dem Speichern im Einstellungsfenster direkt aufgerufen."""
        self.settings.apply_language()
        self._build_tray_menu()
        if self.hotkey.current != self.settings.hotkey:
            self.hotkey.start(self.settings.hotkey)
        self.poll_timer.setInterval(max(500, self.settings.poll_interval_ms))
        self.popup.settings = self.settings
        if self.settings.show_tray_icon:
            self.tray.show()
        else:
            self.tray.hide()
        self.auth.load_token(force=True)
        self._check_ready()

    def quit(self) -> None:
        self.hotkey.stop()
        self.tray.hide()
        self.app.quit()

    def _notify(self, title: str, message: str) -> None:
        if self.settings.show_tray_icon and self.tray.isVisible():
            self.tray.showMessage(title, message, app_icon(), 8000)

    def _set_attention(self, on: bool, tooltip: str = "") -> None:
        self._needs_attention = on
        self.tray.setIcon(app_icon(muted=on))
        self.tray.setToolTip(tooltip or APP_DISPLAY_NAME)

    # ------------------------------------------------------------------
    # Zustand
    # ------------------------------------------------------------------
    def _check_ready(self, initial: bool = False) -> bool:
        if not self.auth.has_credentials():
            self._set_attention(True, tr("tooltip.creds_missing", app=APP_DISPLAY_NAME))
            if initial and not self._settings_opened_once:
                self._settings_opened_once = True
                self._notify(APP_DISPLAY_NAME, tr("notify.no_creds"))
                self.open_settings()
            return False
        if not self.auth.is_logged_in():
            self._set_attention(True, tr("tooltip.login_required", app=APP_DISPLAY_NAME))
            if initial and not self._settings_opened_once:
                self._settings_opened_once = True
                self._notify(APP_DISPLAY_NAME, tr("notify.need_login"))
                self.open_settings()
            return False
        self._set_attention(False)
        return True

    def _handle_reauth(self, message: str) -> None:
        """Refresh-Token abgelaufen (Spotify-Policy: 6 Monate) oder widerrufen."""
        log.warning("Reauth noetig: %s", message)
        self.last_track_id = None
        self._set_attention(True, tr("tooltip.expired", app=APP_DISPLAY_NAME))
        if self.settings.notify_on_reauth:
            self._notify(
                tr("notify.reauth_title", app=APP_DISPLAY_NAME),
                tr("notify.reauth_body"),
            )
            self.open_settings()
        # Polling drosseln, bis der Benutzer sich neu angemeldet hat
        self.poll_timer.setInterval(15000)

    # ------------------------------------------------------------------
    # Poll-Schleife
    # ------------------------------------------------------------------
    def _poll(self) -> None:
        if not self.auth.has_credentials() or not self.auth.is_logged_in():
            self._check_ready()
            return

        try:
            track = self.client.currently_playing()
        except ReauthRequired as exc:
            self._handle_reauth(str(exc))
            return
        except NoCredentials:
            self._check_ready()
            return
        except TransientError as exc:
            self._error_streak += 1
            if self._error_streak in (1, 10, 60):
                log.info("Vorruebergehender Fehler: %s", exc)
            return

        self._error_streak = 0
        if self.poll_timer.interval() != max(500, self.settings.poll_interval_ms):
            self.poll_timer.setInterval(max(500, self.settings.poll_interval_ms))
        self._set_attention(False)

        if track is None:
            return
        self._on_track(track)

    def _on_track(self, track: Track) -> None:
        if track.id != self.last_track_id:
            self.last_track_id = track.id
            self.popup.set_track(track)
            if self.popup.isVisible():
                self.popup.refresh_visible()
            else:
                self.popup.show_popup()
        else:
            self.popup.update_playback(track)

    def show_current_track(self) -> None:
        """Vom Hotkey/Tray: aktuellen Song sofort anzeigen (auch wenn er sich nicht geaendert hat)."""
        try:
            track = self.client.currently_playing()
        except ReauthRequired as exc:
            self._handle_reauth(str(exc))
            return
        except (TransientError, NoCredentials) as exc:
            log.info("Anzeige nicht moeglich: %s", exc)
            return
        if track is None:
            return
        self.last_track_id = track.id
        self.popup.set_track(track)
        if self.popup.isVisible():
            self.popup.refresh_visible()
        else:
            self.popup.show_popup()

    # ------------------------------------------------------------------
    # Einstellungen neu laden
    # ------------------------------------------------------------------
    def _on_settings_changed(self, _path: str) -> None:
        QTimer.singleShot(300, self._reload_settings)

    def _reload_settings(self) -> None:
        path = str(settings_file())
        if settings_file().exists() and path not in self._watcher.files():
            self._watcher.addPath(path)  # nach atomarem Replace neu registrieren

        old_hotkey = self.settings.hotkey
        old_auth_version = self.settings.auth_version
        old_language = self.settings.language
        new = Settings.load()
        self.settings.__dict__.update(new.__dict__)
        self.popup.settings = self.settings

        if self.settings.language != old_language:
            self.settings.apply_language()
            self._build_tray_menu()

        if self.settings.hotkey != old_hotkey:
            self.hotkey.start(self.settings.hotkey)
        if self.settings.auth_version != old_auth_version:
            self.auth.load_token(force=True)
            self.last_track_id = None
            self._check_ready()
        self.poll_timer.setInterval(max(500, self.settings.poll_interval_ms))
        if self.settings.show_tray_icon:
            self.tray.show()
        else:
            self.tray.hide()
        log.info("Einstellungen neu geladen.")
