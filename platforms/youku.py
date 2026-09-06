import os
import re
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox
from core.downloader import BaseDownloader, DownloadResult
from core.instruction_panel import InstructionPanel
from core.utils import get_ffmpeg_path, ensure_dir


class Youku(BaseDownloader):
    name = "优酷"
    icon = "🎞"
    description = "优酷视频下载"

    TIP = "支持：v.youku.com/v_show/id_xxx、youku.com/v_show/id_xxx"

    @staticmethod
    def _normalize_url(url):
        from urllib.parse import unquote

        ids = set(re.findall(
            r"https?://(?:v\.)?youku\.com/v_show/id_([A-Za-z0-9=]+)\.html",
            unquote(url).replace("\\_", "_"),
        ))
        if len(ids) != 1:
            raise ValueError("请粘贴一个优酷视频播放页链接")
        return f"https://v.youku.com/v_show/id_{ids.pop()}.html"

    def create_tab(self, parent):
        frame = ttk.Frame(parent, padding=10)
        ttk.Label(frame, text="优酷", font=("", 16, "bold")).pack(anchor="w")
        ttk.Label(frame, text=f"{self.icon} {self.description}").pack(anchor="w", pady=(0, 4))
        ttk.Label(frame, text="仅支持非 VIP 普通视频；复制播放页链接到下方：").pack(anchor="w")
        self.url_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.url_var, width=60).pack(fill="x", pady=5)
        ttk.Label(frame, text=self.TIP, foreground="#6c757d", font=("", 8)).pack(anchor="w", pady=(0, 6))
        self.create_download_controls(
            frame, self._on_download
        ).pack(anchor="center", pady=10)
        self.create_status_label(frame)
        InstructionPanel(
            frame,
            steps=[
                "在浏览器中打开要下载的优酷普通视频，并选择目标集数。",
                "复制地址栏中的完整链接，粘贴到上方后点击下载。",
                "仅支持非 VIP 视频；下载在后台执行，可点击停止下载。",
            ],
            image_name="优酷下载说明.png",
        ).pack(fill="both", expand=True, pady=(8, 0))
        return frame

    def _on_download(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showerror("错误", "请输入视频地址")
            return
        output_dir = self.get_output_dir("youku")
        self.start_download(url, output_dir)

    def _validate_output(self, path, config):
        if not os.path.isfile(path) or os.path.getsize(path) == 0:
            raise RuntimeError("优酷下载未生成有效文件")
        ffmpeg = get_ffmpeg_path(config)
        if not ffmpeg:
            raise RuntimeError("未找到 FFmpeg，无法校验音视频")
        result = subprocess.run(
            [ffmpeg, "-v", "error", "-i", path, "-map", "0:v:0", "-map", "0:a:0",
             "-t", "0", "-f", "null", "-"],
            capture_output=True, timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode:
            raise RuntimeError("优酷下载文件无法解析或缺少音视频轨")

    def download(self, url, output_dir, **kwargs):
        try:
            from yt_dlp import YoutubeDL

            url = self._normalize_url(url)
            config = kwargs.get("config")
            self._raise_if_cancelled()
            ensure_dir(output_dir)
            options = {
                "outtmpl": os.path.join(output_dir, "%(title)s [%(id)s].%(ext)s"),
                "format": "best",
                "noplaylist": True,
                "skip_unavailable_fragments": False,
                "socket_timeout": 10,
                "retries": 2,
                "fragment_retries": 2,
                "extractor_retries": 1,
            }
            options.update(self.get_yt_dlp_runtime_options(config))
            ffmpeg = get_ffmpeg_path(config)
            if ffmpeg:
                options["ffmpeg_location"] = ffmpeg
            self._set_status("正在解析并下载优酷正片...")
            with YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=True)
                output_path = ydl.prepare_filename(info)
            self._raise_if_cancelled()
            self._set_status("正在校验优酷音视频...")
            self._validate_output(output_path, config)
            return DownloadResult(True, "下载完成", output_path)
        except Exception as error:
            self._raise_if_cancelled()
            return DownloadResult(False, f"优酷下载失败：{error}")
