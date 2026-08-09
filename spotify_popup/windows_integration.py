"""Windows-Integration: Autostart, Startmenue-Eintrag (Suche!) und "Installierte Apps".

Alles laeuft unter HKEY_CURRENT_USER bzw. im Benutzerprofil - es werden keine
Administratorrechte gebraucht.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from . import APP_DISPLAY_NAME, APP_NAME, APP_PUBLISHER, APP_VERSION
from .paths import (
    CREATE_NO_WINDOW,
    IS_FROZEN,
    IS_WINDOWS,
    asset_path,
    custom_icon_path,
    launch_target,
)

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
UNINSTALL_KEY = rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{APP_NAME}"
SERVICE_ARG = "--service"


def _quoted_command(extra_args: list[str]) -> str:
    program, base_args = launch_target()
    parts = [f'"{program}"'] + [f'"{a}"' if " " in a else a for a in base_args + extra_args]
    return " ".join(parts)


def _start_menu_dir() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    path = Path(base) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def shortcut_path() -> Path:
    return _start_menu_dir() / f"{APP_DISPLAY_NAME}.lnk"


def _icon_location() -> str:
    """Icon fuer Verknuepfung und "Installierte Apps" - als "Pfad,Index".

    Wichtig: NICHT auf assets/icon.ico im PyInstaller-Bundle zeigen. Das liegt bei einer
    onefile-exe in einem Temp-Ordner (sys._MEIPASS), der nach dem Beenden verschwindet -
    dann zeigt das Startmenue nur noch ein leeres Datei-Symbol. Das in die exe eingebettete
    Icon ist dagegen dauerhaft da.
    """
    custom = custom_icon_path()
    if custom and custom.suffix.lower() == ".ico":
        return f"{custom},0"  # dauerhafter, absoluter Pfad
    program, _ = launch_target()
    if IS_FROZEN:
        return f"{program},0"  # in die exe eingebettetes Icon
    icon = asset_path("icon.ico")
    return f"{icon},0" if icon else f"{program},0"


# --------------------------------------------------------------------------
# Autostart
# --------------------------------------------------------------------------
def set_autostart(enabled: bool) -> None:
    if not IS_WINDOWS:
        return
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_ALL_ACCESS) as key:
        if enabled:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, _quoted_command([SERVICE_ARG]))
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass


def is_autostart_enabled() -> bool:
    if not IS_WINDOWS:
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, APP_NAME)
            return bool(value)
    except FileNotFoundError:
        return False


def autostart_command() -> str:
    if not IS_WINDOWS:
        return ""
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            return winreg.QueryValueEx(key, APP_NAME)[0]
    except FileNotFoundError:
        return ""


# --------------------------------------------------------------------------
# Startmenue-Verknuepfung (macht die App ueber die Windows-Suche auffindbar)
# --------------------------------------------------------------------------
def create_start_menu_shortcut() -> bool:
    if not IS_WINDOWS:
        return False
    program, base_args = launch_target()
    arguments = " ".join(base_args)
    target = shortcut_path()
    script = (
        "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('{lnk}');"
        "$s.TargetPath='{target}';"
        "$s.Arguments='{args}';"
        "$s.WorkingDirectory='{cwd}';"
        "$s.IconLocation='{icon}';"
        "$s.Description='{desc}';"
        "$s.Save()"
    ).format(
        lnk=str(target).replace("'", "''"),
        target=program.replace("'", "''"),
        args=arguments.replace("'", "''"),
        cwd=str(Path(program).parent).replace("'", "''"),
        icon=_icon_location().replace("'", "''"),
        desc=f"{APP_DISPLAY_NAME} - Einstellungen",
    )
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command", script],
            check=True,
            creationflags=CREATE_NO_WINDOW,
            timeout=30,
        )
        return True
    except Exception:
        return False


def remove_start_menu_shortcut() -> None:
    try:
        shortcut_path().unlink(missing_ok=True)
    except OSError:
        pass


def has_start_menu_shortcut() -> bool:
    return shortcut_path().exists()


# --------------------------------------------------------------------------
# Eintrag unter "Installierte Apps" / "Apps & Features"
# --------------------------------------------------------------------------
def register_app_entry() -> None:
    if not IS_WINDOWS:
        return
    import winreg

    program, _ = launch_target()
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as key:
        values = {
            "DisplayName": APP_DISPLAY_NAME,
            "DisplayVersion": APP_VERSION,
            "Publisher": APP_PUBLISHER,
            "DisplayIcon": _icon_location(),
            "InstallLocation": str(Path(program).parent),
            "UninstallString": _quoted_command(["--uninstall"]),
            "QuietUninstallString": _quoted_command(["--uninstall", "--silent"]),
        }
        for name, value in values.items():
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
        for name in ("NoModify", "NoRepair"):
            winreg.SetValueEx(key, name, 0, winreg.REG_DWORD, 1)


def unregister_app_entry() -> None:
    if not IS_WINDOWS:
        return
    import winreg

    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY)
    except FileNotFoundError:
        pass


def has_app_entry() -> bool:
    if not IS_WINDOWS:
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY):
            return True
    except FileNotFoundError:
        return False


# --------------------------------------------------------------------------
def apply_integration(autostart: bool, start_menu: bool, app_list: bool) -> None:
    set_autostart(autostart)
    if start_menu:
        create_start_menu_shortcut()
    else:
        remove_start_menu_shortcut()
    if app_list:
        register_app_entry()
    else:
        unregister_app_entry()


def remove_all_integration() -> None:
    set_autostart(False)
    remove_start_menu_shortcut()
    unregister_app_entry()


def integration_hint() -> str:
    if IS_FROZEN:
        return ""
    return (
        "Hinweis: Die App laeuft gerade aus dem Quellcode "
        f"({sys.executable}). Autostart/Startmenue zeigen deshalb auf den "
        "Python-Interpreter. Nach dem Build mit PyInstaller einfach erneut setzen."
    )
