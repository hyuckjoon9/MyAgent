from dataclasses import dataclass, field

from core.models.search_types import Match


@dataclass
class SessionState:
    last_matches: list[Match] = field(default_factory=list)
    history: list[str] = field(default_factory=list)
    hidden_mode: bool = False

    def remember_query(self, query: str) -> None:
        self.history.append(query)
        self.history = self.history[-20:]

    def remember_matches(self, matches: list[Match]) -> None:
        self.last_matches = matches
