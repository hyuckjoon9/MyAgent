# Local Folder Assistant

Windows에서 파일과 폴더를 자연어로 찾고 여는 실험용 프로젝트입니다.

## Modes

- `assistant.py`
  - OpenAI `Responses API` 기반
  - 자연어 해석을 모델에 맡기고 로컬 검색 도구를 호출합니다
- `local_assistant.py`
  - API 키 없이 동작하는 로컬 규칙 기반 버전
  - 파일명, 확장자, 최근 수정 파일, 경로 키워드를 기준으로 검색합니다

## Setup

1. Python 3.12+
2. 환경변수 설정

Required:

- `ASSISTANT_ROOTS`

Optional:

- `OPENAI_API_KEY`
- `OPENAI_MODEL` 기본값: `gpt-5.1`

예시:

```powershell
$env:ASSISTANT_ROOTS="C:\Users\dotor\Documents;C:\Users\dotor\Downloads"
$env:OPENAI_API_KEY="your_api_key_here"
```

## Run

로컬 버전:

```powershell
python local_assistant.py
```

OpenAI 버전:

```powershell
pip install -r requirements.txt
python assistant.py
```

## Example prompts

- `다운로드 폴더에서 pdf 찾아줘`
- `최근에 수정한 문서 보여줘`
- `report 들어간 폴더 열어줘`
- `사진 관련 파일 찾아서 열어줘`

## How local mode works

- 검색 범위는 `ASSISTANT_ROOTS` 아래로 제한됩니다
- `열어줘`, `open` 같은 표현이 있으면 상위 결과를 바로 엽니다
- `최근`, `latest`, `recent` 같은 표현이 있으면 최근 수정 파일을 우선 보여줍니다
- `pdf`, `xlsx`, `pptx`, `jpg` 같은 확장자 표현을 인식합니다

## Next steps

- Windows Search 또는 Everything 연동
- 파일 내용 인덱싱 추가
- 단축키 런처 또는 트레이 앱으로 변경
- Ollama 같은 로컬 LLM 연결
