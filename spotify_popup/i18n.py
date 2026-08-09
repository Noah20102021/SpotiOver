"""Winziges i18n-Modul: Deutsch / Englisch.

Kein Qt-Linguist, keine .qm-Dateien - einfach zwei Dicts. Reicht fuer eine App
dieser Groesse und laesst sich ohne Build-Schritt erweitern.

    from .i18n import tr, set_language
    set_language("en")
    tr("btn.save")                     -> "Save"
    tr("status.logged_in", flow="PKCE", date="01.02.2027", days=180)
"""

from __future__ import annotations

LANGUAGES: dict[str, str] = {"de": "Deutsch", "en": "English"}
DEFAULT_LANGUAGE = "de"

_current = DEFAULT_LANGUAGE

STRINGS: dict[str, dict[str, str]] = {
    "de": {
        # --- allgemein ---
        "app.settings_title": "{app} – Einstellungen",
        "btn.save": "Speichern",
        "btn.close": "Schließen",
        "btn.copy": "Kopieren",
        "btn.check": "Prüfen",
        "btn.cancel": "Abbrechen",
        "tab.spotify": "Spotify",
        "tab.display": "Anzeige",
        "tab.experimental": "Experimentell",
        "tab.system": "System",
        "msg.saved": "Gespeichert. Ein laufender Hintergrund-Dienst übernimmt die Änderungen sofort.",
        # --- Sprache ---
        "label.language": "Sprache:",
        "lang.dialog_title": "Sprache / Language",
        "lang.dialog_text": "In welcher Sprache soll die App laufen?\n\nWhich language would you like to use?",
        # --- Spotify-Tab ---
        "group.credentials": "API-Credentials",
        "label.client_id": "Client ID:",
        "label.client_secret": "Client Secret:",
        "label.port": "Redirect-Port:",
        "label.redirect_uri": "Redirect-URI:",
        "ph.client_id": "Client ID aus dem Spotify Developer Dashboard",
        "ph.client_secret": "optional – leer lassen für PKCE (empfohlen)",
        "hint.redirect": (
            "Diese URI muss im Spotify-Dashboard exakt so als Redirect-URI eingetragen sein.\n"
            "Spotify akzeptiert für http nur noch 127.0.0.1 – 'localhost' wird abgelehnt.\n"
            "Gespeichert wird verschlüsselt über: {backend}"
        ),
        "btn.save_creds": "Credentials speichern",
        "btn.delete_creds": "Credentials löschen",
        "group.login": "Anmeldung",
        "btn.login": "Mit Spotify anmelden",
        "btn.logout": "Abmelden",
        "status.no_creds": "Keine API-Credentials hinterlegt.",
        "status.not_logged_in": "Credentials vorhanden, aber noch nicht bei Spotify angemeldet.",
        "status.logged_in": (
            "Angemeldet ({flow}).\n"
            "Die Anmeldung muss laut Spotify-Richtlinie spätestens am {date} erneuert werden "
            "(noch ca. {days} Tage).\n"
            "Läuft sie ab, meldet sich die App von selbst."
        ),
        "flow.pkce": "PKCE, ohne Secret",
        "flow.secret": "Client Secret",
        "msg.need_client_id": "Bitte zumindest die Client ID eintragen.",
        "msg.creds_saved": "Credentials gespeichert. Jetzt einmal 'Mit Spotify anmelden' klicken.",
        "ask.delete_creds": "Client ID, Secret und die gespeicherte Anmeldung wirklich löschen?",
        "msg.need_creds_first": "Bitte zuerst die Credentials speichern.",
        "msg.login_ok": "Anmeldung erfolgreich.",
        "err.login_failed": "Anmeldung fehlgeschlagen",
        "dlg.login_title": "Bei Spotify anmelden",
        "dlg.login_text": (
            "Im Browser wurde die Spotify-Anmeldung geöffnet.\n"
            "Nach dem Bestätigen wird die Seite auf 127.0.0.1 zurückgeleitet –\n"
            "danach kannst du den Browser einfach schließen."
        ),
        # --- Anzeige-Tab ---
        "label.duration": "Anzeigedauer:",
        "label.poll": "Abfrage-Intervall:",
        "label.margin_x": "Abstand links:",
        "label.margin_y": "Abstand oben:",
        "label.hotkey": "Hotkey:",
        "chk.tray": "Tray-Symbol anzeigen (Menü zum Beenden)",
        "note.hotkey": (
            "Hotkey-Syntax von pynput, z. B. <ctrl>+<226> (Strg + '<' auf deutscher Tastatur),\n"
            "<ctrl>+<alt>+m oder <ctrl>+<shift>+s."
        ),
        "err.hotkey_title": "Hotkey ungültig",
        "msg.hotkey_valid": "'{hotkey}' ist gültig.",
        # --- Experimentell ---
        "note.experimental": (
            "Diese Funktionen sind optional. Ausgeschaltet verhält sich das Popup exakt "
            "wie die alte Version."
        ),
        "group.progress": "Progress-Bar",
        "chk.progress": "Progress-Bar am unteren Rand anzeigen",
        "note.progress": (
            "Die untersten 3 Pixel des Popups füllen sich passend zum Songfortschritt grün – "
            "innerhalb der abgerundeten Ecken, ohne dass sich Größe oder Layout ändern."
        ),
        "group.anim": "Animationen",
        "chk.anim": "Erweiterte Animationen verwenden",
        "label.anim_mode": "Modus:",
        "label.anim_duration": "Basisdauer:",
        "btn.preview": "Vorschau anzeigen",
        "preview.title": "Vorschau-Song",
        "anim.classic": "Klassisch (wie früher: Slide von oben, 300 ms)",
        "anim.smooth": "Smooth Slide (weiche Ease-Out-Kurve)",
        "anim.bounce": "Overshoot (fährt kurz über das Ziel hinaus)",
        "anim.pop": "Pop / Scale (poppt auf, kein Slide)",
        "anim.slide_pop": "Slide + Pop (Slide kombiniert mit Aufskalieren)",
        # --- System ---
        "group.integration": "Windows-Integration",
        "chk.autostart": "Beim Anmelden automatisch starten (Hintergrund-Dienst)",
        "chk.startmenu": "Im Startmenü eintragen (über die Windows-Suche findbar)",
        "chk.applist": "Unter 'Installierte Apps' aufführen",
        "chk.reauth": "Benachrichtigen, wenn eine neue Spotify-Anmeldung nötig ist",
        "group.service": "Dienst",
        "note.service_quit": "Autostart startet ihn ab dem nächsten Windows-Start automatisch.",
        "btn.record": "Aufnehmen",
        "dlg.record_title": "Tastenkombination aufnehmen",
        "dlg.record_text": (
            "Drücke jetzt die gewünschte Tastenkombination.\n"
            "Mindestens eine Modifikatortaste (Strg/Alt/Shift) plus eine weitere Taste.\n"
            "Esc bricht ab."
        ),
        "btn.test_popup": "Popup jetzt testen",
        "note.service_running": (
            "Der Hintergrund-Dienst läuft. Er bleibt aktiv, wenn du dieses Fenster schließt – "
            "beenden lässt er sich über das Tray-Symbol → Beenden."
        ),
        "note.service_missing": "Der Hintergrund-Dienst läuft in diesem Prozess nicht.",
        "group.reset": "Zurücksetzen",
        "btn.wipe": "Alle Daten löschen (Credentials, Token, Einstellungen)",
        "ask.wipe": (
            "Wirklich alles löschen? Danach müssen Credentials und Anmeldung neu "
            "eingerichtet werden."
        ),
        "label.datadir": "Datenordner: {path}",
        "hint.dev": (
            "Hinweis: Die App läuft gerade aus dem Quellcode ({python}). "
            "Autostart/Startmenü zeigen deshalb auf den Python-Interpreter. "
            "Nach dem Build mit PyInstaller einfach erneut speichern."
        ),
        # --- Tray / Dienst ---
        "tray.show_now": "Aktuellen Song anzeigen",
        "tray.settings": "Einstellungen ...",
        "tray.quit": "Beenden",
        "notify.no_creds": (
            "Es sind noch keine Spotify-API-Credentials hinterlegt. "
            "Die Einstellungen werden geöffnet."
        ),
        "notify.need_login": "Bitte einmal bei Spotify anmelden.",
        "notify.reauth_title": "{app}: Anmeldung abgelaufen",
        "notify.reauth_body": "Spotify verlangt eine neue Anmeldung. Einstellungen werden geöffnet.",
        "tooltip.creds_missing": "{app}: API-Credentials fehlen",
        "tooltip.login_required": "{app}: Anmeldung erforderlich",
        "tooltip.expired": "{app}: Anmeldung abgelaufen",
        # --- Ersteinrichtung / Deinstallation ---
        "welcome.body": (
            "Willkommen!\n\n"
            "Die App wurde eingerichtet: Sie startet ab jetzt automatisch mit Windows, "
            "liegt im Startmenü und ist über die Windows-Suche zu finden. "
            "Der Autostart lässt sich im Tab 'System' jederzeit abschalten.\n\n"
            "Jetzt noch:\n"
            "1. Client ID (und optional Secret) aus dem Spotify Developer Dashboard eintragen\n"
            "2. Die angezeigte Redirect-URI dort hinterlegen\n"
            "3. 'Mit Spotify anmelden' klicken"
        ),
        "uninstall.question": (
            "Autostart, Startmenü-Eintrag und den Eintrag unter 'Installierte Apps' entfernen?\n\n"
            "Mit 'Ja' werden zusätzlich die gespeicherten Credentials, das Spotify-Token "
            "und die Einstellungen gelöscht.\n"
            "Mit 'Nein' bleiben diese Daten erhalten."
        ),
        "uninstall.done": "Entfernt. Die .exe selbst kannst du jetzt einfach löschen.",
        # --- OAuth-Callback-Seite im Browser ---
        "html.success": "Anmeldung erfolgreich. Du kannst dieses Fenster schließen.",
        "html.bad_state": "Ungültiger state-Parameter. Bitte Login erneut starten.",
        "html.no_code": "Kein Code erhalten.",
        "html.error": "Spotify meldet: {error}",
    },
    "en": {
        # --- general ---
        "app.settings_title": "{app} – Settings",
        "btn.save": "Save",
        "btn.close": "Close",
        "btn.copy": "Copy",
        "btn.check": "Check",
        "btn.cancel": "Cancel",
        "tab.spotify": "Spotify",
        "tab.display": "Display",
        "tab.experimental": "Experimental",
        "tab.system": "System",
        "msg.saved": "Saved. A running background service picks up the changes right away.",
        # --- language ---
        "label.language": "Language:",
        "lang.dialog_title": "Sprache / Language",
        "lang.dialog_text": "In welcher Sprache soll die App laufen?\n\nWhich language would you like to use?",
        # --- Spotify tab ---
        "group.credentials": "API credentials",
        "label.client_id": "Client ID:",
        "label.client_secret": "Client secret:",
        "label.port": "Redirect port:",
        "label.redirect_uri": "Redirect URI:",
        "ph.client_id": "Client ID from the Spotify Developer Dashboard",
        "ph.client_secret": "optional – leave empty to use PKCE (recommended)",
        "hint.redirect": (
            "This URI has to be registered in the Spotify dashboard exactly as shown.\n"
            "For http, Spotify only accepts 127.0.0.1 – 'localhost' is rejected.\n"
            "Stored encrypted via: {backend}"
        ),
        "btn.save_creds": "Save credentials",
        "btn.delete_creds": "Delete credentials",
        "group.login": "Sign-in",
        "btn.login": "Sign in with Spotify",
        "btn.logout": "Sign out",
        "status.no_creds": "No API credentials stored yet.",
        "status.not_logged_in": "Credentials stored, but not signed in to Spotify yet.",
        "status.logged_in": (
            "Signed in ({flow}).\n"
            "Per Spotify policy the sign-in has to be renewed by {date} at the latest "
            "(about {days} days left).\n"
            "If it expires, the app will ask you automatically."
        ),
        "flow.pkce": "PKCE, no secret",
        "flow.secret": "client secret",
        "msg.need_client_id": "Please enter at least the client ID.",
        "msg.creds_saved": "Credentials saved. Now click 'Sign in with Spotify'.",
        "ask.delete_creds": "Really delete client ID, secret and the stored sign-in?",
        "msg.need_creds_first": "Please save your credentials first.",
        "msg.login_ok": "Signed in successfully.",
        "err.login_failed": "Sign-in failed",
        "dlg.login_title": "Sign in with Spotify",
        "dlg.login_text": (
            "The Spotify sign-in page was opened in your browser.\n"
            "After confirming you'll be redirected to 127.0.0.1 –\n"
            "then you can simply close the browser tab."
        ),
        # --- display tab ---
        "label.duration": "Display duration:",
        "label.poll": "Polling interval:",
        "label.margin_x": "Margin left:",
        "label.margin_y": "Margin top:",
        "label.hotkey": "Hotkey:",
        "chk.tray": "Show tray icon (menu to quit)",
        "note.hotkey": (
            "pynput hotkey syntax, e.g. <ctrl>+<226> (Ctrl + '<' on a German layout),\n"
            "<ctrl>+<alt>+m or <ctrl>+<shift>+s."
        ),
        "err.hotkey_title": "Invalid hotkey",
        "msg.hotkey_valid": "'{hotkey}' is valid.",
        # --- experimental ---
        "note.experimental": (
            "These features are optional. With them switched off the popup behaves exactly "
            "like the old version."
        ),
        "group.progress": "Progress bar",
        "chk.progress": "Show a progress bar along the bottom edge",
        "note.progress": (
            "The bottom 3 pixels of the popup fill up green as the track plays – inside the "
            "rounded corners, without changing size or layout."
        ),
        "group.anim": "Animations",
        "chk.anim": "Use advanced animations",
        "label.anim_mode": "Mode:",
        "label.anim_duration": "Base duration:",
        "btn.preview": "Show preview",
        "preview.title": "Preview Song",
        "anim.classic": "Classic (as before: slide in from the top, 300 ms)",
        "anim.smooth": "Smooth slide (soft ease-out curve)",
        "anim.bounce": "Overshoot (goes past the target and settles back)",
        "anim.pop": "Pop / scale (scales up, no slide)",
        "anim.slide_pop": "Slide + pop (slide combined with scaling up)",
        # --- system ---
        "group.integration": "Windows integration",
        "chk.autostart": "Start automatically when I sign in (background service)",
        "chk.startmenu": "Add to the Start menu (findable via Windows search)",
        "chk.applist": "List under 'Installed apps'",
        "chk.reauth": "Notify me when Spotify requires a new sign-in",
        "group.service": "Service",
        "note.service_quit": "With autostart on it launches automatically at the next Windows start.",
        "btn.record": "Record",
        "dlg.record_title": "Record hotkey",
        "dlg.record_text": (
            "Press the key combination you want now.\n"
            "At least one modifier (Ctrl/Alt/Shift) plus another key.\n"
            "Esc cancels."
        ),
        "btn.test_popup": "Test popup now",
        "note.service_running": (
            "The background service is running. It stays active when you close this window – "
            "you can stop it via the tray icon → Quit."
        ),
        "note.service_missing": "The background service is not running in this process.",
        "group.reset": "Reset",
        "btn.wipe": "Delete all data (credentials, token, settings)",
        "ask.wipe": (
            "Really delete everything? You'll have to set up credentials and sign-in again."
        ),
        "label.datadir": "Data folder: {path}",
        "hint.dev": (
            "Note: the app is currently running from source ({python}), so autostart and the "
            "Start menu entry point at the Python interpreter. Just save again after building "
            "with PyInstaller."
        ),
        # --- tray / service ---
        "tray.show_now": "Show current song",
        "tray.settings": "Settings ...",
        "tray.quit": "Quit",
        "notify.no_creds": "No Spotify API credentials stored yet. Opening the settings.",
        "notify.need_login": "Please sign in to Spotify once.",
        "notify.reauth_title": "{app}: sign-in expired",
        "notify.reauth_body": "Spotify requires a new sign-in. Opening the settings.",
        "tooltip.creds_missing": "{app}: API credentials missing",
        "tooltip.login_required": "{app}: sign-in required",
        "tooltip.expired": "{app}: sign-in expired",
        # --- first run / uninstall ---
        "welcome.body": (
            "Welcome!\n\n"
            "The app is set up: it now starts automatically with Windows, sits in the Start "
            "menu and can be found via Windows search. You can turn autostart off any time on "
            "the 'System' tab.\n\n"
            "What's left:\n"
            "1. Enter the client ID (and optionally the secret) from the Spotify Developer Dashboard\n"
            "2. Register the redirect URI shown there\n"
            "3. Click 'Sign in with Spotify'"
        ),
        "uninstall.question": (
            "Remove autostart, the Start menu entry and the 'Installed apps' entry?\n\n"
            "Choosing 'Yes' also deletes the stored credentials, the Spotify token and your "
            "settings.\n"
            "Choosing 'No' keeps that data."
        ),
        "uninstall.done": "Removed. You can simply delete the .exe now.",
        # --- OAuth callback page ---
        "html.success": "Signed in successfully. You can close this window.",
        "html.bad_state": "Invalid state parameter. Please start the sign-in again.",
        "html.no_code": "No authorization code received.",
        "html.error": "Spotify reports: {error}",
    },
}


def set_language(code: str) -> None:
    global _current
    _current = code if code in STRINGS else DEFAULT_LANGUAGE


def current_language() -> str:
    return _current


def system_language() -> str:
    """Sprachvorschlag anhand der Windows-Spracheinstellung."""
    try:
        from PyQt6.QtCore import QLocale

        name = QLocale.system().name().lower()
    except Exception:
        name = ""
    return "de" if name.startswith("de") else "en"


def tr(key: str, **kwargs) -> str:
    text = STRINGS.get(_current, {}).get(key)
    if text is None:
        text = STRINGS[DEFAULT_LANGUAGE].get(key, key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError):
            return text
    return text
