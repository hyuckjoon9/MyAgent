from enum import Enum, auto
from pathlib import Path

from PyQt6.QtCore import QPoint, Qt, pyqtSignal
from PyQt6.QtGui import QCursor, QPixmap
from PyQt6.QtWidgets import QApplication, QLabel, QWidget

from core.config import Config

ASSETS = Path(__file__).parent.parent / "assets"


class CharacterState(Enum):
    IDLE = auto()
    THINKING = auto()
    SPEAKING = auto()


STATE_IMAGE: dict[CharacterState, str] = {
    CharacterState.IDLE: "idle.png",
    CharacterState.THINKING: "thinking.png",
    CharacterState.SPEAKING: "speaking.png",
}

CHAR_SIZE = 180
DRAG_THRESHOLD = 5  # px


class CharacterWindow(QWidget):
    clicked = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self._drag_start: QPoint | None = None
        self._dragging = False
        self._state = CharacterState.IDLE
        self._config = Config()

        self._init_window()
        self._init_label()
        self._restore_or_default_position()

    # ── 초기화 ────────────────────────────────────────────────

    def _init_window(self) -> None:
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(CHAR_SIZE, CHAR_SIZE)
        self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))

    def _init_label(self) -> None:
        self._label = QLabel(self)
        self._label.setGeometry(0, 0, CHAR_SIZE, CHAR_SIZE)
        self._label.setStyleSheet("background: transparent;")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_state(CharacterState.IDLE)

    def _restore_or_default_position(self) -> None:
        saved = self._config.load_position()
        if saved:
            self.move(*saved)
        else:
            self._position_bottom_right()

    def _position_bottom_right(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        available = screen.availableGeometry()
        margin = 20
        x = available.right() - self.width() - margin
        y = available.bottom() - self.height() - margin
        self.move(x, y)

    # ── 상태 전환 ─────────────────────────────────────────────

    def set_state(self, state: CharacterState) -> None:
        self._state = state
        img_path = ASSETS / STATE_IMAGE[state]
        if img_path.exists():
            pixmap = QPixmap(str(img_path)).scaled(
                CHAR_SIZE,
                CHAR_SIZE,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self._label.setPixmap(pixmap)
        else:
            fallback = {
                CharacterState.IDLE: "😊",
                CharacterState.THINKING: "🤔",
                CharacterState.SPEAKING: "💬",
            }
            self._label.setText(
                f'<span style="font-size:48px;">{fallback[state]}</span>'
            )

    # ── 마우스 이벤트 ─────────────────────────────────────────

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.globalPosition().toPoint()
            self._dragging = False
            self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))

    def mouseMoveEvent(self, event) -> None:
        if self._drag_start is None:
            return
        delta = event.globalPosition().toPoint() - self._drag_start
        if not self._dragging and (
            abs(delta.x()) > DRAG_THRESHOLD or abs(delta.y()) > DRAG_THRESHOLD
        ):
            self._dragging = True
        if self._dragging:
            self.move(self.pos() + delta)
            self._drag_start = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if not self._dragging:
                self.clicked.emit()
            else:
                # 드래그 완료 시 위치 저장
                self._config.save_position(self.pos().x(), self.pos().y())
            self._drag_start = None
            self._dragging = False
            self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))

    def closeEvent(self, event) -> None:
        self._config.save_position(self.pos().x(), self.pos().y())
        super().closeEvent(event)
