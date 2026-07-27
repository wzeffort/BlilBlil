import os
import tkinter as tk
from tkinter import ttk, messagebox
from core.downloader import BaseDownloader, DownloadResult
from core.utils import ensure_dir


class YouTube(BaseDownloader):
    name = "YouTube"
    icon = "▶"
    description = "YouTube video downloader (yt-dlp)"

    def create_tab(self, parent):
        frame = ttk.Frame(parent, padding=10)
        ttk.Label(frame, text="YouTube", font=("", 16, "bold")).pack(anchor="w")
        ttk.Label(frame, text=f"{self.icon} {self.description}").pack(anchor="w", pady=(0, 10))
        ttk.Label(frame, text="视频地址:").pack(anchor="w")
        self.url_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.url_var, width=60).pack(fill="x", pady=5)
        ttk.Label(frame, text="格式 ID (留空自动选择最佳):").pack(anchor="w")
        self.fmt_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.fmt_var, width=20).pack(anchor="w", pady=5)
        button_row = ttk.Frame(frame)
        button_row.pack(anchor="w", pady=5)
        ttk.Button(button_row, text="列出格式", command=self._list_formats).pack(side="left", padx=(0, 5))
        self.create_download_controls(
            button_row, self._on_download
        ).pack(side="left")
        self.create_status_label(frame)
        return frame

    def _list_formats(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showerror("Error", "Please enter a URL first")
            return
        try:
            from yt_dlp import YoutubeDL
            with YoutubeDL({"listformats": True}) as ydl:
                ydl.download([url])
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_download(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showerror("错误", "请输入视频地址")
            return
        output_dir = self.get_output_dir("youtube")
        self.start_download(url, output_dir, format_id=self.fmt_var.get())

    def download(self, url, output_dir, **kwargs):
        try:
            from yt_dlp import YoutubeDL
            self._set_status("正在解析 YouTube 视频...")
            ensure_dir(output_dir)
            fmt = kwargs.get("format_id", "").strip()
            opts = {
                "outtmpl": os.path.join(output_dir, "%(title)s.%(ext)s"),
                "nocheckcertificate": True,
            }
            opts.update(
                self.get_yt_dlp_runtime_options(kwargs.get("config"))
            )
            if fmt:
                opts["format"] = fmt
            else:
                opts["format"] = "bv+ba/b"

            with YoutubeDL(opts) as ydl:
                self._set_status("正在下载...")
                info = ydl.extract_info(url, download=True)
                title = info.get("title", "youtube_video")
                ext = info.get("ext", "mp4")
                path = os.path.join(output_dir, f"{title}.{ext}")
                return DownloadResult(True, "Download complete", path)
        except ImportError:
            return DownloadResult(False, "yt-dlp not installed. Run: pip install yt-dlp")
        except Exception as e:
            self._raise_if_cancelled()
            return DownloadResult(False, str(e))
