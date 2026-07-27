import json
import os
import re
import time
import tkinter as tk
from tkinter import ttk, messagebox
import requests
from bs4 import BeautifulSoup
from core.downloader import BaseDownloader, DownloadResult
from core.browser import cookies_to_header
from core.utils import (
    ensure_dir,
    get_ffmpeg_path,
    merge_ts,
    sanitize_filename,
)


class IQiyi(BaseDownloader):
    name = "爱奇艺"
    icon = "🎥"
    description = "iQiyi video downloader"

    def create_tab(self, parent):
        frame = ttk.Frame(parent, padding=10)
        ttk.Label(frame, text="iQiyi", font=("", 16, "bold")).pack(anchor="w")
        ttk.Label(frame, text=f"{self.icon} {self.description}").pack(anchor="w", pady=(0, 10))
        ttk.Label(frame, text="视频页面或 DASH API 地址:").pack(anchor="w")
        self.url_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.url_var, width=60).pack(fill="x", pady=5)
        ttk.Label(
            frame,
            text="推荐直接粘贴 iqiyi.com 视频播放页；旧 DASH 地址仍兼容",
            foreground="#6c757d",
            font=("", 8),
        ).pack(anchor="w", pady=(0, 6))
        self.create_download_controls(
            frame, self._on_download
        ).pack(anchor="center", pady=10)
        self.create_status_label(frame)
        return frame

    @staticmethod
    def _select_target_media_url(urls, target_tvid):
        from urllib.parse import parse_qs, urlparse

        target_m3u8 = None
        for media_url in urls:
            parsed = urlparse(media_url)
            query = parse_qs(parsed.query)
            if target_tvid not in query.get("qd_tvid", []):
                continue
            if parsed.path.lower().endswith(".m3u8"):
                target_m3u8 = media_url
                continue
            if (
                "/videos/v1/" in parsed.path
                and parsed.path.lower().endswith((".f4v", ".mp4"))
            ):
                return media_url
        return target_m3u8

    @staticmethod
    def _performance_urls(entries):
        urls = []
        for entry in entries:
            try:
                message = json.loads(entry["message"])["message"]
                if message["method"] != "Network.responseReceived":
                    continue
                urls.append(message["params"]["response"]["url"])
            except (KeyError, TypeError, ValueError):
                continue
        return urls

    def _download_video_page(self, url, output_dir, config=None):
        driver = None
        try:
            self._set_status("正在后台解析爱奇艺页面...")
            driver = self.create_background_driver(performance_logging=True)
            driver.get(url)
            urls = []
            target_ids = []
            media_url = None
            for _ in range(20):
                self._raise_if_cancelled()
                time.sleep(1)
                urls.extend(
                    self._performance_urls(
                        driver.get_log("performance")
                    )
                )
                for response_url in urls:
                    match = re.search(
                        r"/playervideoinfo\?[^#]*\bid=(\d+)",
                        response_url,
                    )
                    if (
                        match
                        and match.group(1) not in target_ids
                    ):
                        target_ids.append(match.group(1))
                for target_tvid in target_ids:
                    media_url = self._select_target_media_url(
                        urls, target_tvid
                    )
                    if media_url:
                        break
                if media_url:
                    break

            title = sanitize_filename(
                driver.title.split("-爱奇艺", 1)[0].strip()
                or "iqiyi_video"
            )
            cookie_header = cookies_to_header(driver.get_cookies())
        except Exception as error:
            self._raise_if_cancelled()
            return DownloadResult(False, f"爱奇艺后台解析失败: {error}")
        finally:
            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    pass

        if not media_url:
            return DownloadResult(
                False,
                "未捕获到目标视频资源，请确认视频可以正常播放后重试",
            )

        try:
            self._set_status("正在下载爱奇艺视频...")
            ensure_dir(output_dir)
            output_path = os.path.join(output_dir, f"{title}.mp4")
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36"
                ),
                "Referer": url,
            }
            if cookie_header:
                headers["Cookie"] = cookie_header
            if ".m3u8" in media_url.lower():
                from yt_dlp import YoutubeDL

                options = {
                    "outtmpl": output_path,
                    "format": "best",
                    "http_headers": headers,
                    "nocheckcertificate": True,
                    "noplaylist": True,
                }
                options.update(
                    self.get_yt_dlp_runtime_options(config)
                )
                ffmpeg = get_ffmpeg_path(config)
                if ffmpeg:
                    options["ffmpeg_location"] = ffmpeg
                    options["merge_output_format"] = "mp4"
                with YoutubeDL(options) as ydl:
                    ydl.extract_info(media_url, download=True)
                return DownloadResult(
                    True, "下载完成", output_path
                )

            response = requests.get(
                media_url,
                headers=headers,
                stream=True,
                timeout=120,
            )
            response.raise_for_status()
            content_type = response.headers.get("Content-Type", "").lower()
            if "application/json" in content_type:
                resolver_data = response.json()
                cdn_urls = [
                    item.get("URL")
                    for item in resolver_data.get("d", [])
                    if isinstance(item, dict) and item.get("URL")
                ]
                if not cdn_urls:
                    return DownloadResult(
                        False,
                        "爱奇艺 CDN 调度结果中没有可用视频地址",
                    )
                response.close()
                response = requests.get(
                    cdn_urls[0],
                    headers=headers,
                    stream=True,
                    timeout=120,
                )
                response.raise_for_status()
                if "application/json" in response.headers.get(
                    "Content-Type", ""
                ).lower():
                    return DownloadResult(
                        False,
                        "爱奇艺 CDN 返回了无效的视频响应",
                    )

            downloaded_bytes = self.download_response(
                response, output_path
            )
            if downloaded_bytes == 0:
                os.remove(output_path)
                return DownloadResult(False, "爱奇艺视频响应为空")
            return DownloadResult(True, "下载完成", output_path)
        except Exception as error:
            self._raise_if_cancelled()
            return DownloadResult(False, f"爱奇艺视频下载失败: {error}")

    def _on_download(self):
        video_url = self.url_var.get().strip()
        if not video_url:
            messagebox.showerror("错误", "请输入爱奇艺视频地址")
            return
        output_dir = self.get_output_dir("iqiyi")
        self.start_download(video_url, output_dir)

    def download(self, url, output_dir, **kwargs):
        if re.match(r"https?://(?:[^/]+\.)?iqiyi\.com/.+\.html", url):
            return self._download_video_page(
                url, output_dir, kwargs.get("config")
            )

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.iqiyi.com/"
        }
        try:
            self._set_status("正在读取爱奇艺 DASH 数据...")
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

            self._set_status("正在下载视频分片...")
            for link in links:
                self._raise_if_cancelled()
                name = link.split("=")[2].replace("&", "_") + ".ts" if "=" in link else f"seg_{links.index(link)}.ts"
                r = requests.get(link, headers=headers, stream=True, timeout=30)
                r.raise_for_status()
                self.download_response(
                    r, os.path.join(output_dir, name)
                )

            output_path = os.path.join(output_dir, f"{title}.mp4")
            ffmpeg = get_ffmpeg_path(kwargs.get("config"))
            if not ffmpeg:
                return DownloadResult(False, "未找到 FFmpeg，无法合并视频")
            self._set_status("正在合并视频...")
            if merge_ts(filelist, output_path, ffmpeg):
                for f in os.listdir(output_dir):
                    if f.endswith(".ts"):
                        os.remove(os.path.join(output_dir, f))
                os.remove(filelist)
                return DownloadResult(True, "Download complete", output_path)
            return DownloadResult(False, "FFmpeg merge failed")
        except Exception as e:
            self._raise_if_cancelled()
            return DownloadResult(False, str(e))
