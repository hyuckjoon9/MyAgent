from __future__ import annotations

import os
import webbrowser

import customtkinter as ctk
try:
    import pyperclip
except ImportError:  # pragma: no cover - optional dependency
    pyperclip = None

from core.viewmodels.result_item import ResultItem


CARD_BG = "#111827"
CARD_HOVER_BG = "#172036"
CARD_SELECTED_BG = "#172554"
CARD_SELECTED_HOVER_BG = "#1d3473"
CARD_BORDER = "#1f2937"
CARD_HOVER_BORDER = "#334155"
CARD_SELECTED_BORDER = "#3b82f6"
ACTION_BUTTON_FG = "#2563eb"
ACTION_BUTTON_HOVER = "#3b82f6"
ACTION_BUTTON_TEXT = "#eff6ff"
EMPTY_TEXT_COLOR = "#64748b"
LOADING_BAR_FG = "#1e293b"
LOADING_BAR_PROGRESS = "#3b82f6"
NOTICE_LINK = "#60a5fa"
LOADING_MESSAGES = [
    "열심히 찾고 있어요! 잠깐만요 🔍",
    "파일들을 하나하나 살펴보는 중이에요 📂",
    "거의 다 찾아가고 있어요! 조금만 기다려주세요 ✨",
    "찾았다! 싶었는데... 조금 더 확인할게요 👀",
    "마지막으로 한 번 더 훑어볼게요 🚀",
    "짜잔~ 곧 결과가 나와요! 🎉",
]


def _truncate_text(text: str, limit: int = 42) -> str:
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3]}..."


