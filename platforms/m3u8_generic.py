import os
import tkinter as tk
from tkinter import ttk, messagebox
import requests
from core.downloader import BaseDownloader, DownloadResult
from core.utils import get_ffmpeg_path, ensure_dir, merge_ts


class M3U8Generic(BaseDownloader):
    name = "M3U8"
    icon = "🔗"
    description = "Generic M3U8 video downloader"

    def create_tab(self, parent):
        frame = ttk.Frame(parent, padding=10)
        ttk.Label(frame, text="Generic M3U8", font=("", 16, "bold")).pack(anchor="w")
        ttk.Label(frame, text=f"{self.icon} {self.description}").pack(anchor="w", pady=(0, 10))
        ttk.Label(frame, text="M3U8 地址:").pack(anchor="w")
        self.url_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.url_var, width=60).pack(fill="x", pady=5)
        ttk.Button(frame, text="下载", command=self._on_download).pack(pady=10)
        return frame

    def _on_download(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showerror("错误", "请输入 M3U8 地址")
            return
        output_dir = os.path.join(os.getcwd(), "downloads", "m3u8")
        self.start_download(url, output_dir)

    def download(self, url, output_dir, **kwargs):
        try:
            res = requests.get(url, timeout=15)
            lines = res.text.strip().split("\n")
            ts_urls = [line for line in lines if line and not line.startswith("#")]

            if not ts_urls:
                return DownloadResult(False, "No ts segments found in m3u8")

            base_url = url.rsplit("/", 1)[0] + "/"
            ensure_dir(output_dir)
            filelist = os.path.join(output_dir, "filelist.txt")

            with open(filelist, "w") as f:
                for ts in ts_urls:
                    ts_url = ts if ts.startswith("http") else base_url + ts
                    name = ts.split("/")[-1].split("?")[0]
                    f.write(f"file '{name}'\n")
                    r = requests.get(ts_url, stream=True, timeout=30)
                    with open(os.path.join(output_dir, name), "wb") as f2:
                        f2.write(r.content)

            output_path = os.path.join(output_dir, "output.mp4")
            ffmpeg = get_ffmpeg_path(kwargs.get("config"))
            if merge_ts(filelist, output_path, ffmpeg):
                for f in os.listdir(output_dir):
                    if f.endswith(".ts"):
                        os.remove(os.path.join(output_dir, f))
                os.remove(filelist)
                return DownloadResult(True, "Download complete", output_path)
            return DownloadResult(False, "FFmpeg merge failed")
        except Exception as e:
            return DownloadResult(False, str(e))
