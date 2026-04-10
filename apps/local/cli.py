import os
import sys

if os.name == "nt":
    import msvcrt

from apps.local.session import SessionState
from core.env import ENV_PATH, load_project_env
from core.models.search_types import Match
from core.query_parser import QueryIntent, parse_query
from core.search_engine import get_engine_notices, should_auto_open
from core.services.action_service import ActionService
from core.services.query_service import QueryService
from core.viewmodels.result_item import ResultItem

PAGE_SIZE = 5
QUERY_SERVICE = QueryService()
ACTION_SERVICE = ActionService()

BUILTIN_COMMAND_ALIASES = {
    "help": {"help", "도움말", "명령어", "사용법", "도움"},
    "hidden": {"hidden"},
    "roots": {"roots", "root", "경로", "루트", "검색경로", "검색 경로"},
    "history": {"history", "기록", "히스토리", "최근기록", "최근 기록"},
    "refresh": {"refresh", "reindex", "새로고침", "새로인덱스", "인덱스", "인덱싱", "다시인덱스", "재색인"},
    "exit": {"exit", "quit", "나가기", "종료", "끝", "그만"},
}

def _format_match(item: ResultItem) -> str:
    icon = "DIR" if item.kind == "folder" else "FILE"
    return (
        f"{item.index:>2}. [{icon}] {item.name}\n"
        f"    경로  {item.path}\n"
        f"    수정  {item.modified_at}    크기 {item.size_label}    점수 {item.score:.2f}\n"
        f"    이유  {item.reason}"
    )


