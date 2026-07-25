import json
import os
import re
import tkinter as tk
from tkinter import ttk, messagebox
import requests
from bs4 import BeautifulSoup
from core.downloader import BaseDownloader, DownloadResult
from core.utils import sanitize_filename, get_ffmpeg_path, ensure_dir, merge_ts


class Tencent(BaseDownloader):
    name = "腾讯视频"
    icon = "📺"
    description = "Tencent Video downloader"

    def create_tab(self, parent):
        frame = ttk.Frame(parent, padding=10)
        ttk.Label(frame, text="Tencent Video", font=("", 16, "bold")).pack(anchor="w")
        ttk.Label(frame, text=f"{self.icon} {self.description}").pack(anchor="w", pady=(0, 10))
        ttk.Label(frame, text="Video URL:").pack(anchor="w")
        self.url_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.url_var, width=60).pack(fill="x", pady=5)
        ttk.Label(frame, text="Cookie:").pack(anchor="w")
        self.cookie_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.cookie_var, width=60).pack(fill="x", pady=5)
        ttk.Label(frame, text="Data params (JSON):").pack(anchor="w")
        self.data_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.data_var, width=60).pack(fill="x", pady=5)
        ttk.Button(frame, text="Download", command=self._on_download).pack(pady=10)
        return frame

    def _on_download(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showerror("Error", "Please enter proxyhttp URL")
            return
        output_dir = os.path.join(os.getcwd(), "downloads", "tencent")
        result = self.download(url, output_dir,
                               cookie=self.cookie_var.get(),
                               data=self.data_var.get())
        if result.success:
            messagebox.showinfo("Success", f"Downloaded: {result.file_path}")
        else:
            messagebox.showerror("Error", result.message)

    def download(self, url, output_dir, **kwargs):
        headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; Redmi K30 Pro) AppleWebKit/537.36",
            "cookie": kwargs.get("cookie", "")
        }
        data_str = kwargs.get("data", "{}")
        try:
            data = json.loads(data_str) if data_str else {}
        except json.JSONDecodeError:
            return DownloadResult(False, "Invalid JSON in data params")

        try:
            res = requests.get(url, headers=headers, params=data, timeout=15)
            soup = BeautifulSoup(res.content, "html.parser")
            info = json.loads(soup.text)
            vinfo = json.loads(info["vinfo"])
            m3u8 = vinfo["vl"]["vi"][0]["ul"]["m3u8"]
            s = re.sub(r"#.*", "", m3u8)
            links = s.split()
            if not links:
                return DownloadResult(False, "No ts segments found")

            ensure_dir(output_dir)
            filelist = os.path.join(output_dir, "filelist.txt")
            with open(filelist, "w") as f:
                for link in links:
                    name = link.split("?")[0].split("/")[-1]
                    f.write(f"file '{name}'\n")

            for i, link in enumerate(links):
                name = link.split("?")[0].split("/")[-1]
                r = requests.get(link, headers=headers, stream=True, timeout=30)
                with open(os.path.join(output_dir, name), "wb") as f:
                    f.write(r.content)

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
