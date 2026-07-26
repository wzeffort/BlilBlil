import json
import os
import re
import tkinter as tk
from tkinter import ttk, messagebox
import requests
from bs4 import BeautifulSoup
from core.downloader import BaseDownloader, DownloadResult
from core.utils import sanitize_filename, get_ffmpeg_path, ensure_dir, merge_ts


class Youku(BaseDownloader):
    name = "优酷"
    icon = "🎞"
    description = "优酷视频下载"

    TIP = "支持：v.youku.com/v_show/id_xxx、youku.com/v_show/id_xxx"

    def create_tab(self, parent):
        frame = ttk.Frame(parent, padding=10)
        ttk.Label(frame, text="优酷", font=("", 16, "bold")).pack(anchor="w")
        ttk.Label(frame, text=f"{self.icon} {self.description}").pack(anchor="w", pady=(0, 4))
        ttk.Label(frame, text="视频地址:").pack(anchor="w")
        self.url_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.url_var, width=60).pack(fill="x", pady=5)
        ttk.Label(frame, text=self.TIP, foreground="#6c757d", font=("", 8)).pack(anchor="w", pady=(0, 6))
        ttk.Button(frame, text="下载", command=self._on_download).pack(pady=10)
        return frame

    def _on_download(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showerror("错误", "请输入视频地址")
            return
        output_dir = self.get_output_dir("youku")
        self.start_download(url, output_dir)

    def _parse_state(self, html):
        m = re.search(r"window\.__INITIAL_STATE__\s*=\s*(\{.+?\})\s*(?:;|</)", html, re.DOTALL)
        if m:
            return json.loads(m.group(1))
        return None

    def _find_segs(self, state):
        for key in ("videoData", "showData", "programInfo"):
            vd = state.get(key, {})
            streams = vd.get("streams", [])
            if not streams:
                continue
            for s in streams:
                segs = s.get("segs", [])
                if segs:
                    title = vd.get("title", "youku_video")
                    return title, [seg["cdn_url"] for seg in segs if seg.get("cdn_url")]
        return None, []

    def download(self, url, output_dir, **kwargs):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://v.youku.com/"
        }
        try:
            def _do_download(state_or_html, cookie_str=""):
                if isinstance(state_or_html, str):
                    state = self._parse_state(state_or_html)
                else:
                    state = state_or_html
                if not state:
                    return None
                title, seg_urls = self._find_segs(state)
                if not seg_urls:
                    return None
                title = sanitize_filename(title or "youku_video")
                ensure_dir(output_dir)
                output_path = os.path.join(output_dir, f"{title}.mp4")
                h = {**headers}
                if cookie_str:
                    h["Cookie"] = cookie_str

                if len(seg_urls) == 1:
                    r = requests.get(seg_urls[0], headers=h, stream=True, timeout=60)
                    with open(output_path, "wb") as f:
                        for chunk in r.iter_content(8192):
                            if chunk:
                                f.write(chunk)
                    return DownloadResult(True, "下载完成", output_path)

                filelist = os.path.join(output_dir, "filelist.txt")
                with open(filelist, "w") as f:
                    for cdn in seg_urls:
                        name = cdn.split("/")[-1].split("?")[0]
                        if not name:
                            name = f"seg_{seg_urls.index(cdn)}.ts"
                        f.write(f"file '{name}'\n")

                for cdn in seg_urls:
                    name = cdn.split("/")[-1].split("?")[0]
                    if not name:
                        name = f"seg_{seg_urls.index(cdn)}.ts"
                    r = requests.get(cdn, headers=h, stream=True, timeout=60)
                    with open(os.path.join(output_dir, name), "wb") as f:
                        f.write(r.content)

                ffmpeg = get_ffmpeg_path(kwargs.get("config"))
                if merge_ts(filelist, output_path, ffmpeg):
                    for f in os.listdir(output_dir):
                        if f.endswith(".ts"):
                            os.remove(os.path.join(output_dir, f))
                    os.remove(filelist)
                    return DownloadResult(True, "下载完成", output_path)
                return DownloadResult(False, "FFmpeg 合并失败")

            # --- direct try ---
            s = requests.Session()
            s.headers.update(headers)
            resp = s.get(url, timeout=15)
            html = resp.text
            result = _do_download(html)
            if result:
                return result

            # --- selenium fallback ---
            try:
                from core.browser import _make_driver, cookies_to_header
                import time

                driver = _make_driver(headless=False)
                driver.get(url)
                time.sleep(6)

                state2 = driver.execute_script("return window.__INITIAL_STATE__;")
                cookies = driver.get_cookies()
                driver.quit()

                ck = cookies_to_header(cookies)
                result2 = _do_download(state2, cookie_str=ck)
                if result2:
                    return result2
                return DownloadResult(False, "未能解析视频数据，请尝试使用 VIP 播放")
            except ImportError:
                return DownloadResult(False, "需要安装 selenium 和 Chrome 浏览器\npip install selenium")
            except Exception as se:
                return DownloadResult(False, f"自动化获取失败: {se}")

        except Exception as e:
            return DownloadResult(False, f"下载失败: {e}")
