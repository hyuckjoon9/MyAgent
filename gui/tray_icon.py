from pathlib import Path

from PyQt6.QtGui import QIcon, QPixmap, QColor
from PyQt6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

ASSETS = Path(__file__).parent.parent / "assets"


def _make_fallback_icon() -> QIcon:
    """assets/tray_icon.png 없을 때 단색 아이콘 생성."""
    pixmap = QPixmap(16, 16)
    pixmap.fill(QColor("#6C63FF"))
    return QIcon(pixmap)


class TrayIcon(QSystemTrayIcon):
    def __init__(self, character_window, parent=None) -> None:
        icon_path = ASSETS / "tray_icon.png"
        icon = QIcon(str(icon_path)) if icon_path.exists() else _make_fallback_icon()
        super().__init__(icon, parent)

        self._character = character_window
        self._build_menu()
        self.activated.connect(self._on_activated)
        self.setToolTip("MyAgent")
        self.show()

    def _build_menu(self) -> None:
        menu = QMenu()

        toggle_action = menu.addAction("보이기 / 숨기기")
        toggle_action.triggered.connect(self._toggle_character)

        menu.addSeparator()

        quit_action = menu.addAction("종료")
        quit_action.triggered.connect(QApplication.quit)

        self.setContextMenu(menu)

    def _toggle_character(self) -> None:
        if self._character.isVisible():
            self._character.hide()
        else:
            self._character.show()

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._toggle_character()
