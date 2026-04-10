from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DriveItem:
    name: str
    root: Path
    label: str
    is_ready: bool = True

