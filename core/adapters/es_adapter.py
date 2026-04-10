from __future__ import annotations

import subprocess
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
from core.utils.everything_helper import EverythingRuntimeInfo, ensure_everything_runtime, find_es_exe


ES_QUERY_TIMEOUT_MS = 10000
ES_READY_RETRY_COUNT = 2
ES_READY_RETRY_DELAY = 1.0


class EsAdapter(SearchAdapter):
    engine_name = "everything"

    display_name = "Everything"

    def __init__(self, auto_start: bool = True, runtime_info: EverythingRuntimeInfo | None = None) -> None:
        self._auto_start = auto_start
        self.runtime_info = runtime_info or ensure_everything_runtime(auto_start=auto_start)
        self.es_exe = self.runtime_info.es_exe_path or find_es_exe()
        if self.es_exe is None:
            raise RuntimeError("es.exe 경로를 찾지 못했습니다.")
        self._ensure_ready()

    def _ensure_ready(self) -> None:
        if not self.runtime_info.is_running or not self.runtime_info.ipc_ready:
            raise RuntimeError("Everything 프로세스가 실행 중이 아닙니다.")
        self._ensure_ipc_ready()

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

    def _run_es(self, *args: str, timeout_seconds: int | None = None) -> subprocess.CompletedProcess[str]:
        command = [
            str(self.es_exe),
            *args,
        ]
        try:
            return subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
                timeout=timeout_seconds or max(5, (ES_QUERY_TIMEOUT_MS // 1000) + 5),
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise RuntimeError(f"es.exe 실행에 실패했습니다: {exc}") from exc

    def _start_everything_for_es(self) -> bool:
        exe_path = self.runtime_info.exe_path
        if exe_path is None:
            return False
        try:
            subprocess.Popen(
                [str(exe_path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=str(exe_path.parent),
            )
        except OSError:
            return False
        return True

    def _ensure_ipc_ready(self) -> None:
        last_error: str | None = None
        for attempt in range(ES_READY_RETRY_COUNT + 1):
            result = self._run_es("-n", "1", timeout_seconds=5)
            if result.returncode == 0:
                return
            last_error = result.stderr.strip() or result.stdout.strip() or f"exit={result.returncode}"
            if "IPC window not found" not in last_error:
                break
            if attempt >= ES_READY_RETRY_COUNT:
                break
            if self._auto_start:
                self._start_everything_for_es()
            time.sleep(ES_READY_RETRY_DELAY)
            self.runtime_info = ensure_everything_runtime(auto_start=False)

        raise RuntimeError(f"es.exe 질의에 실패했습니다: {last_error or 'unknown error'}")

    def _query_paths(self, expression: str, limit: int) -> list[Path]:
        self._ensure_ready()
        result = self._run_es(
            "-timeout",
            str(ES_QUERY_TIMEOUT_MS),
            "-n",
            str(max(1, min(limit, MAX_RESULT_LIMIT))),
            *( [expression] if expression else [] ),
        )
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or f"exit={result.returncode}"
            raise RuntimeError(f"es.exe 질의에 실패했습니다: {detail}")

        return [Path(line.strip()) for line in result.stdout.splitlines() if line.strip()]

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
