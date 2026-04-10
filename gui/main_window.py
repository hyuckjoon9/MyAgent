from __future__ import annotations

from queue import Empty, Queue
from threading import Thread
from typing import Any
from pathlib import Path

import customtkinter as ctk

from apps.local.session import SessionState
from core.env import load_project_env, set_runtime_roots
from core.search_engine import get_search_availability, get_search_manager
from core.services.action_service import ActionService
from core.services.query_service import QueryService
from core.services.root_service import RootService
from core.viewmodels.action_result import ActionResult
from core.viewmodels.drive_item import DriveItem
from core.viewmodels.query_result import QueryExecutionResult
from core.viewmodels.result_item import ResultItem
from gui.startup import StartupContext
from gui.widgets.result_list import ResultList
from gui.widgets.search_bar import SearchBar


PRIMARY_BUTTON_FG = "#2563eb"
PRIMARY_BUTTON_HOVER = "#3b82f6"
PRIMARY_BUTTON_DISABLED = "#475569"
PRIMARY_BUTTON_TEXT = "#eff6ff"
ROOT_PANEL_BG = "#0f172a"
ROOT_PANEL_BORDER = "#1e293b"
STOP_BUTTON_FG = "#b91c1c"
STOP_BUTTON_HOVER = "#dc2626"
STOP_BUTTON_DISABLED = "#3f3f46"
STOP_BUTTON_TEXT = "#fff1f2"


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
        self._root_service = RootService()
        self._session = SessionState()
        self._task_queue: Queue[dict[str, Any]] = Queue()
        self._busy = False
        self._startup_context = startup_context
        self._on_hide_to_tray = on_hide_to_tray
        self._on_quit_request = on_quit_request
        self._status_clear_after_id: str | None = None
        self._available_drives: list[DriveItem] = []
        self._drive_vars: dict[str, ctk.BooleanVar] = {}
        self._task_sequence = 0
        self._active_task_id: int | None = None
        self._active_task_kind: str | None = None
        self._cancelled_task_ids: set[int] = set()
        self._search_available = True

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
        panel.grid_columnconfigure(5, weight=1)

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

        self.stop_button = ctk.CTkButton(
            panel,
            text="■",
            width=44,
            command=self._cancel_active_task,
        )
        self._apply_stop_button_style(self.stop_button)
        self.stop_button.grid(row=0, column=4, padx=8, pady=14)

        self.selection_label = ctk.CTkLabel(panel, text="선택 0개", anchor="w", text_color="#cbd5e1")
        self.selection_label.grid(row=0, column=5, padx=(16, 16), pady=14, sticky="w")

        self.root_panel = ctk.CTkFrame(
            panel,
            fg_color=ROOT_PANEL_BG,
            corner_radius=14,
            border_width=1,
            border_color=ROOT_PANEL_BORDER,
        )
        self.root_panel.grid(row=1, column=0, columnspan=6, sticky="ew", padx=16, pady=(0, 14))
        self.root_panel.grid_columnconfigure(1, weight=1)

        root_title = ctk.CTkLabel(
            self.root_panel,
            text="검색 드라이브",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#f8fafc",
            anchor="w",
        )
        root_title.grid(row=0, column=0, sticky="w", padx=14, pady=(12, 4))

        self.root_summary_label = ctk.CTkLabel(
            self.root_panel,
            text="드라이브를 먼저 체크하세요.",
            text_color="#94a3b8",
            anchor="w",
        )
        self.root_summary_label.grid(row=0, column=1, sticky="w", padx=(4, 14), pady=(12, 4))

        self.root_options_frame = ctk.CTkFrame(self.root_panel, fg_color="transparent")
        self.root_options_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=12, pady=(0, 12))

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
        self._load_drive_options()
        self._refresh_engine_status()
        self._apply_search_availability()
        self.focus_force()
        self.search_bar.focus_input()
        if self._search_available:
            self.result_list.show_idle_state()
        self._update_action_buttons(0)
        self.stop_button.configure(state="disabled", fg_color=STOP_BUTTON_DISABLED)
        if self._startup_context and self._startup_context.notices:
            self._set_status("\n".join(self._startup_context.notices))

    def _refresh_engine_status(self) -> None:
        engine_name = get_search_manager().engine_name()
        self.engine_label.configure(text=f"|  엔진: {engine_name}")

    def _apply_search_availability(self) -> None:
        availability = get_search_availability()
        self._search_available = availability.search_enabled
        button_state = "normal" if availability.search_enabled and not self._busy else "disabled"
        self.search_bar.button.configure(state=button_state)
        if not availability.search_enabled:
            self.result_list.show_notice(
                availability.guidance_message or "",
                url=availability.guidance_url,
                link_text=availability.guidance_url,
            )

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

    def _apply_stop_button_style(self, button: ctk.CTkButton) -> None:
        button.configure(
            fg_color=STOP_BUTTON_DISABLED,
            hover_color=STOP_BUTTON_HOVER,
            text_color=STOP_BUTTON_TEXT,
            text_color_disabled="#cbd5e1",
            corner_radius=12,
            font=ctk.CTkFont(size=16, weight="bold"),
        )

    def _set_busy(self, busy: bool, status_text: str | None = None) -> None:
        self._busy = busy
        search_state = "disabled" if busy else "normal"
        self.search_bar.entry.configure(state=search_state)
        button_state = "disabled" if busy or not self._search_available else "normal"
        self.search_bar.button.configure(state=button_state)
        self.refresh_button.configure(state="normal")
        self.roots_button.configure(state="normal")
        self._set_drive_controls_state("disabled" if busy else "normal")
        self._update_action_buttons(len(self._get_selected_items()))
        self.stop_button.configure(
            state="normal" if busy else "disabled",
            fg_color=STOP_BUTTON_FG if busy else STOP_BUTTON_DISABLED,
        )
        if status_text is not None:
            self._set_status(status_text)

    def _start_task(self, kind: str, status_text: str, func, *args) -> None:
        if self._busy:
            self._set_status("이전 작업이 아직 진행 중입니다.")
            return
        if kind == "query":
            self.result_list.show_loading_state()
            self._update_selection_count(0)
        self._task_sequence += 1
        task_id = self._task_sequence
        self._active_task_id = task_id
        self._active_task_kind = kind
        self._set_busy(True, status_text)

        def runner() -> None:
            try:
                payload = func(*args)
                self._task_queue.put({"task_id": task_id, "kind": kind, "ok": True, "payload": payload})
            except Exception as exc:
                self._task_queue.put({"task_id": task_id, "kind": kind, "ok": False, "error": exc})

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
        task_id = event.get("task_id")
        if task_id in self._cancelled_task_ids:
            self._cancelled_task_ids.discard(task_id)
            return
        if self._active_task_id is not None and task_id != self._active_task_id:
            return

        self._active_task_id = None
        self._active_task_kind = None
        self._set_busy(False)
        if not event.get("ok"):
            error = event.get("error")
            if isinstance(error, RuntimeError):
                self._set_status(f"설정 오류: {error}")
            else:
                self._set_status(f"작업 실패: {error}")
            self.after(10, self.search_bar.focus_input)
            return

        kind = event["kind"]
        payload = event["payload"]
        if kind == "query":
            self._handle_query_result(payload)
            self.after(10, self.search_bar.focus_input)
            return
        if kind == "open":
            self._handle_action_result(payload)
            self.after(10, self.search_bar.focus_input)
            return
        if kind == "compress":
            self._handle_action_result(payload)
            self.after(10, self.search_bar.focus_input)
            return
        if kind == "refresh":
            self._handle_refresh_result(payload)
            self.after(10, self.search_bar.focus_input)
            return

    def _cancel_active_task(self) -> None:
        if self._active_task_id is None or not self._busy:
            return
        self._cancelled_task_ids.add(self._active_task_id)
        kind = self._active_task_kind
        self._active_task_id = None
        self._active_task_kind = None
        self._set_busy(False)
        if kind == "query":
            self.result_list.show_idle_state()
            self._update_selection_count(0)
        self._set_status("진행 중인 작업을 취소했습니다.")
        self.after(10, self.search_bar.focus_input)

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
        if not self._ensure_roots_selected():
            return
        self._start_task("refresh", "검색 인덱스를 새로고침하는 중입니다...", self._action_service.refresh_index)

    def _show_roots(self) -> None:
        roots = self._get_selected_roots()
        if not roots:
            self._set_status("드라이브를 먼저 체크하세요.")
            return
        joined = " | ".join(str(root) for root in roots)
        self._set_status(f"검색 루트: {joined}")

    def _run_query(self, query: str) -> None:
        if not self._search_available:
            availability = get_search_availability()
            self.result_list.show_notice(
                availability.guidance_message or "",
                url=availability.guidance_url,
                link_text=availability.guidance_url,
            )
            return
        if not query:
            self._set_status("검색어를 입력하세요.")
            self.result_list.show_idle_state()
            self._update_selection_count(0)
            return
        if not self._ensure_roots_selected():
            return
        self._start_task("query", f"검색 중: {query}", self._query_service.execute, query, self._session)

    def _handle_query_result(self, result: QueryExecutionResult) -> None:
        self._refresh_engine_status()
        self._apply_search_availability()

        if result.message and result.selection_target is None:
            self._set_status(result.message)
            if result.items:
                self.result_list.set_items(result.items)
            else:
                self.result_list.show_empty_state()
            self._update_selection_count(0)
            return

        if result.items:
            self.result_list.set_items(result.items)
        else:
            self.result_list.show_empty_state()
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
        self._apply_search_availability()

    def _handle_refresh_result(self, result: ActionResult) -> None:
        self._set_status(result.message)
        self._refresh_engine_status()
        self._apply_search_availability()
        query = self.search_bar.get_query()
        if query:
            self._run_query(query)

    def _load_drive_options(self) -> None:
        self._available_drives = self._root_service.list_available_drives()
        self._drive_vars = {}
        for widget in self.root_options_frame.winfo_children():
            widget.destroy()

        if not self._available_drives:
            empty_label = ctk.CTkLabel(
                self.root_options_frame,
                text="사용 가능한 드라이브를 찾지 못했습니다.",
                text_color="#94a3b8",
                anchor="w",
            )
            empty_label.grid(row=0, column=0, sticky="w", padx=4, pady=4)
            set_runtime_roots([])
            self._session.set_selected_roots([])
            return

        for index, drive in enumerate(self._available_drives):
            variable = ctk.BooleanVar(value=False)
            self._drive_vars[str(drive.root)] = variable
            checkbox = ctk.CTkCheckBox(
                self.root_options_frame,
                text=drive.label,
                variable=variable,
                onvalue=True,
                offvalue=False,
                text_color="#e2e8f0",
                border_color="#475569",
                hover_color="#2563eb",
                checkmark_color="#f8fafc",
                command=self._handle_drive_selection_changed,
            )
            checkbox.grid(row=0, column=index, sticky="w", padx=(4, 12), pady=4)

        self._handle_drive_selection_changed()

    def _set_drive_controls_state(self, state: str) -> None:
        for widget in self.root_options_frame.winfo_children():
            if isinstance(widget, ctk.CTkCheckBox):
                widget.configure(state=state)

    def _get_selected_roots(self) -> list[Path]:
        selected: list[Path] = []
        for drive in self._available_drives:
            variable = self._drive_vars.get(str(drive.root))
            if variable is not None and variable.get():
                try:
                    selected.append(drive.root.resolve())
                except OSError:
                    continue
        return selected

    def _handle_drive_selection_changed(self) -> None:
        roots = self._get_selected_roots()
        set_runtime_roots(roots)
        self._session.set_selected_roots(roots)
        count = len(roots)
        if count == 0:
            self.root_summary_label.configure(text="드라이브를 먼저 체크하세요.")
            if self._search_available:
                self.result_list.show_idle_state()
            self._session.remember_matches([])
            self._update_selection_count(0)
            return
        joined = ", ".join(root.drive or str(root) for root in roots)
        self.root_summary_label.configure(text=f"{count}개 선택됨: {joined}")

    def _ensure_roots_selected(self) -> bool:
        if self._get_selected_roots():
            return True
        self._set_status("드라이브를 먼저 체크하세요.")
        if self._search_available:
            self.result_list.show_idle_state()
        self._session.remember_matches([])
        self._update_selection_count(0)
        return False
