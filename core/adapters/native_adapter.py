from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable

from core.env import PROJECT_ROOT, load_roots
from core.interfaces.search_adapter import SearchAdapter
from core.models.search_types import IndexedPath, Match
from core.query_parser import EXTENSION_GROUPS, LOCATION_ALIASES, QueryIntent, parse_query


INDEX_DIR = PROJECT_ROOT / ".cache"
INDEX_PATH = INDEX_DIR / "local_index.json"
MAX_RESULT_LIMIT = 500


def serialize_entries(entries: list[IndexedPath], roots: list[Path]) -> dict[str, object]:
    return {
        "roots": [str(root) for root in roots],
        "generated_at": datetime.now().timestamp(),
        "entries": [asdict(entry) for entry in entries],
    }


def read_entries(data: dict[str, object]) -> list[IndexedPath]:
    return [IndexedPath(**item) for item in data.get("entries", [])]  # type: ignore[arg-type]


def is_cache_fresh(data: dict[str, object], roots: list[Path]) -> bool:
    if data.get("roots", []) != [str(root) for root in roots]:
        return False
    generated_at = float(data.get("generated_at", 0))
    return (datetime.now().timestamp() - generated_at) < 300


def iter_paths(root: Path) -> Iterable[Path]:
    yield root
    for path in root.rglob("*"):
        yield path


def index_path(path: Path, modified_ts: float, size: int) -> IndexedPath:
    return IndexedPath(
        path=str(path),
        name=path.name.lower(),
        parent=str(path.parent).lower(),
        suffix=path.suffix.lower(),
        is_dir=path.is_dir(),
        modified_ts=modified_ts,
        size=size,
    )


