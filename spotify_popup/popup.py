"""Das eigentliche Now-Playing-Popup.

Alles wird selbst gezeichnet (statt QLabel/QFrame). Das hat zwei Gruende:
  * die Progress-Bar kann so sauber als unterer Rand *innerhalb* der abgerundeten
    Ecken liegen, ohne dass sich am restlichen Widget irgendetwas aendert
  * fuer die "Pop"-Animationen laesst sich der komplette Inhalt skalieren
    (Kind-Widgets wuerden bei einer Painter-Transformation nicht mitskalieren)

Mit ausgeschalteten Experimental-Features sieht und verhaelt sich das Popup
exakt wie die alte Version: Slide von oben nach (20, 20), 300 ms, Cubic.
"""

from __future__ import annotations

import threading
import time
from typing import Optional

import requests
from PyQt6.QtCore import (
    QEasingCurve,
    QObject,
    QParallelAnimationGroup,
    QPoint,
    QPropertyAnimation,
    QRectF,
    Qt,
    QTimer,
    pyqtProperty,
    pyqtSignal,
)
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPixmap
from PyQt6.QtWidgets import QWidget

from .config import Settings
from .spotify_client import Track

# --- Optik: exakt die Masse aus dem urspruenglichen Skript ------------------
# Container: 64 px hoch (so hoch wie das Cover), Ecken rundum 10 px.
# Innenabstaende im Original: Layout-Rand rechts 12, Text-Layout rechts 8,
# Abstand Cover<->Text 8. Mehr ist da nicht - kein Streifen unter dem Cover.
COVER_SIZE = 64
CARD_HEIGHT = 64
CORNER_RADIUS = 10
PROGRESS_HEIGHT = 3        # die "unteren 2-3 Pixel", NUR wenn eingeschaltet
SPACING = 8
RIGHT_MARGIN = 20          # 12 (Layout) + 8 (Text-Layout)
MAX_TEXT_WIDTH = 250
BG_COLOR = QColor("#181818")
GREEN = QColor("#1DB954")
WHITE = QColor("#FFFFFF")

# Puffer rund um die Karte, damit Overshoot-/Scale-Animationen nicht abgeschnitten werden
WINDOW_PADDING = 24


class _CoverLoader(QObject):
    """Laedt Cover-Bilder im Hintergrund (frueher blockierte das den UI-Thread)."""

    loaded = pyqtSignal(str, bytes)

    def __init__(self) -> None:
        super().__init__()
        self._inflight: set[str] = set()
        self._lock = threading.Lock()

    def fetch(self, url: str) -> None:
        with self._lock:
            if url in self._inflight:
                return
            self._inflight.add(url)

        def worker() -> None:
            data = b""
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    data = response.content
            except requests.RequestException:
                data = b""
            finally:
                with self._lock:
                    self._inflight.discard(url)
            self.loaded.emit(url, data)

        threading.Thread(target=worker, daemon=True).start()


