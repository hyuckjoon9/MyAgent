from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Literal

from pydantic import BaseModel, Field

try:
    import regex as re
    HAS_REGEX_UNICODE_PROPERTIES = True
except ImportError:  # pragma: no cover
    import re  # type: ignore[no-redef]
    HAS_REGEX_UNICODE_PROPERTIES = False

try:
    from rapidfuzz import fuzz
except ImportError:  # pragma: no cover
    fuzz = None

try:
    from konlpy.tag import Okt
except ImportError:  # pragma: no cover
    Okt = None


INTENT_VERB_MAP = {
    "열다": "OPEN",
    "찾다": "SEARCH",
    "검색하다": "SEARCH",
    "압축하다": "ZIP",
    "삭제하다": "DELETE",
    "보여주다": "LIST",
    "정렬하다": "SORT",
    "필터하다": "FILTER",
}
ACTION_MAP = {
    "OPEN": "open",
    "SEARCH": "search",
    "LIST": "search",
    "ZIP": "compress",
    "DELETE": "delete",
    "SORT": "search",
    "FILTER": "search",
}
COMMON_EXTENSIONS = (
    "pdf",
    "doc",
    "docx",
    "xls",
    "xlsx",
    "ppt",
    "pptx",
    "txt",
    "md",
    "jpg",
    "jpeg",
    "png",
    "gif",
    "zip",
    "csv",
    "py",
    "json",
)
EXTENSION_ALIASES = {
    "엑셀": "excel",
    "excel": "excel",
    "xlsx": "excel",
    "xls": "excel",
    "워드": "word",
    "word": "word",
    "doc": "word",
    "docx": "word",
    "파워포인트": "powerpoint",
    "ppt": "powerpoint",
    "pptx": "powerpoint",
}
EXTENSION_GROUPS = {
    "excel": {"xls", "xlsx"},
    "word": {"doc", "docx"},
    "powerpoint": {"ppt", "pptx"},
}
LOCATION_ALIASES = {
    "downloads": {"downloads", "download", "다운로드"},
    "documents": {"documents", "document", "docs", "문서"},
    "desktop": {"desktop", "바탕화면"},
    "pictures": {"pictures", "photos", "images", "사진"},
    "videos": {"videos", "video", "동영상"},
    "music": {"music", "음악"},
}
LOCATION_SURFACE = {alias: canonical for canonical, aliases in LOCATION_ALIASES.items() for alias in aliases}
TARGET_WORDS = {
    "file": {"파일", "file", "files"},
    "folder": {"폴더", "folder", "folders", "디렉토리", "directory", "directories"},
}
RECENT_HINTS = {"최근": "modified_desc", "최신": "modified_desc", "recent": "modified_desc", "latest": "modified_desc"}
OLD_HINTS = {"오래된": "modified_asc", "oldest": "modified_asc"}
NAME_SORT_HINTS = {"이름순": "name_asc", "name": "name_asc"}
SIZE_DESC_HINTS = ("용량 큰", "큰 파일", "큰파일", "용량순", "large", "biggest")
SIZE_ASC_HINTS = ("용량 작은", "작은 파일", "smallest")
EXCLUDE_HINTS = ("빼고", "제외", "말고", "without", "except")
FOLLOWUP_LAST_HINTS = ("그거", "방금 거", "방금거", "이거", "저거", "last")
FOLLOWUP_SELECTED_HINTS = ("선택한 것", "선택한거", "선택 항목", "selected")
VERB_NORMALIZATION = {
    "열어줘": "열다",
    "열어": "열다",
    "열기": "열다",
    "실행해줘": "열다",
    "실행": "열다",
    "켜줘": "열다",
    "찾아줘": "찾다",
    "찾아": "찾다",
    "찾기": "찾다",
    "검색해줘": "검색하다",
    "검색": "검색하다",
    "압축해줘": "압축하다",
    "압축해": "압축하다",
    "압축": "압축하다",
    "묶어줘": "압축하다",
    "묶어": "압축하다",
    "보여줘": "보여주다",
    "보여": "보여주다",
    "보여줘요": "보여주다",
    "다시보여줘": "보여주다",
    "삭제해줘": "삭제하다",
    "삭제": "삭제하다",
    "지워줘": "삭제하다",
    "정렬해줘": "정렬하다",
    "정렬": "정렬하다",
    "필터해줘": "필터하다",
    "필터": "필터하다",
}
STOP_NOUNS = {
    "최근",
    "최신",
    "오늘",
    "어제",
    "이번",
    "주",
    "이번주",
    "지난주",
    "저번주",
    "지난",
    "저번",
    "달",
    "이번달",
    "이번 달",
    "초",
    "수정",
    "수정한",
    "변경",
    "변경한",
    "용량",
    "큰",
    "작은",
    "전",
    "전에",
    "관련",
    "순으로",
    "최신순으로",
    "중에",
    "빼고",
    "개",
    "만",
    "다시",
    "좀",
    "해줘",
    "주세요",
    "줘",
    "보여줘",
    "찾아줘",
    "열어줘",
    "압축해",
    "압축해줘",
}


