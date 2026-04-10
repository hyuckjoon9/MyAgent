from __future__ import annotations

import ctypes
import time
from pathlib import Path

from core.adapters.native_adapter import (
    MAX_RESULT_LIMIT,
    index_path,
    indexed_entry_to_match,
    resolve_entries_scope,
    sort_matches,
)
from core.env import load_roots
from core.interfaces.search_adapter import SearchAdapter
from core.models.search_types import Match
from core.query_parser import QueryIntent, parse_query
from core.utils.everything_helper import EverythingRuntimeInfo, ensure_everything_runtime


EVERYTHING_REQUEST_FULL_PATH_AND_FILE_NAME = 0x00000004
DB_READY_WAIT_SECONDS = 8.0
DB_READY_POLL_INTERVAL = 0.2


class EverythingAdapter(SearchAdapter):
    engine_name = "everything"
    display_name = "Everything"

    def __init__(self, auto_start: bool = True) -> None:
        self.runtime_info = ensure_everything_runtime(auto_start=auto_start)
        self._dll = self._load_dll(self.runtime_info)
        self._bind_api()

    @staticmethod
    def _load_dll(runtime_info: EverythingRuntimeInfo) -> ctypes.WinDLL:
        if not runtime_info.dll_path:
            raise RuntimeError("Everything DLL 경로를 찾지 못했습니다.")
        try:
            return ctypes.WinDLL(str(runtime_info.dll_path))
        except OSError as exc:
            raise RuntimeError(f"Everything DLL을 로드하지 못했습니다: {runtime_info.dll_path}") from exc

    def _bind_api(self) -> None:
        self._dll.Everything_SetSearchW.argtypes = [ctypes.c_wchar_p]
        self._dll.Everything_SetSearchW.restype = None
        self._dll.Everything_SetRequestFlags.argtypes = [ctypes.c_uint]
        self._dll.Everything_SetRequestFlags.restype = None
        self._dll.Everything_SetMax.argtypes = [ctypes.c_uint]
        self._dll.Everything_SetMax.restype = None
        self._dll.Everything_SetOffset.argtypes = [ctypes.c_uint]
        self._dll.Everything_SetOffset.restype = None
        self._dll.Everything_QueryW.argtypes = [ctypes.c_bool]
        self._dll.Everything_QueryW.restype = ctypes.c_bool
        self._dll.Everything_GetNumResults.argtypes = []
        self._dll.Everything_GetNumResults.restype = ctypes.c_uint
        self._dll.Everything_GetResultFullPathNameW.argtypes = [ctypes.c_uint, ctypes.c_wchar_p, ctypes.c_uint]
        self._dll.Everything_GetResultFullPathNameW.restype = ctypes.c_uint
        self._dll.Everything_GetLastError.argtypes = []
        self._dll.Everything_GetLastError.restype = ctypes.c_uint
        self._dll.Everything_IsDBLoaded.argtypes = []
        self._dll.Everything_IsDBLoaded.restype = ctypes.c_bool
        self._dll.Everything_Reset.argtypes = []
        self._dll.Everything_Reset.restype = None

    def _ensure_ready(self) -> None:
        if not self.runtime_info.is_running:
            raise RuntimeError("Everything 프로세스가 실행 중이 아닙니다.")
        if bool(self._dll.Everything_IsDBLoaded()):
            return

        deadline = time.monotonic() + DB_READY_WAIT_SECONDS
        while time.monotonic() < deadline:
            time.sleep(DB_READY_POLL_INTERVAL)
            if bool(self._dll.Everything_IsDBLoaded()):
                return

        raise RuntimeError("Everything 데이터베이스가 아직 준비되지 않았습니다.")

    def _build_search_expression(self, intent: QueryIntent) -> str:
        tokens: list[str] = []
        if intent.target_kind == "folder":
            tokens.append("folder:")
        elif intent.target_kind == "file":
            tokens.append("file:")
        if intent.extension:
            tokens.append(f"ext:{intent.extension}")
        tokens.extend(intent.keywords)
        return " ".join(tokens)

    def _query_paths(self, expression: str, limit: int) -> list[Path]:
        self._ensure_ready()
        self._dll.Everything_Reset()
        self._dll.Everything_SetSearchW(expression)
        self._dll.Everything_SetRequestFlags(EVERYTHING_REQUEST_FULL_PATH_AND_FILE_NAME)
        self._dll.Everything_SetOffset(0)
        self._dll.Everything_SetMax(max(1, min(limit, MAX_RESULT_LIMIT)))
        if not bool(self._dll.Everything_QueryW(True)):
            error_code = int(self._dll.Everything_GetLastError())
            raise RuntimeError(f"Everything 쿼리에 실패했습니다. error={error_code}")

        count = int(self._dll.Everything_GetNumResults())
        results: list[Path] = []
        for index in range(count):
            buffer = ctypes.create_unicode_buffer(32768)
            self._dll.Everything_GetResultFullPathNameW(index, buffer, len(buffer))
            if buffer.value:
                results.append(Path(buffer.value))
        return results

    def search(self, query: str, limit: int) -> list[Match]:
        intent = parse_query(query)
        return self.search_intent(intent, limit)

    def search_intent(self, intent: QueryIntent, limit: int) -> list[Match]:
        roots = [root.resolve() for root in load_roots()]
        expression = self._build_search_expression(intent)
        raw_paths = self._query_paths(expression, max(100, min(limit * 20, MAX_RESULT_LIMIT)))
        indexed_entries = []
        for path in raw_paths:
            try:
                resolved = path.resolve()
                if not any(root == resolved or root in resolved.parents for root in roots):
                    continue
                stat = resolved.stat()
            except OSError:
                continue
            indexed_entries.append(index_path(resolved, stat.st_mtime, 0 if resolved.is_dir() else stat.st_size))

        scoped_entries = resolve_entries_scope(indexed_entries, intent.location_hint)
        matches: list[Match] = []
        for entry in scoped_entries:
            entry_path = Path(entry.path)
            if intent.action == "compress" and entry.is_dir and entry_path.resolve() in roots:
                continue
            match = indexed_entry_to_match(entry, intent)
            if match is not None:
                matches.append(match)

        sort_matches(matches, intent)
        return matches[: max(1, min(limit, MAX_RESULT_LIMIT))]
