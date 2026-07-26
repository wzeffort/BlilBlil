import json
import os
import re
import tkinter as tk
from tkinter import ttk, messagebox
import requests
from bs4 import BeautifulSoup
from core.downloader import BaseDownloader, DownloadResult
from core.utils import get_ffmpeg_path, ensure_dir, merge_ts


class IQiyi(BaseDownloader):
    name = "爱奇艺"
    icon = "🎥"
    description = "iQiyi video downloader"

    def create_tab(self, parent):
        frame = ttk.Frame(parent, padding=10)
        ttk.Label(frame, text="iQiyi", font=("", 16, "bold")).pack(anchor="w")
        ttk.Label(frame, text=f"{self.icon} {self.description}").pack(anchor="w", pady=(0, 10))
        ttk.Label(frame, text="DASH API 地址:").pack(anchor="w")
        self.url_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.url_var, width=60).pack(fill="x", pady=5)
        ttk.Label(frame, text="页面地址(用于获取标题):").pack(anchor="w")
        self.page_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.page_var, width=60).pack(fill="x", pady=5)
        ttk.Button(frame, text="下载", command=self._on_download).pack(pady=10)
        return frame

    def _on_download(self):
        dash_url = self.url_var.get().strip()
        page_url = self.page_var.get().strip()
        if not dash_url:
            messagebox.showerror("错误", "请输入 DASH API 地址")
            return
        output_dir = self.get_output_dir("iqiyi")
        self.start_download(dash_url, output_dir, page_url=page_url)

    def download(self, url, output_dir, **kwargs):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.iqiyi.com/"
        }
        try:
            res = requests.get(url, headers=headers, timeout=15)
            data = json.loads(res.text)
            m3u8 = None
            for video in data["data"]["program"]["video"]:
                if "m3u8" in video:
                    m3u8 = video["m3u8"]
                    break
            if not m3u8:
                return DownloadResult(False, "No m3u8 found")
            s = re.sub(r"#.*", "", m3u8)
            links = [l.split("\n")[0] for l in s.split() if l.strip()]
            if not links:
                return DownloadResult(False, "No ts segments")

            title = "iqiyi_video"
            page_url = kwargs.get("page_url", "")
            if page_url:
                try:
                    pr = requests.get(page_url, headers=headers, timeout=10)
                    ps = BeautifulSoup(pr.content, "html.parser")
                    meta = ps.find("meta", attrs={"name": "irTitle"})
                    if meta:
                        title = re.sub(r'[\\/:*?"<>|]', "_", meta.get("content", "iqiyi_video"))
                except Exception:
                    pass

            ensure_dir(output_dir)
            filelist = os.path.join(output_dir, "filelist.txt")
            with open(filelist, "w") as f:
                for link in links:
                    name = link.split("=")[2].replace("&", "_") + ".ts" if "=" in link else f"seg_{links.index(link)}.ts"
                    f.write(f"file '{name}'\n")

            for link in links:
                name = link.split("=")[2].replace("&", "_") + ".ts" if "=" in link else f"seg_{links.index(link)}.ts"
                r = requests.get(link, headers=headers, stream=True, timeout=30)
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
