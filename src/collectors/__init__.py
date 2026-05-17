from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional, List
import hashlib
import json


@dataclass
class CollectedData:
    title: str
    content: str = ""
    url: str = ""
    author: str = ""
    published_at: Any = None
    raw_data: Any = None

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(
            (self.title + self.content + self.url).encode()
        ).hexdigest()[:32]


@dataclass
class CollectionResult:
    status: str  # "success", "error", "no_data"
    items: List[CollectedData] = field(default_factory=list)
    summary: str = ""
    error: str = ""
    duration_ms: float = 0.0


class BaseCollector(ABC):
    type_id: str = ""
    name: str = ""
    description: str = ""
    config_schema: dict = {}

    def __init__(self, config: dict):
        self.config = config

    @abstractmethod
    def collect(self) -> CollectionResult:
        ...


COLLECTOR_REGISTRY: dict[str, type[BaseCollector]] = {}


def register_collector(cls: type[BaseCollector]):
    COLLECTOR_REGISTRY[cls.type_id] = cls
    return cls


def get_collector(type_id: str) -> type[BaseCollector]:
    cls = COLLECTOR_REGISTRY.get(type_id)
    if not cls:
        raise ValueError(f"Unknown collector type: {type_id}")
    return cls


def get_all_collector_types() -> list[dict]:
    return [
        {"type_id": cls.type_id, "name": cls.name, "description": cls.description, "config_schema": cls.config_schema}
        for cls in COLLECTOR_REGISTRY.values()
    ]


import importlib
import pkgutil
import logging
logger = logging.getLogger("collectors")
for importer, modname, ispkg in pkgutil.iter_modules(__path__):
    if modname != "__init__" and not modname.startswith("_"):
        try:
            importlib.import_module(f".{modname}", __package__)
        except Exception as e:
            logger.warning(f"Failed to load collector {modname}: {e}")
