from __future__ import annotations

from typing import Callable

from PIL import Image, ImageDraw
import pystray


class TrayController:
    def __init__(self, on_show: Callable[[], None], on_quit: Callable[[], None]) -> None:
        self._on_show = on_show
        self._on_quit = on_quit
        self._icon = pystray.Icon(
            "MyAgent",
            self._create_icon_image(),
            "MyAgent",
            menu=pystray.Menu(
                pystray.MenuItem("열기", self._handle_show, default=True),
                pystray.MenuItem("종료", self._handle_quit),
            ),
        )

    def start(self) -> None:
        self._icon.run_detached()

    def stop(self) -> None:
        try:
            self._icon.stop()
        except Exception:
            pass

    def _handle_show(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        _ = icon, item
        self._on_show()

    def _handle_quit(self, icon: pystray.Icon, item: pystray.MenuItem) -> None:
        _ = icon, item
        self._on_quit()

    def _create_icon_image(self) -> Image.Image:
        image = Image.new("RGBA", (64, 64), (243, 244, 246, 255))
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((8, 8, 56, 56), radius=14, fill=(37, 99, 235, 255))
        draw.rectangle((18, 18, 46, 46), fill=(255, 255, 255, 255))
        draw.rectangle((24, 24, 40, 40), fill=(37, 99, 235, 255))
        return image
