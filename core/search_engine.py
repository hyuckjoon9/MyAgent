from __future__ import annotations

import os
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from core.adapters.es_adapter import EsAdapter
from core.adapters.native_adapter import MAX_RESULT_LIMIT, NativeAdapter
from core.adapters.windows_search_adapter import WindowsSearchAdapter
from core.interfaces.search_adapter import SearchAdapter
from core.models.search_types import Match
from core.query_parser import QueryIntent, parse_query
from core.utils.everything_helper import (
    EVERYTHING_INSTALL_URL,
    ensure_everything_runtime,
    terminate_everything_process,
)


AUTO_OPEN_MARGIN = 1.2
AUTO_OPEN_SCORE = 4.2
RESULT_LIMIT = 10
RISKY_EXTENSIONS = {".exe", ".bat", ".cmd", ".ps1", ".vbs", ".msi"}
EVERYTHING_MISSING_MESSAGE = (
    "Everything이 설치되어 있지 않습니다.\n"
    "아래 링크에서 설치 후 프로그램을 다시 시작해주세요.\n"
    f"{EVERYTHING_INSTALL_URL}"
)


@dataclass
class SearchAvailability:
    search_enabled: bool
    guidance_message: str | None = None
    guidance_url: str | None = None


class SearchManager:
    def __init__(self) -> None:
        self.mode = os.getenv("ASSISTANT_SEARCH_MODE", "auto").strip().lower() or "auto"
        self.everything_auto_start = os.getenv("EVERYTHING_AUTO_START", "true").strip().lower() not in {"0", "false", "no"}
        self.notice_messages: list[str] = []
        self._availability = SearchAvailability(search_enabled=True)
        self._spawned_everything_pid: int | None = None
        self.adapter: SearchAdapter = self._select_adapter()

    def _build_everything_install_notice(self) -> list[str]:
        return [
            "Assistant> Everything 설치를 찾지 못했습니다.",
            f"Assistant> 설치 링크: {EVERYTHING_INSTALL_URL}",
        ]

    def _build_native_notice(self, detail: str = "") -> list[str]:
        messages = ["Assistant> Everything 연결에 실패해 로컬 인덱스 엔진으로 전환합니다."]
        if detail:
            messages.append(f"Assistant> 상세: {detail}")
        return messages

    def _build_windows_notice(self, detail: str = "") -> list[str]:
        messages = ["Assistant> Everything 연결에 실패해 Windows Search 엔진으로 전환합니다."]
        if detail:
            messages.append(f"Assistant> 상세: {detail}")
        return messages

    def _select_adapter(self) -> SearchAdapter:
        runtime_info = ensure_everything_runtime(auto_start=self.everything_auto_start)
        if not runtime_info.installed:
            self._availability = SearchAvailability(
                search_enabled=False,
                guidance_message=EVERYTHING_MISSING_MESSAGE,
                guidance_url=EVERYTHING_INSTALL_URL,
            )
            self.notice_messages.extend(self._build_everything_install_notice())
            return NativeAdapter()

        self._availability = SearchAvailability(search_enabled=True)
        if runtime_info.was_started:
            self._spawned_everything_pid = runtime_info.spawn_pid

        try:
            adapter = EsAdapter(auto_start=False, runtime_info=runtime_info)
            engine_message = "Assistant> 검색 엔진 모드: Everything"
            if runtime_info.was_started:
                engine_message += " (자동 실행됨)"
            self.notice_messages.append(engine_message)
            return adapter
        except Exception as exc:
            self.notice_messages.extend(self._build_windows_notice(str(exc)))

        try:
            adapter = WindowsSearchAdapter()
            return adapter
        except Exception as exc:
            self.notice_messages.extend(self._build_native_notice(str(exc)))
            return NativeAdapter()

    def _swap_to_fallback(self, detail: str) -> SearchAdapter:
        try:
            adapter = WindowsSearchAdapter()
            self.adapter = adapter
            self.notice_messages.extend(self._build_windows_notice(detail))
            return adapter
        except Exception as exc:
            native_adapter = NativeAdapter()
            self.adapter = native_adapter
            joined = detail if not detail else f"{detail}; windows search: {exc}"
            self.notice_messages.extend(self._build_native_notice(joined))
            return native_adapter

    def get_and_clear_notices(self) -> list[str]:
        messages = self.notice_messages[:]
        self.notice_messages.clear()
        return messages

    def get_availability(self) -> SearchAvailability:
        return self._availability

    def search_intent(self, intent: QueryIntent, limit: int, refresh_index: bool = False) -> list[Match]:
        if not self._availability.search_enabled:
            raise RuntimeError("Everything이 설치되어 있지 않아 검색할 수 없습니다.")

        bounded_limit = max(1, min(limit, MAX_RESULT_LIMIT))
        try:
            if refresh_index:
                self.adapter.rebuild_index()
            if hasattr(self.adapter, "search_intent"):
                if isinstance(self.adapter, NativeAdapter):
                    return self.adapter.search_intent(intent, bounded_limit, refresh_index=False)
                return self.adapter.search_intent(intent, bounded_limit)
            return self.adapter.search(intent.raw, bounded_limit)
        except Exception as exc:
            if isinstance(self.adapter, (EsAdapter, WindowsSearchAdapter)):
                fallback_adapter = self._swap_to_fallback(str(exc))
                if refresh_index:
                    fallback_adapter.rebuild_index()
                if isinstance(fallback_adapter, NativeAdapter):
                    return fallback_adapter.search_intent(intent, bounded_limit, refresh_index=False)
                return fallback_adapter.search_intent(intent, bounded_limit)  # type: ignore[attr-defined]
            raise

    def rebuild_index(self) -> int:
        return self.adapter.rebuild_index()

    def engine_name(self) -> str:
        if not self._availability.search_enabled:
            return "Everything 미설치"
        display_name = getattr(self.adapter, "display_name", None)
        if display_name:
            return display_name
        if isinstance(self.adapter, NativeAdapter):
            return "로컬 인덱스"
        return getattr(self.adapter, "engine_name", "unknown")

    def shutdown(self) -> None:
        if self._spawned_everything_pid is None:
            return
        terminate_everything_process(self._spawned_everything_pid)
        self._spawned_everything_pid = None


