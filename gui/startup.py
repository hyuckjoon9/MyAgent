from __future__ import annotations

from dataclasses import dataclass, field

from core.env import load_project_env
from core.search_engine import get_engine_notices, get_search_manager


@dataclass
class StartupContext:
    engine_name: str
    notices: list[str] = field(default_factory=list)


def load_startup_context() -> StartupContext:
    load_project_env()
    manager = get_search_manager()
    notices = get_engine_notices()
    return StartupContext(engine_name=manager.engine_name(), notices=notices)
