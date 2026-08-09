"""Sichere Ablage von Client-ID/Secret und OAuth-Token.

Reihenfolge:
1. Windows Credential Manager ueber `keyring` (bevorzugt)
2. Fallback: Datei, mit Windows-DPAPI an den Benutzeraccount gebunden verschluesselt

In beiden Faellen liegt nichts davon im Code oder im Build -> die fertige .exe
kann bedenkenlos auf GitHub hochgeladen werden.
"""

from __future__ import annotations

import base64
import json
import os
import sys
from typing import Optional

from . import APP_NAME
from .paths import secrets_file

_SERVICE = APP_NAME

try:  # optionale Abhaengigkeit
    import keyring

    _KEYRING_OK = True
except Exception:  # pragma: no cover
    keyring = None  # type: ignore[assignment]
    _KEYRING_OK = False


# --------------------------------------------------------------------------
# DPAPI (nur Windows)
# --------------------------------------------------------------------------
def _dpapi(protect: bool, data: bytes) -> bytes:
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    def to_blob(payload: bytes) -> DATA_BLOB:
        buf = ctypes.create_string_buffer(payload, len(payload))
        return DATA_BLOB(len(payload), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))

    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    blob_in = to_blob(data)
    blob_out = DATA_BLOB()
    fn = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    ok = fn(ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out))
    if not ok:
        raise OSError(f"DPAPI-Aufruf fehlgeschlagen (Code {ctypes.get_last_error()})")
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        kernel32.LocalFree(blob_out.pbData)


def _file_read() -> dict[str, str]:
    path = secrets_file()
    if not path.exists():
        return {}
    try:
        raw = path.read_bytes()
        if sys.platform.startswith("win"):
            raw = _dpapi(False, raw)
        return json.loads(raw.decode("utf-8"))
    except Exception:
        return {}


def _file_write(values: dict[str, str]) -> None:
    path = secrets_file()
    raw = json.dumps(values).encode("utf-8")
    if sys.platform.startswith("win"):
        raw = _dpapi(True, raw)
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(raw)
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, path)


# --------------------------------------------------------------------------
# Oeffentliche API
# --------------------------------------------------------------------------
def set_secret(key: str, value: Optional[str]) -> None:
    if value is None:
        delete_secret(key)
        return
    if _KEYRING_OK:
        try:
            keyring.set_password(_SERVICE, key, value)
            return
        except Exception:
            pass
    values = _file_read()
    values[key] = value
    _file_write(values)


def get_secret(key: str) -> Optional[str]:
    if _KEYRING_OK:
        try:
            value = keyring.get_password(_SERVICE, key)
            if value is not None:
                return value
        except Exception:
            pass
    return _file_read().get(key)


def delete_secret(key: str) -> None:
    if _KEYRING_OK:
        try:
            keyring.delete_password(_SERVICE, key)
        except Exception:
            pass
    values = _file_read()
    if key in values:
        values.pop(key, None)
        _file_write(values)


def wipe_all() -> None:
    for key in ("client_id", "client_secret", "token"):
        delete_secret(key)
    try:
        secrets_file().unlink(missing_ok=True)
    except OSError:
        pass


def backend_name() -> str:
    if _KEYRING_OK:
        try:
            return f"Windows Credential Manager ({keyring.get_keyring().__class__.__name__})"
        except Exception:
            pass
    return "DPAPI-verschluesselte Datei"
