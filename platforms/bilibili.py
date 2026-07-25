import json
import os
import re
import tkinter as tk
from tkinter import ttk, messagebox
import requests
from bs4 import BeautifulSoup
from core.downloader import BaseDownloader, DownloadResult
from core.utils import sanitize_filename, get_ffmpeg_path, merge_audio_video, ensure_dir


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
        return os.path.join(os.getcwd(), "downloads", "bilibili")

    def download(self, url, output_dir, **kwargs):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ",
            "Referer": "https://www.bilibili.com",
        }
        try:
            res1 = requests.get(url, headers=headers, stream=True)
            soup = BeautifulSoup(res1.text, "html.parser")

            scripts = soup.find_all("script")
            playinfo = None
            for script in scripts:
                if "window.__playinfo__" in script.text:
                    json_str = script.text.split("=", 1)[1].strip()
                    json_str = json_str.rsplit(";", 1)[0]
                    playinfo = json.loads(json_str)
                    break

            if not playinfo:
                return DownloadResult(False, "未找到播放信息，请确认链接有效")

            audio_url = playinfo["data"]["dash"]["audio"][0]["base_url"]
            video_url = playinfo["data"]["dash"]["video"][0]["base_url"]

            title_tag = soup.find("h1", class_="video-title")
            title = sanitize_filename(title_tag.text if title_tag else "bilibili_video")

            audio_data = requests.get(audio_url, headers=headers).content
            video_data = requests.get(video_url, headers=headers).content

            ensure_dir(output_dir)
            audio_path = os.path.join(output_dir, "audio.m4s")
            video_path = os.path.join(output_dir, "video.m4s")
            output_path = os.path.join(output_dir, f"{title}.mp4")

            with open(audio_path, "wb") as f:
                f.write(audio_data)
            with open(video_path, "wb") as f:
                f.write(video_data)

            ffmpeg = get_ffmpeg_path(kwargs.get("config"))
            if merge_audio_video(audio_path, video_path, output_path, ffmpeg):
                return DownloadResult(True, "下载完成", output_path)
            return DownloadResult(False, "FFmpeg 合并失败")
        except Exception as e:
            return DownloadResult(False, f"下载失败: {e}")
