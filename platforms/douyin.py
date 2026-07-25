import os
import re
import time
import tkinter as tk
from tkinter import ttk, messagebox
import requests
from core.downloader import BaseDownloader, DownloadResult
from core.utils import ensure_dir, sanitize_filename


class Douyin(BaseDownloader):
    name = "抖音"
    icon = "🎵"
    description = "抖音视频下载"

    def create_tab(self, parent):
        frame = ttk.Frame(parent, padding=10)
        ttk.Label(frame, text="抖音", font=("", 16, "bold")).pack(anchor="w")
        ttk.Label(frame, text=f"{self.icon} {self.description}").pack(anchor="w", pady=(0, 2))
        ttk.Label(frame, text="视频地址:").pack(anchor="w")
        self.url_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.url_var, width=60).pack(fill="x", pady=3)
        ttk.Label(frame, text="支持：douyin.com/video/xxx、v.douyin.com/xxx", foreground="#6c757d", font=("", 8)).pack(anchor="w", pady=(0, 2))
        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(frame, textvariable=self.status_var, font=("", 9)).pack(anchor="w", pady=(4, 0))
        ttk.Button(frame, text="下载", command=self._on_download).pack(pady=8)
        return frame

    @staticmethod
    def _extract_id(url):
        m = re.search(r'(?:video|note|modal_id)[/=](\d{15,25})', url)
        if m:
            return m.group(1)
        m = re.search(r'(\d{15,25})', url)
        return m.group(1) if m else None

    def _on_download(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showerror("错误", "请输入视频地址")
            return
        output_dir = os.path.join(os.getcwd(), "downloads", "douyin")
        self.start_download(url, output_dir)

    def _set_status(self, text):
        try:
            self.status_var.set(text)
        except Exception:
            pass

    def download(self, url, output_dir, **kwargs):
        aid = self._extract_id(url)
        if not aid:
            return DownloadResult(False, f"无法从链接提取视频 ID")

        video_url = f"https://www.douyin.com/video/{aid}"

        self._set_status("尝试 yt-dlp...")
        try:
            from yt_dlp import YoutubeDL
            ensure_dir(output_dir)
            opts = {
                "outtmpl": os.path.join(output_dir, "%(title)s.%(ext)s"),
                "format": "best",
                "nocheckcertificate": True,
            }
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(video_url, download=True)
                title = info.get("title", "douyin_video")
                ext = info.get("ext", "mp4")
                path = os.path.join(output_dir, f"{title}.{ext}")
                self._set_status("完成")
                return DownloadResult(True, "下载完成", path)
        except ImportError:
            pass
        except Exception as ye:
            if "cookies" not in str(ye).lower():
                return DownloadResult(False, f"yt-dlp: {ye}")

        self._set_status("启动浏览器...")
        try:
            from core.browser import cookies_to_header
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options

            opts = Options()
            opts.add_experimental_option("excludeSwitches", ["enable-automation"])
            opts.add_experimental_option("useAutomationExtension", False)
            opts.add_argument(
                "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"
            )
            driver = webdriver.Chrome(options=opts)
            driver.get(video_url)
            self._set_status("等待页面加载...")
            time.sleep(6)

            self._set_status("提取数据...")
            title = ""
            video_src = None
            try:
                state = driver.execute_script("return window.__INITIAL_STATE__;")
                if state:
                    for path in [
                        ("aweme_detail", "video", "play_addr", "url_list"),
                        ("aweme_detail_v2", "video", "play_addr", "url_list"),
                        ("videoData", "video", "play_addr", "url_list"),
                        ("aweme_detail", "video", "play_addr_h264", "url_list"),
                        ("aweme_detail", "video", "download_addr", "url_list"),
                    ]:
                        obj = state
                        try:
                            if isinstance(obj, dict) and path[0] in obj:
                                detail = obj[path[0]]
                                if isinstance(detail, dict):
                                    title = detail.get("desc", "") or title
                            for key in path:
                                obj = obj.get(key, {}) if isinstance(obj, dict) else None
                                if obj is None:
                                    break
                            if isinstance(obj, list) and obj:
                                video_src = obj[0]
                                break
                        except Exception:
                            continue
            except Exception:
                pass

            if not video_src:
                try:
                    video_src = driver.execute_script(
                        "var v=document.querySelector('video');"
                        "if(v) return v.currentSrc||v.src||''; return '';"
                    )
                    if not video_src or video_src.startswith("blob:"):
                        video_src = None
                except Exception:
                    pass

            cookies = driver.get_cookies()
            driver.quit()

            if not video_src:
                self._set_status("失败")
                return DownloadResult(False, "未能提取视频。\n请确保浏览器已登录抖音")

            self._set_status("下载中...")
            ck = cookies_to_header(cookies)
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Cookie": ck,
                "Referer": "https://www.douyin.com/",
            }
            ensure_dir(output_dir)
            fname = sanitize_filename(title) if title else f"douyin_{aid}"
            path = os.path.join(output_dir, f"{fname}.mp4")
            r = requests.get(video_src, headers=headers, stream=True, timeout=120)
            total = int(r.headers.get("content-length", 0))
            if total < 50000:
                self._set_status("广告")
                return DownloadResult(False, "视频过小(<50KB)，可能是广告")
            with open(path, "wb") as f:
                for chunk in r.iter_content(16384):
                    if chunk:
                        f.write(chunk)
            self._set_status("完成")
            return DownloadResult(True, "下载完成", path)
        except ImportError:
            return DownloadResult(False, "需要 selenium: pip install selenium")
        except Exception as se:
            self._set_status("失败")
            return DownloadResult(False, f"失败: {se}")
