"""Einstellungsfenster - das ist das, was beim manuellen Start der .exe aufgeht."""

from __future__ import annotations

import copy
import datetime as dt
from typing import Optional

from PyQt6.QtCore import QThread, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from . import APP_DISPLAY_NAME, APP_VERSION
from . import windows_integration as win
from .config import ANIMATION_MODES, DEFAULT_HOTKEY, Settings
from .hotkey import HotkeyListener, HotkeyRecorder
from .i18n import LANGUAGES, tr
from .icons import app_icon
from .paths import data_dir
from .popup import PopupWindow
from .secrets_store import backend_name, wipe_all
from .spotify_auth import SpotifyAuth
from .spotify_client import Track


class _LoginWorker(QThread):
    finished_ok = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self, auth: SpotifyAuth):
        super().__init__()
        self.auth = auth
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        try:
            self.auth.interactive_login(cancelled=lambda: self._cancel)
            self.finished_ok.emit()
        except Exception as exc:
            self.failed.emit(str(exc))


class _LoginDialog(QDialog):
    def __init__(self, auth: SpotifyAuth, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle(tr("dlg.login_title"))
        self.setModal(True)
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(tr("dlg.login_text")))
        bar = QProgressBar()
        bar.setRange(0, 0)
        layout.addWidget(bar)

        cancel = QPushButton(tr("btn.cancel"))
        cancel.clicked.connect(self.reject)
        layout.addWidget(cancel, alignment=Qt.AlignmentFlag.AlignRight)

        self.worker = _LoginWorker(auth)
        self.worker.finished_ok.connect(self.accept)
        self.worker.failed.connect(self._on_failed)
        self.error: str = ""
        self.worker.start()

    def _on_failed(self, message: str) -> None:
        self.error = message
        self.reject()

    def reject(self) -> None:  # noqa: D102
        self.worker.cancel()
        super().reject()