def format_matches(matches: list[Match], page: int = 0, page_size: int = PAGE_SIZE) -> str:
    if not matches:
        return "Assistant> 결과를 찾지 못했습니다."
    items = [ResultItem.from_match(index, match) for index, match in enumerate(matches, start=1)]
    total_pages = max(1, (len(matches) + page_size - 1) // page_size)
    page = max(0, min(page, total_pages - 1))
    start = page * page_size
    page_items = items[start : start + page_size]
    lines = [
        f"Assistant> 후보 결과 ({len(matches)}개, {page + 1}/{total_pages} 페이지)",
        "----------------------------------------",
    ]
    for item in page_items:
        if item.index > 1:
            lines.append("")
        lines.append(_format_match(item))
    return "\n".join(lines)


def _render_picker(matches: list[Match], selected: int, marked: set[int] | None = None) -> None:
    os.system("cls")
    marked = marked or set()
    total_pages = max(1, (len(matches) + PAGE_SIZE - 1) // PAGE_SIZE)
    current_page = selected // PAGE_SIZE
    start = current_page * PAGE_SIZE
    end = min(start + PAGE_SIZE, len(matches))
    print("Assistant> 방향키로 이동합니다. 좌/우로 페이지 이동, Space로 표시, Enter로 열기, Esc로 취소합니다.")
    print(f"Assistant> 현재 페이지: {current_page + 1}/{total_pages}")
    print("------------------------------------------------------------")
    for index in range(start, end):
        item = ResultItem.from_match(index + 1, matches[index])
        pointer = ">" if index == selected else " "
        marker = "[v]" if index in marked else "[ ]"
        print(f"{pointer} {marker} {item.index:>2}. {item.name}")
        print(f"    {item.parent}")
        print(f"    {item.modified_at} | {item.size_label} | {item.reason}")
        if index < end - 1:
            print("")


def _pick_with_arrows(matches: list[Match], allow_multi: bool = False) -> list[int] | None:
    if os.name != "nt" or not sys.stdin.isatty():
        return None

    selected = 0
    marked: set[int] = set()
    while True:
        _render_picker(matches, selected, marked if allow_multi else None)
        key = msvcrt.getwch()
        if key == "\x03":
            os.system("cls")
            raise KeyboardInterrupt
        if key in ("\r", "\n"):
            os.system("cls")
            if allow_multi and marked:
                return sorted(marked)
            return [selected]
        if key == "\x1b":
            os.system("cls")
            return []
        if allow_multi and key == " ":
            if selected in marked:
                marked.remove(selected)
            else:
                marked.add(selected)
        if key in ("\x00", "\xe0"):
            code = msvcrt.getwch()
            if code == "H":
                selected = (selected - 1) % len(matches)
            elif code == "P":
                selected = (selected + 1) % len(matches)
            elif code == "K":
                selected = ((selected // PAGE_SIZE) - 1) % max(1, (len(matches) + PAGE_SIZE - 1) // PAGE_SIZE) * PAGE_SIZE
            elif code == "M":
                selected = ((selected // PAGE_SIZE) + 1) % max(1, (len(matches) + PAGE_SIZE - 1) // PAGE_SIZE) * PAGE_SIZE


def _view_matches_with_pages(matches: list[Match]) -> None:
    if os.name != "nt" or not sys.stdin.isatty() or len(matches) <= PAGE_SIZE:
        print(format_matches(matches))
        return

    page = 0
    total_pages = max(1, (len(matches) + PAGE_SIZE - 1) // PAGE_SIZE)
    while True:
        os.system("cls")
        print(format_matches(matches, page=page, page_size=PAGE_SIZE))
        print("")
        print("Assistant> 좌/우로 페이지 이동, Enter 또는 Esc로 닫습니다.")
        key = msvcrt.getwch()
        if key == "\x03":
            os.system("cls")
            raise KeyboardInterrupt
        if key in ("\r", "\n", "\x1b"):
            os.system("cls")
            return
        if key in ("\x00", "\xe0"):
            code = msvcrt.getwch()
            if code == "K":
                page = (page - 1) % total_pages
            elif code == "M":
                page = (page + 1) % total_pages


def _normalize_builtin_command(command: str) -> str:
    normalized = " ".join(command.lower().split())
    compact = normalized.replace(" ", "")
    for canonical, aliases in BUILTIN_COMMAND_ALIASES.items():
        if normalized in aliases or compact in aliases:
            return canonical
    return normalized


def _print_main_commands() -> None:
    print("Assistant> 명령: help(도움말), roots(경로), history(기록), refresh(새로고침), exit(나가기)")


def _print_open_commands() -> None:
    print("Assistant> 입력: 번호들(예: 1 3), 좌/우=페이지, Enter=취소, Esc=취소")


def _print_compress_commands() -> None:
    print("Assistant> 입력: 번호들(예: 1 3), 좌/우=페이지, Enter=취소, Esc=취소, y/n=확인")


def _handle_builtin_command(command: str, session: SessionState) -> bool:
    if command == "help":
        print("Assistant> 도움말: 아래 명령을 사용할 수 있습니다.")
        return True
    if command == "hidden":
        session.hidden_mode = True
        print("Assistant> 질문하세요.")
        return True
    if command == "roots":
        print("Assistant> 현재 검색 루트:")
        for root in ACTION_SERVICE.list_roots():
            print(f"  - {root}")
        return True
    if command == "history":
        if not session.history:
            print("Assistant> 아직 검색 기록이 없습니다.")
        else:
            print("Assistant> 최근 검색 기록:")
            for item in session.history[-10:]:
                print(f"  - {item}")
        return True
    if command == "refresh":
        result = ACTION_SERVICE.refresh_index()
        print(f"Assistant> {result.message}")
        return True
    return False


def _handle_selection(intent: QueryIntent, session: SessionState) -> bool:
    if intent.selection_index is None or intent.action not in {"open", "compress"}:
        return False
    if not session.last_matches:
        print("Assistant> 직전 검색 결과가 없어서 번호만으로는 열 수 없습니다.")
        return True

    index = intent.selection_index - 1
    if index < 0 or index >= len(session.last_matches):
        print("Assistant> 선택한 번호가 결과 범위를 벗어났습니다.")
        return True

    target = session.last_matches[index]
    if intent.action == "compress":
        return _compress_matches([target])

    result = ACTION_SERVICE.open_match(target)
    status = result.statuses[0]
    if status.ok:
        print(f"Assistant> 열었습니다: {status.path}")
    else:
        print(f"Assistant> 열지 못했습니다: {status.error}")
    return True


def _open_matches(matches: list[Match]) -> bool:
    result = ACTION_SERVICE.open_matches(matches)
    opened = 0
    for status in result.statuses:
        if status.ok:
            opened += 1
            print(f"Assistant> 열었습니다: {status.path}")
        else:
            print(f"Assistant> 열지 못했습니다: {status.path} ({status.error})")
    return opened > 0


def _open_selected_matches(matches: list[Match], selected_indexes: list[int] | None) -> bool:
    if not selected_indexes:
        return False
    picked = [matches[index] for index in selected_indexes if 0 <= index < len(matches)]
    return _open_matches(picked)


def _confirm(prompt: str) -> bool:
    print("Assistant> 입력: y=진행, n=취소")
    answer = input(f"{prompt} [y/N]: ").strip().lower()
    return answer in {"y", "yes", "ㅇ", "예"}


def _ask_open_archive(archive_path: str) -> None:
    if _confirm("Assistant> 압축 파일을 지금 열까요?"):
        result = ACTION_SERVICE.open_paths([archive_path])
        if result.ok:
            print(f"Assistant> 열었습니다: {archive_path}")
        else:
            error = result.statuses[0].error if result.statuses else result.error
            print(f"Assistant> 열지 못했습니다: {error}")


def _compress_matches(matches: list[Match]) -> bool:
    if not matches:
        return False
    if len(matches) >= 5:
        print(f"Assistant> 선택한 항목이 {len(matches)}개입니다.")
    print("Assistant> 아래 항목을 zip으로 압축합니다.")
    for match in matches:
        print(f"  - {match.path}")
    if not _confirm("Assistant> 계속할까요?"):
        print("Assistant> 압축을 취소했습니다.")
        return True
    result = ACTION_SERVICE.compress_matches(matches)
    if not result.ok:
        print(f"Assistant> {result.message}")
        return True
    archive_path = result.archive_path
    print(f"Assistant> {result.message}")
    if archive_path:
        _ask_open_archive(archive_path)
    return True


def _compress_selected_matches(matches: list[Match], selected_indexes: list[int] | None) -> bool:
    if not selected_indexes:
        return False
    picked = [matches[index] for index in selected_indexes if 0 <= index < len(matches)]
    return _compress_matches(picked)


def _maybe_compress(intent: QueryIntent, matches: list[Match]) -> bool:
    if intent.action != "compress":
        return False

    requested_count = intent.result_limit or len(matches)
    if intent.open_multiple and requested_count > 1:
        print(f"Assistant> 요청한 개수에 맞춰 상위 {requested_count}개 후보를 압축 대상으로 잡았습니다.")
        return _compress_matches(matches[:requested_count])

    print("Assistant> 방향키로 이동하고 Space로 압축할 항목을 고르세요. Enter로 확인합니다.")
    selected = _pick_with_arrows(matches, allow_multi=True)
    if selected == []:
        print("Assistant> 압축을 취소했습니다.")
        return True
    if _compress_selected_matches(matches, selected):
        return True

    _print_compress_commands()
    choice = input("Compress> 번호를 입력하거나 Enter로 취소: ").strip()
    if not choice:
        print("Assistant> 압축을 취소했습니다.")
        return True
    indexes = _parse_selection_input(choice)
    if indexes:
        return _compress_selected_matches(matches, indexes)
    follow_up = parse_query(f"{choice}번 압축해")
    return _handle_selection(follow_up, SessionState(last_matches=matches))


def _maybe_open(intent: QueryIntent, matches: list[Match], session: SessionState) -> bool:
    if intent.action != "open":
        return False

    auto_open, reason = should_auto_open(matches)
    requested_count = intent.result_limit or len(matches)
    if intent.open_multiple and requested_count > 1:
        print(f"Assistant> 요청한 개수에 맞춰 상위 {requested_count}개 후보만 보여줍니다.")
        _open_matches(matches[:requested_count])
        return True

    if auto_open:
        result = open_path(matches[0].path)
        if result.get("ok"):
            print(f"Assistant> 열었습니다: {matches[0].path}")
        else:
            print(f"Assistant> 열지 못했습니다: {result.get('error')}")
        return True

    print("Assistant> 자동으로 열지 않았습니다.")
    print(f"Assistant> 이유: {reason}")
    print(format_matches(matches[:3]))
    selected = _pick_with_arrows(matches[:3], allow_multi=True)
    if selected == []:
        return True
    if _open_selected_matches(matches[:3], selected):
        return True

    _print_open_commands()
    choice = input("Open> 열 항목 번호를 입력하거나 Enter로 취소: ").strip()
    if not choice:
        return True
    indexes = _parse_selection_input(choice)
    if indexes:
        return _open_selected_matches(matches[:3], indexes)
    follow_up = parse_query(f"{choice}번 열어")
    return _handle_selection(follow_up, session)


def _parse_selection_input(text: str) -> list[int]:
    indexes: list[int] = []
    seen: set[int] = set()
    for token in text.replace(",", " ").split():
        if token.isdigit():
            index = int(token) - 1
            if index >= 0 and index not in seen:
                indexes.append(index)
                seen.add(index)
    return indexes


def run_query(user_input: str, session: SessionState) -> list[Match]:
    result = QUERY_SERVICE.execute(user_input, session)
    intent = result.intent
    if result.message and result.selection_target is None:
        print(f"Assistant> {result.message}")
        return []
    if result.selection_target is not None:
        if intent.action == "compress":
            _compress_matches([result.selection_target])
        else:
            open_result = ACTION_SERVICE.open_match(result.selection_target)
            status = open_result.statuses[0]
            if status.ok:
                print(f"Assistant> 열었습니다: {status.path}")
            else:
                print(f"Assistant> 열지 못했습니다: {status.error}")
        return []

    matches = result.matches
    if intent.action == "search":
        _view_matches_with_pages(matches)
    else:
        print(format_matches(matches))

    if not matches:
        return matches

    if _maybe_compress(intent, matches):
        return matches

    if _maybe_open(intent, matches, session):
        return matches

    return matches


def main() -> None:
    load_project_env()
    session = SessionState()

    print("Local Folder Assistant")
    print(f".env 로드: {ENV_PATH}")
    for notice in get_engine_notices():
        print(notice)
    _print_main_commands()

    try:
        while True:
            user_input = input("\nYou> ").strip()
            if not user_input:
                _print_main_commands()
                continue
            if session.hidden_mode:
                session.hidden_mode = False
                print("Assistant> 혁준님입니다!!!")
                _print_main_commands()
                continue
            normalized_command = _normalize_builtin_command(user_input)
            if normalized_command == "exit":
                break
            if _handle_builtin_command(normalized_command, session):
                _print_main_commands()
                continue
            try:
                run_query(user_input, session)
            except RuntimeError as exc:
                print(f"Assistant> 설정 오류: {exc}")
            _print_main_commands()
    except KeyboardInterrupt:
        print("\nAssistant> 종료합니다.")


if __name__ == "__main__":
    main()
