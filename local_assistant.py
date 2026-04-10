import sys

from apps.local.cli import main as cli_main


if __name__ == "__main__":
    if "--cli" in sys.argv:
        cli_main()
    else:
        try:
            from gui.app import main as gui_main
        except ModuleNotFoundError as exc:
            if exc.name in {"customtkinter", "pystray", "PIL"}:
                print(
                    "GUI 실행에 필요한 패키지가 설치되지 않았습니다. "
                    "`pip install -r requirements.txt` 후 다시 실행하거나 `python local_assistant.py --cli`를 사용하세요."
                )
                sys.exit(1)
            raise
        gui_main()
