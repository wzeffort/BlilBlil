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
    description = "腾讯视频下载"

    TIP = "支持：v.qq.com/x/cover/xxx、v.qq.com/x/page/xxx"

    def create_tab(self, parent):
        frame = ttk.Frame(parent, padding=10)
        ttk.Label(frame, text="腾讯视频", font=("", 16, "bold")).pack(anchor="w")
        ttk.Label(frame, text=f"{self.icon} {self.description}").pack(anchor="w", pady=(0, 4))
        ttk.Label(frame, text="视频地址:").pack(anchor="w")
        self.url_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.url_var, width=60).pack(fill="x", pady=5)
        ttk.Label(frame, text=self.TIP, foreground="#6c757d", font=("", 8)).pack(anchor="w", pady=(0, 6))
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
        output_dir = self.get_output_dir("tencent")
        self.start_download(url, output_dir)

    def _parse_page(self, html):
        """Try to extract state from page HTML."""
        m = re.search(r"window\.__INITIAL_STATE__\s*=\s*(\{.+?\})\s*(?:;|</)", html, re.DOTALL)
        if m:
            return json.loads(m.group(1))
        return None

    def _find_video_from_state(self, state):
        """Extract video URL from __INITIAL_STATE__."""
        if not state:
            return None, None
        for key in ("videoInfo", "vodVideoInfo", "programInfo", "videoData"):
            vi = state.get(key, {})
            if not vi:
                continue
            streams = vi.get("streams") or vi.get("videoInfo", {}).get("streams", [])
            if not streams:
                continue
            for s in streams:
                ul = s.get("url_list") or s.get("url") or s.get("playUrl")
                if ul:
                    title = vi.get("title", "") or vi.get("playTitle", "tencent_video")
                    src = ul if isinstance(ul, str) else (ul[0] if isinstance(ul, list) else None)
                    return title, src
        return None, None

    def download(self, url, output_dir, **kwargs):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://v.qq.com/"
        }
        try:
            from yt_dlp import YoutubeDL

            self._set_status("正在解析腾讯视频...")
            ensure_dir(output_dir)
            options = {
                "outtmpl": os.path.join(output_dir, "%(title)s.%(ext)s"),
                "format": "bv+ba/b",
                "nocheckcertificate": True,
            }
            options.update(
                self.get_yt_dlp_runtime_options(kwargs.get("config"))
            )
            ffmpeg = get_ffmpeg_path(kwargs.get("config"))
            if ffmpeg:
                options["ffmpeg_location"] = ffmpeg
                options["merge_output_format"] = "mp4"
            with YoutubeDL(options) as ydl:
                self._set_status("正在下载...")
                info = ydl.extract_info(url, download=True)
                output_path = ydl.prepare_filename(info)
                merged_path = os.path.splitext(output_path)[0] + ".mp4"
                if os.path.exists(merged_path):
                    output_path = merged_path
                return DownloadResult(True, "下载完成", output_path)
        except ImportError:
            pass
        except Exception as error:
            self._raise_if_cancelled()
            self._log(
                f"腾讯 yt-dlp 解析失败，转为网页解析: {error}",
                "warning",
            )
            self._set_status("专用解析失败，尝试网页解析...")

        try:
            # --- direct try ---
            self._set_status("正在尝试网页解析...")
            s = requests.Session()
            s.headers.update(headers)
            resp = s.get(url, timeout=15)
            html = resp.text

            state = self._parse_page(html)
            title, video_src = self._find_video_from_state(state)
            if video_src:
                self._set_status("正在下载...")
                ensure_dir(output_dir)
                title = sanitize_filename(title or "tencent_video")
                path = os.path.join(output_dir, f"{title}.mp4")
                r = s.get(video_src, stream=True, timeout=60)
                r.raise_for_status()
                self.download_response(r, path)
                return DownloadResult(True, "下载完成", path)

            # --- selenium fallback ---
            try:
                from core.browser import cookies_to_header
                import time

                self._set_status("正在后台解析腾讯页面...")
                driver = self.create_background_driver()
                driver.get(url)
                time.sleep(6)

                state2 = driver.execute_script("return window.__INITIAL_STATE__;")
                title2, video_src2 = self._find_video_from_state(state2)

                if video_src2:
                    cookies = driver.get_cookies()
                    driver.quit()
                    ck = cookies_to_header(cookies)
                    title2 = sanitize_filename(title2 or "tencent_video")
                    ensure_dir(output_dir)
                    path2 = os.path.join(output_dir, f"{title2}.mp4")
                    h = {**headers, "Cookie": ck}
                    self._set_status("正在下载...")
                    r2 = requests.get(video_src2, headers=h, stream=True, timeout=60)
                    r2.raise_for_status()
                    self.download_response(r2, path2)
                    return DownloadResult(True, "下载完成", path2)

                driver.quit()
                return DownloadResult(False, "未能解析视频数据，请尝试使用 VIP 播放")
            except ImportError:
                return DownloadResult(False, "需要安装 selenium 和 Chrome 浏览器\npip install selenium")
            except Exception as se:
                self._raise_if_cancelled()
                return DownloadResult(False, f"自动化获取失败: {se}")

        except Exception as e:
            self._raise_if_cancelled()
            return DownloadResult(False, f"下载失败: {e}")
