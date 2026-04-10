from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from core.models.search_types import Match


def _format_size(size: int) -> str:
    if size <= 0:
        return "-"
    units = ["B", "KB", "MB", "GB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.0f}{unit}"
        value /= 1024
    return f"{value:.0f}GB"


@dataclass
class ResultItem:
    index: int
    name: str
    path: str
    parent: str
    kind: str
    score: float
    modified_at: str
    size_label: str
    reason: str
    match: Match

    @classmethod
    def from_match(cls, index: int, match: Match) -> "ResultItem":
        return cls(
            index=index,
            name=match.path.name,
            path=str(match.path),
            parent=str(match.path.parent),
            kind=match.kind,
            score=match.score,
            modified_at=datetime.fromtimestamp(match.modified_ts).strftime("%Y-%m-%d %H:%M"),
            size_label=_format_size(match.size),
            reason=match.reason,
            match=match,
        )
