import json
import os
import tkinter as tk
from tkinter import ttk, messagebox
import requests
from bs4 import BeautifulSoup
from core.downloader import BaseDownloader, DownloadResult
from core.utils import sanitize_filename, get_ffmpeg_path, merge_audio_video, ensure_dir


class Bilibili(BaseDownloader):
    name = "B站"
    icon = "🎬"
    description = "Bilibili video downloader"

    def create_tab(self, parent):
        frame = ttk.Frame(parent, padding=10)
        ttk.Label(frame, text="Bilibili", font=("", 16, "bold")).pack(anchor="w")
        ttk.Label(frame, text=f"{self.icon} {self.description}").pack(anchor="w", pady=(0, 10))

        ttk.Label(frame, text="Video URL:").pack(anchor="w")
        self.url_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.url_var, width=60).pack(fill="x", pady=5)

        self.download_btn = ttk.Button(frame, text="Download", command=self._on_download)
        self.download_btn.pack(pady=10)

        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(frame, textvariable=self.status_var).pack(anchor="w")
        return frame

    def _on_download(self):
        url = self.url_var.get().strip()
        if not self.validate_url(url):
            messagebox.showerror("Error", "Invalid URL")
            return
        output_dir = self._get_output_dir()
        result = self.download(url, output_dir)
        if result.success:
            messagebox.showinfo("Success", f"Downloaded: {result.file_path}")
        else:
            messagebox.showerror("Error", result.message)

    def _get_output_dir(self):
        return os.path.join(os.getcwd(), "downloads")

    def download(self, url, output_dir, **kwargs):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.bilibili.com"
        }
        try:
            res = requests.get(url, headers=headers, timeout=15)
            res.encoding = "utf-8"
            soup = BeautifulSoup(res.text, "html.parser")

            playinfo = None
            for script in soup.find_all("script"):
                if "window.__playinfo__" in script.text:
                    json_str = script.text.split("=", 1)[1].strip().rsplit(";", 1)[0]
                    playinfo = json.loads(json_str)
                    break

            if not playinfo:
                return DownloadResult(False, "No playinfo found")

            audio_url = playinfo["data"]["dash"]["audio"][0]["base_url"]
            video_url = playinfo["data"]["dash"]["video"][0]["base_url"]

            title_tag = soup.find("h1", class_="video-title")
            title = sanitize_filename(title_tag.text if title_tag else "bilibili_video")

            ensure_dir(output_dir)
            audio_path = os.path.join(output_dir, "audio.m4s")
            video_path = os.path.join(output_dir, "video.m4s")
            output_path = os.path.join(output_dir, f"{title}.mp4")

            for path, src_url in [(audio_path, audio_url), (video_path, video_url)]:
                r = requests.get(src_url, headers=headers, stream=True, timeout=30)
                with open(path, "wb") as f:
                    for chunk in r.iter_content(1024):
                        if chunk:
                            f.write(chunk)

            ffmpeg = get_ffmpeg_path(kwargs.get("config"))
            if merge_audio_video(audio_path, video_path, output_path, ffmpeg):
                return DownloadResult(True, "Download complete", output_path)
            return DownloadResult(False, "FFmpeg merge failed")
        except Exception as e:
            return DownloadResult(False, str(e))
