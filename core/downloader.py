import abc
import os
import threading
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

    def start_download(self, url, output_dir, **kwargs):
        app = getattr(self, "app", None)
        if app:
            app.progress["mode"] = "indeterminate"
            app.progress.start(15)
            if "config" not in kwargs:
                kwargs["config"] = app.get_config()
        thread = threading.Thread(
            target=self._download_thread,
            args=(url, output_dir),
            kwargs=kwargs,
            daemon=True,
        )
        thread.start()

    def get_output_dir(self, platform_name: str) -> str:
        app = getattr(self, "app", None)
        if app:
            try:
                base_dir = app.get_config()["download_dir"]
                if base_dir:
                    return os.path.join(base_dir, platform_name)
            except (KeyError, TypeError, AttributeError):
                pass
        return os.path.join(os.getcwd(), "downloads", platform_name)

    def _download_thread(self, url, output_dir, **kwargs):
        try:
            result = self.download(url, output_dir, **kwargs)
        except Exception as exc:
            result = DownloadResult(False, f"下载失败: {exc}")
        app = getattr(self, "app", None)
        if app:
            try:
                app.root.after(250, lambda r=result: app._on_download_done(r))
            except Exception:
                pass
