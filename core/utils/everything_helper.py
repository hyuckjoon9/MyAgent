from __future__ import annotations

import os
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

try:
    import winreg
except ImportError:  # pragma: no cover - Windows only
    winreg = None  # type: ignore[assignment]

from core.env import PROJECT_ROOT


EVERYTHING_INSTALL_URL = "https://www.voidtools.com/downloads/"
REGISTRY_CANDIDATES = (
    (r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\Everything.exe", ""),
    (r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\Everything.exe", ""),
    (r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Everything", "InstallLocation"),
    (r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\Everything", "InstallLocation"),
    (r"SOFTWARE\voidtools\Everything", "InstallFolder"),
    (r"SOFTWARE\WOW6432Node\voidtools\Everything", "InstallFolder"),
)


@dataclass
class EverythingRuntimeInfo:
    installed: bool
    exe_path: Path | None
    dll_path: Path | None
    is_running: bool
    was_started: bool = False
    status_message: str = ""


def _normalize_candidate(candidate: str) -> Path | None:
    if not candidate:
        return None
    normalized = candidate.strip().strip('"')
    if not normalized:
        return None
    path = Path(normalized)
    if path.is_dir():
        exe_candidate = path / "Everything.exe"
        return exe_candidate if exe_candidate.exists() else None
    return path if path.exists() else None


def _read_registry_path(root: int, key_path: str, value_name: str) -> Path | None:
    if winreg is None:
        return None
    try:
        with winreg.OpenKey(root, key_path) as key:
            value, _ = winreg.QueryValueEx(key, value_name)
    except OSError:
        return None
    return _normalize_candidate(str(value))


def find_everything_exe() -> Path | None:
    env_exe = _normalize_candidate(os.getenv("EVERYTHING_EXE_PATH", ""))
    if env_exe is not None:
        return env_exe

    if winreg is None:
        bundle_candidate = PROJECT_ROOT / "libs" / "Everything.exe"
        return bundle_candidate if bundle_candidate.exists() else None

    for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for key_path, value_name in REGISTRY_CANDIDATES:
            candidate = _read_registry_path(root, key_path, value_name)
            if candidate is not None:
                return candidate

    bundle_candidate = PROJECT_ROOT / "libs" / "Everything.exe"
    if bundle_candidate.exists():
        return bundle_candidate
    return None


def find_everything_dll(exe_path: Path | None = None) -> Path | None:
    env_dll = _normalize_candidate(os.getenv("EVERYTHING_DLL_PATH", ""))
    if env_dll is not None:
        return env_dll

    arch_specific = "Everything64.dll" if os.environ.get("PROCESSOR_ARCHITECTURE", "").endswith("64") else "Everything32.dll"
    candidates = [
        PROJECT_ROOT / "libs" / arch_specific,
        PROJECT_ROOT / "libs" / "Everything64.dll",
        PROJECT_ROOT / "libs" / "Everything32.dll",
    ]
    if exe_path is not None:
        candidates.extend(
            [
                exe_path.with_name(arch_specific),
                exe_path.with_name("Everything64.dll"),
                exe_path.with_name("Everything32.dll"),
            ]
        )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def is_everything_running() -> bool:
    if os.name != "nt":
        return False
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq Everything.exe"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return "Everything.exe" in result.stdout


def _start_everything(exe_path: Path) -> bool:
    try:
        subprocess.Popen(
            [str(exe_path), "-startup"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=str(exe_path.parent),
        )
    except OSError:
        return False

    for _ in range(10):
        time.sleep(0.4)
        if is_everything_running():
            return True
    return False


def ensure_everything_runtime(auto_start: bool = True) -> EverythingRuntimeInfo:
    exe_path = find_everything_exe()
    dll_path = find_everything_dll(exe_path)
    installed = exe_path is not None or dll_path is not None
    running = is_everything_running()
    started = False
    status = ""

    if installed and not running and auto_start and exe_path is not None:
        started = _start_everything(exe_path)
        running = running or started
        if started:
            status = "Everything 프로세스를 자동 실행했습니다."
        else:
            status = "Everything 설치는 감지했지만 자동 실행에는 실패했습니다."
    elif installed and running:
        status = "Everything 실행 상태를 확인했습니다."
    elif installed:
        status = "Everything 설치는 감지했지만 실행 중이 아닙니다."
    else:
        status = "Everything 설치를 찾지 못했습니다."

    return EverythingRuntimeInfo(
        installed=installed,
        exe_path=exe_path,
        dll_path=dll_path,
        is_running=running,
        was_started=started,
        status_message=status,
    )
