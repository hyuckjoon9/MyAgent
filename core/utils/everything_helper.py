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


EVERYTHING_INSTALL_URL = "https://www.voidtools.com/ko-kr/downloads/"
REGISTRY_CANDIDATES = (
    (r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\Everything.exe", ""),
    (r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\Everything.exe", ""),
    (r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Everything", "InstallLocation"),
    (r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\Everything", "InstallLocation"),
    (r"SOFTWARE\voidtools\Everything", "InstallFolder"),
    (r"SOFTWARE\WOW6432Node\voidtools\Everything", "InstallFolder"),
)
IPC_TEST_TIMEOUT_SECONDS = 3
IPC_READY_WAIT_SECONDS = 10
IPC_READY_RETRY_SECONDS = 1


@dataclass
class EverythingRuntimeInfo:
    installed: bool
    exe_path: Path | None
    dll_path: Path | None
    es_exe_path: Path | None
    is_running: bool
    ipc_ready: bool
    was_started: bool = False
    spawn_pid: int | None = None
    existing_pid: int | None = None
    status_message: str = ""


@dataclass
class EverythingProcessInfo:
    pid: int
    exe_path: Path | None = None


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

    if winreg is not None:
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


def find_es_exe() -> Path | None:
    env_es = _normalize_candidate(os.getenv("ES_EXE_PATH", ""))
    if env_es is not None:
        return env_es

    candidates = [
        PROJECT_ROOT / "libs" / "es" / "es.exe",
        PROJECT_ROOT / "libs" / "es.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def get_running_everything_process() -> EverythingProcessInfo | None:
    if os.name != "nt":
        return None
    command = [
        "powershell",
        "-NoProfile",
        "-Command",
        "Get-Process -Name Everything -ErrorAction SilentlyContinue | "
        "Select-Object -First 1 Id,Path | ConvertTo-Json -Compress",
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    raw = result.stdout.strip()
    if not raw:
        return None
    try:
        import json

        data = json.loads(raw)
    except Exception:
        return None
    pid = int(data.get("Id", 0) or 0)
    if pid <= 0:
        return None
    exe_path = _normalize_candidate(str(data.get("Path", "") or ""))
    return EverythingProcessInfo(pid=pid, exe_path=exe_path)


def is_everything_running() -> bool:
    return get_running_everything_process() is not None


def test_everything_ipc(es_exe_path: Path | None, timeout_seconds: int = IPC_TEST_TIMEOUT_SECONDS) -> tuple[bool, str]:
    if es_exe_path is None:
        return False, "es.exe 경로를 찾지 못했습니다."
    try:
        result = subprocess.run(
            [str(es_exe_path), "-timeout", str(timeout_seconds * 1000), "-n", "1", "*"],
            capture_output=True,
            text=True,
            timeout=max(timeout_seconds, 1) + 1,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, f"es.exe IPC 확인이 {timeout_seconds}초 안에 완료되지 않았습니다."
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"es.exe 실행에 실패했습니다: {exc}"
    if result.returncode == 0:
        return True, ""
    detail = result.stderr.strip() or result.stdout.strip() or f"exit={result.returncode}"
    return False, detail


def terminate_everything_process(pid: int | None) -> bool:
    if pid is None or pid <= 0:
        return False
    try:
        result = subprocess.run(
            ["taskkill", "/PID", str(pid), "/F"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0


def _start_everything(exe_path: Path) -> subprocess.Popen[bytes] | None:
    try:
        return subprocess.Popen(
            [str(exe_path), "-startup"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            cwd=str(exe_path.parent),
        )
    except OSError:
        return None


def ensure_everything_runtime(auto_start: bool = True) -> EverythingRuntimeInfo:
    exe_path = find_everything_exe()
    dll_path = find_everything_dll(exe_path)
    es_exe_path = find_es_exe()
    installed = exe_path is not None
    if not installed:
        return EverythingRuntimeInfo(
            installed=False,
            exe_path=None,
            dll_path=dll_path,
            es_exe_path=es_exe_path,
            is_running=False,
            ipc_ready=False,
            status_message="Everything 설치를 찾지 못했습니다.",
        )

    process_info = get_running_everything_process()
    if process_info is not None:
        ipc_ready, ipc_detail = test_everything_ipc(es_exe_path, timeout_seconds=IPC_TEST_TIMEOUT_SECONDS)
        if ipc_ready:
            return EverythingRuntimeInfo(
                installed=True,
                exe_path=exe_path,
                dll_path=dll_path,
                es_exe_path=es_exe_path,
                is_running=True,
                ipc_ready=True,
                existing_pid=process_info.pid,
                status_message="기존 Everything 프로세스와 IPC 연결에 성공했습니다.",
            )
        terminate_everything_process(process_info.pid)
        time.sleep(0.5)
        process_info = None
        status_prefix = f"기존 Everything 프로세스의 IPC 연결에 실패해 종료했습니다: {ipc_detail}"
    else:
        status_prefix = "실행 중인 Everything 프로세스가 없어 새로 시작합니다."

    if not auto_start:
        return EverythingRuntimeInfo(
            installed=True,
            exe_path=exe_path,
            dll_path=dll_path,
            es_exe_path=es_exe_path,
            is_running=False,
            ipc_ready=False,
            status_message=status_prefix,
        )

    spawned_process = _start_everything(exe_path)
    if spawned_process is None:
        return EverythingRuntimeInfo(
            installed=True,
            exe_path=exe_path,
            dll_path=dll_path,
            es_exe_path=es_exe_path,
            is_running=False,
            ipc_ready=False,
            status_message=f"{status_prefix} Everything 실행에 실패했습니다.",
        )

    deadline = time.monotonic() + IPC_READY_WAIT_SECONDS
    last_error = ""
    while time.monotonic() < deadline:
        ipc_ready, last_error = test_everything_ipc(es_exe_path, timeout_seconds=IPC_TEST_TIMEOUT_SECONDS)
        if ipc_ready:
            return EverythingRuntimeInfo(
                installed=True,
                exe_path=exe_path,
                dll_path=dll_path,
                es_exe_path=es_exe_path,
                is_running=True,
                ipc_ready=True,
                was_started=True,
                spawn_pid=spawned_process.pid,
                status_message="Everything를 백그라운드로 시작하고 IPC 연결을 확인했습니다.",
            )
        time.sleep(IPC_READY_RETRY_SECONDS)

    return EverythingRuntimeInfo(
        installed=True,
        exe_path=exe_path,
        dll_path=dll_path,
        es_exe_path=es_exe_path,
        is_running=is_everything_running(),
        ipc_ready=False,
        was_started=True,
        spawn_pid=spawned_process.pid,
        status_message=f"Everything를 시작했지만 {IPC_READY_WAIT_SECONDS}초 안에 IPC 연결에 실패했습니다: {last_error or 'unknown error'}",
    )