_OKT = None


class FilterSpec(BaseModel):
    extension: str | None = None
    count: int | None = None
    sort: str | None = None
    exclude: list[str] = Field(default_factory=list)
    location: str | None = None


class ReferenceSpec(BaseModel):
    type: Literal["index", "last", "selected", "none"] = "none"
    value: str | int | None = None


class ParsedCommand(BaseModel):
    intent: str
    target: str | None
    verbs: list[str] = Field(default_factory=list)
    nouns: list[str] = Field(default_factory=list)
    filters: FilterSpec = Field(default_factory=FilterSpec)
    reference: ReferenceSpec = Field(default_factory=ReferenceSpec)
    is_followup: bool = False
    raw: str
    normalized: str


@dataclass
class QueryIntent:
    raw: str
    normalized: str
    action: str = "search"
    target_kind: str = "any"
    extension: str | None = None
    location_hint: str | None = None
    keywords: list[str] = field(default_factory=list)
    wants_recent: bool = False
    selection_index: int | None = None
    time_filter: str | None = None
    days: int | None = None
    result_limit: int | None = None
    open_multiple: bool = False
    sort_by: str | None = None
    exclude_keywords: list[str] = field(default_factory=list)
    size_preference: str | None = None
    reference_type: str = "none"
    parsed_command: ParsedCommand | None = None


def _get_okt() -> Okt | None:
    global _OKT
    if Okt is None:
        return None
    if _OKT is None:
        try:
            _OKT = Okt()
        except Exception:
            _OKT = False
    return _OKT if _OKT is not False else None


def normalize_query(text: str) -> str:
    lowered = text.lower().strip()
    if HAS_REGEX_UNICODE_PROPERTIES:
        cleaned = re.sub(r"[^\p{Hangul}\w\s.-]", " ", lowered)
    else:
        cleaned = re.sub(r"[^가-힣\w\s.-]", " ", lowered)
    separated = cleaned
    for ext in COMMON_EXTENSIONS:
        separated = re.sub(rf"(?<![\w])({re.escape(ext)})(\d+)(개?)", r"\1 \2\3", separated)
    separated = re.sub(r"(\d+)(개)([가-힣a-z]+)", r"\1 \2 \3", separated)
    separated = re.sub(r"([가-힣a-z]+)(\d+)(번)", r"\1 \2\3", separated)
    return re.sub(r"\s+", " ", separated).strip()


def _best_fuzzy_match(token: str, candidates: set[str], threshold: int = 82) -> str | None:
    if token in candidates:
        return token
    if fuzz is None:
        return None
    best = max(candidates, key=lambda candidate: fuzz.ratio(token, candidate))
    return best if fuzz.ratio(token, best) >= threshold else None


def _extract_count(normalized: str) -> int | None:
    match = re.search(r"(\d+)\s*개", normalized)
    if match:
        return max(1, min(int(match.group(1)), 20))
    return None


def _extract_extension(tokens: list[str], normalized: str) -> str | None:
    for token in tokens:
        if token in EXTENSION_ALIASES:
            return EXTENSION_ALIASES[token]
        if token in COMMON_EXTENSIONS:
            return token
        fuzzy = _best_fuzzy_match(token, set(COMMON_EXTENSIONS))
        if fuzzy:
            return fuzzy
    for surface, mapped in EXTENSION_ALIASES.items():
        if surface in normalized:
            return mapped
    for ext in COMMON_EXTENSIONS:
        if re.search(rf"(^|[\s]){re.escape(ext)}($|[\s])", normalized):
            return ext
    return None


def _extract_location(tokens: list[str], normalized: str) -> str | None:
    for token in tokens:
        if token in LOCATION_SURFACE:
            return LOCATION_SURFACE[token]
        fuzzy = _best_fuzzy_match(token, set(LOCATION_SURFACE))
        if fuzzy:
            return LOCATION_SURFACE[fuzzy]
    for surface, canonical in LOCATION_SURFACE.items():
        if surface in normalized:
            return canonical
    return None