class PopupWindow(QWidget):
    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings

        self._card_scale = 1.0
        self._card_width = 320
        self._artist = ""
        self._title = ""
        self._cover: Optional[QPixmap] = None
        self._cover_cache: dict[str, QPixmap] = {}
        self._pending_cover_url: Optional[str] = None

        self._progress = 0.0
        self._progress_ms = 0
        self._duration_ms = 1
        self._playing = False
        self._progress_ref = time.monotonic()

        self._font_artist = QFont("Segoe UI", 10)
        self._font_title = QFont("Segoe UI", 14)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self._cover_loader = _CoverLoader()
        self._cover_loader.loaded.connect(self._on_cover_loaded)

        self.hide_timer = QTimer(self)
        self.hide_timer.setSingleShot(True)
        self.hide_timer.timeout.connect(self.start_hide_animation)

        self.progress_timer = QTimer(self)
        self.progress_timer.setInterval(100)
        self.progress_timer.timeout.connect(self._tick_progress)

        self._anim_in: Optional[QParallelAnimationGroup] = None
        self._anim_out: Optional[QParallelAnimationGroup] = None

    # ------------------------------------------------------------------
    # Property fuer die Scale-Animation
    # ------------------------------------------------------------------
    def _get_card_scale(self) -> float:
        return self._card_scale

    def _set_card_scale(self, value: float) -> None:
        self._card_scale = float(value)
        self.update()

    cardScale = pyqtProperty(float, fget=_get_card_scale, fset=_set_card_scale)

    # ------------------------------------------------------------------
    # Inhalte
    # ------------------------------------------------------------------
    def _shorten(self, text: str) -> str:
        return text if len(text) < 30 else text[:27] + "..."

    def set_track(self, track: Track) -> None:
        self._artist = self._shorten(track.artists)
        self._title = self._shorten(track.title)
        self.update_playback(track)

        metrics_artist = QFontMetrics(self._font_artist)
        metrics_title = QFontMetrics(self._font_title)
        text_width = max(
            metrics_artist.horizontalAdvance(self._artist),
            metrics_title.horizontalAdvance(self._title),
        )
        text_width = min(text_width, MAX_TEXT_WIDTH)
        self._card_width = COVER_SIZE + SPACING + text_width + RIGHT_MARGIN

        self._cover = None
        self._pending_cover_url = track.cover_url
        if track.cover_url:
            cached = self._cover_cache.get(track.cover_url)
            if cached is not None:
                self._cover = cached
            else:
                self._cover_loader.fetch(track.cover_url)

        self.setFixedSize(self._card_width + 2 * WINDOW_PADDING, CARD_HEIGHT + 2 * WINDOW_PADDING)
        self.update()

    def update_playback(self, track: Track) -> None:
        """Nur Fortschritt/Play-State aktualisieren (wird bei jedem Poll aufgerufen)."""
        self._progress_ms = track.progress_ms
        self._duration_ms = max(1, track.duration_ms)
        self._playing = track.is_playing
        self._progress_ref = time.monotonic()
        self._recalc_progress()

    def _recalc_progress(self) -> None:
        elapsed = (time.monotonic() - self._progress_ref) * 1000 if self._playing else 0
        value = (self._progress_ms + elapsed) / self._duration_ms
        self._progress = max(0.0, min(1.0, value))

    def _tick_progress(self) -> None:
        if not self.settings.experimental_progress_bar:
            return
        previous = self._progress
        self._recalc_progress()
        if abs(previous - self._progress) * self._card_width > 0.5:
            self.update()

    def _on_cover_loaded(self, url: str, data: bytes) -> None:
        if not data:
            return
        pixmap = QPixmap()
        if not pixmap.loadFromData(data):
            return
        # Auf Displays mit Skalierung (125 %, 150 %) muss das Bild in Geraetepixeln
        # skaliert werden, sonst sieht das Cover matschig aus.
        ratio = max(1.0, self.devicePixelRatioF())
        edge = int(round(COVER_SIZE * ratio))
        scaled = pixmap.scaled(
            edge,
            edge,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        rounded = self._round_pixmap(scaled, int(round(CORNER_RADIUS * ratio)))
        rounded.setDevicePixelRatio(ratio)
        if len(self._cover_cache) > 40:
            self._cover_cache.clear()
        self._cover_cache[url] = rounded
        if url == self._pending_cover_url:
            self._cover = rounded
            self.update()

    @staticmethod
    def _round_pixmap(pixmap: QPixmap, radius: int) -> QPixmap:
        rounded = QPixmap(pixmap.size())
        rounded.fill(Qt.GlobalColor.transparent)
        path = QPainterPath()
        path.addRoundedRect(QRectF(0, 0, pixmap.width(), pixmap.height()), radius, radius)
        painter = QPainter(rounded)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, pixmap)
        painter.end()
        return rounded

    # ------------------------------------------------------------------
    # Zeichnen
    # ------------------------------------------------------------------
    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
            | QPainter.RenderHint.TextAntialiasing
        )

        card_w, card_h = self._card_width, CARD_HEIGHT
        painter.translate(self.width() / 2, self.height() / 2)
        painter.scale(self._card_scale, self._card_scale)
        painter.translate(-card_w / 2, -card_h / 2)

        card_rect = QRectF(0, 0, card_w, card_h)
        card_path = QPainterPath()
        card_path.addRoundedRect(card_rect, CORNER_RADIUS, CORNER_RADIUS)

        painter.fillPath(card_path, BG_COLOR)

        painter.save()
        painter.setClipPath(card_path)
        if self._cover is not None:
            painter.drawPixmap(0, 0, COVER_SIZE, COVER_SIZE, self._cover)
        if self.settings.experimental_progress_bar and self._progress > 0:
            # Die Bar liegt INNERHALB des Clip-Pfads -> sie uebernimmt automatisch
            # den Corner-Radius der unteren Ecken und waechst von links nach rechts.
            bar = QRectF(0, card_h - PROGRESS_HEIGHT, card_w * self._progress, PROGRESS_HEIGHT)
            painter.fillRect(bar, GREEN)
        painter.restore()

        text_x = COVER_SIZE + SPACING
        text_w = card_w - text_x - RIGHT_MARGIN
        metrics_artist = QFontMetrics(self._font_artist)
        metrics_title = QFontMetrics(self._font_title)
        block_h = metrics_artist.height() + metrics_title.height()
        top = (CARD_HEIGHT - block_h) / 2

        painter.setFont(self._font_artist)
        painter.setPen(WHITE)
        painter.drawText(
            QRectF(text_x, top, text_w, metrics_artist.height()),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            metrics_artist.elidedText(self._artist, Qt.TextElideMode.ElideRight, int(text_w)),
        )

        painter.setFont(self._font_title)
        painter.setPen(GREEN)
        painter.drawText(
            QRectF(text_x, top + metrics_artist.height(), text_w, metrics_title.height()),
            int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter),
            metrics_title.elidedText(self._title, Qt.TextElideMode.ElideRight, int(text_w)),
        )
        painter.end()

    # ------------------------------------------------------------------
    # Positionen / Animationen
    # ------------------------------------------------------------------
    def _target_pos(self) -> QPoint:
        return QPoint(
            self.settings.margin_x - WINDOW_PADDING,
            self.settings.margin_y - WINDOW_PADDING,
        )

    def _offscreen_pos(self) -> QPoint:
        return QPoint(self._target_pos().x(), -(self.height() + 10))

    def _stop_animations(self) -> None:
        for group in (self._anim_in, self._anim_out):
            if group is not None:
                group.stop()

    def show_popup(self) -> None:
        self._stop_animations()
        self.progress_timer.start()

        mode = self.settings.effective_animation_mode
        duration = max(80, int(self.settings.animation_duration_ms))
        target = self._target_pos()

        group = QParallelAnimationGroup(self)

        if mode == "pop":
            self.move(target)
            self._card_scale = 0.86
            self.setWindowOpacity(0.0)
            group.addAnimation(self._scale_anim(0.86, 1.0, duration, QEasingCurve.Type.OutBack))
            group.addAnimation(self._opacity_anim(0.0, 1.0, int(duration * 0.7)))
        else:
            self._card_scale = 1.0
            self.setWindowOpacity(1.0)
            curve = {
                "classic": QEasingCurve.Type.OutCubic,
                "smooth": QEasingCurve.Type.OutQuint,
                "bounce": QEasingCurve.Type.OutBack,
                "slide_pop": QEasingCurve.Type.OutQuint,
            }[mode]
            slide_duration = {
                "classic": duration,
                "smooth": int(duration * 1.5),
                "bounce": int(duration * 1.7),
                "slide_pop": int(duration * 1.4),
            }[mode]
            slide = QPropertyAnimation(self, b"pos", self)
            slide.setDuration(slide_duration)
            slide.setEasingCurve(curve)
            slide.setStartValue(self._offscreen_pos())
            slide.setEndValue(target)
            group.addAnimation(slide)

            if mode == "slide_pop":
                self._card_scale = 0.92
                group.addAnimation(
                    self._scale_anim(0.92, 1.0, int(duration * 1.6), QEasingCurve.Type.OutBack)
                )
                group.addAnimation(self._opacity_anim(0.4, 1.0, int(duration * 0.8)))

        self._anim_in = group
        self.show()
        self.raise_()
        group.start()
        self.hide_timer.start(max(1000, int(self.settings.display_duration_ms)))

    def refresh_visible(self) -> None:
        """Neuer Track, waehrend das Popup schon steht: nur Inhalt tauschen, Timer neu."""
        self.update()
        self.hide_timer.start(max(1000, int(self.settings.display_duration_ms)))

    def start_hide_animation(self) -> None:
        if not self.isVisible():
            return
        self._stop_animations()

        mode = self.settings.effective_animation_mode
        duration = max(80, int(self.settings.animation_duration_ms))
        group = QParallelAnimationGroup(self)

        if mode == "pop":
            group.addAnimation(
                self._scale_anim(self._card_scale, 0.9, int(duration * 0.8), QEasingCurve.Type.InCubic)
            )
            group.addAnimation(self._opacity_anim(1.0, 0.0, int(duration * 0.8)))
        else:
            curve = {
                "classic": QEasingCurve.Type.InCubic,
                "smooth": QEasingCurve.Type.InQuart,
                "bounce": QEasingCurve.Type.InBack,
                "slide_pop": QEasingCurve.Type.InQuart,
            }[mode]
            slide_duration = {
                "classic": duration,
                "smooth": duration,
                "bounce": int(duration * 1.2),
                "slide_pop": duration,
            }[mode]
            slide = QPropertyAnimation(self, b"pos", self)
            slide.setDuration(slide_duration)
            slide.setEasingCurve(curve)
            slide.setStartValue(self.pos())
            slide.setEndValue(self._offscreen_pos())
            group.addAnimation(slide)
            if mode == "slide_pop":
                group.addAnimation(self._opacity_anim(1.0, 0.0, duration))

        group.finished.connect(self._after_hide)
        self._anim_out = group
        group.start()

    def _after_hide(self) -> None:
        self.hide()
        self.progress_timer.stop()
        self.setWindowOpacity(1.0)
        self._card_scale = 1.0

    def _scale_anim(self, start: float, end: float, duration: int, curve) -> QPropertyAnimation:
        anim = QPropertyAnimation(self, b"cardScale", self)
        anim.setDuration(duration)
        anim.setEasingCurve(curve)
        anim.setStartValue(start)
        anim.setEndValue(end)
        return anim

    def _opacity_anim(self, start: float, end: float, duration: int) -> QPropertyAnimation:
        anim = QPropertyAnimation(self, b"windowOpacity", self)
        anim.setDuration(max(60, duration))
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.setStartValue(start)
        anim.setEndValue(end)
        return anim
