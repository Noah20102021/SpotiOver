"""Einstiegspunkt.

  <exe>              -> Dienst startet im Hintergrund UND das Einstellungsfenster geht auf
  <exe> --service    -> nur der Dienst, kein Fenster (so steht es im Autostart)
  <exe> --uninstall  -> Autostart/Startmenue/App-Eintrag wieder entfernen

Wichtig: Dienst und Einstellungsfenster laufen im **selben** Prozess. Das Fenster zu
schliessen beendet den Dienst also nicht - er lebt im Tray weiter. Beendet wird nur ueber
Tray -> Beenden.

Startet man die exe ein zweites Mal (Doppelklick, Startmenue, Windows-Suche), meldet sich
die neue Instanz ueber eine lokale Named Pipe bei der laufenden, laesst dort das
Einstellungsfenster aufgehen und beendet sich sofort wieder.
"""

from __future__ import annotations

import argparse
import logging
import logging.handlers
import sys
from typing import Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from . import APP_DISPLAY_NAME, APP_NAME
from . import windows_integration as win
from .config import Settings
from .i18n import system_language, tr
from .icons import app_icon
from .paths import IS_WINDOWS, ipc_name, log_file

CMD_SHOW_SETTINGS = b"show-settings"
CMD_PING = b"ping"

log = logging.getLogger(__name__)


def _setup_logging() -> None:
    handler = logging.handlers.RotatingFileHandler(
        log_file(), maxBytes=512_000, backupCount=2, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)


# --------------------------------------------------------------------------
# Einzelinstanz ueber lokale Named Pipe
# --------------------------------------------------------------------------
def _notify_running_instance(command: bytes) -> bool:
    """True, wenn schon eine Instanz laeuft und den Befehl entgegengenommen hat."""
    socket = QLocalSocket()
    socket.connectToServer(ipc_name())
    if not socket.waitForConnected(400):
        return False
    socket.write(command)
    socket.flush()
    socket.waitForBytesWritten(400)
    socket.disconnectFromServer()
    return True


class _InstanceServer:
    """Nimmt Befehle weiterer Programmstarts entgegen."""

    def __init__(self, on_show_settings) -> None:
        self.on_show_settings = on_show_settings
        self.server = QLocalServer()
        QLocalServer.removeServer(ipc_name())  # evtl. Leiche eines Absturzes
        if not self.server.listen(ipc_name()):
            log.warning("Named Pipe konnte nicht geoeffnet werden: %s", self.server.errorString())
        self.server.newConnection.connect(self._on_connection)

    def _on_connection(self) -> None:
        socket = self.server.nextPendingConnection()
        if socket is None:
            return

        def read() -> None:
            data = bytes(socket.readAll())
            if data.startswith(CMD_SHOW_SETTINGS):
                self.on_show_settings()
            socket.disconnectFromServer()

        socket.readyRead.connect(read)
        socket.disconnected.connect(socket.deleteLater)


# --------------------------------------------------------------------------
# Einstellungsfenster
# --------------------------------------------------------------------------
class _SettingsHost:
    """Haelt das Einstellungsfenster; baut es beim Sprachwechsel uebersetzt neu auf."""

    def __init__(self, settings: Settings, service=None):
        self.settings = settings
        self.service = service
        self.window = None

    def show(self, start_tab: int = 0) -> None:
        from .settings_window import SettingsWindow

        if self.window is not None:
            self.window.reload()
        else:
            self.window = SettingsWindow(self.settings, service=self.service, start_tab=start_tab)
            self.window.language_changed.connect(self._rebuild)
            if self.service is not None:
                self.window.settings_saved.connect(self.service.apply_settings)
                # Sprachwechsel sofort auch im Tray-Menue uebernehmen
                self.window.language_changed.connect(self.service.apply_settings)
        self.window.show()
        self.window.setWindowState(self.window.windowState() & ~Qt.WindowState.WindowMinimized)
        self.window.raise_()
        self.window.activateWindow()

    def _rebuild(self) -> None:
        previous = self.window
        tab = previous.current_tab() if previous else 0
        self.window = None

        def rebuild() -> None:
            self.show(tab)
            if previous is not None:
                if self.window is not None:
                    self.window.move(previous.pos())
                previous.close()
                previous.deleteLater()

        QTimer.singleShot(0, rebuild)


