import os
import sys
from pathlib import Path

from dotenv import load_dotenv


def _runtime_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


PROJECT_ROOT = _runtime_root()
ENV_PATH = PROJECT_ROOT / ".env"


def load_project_env() -> Path:
    load_dotenv(ENV_PATH)
    return ENV_PATH


def load_roots() -> list[Path]:
    load_project_env()
    raw = os.getenv("ASSISTANT_ROOTS", "").strip()
    if not raw:
        raise RuntimeError("ASSISTANT_ROOTS is not set.")

    roots: list[Path] = []
    for item in raw.split(";"):
        candidate = Path(item.strip()).expanduser()
        if candidate.exists():
            roots.append(candidate)

    if not roots:
        raise RuntimeError("No valid paths found in ASSISTANT_ROOTS.")
    return roots
