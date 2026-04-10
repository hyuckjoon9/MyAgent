from __future__ import annotations

from dataclasses import dataclass, field

from core.models.search_types import Match
from core.query_parser import QueryIntent
from core.viewmodels.result_item import ResultItem


@dataclass
class QueryExecutionResult:
    query: str
    intent: QueryIntent
    matches: list[Match] = field(default_factory=list)
    items: list[ResultItem] = field(default_factory=list)
    message: str | None = None
    selection_target: Match | None = None
    used_session_matches: bool = False
    engine_name: str | None = None

    @property
    def has_matches(self) -> bool:
        return bool(self.matches)

    @property
    def is_selection_request(self) -> bool:
        return self.selection_target is not None or self.used_session_matches or self.message is not None
