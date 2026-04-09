# MyAgent — 플로팅 캐릭터 어시스턴트 설계 (Plan B)

## 파일 구조

```
MyAgent/
├── assistant.py            # 기존 유지 (OpenAI 백엔드)
├── local_assistant.py      # 기존 유지 (규칙 기반 백엔드)
├── requirements.txt        # PyQt6 등 추가
│
├── gui/
│   ├── __init__.py
│   ├── main.py             # 앱 진입점
│   ├── character_window.py # 플로팅 캐릭터 윈도우 (핵심)
│   ├── bubble_window.py    # 말풍선 + 입력창 팝업
│   ├── tray_icon.py        # 시스템 트레이 아이콘
│   └── worker.py           # QThread 기반 AI 호출 워커
│
├── core/
│   ├── __init__.py
│   ├── backend.py          # assistant.py / local_assistant.py 통합 어댑터
│   └── config.py           # 설정값 (위치, API 모드 등)
│
└── assets/
    ├── idle.png
    ├── thinking.png
    ├── speaking.png
    └── tray_icon.png
```

---

## 모듈별 역할

### gui/main.py
- `QApplication` 생성
- `CharacterWindow`, `TrayIcon` 인스턴스화 및 시그널 연결
- 환경 변수 검증 후 `app.exec()` 루프 진입

### gui/character_window.py
- `QWidget` 상속, 아래 플래그 조합:
  ```python
  Qt.WindowType.FramelessWindowHint
  | Qt.WindowType.WindowStaysOnTopHint
  | Qt.WindowType.Tool
  ```
- `WA_TranslucentBackground = True` (PNG 알파 채널 바탕화면으로 투과)
- `set_state(state: CharacterState)` — idle/thinking/speaking PNG 교체
- 드래그 이동: `mousePressEvent` / `mouseMoveEvent` 오버라이드
- 클릭 판별: 이동 거리 5px 이하면 클릭으로 간주 → `BubbleWindow` 토글
- 초기 위치: `QScreen.availableGeometry()` 기준 우하단

### gui/bubble_window.py
- `Qt.WindowType.Tool` 별도 윈도우 (캐릭터 윈도우와 분리)
- `paintEvent` + `QPainterPath`로 둥근 말풍선 + 꼬리 삼각형 직접 드로잉
- `QLabel` (응답 텍스트), `QLineEdit` (입력창), `QPushButton` (전송)
- `show_thinking()` — 입력창 비활성화 + "생각 중..." 표시
- `show_response(text)` — 응답 표시 + 입력창 재활성화
- Escape 키 / 포커스 이탈 시 닫힘

### gui/tray_icon.py
- `QSystemTrayIcon` — 우클릭 메뉴: 보이기/숨기기, 종료
- 더블클릭 → `CharacterWindow` 토글

### gui/worker.py
- `QThread` 상속 `AssistantWorker`
- 시그널: `response_ready(str)`, `error_occurred(str)`, `thinking_started()`
- `run()` 내부에서만 `core/backend.py` 호출 (UI 스레드 접근 금지)
- 완료 시 `deleteLater()`

### core/backend.py
- `query(user_input: str) -> str` 단일 인터페이스
- API 키 유무에 따라 OpenAI / 로컬 모드 자동 선택
- 두 백엔드의 반환 타입 차이를 이 레이어에서 정규화

### core/config.py
- `QSettings`로 창 위치, 백엔드 모드 저장/복원

---

## 인터랙션 흐름

```
사용자가 캐릭터 클릭
    → BubbleWindow 팝업
    → 텍스트 입력 후 엔터
    → show_thinking() (UI 즉시 반응)
    → AssistantWorker.start() (별도 스레드)
        → core/backend.query() 실행
        → response_ready.emit(text)
    → show_response(text)
    → CharacterState → SPEAKING
```

---

## PyQt6 투명 윈도우 주의사항

- `setAttribute(WA_TranslucentBackground)` 호출은 `setWindowFlags()` 이후, `show()` 이전에 해야 함
- `QLabel` 배경도 `setStyleSheet("background: transparent;")` 필요
- 말풍선과 캐릭터는 별도 윈도우로 분리 — 같은 위젯에 넣으면 말풍선 표시 시 캐릭터 위치 흔들림

---

## 구현 단계

| Phase | 내용 | 완료 기준 |
|-------|------|-----------|
| **1** | 투명 프레임리스 윈도우 + PNG 표시 + 드래그 + 트레이 | 캐릭터가 바탕화면 위에 떠서 드래그 이동됨 |
| **2** | 말풍선 팝업 + 로컬 백엔드 연결 + QThread | API 없이 파일 검색 결과가 말풍선에 표시됨 |
| **3** | OpenAI 백엔드 + 캐릭터 상태 전환 + 위치 저장 | 호출 중 thinking PNG, 완료 후 speaking PNG |
| **4** | 말풍선 UI 개선 + 글로벌 핫키 + pyinstaller 패키징 | 단일 .exe 실행 가능 |

---

## 추가 의존성

| 패키지 | 용도 |
|--------|------|
| `PyQt6` | GUI 전체 |
| `python-dotenv` | .env 환경 변수 로드 |
| `keyboard` (Phase 4) | 글로벌 핫키 |
