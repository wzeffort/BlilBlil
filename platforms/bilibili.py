import os
import tkinter as tk
from tkinter import ttk, messagebox
from core.downloader import BaseDownloader, DownloadResult
from core.utils import get_ffmpeg_path, ensure_dir


class Bilibili(BaseDownloader):
    name = "B站"
    icon = "🎬"
    description = "B站视频下载"

    def create_tab(self, parent):
        frame = ttk.Frame(parent, padding=10)
        ttk.Label(frame, text="B站", font=("", 16, "bold")).pack(anchor="w")
        ttk.Label(frame, text=f"{self.icon} {self.description}").pack(anchor="w", pady=(0, 2))
        ttk.Label(frame, text="视频地址:").pack(anchor="w")
        self.url_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.url_var, width=60).pack(fill="x", pady=3)
        ttk.Button(frame, text="下载", command=self._on_download).pack(pady=8)
        return frame

    def _on_download(self):
        url = self.url_var.get().strip()
        if not self.validate_url(url):
            messagebox.showerror("错误", "请输入有效的视频地址")
            return
        output_dir = self._get_output_dir()
        self.start_download(url, output_dir)

    def _get_output_dir(self):
        return self.get_output_dir("bilibili")

    def download(self, url, output_dir, **kwargs):
        try:
            ffmpeg = get_ffmpeg_path(kwargs.get("config"))
            if not ffmpeg:
                return DownloadResult(
                    False,
                    "未找到 FFmpeg，无法合并 B 站音视频。"
                    "\n请将 ffmpeg.exe 放到 ffmpeg 文件夹，或在配置中指定路径。",
                )

            from yt_dlp import YoutubeDL

            ensure_dir(output_dir)
            options = {
                "outtmpl": os.path.join(output_dir, "%(title)s [%(id)s].%(ext)s"),
                "noplaylist": True,
                "nocheckcertificate": True,
                "format": "bv*+ba/b",
                "ffmpeg_location": ffmpeg,
                "merge_output_format": "mp4",
            }

            with YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=True)
                output_path = ydl.prepare_filename(info)
                merged_path = os.path.splitext(output_path)[0] + ".mp4"
                if os.path.exists(merged_path):
                    output_path = merged_path
                return DownloadResult(True, "下载完成", output_path)
        except ImportError:
            return DownloadResult(
                False,
                "缺少 yt-dlp，请执行：pip install -r requirements.txt",
            )
        except Exception as e:
            return DownloadResult(False, f"下载失败: {e}")
