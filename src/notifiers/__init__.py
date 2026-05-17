from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any
import importlib
import pkgutil
import logging

logger = logging.getLogger("notifiers")


@dataclass
class NotificationResult:
    success: bool
    message: str = ""


class BaseNotifier(ABC):
    channel_type: str = ""
    name: str = ""
    config_schema: dict = {}

    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def send(self, title: str, message: str, severity: str, monitor_name: str = "",
             check_details: dict = None) -> NotificationResult:
        ...


NOTIFIER_REGISTRY: dict[str, type[BaseNotifier]] = {}


def register_notifier(notifier_class: type[BaseNotifier]):
    NOTIFIER_REGISTRY[notifier_class.channel_type] = notifier_class
    logger.info(f"Registered notifier: {notifier_class.channel_type}")
    return notifier_class


def get_notifier(channel_type: str) -> type[BaseNotifier]:
    cls = NOTIFIER_REGISTRY.get(channel_type)
    if not cls:
        raise ValueError(f"Unknown notifier type: {channel_type}")
    return cls


def get_all_notifier_types() -> list[dict]:
    return [
        {"type_id": cls.channel_type, "name": cls.name, "config_schema": cls.config_schema}
        for cls in NOTIFIER_REGISTRY.values()
    ]


# Auto-discover all notifier plugins
for importer, modname, ispkg in pkgutil.iter_modules(__path__):
    if modname != "__init__" and not modname.startswith("_"):
        try:
            importlib.import_module(f".{modname}", __package__)
        except Exception as e:
            logger.warning(f"Failed to load notifier plugin {modname}: {e}")
