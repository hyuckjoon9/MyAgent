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
_RUNTIME_ROOTS_OVERRIDE: list[Path] | None = None


def load_project_env() -> Path:
    load_dotenv(ENV_PATH)
    return ENV_PATH


def _load_env_roots() -> list[Path]:
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


def set_runtime_roots(roots: list[Path]) -> None:
    global _RUNTIME_ROOTS_OVERRIDE

    normalized: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        candidate = Path(root).expanduser()
        if not candidate.exists():
            continue
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved in seen:
            continue
        normalized.append(resolved)
        seen.add(resolved)
    _RUNTIME_ROOTS_OVERRIDE = normalized


def clear_runtime_roots() -> None:
    global _RUNTIME_ROOTS_OVERRIDE
    _RUNTIME_ROOTS_OVERRIDE = None


def load_roots() -> list[Path]:
    if _RUNTIME_ROOTS_OVERRIDE is not None:
        if not _RUNTIME_ROOTS_OVERRIDE:
            raise RuntimeError("No runtime search roots selected.")
        return _RUNTIME_ROOTS_OVERRIDE[:]
    return _load_env_roots()
