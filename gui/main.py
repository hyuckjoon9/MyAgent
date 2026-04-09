import signal
import sys
from pathlib import Path

from dotenv import load_dotenv
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from core.backend import create_backend
from gui.bubble_window import BubbleWindow
from gui.character_window import CharacterState, CharacterWindow
from gui.tray_icon import TrayIcon
from gui.worker import AssistantWorker


class App:
    def __init__(self) -> None:
        self._backend = create_backend()
        self._worker: AssistantWorker | None = None

        self._character = CharacterWindow()
        self._bubble = BubbleWindow()

        self._character.clicked.connect(self._on_character_clicked)
        self._bubble.submitted.connect(self._on_query_submitted)

        self._tray = TrayIcon(self._character)
        self._character.show()

    # ── 캐릭터 클릭 ──────────────────────────────────────────

    def _on_character_clicked(self) -> None:
        if self._bubble.isVisible():
            self._bubble.hide()
        else:
            self._bubble.move_near_character(
                self._character.pos(),
                (self._character.width(), self._character.height()),
            )
            self._bubble.show()
            self._bubble.activateWindow()

    # ── 쿼리 처리 ─────────────────────────────────────────────

    def _on_query_submitted(self, text: str) -> None:
        if self._worker and self._worker.isRunning():
            return  # 이전 요청 진행 중이면 무시

        self._bubble.show_thinking()
        self._character.set_state(CharacterState.THINKING)

        self._worker = AssistantWorker(self._backend, text)
        self._worker.response_ready.connect(self._on_response)
        self._worker.error_occurred.connect(self._on_error)
        self._worker.finished.connect(self._worker.deleteLater)
        self._worker.finished.connect(self._clear_worker)
        self._worker.start()

    def _clear_worker(self) -> None:
        self._worker = None

    def _on_response(self, text: str) -> None:
        self._character.set_state(CharacterState.SPEAKING)
        self._bubble.show_response(text)

    def _on_error(self, msg: str) -> None:
        self._character.set_state(CharacterState.IDLE)
        self._bubble.show_error(msg)


def main() -> None:
    load_dotenv(Path(__file__).parent.parent / ".env")

    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # 다크모드 무관하게 라이트 테마 고정
    app.setQuitOnLastWindowClosed(False)

    # Ctrl+C 처리: Qt 이벤트 루프가 SIGINT를 막는 문제 해결
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    timer = QTimer()
    timer.start(500)  # 0.5초마다 Python으로 제어권 반환해서 시그널 처리
    timer.timeout.connect(lambda: None)

    _app = App()  # noqa: F841

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