def _ask_language(settings: Settings) -> None:
    """Sprachabfrage beim allerersten Start."""
    from .settings_window import LanguageDialog

    suggested = system_language()
    settings.language = suggested
    settings.apply_language()

    dialog = LanguageDialog(suggested)
    dialog.exec()
    settings.language = dialog.choice
    settings.apply_language()
    settings.save()


def _first_run_setup(settings: Settings) -> bool:
    """Beim allerersten Start alles Noetige selbst einrichten."""
    if settings.first_run_done:
        return False
    # Defaults aus config.Settings (autostart ist dort standardmaessig True)
    settings.start_menu_entry = True
    settings.app_list_entry = True
    settings.first_run_done = True
    settings.save()
    try:
        win.apply_integration(
            settings.autostart, settings.start_menu_entry, settings.app_list_entry
        )
    except Exception:
        log.exception("Windows-Integration fehlgeschlagen")
    return True


# --------------------------------------------------------------------------
# Hauptmodi
# --------------------------------------------------------------------------
def run_app(settings: Settings, show_window: bool) -> int:
    from .service import PopupService

    if _notify_running_instance(CMD_SHOW_SETTINGS if show_window else CMD_PING):
        log.info("Es laeuft bereits eine Instanz - Befehl weitergereicht.")
        return 0

    app = QApplication(sys.argv)
    app.setApplicationName(APP_DISPLAY_NAME)
    app.setWindowIcon(app_icon())
    # Der Dienst muss weiterlaufen, wenn das Einstellungsfenster geschlossen wird.
    app.setQuitOnLastWindowClosed(False)

    if not settings.language:
        _ask_language(settings)
    first_run = _first_run_setup(settings) if IS_WINDOWS else False

    if not QSystemTrayIcon.isSystemTrayAvailable():
        log.warning("Kein System-Tray verfuegbar.")

    service = PopupService(app, settings)
    host = _SettingsHost(settings, service)
    service.settings_requested.connect(host.show)

    server = _InstanceServer(host.show)  # noqa: F841 - haelt die Pipe offen

    if show_window:
        host.show()
        if first_run:
            QMessageBox.information(host.window, APP_DISPLAY_NAME, tr("welcome.body"))

    return app.exec()


def run_uninstall(settings: Settings, silent: bool) -> int:
    from .paths import data_dir
    from .secrets_store import wipe_all

    app: Optional[QApplication] = None
    delete_data = silent
    if not silent:
        app = QApplication(sys.argv)
        answer = QMessageBox.question(
            None,
            APP_DISPLAY_NAME,
            tr("uninstall.question"),
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No
            | QMessageBox.StandardButton.Cancel,
        )
        if answer == QMessageBox.StandardButton.Cancel:
            return 0
        delete_data = answer == QMessageBox.StandardButton.Yes

    win.remove_all_integration()
    if delete_data:
        wipe_all()
        for name in ("settings.json", "app.log"):
            try:
                (data_dir() / name).unlink(missing_ok=True)
            except OSError:
                pass

    if not silent and app is not None:
        QMessageBox.information(None, APP_DISPLAY_NAME, tr("uninstall.done"))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog=APP_NAME, add_help=True)
    parser.add_argument(
        "--service", action="store_true", help="nur den Hintergrund-Dienst starten, ohne Fenster"
    )
    parser.add_argument("--uninstall", action="store_true", help="Windows-Integration entfernen")
    parser.add_argument("--silent", action="store_true", help="ohne Rueckfragen")
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    _setup_logging()
    settings = Settings.load()
    settings.apply_language()

    if args.uninstall:
        return run_uninstall(settings, args.silent)
    return run_app(settings, show_window=not args.service)


if __name__ == "__main__":
    sys.exit(main())
