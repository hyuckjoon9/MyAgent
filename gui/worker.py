from PyQt6.QtCore import QThread, pyqtSignal


class AssistantWorker(QThread):
    response_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, backend, query: str) -> None:
        super().__init__()
        self._backend = backend
        self._query = query

    def run(self) -> None:
        try:
            result = self._backend.query(self._query)
            self.response_ready.emit(result)
        except Exception as e:
            self.error_occurred.emit(str(e))
