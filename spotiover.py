import spotipy
from spotipy.oauth2 import SpotifyOAuth
from PyQt6.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QFrame
from PyQt6.QtCore import Qt, QTimer, QPoint, QPropertyAnimation, QEasingCurve, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QPixmap
from PyQt6.QtGui import QPainterPath, QPainter, QBrush
import sys
import time
import requests
from io import BytesIO
import os
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
import threading
from pynput import keyboard

# Token Cache im Benutzerverzeichnis
cache_path = os.path.join(os.path.expanduser("~"), ".spotify_token_cache")
auth_code = None

class SpotifySignals(QObject):
    show_track = pyqtSignal()

class PopupWindow(QWidget):
    def __init__(self, spotify_client):
        super().__init__()
        self.spotify_client = spotify_client
        self.signals = SpotifySignals()
        self.signals.show_track.connect(self.show_current_track)
        
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Container für den Inhalt
        self.container = QFrame(self)
        self.container.setObjectName("container")
        
        container_layout = QHBoxLayout(self.container)
        container_layout.setContentsMargins(0, 0, 12, 0)
        container_layout.setSpacing(8)
        
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.container)
        
        self.cover_label = RoundedLabel()
        self.cover_label.setFixedSize(64, 64)
        container_layout.addWidget(self.cover_label)
        
        text_layout = QVBoxLayout()
        text_layout.setSpacing(0)
        text_layout.setContentsMargins(0, 12, 8, 12)
        
        self.artist_label = QLabel()
        self.artist_label.setFont(QFont('Segoe UI', 10))
        self.artist_label.setStyleSheet("color: white; background-color: transparent;")
        text_layout.addWidget(self.artist_label)
        
        self.title_label = QLabel()
        self.title_label.setFont(QFont('Segoe UI', 14))
        self.title_label.setStyleSheet("color: #1DB954; background-color: transparent;")
        text_layout.addWidget(self.title_label)
        
        container_layout.addLayout(text_layout)
        
        self.container.setStyleSheet("""
        #container {
            background-color: #181818;
            border-radius: 10px;
        }
        """)
        
        self.hide_timer = QTimer(self)
        self.hide_timer.timeout.connect(self.start_hide_animation)
        
        self.title_label.setMaximumWidth(250)
        self.artist_label.setMaximumWidth(250)
        
        self.show_animation = QPropertyAnimation(self, b"pos")
        self.show_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.show_animation.setDuration(300)
        
        self.hide_animation = QPropertyAnimation(self, b"pos")
        self.hide_animation.setEasingCurve(QEasingCurve.Type.InCubic)
        self.hide_animation.setDuration(300)
        self.hide_animation.finished.connect(self.hide)

        # Timer für Track-Check
        self.check_timer = QTimer(self)
        self.check_timer.timeout.connect(self.check_current_track)
        self.check_timer.start(1000)
        
        self.last_track = None

    def load_cover_image(self, url):
        try:
            response = requests.get(url)
            image_data = BytesIO(response.content)
            pixmap = QPixmap()
            pixmap.loadFromData(image_data.getvalue())
            scaled_pixmap = pixmap.scaled(64, 64, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.cover_label.setPixmap(scaled_pixmap)
        except Exception as e:
            print(f"Fehler beim Laden des Cover-Artworks: {e}")

    def show_notification(self, title, artist, cover_url):
        artist_text = artist if len(artist) < 30 else artist[:27] + "..."
        title_text = title if len(title) < 30 else title[:27] + "..."
        
        self.artist_label.setText(artist_text)
        self.title_label.setText(title_text)
        
        if cover_url:
            self.load_cover_image(cover_url)
        
        self.adjustSize()
        self.setFixedHeight(64)
        
        self.start_show_animation()
        self.hide_timer.start(6000)

    def start_show_animation(self):
        start_pos = QPoint(20, -50)
        end_pos = QPoint(20, 20)
        
        self.show_animation.setStartValue(start_pos)
        self.show_animation.setEndValue(end_pos)
        self.show()
        self.show_animation.start()

    def start_hide_animation(self):
        current_pos = self.pos()
        end_pos = QPoint(current_pos.x(), -50)
        
        self.hide_animation.setStartValue(current_pos)
        self.hide_animation.setEndValue(end_pos)
        self.hide_animation.start()

    def show_current_track(self):
        try:
            current = self.spotify_client.current_user_playing_track()
            if current is not None and current['item'] is not None:
                artists = ", ".join([artist['name'] for artist in current['item']['artists']])
                title = current['item']['name']
                cover_url = current['item']['album']['images'][-1]['url'] if current['item']['album']['images'] else None
                self.show_notification(title, artists, cover_url)
        except Exception as e:
            print(f"Fehler beim Abrufen des aktuellen Tracks: {e}")

    def check_current_track(self):
        try:
            current = self.spotify_client.current_user_playing_track()
            if current is not None and current['item'] is not None:
                track_id = current['item']['id']
                if track_id != self.last_track:
                    self.last_track = track_id
                    self.show_current_track()
        except Exception as e:
            print(f"Fehler beim Abrufen des aktuellen Tracks: {e}")

class RoundedLabel(QLabel):
    def __init__(self):
        super().__init__()

    def setPixmap(self, pixmap):
        rounded_pixmap = self.round_pixmap(pixmap, 10)
        super().setPixmap(rounded_pixmap)

    def round_pixmap(self, pixmap, radius):
        size = pixmap.size()
        mask = QPixmap(size)
        mask.fill(Qt.GlobalColor.transparent)

        painter = QPainter(mask)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(0, 0, size.width(), size.height(), radius, radius)
        painter.fillPath(path, QBrush(Qt.GlobalColor.white))
        painter.end()

        rounded = QPixmap(size)
        rounded.fill(Qt.GlobalColor.transparent)

        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, pixmap)
        painter.end()

        return rounded

def get_spotify_client():
    auth_manager = SpotifyOAuth(
        client_id="Your-Client-ID",
        client_secret="Your-Client-Secret",
        redirect_uri="http://localhost:8888/callback",
        scope="user-read-currently-playing",
        cache_path=cache_path,
        open_browser=True
    )
    
    token_info = auth_manager.cache_handler.get_cached_token()
    
    if not token_info or auth_manager.is_token_expired(token_info):
        auth_manager.get_access_token(None)
    
    return spotipy.Spotify(auth_manager=auth_manager)

def main():
    app = QApplication(sys.argv)
    
    # Initialisiere Spotify-Client
    try:
        spotify_client = get_spotify_client()
    except Exception as e:
        print(f"Fehler bei der Spotify-Authentifizierung: {e}")
        return
    
    # Erstelle das Popup-Fenster
    popup = PopupWindow(spotify_client)
    signals = popup.signals
    
    def on_hotkey():
        signals.show_track.emit()
    
    # Hotkey-Listener in separatem Thread
    def setup_hotkey():
        with keyboard.GlobalHotKeys({
            '<ctrl>+<': on_hotkey
        }) as h:
            h.join()
    
    hotkey_thread = threading.Thread(target=setup_hotkey, daemon=True)
    hotkey_thread.start()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()