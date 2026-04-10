from __future__ import annotations

import customtkinter as ctk


class SearchBar(ctk.CTkFrame):
    def __init__(self, master, on_submit) -> None:
        super().__init__(master, fg_color="transparent")
        self._on_submit = on_submit

        self.grid_columnconfigure(0, weight=1)

        self.entry = ctk.CTkEntry(
            self,
            placeholder_text="예: 최근 pdf 파일 3개 찾아줘",
            height=44,
            corner_radius=14,
            fg_color="#111827",
            border_color="#334155",
            text_color="#f8fafc",
            placeholder_text_color="#64748b",
        )
        self.entry.grid(row=0, column=0, sticky="ew", padx=(0, 12))
        self.entry.bind("<Return>", self._handle_submit)

        self.button = ctk.CTkButton(
            self,
            text="검색",
            width=96,
            command=self.submit,
            height=44,
            corner_radius=14,
            fg_color="#2563eb",
            hover_color="#3b82f6",
            text_color="#eff6ff",
        )
        self.button.grid(row=0, column=1, sticky="e")

    def focus_input(self) -> None:
        self.entry.focus_set()
        self.entry.icursor("end")

    def get_query(self) -> str:
        return self.entry.get().strip()

    def set_query(self, text: str) -> None:
        self.entry.delete(0, "end")
        self.entry.insert(0, text)

    def submit(self) -> None:
        self._on_submit(self.get_query())

    def _handle_submit(self, _event) -> str | None:
        self.submit()
        return "break"
