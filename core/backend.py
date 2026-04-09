import os
import sys
from pathlib import Path

# 프로젝트 루트를 경로에 추가 (assistant.py, local_assistant.py 임포트용)
ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import local_assistant


def _format_search_results(result: dict) -> str:
    items = result.get("results", [])
    if not items:
        return "해당하는 파일을 찾지 못했어요."
    lines = []
    for i, item in enumerate(items[:5], 1):
        path = Path(item["path"])
        kind = "📁" if item.get("kind") == "folder" else "📄"
        lines.append(f"{i}. {kind} {path.name}\n   {path.parent}")
    return "\n".join(lines)


def _format_recent_results(result: dict) -> str:
    items = result.get("results", [])
    if not items:
        return "최근 수정한 파일이 없어요."
    lines = []
    for i, item in enumerate(items[:5], 1):
        path = Path(item["path"])
        lines.append(f"{i}. 📄 {path.name}\n   {path.parent}")
    return "\n".join(lines)


class LocalBackend:
    """API 키 없이 동작하는 규칙 기반 백엔드."""

    def query(self, user_input: str) -> str:
        text = user_input.lower()

        # 최근 파일 요청
        if any(k in text for k in ["최근", "recent", "latest", "방금"]):
            result = local_assistant.list_recent_files(limit=5)
            return _format_recent_results(result)

        # 파일 열기 요청
        open_keywords = ["열어", "열기", "open", "실행", "켜줘"]
        wants_open = any(k in text for k in open_keywords)

        # 검색어 추출 및 검색
        result = local_assistant.search_files(user_input, limit=5)
        items = result.get("results", [])

        if not items:
            return "해당하는 파일을 찾지 못했어요."

        if wants_open:
            top = items[0]["path"]
            open_result = local_assistant.open_path(top)
            if open_result.get("ok"):
                return f"열었어요!\n📄 {Path(top).name}"
            return f"파일을 열지 못했어요: {open_result.get('error')}"

        return _format_search_results(result)


class OpenAIBackend:
    """OpenAI Responses API 기반 백엔드."""

    def __init__(self) -> None:
        from openai import OpenAI
        import assistant

        self._client = OpenAI()
        self._assistant = assistant

    def query(self, user_input: str) -> str:
        import json

        response = self._client.responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            instructions=(
                "You are a friendly local Windows folder assistant. "
                "Use tools whenever you need to search or open files. "
                "Answer in Korean. Keep responses concise."
            ),
            input=user_input,
            tools=self._assistant.TOOLS,
        )

        while True:
            calls = [item for item in response.output if item.type == "function_call"]
            if not calls:
                break

            tool_outputs = []
            for call in calls:
                args = json.loads(call.arguments)
                result = self._assistant.run_tool(call.name, args)
                tool_outputs.append(
                    {
                        "type": "function_call_output",
                        "call_id": call.call_id,
                        "output": json.dumps(result, ensure_ascii=False),
                    }
                )

            response = self._client.responses.create(
                model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                previous_response_id=response.id,
                input=tool_outputs,
                tools=self._assistant.TOOLS,
            )

        return self._assistant.extract_text(response) or "응답이 비어 있어요."


def create_backend():
    """API 키 유무에 따라 백엔드 자동 선택."""
    if os.getenv("OPENAI_API_KEY"):
        try:
            return OpenAIBackend()
        except Exception:
            pass
    return LocalBackend()
