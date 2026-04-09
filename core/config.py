from PyQt6.QtCore import QSettings


_ORG = "MyAgent"
_APP = "FloatingAssistant"


class Config:
    def __init__(self) -> None:
        self._s = QSettings(_ORG, _APP)

    # ── 창 위치 ───────────────────────────────────────────────

    def save_position(self, x: int, y: int) -> None:
        self._s.setValue("window/x", x)
        self._s.setValue("window/y", y)

    def load_position(self) -> tuple[int, int] | None:
        x = self._s.value("window/x")
        y = self._s.value("window/y")
        if x is not None and y is not None:
            return int(x), int(y)
        return None
