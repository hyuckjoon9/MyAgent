from dataclasses import dataclass
from pathlib import Path


@dataclass
class IndexedPath:
    path: str
    name: str
    parent: str
    suffix: str
    is_dir: bool
    modified_ts: float
    size: int


@dataclass
class Match:
    path: Path
    kind: str
    score: float
    modified_ts: float
    size: int
    reason: str
