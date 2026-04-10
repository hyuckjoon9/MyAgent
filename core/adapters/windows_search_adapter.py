from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from core.adapters.native_adapter import (
    MAX_RESULT_LIMIT,
    indexed_entry_to_match,
    resolve_entries_scope,
    sort_matches,
)
from core.env import load_roots
from core.interfaces.search_adapter import SearchAdapter
from core.models.search_types import IndexedPath, Match
from core.query_parser import QueryIntent, parse_query

try:
    import pythoncom
    from win32com.client import Dispatch
except ImportError:  # pragma: no cover - optional dependency
    pythoncom = None  # type: ignore[assignment]
    Dispatch = None  # type: ignore[assignment]


class WindowsSearchAdapter(SearchAdapter):
    engine_name = "windows_search"
    display_name = "Windows Search"

    def __init__(self) -> None:
        if Dispatch is None or pythoncom is None:
            raise RuntimeError("Windows Search API를 위한 pywin32가 설치되어 있지 않습니다.")

    def search(self, query: str, limit: int) -> list[Match]:
        intent = parse_query(query)
        return self.search_intent(intent, limit)

    def search_intent(self, intent: QueryIntent, limit: int) -> list[Match]:
        roots = [root.resolve() for root in load_roots()]
        raw_entries = self._query_entries(intent, max(100, min(limit * 20, MAX_RESULT_LIMIT)), roots)
        scoped_entries = resolve_entries_scope(raw_entries, intent.location_hint)
        matches: list[Match] = []
        for entry in scoped_entries:
            entry_path = Path(entry.path)
            if intent.action == "compress" and entry.is_dir and entry_path.resolve() in roots:
                continue
            match = indexed_entry_to_match(entry, intent)
            if match is not None:
                matches.append(match)
        sort_matches(matches, intent)
        return matches[: max(1, min(limit, MAX_RESULT_LIMIT))]

    def _query_entries(self, intent: QueryIntent, limit: int, roots: list[Path]):
        pythoncom.CoInitialize()
        connection = None
        recordset = None
        try:
            connection = Dispatch("ADODB.Connection")
            connection.ConnectionTimeout = 5
            connection.Open("Provider=Search.CollatorDSO;Extended Properties='Application=Windows';")
            recordset = Dispatch("ADODB.Recordset")
            sql = self._build_sql(intent, limit, roots)
            recordset.Open(sql, connection)
            entries = []
            while not recordset.EOF:
                raw_path = str(recordset.Fields("System.ItemPathDisplay").Value or "").strip()
                if not raw_path:
                    recordset.MoveNext()
                    continue
                path = Path(raw_path)
                attributes = int(recordset.Fields("System.FileAttributes").Value or 0)
                is_dir = bool(attributes & 16)
                modified_value = recordset.Fields("System.DateModified").Value
                size_value = recordset.Fields("System.Size").Value
                modified_ts = modified_value.timestamp() if hasattr(modified_value, "timestamp") else 0.0
                size = int(size_value or 0)
                entries.append(
                    IndexedPath(
                        path=str(path),
                        name=path.name.lower(),
                        parent=str(path.parent).lower(),
                        suffix=path.suffix.lower(),
                        is_dir=is_dir,
                        modified_ts=modified_ts,
                        size=0 if is_dir else size,
                    )
                )
                recordset.MoveNext()
            return entries
        except Exception as exc:
            raise RuntimeError(f"Windows Search API 질의에 실패했습니다: {exc}") from exc
        finally:
            if recordset is not None:
                try:
                    recordset.Close()
                except Exception:
                    pass
            if connection is not None:
                try:
                    connection.Close()
                except Exception:
                    pass
            pythoncom.CoUninitialize()

    def _build_sql(self, intent: QueryIntent, limit: int, roots: list[Path]) -> str:
        where_parts = self._build_scope_filter(roots)
        if intent.target_kind == "folder":
            where_parts.append("System.ItemType IS NULL")
        elif intent.target_kind == "file":
            where_parts.append("System.ItemType IS NOT NULL")
        if intent.extension:
            where_parts.append(f"System.FileExtension = '.{self._escape_value(intent.extension.lower())}'")
        for keyword in intent.keywords:
            token = self._escape_like(keyword)
            where_parts.append(
                f"(System.FileName LIKE '%{token}%' OR System.ItemFolderPathDisplay LIKE '%{token}%')"
            )
        date_filter = self._build_date_filter(intent)
        if date_filter:
            where_parts.append(date_filter)
        where_clause = " AND ".join(where_parts) if where_parts else "1=1"
        order_clause = self._build_order_clause(intent)
        return (
            "SELECT TOP {limit} "
            "System.ItemPathDisplay, System.DateModified, System.Size, System.FileAttributes "
            "FROM SYSTEMINDEX "
            "WHERE {where_clause} "
            "{order_clause}"
        ).format(limit=max(1, limit), where_clause=where_clause, order_clause=order_clause)

    def _build_scope_filter(self, roots: list[Path]) -> list[str]:
        if not roots:
            return []
        scopes = []
        for root in roots:
            scope = str(root).replace("\\", "/").rstrip("/")
            scopes.append(f"SCOPE='file:{self._escape_value(scope)}'")
        if len(scopes) == 1:
            return [scopes[0]]
        return [f"({' OR '.join(scopes)})"]

    def _build_date_filter(self, intent: QueryIntent) -> str:
        now = datetime.now()
        start: datetime | None = None
        end: datetime | None = None
        if intent.time_filter == "today":
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
        elif intent.time_filter == "yesterday":
            end = now.replace(hour=0, minute=0, second=0, microsecond=0)
            start = end - timedelta(days=1)
        elif intent.time_filter == "this_week":
            start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
            end = now + timedelta(seconds=1)
        elif intent.time_filter == "last_week":
            end = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
            start = end - timedelta(days=7)
        elif intent.time_filter == "this_month":
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end = now + timedelta(seconds=1)
        elif intent.time_filter == "this_month_early":
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=10)
        elif intent.time_filter == "days_ago" and intent.days is not None:
            start = (now - timedelta(days=intent.days)).replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
        elif intent.time_filter == "last_days" and intent.days:
            start = now - timedelta(days=intent.days)
            end = now + timedelta(seconds=1)
        if start is None:
            return ""
        start_text = start.strftime("%Y-%m-%d %H:%M:%S")
        if end is None:
            return f"System.DateModified >= '{start_text}'"
        end_text = end.strftime("%Y-%m-%d %H:%M:%S")
        return f"(System.DateModified >= '{start_text}' AND System.DateModified < '{end_text}')"

    def _build_order_clause(self, intent: QueryIntent) -> str:
        if intent.sort_by == "size_desc":
            return "ORDER BY System.Size DESC"
        if intent.sort_by == "size_asc":
            return "ORDER BY System.Size ASC"
        if intent.sort_by == "name_asc":
            return "ORDER BY System.FileName ASC"
        if intent.sort_by == "modified_asc":
            return "ORDER BY System.DateModified ASC"
        return "ORDER BY System.DateModified DESC"

    def _escape_like(self, value: str) -> str:
        return self._escape_value(value).replace("%", "[%]").replace("_", "[_]")

    def _escape_value(self, value: str) -> str:
        return value.replace("'", "''")