_MANAGER: SearchManager | None = None


def get_search_manager() -> SearchManager:
    global _MANAGER
    if _MANAGER is None:
        _MANAGER = SearchManager()
    return _MANAGER


def shutdown_search_manager() -> None:
    global _MANAGER
    if _MANAGER is None:
        return
    _MANAGER.shutdown()


def get_engine_notices() -> list[str]:
    return get_search_manager().get_and_clear_notices()


def get_search_availability() -> SearchAvailability:
    return get_search_manager().get_availability()


def search(intent: QueryIntent, limit: int = RESULT_LIMIT, refresh_index: bool = False) -> list[Match]:
    return get_search_manager().search_intent(intent, limit=limit, refresh_index=refresh_index)


def _match_to_dict(match: Match) -> dict[str, object]:
    return {
        "path": str(match.path),
        "kind": match.kind,
        "score": match.score,
        "modified_ts": match.modified_ts,
        "size": match.size,
        "reason": match.reason,
    }


def search_files(query: str, limit: int = RESULT_LIMIT) -> dict[str, object]:
    intent = parse_query(query)
    manager = get_search_manager()
    return {
        "query": query,
        "engine": manager.engine_name(),
        "results": [_match_to_dict(item) for item in manager.search_intent(intent, limit=limit)],
    }


def list_recent_files(limit: int = RESULT_LIMIT, extension: str | None = None) -> dict[str, object]:
    recent_query = "recent file"
    if extension:
        recent_query = f"recent {extension} file"
    matches = search(parse_query(recent_query), limit=limit)
    matches.sort(key=lambda item: item.modified_ts, reverse=True)
    return {"results": [_match_to_dict(item) for item in matches[: max(1, min(limit, MAX_RESULT_LIMIT))]]}


def open_path(path: str | Path) -> dict[str, object]:
    target = Path(path)
    if not target.exists():
        return {"ok": False, "error": "Path not found", "path": str(path)}
    if target.is_file() and target.suffix.lower() in RISKY_EXTENSIONS:
        return {"ok": False, "error": f"Blocked risky file type: {target.suffix.lower()}", "path": str(target)}

    os.startfile(str(target))  # type: ignore[attr-defined]
    return {"ok": True, "opened": str(target)}


def _safe_archive_name(base_dir: Path, stem: str) -> Path:
    candidate = base_dir / f"{stem}.zip"
    index = 1
    while candidate.exists():
        candidate = base_dir / f"{stem} ({index}).zip"
        index += 1
    return candidate


def _default_archive_stem(paths: list[Path]) -> str:
    now = datetime.now().strftime("%Y%m%d_%H%M%S")
    if len(paths) == 1:
        return f"{paths[0].stem}_{now}"
    if all(path.parent == paths[0].parent for path in paths):
        return f"{paths[0].parent.name}_bundle_{now}"
    return f"archive_{now}"


def _common_output_dir(paths: list[Path]) -> Path:
    if len(paths) == 1:
        path = paths[0]
        return path.parent if path.is_file() else path.parent
    common_path = Path(os.path.commonpath([str(path.parent if path.is_file() else path.parent) for path in paths]))
    return common_path


def create_zip(paths: list[str | Path]) -> dict[str, object]:
    from core.env import load_roots

    targets = [Path(path) for path in paths]
    if not targets:
        return {"ok": False, "error": "No paths selected"}
    missing = [str(path) for path in targets if not path.exists()]
    if missing:
        return {"ok": False, "error": f"Missing paths: {', '.join(missing)}"}
    roots = {root.resolve() for root in load_roots()}
    blocked = [str(path) for path in targets if path.resolve() in roots]
    if blocked:
        return {"ok": False, "error": f"Cannot compress configured root folder: {', '.join(blocked)}"}

    archive_dir = _common_output_dir(targets)
    archive_path = _safe_archive_name(archive_dir, _default_archive_stem(targets))

    with zipfile.ZipFile(archive_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for target in targets:
            if target.is_file():
                zf.write(target, arcname=target.name)
                continue
            for child in target.rglob("*"):
                if child.is_file():
                    zf.write(child, arcname=str(Path(target.name) / child.relative_to(target)))

    return {"ok": True, "archive": str(archive_path), "count": len(targets)}


def should_auto_open(matches: list[Match]) -> tuple[bool, str]:
    if not matches:
        return False, "열 결과가 없습니다."
    if len(matches) == 1:
        return True, "후보가 1개라 바로 열 수 있습니다."
    first = matches[0]
    second = matches[1]
    if first.score >= AUTO_OPEN_SCORE and (first.score - second.score) >= AUTO_OPEN_MARGIN:
        return True, "1위 결과의 점수가 충분히 높고 2위와 차이가 큽니다."
    return False, "상위 결과가 비슷해서 확인이 필요합니다."


def rebuild_index() -> int:
    return get_search_manager().rebuild_index()
