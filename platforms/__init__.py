import importlib
import pkgutil
from core.downloader import BaseDownloader

_platforms: list[type[BaseDownloader]] = []


def discover_platforms():
    global _platforms
    if _platforms:
        return _platforms
    package = importlib.import_module("platforms")
    for importer, modname, ispkg in pkgutil.iter_modules(package.__path__):
        if modname.startswith("_"):
            continue
        module = importlib.import_module(f"platforms.{modname}")
        for attr in dir(module):
            cls = getattr(module, attr)
            if isinstance(cls, type) and issubclass(cls, BaseDownloader) and cls is not BaseDownloader:
                _platforms.append(cls)
    return _platforms
