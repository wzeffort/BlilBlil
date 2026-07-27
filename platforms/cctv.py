import json
import os
import subprocess
import time
import tkinter as tk
from tkinter import ttk, messagebox
import requests
from bs4 import BeautifulSoup
from core.downloader import BaseDownloader, DownloadResult
from core.utils import get_ffmpeg_path, ensure_dir


class CCTV(BaseDownloader):
    name = "CCTV"
    icon = "📡"
    description = "CCTV video downloader"

    def create_tab(self, parent):
        frame = ttk.Frame(parent, padding=10)
        ttk.Label(frame, text="CCTV", font=("", 16, "bold")).pack(anchor="w")
        ttk.Label(frame, text=f"{self.icon} {self.description}").pack(anchor="w", pady=(0, 10))
        ttk.Label(frame, text="视频地址:").pack(anchor="w")
        self.url_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.url_var, width=60).pack(fill="x", pady=5)
        self.create_download_controls(
            frame, self._on_download
        ).pack(anchor="center", pady=10)
        self.create_status_label(frame)
        return frame

    def _on_download(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showerror("错误", "请输入视频地址")
            return
        output_dir = self.get_output_dir("cctv")
        self.start_download(url, output_dir)

    def download(self, url, output_dir, **kwargs):
        try:
            self._set_status("正在解析 CCTV 视频...")
            res = requests.get(url, timeout=15)
            data = json.loads(res.text)
            hls_url = data["hls_url"]

            self._set_status("正在下载并合并...")
            ensure_dir(output_dir)
            output_path = os.path.join(output_dir, "cctv_video.mp4")
            ffmpeg = get_ffmpeg_path(kwargs.get("config"))
            if not ffmpeg:
                return DownloadResult(False, "未找到 FFmpeg")
            cmd = [ffmpeg, "-i", hls_url, "-c", "copy", output_path]
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            while process.poll() is None:
                if self._get_cancel_event().is_set():
                    process.terminate()
                    process.wait(timeout=5)
                    self._raise_if_cancelled()
                time.sleep(0.2)
            _, stderr = process.communicate()
            if process.returncode == 0:
                return DownloadResult(True, "Download complete", output_path)
            return DownloadResult(False, stderr.decode(errors="replace"))
        except Exception as e:
            self._raise_if_cancelled()
            return DownloadResult(False, str(e))
