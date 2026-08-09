"""Spotify Popup - kleines Now-Playing-Widget fuer Windows."""

# ---------------------------------------------------------------------------
# Hier und nur hier umbenennen / umgestalten:
# ---------------------------------------------------------------------------

APP_NAME = "Spotiover"          # exe-Name, Datenordner, Registry-Schluessel, Named Pipe
APP_DISPLAY_NAME = "Spotiover"  # alles Sichtbare: Fenstertitel, Tray, Startmenue
APP_VERSION = "2.1.0"
APP_PUBLISHER = "Private"

# Eigenes Logo (optional).
#   ""                        -> mitgeliefertes assets/icon.ico
#   "assets/mein_logo.ico"    -> relativ zum Projekt- bzw. exe-Ordner
#   r"C:\Bilder\logo.png"     -> absoluter Pfad
# Fuer Fenster und Tray sind .ico, .png und .svg moeglich.
# Fuer das exe-Icon und die Startmenue-Verknuepfung muss es eine .ico sein
# (PNG wird dort von Windows ignoriert); build.spec zieht sich diesen Wert automatisch.
APP_ICON_FILE = ""

__all__ = [
    "APP_NAME",
    "APP_DISPLAY_NAME",
    "APP_VERSION",
    "APP_PUBLISHER",
    "APP_ICON_FILE",
]
