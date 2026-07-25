import abc
from dataclasses import dataclass
from typing import Optional


@dataclass
class DownloadResult:
    success: bool
    message: str
    file_path: Optional[str] = None


class BaseDownloader(abc.ABC):
    name: str = ""
    icon: str = ""
    description: str = ""

    @abc.abstractmethod
    def create_tab(self, parent) -> object:
        pass

    def validate_url(self, url: str) -> bool:
        return bool(url and url.startswith("http"))

    @abc.abstractmethod
    def download(self, url: str, output_dir: str, **kwargs) -> DownloadResult:
        pass
