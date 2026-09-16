import json
import os
import re
import subprocess
import time
import tkinter as tk
from tkinter import ttk, messagebox
from urllib.parse import parse_qs, unquote, urlparse

import requests
from core.downloader import BaseDownloader, DownloadResult
from core.instruction_panel import InstructionPanel
from core.utils import (
    ensure_dir,
    get_ffmpeg_path,
    merge_audio_video,
    sanitize_filename,
)


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
        ttk.Label(frame, text="仅支持非 VIP 普通视频；复制播放页链接到下方：").pack(anchor="w")
        self.url_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.url_var, width=60).pack(fill="x", pady=3)
        ttk.Label(frame, text="支持：douyin.com/video/xxx、v.douyin.com/xxx", foreground="#6c757d", font=("", 8)).pack(anchor="w", pady=(0, 2))
        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(frame, textvariable=self.status_var, font=("", 9)).pack(anchor="w", pady=(4, 0))
        ttk.Button(frame, text="下载", command=self._on_download).pack(pady=8)
        InstructionPanel(
            frame,
            steps=[
                "打开抖音视频详情页。",
                "复制浏览器地址栏中的完整链接，也支持分享短链接。",
                "将链接粘贴到上方输入框，点击下载；解析会在后台完成。",
            ],
            image_name="抖音下载说明.png",
        ).pack(fill="both", expand=True, pady=(8, 0))
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
            ancestor_href = candidate.get("ancestor_href", "")
            try:
                video_ids = parse_qs(urlparse(src).query).get("__vid", [])
            except (TypeError, ValueError):
                video_ids = []
            linked_aweme_id = Douyin._extract_id(ancestor_href)
            if aweme_id in video_ids or linked_aweme_id == aweme_id:
                return src
        return None

    @staticmethod
    def _network_media_urls(entries):
        video_url = None
        audio_url = None
        for entry in entries or []:
            try:
                message = json.loads(entry["message"])["message"]
                if message.get("method") != "Network.responseReceived":
                    continue
                response = message["params"]["response"]
                url = response.get("url", "")
                mime_type = response.get("mimeType", "").lower()
            except (KeyError, TypeError, ValueError):
                continue
            if "douyinvod.com" not in url:
                continue
            if "/media-audio-" in url or mime_type.startswith("audio/"):
                audio_url = audio_url or url
                continue
            if not video_url and (
                "/media-video-" in url or mime_type.startswith("video/")
            ):
                video_url = url
            if video_url and audio_url:
                break
        return video_url, audio_url

    @staticmethod
    def _require_video(path, config=None):
        ffmpeg = get_ffmpeg_path(config)
        if not ffmpeg:
            raise ValueError("未找到 FFmpeg，无法验证下载文件是否包含画面。")
        result = subprocess.run(
            [ffmpeg, "-v", "error", "-nostdin", "-i", path,
             "-map", "0:v:0", "-t", "1", "-f", "null", "-"],
            capture_output=True,
            timeout=30,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode:
            raise ValueError(
                "下载内容没有可解码的视频轨道，不能作为视频下载成功。"
                "请保留原链接以便排查。"
            )

    @staticmethod
    def _download_stream(url, path, headers):
        response = requests.get(url, headers=headers, stream=True, timeout=120)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").lower()
        if "text/html" in content_type or "application/json" in content_type:
            raise ValueError(f"媒体地址返回了无效内容: {content_type}")
        total = 0
        with open(path, "wb") as file:
            for chunk in response.iter_content(16384):
                if chunk:
                    file.write(chunk)
                    total += len(chunk)
        if total < 50000:
            raise ValueError("目标媒体内容异常（小于 50KB）")

    def _on_download(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showerror("错误", "请输入视频地址")
            return
        output_dir = self.get_output_dir("douyin")
        self.start_download(url, output_dir)

    def download(self, url, output_dir, **kwargs):
        try:
            video_url, aid = self._resolve_video_url(url)
        except Exception as exc:
            return DownloadResult(False, f"无法解析抖音链接: {exc}")

        self._set_status("启动浏览器...")
        driver = None
        try:
            from core.browser import cookies_to_header

            driver = self.create_background_driver(performance_logging=True)
            driver.get("https://www.douyin.com/")
            time.sleep(2)
            driver.get_log("performance")
            driver.get(video_url)
            self._set_status("等待页面加载...")
            media_video_url = None
            media_audio_url = None
            deadline = time.monotonic() + 12
            while time.monotonic() < deadline:
                time.sleep(1)
                network_video, network_audio = self._network_media_urls(
                    driver.get_log("performance")
                )
                media_video_url = media_video_url or network_video
                media_audio_url = media_audio_url or network_audio
                if media_video_url and media_audio_url:
                    break

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

            if media_video_url and media_audio_url:
                self._set_status("下载并合并音视频...")
                ck = cookies_to_header(cookies)
                headers = {**self.REQUEST_HEADERS, "Cookie": ck}
                ensure_dir(output_dir)
                page_title = re.sub(
                    r"\s*-\s*抖音\s*$", "", driver.title
                ).strip()
                fname = sanitize_filename(page_title) if page_title else f"douyin_{aid}"
                path = os.path.join(output_dir, f"{fname}.mp4")
                video_part = path + ".video.part"
                audio_part = path + ".audio.part"
                merged_part = path + ".merged.part.mp4"
                try:
                    self._download_stream(media_video_url, video_part, headers)
                    self._require_video(video_part, kwargs.get("config"))
                    self._download_stream(media_audio_url, audio_part, headers)
                    ffmpeg = get_ffmpeg_path(kwargs.get("config"))
                    if not ffmpeg:
                        return DownloadResult(
                            False,
                            "已找到抖音音视频流，但未找到 FFmpeg，无法合并。",
                        )
                    if not merge_audio_video(
                        audio_part, video_part, merged_part, ffmpeg
                    ):
                        return DownloadResult(False, "抖音音视频合并失败")
                    self._require_video(merged_part, kwargs.get("config"))
                    os.replace(merged_part, path)
                    self._set_status("完成")
                    return DownloadResult(True, "下载完成", path)
                finally:
                    for temporary_path in (
                        video_part,
                        audio_part,
                        merged_part,
                    ):
                        if os.path.exists(temporary_path):
                            os.remove(temporary_path)

            if not video_src:
                self._set_status("失败")
                return DownloadResult(
                    False,
                    "未找到与作品 ID 匹配的视频，已拒绝下载页面广告。"
                    "\n请稍后重试，或确认该作品可在浏览器中正常播放。",
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
            self._require_video(partial_path, kwargs.get("config"))
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
