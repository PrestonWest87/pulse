from abc import ABC, abstractmethod
from dataclasses import dataclass
import importlib
import pkgutil
import logging

logger = logging.getLogger("outbounds")


@dataclass
class DispatchResult:
    success: bool
    message: str = ""


class BaseOutbound(ABC):
    channel_type: str = ""
    name: str = ""
    config_schema: dict = {}

    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def send(self, title: str, message: str, severity: str, source_name: str = "",
             item_url: str = "") -> DispatchResult:
        ...


OUTBOUND_REGISTRY: dict[str, type[BaseOutbound]] = {}


def register_outbound(cls: type[BaseOutbound]):
    OUTBOUND_REGISTRY[cls.channel_type] = cls
    return cls


def get_outbound(channel_type: str) -> type[BaseOutbound]:
    cls = OUTBOUND_REGISTRY.get(channel_type)
    if not cls:
        raise ValueError(f"Unknown outbound type: {channel_type}")
    return cls


def get_all_outbound_types() -> list[dict]:
    return [
        {"type_id": cls.channel_type, "name": cls.name, "config_schema": cls.config_schema}
        for cls in OUTBOUND_REGISTRY.values()
    ]


for importer, modname, ispkg in pkgutil.iter_modules(__path__):
    if modname != "__init__" and not modname.startswith("_"):
        try:
            importlib.import_module(f".{modname}", __package__)
        except Exception as e:
            logger.warning(f"Failed to load outbound {modname}: {e}")
