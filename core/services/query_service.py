from __future__ import annotations

from apps.local.session import SessionState
from core.models.search_types import Match
from core.query_parser import QueryIntent, parse_query
from core.search_engine import get_search_manager, search
from core.viewmodels.query_result import QueryExecutionResult
from core.viewmodels.result_item import ResultItem


class QueryService:
    def execute(self, user_input: str, session: SessionState) -> QueryExecutionResult:
        intent = parse_query(user_input)
        selection_result = self._resolve_selection(intent, session, user_input)
        if selection_result is not None:
            return selection_result

        limit = intent.result_limit or 500
        matches = search(intent, limit=limit)
        session.remember_query(user_input)
        session.remember_matches(matches)
        return QueryExecutionResult(
            query=user_input,
            intent=intent,
            matches=matches,
            items=self._build_items(matches),
            engine_name=get_search_manager().engine_name(),
        )

    def _resolve_selection(
        self,
        intent: QueryIntent,
        session: SessionState,
        user_input: str,
    ) -> QueryExecutionResult | None:
        if intent.selection_index is None or intent.action not in {"open", "compress"}:
            return None
        if not session.last_matches:
            return QueryExecutionResult(
                query=user_input,
                intent=intent,
                message="직전 검색 결과가 없어서 번호만으로는 열 수 없습니다.",
                used_session_matches=True,
            )

        index = intent.selection_index - 1
        if index < 0 or index >= len(session.last_matches):
            return QueryExecutionResult(
                query=user_input,
                intent=intent,
                message="선택한 번호가 결과 범위를 벗어났습니다.",
                used_session_matches=True,
            )

        target = session.last_matches[index]
        return QueryExecutionResult(
            query=user_input,
            intent=intent,
            matches=session.last_matches,
            items=self._build_items(session.last_matches),
            selection_target=target,
            used_session_matches=True,
            engine_name=get_search_manager().engine_name(),
        )

    def _build_items(self, matches: list[Match]) -> list[ResultItem]:
        return [ResultItem.from_match(index, match) for index, match in enumerate(matches, start=1)]
