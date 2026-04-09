from PyQt6.QtCore import Qt, QPoint, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

BUBBLE_W = 300
BUBBLE_H = 220
TAIL_H = 14
RADIUS = 14
BG_COLOR = QColor("#FFFFFF")
BORDER_COLOR = QColor("#D0D0D0")


class BubbleWindow(QWidget):
    submitted = pyqtSignal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(BUBBLE_W, BUBBLE_H + TAIL_H)
        self._build_ui()

    # ── UI 구성 ───────────────────────────────────────────────

    def _build_ui(self) -> None:
        container = QWidget(self)
        container.setGeometry(0, 0, BUBBLE_W, BUBBLE_H)
        container.setStyleSheet(
            "QWidget { background: white; color: #222222; }"
        )

        layout = QVBoxLayout(container)
        layout.setContentsMargins(14, 12, 14, 10)
        layout.setSpacing(8)

        # 응답 텍스트 — 스크롤 가능
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            "QScrollArea { border: none; background: white; }"
            "QScrollBar:vertical { width: 6px; background: #F0F0F0; }"
            "QScrollBar::handle:vertical { background: #C0C0C0; border-radius: 3px; }"
        )

        self._response_label = QLabel("무엇을 도와드릴까요?")
        self._response_label.setWordWrap(True)
        self._response_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._response_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._response_label.setStyleSheet(
            "QLabel { color: #222222; font-size: 13px; background: white; padding: 2px; }"
        )
        scroll.setWidget(self._response_label)
        layout.addWidget(scroll)

        # 입력 행
        input_row = QHBoxLayout()
        input_row.setSpacing(6)

        self._input = QLineEdit()
        self._input.setPlaceholderText("여기에 입력하세요...")
        self._input.setStyleSheet(
            "QLineEdit {"
            "  border: 1px solid #D0D0D0; border-radius: 8px;"
            "  padding: 5px 10px; font-size: 12px;"
            "  background: #F8F8F8; color: #222222;"
            "}"
            "QLineEdit:focus { border-color: #6C63FF; background: white; }"
        )
        self._input.returnPressed.connect(self._on_submit)

        self._send_btn = QPushButton("▶")
        self._send_btn.setFixedSize(32, 32)
        self._send_btn.setStyleSheet(
            "QPushButton { background: #6C63FF; color: white; border: none; border-radius: 8px; font-size: 12px; }"
            "QPushButton:hover { background: #574fd6; }"
            "QPushButton:disabled { background: #C0C0C0; }"
        )
        self._send_btn.clicked.connect(self._on_submit)

        input_row.addWidget(self._input)
        input_row.addWidget(self._send_btn)
        layout.addLayout(input_row)

    # ── 말풍선 드로잉 ─────────────────────────────────────────

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        path = QPainterPath()
        path.addRoundedRect(0, 0, BUBBLE_W, BUBBLE_H, RADIUS, RADIUS)

        tail_x = BUBBLE_W - 36
        path.moveTo(tail_x, BUBBLE_H)
        path.lineTo(tail_x + 10, BUBBLE_H + TAIL_H)
        path.lineTo(tail_x + 24, BUBBLE_H)
        path.closeSubpath()

        painter.setPen(QPen(BORDER_COLOR, 1))
        painter.setBrush(BG_COLOR)
        painter.drawPath(path)

    # ── 위치 조정 ─────────────────────────────────────────────

    def move_near_character(self, char_pos: QPoint, char_size: tuple[int, int]) -> None:
        x = char_pos.x() + char_size[0] - BUBBLE_W
        y = char_pos.y() - BUBBLE_H - TAIL_H + 4
        self.move(x, y)

    # ── 상태 전환 ─────────────────────────────────────────────

    def show_thinking(self) -> None:
        self._response_label.setText("생각 중...")
        self._response_label.setStyleSheet(
            "QLabel { color: #999999; font-size: 13px; font-style: italic; background: white; padding: 2px; }"
        )
        self._input.setEnabled(False)
        self._send_btn.setEnabled(False)

    def show_response(self, text: str) -> None:
        self._response_label.setText(text)
        self._response_label.setStyleSheet(
            "QLabel { color: #222222; font-size: 13px; background: white; padding: 2px; }"
        )
        self._input.setEnabled(True)
        self._send_btn.setEnabled(True)
        self._input.setFocus()

    def show_error(self, msg: str) -> None:
        self._response_label.setText(f"오류: {msg}")
        self._response_label.setStyleSheet(
            "QLabel { color: #E53935; font-size: 13px; background: white; padding: 2px; }"
        )
        self._input.setEnabled(True)
        self._send_btn.setEnabled(True)

    # ── 이벤트 ───────────────────────────────────────────────

    def _on_submit(self) -> None:
        text = self._input.text().strip()
        if not text:
            return
        self._input.clear()
        self.submitted.emit(text)

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(event)
