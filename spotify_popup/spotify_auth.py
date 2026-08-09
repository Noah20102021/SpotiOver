"""Spotify-OAuth: Authorization Code (mit oder ohne PKCE), Login ueber Loopback-Server,
Token-Refresh inklusive korrekter Behandlung abgelaufener Refresh-Tokens.

Hintergrund (Spotify-Mail vom Juni 2026): Refresh-Tokens laufen nach sechs Monaten ab.
Ein Refresh liefert dann `invalid_grant`. Dann gilt:
  * NICHT erneut versuchen
  * gespeichertes Token verwerfen
  * Benutzer neu durch den Login-Flow schicken
Genau das macht `ReauthRequired` weiter unten.
"""

from __future__ import annotations

import base64
import hashlib
import http.server
import json
import secrets
import threading
import time
import urllib.parse
import webbrowser
from dataclasses import asdict, dataclass
from typing import Callable, Optional

import requests

from . import APP_DISPLAY_NAME
from .config import Settings
from .i18n import current_language, tr
from .secrets_store import delete_secret, get_secret, set_secret

AUTHORIZE_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
SCOPE = "user-read-currently-playing"

# Spotify: Refresh-Token lebt sechs Monate. Etwas Puffer fuer die Warnung im UI.
REFRESH_TOKEN_LIFETIME_DAYS = 180
HTTP_TIMEOUT = 15


class AuthError(Exception):
    """Allgemeiner Fehler beim Authentifizieren."""


class ReauthRequired(AuthError):
    """Refresh-Token ungueltig/abgelaufen - der Benutzer muss sich neu anmelden."""


class NoCredentials(AuthError):
    """Es sind noch keine API-Credentials hinterlegt."""


@dataclass
class Token:
    access_token: str
    refresh_token: str
    expires_at: float
    scope: str = SCOPE
    refresh_issued_at: float = 0.0

    @property
    def expired(self) -> bool:
        return time.time() >= self.expires_at - 60  # 60 s Sicherheitspuffer

    @property
    def refresh_expires_at(self) -> float:
        base = self.refresh_issued_at or time.time()
        return base + REFRESH_TOKEN_LIFETIME_DAYS * 86400


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    result: dict = {}
    expected_state: str = ""

    def do_GET(self):  # noqa: N802 (von BaseHTTPRequestHandler vorgegeben)
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        state = params.get("state", [""])[0]

        if state != _CallbackHandler.expected_state:
            body, ok = tr("html.bad_state"), False
        elif "error" in params:
            body, ok = tr("html.error", error=params["error"][0]), False
            _CallbackHandler.result = {"error": params["error"][0]}
        elif "code" in params:
            body, ok = tr("html.success"), True
            _CallbackHandler.result = {"code": params["code"][0]}
        else:
            body, ok = tr("html.no_code"), False

        html = f"""<!doctype html><html lang="{current_language()}"><head><meta charset="utf-8">
<title>{APP_DISPLAY_NAME}</title></head>
<body style="font-family:Segoe UI,sans-serif;background:#181818;color:#fff;
display:flex;align-items:center;justify-content:center;height:100vh;margin:0">
<div style="text-align:center">
<h2 style="color:{'#1DB954' if ok else '#e2554f'};margin-bottom:8px">{APP_DISPLAY_NAME}</h2>
<p>{body}</p></div></body></html>"""
        encoded = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, *_args):  # Konsolen-Spam unterdruecken
        return