def _extract_sort(normalized: str) -> str | None:
    if any(hint in normalized for hint in SIZE_DESC_HINTS):
        return "size_desc"
    if any(hint in normalized for hint in SIZE_ASC_HINTS):
        return "size_asc"
    if any(hint in normalized for hint in RECENT_HINTS):
        return "modified_desc"
    if any(hint in normalized for hint in OLD_HINTS):
        return "modified_asc"
    if any(hint in normalized for hint in NAME_SORT_HINTS):
        return "name_asc"
    return None


def _extract_time_filter(normalized: str) -> tuple[str | None, int | None]:
    if "오늘" in normalized or "today" in normalized:
        return "today", 1
    if "어제" in normalized or "yesterday" in normalized:
        return "yesterday", 1
    match = re.search(r"(\d+)\s*일\s*전", normalized)
    if match:
        return "days_ago", int(match.group(1))
    if "이번주" in normalized or "이번 주" in normalized or "this week" in normalized:
        return "this_week", 7
    if "지난주" in normalized or "지난 주" in normalized or "저번주" in normalized or "저번 주" in normalized:
        return "last_week", 7
    if "이번달초" in normalized or "이번 달 초" in normalized:
        return "this_month_early", None
    if "이번달" in normalized or "이번 달" in normalized:
        return "this_month", None
    match = re.search(r"최근\s*(\d+)\s*일", normalized)
    if match:
        return "last_days", int(match.group(1))
    match = re.search(r"last\s*(\d+)\s*days?", normalized)
    if match:
        return "last_days", int(match.group(1))
    return None, None


def _extract_exclude(tokens: list[str], normalized: str) -> list[str]:
    excludes: list[str] = []
    match = re.search(r"([가-힣a-z0-9_.-]+)\s*(빼고|제외|말고)", normalized)
    if match:
        excludes.append(match.group(1))
    if "zip 빼고" in normalized and "zip" not in excludes:
        excludes.append("zip")
    for index, token in enumerate(tokens[:-1]):
        if tokens[index + 1] in EXCLUDE_HINTS and token not in excludes:
            excludes.append(token)
    return excludes


def _extract_reference(normalized: str) -> ReferenceSpec:
    for hint in FOLLOWUP_SELECTED_HINTS:
        if hint in normalized:
            return ReferenceSpec(type="selected", value=hint)
    for hint in FOLLOWUP_LAST_HINTS:
        if hint in normalized:
            return ReferenceSpec(type="last", value=hint)
    match = re.search(r"(\d+)\s*번", normalized)
    if match:
        return ReferenceSpec(type="index", value=int(match.group(1)))
    if normalized.isdigit():
        return ReferenceSpec(type="index", value=int(normalized))
    if "다시" in normalized:
        return ReferenceSpec(type="last", value="implicit_last")
    return ReferenceSpec()


def _extract_target(tokens: list[str], extension: str | None) -> str | None:
    token_set = set(tokens)
    if token_set & TARGET_WORDS["folder"]:
        return "folder"
    if token_set & TARGET_WORDS["file"]:
        return "file"
    if extension:
        return "file"
    return None


def _extract_pos_tokens(normalized: str) -> tuple[list[str], list[str]]:
    okt = _get_okt()
    if okt is None:
        tokens = normalized.split()
        nouns = [token for token in tokens if not re.fullmatch(r"\d+(개|번)?", token)]
        return tokens, nouns

    morphs = okt.pos(normalized, stem=True, norm=True)
    verbs = [word for word, pos in morphs if pos in {"Verb", "Adjective"}]
    nouns = [word for word, pos in morphs if pos in {"Noun", "Alpha", "Number"}]
    return verbs, nouns


def _normalize_verbs(normalized: str, verb_tokens: list[str]) -> list[str]:
    verbs: list[str] = []
    for token in normalized.split():
        if token in VERB_NORMALIZATION and VERB_NORMALIZATION[token] not in verbs:
            verbs.append(VERB_NORMALIZATION[token])
    for token in verb_tokens:
        if token in INTENT_VERB_MAP and token not in verbs:
            verbs.append(token)
    if not verbs:
        if any(hint in normalized for hint in ("열어", "열기", "실행", "켜")):
            verbs.append("열다")
        elif any(hint in normalized for hint in ("압축", "묶어", "zip")):
            verbs.append("압축하다")
        elif any(hint in normalized for hint in ("보여", "목록")):
            verbs.append("보여주다")
        elif any(hint in normalized for hint in ("정렬",)):
            verbs.append("정렬하다")
        elif any(hint in normalized for hint in ("필터", "빼고", "제외")):
            verbs.append("필터하다")
        else:
            verbs.append("찾다")
    return verbs


