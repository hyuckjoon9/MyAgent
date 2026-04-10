from __future__ import annotations

import tkinter as tk
from queue import Empty, Queue
from threading import Thread
from typing import Any

from gui.main_window import MainWindow
from gui.startup import StartupContext, load_startup_context
from gui.tray_controller import TrayController
from core.search_engine import shutdown_search_manager


class SplashScreen:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("MyAgent")
        self.root.geometry("420x220")
        self.root.resizable(False, False)
        self.root.configure(bg="#0b1220")
        self.root.overrideredirect(True)

        self._center()

        frame = tk.Frame(self.root, bg="#0b1220", padx=28, pady=28)
        frame.pack(fill="both", expand=True)

        title = tk.Label(
            frame,
            text="MyAgent",
            font=("Segoe UI", 24, "bold"),
            bg="#0b1220",
            fg="#f8fafc",
        )
        title.pack(anchor="w")

        subtitle = tk.Label(
            frame,
            text="로컬 검색 엔진을 준비하는 중입니다.",
            font=("Segoe UI", 11),
            bg="#0b1220",
            fg="#94a3b8",
        )
        subtitle.pack(anchor="w", pady=(10, 26))

        self.status_var = tk.StringVar(value="초기화 시작...")
        status = tk.Label(
            frame,
            textvariable=self.status_var,
            font=("Segoe UI", 10),
            bg="#0b1220",
            fg="#cbd5e1",
        )
        status.pack(anchor="w")

        progress = tk.Frame(frame, bg="#1f2937", height=8)
        progress.pack(fill="x", pady=(18, 0))

        bar = tk.Frame(progress, bg="#3b82f6", height=8, width=220)
        bar.pack(side="left", fill="y")

    def _center(self) -> None:
        self.root.update_idletasks()
        width = 420
        height = 220
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def set_status(self, text: str) -> None:
        self.status_var.set(text)

    def close(self) -> None:
        self.root.destroy()


def _run_startup() -> StartupContext:
    return load_startup_context()


def main() -> None:
    splash = SplashScreen()
    queue: Queue[dict[str, Any]] = Queue()

    def startup_worker() -> None:
        try:
            context = _run_startup()
            queue.put({"ok": True, "context": context})
        except Exception as exc:
            queue.put({"ok": False, "error": exc})

    Thread(target=startup_worker, daemon=True).start()

    def poll() -> None:
        try:
            event = queue.get_nowait()
        except Empty:
            splash.root.after(80, poll)
            return

        if not event.get("ok"):
            splash.set_status(f"초기화 실패: {event['error']}")
            splash.root.after(1200, splash.close)
            return

        splash.set_status("메인 창을 여는 중입니다...")
        context: StartupContext = event["context"]
        splash.close()
        app: MainWindow | None = None
        tray: TrayController | None = None

        def show_from_tray() -> None:
            if app is not None:
                app.after(0, app.show_window)

        def quit_from_tray() -> None:
            if app is not None:
                app.after(0, app.destroy)

        def notify_hidden() -> None:
            if app is not None:
                app.after(0, lambda: app._set_status("창을 닫아 트레이로 숨김 처리했습니다."))

        app = MainWindow(
            startup_context=context,
            on_hide_to_tray=notify_hidden,
            on_quit_request=quit_from_tray,
        )
        tray = TrayController(on_show=show_from_tray, on_quit=quit_from_tray)
        tray.start()
        try:
            app.mainloop()
        finally:
            if tray is not None:
                tray.stop()
            shutdown_search_manager()

    splash.root.after(120, poll)
    splash.root.mainloop()


if __name__ == "__main__":
    main()