class SpotifyAuth:
    """Kapselt alles rund um Tokens. Thread-sicher fuer die zwei Nutzer (UI + Poll-Timer)."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._lock = threading.RLock()
        self._token: Optional[Token] = None
        self._token_loaded = False

    # ------------------------------------------------------------------
    # Credentials
    # ------------------------------------------------------------------
    @property
    def client_id(self) -> str:
        return (get_secret("client_id") or "").strip()

    @property
    def client_secret(self) -> str:
        return (get_secret("client_secret") or "").strip()

    @property
    def uses_pkce(self) -> bool:
        """Ohne Client-Secret laeuft der Flow ueber PKCE (von Spotify fuer Desktop-Apps empfohlen)."""
        return not self.client_secret

    def has_credentials(self) -> bool:
        return bool(self.client_id)

    def save_credentials(self, client_id: str, client_secret: str) -> None:
        set_secret("client_id", client_id.strip())
        if client_secret.strip():
            set_secret("client_secret", client_secret.strip())
        else:
            delete_secret("client_secret")

    def clear_credentials(self) -> None:
        delete_secret("client_id")
        delete_secret("client_secret")
        self.clear_token()

    # ------------------------------------------------------------------
    # Token-Persistenz
    # ------------------------------------------------------------------
    def load_token(self, force: bool = False) -> Optional[Token]:
        with self._lock:
            if self._token_loaded and not force:
                return self._token
            raw = get_secret("token")
            self._token = None
            if raw:
                try:
                    self._token = Token(**json.loads(raw))
                except Exception:
                    delete_secret("token")
            self._token_loaded = True
            return self._token

    def _store_token(self, token: Token) -> None:
        with self._lock:
            self._token = token
            self._token_loaded = True
            set_secret("token", json.dumps(asdict(token)))

    def clear_token(self) -> None:
        with self._lock:
            self._token = None
            self._token_loaded = True
            delete_secret("token")

    def is_logged_in(self) -> bool:
        return self.load_token() is not None

    # ------------------------------------------------------------------
    # Access-Token besorgen
    # ------------------------------------------------------------------
    def get_access_token(self, force_refresh: bool = False) -> str:
        with self._lock:
            if not self.has_credentials():
                raise NoCredentials("Es sind keine Spotify-API-Credentials hinterlegt.")
            token = self.load_token()
            if token is None:
                raise ReauthRequired("Noch keine Anmeldung vorhanden.")
            if force_refresh or token.expired:
                token = self._refresh(token)
            return token.access_token

    def _refresh(self, token: Token) -> Token:
        data = {"grant_type": "refresh_token", "refresh_token": token.refresh_token}
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        if self.uses_pkce:
            data["client_id"] = self.client_id
        else:
            basic = base64.b64encode(
                f"{self.client_id}:{self.client_secret}".encode("utf-8")
            ).decode("ascii")
            headers["Authorization"] = f"Basic {basic}"

        try:
            response = requests.post(TOKEN_URL, data=data, headers=headers, timeout=HTTP_TIMEOUT)
        except requests.RequestException as exc:
            # Netzwerkproblem ist KEIN Grund, das Token wegzuwerfen.
            raise AuthError(f"Netzwerkfehler beim Token-Refresh: {exc}") from exc

        if response.status_code == 200:
            payload = response.json()
            new_refresh = payload.get("refresh_token")
            refreshed = Token(
                access_token=payload["access_token"],
                # Spotify rotiert Refresh-Tokens (v.a. bei PKCE) - immer den neuen speichern.
                refresh_token=new_refresh or token.refresh_token,
                expires_at=time.time() + int(payload.get("expires_in", 3600)),
                scope=payload.get("scope", token.scope),
                refresh_issued_at=time.time() if new_refresh else token.refresh_issued_at,
            )
            self._store_token(refreshed)
            return refreshed

        error = ""
        try:
            error = (response.json() or {}).get("error", "")
        except ValueError:
            error = response.text[:200]

        if response.status_code in (400, 401) and error in (
            "invalid_grant",
            "invalid_client",
        ):
            # Genau der Fall aus der Spotify-Mail: Token verwerfen, NICHT erneut versuchen.
            self.clear_token()
            if error == "invalid_client":
                raise ReauthRequired(
                    "Die hinterlegten API-Credentials wurden von Spotify abgelehnt "
                    "(invalid_client). Bitte Client-ID/Secret pruefen."
                )
            raise ReauthRequired(
                "Das Refresh-Token ist abgelaufen oder wurde widerrufen (invalid_grant). "
                "Bitte erneut bei Spotify anmelden."
            )

        raise AuthError(f"Token-Refresh fehlgeschlagen (HTTP {response.status_code}): {error}")

    # ------------------------------------------------------------------
    # Interaktiver Login
    # ------------------------------------------------------------------
    def build_authorize_url(self, state: str, code_challenge: Optional[str]) -> str:
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": self.settings.redirect_uri,
            "scope": SCOPE,
            "state": state,
            "show_dialog": "false",
        }
        if code_challenge:
            params["code_challenge_method"] = "S256"
            params["code_challenge"] = code_challenge
        return f"{AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"

    def interactive_login(
        self,
        timeout: int = 180,
        on_url: Optional[Callable[[str], None]] = None,
        cancelled: Optional[Callable[[], bool]] = None,
    ) -> Token:
        """Oeffnet den Browser, faengt den Redirect auf 127.0.0.1 ab und tauscht den Code ein."""
        if not self.has_credentials():
            raise NoCredentials("Bitte zuerst die API-Credentials speichern.")

        state = secrets.token_urlsafe(16)
        verifier = challenge = None
        if self.uses_pkce:
            verifier = _b64url(secrets.token_bytes(64))
            challenge = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())

        _CallbackHandler.result = {}
        _CallbackHandler.expected_state = state

        try:
            server = http.server.HTTPServer(("127.0.0.1", self.settings.redirect_port), _CallbackHandler)
        except OSError as exc:
            raise AuthError(
                f"Port {self.settings.redirect_port} ist belegt ({exc}). "
                "Bitte in den Einstellungen einen anderen Port waehlen "
                "(und ihn im Spotify-Dashboard als Redirect-URI eintragen)."
            ) from exc

        server.timeout = 1
        url = self.build_authorize_url(state, challenge)
        if on_url:
            on_url(url)
        webbrowser.open(url)

        deadline = time.time() + timeout
        try:
            while not _CallbackHandler.result and time.time() < deadline:
                if cancelled and cancelled():
                    raise AuthError("Login abgebrochen.")
                server.handle_request()
        finally:
            server.server_close()

        result = _CallbackHandler.result
        _CallbackHandler.result = {}
        if not result:
            raise AuthError("Zeitueberschreitung: Es kam keine Antwort von Spotify zurueck.")
        if "error" in result:
            raise AuthError(f"Spotify hat die Anmeldung abgelehnt: {result['error']}")

        return self._exchange_code(result["code"], verifier)

    def _exchange_code(self, code: str, verifier: Optional[str]) -> Token:
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.settings.redirect_uri,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        if verifier:
            data["client_id"] = self.client_id
            data["code_verifier"] = verifier
        else:
            basic = base64.b64encode(
                f"{self.client_id}:{self.client_secret}".encode("utf-8")
            ).decode("ascii")
            headers["Authorization"] = f"Basic {basic}"

        try:
            response = requests.post(TOKEN_URL, data=data, headers=headers, timeout=HTTP_TIMEOUT)
        except requests.RequestException as exc:
            raise AuthError(f"Netzwerkfehler beim Code-Tausch: {exc}") from exc

        if response.status_code != 200:
            detail = response.text[:300]
            raise AuthError(f"Code-Tausch fehlgeschlagen (HTTP {response.status_code}): {detail}")

        payload = response.json()
        if "refresh_token" not in payload:
            raise AuthError("Spotify hat kein Refresh-Token geliefert.")
        token = Token(
            access_token=payload["access_token"],
            refresh_token=payload["refresh_token"],
            expires_at=time.time() + int(payload.get("expires_in", 3600)),
            scope=payload.get("scope", SCOPE),
            refresh_issued_at=time.time(),
        )
        self._store_token(token)
        return token