def _extract_nouns(tokens: list[str], noun_tokens: list[str], extension: str | None, location: str | None) -> list[str]:
    nouns: list[str] = []
    for noun in noun_tokens or tokens:
        if noun in STOP_NOUNS or noun in VERB_NORMALIZATION:
            continue
        if re.fullmatch(r"\d+(개|번)?", noun):
            continue
        if re.fullmatch(r"\d+일", noun):
            continue
        if noun not in nouns:
            nouns.append(noun)
    if extension and extension not in nouns:
        nouns.append(extension)
    if location and location not in nouns:
        nouns.append(location)
    return nouns


def _select_intent(verbs: list[str]) -> str:
    for verb in reversed(verbs):
        mapped = INTENT_VERB_MAP.get(verb)
        if mapped:
            return mapped
    return "SEARCH"


def parse_command(text: str) -> ParsedCommand:
    normalized = normalize_query(text)
    tokens = normalized.split()
    verb_tokens, noun_tokens = _extract_pos_tokens(normalized)
    verbs = _normalize_verbs(normalized, verb_tokens)
    intent = _select_intent(verbs)
    extension = _extract_extension(tokens, normalized)
    location = _extract_location(tokens, normalized)
    reference = _extract_reference(normalized)
    excludes = _extract_exclude(tokens, normalized)
    if extension in excludes:
        extension = None
    filters = FilterSpec(
        extension=extension,
        count=_extract_count(normalized),
        sort=_extract_sort(normalized),
        exclude=excludes,
        location=location,
    )
    target = _extract_target(tokens, extension)
    nouns = _extract_nouns(tokens, noun_tokens, extension, location)
    has_search_verb = any(verb in {"찾다", "검색하다"} for verb in verbs)
    is_followup = reference.type != "none" and not has_search_verb
    return ParsedCommand(
        intent=intent,
        target=target,
        verbs=verbs,
        nouns=nouns,
        filters=filters,
        reference=reference,
        is_followup=is_followup,
        raw=text,
        normalized=normalized,
    )


def parse_command_json(text: str) -> str:
    return json.dumps(parse_command(text).model_dump(), ensure_ascii=False)


def _map_sort_to_time_filter(sort: str | None) -> tuple[str | None, bool]:
    if sort == "modified_desc":
        return None, True
    return None, False


def _keywords_from_command(command: ParsedCommand) -> list[str]:
    blocked = {
        command.filters.extension,
        command.filters.location,
        "파일",
        "폴더",
        "최근",
        "최신",
        "오늘",
        "어제",
        "이번",
        "주",
        "이번주",
        "지난주",
        "저번주",
        "달",
        "이번달",
        "초",
        "수정",
        "수정한",
        "변경",
        "변경한",
        "용량",
        "큰",
        "작은",
        "엑셀",
    }
    blocked.update(command.filters.exclude)
    return [noun for noun in command.nouns if noun and noun not in blocked]


def parse_query(text: str) -> QueryIntent:
    command = parse_command(text)
    time_filter, days = _extract_time_filter(command.normalized)
    sort_time_filter, wants_recent = _map_sort_to_time_filter(command.filters.sort)
    if sort_time_filter is not None:
        time_filter = sort_time_filter
    if wants_recent is False and time_filter is not None:
        wants_recent = True
    action = ACTION_MAP.get(command.intent, "search")
    target_kind = command.target or "any"
    selection_index = command.reference.value if command.reference.type == "index" else None
    result_limit = command.filters.count
    open_multiple = action in {"open", "compress"} and (result_limit or 0) > 1
    return QueryIntent(
        raw=text,
        normalized=command.normalized,
        action=action,
        target_kind=target_kind,
        extension=command.filters.extension,
        location_hint=command.filters.location,
        keywords=_keywords_from_command(command),
        wants_recent=wants_recent,
        selection_index=selection_index if isinstance(selection_index, int) else None,
        time_filter=time_filter,
        days=days,
        result_limit=result_limit,
        open_multiple=open_multiple,
        sort_by=command.filters.sort,
        exclude_keywords=command.filters.exclude,
        size_preference="large" if command.filters.sort == "size_desc" else "small" if command.filters.sort == "size_asc" else None,
        reference_type=command.reference.type,
        parsed_command=command,
    )
