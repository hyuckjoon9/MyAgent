from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PathActionStatus:
    path: str
    ok: bool
    error: str | None = None


@dataclass
class ActionResult:
    ok: bool
    action: str
    message: str
    statuses: list[PathActionStatus] = field(default_factory=list)
    archive_path: str | None = None
    count: int = 0
    error: str | None = None
