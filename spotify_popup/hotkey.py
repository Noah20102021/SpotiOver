"""Globaler Hotkey ueber pynput, gekapselt als QObject mit Signal."""

from __future__ import annotations

import threading
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal


def _safe_emit(signal, *args) -> None:
    """Signale aus dem Listener-Thread koennen nach dem Beenden ins Leere laufen -
    dann ist das C++-Objekt schon weg und Qt wirft einen RuntimeError."""
    try:
        signal.emit(*args)
    except RuntimeError:
        pass


class HotkeyListener(QObject):
    triggered = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._listener = None
        self._thread: Optional[threading.Thread] = None
        self._current = ""

    @property
    def current(self) -> str:
        return self._current

    def start(self, hotkey: str) -> None:
        self.stop()
        if not hotkey.strip():
            return
        self._current = hotkey

        def run() -> None:
            try:
                from pynput import keyboard

                listener = keyboard.GlobalHotKeys({hotkey: lambda: _safe_emit(self.triggered)})
                self._listener = listener
                listener.run()  # blockiert bis stop()
            except Exception as exc:  # ungueltige Kombination, fehlende Rechte, ...
                _safe_emit(self.failed, f"Hotkey '{hotkey}' konnte nicht registriert werden: {exc}")

        self._thread = threading.Thread(target=run, daemon=True, name="hotkey")
        self._thread.start()

    def stop(self) -> None:
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None
        self._thread = None
        self._current = ""

    @staticmethod
    def validate(hotkey: str) -> Optional[str]:
        """Gibt None zurueck, wenn die Kombination parsebar ist, sonst die Fehlermeldung."""
        try:
            from pynput import keyboard

            keyboard.HotKey.parse(hotkey)
            return None
        except Exception as exc:
            return str(exc)


# Modifier -> pynput-Schreibweise
_MODIFIERS = {
    "ctrl": "<ctrl>",
    "ctrl_l": "<ctrl>",
    "ctrl_r": "<ctrl>",
    "alt": "<alt>",
    "alt_l": "<alt>",
    "alt_r": "<alt>",
    "alt_gr": "<alt_gr>",
    "shift": "<shift>",
    "shift_l": "<shift>",
    "shift_r": "<shift>",
    "cmd": "<cmd>",
    "cmd_l": "<cmd>",
    "cmd_r": "<cmd>",
}
_MODIFIER_ORDER = ["<ctrl>", "<alt>", "<alt_gr>", "<shift>", "<cmd>"]


class HotkeyRecorder(QObject):
    """Nimmt die naechste gedrueckte Tastenkombination auf und liefert sie als pynput-String."""

    recorded = pyqtSignal(str)
    cancelled = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._listener = None
        self._pressed: list[str] = []

    def start(self) -> None:
        self.stop()
        self._pressed = []

        def run() -> None:
            try:
                from pynput import keyboard
            except Exception as exc:
                _safe_emit(self.failed, str(exc))
                return

            def on_press(key) -> None:
                name = getattr(key, "name", None)
                if name == "esc":
                    _safe_emit(self.cancelled)
                    self.stop()
                    return
                if name in _MODIFIERS:
                    token = _MODIFIERS[name]
                    if token not in self._pressed:
                        self._pressed.append(token)
                    return
                combo = self._finish(key)
                if combo:
                    _safe_emit(self.recorded, combo)
                self.stop()

            def on_release(key) -> None:
                name = getattr(key, "name", None)
                if name in _MODIFIERS:
                    token = _MODIFIERS[name]
                    if token in self._pressed:
                        self._pressed.remove(token)

            try:
                listener = keyboard.Listener(on_press=on_press, on_release=on_release)
                self._listener = listener
                listener.run()
            except Exception as exc:
                _safe_emit(self.failed, str(exc))

        threading.Thread(target=run, daemon=True, name="hotkey-recorder").start()

    def _finish(self, key) -> str:
        modifiers = [m for m in _MODIFIER_ORDER if m in self._pressed]

        name = getattr(key, "name", None)
        if name:  # F-Tasten, Pfeile, Space, Enter, ...
            main = f"<{name}>"
        else:
            char = getattr(key, "char", None)
            vk = getattr(key, "vk", None)
            if vk is not None and (0x30 <= vk <= 0x39 or 0x41 <= vk <= 0x5A):
                # Buchstaben/Ziffern ueber den Keycode: Mit gedruecktem Strg liefert
                # Windows als char ein Steuerzeichen, der vk bleibt aber korrekt.
                main = chr(vk).lower()
            elif char and char.isalnum():
                main = char.lower()
            elif vk:
                # Sonderzeichen wie '<' oder '^' sind layoutabhaengig - ueber den
                # virtuellen Keycode ist die Zuordnung eindeutig.
                main = f"<{vk}>"
            elif char:
                main = char
            else:
                return ""
        return "+".join(modifiers + [main])

    def stop(self) -> None:
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None
