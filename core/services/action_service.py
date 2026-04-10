from __future__ import annotations

from pathlib import Path

from core.env import load_roots
from core.models.search_types import Match
from core.search_engine import create_zip, open_path, rebuild_index
from core.viewmodels.action_result import ActionResult, PathActionStatus


class ActionService:
    def open_paths(self, paths: list[str | Path]) -> ActionResult:
        statuses: list[PathActionStatus] = []
        opened = 0
        for path in paths:
            result = open_path(path)
            target_path = str(result.get("opened") or result.get("path") or path)
            ok = bool(result.get("ok"))
            statuses.append(PathActionStatus(path=target_path, ok=ok, error=result.get("error")))
            if ok:
                opened += 1
        message = f"{opened}개 항목을 열었습니다." if opened else "열지 못했습니다."
        return ActionResult(
            ok=opened > 0,
            action="open",
            message=message,
            statuses=statuses,
            count=opened,
            error=None if opened > 0 else "No paths were opened",
        )

    def open_matches(self, matches: list[Match]) -> ActionResult:
        return self.open_paths([match.path for match in matches])

    def open_match(self, match: Match) -> ActionResult:
        return self.open_matches([match])

    def compress_matches(self, matches: list[Match]) -> ActionResult:
        paths = [match.path for match in matches]
        result = create_zip(paths)
        ok = bool(result.get("ok"))
        archive_path = result.get("archive")
        message = (
            f"압축을 만들었습니다: {archive_path}"
            if ok and archive_path
            else f"압축하지 못했습니다: {result.get('error')}"
        )
        return ActionResult(
            ok=ok,
            action="compress",
            message=message,
            statuses=[PathActionStatus(path=str(match.path), ok=ok) for match in matches],
            archive_path=str(archive_path) if archive_path else None,
            count=int(result.get("count", 0)) if ok else 0,
            error=result.get("error"),
        )

    def refresh_index(self) -> ActionResult:
        count = rebuild_index()
        return ActionResult(
            ok=True,
            action="refresh",
            message=f"현재 검색 디렉터리를 새로고침했습니다. 총 {count}개 항목을 반영했습니다.",
            count=count,
        )

    def list_roots(self) -> list[Path]:
        return load_roots()