def build_index(roots: list[Path]) -> list[IndexedPath]:
    entries: list[IndexedPath] = []
    for root in roots:
        for path in iter_paths(root):
            try:
                stat = path.stat()
            except OSError:
                continue
            entries.append(index_path(path, stat.st_mtime, 0 if path.is_dir() else stat.st_size))

    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(
        json.dumps(serialize_entries(entries, roots), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return entries


def load_index(refresh: bool = False) -> list[IndexedPath]:
    roots = load_roots()
    if not refresh and INDEX_PATH.exists():
        try:
            data = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
            if is_cache_fresh(data, roots):
                return read_entries(data)
        except (OSError, json.JSONDecodeError):
            pass
    return build_index(roots)


def resolve_entries_scope(entries: list[IndexedPath], location_hint: str | None) -> list[IndexedPath]:
    if not location_hint:
        return entries

    aliases = LOCATION_ALIASES.get(location_hint, set())
    filtered = [
        entry
        for entry in entries
        if any(alias in entry.path.lower().split("\\") for alias in aliases)
        or any(alias in entry.path.lower() for alias in aliases)
    ]
    return filtered or entries


def matches_time_filter(entry: IndexedPath, intent: QueryIntent) -> bool:
    if not intent.time_filter:
        return True

    modified = datetime.fromtimestamp(entry.modified_ts)
    now = datetime.now()
    if intent.time_filter == "today":
        return modified.date() == now.date()
    if intent.time_filter == "yesterday":
        return modified.date() == (now - timedelta(days=1)).date()
    if intent.time_filter == "this_week":
        start = now - timedelta(days=now.weekday())
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        return modified >= start
    if intent.time_filter == "last_week":
        this_week_start = now - timedelta(days=now.weekday())
        this_week_start = this_week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        last_week_start = this_week_start - timedelta(days=7)
        return last_week_start <= modified < this_week_start
    if intent.time_filter == "this_month":
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return modified >= month_start
    if intent.time_filter == "this_month_early":
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        early_end = month_start + timedelta(days=10)
        return month_start <= modified < early_end
    if intent.time_filter == "days_ago" and intent.days is not None:
        target_date = (now - timedelta(days=intent.days)).date()
        return modified.date() == target_date
    if intent.time_filter == "last_days" and intent.days:
        return modified >= now - timedelta(days=intent.days)
    return True


def matches_extension(entry: IndexedPath, extension: str | None) -> bool:
    if extension is None or entry.is_dir:
        return True
    if extension in EXTENSION_GROUPS:
        return entry.suffix.lstrip(".") in EXTENSION_GROUPS[extension]
    return entry.suffix == f".{extension}"


def is_excluded(entry: IndexedPath, excludes: list[str]) -> bool:
    haystacks = [entry.name, entry.parent, entry.path.lower(), entry.suffix.lstrip(".")]
    for token in excludes:
        lowered = token.lower()
        if lowered in EXTENSION_GROUPS and entry.suffix.lstrip(".") in EXTENSION_GROUPS[lowered]:
            return True
        if any(lowered and lowered in haystack for haystack in haystacks):
            return True
    return False


def keyword_hits(text: str, keywords: list[str]) -> int:
    return sum(1 for token in keywords if token and token in text)


def score_entry(entry: IndexedPath, intent: QueryIntent) -> tuple[float, list[str]]:
    if intent.target_kind == "folder" and not entry.is_dir:
        return 0.0, []
    if intent.target_kind == "file" and entry.is_dir:
        return 0.0, []
    if not matches_extension(entry, intent.extension):
        return 0.0, []
    if is_excluded(entry, intent.exclude_keywords):
        return 0.0, []
    if not matches_time_filter(entry, intent):
        return 0.0, []

    score = 0.0
    reasons: list[str] = []

    if intent.extension and matches_extension(entry, intent.extension):
        score += 1.4
        reasons.append(f"{intent.extension} 확장자 일치")

    if intent.location_hint and intent.location_hint in entry.path.lower():
        score += 0.8
        reasons.append("위치 힌트 일치")

    if intent.keywords:
        name_hits = keyword_hits(entry.name, intent.keywords)
        parent_hits = keyword_hits(entry.parent, intent.keywords)
        if name_hits:
            score += name_hits * 1.8
            reasons.append("파일명/폴더명 키워드 일치")
        if parent_hits:
            score += parent_hits * 0.9
            reasons.append("상위 경로 키워드 일치")
    else:
        score += 0.6

    recency_bonus = max(
        0.0,
        1.2 - ((datetime.now().timestamp() - entry.modified_ts) / 86400) * 0.1,
    )
    if recency_bonus > 0:
        score += recency_bonus
        reasons.append("최근 수정 보너스")

    if entry.is_dir:
        score += 0.2

    if intent.wants_recent and not entry.is_dir:
        score += 0.8
        reasons.append("최근 파일 요청")
    if intent.size_preference == "large" and not entry.is_dir:
        score += min(1.2, entry.size / (1024 * 1024 * 512))
        reasons.append("큰 파일 우선")
    if intent.size_preference == "small" and not entry.is_dir:
        score += max(0.0, 1.0 - min(1.0, entry.size / (1024 * 1024 * 10)))
        reasons.append("작은 파일 우선")

    return score, reasons


def is_broad_listing(intent: QueryIntent) -> bool:
    return not any(
        (
            intent.extension,
            intent.location_hint,
            intent.keywords,
            intent.wants_recent,
            intent.time_filter,
            intent.days,
        )
    )


def indexed_entry_to_match(entry: IndexedPath, intent: QueryIntent) -> Match | None:
    score, reasons = score_entry(entry, intent)
    if not is_broad_listing(intent) and score < 0.9:
        return None
    return Match(
        path=Path(entry.path),
        kind="folder" if entry.is_dir else "file",
        score=round(score, 3),
        modified_ts=entry.modified_ts,
        size=entry.size,
        reason=", ".join(dict.fromkeys(reasons)) or "기본 목록 표시",
    )


def sort_matches(matches: list[Match], intent: QueryIntent) -> list[Match]:
    if intent.sort_by == "size_desc":
        matches.sort(key=lambda item: (item.size, item.score, item.modified_ts), reverse=True)
    elif intent.sort_by == "size_asc":
        matches.sort(key=lambda item: (item.size, -item.score, -item.modified_ts))
    elif intent.sort_by == "name_asc":
        matches.sort(key=lambda item: (item.path.name.lower(), -item.score))
    elif intent.sort_by == "modified_asc":
        matches.sort(key=lambda item: (item.modified_ts, item.score))
    elif intent.wants_recent or intent.time_filter or intent.sort_by == "modified_desc":
        matches.sort(key=lambda item: (item.modified_ts, item.score), reverse=True)
    else:
        matches.sort(key=lambda item: (item.score, item.modified_ts), reverse=True)
    return matches


class NativeAdapter(SearchAdapter):
    engine_name = "native"

    def search(self, query: str, limit: int) -> list[Match]:
        intent = parse_query(query)
        return self.search_intent(intent, limit)

    def search_intent(self, intent: QueryIntent, limit: int, refresh_index: bool = False) -> list[Match]:
        entries = resolve_entries_scope(load_index(refresh=refresh_index), intent.location_hint)
        root_paths = {root.resolve() for root in load_roots()}
        matches: list[Match] = []
        for entry in entries:
            entry_path = Path(entry.path)
            if intent.action == "compress" and entry.is_dir and entry_path.resolve() in root_paths:
                continue
            match = indexed_entry_to_match(entry, intent)
            if match is not None:
                matches.append(match)

        sort_matches(matches, intent)
        return matches[: max(1, min(limit, MAX_RESULT_LIMIT))]

    def rebuild_index(self) -> int:
        return len(build_index(load_roots()))
