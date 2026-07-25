import os
import random
import tkinter as tk
from tkinter import ttk, messagebox
import requests
from core.downloader import BaseDownloader, DownloadResult
from core.utils import ensure_dir


class Douyin(BaseDownloader):
    name = "抖音"
    icon = "🎵"
    description = "Douyin (TikTok China) video downloader"

    def create_tab(self, parent):
        frame = ttk.Frame(parent, padding=10)
        ttk.Label(frame, text="Douyin", font=("", 16, "bold")).pack(anchor="w")
        ttk.Label(frame, text=f"{self.icon} {self.description}").pack(anchor="w", pady=(0, 10))
        ttk.Label(frame, text="Video URL:").pack(anchor="w")
        self.url_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.url_var, width=60).pack(fill="x", pady=5)
        ttk.Button(frame, text="Download", command=self._on_download).pack(pady=10)
        return frame

    def _on_download(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showerror("Error", "Please paste a video URL")
            return
        output_dir = os.path.join(os.getcwd(), "downloads", "douyin")
        result = self.download(url, output_dir)
        if result.success:
            messagebox.showinfo("Success", f"Downloaded: {result.file_path}")
        else:
            messagebox.showerror("Error", result.message)

    def download(self, url, output_dir, **kwargs):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.douyin.com/"
        }
        try:
            ensure_dir(output_dir)
            r = requests.get(url, headers=headers, stream=True, timeout=30)
            if r.status_code != 200:
                return DownloadResult(False, f"HTTP {r.status_code}")
            name = f"douyin_{random.randint(10000, 99999)}.mp4"
            path = os.path.join(output_dir, name)
            with open(path, "wb") as f:
                for chunk in r.iter_content(1024):
                    if chunk:
                        f.write(chunk)
            return DownloadResult(True, "Download complete", path)
        except Exception as e:
            return DownloadResult(False, str(e))
