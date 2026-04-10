from __future__ import annotations

import ctypes
import os
from pathlib import Path

from core.viewmodels.drive_item import DriveItem


class RootService:
    def list_available_drives(self) -> list[DriveItem]:
        if os.name != "nt":
            return []

        drives: list[DriveItem] = []
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        for index in range(26):
            if not (bitmask & (1 << index)):
                continue
            letter = chr(ord("A") + index)
            root = Path(f"{letter}:/")
            if not root.exists():
                continue
            label = f"{letter}:\\"
            drives.append(DriveItem(name=label, root=root, label=label))

        return drives

