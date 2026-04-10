from __future__ import annotations

from abc import ABC, abstractmethod

from core.models.search_types import Match


class SearchAdapter(ABC):
    engine_name: str = "unknown"

    @abstractmethod
    def search(self, query: str, limit: int) -> list[Match]:
        raise NotImplementedError

    def rebuild_index(self) -> int:
        return 0