class HotkeyRecordDialog(QDialog):
    """Nimmt die naechste gedrueckte Tastenkombination auf."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle(tr("dlg.record_title"))
        self.setModal(True)
        self.setMinimumWidth(380)
        self.result_hotkey: str = ""

        layout = QVBoxLayout(self)
        label = QLabel(tr("dlg.record_text"))
        label.setWordWrap(True)
        layout.addWidget(label)

        self.preview = QLabel("...")
        font = self.preview.font()
        font.setPointSize(font.pointSize() + 3)
        font.setBold(True)
        self.preview.setFont(font)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(44)
        layout.addWidget(self.preview)

        cancel = QPushButton(tr("btn.cancel"))
        cancel.clicked.connect(self.reject)
        layout.addWidget(cancel, alignment=Qt.AlignmentFlag.AlignRight)

        self.recorder = HotkeyRecorder(self)
        self.recorder.recorded.connect(self._on_recorded)
        self.recorder.cancelled.connect(self.reject)
        self.recorder.failed.connect(lambda msg: self.reject())
        self.recorder.start()

    def _on_recorded(self, hotkey: str) -> None:
        self.result_hotkey = hotkey
        self.preview.setText(hotkey)
        QTimer.singleShot(250, self.accept)  # kurz anzeigen, was erkannt wurde

    def done(self, result: int) -> None:  # noqa: D102
        self.recorder.stop()
        super().done(result)


class LanguageDialog(QDialog):
    """Sprachabfrage beim allerersten Start."""

    def __init__(self, suggested: str = "de", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.choice = suggested
        self.setWindowTitle(tr("lang.dialog_title"))
        self.setWindowIcon(app_icon())
        self.setModal(True)

        layout = QVBoxLayout(self)
        label = QLabel(tr("lang.dialog_text"))
        label.setWordWrap(True)
        layout.addWidget(label)

        buttons = QHBoxLayout()
        for code, name in LANGUAGES.items():
            button = QPushButton(name)
            button.setMinimumWidth(120)
            button.setDefault(code == suggested)
            button.clicked.connect(lambda _checked=False, c=code: self._pick(c))
            buttons.addWidget(button)
        layout.addLayout(buttons)

    def _pick(self, code: str) -> None:
        self.choice = code
        self.accept()


class SettingsWindow(QWidget):
    language_changed = pyqtSignal()
    settings_saved = pyqtSignal()

    def __init__(self, settings: Settings, service=None, start_tab: int = 0):
        super().__init__()
        self.settings = settings
        self.service = service
        self.auth = SpotifyAuth(settings)
        self._preview: Optional[PopupWindow] = None

        self.setWindowTitle(tr("app.settings_title", app=APP_DISPLAY_NAME))
        self.setWindowIcon(app_icon())
        self.setMinimumWidth(540)

        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_spotify_tab(), tr("tab.spotify"))
        self.tabs.addTab(self._build_display_tab(), tr("tab.display"))
        self.tabs.addTab(self._build_experimental_tab(), tr("tab.experimental"))
        self.tabs.addTab(self._build_system_tab(), tr("tab.system"))
        self.tabs.setCurrentIndex(min(start_tab, self.tabs.count() - 1))

        save_button = QPushButton(tr("btn.save"))
        save_button.setDefault(True)
        save_button.clicked.connect(self.save)
        close_button = QPushButton(tr("btn.close"))
        close_button.clicked.connect(self.close)

        buttons = QHBoxLayout()
        buttons.addWidget(QLabel(f"v{APP_VERSION}"))
        buttons.addStretch(1)
        buttons.addWidget(save_button)
        buttons.addWidget(close_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)
        layout.addLayout(buttons)

        self._load_into_widgets()
        self._refresh_status()

    def current_tab(self) -> int:
        return self.tabs.currentIndex()

    def reload(self) -> None:
        """Beim erneuten Oeffnen: Werte frisch aus Einstellungen/Registry ziehen."""
        self._load_into_widgets()
        self._refresh_status()

    # ------------------------------------------------------------------
    # Tabs
    # ------------------------------------------------------------------
    def _build_spotify_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        creds_box = QGroupBox(tr("group.credentials"))
        form = QFormLayout(creds_box)
        self.client_id_edit = QLineEdit()
        self.client_id_edit.setPlaceholderText(tr("ph.client_id"))
        self.client_secret_edit = QLineEdit()
        self.client_secret_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.client_secret_edit.setPlaceholderText(tr("ph.client_secret"))
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1024, 65535)

        self.redirect_label = QLabel()
        self.redirect_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        copy_button = QPushButton(tr("btn.copy"))
        copy_button.clicked.connect(
            lambda: QGuiApplication.clipboard().setText(self._redirect_uri())
        )
        redirect_row = QHBoxLayout()
        redirect_row.addWidget(self.redirect_label, 1)
        redirect_row.addWidget(copy_button)
        redirect_widget = QWidget()
        redirect_widget.setLayout(redirect_row)

        form.addRow(tr("label.client_id"), self.client_id_edit)
        form.addRow(tr("label.client_secret"), self.client_secret_edit)
        form.addRow(tr("label.port"), self.port_spin)
        form.addRow(tr("label.redirect_uri"), redirect_widget)
        self.port_spin.valueChanged.connect(lambda _: self._update_redirect_label())

        hint = QLabel(tr("hint.redirect", backend=backend_name()))
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #666;")

        cred_buttons = QHBoxLayout()
        save_creds = QPushButton(tr("btn.save_creds"))
        save_creds.clicked.connect(self._save_credentials)
        delete_creds = QPushButton(tr("btn.delete_creds"))
        delete_creds.clicked.connect(self._delete_credentials)
        cred_buttons.addWidget(save_creds)
        cred_buttons.addWidget(delete_creds)
        cred_buttons.addStretch(1)

        status_box = QGroupBox(tr("group.login"))
        status_layout = QVBoxLayout(status_box)
        self.status_label = QLabel()
        self.status_label.setWordWrap(True)
        status_layout.addWidget(self.status_label)

        login_row = QHBoxLayout()
        self.login_button = QPushButton(tr("btn.login"))
        self.login_button.clicked.connect(self._do_login)
        self.logout_button = QPushButton(tr("btn.logout"))
        self.logout_button.clicked.connect(self._do_logout)
        login_row.addWidget(self.login_button)
        login_row.addWidget(self.logout_button)
        login_row.addStretch(1)
        status_layout.addLayout(login_row)

        layout.addWidget(creds_box)
        layout.addWidget(hint)
        layout.addLayout(cred_buttons)
        layout.addWidget(status_box)
        layout.addStretch(1)
        return page

    def _build_display_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)

        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(1000, 30000)
        self.duration_spin.setSingleStep(500)
        self.duration_spin.setSuffix(" ms")

        self.poll_spin = QSpinBox()
        self.poll_spin.setRange(500, 10000)
        self.poll_spin.setSingleStep(250)
        self.poll_spin.setSuffix(" ms")

        self.margin_x_spin = QSpinBox()
        self.margin_x_spin.setRange(0, 2000)
        self.margin_y_spin = QSpinBox()
        self.margin_y_spin.setRange(0, 2000)

        self.hotkey_edit = QLineEdit()
        self.hotkey_edit.setPlaceholderText(DEFAULT_HOTKEY)
        hotkey_record = QPushButton(tr("btn.record"))
        hotkey_record.clicked.connect(self._record_hotkey)
        hotkey_test = QPushButton(tr("btn.check"))
        hotkey_test.clicked.connect(self._check_hotkey)
        hotkey_row = QHBoxLayout()
        hotkey_row.addWidget(self.hotkey_edit, 1)
        hotkey_row.addWidget(hotkey_record)
        hotkey_row.addWidget(hotkey_test)
        hotkey_widget = QWidget()
        hotkey_widget.setLayout(hotkey_row)

        self.tray_check = QCheckBox(tr("chk.tray"))

        form.addRow(tr("label.duration"), self.duration_spin)
        form.addRow(tr("label.poll"), self.poll_spin)
        form.addRow(tr("label.margin_x"), self.margin_x_spin)
        form.addRow(tr("label.margin_y"), self.margin_y_spin)
        form.addRow(tr("label.hotkey"), hotkey_widget)
        form.addRow("", self.tray_check)

        note = QLabel(tr("note.hotkey"))
        note.setStyleSheet("color: #666;")
        form.addRow("", note)
        return page

    def _build_experimental_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        warning = QLabel(tr("note.experimental"))
        warning.setWordWrap(True)
        layout.addWidget(warning)

        progress_box = QGroupBox(tr("group.progress"))
        progress_layout = QVBoxLayout(progress_box)
        self.progress_check = QCheckBox(tr("chk.progress"))
        progress_layout.addWidget(self.progress_check)
        progress_note = QLabel(tr("note.progress"))
        progress_note.setWordWrap(True)
        progress_note.setStyleSheet("color: #666;")
        progress_layout.addWidget(progress_note)

        anim_box = QGroupBox(tr("group.anim"))
        anim_layout = QFormLayout(anim_box)
        self.anim_check = QCheckBox(tr("chk.anim"))
        self.anim_combo = QComboBox()
        for key in ANIMATION_MODES:
            self.anim_combo.addItem(tr(f"anim.{key}"), key)
        self.anim_duration_spin = QSpinBox()
        self.anim_duration_spin.setRange(100, 1200)
        self.anim_duration_spin.setSingleStep(50)
        self.anim_duration_spin.setSuffix(" ms")
        self.anim_check.toggled.connect(self.anim_combo.setEnabled)
        self.anim_check.toggled.connect(self.anim_duration_spin.setEnabled)

        anim_layout.addRow(self.anim_check)
        anim_layout.addRow(tr("label.anim_mode"), self.anim_combo)
        anim_layout.addRow(tr("label.anim_duration"), self.anim_duration_spin)

        preview_button = QPushButton(tr("btn.preview"))
        preview_button.clicked.connect(self._show_preview)

        layout.addWidget(progress_box)
        layout.addWidget(anim_box)
        layout.addWidget(preview_button)
        layout.addStretch(1)
        return page

    def _build_system_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        language_box = QGroupBox(tr("label.language").rstrip(":"))
        language_layout = QFormLayout(language_box)
        self.language_combo = QComboBox()
        for code, name in LANGUAGES.items():
            self.language_combo.addItem(name, code)
        self.language_combo.currentIndexChanged.connect(self._on_language_selected)
        language_layout.addRow(tr("label.language"), self.language_combo)

        integration_box = QGroupBox(tr("group.integration"))
        integration_layout = QVBoxLayout(integration_box)
        self.autostart_check = QCheckBox(tr("chk.autostart"))
        self.startmenu_check = QCheckBox(tr("chk.startmenu"))
        self.applist_check = QCheckBox(tr("chk.applist"))
        self.reauth_check = QCheckBox(tr("chk.reauth"))
        for widget in (
            self.autostart_check,
            self.startmenu_check,
            self.applist_check,
            self.reauth_check,
        ):
            integration_layout.addWidget(widget)

        hint = win.integration_hint()
        if hint:
            hint_label = QLabel(hint)
            hint_label.setWordWrap(True)
            hint_label.setStyleSheet("color: #a06000;")
            integration_layout.addWidget(hint_label)

        service_box = QGroupBox(tr("group.service"))
        service_layout = QVBoxLayout(service_box)
        status = QLabel(tr("note.service_running") if self.service else tr("note.service_missing"))
        status.setWordWrap(True)
        service_layout.addWidget(status)
        test_button = QPushButton(tr("btn.test_popup"))
        test_button.clicked.connect(self._test_popup)
        test_button.setEnabled(self.service is not None)
        service_layout.addWidget(test_button)
        service_layout.addWidget(QLabel(tr("note.service_quit")))

        danger_box = QGroupBox(tr("group.reset"))
        danger_layout = QVBoxLayout(danger_box)
        wipe_button = QPushButton(tr("btn.wipe"))
        wipe_button.clicked.connect(self._wipe_everything)
        danger_layout.addWidget(wipe_button)
        danger_layout.addWidget(QLabel(tr("label.datadir", path=str(data_dir()))))

        layout.addWidget(language_box)
        layout.addWidget(integration_box)
        layout.addWidget(service_box)
        layout.addWidget(danger_box)
        layout.addStretch(1)
        return page

    # ------------------------------------------------------------------
    # Laden / Speichern
    # ------------------------------------------------------------------
    def _load_into_widgets(self) -> None:
        settings = self.settings
        self._loading = True

        self.client_id_edit.setText(self.auth.client_id)
        self.client_secret_edit.setText(self.auth.client_secret)
        self.port_spin.setValue(settings.redirect_port)
        self._update_redirect_label()

        self.duration_spin.setValue(settings.display_duration_ms)
        self.poll_spin.setValue(settings.poll_interval_ms)
        self.margin_x_spin.setValue(settings.margin_x)
        self.margin_y_spin.setValue(settings.margin_y)
        self.hotkey_edit.setText(settings.hotkey)
        self.tray_check.setChecked(settings.show_tray_icon)

        self.progress_check.setChecked(settings.experimental_progress_bar)
        self.anim_check.setChecked(settings.experimental_animations)
        index = self.anim_combo.findData(settings.animation_mode)
        self.anim_combo.setCurrentIndex(max(0, index))
        self.anim_duration_spin.setValue(settings.animation_duration_ms)
        self.anim_combo.setEnabled(settings.experimental_animations)
        self.anim_duration_spin.setEnabled(settings.experimental_animations)

        language_index = self.language_combo.findData(settings.language or "de")
        self.language_combo.setCurrentIndex(max(0, language_index))

        self.autostart_check.setChecked(win.is_autostart_enabled() or settings.autostart)
        self.startmenu_check.setChecked(win.has_start_menu_shortcut() or settings.start_menu_entry)
        self.applist_check.setChecked(win.has_app_entry() or settings.app_list_entry)
        self.reauth_check.setChecked(settings.notify_on_reauth)

        self._loading = False

    def _collect(self) -> None:
        settings = self.settings
        settings.redirect_port = self.port_spin.value()
        settings.display_duration_ms = self.duration_spin.value()
        settings.poll_interval_ms = self.poll_spin.value()
        settings.margin_x = self.margin_x_spin.value()
        settings.margin_y = self.margin_y_spin.value()
        settings.hotkey = self.hotkey_edit.text().strip() or DEFAULT_HOTKEY
        settings.show_tray_icon = self.tray_check.isChecked()
        settings.experimental_progress_bar = self.progress_check.isChecked()
        settings.experimental_animations = self.anim_check.isChecked()
        settings.animation_mode = self.anim_combo.currentData()
        settings.animation_duration_ms = self.anim_duration_spin.value()
        settings.language = self.language_combo.currentData()
        settings.autostart = self.autostart_check.isChecked()
        settings.start_menu_entry = self.startmenu_check.isChecked()
        settings.app_list_entry = self.applist_check.isChecked()
        settings.notify_on_reauth = self.reauth_check.isChecked()
        settings.first_run_done = True

    def save(self) -> None:
        error = HotkeyListener.validate(self.hotkey_edit.text().strip() or DEFAULT_HOTKEY)
        if error:
            QMessageBox.warning(self, tr("err.hotkey_title"), error)
            return
        self._collect()
        self.settings.save()
        win.apply_integration(
            self.settings.autostart,
            self.settings.start_menu_entry,
            self.settings.app_list_entry,
        )
        self.settings_saved.emit()
        QMessageBox.information(self, APP_DISPLAY_NAME, tr("msg.saved"))

    # ------------------------------------------------------------------
    # Sprache
    # ------------------------------------------------------------------
    def _on_language_selected(self, _index: int) -> None:
        if getattr(self, "_loading", False):
            return
        code = self.language_combo.currentData()
        if not code or code == self.settings.language:
            return
        self._collect()
        self.settings.language = code
        self.settings.save()
        self.settings.apply_language()
        self.language_changed.emit()  # das Fenster wird uebersetzt neu aufgebaut

    def _record_hotkey(self) -> None:
        if self.service is not None:
            self.service.pause_hotkey()  # alte Kombination waehrend der Aufnahme stumm
        try:
            dialog = HotkeyRecordDialog(self)
            if dialog.exec() == QDialog.DialogCode.Accepted and dialog.result_hotkey:
                self.hotkey_edit.setText(dialog.result_hotkey)
        finally:
            if self.service is not None:
                self.service.resume_hotkey()

    def _check_hotkey(self) -> None:
        value = self.hotkey_edit.text().strip() or DEFAULT_HOTKEY
        error = HotkeyListener.validate(value)
        if error:
            QMessageBox.warning(self, tr("err.hotkey_title"), error)
        else:
            QMessageBox.information(self, APP_DISPLAY_NAME, tr("msg.hotkey_valid", hotkey=value))

    # ------------------------------------------------------------------
    # Credentials / Login
    # ------------------------------------------------------------------
    def _redirect_uri(self) -> str:
        return f"http://127.0.0.1:{self.port_spin.value()}/callback"

    def _update_redirect_label(self) -> None:
        self.redirect_label.setText(self._redirect_uri())

    def _save_credentials(self) -> None:
        client_id = self.client_id_edit.text().strip()
        if not client_id:
            QMessageBox.warning(self, APP_DISPLAY_NAME, tr("msg.need_client_id"))
            return
        self.settings.redirect_port = self.port_spin.value()
        self.settings.save()
        self.auth.save_credentials(client_id, self.client_secret_edit.text())
        self._refresh_status()
        QMessageBox.information(self, APP_DISPLAY_NAME, tr("msg.creds_saved"))

    def _delete_credentials(self) -> None:
        if (
            QMessageBox.question(self, APP_DISPLAY_NAME, tr("ask.delete_creds"))
            != QMessageBox.StandardButton.Yes
        ):
            return
        self.auth.clear_credentials()
        self.client_id_edit.clear()
        self.client_secret_edit.clear()
        self.settings.bump_auth_version()
        self._refresh_status()

    def _do_login(self) -> None:
        if not self.auth.has_credentials():
            QMessageBox.warning(self, APP_DISPLAY_NAME, tr("msg.need_creds_first"))
            return
        self.settings.redirect_port = self.port_spin.value()
        self.settings.save()
        dialog = _LoginDialog(self.auth, self)
        result = dialog.exec()
        if result == QDialog.DialogCode.Accepted:
            self.settings.bump_auth_version()
            self._refresh_status()
            self.settings_saved.emit()  # Dienst laedt das frische Token sofort
            QMessageBox.information(self, APP_DISPLAY_NAME, tr("msg.login_ok"))
        elif dialog.error:
            QMessageBox.critical(self, tr("err.login_failed"), dialog.error)

    def _do_logout(self) -> None:
        self.auth.clear_token()
        self.settings.bump_auth_version()
        self._refresh_status()
        self.settings_saved.emit()

    def _refresh_status(self) -> None:
        if not self.auth.has_credentials():
            text = tr("status.no_creds")
        else:
            token = self.auth.load_token(force=True)
            if token is None:
                text = tr("status.not_logged_in")
            else:
                expiry = dt.datetime.fromtimestamp(token.refresh_expires_at)
                days = max(0, int((token.refresh_expires_at - dt.datetime.now().timestamp()) / 86400))
                flow = tr("flow.pkce") if self.auth.uses_pkce else tr("flow.secret")
                text = tr(
                    "status.logged_in",
                    flow=flow,
                    date=f"{expiry:%d.%m.%Y}",
                    days=days,
                )
        self.status_label.setText(text)
        self.login_button.setEnabled(self.auth.has_credentials())
        self.logout_button.setEnabled(self.auth.is_logged_in())

    def _test_popup(self) -> None:
        if self.service is not None:
            self.service.show_current_track()

    # ------------------------------------------------------------------
    # Vorschau / Reset
    # ------------------------------------------------------------------
    def _show_preview(self) -> None:
        preview_settings = copy.copy(self.settings)
        preview_settings.experimental_progress_bar = self.progress_check.isChecked()
        preview_settings.experimental_animations = self.anim_check.isChecked()
        preview_settings.animation_mode = self.anim_combo.currentData()
        preview_settings.animation_duration_ms = self.anim_duration_spin.value()
        preview_settings.display_duration_ms = 4000
        preview_settings.margin_x = self.margin_x_spin.value()
        preview_settings.margin_y = self.margin_y_spin.value()

        self._preview = PopupWindow(preview_settings)
        demo = Track(
            id="preview",
            title=tr("preview.title"),
            artists=APP_DISPLAY_NAME,
            cover_url=None,
            duration_ms=200000,
            progress_ms=70000,
            is_playing=True,
        )
        self._preview.set_track(demo)
        self._preview.show_popup()

    def _wipe_everything(self) -> None:
        if (
            QMessageBox.question(self, APP_DISPLAY_NAME, tr("ask.wipe"))
            != QMessageBox.StandardButton.Yes
        ):
            return
        wipe_all()
        language = self.settings.language
        fresh = Settings()
        fresh.language = language  # Sprache behalten, alles andere zuruecksetzen
        fresh.auth_version = self.settings.auth_version + 1
        self.settings.__dict__.update(fresh.__dict__)
        self.settings.save()
        self._load_into_widgets()
        self._refresh_status()
