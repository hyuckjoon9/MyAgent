from __future__ import annotations

import os
import zipfile
from datetime import datetime
from pathlib import Path

from core.adapters.everything_adapter import EverythingAdapter
from core.adapters.native_adapter import MAX_RESULT_LIMIT, NativeAdapter
from core.interfaces.search_adapter import SearchAdapter
from core.models.search_types import Match
from core.query_parser import QueryIntent, parse_query
from core.utils.everything_helper import EVERYTHING_INSTALL_URL


AUTO_OPEN_MARGIN = 1.2
AUTO_OPEN_SCORE = 4.2
RESULT_LIMIT = 10
RISKY_EXTENSIONS = {".exe", ".bat", ".cmd", ".ps1", ".vbs", ".msi"}


class SearchManager:
    def __init__(self) -> None:
        self.mode = os.getenv("ASSISTANT_SEARCH_MODE", "auto").strip().lower() or "auto"
        self.everything_auto_start = os.getenv("EVERYTHING_AUTO_START", "true").strip().lower() not in {"0", "false", "no"}
        self.notice_messages: list[str] = []
        self.adapter: SearchAdapter = self._select_adapter()

    def _build_fallback_notice(self, detail: str = "") -> list[str]:
        messages = [
            "Assistant> 초고속 검색 엔진을 찾을 수 없어 기본 모드로 전환합니다.",
            f"Assistant> Everything 설치: {EVERYTHING_INSTALL_URL}",
        ]
        if detail:
            messages.append(f"Assistant> 상세: {detail}")
        return messages

    def _use_native(self, detail: str = "") -> SearchAdapter:
        self.notice_messages.extend(self._build_fallback_notice(detail))
        return NativeAdapter()

    def _select_adapter(self) -> SearchAdapter:
        if self.mode == "native":
            self.notice_messages.append("Assistant> 검색 엔진 모드: native 강제 모드로 실행합니다.")
            return NativeAdapter()

        try:
            adapter = EverythingAdapter(auto_start=self.everything_auto_start)
            if not adapter.runtime_info.is_running:
                return self._use_native(adapter.runtime_info.status_message)
            engine_message = "Assistant> 검색 엔진 모드: Everything"
            if adapter.runtime_info.was_started:
                engine_message += " (자동 실행됨)"
            self.notice_messages.append(engine_message)
            return adapter
        except Exception as exc:
            if self.mode == "everything":
                self.notice_messages.append("Assistant> 검색 엔진 모드: everything 강제 요청이 있었지만 안정성을 위해 native로 전환합니다.")
            return self._use_native(str(exc))

    def _swap_to_native(self, detail: str) -> NativeAdapter:
        native_adapter = NativeAdapter()
        self.adapter = native_adapter
        self.notice_messages.extend(self._build_fallback_notice(detail))
        return native_adapter

    def get_and_clear_notices(self) -> list[str]:
        messages = self.notice_messages[:]
        self.notice_messages.clear()
        return messages

    def search_intent(self, intent: QueryIntent, limit: int, refresh_index: bool = False) -> list[Match]:
        bounded_limit = max(1, min(limit, MAX_RESULT_LIMIT))
        try:
            if refresh_index:
                self.adapter.rebuild_index()
            if isinstance(self.adapter, NativeAdapter):
                return self.adapter.search_intent(intent, bounded_limit, refresh_index=False)
            if isinstance(self.adapter, EverythingAdapter):
                return self.adapter.search_intent(intent, bounded_limit)
            return self.adapter.search(intent.raw, bounded_limit)
        except Exception as exc:
            if isinstance(self.adapter, EverythingAdapter):
                native_adapter = self._swap_to_native(str(exc))
                if refresh_index:
                    native_adapter.rebuild_index()
                return native_adapter.search_intent(intent, bounded_limit, refresh_index=False)
            raise

    def rebuild_index(self) -> int:
        return self.adapter.rebuild_index()

    def engine_name(self) -> str:
        return self.adapter.engine_name


_MANAGER: SearchManager | None = None


def get_search_manager() -> SearchManager:
    global _MANAGER
    if _MANAGER is None:
        _MANAGER = SearchManager()
    return _MANAGER


def get_engine_notices() -> list[str]:
    return get_search_manager().get_and_clear_notices()


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
