from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional
from datetime import datetime
import importlib
import pkgutil
import logging

logger = logging.getLogger("monitors")


@dataclass
class MonitorResult:
    status: str  # "up", "down", "degraded", "error"
    status_code: Optional[int] = None
    response_time_ms: Optional[float] = None
    response_summary: Optional[str] = None
    error: Optional[str] = None
    raw_data: Any = None


class BaseMonitor(ABC):
    type_id: str = ""
    name: str = ""
    description: str = ""
    config_schema: dict = field(default_factory=dict)

    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def check(self) -> MonitorResult:
        ...

    @classmethod
    def validate_config(cls, config: dict) -> list[str]:
        return []


MONITOR_REGISTRY: dict[str, type[BaseMonitor]] = {}


def register_monitor(monitor_class: type[BaseMonitor]):
    MONITOR_REGISTRY[monitor_class.type_id] = monitor_class
    logger.info(f"Registered monitor: {monitor_class.type_id}")
    return monitor_class


def get_monitor(type_id: str) -> type[BaseMonitor]:
    cls = MONITOR_REGISTRY.get(type_id)
    if not cls:
        raise ValueError(f"Unknown monitor type: {type_id}")
    return cls


def get_all_monitor_types() -> list[dict]:
    return [
        {"type_id": cls.type_id, "name": cls.name, "description": cls.description, "config_schema": cls.config_schema}
        for cls in MONITOR_REGISTRY.values()
    ]


# Auto-discover all monitor plugins in this package
__all__ = []
for importer, modname, ispkg in pkgutil.iter_modules(__path__):
    if modname != "__init__" and not modname.startswith("_"):
        try:
            importlib.import_module(f".{modname}", __package__)
            __all__.append(modname)
            logger.debug(f"Loaded monitor plugin: {modname}")
        except Exception as e:
            logger.warning(f"Failed to load monitor plugin {modname}: {e}")
