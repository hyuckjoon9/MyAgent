from __future__ import annotations

from queue import Empty, Queue
from threading import Thread
from typing import Any

import customtkinter as ctk

from apps.local.session import SessionState
from core.env import load_project_env
from core.search_engine import get_search_manager
from core.services.action_service import ActionService
from core.services.query_service import QueryService
from core.viewmodels.action_result import ActionResult
from core.viewmodels.query_result import QueryExecutionResult
from core.viewmodels.result_item import ResultItem
from gui.startup import StartupContext
from gui.widgets.result_list import ResultList
from gui.widgets.search_bar import SearchBar


PRIMARY_BUTTON_FG = "#2563eb"
PRIMARY_BUTTON_HOVER = "#3b82f6"
PRIMARY_BUTTON_DISABLED = "#475569"
PRIMARY_BUTTON_TEXT = "#eff6ff"


class MainWindow(ctk.CTk):
    def __init__(
        self,
        startup_context: StartupContext | None = None,
        on_hide_to_tray=None,
        on_quit_request=None,
    ) -> None:
        super().__init__()
        load_project_env()

        self._query_service = QueryService()
        self._action_service = ActionService()
        self._session = SessionState()
        self._task_queue: Queue[dict[str, Any]] = Queue()
        self._busy = False
        self._startup_context = startup_context
        self._on_hide_to_tray = on_hide_to_tray
        self._on_quit_request = on_quit_request
        self._status_clear_after_id: str | None = None

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.title("MyAgent")
        self.geometry("980x720")
        self.minsize(860, 620)
        self.configure(fg_color="#0b1220")

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        self._build_header()
        self._build_actions()
        self._build_results()

        self.protocol("WM_DELETE_WINDOW", self._handle_window_close)
        self.after(50, self._post_init)
        self.after(100, self._poll_task_queue)

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(24, 10))
        header.grid_columnconfigure(1, weight=1)

        title = ctk.CTkLabel(
            header,
            text="MyAgent Local Search",
            font=ctk.CTkFont(size=28, weight="bold"),
            anchor="w",
            text_color="#f8fafc",
        )
        title.grid(row=0, column=0, sticky="w")

        self.engine_label = ctk.CTkLabel(
            header,
            text="|  엔진: -",
            anchor="w",
            font=ctk.CTkFont(size=13),
            text_color="#94a3b8",
        )
        self.engine_label.grid(row=0, column=1, sticky="w", padx=(12, 0), pady=(4, 0))

        self.search_bar = SearchBar(header, on_submit=self._run_query)
        self.search_bar.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(18, 0))

    def _build_actions(self) -> None:
        panel = ctk.CTkFrame(self, fg_color="#111827", corner_radius=18, border_width=1, border_color="#1f2937")
        panel.grid(row=1, column=0, sticky="ew", padx=24, pady=(0, 10))

        self.open_button = ctk.CTkButton(
            panel,
            text="열기",
            width=96,
            command=self._open_selected,
        )
        self._apply_primary_button_style(self.open_button)
        self.open_button.grid(row=0, column=0, padx=(16, 8), pady=14)

        self.compress_button = ctk.CTkButton(
            panel,
            text="압축",
            width=96,
            command=self._compress_selected,
        )
        self._apply_primary_button_style(self.compress_button)
        self.compress_button.grid(row=0, column=1, padx=8, pady=14)

        self.refresh_button = ctk.CTkButton(
            panel,
            text="새로고침",
            width=96,
            command=self._refresh_index,
        )
        self._apply_primary_button_style(self.refresh_button)
        self.refresh_button.grid(row=0, column=2, padx=8, pady=14)

        self.roots_button = ctk.CTkButton(
            panel,
            text="경로 보기",
            width=110,
            command=self._show_roots,
        )
        self._apply_primary_button_style(self.roots_button)
        self.roots_button.grid(row=0, column=3, padx=8, pady=14)

        self.selection_label = ctk.CTkLabel(panel, text="선택 0개", anchor="w", text_color="#cbd5e1")
        self.selection_label.grid(row=0, column=4, padx=(16, 16), pady=14, sticky="w")

    def _build_results(self) -> None:
        self.result_list = ResultList(
            self,
            on_selection_changed=self._update_selection_count,
            on_toast=self._set_status,
        )
        self.result_list.grid(row=2, column=0, sticky="nsew", padx=24, pady=(0, 20))

        self.toast_frame = ctk.CTkFrame(
            self,
            fg_color="#111827",
            corner_radius=14,
            border_width=1,
            border_color="#1f2937",
        )
        self.status_label = ctk.CTkLabel(
            self.toast_frame,
            text="검색어를 입력하세요.",
            anchor="w",
            justify="left",
            wraplength=700,
            text_color="#e2e8f0",
        )
        self.status_label.grid(row=0, column=0, sticky="ew", padx=16, pady=12)
        self.toast_frame.place_forget()

    def _post_init(self) -> None:
        self._refresh_engine_status()
        self.focus_force()
        self._update_action_buttons(0)

    def _refresh_engine_status(self) -> None:
        engine_name = self._startup_context.engine_name if self._startup_context else get_search_manager().engine_name()
        self.engine_label.configure(text=f"|  엔진: {engine_name}")

    def show_window(self) -> None:
        self.deiconify()
        self.after(10, self.lift)
        self.after(20, self.focus_force)

    def hide_window(self) -> None:
        self.withdraw()

    def request_quit(self) -> None:
        if self._on_quit_request is not None:
            self._on_quit_request()
            return
        self.destroy()

    def _handle_window_close(self) -> None:
        self.hide_window()
        if self._on_hide_to_tray is not None:
            self._on_hide_to_tray()
        else:
            self._set_status("트레이로 숨김 처리되었습니다.")

    def _set_status(self, text: str) -> None:
        if self._status_clear_after_id is not None:
            self.after_cancel(self._status_clear_after_id)
            self._status_clear_after_id = None
        self.status_label.configure(text=text)
        if text:
            self.toast_frame.place(relx=0.5, rely=1.0, x=0, y=-22, anchor="s")
            self.toast_frame.lift()
            self._status_clear_after_id = self.after(3000, self._clear_status)
        else:
            self.toast_frame.place_forget()

    def _clear_status(self) -> None:
        self._status_clear_after_id = None
        self.status_label.configure(text="")
        self.toast_frame.place_forget()

    def _apply_primary_button_style(self, button: ctk.CTkButton) -> None:
        button.configure(
            fg_color=PRIMARY_BUTTON_FG,
            hover_color=PRIMARY_BUTTON_HOVER,
            text_color=PRIMARY_BUTTON_TEXT,
            text_color_disabled="#cbd5e1",
            corner_radius=12,
        )

    def _set_busy(self, busy: bool, status_text: str | None = None) -> None:
        self._busy = busy
        search_state = "disabled" if busy else "normal"
        self.search_bar.entry.configure(state=search_state)
        self.search_bar.button.configure(state=search_state)
        self.refresh_button.configure(state="normal")
        self.roots_button.configure(state="normal")
        self._update_action_buttons(len(self._get_selected_items()))
        if status_text is not None:
            self._set_status(status_text)

    def _start_task(self, kind: str, status_text: str, func, *args) -> None:
        if self._busy:
            self._set_status("이전 작업이 아직 진행 중입니다.")
            return
        self._set_busy(True, status_text)

        def runner() -> None:
            try:
                payload = func(*args)
                self._task_queue.put({"kind": kind, "ok": True, "payload": payload})
            except Exception as exc:
                self._task_queue.put({"kind": kind, "ok": False, "error": exc})

        Thread(target=runner, daemon=True).start()

    def _poll_task_queue(self) -> None:
        try:
            while True:
                event = self._task_queue.get_nowait()
                self._handle_task_event(event)
        except Empty:
            pass
        self.after(100, self._poll_task_queue)

    def _handle_task_event(self, event: dict[str, Any]) -> None:
        self._set_busy(False)
        if not event.get("ok"):
            error = event.get("error")
            if isinstance(error, RuntimeError):
                self._set_status(f"설정 오류: {error}")
            else:
                self._set_status(f"작업 실패: {error}")
            return

        kind = event["kind"]
        payload = event["payload"]
        if kind == "query":
            self._handle_query_result(payload)
            return
        if kind == "open":
            self._handle_action_result(payload)
            return
        if kind == "compress":
            self._handle_action_result(payload)
            return
        if kind == "refresh":
            self._handle_refresh_result(payload)
            return

    def _get_selected_items(self) -> list[ResultItem]:
        selected = self.result_list.get_selected_items()
        return selected

    def _update_selection_count(self, count: int) -> None:
        self.selection_label.configure(text=f"선택 {count}개")
        self._update_action_buttons(count)

    def _update_action_buttons(self, selected_count: int) -> None:
        is_selected = selected_count > 0 and not self._busy
        state = "normal" if is_selected else "disabled"
        fg_color = PRIMARY_BUTTON_FG if is_selected else PRIMARY_BUTTON_DISABLED
        self.open_button.configure(state=state, fg_color=fg_color)
        self.compress_button.configure(state=state, fg_color=fg_color)

    def _resolve_action_items(self) -> list[ResultItem]:
        return self._get_selected_items()

    def _open_selected(self) -> None:
        items = self._resolve_action_items()
        if not items:
            self._set_status("열 항목이 없습니다.")
            return
        self._start_task("open", "선택한 항목을 여는 중입니다...", self._action_service.open_matches, [item.match for item in items])

    def _compress_selected(self) -> None:
        items = self._resolve_action_items()
        if not items:
            self._set_status("압축할 항목이 없습니다.")
            return
        self._start_task(
            "compress",
            "선택한 항목을 압축하는 중입니다...",
            self._action_service.compress_matches,
            [item.match for item in items],
        )

    def _refresh_index(self) -> None:
        self._start_task("refresh", "검색 인덱스를 새로고침하는 중입니다...", self._action_service.refresh_index)

    def _show_roots(self) -> None:
        try:
            roots = self._action_service.list_roots()
        except RuntimeError as exc:
            self._set_status(f"설정 오류: {exc}")
            return
        joined = " | ".join(str(root) for root in roots)
        self._set_status(f"검색 루트: {joined}")

    def _run_query(self, query: str) -> None:
        if not query:
            self._set_status("검색어를 입력하세요.")
            self.result_list.set_items([])
            self._update_selection_count(0)
            return
        self._start_task("query", f"검색 중: {query}", self._query_service.execute, query, self._session)

    def _handle_query_result(self, result: QueryExecutionResult) -> None:
        self._refresh_engine_status()

        if result.message and result.selection_target is None:
            self._set_status(result.message)
            self.result_list.set_items(result.items)
            self._update_selection_count(0)
            return

        self.result_list.set_items(result.items)
        self._update_selection_count(0)

        if result.selection_target is not None:
            action_name = "열기" if result.intent.action == "open" else "압축"
            self._set_status(f"후속 명령 실행: {result.selection_target.path.name} ({action_name})")
            if result.intent.action == "open":
                self._start_task(
                    "open",
                    f"후속 명령으로 여는 중: {result.selection_target.path.name}",
                    self._action_service.open_match,
                    result.selection_target,
                )
            elif result.intent.action == "compress":
                self._start_task(
                    "compress",
                    f"후속 명령으로 압축하는 중: {result.selection_target.path.name}",
                    self._action_service.compress_matches,
                    [result.selection_target],
                )
            return

        if not result.items:
            self._set_status("결과를 찾지 못했습니다.")
            return

        self._set_status(f"{len(result.items)}개 결과를 표시합니다.")

    def _handle_action_result(self, result: ActionResult) -> None:
        self._set_status(result.message)
        self._refresh_engine_status()

    def _handle_refresh_result(self, result: ActionResult) -> None:
        self._set_status(result.message)
        self._refresh_engine_status()
        query = self.search_bar.get_query()
        if query:
            self._run_query(query)
