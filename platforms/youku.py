import json
import os
import re
import tkinter as tk
from tkinter import ttk, messagebox
import requests
from bs4 import BeautifulSoup
from core.downloader import BaseDownloader, DownloadResult
from core.utils import get_ffmpeg_path, ensure_dir, merge_ts


class Youku(BaseDownloader):
    name = "优酷"
    icon = "🎞"
    description = "Youku video downloader"

    def create_tab(self, parent):
        frame = ttk.Frame(parent, padding=10)
        ttk.Label(frame, text="Youku", font=("", 16, "bold")).pack(anchor="w")
        ttk.Label(frame, text=f"{self.icon} {self.description}").pack(anchor="w", pady=(0, 10))
        ttk.Label(frame, text="Mtop API URL:").pack(anchor="w")
        self.url_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.url_var, width=60).pack(fill="x", pady=5)
        ttk.Label(frame, text="Cookie:").pack(anchor="w")
        self.cookie_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.cookie_var, width=60).pack(fill="x", pady=5)
        ttk.Button(frame, text="Download", command=self._on_download).pack(pady=10)
        return frame

    def _on_download(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showerror("Error", "Please enter Mtop API URL")
            return
        output_dir = os.path.join(os.getcwd(), "downloads", "youku")
        result = self.download(url, output_dir, cookie=self.cookie_var.get())
        if result.success:
            messagebox.showinfo("Success", f"Downloaded: {result.file_path}")
        else:
            messagebox.showerror("Error", result.message)

    def download(self, url, output_dir, **kwargs):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://v.youku.com/",
            "Cookie": kwargs.get("cookie", "")
        }
        try:
            res = requests.get(url, headers=headers, timeout=15)
            text = res.text
            if text.startswith("mtopjsonp"):
                text = text[12:-1]
            data = json.loads(text)
            title = data["data"]["data"]["video"]["title"].replace(" ", "_")
            title = re.sub(r'[\\/:*?"<>|]', "_", title)

            cdn_urls = [seg["cdn_url"] for seg in data["data"]["data"]["stream"][1]["segs"]]

            ensure_dir(output_dir)
            filelist = os.path.join(output_dir, "filelist.txt")
            with open(filelist, "w") as f:
                for cdn in cdn_urls:
                    name = cdn.split("=")[-2].replace("&", "_") + ".ts" if "=" in cdn else f"seg_{cdn_urls.index(cdn)}.ts"
                    f.write(f"file '{name}'\n")

            for cdn in cdn_urls:
                name = cdn.split("=")[-2].replace("&", "_") + ".ts" if "=" in cdn else f"seg_{cdn_urls.index(cdn)}.ts"
                r = requests.get(cdn, headers=headers, stream=True, timeout=30)
                with open(os.path.join(output_dir, name), "wb") as f:
                    f.write(r.content)

            output_path = os.path.join(output_dir, f"{title}.mp4")
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
