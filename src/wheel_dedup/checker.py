import importlib.metadata
from typing import Dict, Optional

from .parser import normalize


class InstalledChecker:
    def __init__(self) -> None:
        self._cache: Dict[str, Optional[str]] = {}
        self._loaded = False

    def _load(self) -> None:
        if self._loaded:
            return
        for dist in importlib.metadata.distributions():
            name = dist.metadata["Name"]
            if name:
                version = dist.metadata["Version"]
                self._cache[normalize(name)] = version
        self._loaded = True

    def get_installed_version(self, name: str) -> Optional[str]:
        self._load()
        return self._cache.get(normalize(name))

    def is_installed(self, name: str) -> bool:
        return self.get_installed_version(name) is not None

    def get_all_installed(self) -> Dict[str, str]:
        self._load()
        return {k: v for k, v in self._cache.items() if v is not None}