class ResultList(ctk.CTkScrollableFrame):
    def __init__(self, master, on_selection_changed=None, on_toast=None) -> None:
        super().__init__(master, corner_radius=18, fg_color="transparent")
        self._on_selection_changed = on_selection_changed
        self._on_toast = on_toast
        self.grid_columnconfigure(0, weight=1)
        self._items: list[ResultItem] = []
        self._selected: dict[str, ctk.BooleanVar] = {}
        self._card_frames: dict[str, ctk.CTkFrame] = {}
        self._hovered_paths: set[str] = set()
        self._empty_label = ctk.CTkLabel(
            self,
            text="",
            anchor="w",
            justify="left",
            text_color=EMPTY_TEXT_COLOR,
        )
        self._notice_frame = ctk.CTkFrame(
            self,
            corner_radius=16,
            fg_color="#0f172a",
            border_width=1,
            border_color="#1e293b",
        )
        self._notice_label = ctk.CTkLabel(
            self._notice_frame,
            text="",
            justify="center",
            text_color="#e2e8f0",
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        self._notice_label.grid(row=0, column=0, padx=20, pady=(16, 6))
        self._notice_link = ctk.CTkButton(
            self._notice_frame,
            text="",
            fg_color="transparent",
            hover=False,
            text_color=NOTICE_LINK,
            font=ctk.CTkFont(size=14, underline=True),
            command=self._open_notice_link,
        )
        self._notice_link.grid(row=1, column=0, padx=20, pady=(0, 14))
        self._notice_link.grid_remove()
        self._notice_frame.grid_columnconfigure(0, weight=1)
        self._loading_frame = ctk.CTkFrame(
            self,
            corner_radius=18,
            fg_color="#0f172a",
            border_width=1,
            border_color="#1e293b",
        )
        self._loading_label = ctk.CTkLabel(
            self._loading_frame,
            text="검색 중...",
            text_color="#e2e8f0",
            font=ctk.CTkFont(size=15, weight="bold"),
        )
        self._loading_label.grid(row=0, column=0, padx=20, pady=(22, 10))
        self._loading_bar = ctk.CTkProgressBar(
            self._loading_frame,
            mode="indeterminate",
            progress_color=LOADING_BAR_PROGRESS,
            fg_color=LOADING_BAR_FG,
            height=10,
            corner_radius=999,
        )
        self._loading_bar.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 22))
        self._loading_frame.grid_columnconfigure(0, weight=1)
        self._rows: list[ctk.CTkFrame] = []
        self._loading_message_index = 0
        self._loading_after_id: str | None = None
        self._notice_url: str | None = None
        self.show_idle_state()

    def set_items(self, items: list[ResultItem]) -> None:
        self._reset_content()
        self._items = items[:]

        for row_index, item in enumerate(items):
            extension = "폴더" if os.path.isdir(item.path) else (os.path.splitext(item.path)[1] or "-")
            card = ctk.CTkFrame(
                self,
                corner_radius=18,
                fg_color=CARD_BG,
                border_width=1,
                border_color=CARD_BORDER,
            )
            card.grid(row=row_index + 1, column=0, sticky="ew", padx=2, pady=(0, 8))
            card.grid_columnconfigure(0, weight=1)
            card.grid_columnconfigure(1, weight=0)

            selected_var = ctk.BooleanVar(value=False)
            self._selected[item.path] = selected_var
            self._card_frames[item.path] = card

            title = ctk.CTkLabel(
                card,
                text=f"{item.index}. {_truncate_text(item.name)}",
                font=ctk.CTkFont(size=15, weight="bold"),
                anchor="w",
                text_color="#f8fafc",
            )
            title.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 4))

            checkbox = ctk.CTkCheckBox(
                card,
                text="선택",
                variable=selected_var,
                onvalue=True,
                offvalue=False,
                width=70,
                text_color="#cbd5e1",
                border_color="#475569",
                hover_color="#2563eb",
                checkmark_color="#f8fafc",
                command=lambda path=item.path: self._on_select_toggle(path),
            )
            checkbox.grid(row=0, column=1, sticky="e", padx=(0, 14), pady=(12, 4))

            meta = ctk.CTkLabel(
                card,
                text=f"수정 {item.modified_at}   크기 {item.size_label}   확장자 {extension}",
                anchor="w",
                text_color="#94a3b8",
            )
            meta.grid(row=1, column=0, sticky="ew", padx=14)
            self._bind_click_toggle(card, item.path)
            self._bind_click_toggle(title, item.path)
            self._bind_click_toggle(meta, item.path)

            toggle_row = ctk.CTkFrame(card, fg_color="transparent")
            toggle_row.grid(row=2, column=0, columnspan=2, sticky="ew", padx=12, pady=(8, 12))
            toggle_row.grid_columnconfigure(2, weight=1)

            path_row = ctk.CTkFrame(toggle_row, fg_color="transparent")
            path_row.grid_columnconfigure(0, weight=1)

            path_label = ctk.CTkLabel(
                path_row,
                text=item.path,
                anchor="w",
                justify="left",
                wraplength=620,
                text_color="#94a3b8",
            )
            path_label.grid(row=0, column=0, sticky="ew")

            copy_button = ctk.CTkButton(
                path_row,
                text="⧉",
                width=28,
                height=28,
                command=lambda path=item.path: self._copy_path(path),
            )
            self._apply_action_button_style(copy_button)
            copy_button.grid(row=0, column=1, sticky="e", padx=(8, 0))

            def open_folder(path=item.path):
                os.startfile(os.path.dirname(path))

            path_button = ctk.CTkButton(
                toggle_row,
                text="경로 보기",
                width=92,
                height=28,
                command=lambda row=path_row: self._toggle_path_row(row),
            )
            self._apply_action_button_style(path_button)
            path_button.grid(row=0, column=0, sticky="w")

            open_folder_button = ctk.CTkButton(
                toggle_row,
                text="폴더 열기",
                width=92,
                height=28,
                command=open_folder,
            )
            self._apply_action_button_style(open_folder_button)
            open_folder_button.grid(row=0, column=1, sticky="w", padx=(8, 0))

            self._bind_hover_state(card, item.path)
            self._bind_hover_state(title, item.path)
            self._bind_hover_state(meta, item.path)
            self._bind_hover_state(toggle_row, item.path)
            self._bind_hover_state(path_row, item.path)
            self._bind_hover_state(path_label, item.path)
            self._bind_hover_state(path_button, item.path)
            self._bind_hover_state(open_folder_button, item.path)
            self._bind_hover_state(copy_button, item.path)

            self._rows.append(card)

    def show_idle_state(self) -> None:
        self._reset_content()

    def show_loading_state(self) -> None:
        self._reset_content()
        self._loading_message_index = 0
        self._notice_label.configure(text=LOADING_MESSAGES[0])
        self._notice_frame.grid(row=0, column=0, sticky="ew", padx=2, pady=(2, 10))
        self._loading_frame.grid(row=1, column=0, sticky="ew", padx=2, pady=2)
        self._loading_bar.start()
        self._schedule_loading_message_rotation()

    def show_empty_state(self, text: str = "검색 결과가 없습니다.") -> None:
        self._reset_content()
        self._empty_label.configure(text=text)
        self._empty_label.grid(row=1, column=0, sticky="ew", padx=8, pady=8)

    def show_notice(self, text: str, url: str | None = None, link_text: str | None = None) -> None:
        self._reset_content()
        self._notice_url = url
        self._notice_label.configure(text=text)
        self._notice_frame.grid(row=0, column=0, sticky="ew", padx=2, pady=2)
        if url:
            self._notice_link.configure(text=link_text or url)
            self._notice_link.grid()
        else:
            self._notice_link.grid_remove()

    def get_selected_items(self) -> list[ResultItem]:
        return [item for item in self._items if self._selected.get(item.path) and self._selected[item.path].get()]

    def get_items(self) -> list[ResultItem]:
        return self._items[:]

    def clear_selection(self) -> None:
        for value in self._selected.values():
            value.set(False)
        self._emit_selection_changed()

    def _copy_path(self, path: str) -> None:
        if pyperclip is not None:
            pyperclip.copy(path)
        else:
            self.clipboard_clear()
            self.clipboard_append(path)
        self.update_idletasks()
        if self._on_toast is not None:
            self._on_toast("경로가 복사되었습니다.")

    def _apply_action_button_style(self, button: ctk.CTkButton) -> None:
        button.configure(
            fg_color=ACTION_BUTTON_FG,
            hover_color=ACTION_BUTTON_HOVER,
            text_color=ACTION_BUTTON_TEXT,
            corner_radius=10,
        )

    def _bind_click_toggle(self, widget, path: str) -> None:
        widget.bind("<Button-1>", lambda _event, item_path=path: self._toggle_selection(item_path), add="+")

    def _bind_hover_state(self, widget, path: str) -> None:
        widget.bind("<Enter>", lambda _event, item_path=path: self._set_hover_state(item_path, True), add="+")
        widget.bind("<Leave>", lambda _event, item_path=path: self.after(1, lambda: self._handle_hover_leave(item_path)), add="+")

    def _toggle_selection(self, path: str) -> None:
        selected = self._selected.get(path)
        if selected is None:
            return
        selected.set(not selected.get())
        self._on_select_toggle(path)

    def _set_hover_state(self, path: str, hovered: bool) -> None:
        if hovered:
            self._hovered_paths.add(path)
        else:
            self._hovered_paths.discard(path)
        self._apply_card_state(path)

    def _handle_hover_leave(self, path: str) -> None:
        card = self._card_frames.get(path)
        if card is None:
            return
        pointer_x, pointer_y = self.winfo_pointerxy()
        within_x = card.winfo_rootx() <= pointer_x <= card.winfo_rootx() + card.winfo_width()
        within_y = card.winfo_rooty() <= pointer_y <= card.winfo_rooty() + card.winfo_height()
        if within_x and within_y:
            return
        self._set_hover_state(path, False)

    def _toggle_path_row(self, path_row: ctk.CTkFrame) -> None:
        if path_row.winfo_manager():
            path_row.grid_forget()
            return
        path_row.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(8, 0))

    def _on_select_toggle(self, path: str) -> None:
        self._apply_card_state(path)
        self._emit_selection_changed()

    def _apply_card_state(self, path: str) -> None:
        card = self._card_frames.get(path)
        selected = self._selected.get(path)
        if card is None or selected is None:
            return
        hovered = path in self._hovered_paths
        if selected.get():
            fg_color = CARD_SELECTED_HOVER_BG if hovered else CARD_SELECTED_BG
            border_color = CARD_SELECTED_BORDER
        else:
            fg_color = CARD_HOVER_BG if hovered else CARD_BG
            border_color = CARD_HOVER_BORDER if hovered else CARD_BORDER
        card.configure(fg_color=fg_color, border_color=border_color)

    def _emit_selection_changed(self) -> None:
        for path in self._card_frames:
            self._apply_card_state(path)
        if self._on_selection_changed is not None:
            self._on_selection_changed(len(self.get_selected_items()))

    def _reset_content(self) -> None:
        self._items = []
        self._selected = {}
        self._card_frames = {}
        self._hovered_paths.clear()
        if self._loading_after_id is not None:
            self.after_cancel(self._loading_after_id)
            self._loading_after_id = None
        for row in self._rows:
            row.destroy()
        self._rows.clear()
        self._empty_label.grid_forget()
        self._notice_frame.grid_forget()
        self._notice_link.grid_remove()
        self._notice_url = None
        self._loading_bar.stop()
        self._loading_frame.grid_forget()

    def _schedule_loading_message_rotation(self) -> None:
        if self._loading_after_id is not None:
            self.after_cancel(self._loading_after_id)
        self._loading_after_id = self.after(3000, self._rotate_loading_message)

    def _rotate_loading_message(self) -> None:
        self._loading_message_index = (self._loading_message_index + 1) % len(LOADING_MESSAGES)
        self._notice_label.configure(text=LOADING_MESSAGES[self._loading_message_index])
        self._schedule_loading_message_rotation()

    def _open_notice_link(self) -> None:
        if not self._notice_url:
            return
        webbrowser.open(self._notice_url)
