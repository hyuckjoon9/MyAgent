# MyAgent

자연어로 로컬 파일을 찾고 열고 압축할 수 있게 만든 Windows 데스크탑 검색 도우미입니다.

CustomTkinter 기반 다크 테마 GUI를 기본으로 사용하며, Everything 사용 가능 시 고속 검색을 우선 적용합니다.

## 왜 만들었나

Windows 기본 검색은 파일명 일부나 단순 필터에는 강하지만, 이런 요청은 바로 처리하기 어렵습니다.

- `최근에 수정한 pdf 보여줘`
- `이번 주 회의록 엑셀 찾아줘`
- `다운로드 폴더에서 zip 빼고 찾아줘`
- `3개만 보여줘`

이 프로젝트는 이런 자연어 요청을 구조화해서 로컬 파일 검색과 후속 액션으로 연결하기 위해 만들었습니다.

## 핵심 기능

- 자연어 기반 로컬 파일 검색
- 다크 테마 데스크탑 GUI
- 검색 결과 카드형 UI 제공
- 카드 클릭 또는 체크박스로 결과 선택
- 카드 내부에서 경로 펼침, 경로 복사, 폴더 열기
- 파일/폴더 열기
- 여러 결과 선택 후 일괄 열기
- 여러 결과 선택 후 zip 압축
- 검색 엔진 자동 선택
- `Everything` 사용 가능 시 고속 검색
- `Everything` 미사용 환경에서 native 검색 fallback
- 시스템 트레이 최소화 후 다시 열기

## 실행 방법

### 1. 설치

```powershell
pip install -r requirements.txt
```

### 2. 환경변수 파일 준비

프로젝트 루트에 `.env` 파일을 만들고 값을 설정합니다.

```env
ASSISTANT_ROOTS=C:\Users\YourName\Documents
ASSISTANT_SEARCH_MODE=auto
EVERYTHING_AUTO_START=true
EVERYTHING_DLL_PATH=
```

설정 항목:

- `ASSISTANT_ROOTS`: 검색할 루트 경로. 여러 개면 `;` 로 구분
- `ASSISTANT_SEARCH_MODE`: `auto`, `everything`, `native`
- `EVERYTHING_AUTO_START`: Everything 자동 실행 시도 여부
- `EVERYTHING_DLL_PATH`: Everything DLL 경로를 수동 지정할 때 사용

### 3. 실행

GUI 실행:

```powershell
python local_assistant.py
```

CLI 실행:

```powershell
python local_assistant.py --cli
```

## 사용 흐름

1. 앱을 실행하면 검색 엔진 초기화 후 메인 창이 열립니다.
2. 검색창에 자연어로 파일 요청을 입력합니다.
3. 결과 카드를 보고 필요한 항목을 선택합니다.
4. `열기`, `압축`, `경로 보기`, `폴더 열기` 같은 액션을 이어서 수행합니다.
5. 처리 결과는 하단 토스트 메시지로 짧게 표시됩니다.

## 기술 스택

- Python
- CustomTkinter
- tkinter
- pystray
- Pillow
- python-dotenv
- pydantic
- rapidfuzz
- regex
- KoNLPy

## 프로젝트 구조

```text
MyAgent/
├── apps/
│   └── local/
│       ├── cli.py
│       └── session.py
├── core/
│   ├── adapters/
│   ├── interfaces/
│   ├── models/
│   ├── services/
│   ├── utils/
│   ├── viewmodels/
│   ├── env.py
│   ├── query_parser.py
│   └── search_engine.py
├── gui/
│   ├── widgets/
│   │   ├── result_list.py
│   │   └── search_bar.py
│   ├── app.py
│   ├── main_window.py
│   ├── startup.py
│   └── tray_controller.py
├── libs/
│   └── Everything64.dll
├── .env.example
├── local_assistant.py
├── myagent_gui.spec
├── README.md
└── requirements.txt
```

## 핵심 시나리오 예시

1. `최근에 수정한 pdf 보여줘`
2. `다운로드 폴더에서 zip 빼고 찾아줘`
3. `이번 주 수정한 파일 3개만 보여줘`
4. `회의록 관련 엑셀 찾아줘`
5. `찾은 파일들 압축해줘`

## 주의사항

- `.env` 의 `ASSISTANT_ROOTS` 가 비어 있으면 검색이 동작하지 않습니다.
- `Everything` 이 설치되어 있지 않거나 실행할 수 없으면 자동으로 native 검색으로 전환됩니다.
- `ASSISTANT_SEARCH_MODE=everything` 으로 강제해도 런타임 문제가 있으면 안정성을 위해 native 검색으로 전환될 수 있습니다.
- GUI 실행에는 `customtkinter`, `pystray`, `Pillow` 가 필요합니다. 없으면 `python local_assistant.py --cli` 로 실행할 수 있습니다.
- 패키징 실행 파일 환경에서는 `.env` 가 실행 파일과 같은 위치에 있어야 합니다.
- 메인 창을 닫으면 기본적으로 앱이 종료되지 않고 시스템 트레이로 숨겨집니다.
