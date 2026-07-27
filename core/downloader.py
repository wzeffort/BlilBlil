import abc
import os
import threading
from dataclasses import dataclass
from typing import Optional


class DownloadCancelled(Exception):
    pass


class _YTDLPLogger:
    def __init__(self, downloader):
        self.downloader = downloader

    def debug(self, message):
        self.downloader._log(message)

    info = debug

    def warning(self, message):
        self.downloader._log(message, "warning")

    def error(self, message):
        self.downloader._log(message, "error")


@dataclass
class DownloadResult:
    success: bool
    message: str
    file_path: Optional[str] = None
    cancelled: bool = False


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
        worker = getattr(self, "_download_worker", None)
        if worker is not None and worker.is_alive():
            return
        self._get_cancel_event().clear()
        self._last_logged_percent = -5
        self._set_task_active(True)
        self._set_status("准备下载...")
        self._log(f"开始下载: {url}")
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
        self._download_worker = thread
        thread.start()

    def create_download_controls(self, parent, command):
        from tkinter import ttk

        controls = ttk.Frame(parent)
        self.download_button = ttk.Button(
            controls, text="下载", command=command
        )
        self.download_button.pack(side="left", padx=(0, 6))
        self.stop_button = ttk.Button(
            controls,
            text="停止下载",
            command=self.stop_download,
            state="disabled",
        )
        self.stop_button.pack(side="left")
        return controls

    def _get_cancel_event(self):
        event = getattr(self, "_cancel_event", None)
        if event is None:
            event = threading.Event()
            self._cancel_event = event
        return event

    def stop_download(self):
        self._get_cancel_event().set()
        self._set_status("正在停止下载...")
        self._log("用户请求停止下载", "warning")
        button = getattr(self, "stop_button", None)
        if button is not None:
            button.configure(state="disabled")

    def _raise_if_cancelled(self):
        if self._get_cancel_event().is_set():
            raise DownloadCancelled("下载已停止")

    def _run_on_ui(self, callback):
        app = getattr(self, "app", None)
        root = getattr(app, "root", None)
        if root is not None:
            try:
                root.after(0, callback)
                return
            except Exception:
                pass
        callback()

    def _set_task_active(self, active):
        def update():
            download = getattr(self, "download_button", None)
            stop = getattr(self, "stop_button", None)
            if download is not None:
                download.configure(
                    state="disabled" if active else "normal"
                )
            if stop is not None:
                stop.configure(state="normal" if active else "disabled")

        self._run_on_ui(update)

    def _log(self, message, tag="info"):
        app = getattr(self, "app", None)
        log_method = getattr(app, "log", None)
        if log_method is not None and message:
            self._run_on_ui(
                lambda: log_method(str(message), tag)
            )

    def create_status_label(self, parent):
        import tkinter as tk
        from tkinter import ttk

        self.status_var = tk.StringVar(master=parent, value="就绪")
        label = ttk.Label(
            parent,
            textvariable=self.status_var,
            foreground="#6c757d",
            font=("", 9),
        )
        label.pack(anchor="w", pady=(4, 0))
        return label

    def _set_status(self, text):
        status_var = getattr(self, "status_var", None)
        app = getattr(self, "app", None)
        log_method = getattr(app, "log", None)

        def update():
            if status_var is not None:
                status_var.set(text)
            if log_method is not None:
                log_method(text, "info")

        self._run_on_ui(update)

    def _report_progress(self, percent):
        app = getattr(self, "app", None)
        progress = getattr(app, "progress", None)
        if progress is None:
            return

        def update():
            try:
                progress.stop()
            except AttributeError:
                pass
            progress["mode"] = "determinate"
            progress["value"] = max(0, min(100, percent))

        self._run_on_ui(update)

    def _yt_dlp_progress_hook(self, data):
        self._raise_if_cancelled()
        if data.get("status") == "downloading":
            downloaded = data.get("downloaded_bytes") or 0
            total = (
                data.get("total_bytes")
                or data.get("total_bytes_estimate")
                or 0
            )
            if total:
                percent = downloaded * 100 / total
                self._report_progress(percent)
                whole = int(percent)
                if whole >= getattr(self, "_last_logged_percent", -5) + 5:
                    speed = (data.get("speed") or 0) / 1024
                    eta = data.get("eta")
                    self._log(
                        f"下载进度 {whole}% | {speed:.1f} KiB/s"
                        f" | 剩余 {eta if eta is not None else '-'} 秒"
                    )
                    self._last_logged_percent = whole
        elif data.get("status") == "finished":
            self._report_progress(100)
            self._set_status("下载完成，正在处理文件...")

    def get_yt_dlp_runtime_options(self, config=None):
        threads = 3
        if config is not None:
            try:
                threads = int(config["max_threads"])
            except (KeyError, TypeError, ValueError):
                pass
        return {
            "concurrent_fragment_downloads": max(1, min(16, threads)),
            "progress_hooks": [self._yt_dlp_progress_hook],
            "logger": _YTDLPLogger(self),
        }

    def download_response(self, response, output_path, chunk_size=262144):
        total = int(response.headers.get("Content-Length") or 0)
        downloaded = 0
        try:
            with open(output_path, "wb") as file:
                for chunk in response.iter_content(chunk_size):
                    self._raise_if_cancelled()
                    if not chunk:
                        continue
                    file.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        self._report_progress(downloaded * 100 / total)
        except DownloadCancelled:
            if os.path.exists(output_path):
                os.remove(output_path)
            raise
        return downloaded

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

    def create_background_driver(self, performance_logging=False):
        from core.browser import _make_driver

        options = {"headless": True}
        if performance_logging:
            options["performance_logging"] = True
        return _make_driver(**options)

    def _download_thread(self, url, output_dir, **kwargs):
        try:
            result = self.download(url, output_dir, **kwargs)
        except DownloadCancelled:
            result = DownloadResult(
                False, "下载已停止", cancelled=True
            )
        except Exception as exc:
            result = DownloadResult(False, f"下载失败: {exc}")
        self._set_task_active(False)
        if result.cancelled:
            self._set_status("已停止")
            self._log(result.message, "warning")
        else:
            self._set_status("完成" if result.success else "失败")
            self._log(
                result.message,
                "success" if result.success else "error",
            )
        app = getattr(self, "app", None)
        if app:
            try:
                app.root.after(250, lambda r=result: app._on_download_done(r))
            except Exception:
                pass
