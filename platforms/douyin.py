import json
import os
import re
import time
import tkinter as tk
from tkinter import ttk, messagebox
from urllib.parse import parse_qs, unquote, urlparse

import requests
from core.downloader import BaseDownloader, DownloadResult
from core.utils import ensure_dir, sanitize_filename


class Douyin(BaseDownloader):
    name = "抖音"
    icon = "🎵"
    description = "抖音视频下载"
    REQUEST_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/143.0.0.0 Safari/537.36"
        ),
        "Referer": "https://www.douyin.com/",
    }

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

    @classmethod
    def _resolve_video_url(cls, url):
        aweme_id = cls._extract_id(url)
        if aweme_id:
            return f"https://www.douyin.com/video/{aweme_id}", aweme_id

        response = requests.get(
            url,
            allow_redirects=True,
            headers=cls.REQUEST_HEADERS,
            timeout=15,
        )
        response.raise_for_status()
        aweme_id = cls._extract_id(response.url)
        if not aweme_id:
            raise ValueError("短链接跳转后仍未找到作品 ID")
        return f"https://www.douyin.com/video/{aweme_id}", aweme_id

    @staticmethod
    def _find_target_video(state, aweme_id):
        stack = [state]
        visited = set()
        while stack:
            value = stack.pop()
            if isinstance(value, dict):
                identity = id(value)
                if identity in visited:
                    continue
                visited.add(identity)

                ids = (
                    value.get("aweme_id"),
                    value.get("group_id"),
                    value.get("item_id"),
                )
                if aweme_id in {str(item) for item in ids if item is not None}:
                    video = value.get("video") or {}
                    for address_key in (
                        "play_addr_h264",
                        "play_addr",
                        "download_addr",
                    ):
                        address = video.get(address_key)
                        if isinstance(address, dict):
                            address = address.get("url_list")
                        if isinstance(address, list) and address:
                            return value.get("desc") or "", address[0]
                        if isinstance(address, str) and address:
                            return value.get("desc") or "", address

                stack.extend(value.values())
            elif isinstance(value, (list, tuple)):
                stack.extend(value)
        return None, None

    @staticmethod
    def _select_target_dom_video(candidates, aweme_id):
        for candidate in candidates or []:
            src = candidate.get("src", "")
            try:
                video_ids = parse_qs(urlparse(src).query).get("__vid", [])
            except (TypeError, ValueError):
                video_ids = []
            if aweme_id in video_ids:
                return src
        return None

    def _on_download(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showerror("错误", "请输入视频地址")
            return
        output_dir = self.get_output_dir("douyin")
        self.start_download(url, output_dir)

    def _set_status(self, text):
        status_var = getattr(self, "status_var", None)
        if status_var is None:
            return

        def update():
            try:
                status_var.set(text)
            except Exception:
                pass

        app = getattr(self, "app", None)
        try:
            if app and getattr(app, "root", None):
                app.root.after(0, update)
            else:
                update()
        except Exception:
            pass

    def download(self, url, output_dir, **kwargs):
        try:
            video_url, aid = self._resolve_video_url(url)
        except Exception as exc:
            return DownloadResult(False, f"无法解析抖音链接: {exc}")

        self._set_status("尝试 yt-dlp...")
        ytdlp_error = None
        try:
            from yt_dlp import YoutubeDL
            ensure_dir(output_dir)
            opts = {
                "outtmpl": os.path.join(output_dir, "%(title)s.%(ext)s"),
                "format": "best",
                "nocheckcertificate": True,
                "noplaylist": True,
            }
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(video_url, download=True)
                path = ydl.prepare_filename(info)
                self._set_status("完成")
                return DownloadResult(True, "下载完成", path)
        except ImportError:
            ytdlp_error = "未安装 yt-dlp"
        except Exception as ye:
            ytdlp_error = str(ye)

        self._set_status("启动浏览器...")
        driver = None
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
            title = None
            video_src = None
            try:
                states = driver.execute_script(
                    "return ["
                    "window.__INITIAL_STATE__ || null,"
                    "window._ROUTER_DATA || null,"
                    "window.__UNIVERSAL_DATA_FOR_REHYDRATION__ || null,"
                    "(document.getElementById('RENDER_DATA') || {}).textContent || null"
                    "];"
                )
                for state in states or []:
                    if isinstance(state, str):
                        try:
                            state = json.loads(unquote(state))
                        except (ValueError, TypeError):
                            continue
                    title, video_src = self._find_target_video(state, aid)
                    if video_src:
                        break
            except Exception:
                pass

            if not video_src:
                candidates = driver.execute_script(
                    "return [...document.querySelectorAll('video')].map(v => ({"
                    "src: v.currentSrc || v.src || '',"
                    "ancestor_href: v.closest('a') ? v.closest('a').href : ''"
                    "}));"
                )
                video_src = self._select_target_dom_video(candidates, aid)
                if video_src:
                    title = re.sub(r"\s*-\s*抖音\s*$", "", driver.title).strip()

            cookies = driver.get_cookies()

            if not video_src:
                self._set_status("失败")
                detail = f"\nyt-dlp: {ytdlp_error}" if ytdlp_error else ""
                return DownloadResult(
                    False,
                    "未找到与作品 ID 匹配的视频，已拒绝下载页面广告。"
                    "\n请确认浏览器已登录抖音。"
                    f"{detail}",
                )

            self._set_status("下载中...")
            ck = cookies_to_header(cookies)
            headers = {**self.REQUEST_HEADERS, "Cookie": ck}
            ensure_dir(output_dir)
            fname = sanitize_filename(title) if title else f"douyin_{aid}"
            path = os.path.join(output_dir, f"{fname}.mp4")
            partial_path = path + ".part"
            r = requests.get(video_src, headers=headers, stream=True, timeout=120)
            r.raise_for_status()
            content_type = r.headers.get("content-type", "").lower()
            if "text/html" in content_type or "application/json" in content_type:
                return DownloadResult(False, f"视频地址返回了无效内容: {content_type}")

            total = 0
            with open(partial_path, "wb") as f:
                for chunk in r.iter_content(16384):
                    if chunk:
                        f.write(chunk)
                        total += len(chunk)
            if total < 50000:
                os.remove(partial_path)
                self._set_status("失败")
                return DownloadResult(False, "目标视频内容异常（小于 50KB）")
            os.replace(partial_path, path)
            self._set_status("完成")
            return DownloadResult(True, "下载完成", path)
        except ImportError:
            return DownloadResult(
                False,
                "yt-dlp 下载失败且缺少 Selenium 浏览器兜底。"
                "\n请执行：pip install -r requirements.txt",
            )
        except Exception as se:
            self._set_status("失败")
            return DownloadResult(False, f"失败: {se}")
        finally:
            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    pass
