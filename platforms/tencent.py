import base64
from concurrent.futures import ThreadPoolExecutor, wait
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import tkinter as tk
from tkinter import messagebox, ttk
from urllib.parse import urljoin, urlsplit

import requests

from core.browser import cookies_to_header
from core.instruction_panel import InstructionPanel
from core.tencent_routes import rebase_manifest
from core.downloader import BaseDownloader, DownloadResult
from core.n_m3u8dl import (
    build_n_m3u8dl_command,
    find_n_m3u8dl,
    run_n_m3u8dl,
)
from core.utils import ensure_dir, get_ffmpeg_path, sanitize_filename


class Tencent(BaseDownloader):
    name = "腾讯视频"
    icon = "📺"
    description = "腾讯视频下载"

    TIP = "支持：v.qq.com/x/cover/xxx、v.qq.com/x/page/xxx"
    REQUEST_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/143.0.0.0 Safari/537.36"
        ),
        "Referer": "https://v.qq.com/",
    }
    PROBE_LIMIT = 4
    PROBE_BYTES = 256 * 1024
    PROBE_DEADLINE = 8
    PROBE_SAMPLE_SECONDS = 2

    def create_tab(self, parent):
        frame = ttk.Frame(parent, padding=10)
        ttk.Label(
            frame,
            text="腾讯视频",
            font=("", 16, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            frame,
            text=f"{self.icon} {self.description}",
        ).pack(anchor="w", pady=(0, 4))
        ttk.Label(frame, text="仅支持非 VIP 普通视频；复制播放页链接到下方：").pack(anchor="w")
        self.url_var = tk.StringVar()
        ttk.Entry(
            frame,
            textvariable=self.url_var,
            width=60,
        ).pack(fill="x", pady=5)
        ttk.Label(
            frame,
            text=self.TIP,
            foreground="#6c757d",
            font=("", 8),
        ).pack(anchor="w", pady=(0, 6))
        self.create_download_controls(
            frame,
            self._on_download,
        ).pack(anchor="center", pady=10)
        self.create_status_label(frame)
        InstructionPanel(
            frame,
            steps=[
                "在浏览器中打开想下载的腾讯视频，并切换到目标集数。",
                "复制地址栏中的完整链接，粘贴到上方输入框，点击下载。",
                "解析在后台静音进行；如需等待广告结束，请稍等，也可点击停止下载。",
            ],
            image_name="腾讯视频下载说明.png",
        ).pack(fill="both", expand=True, pady=(8, 0))
        return frame

    def _on_download(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showerror("错误", "请输入视频地址")
            return
        self.start_download(url, self.get_output_dir("tencent"))

    @staticmethod
    def _format_candidates(formats):
        candidates = [
            item
            for item in formats
            if item.get("url")
            # Tencent often leaves vcodec unset even for muxed video. Only an
            # explicit "none" is reliable evidence that the format is audio-only.
            and (item.get("vcodec") or "").lower() != "none"
        ]
        return sorted(
            candidates,
            key=lambda item: (
                item.get("height") or 0,
                item.get("tbr") or 0,
            ),
            reverse=True,
        )

    def _probe_format(
        self,
        format_info,
        headers,
        active_responses=None,
    ):
        manifest = None
        response = None
        try:
            self._raise_if_cancelled()
            media_url = format_info["url"]
            request_headers = {
                **headers,
                **(format_info.get("http_headers") or {}),
            }
            if ".m3u8" in media_url.lower():
                manifest = requests.get(
                    media_url,
                    headers=request_headers,
                    timeout=(3, 4),
                )
                manifest.raise_for_status()
                entries = [
                    line.strip()
                    for line in manifest.text.splitlines()
                    if line.strip() and not line.startswith("#")
                ]
                if not entries:
                    return 0.0
                media_url = urljoin(media_url, entries[0])

            started = time.monotonic()
            response = requests.get(
                media_url,
                headers=request_headers,
                stream=True,
                timeout=(3, 4),
            )
            if active_responses is not None:
                active_responses.append(response)
            response.raise_for_status()
            received = 0
            for chunk in response.iter_content(4 * 1024):
                self._raise_if_cancelled()
                if not chunk:
                    continue
                received += len(chunk)
                if received >= self.PROBE_BYTES:
                    break
                if (
                    time.monotonic() - started
                    >= self.PROBE_SAMPLE_SECONDS
                ):
                    break
            elapsed = max(time.monotonic() - started, 0.001)
            return received / elapsed
        except Exception:
            self._raise_if_cancelled()
            return 0.0
        finally:
            if manifest is not None:
                manifest.close()
            if response is not None:
                response.close()
                if (
                    active_responses is not None
                    and response in active_responses
                ):
                    active_responses.remove(response)

    def _ordered_candidates(self, formats, headers):
        candidates = self._format_candidates(formats)
        probe_count = min(len(candidates), self.PROBE_LIMIT)
        speeds = [0.0] * len(candidates)
        if probe_count:
            self._set_status(
                f"正在并行测速 {probe_count} 条腾讯线路..."
            )
            executor = ThreadPoolExecutor(max_workers=probe_count)
            active_responses = []
            futures = [
                executor.submit(
                    self._probe_format,
                    candidate,
                    headers,
                    active_responses,
                )
                for candidate in candidates[:probe_count]
            ]
            done, pending = wait(futures, timeout=self.PROBE_DEADLINE)
            for active_response in list(active_responses):
                active_response.close()
            for index, future in enumerate(futures):
                if future in done:
                    try:
                        speeds[index] = future.result()
                    except Exception:
                        speeds[index] = 0.0
                else:
                    future.cancel()
                if future in done or future.cancelled():
                    self._log(
                        "腾讯线路 "
                        f"{candidates[index].get('format_id', 'unknown')} "
                        f"测速 {speeds[index] / 1024:.1f} KiB/s"
                    )
            if pending:
                self._log(
                    f"{len(pending)} 条腾讯线路测速超时，已跳过",
                    "warning",
                )
            executor.shutdown(wait=False, cancel_futures=True)
        measured = [
            (speeds[index], index, candidate)
            for index, candidate in enumerate(candidates)
        ]
        measured.sort(key=lambda item: (-item[0], item[1]))
        self._fastest_probe_speed = max(speeds, default=0.0)
        return [item[2] for item in measured]

    def _capture_browser_route(self, url, manifest, source_url, timeout_seconds=90):
        from selenium.common.exceptions import TimeoutException

        self._set_status("线路过慢，正在等待浏览器正片线路（可能需等待广告结束）...")
        driver = self.create_background_driver(performance_logging=True)
        try:
            driver.set_page_load_timeout(12)
            driver.execute_cdp_cmd("Network.enable", {})
            try:
                driver.get(url)
            except TimeoutException:
                pass  # Ads and analytics need not finish loading to inspect media.
            deadline = time.monotonic() + timeout_seconds
            while time.monotonic() < deadline:
                self._raise_if_cancelled()
                for entry in driver.get_log("performance"):
                    message = self._performance_message(entry) or {}
                    if message.get("method") != "Network.responseReceived":
                        continue
                    response = message.get("params", {}).get("response", {})
                    media_url = response.get("url", "")
                    if response.get("status") not in (200, 206) or not urlsplit(media_url).path.endswith(".ts"):
                        continue
                    rewritten = rebase_manifest(manifest, source_url, media_url)
                    if rewritten:
                        self._log(f"已匹配正片分片，采用浏览器线路 {urlsplit(media_url).hostname}")
                        return rewritten
                time.sleep(0.25)
            raise RuntimeError("未获得与当前正片播放列表匹配的浏览器线路")
        finally:
            driver.quit()

    def _download_browser_route(self, url, info, candidate, headers, output_dir, config):
        request_headers = {**headers, **(candidate.get("http_headers") or {})}
        with requests.get(candidate["url"], headers=request_headers, timeout=(4, 8)) as response:
            response.raise_for_status()
            manifest = response.text
        rewritten = self._capture_browser_route(url, manifest, candidate["url"])
        # Keep short-lived signed URLs out of logs and remove the local playlist
        # after the downloader has finished reading it.
        with tempfile.TemporaryDirectory(prefix="tencent-route-") as temp_dir:
            playlist = os.path.join(temp_dir, "video.m3u8")
            with open(playlist, "w", encoding="utf-8") as file:
                file.write(rewritten)
            save_name = sanitize_filename(info.get("title") or "tencent_video") + " [browser]"
            command = build_n_m3u8dl_command(
                find_n_m3u8dl(config), playlist, request_headers,
                output_dir, save_name, config, get_ffmpeg_path(config),
            )
            self._set_status("已取得浏览器正片线路，正在下载完整视频...")
            return run_n_m3u8dl(command, output_dir, save_name, self._raise_if_cancelled)

    def _media_tracks(self, path, config):
        if not os.path.isfile(path) or os.path.getsize(path) <= 0:
            return set()

        ffmpeg = get_ffmpeg_path(config)
        ffprobe = shutil.which("ffprobe")
        if ffmpeg:
            sibling_name = (
                "ffprobe.exe"
                if os.path.basename(ffmpeg).lower().endswith(".exe")
                else "ffprobe"
            )
            sibling = os.path.join(
                os.path.dirname(os.path.abspath(ffmpeg)),
                sibling_name,
            )
            if os.path.isfile(sibling):
                ffprobe = sibling

        if ffprobe:
            result = subprocess.run(
                [
                    ffprobe,
                    "-v",
                    "error",
                    "-show_entries",
                    "stream=codec_type",
                    "-of",
                    "json",
                    path,
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=15,
            )
            if result.returncode == 0:
                try:
                    payload = json.loads(result.stdout)
                    return {
                        item["codec_type"]
                        for item in payload.get("streams", [])
                        if item.get("codec_type")
                    }
                except (KeyError, TypeError, ValueError):
                    pass

        if not ffmpeg:
            raise RuntimeError("未找到 FFmpeg，无法检查音视频轨")
        result = subprocess.run(
            [ffmpeg, "-hide_banner", "-i", path],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
        )
        details = f"{result.stdout}\n{result.stderr}"
        tracks = set()
        if re.search(r"Stream #.*Video:", details, re.IGNORECASE):
            tracks.add("video")
        if re.search(r"Stream #.*Audio:", details, re.IGNORECASE):
            tracks.add("audio")
        return tracks

    def _validate_output(self, path, config):
        tracks = self._media_tracks(path, config)
        if "video" not in tracks:
            raise RuntimeError("下载结果缺少视频轨")
        if "audio" not in tracks:
            raise RuntimeError("下载结果缺少音频轨")

    def _extract_with_yt_dlp(self, url, headers, config):
        from yt_dlp import YoutubeDL
        from yt_dlp.extractor.tencent import VQQVideoIE

        options = {
            "http_headers": headers,
            "nocheckcertificate": True,
            "noplaylist": True,
            # Tencent exposes several CDN manifests. A dead DNS route must not
            # block extraction once per manifest for minutes.
            "socket_timeout": 5,
            "extractor_retries": 0,
            "retries": 0,
        }
        options.update(self.get_yt_dlp_runtime_options(config))
        options["concurrent_fragment_downloads"] = 2
        with YoutubeDL(options) as ydl:
            extractor = VQQVideoIE(ydl)

            def collect_manifest(
                manifest_url,
                video_id,
                ext="mp4",
                *args,
                **kwargs,
            ):
                # The Tencent API has already supplied the signed manifest URL.
                # Do not synchronously resolve every CDN here; our bounded probe
                # below is responsible for checking and ordering those routes.
                return ([{
                    "url": manifest_url,
                    "ext": ext,
                    "protocol": "m3u8_native",
                }], {})

            extractor._extract_m3u8_formats_and_subtitles = collect_manifest
            video_id = self._target_vid(url)
            if not video_id:
                raise RuntimeError("无法从腾讯地址识别视频 VID")
            series_match = re.search(r"/cover/([^/]+)/", url)
            series_id = series_match.group(1) if series_match else None
            api_response = extractor._get_video_api_response(
                url,
                video_id,
                series_id,
                "srt",
                "hls",
                "hd",
            )
            extractor._check_api_response(api_response)
            formats, subtitles = (
                extractor._extract_video_formats_and_subtitles(
                    api_response,
                    video_id,
                )
            )
            video = api_response.get("vl", {}).get("vi", [{}])[0]
            return {
                "id": video_id,
                "title": video.get("ti") or f"tencent_{video_id}",
                "formats": formats,
                "subtitles": subtitles,
            }

    def _download_candidate(
        self,
        url,
        info,
        candidate,
        headers,
        output_dir,
        config,
    ):
        media_url = candidate["url"]
        if ".m3u8" in media_url.lower():
            executable = find_n_m3u8dl(config)
            if executable:
                title = sanitize_filename(
                    info.get("title") or "tencent_video"
                )
                format_id = sanitize_filename(
                    str(candidate.get("format_id") or "unknown")
                )
                save_name = f"{title} [{format_id}]"
                candidate_headers = {
                    **headers,
                    **(candidate.get("http_headers") or {}),
                }
                command = build_n_m3u8dl_command(
                    executable,
                    media_url,
                    candidate_headers,
                    output_dir,
                    save_name,
                    config,
                    get_ffmpeg_path(config),
                )
                self._set_status(
                    f"正在使用高速分片后端下载线路 {format_id}..."
                )
                try:
                    return run_n_m3u8dl(
                        command,
                        output_dir,
                        save_name,
                        self._raise_if_cancelled,
                    )
                except Exception as error:
                    self._raise_if_cancelled()
                    self._log(
                        "N_m3u8DL-RE 下载失败，"
                        f"正在回退 yt-dlp: {error}",
                        "warning",
                    )

        return self._download_candidate_with_yt_dlp(
            url,
            info,
            candidate,
            headers,
            output_dir,
            config,
        )

    def _download_candidate_with_yt_dlp(
        self,
        url,
        info,
        candidate,
        headers,
        output_dir,
        config,
    ):
        from yt_dlp import YoutubeDL

        title = sanitize_filename(info.get("title") or "tencent_video")
        format_id = candidate["format_id"]
        safe_format_id = sanitize_filename(str(format_id))
        candidate_headers = {
            **headers,
            **(candidate.get("http_headers") or {}),
        }
        options = {
            # Keep every CDN/format retry isolated. Reusing one output name lets
            # yt-dlp resume a stale .part/.ytdl file from the previous route,
            # which can produce an audio-only or corrupt result.
            "outtmpl": os.path.join(
                output_dir,
                f"{title} [{safe_format_id}].%(ext)s",
            ),
            "format": "bestvideo+bestaudio/best",
            "http_headers": candidate_headers,
            "nocheckcertificate": True,
            "noplaylist": True,
            "socket_timeout": 8,
            "extractor_retries": 1,
            "retries": 1,
            "fragment_retries": 1,
        }
        options.update(self.get_yt_dlp_runtime_options(config))
        options["concurrent_fragment_downloads"] = 2
        ffmpeg = get_ffmpeg_path(config)
        if ffmpeg:
            options["ffmpeg_location"] = ffmpeg
            options["merge_output_format"] = "mp4"
        with YoutubeDL(options) as ydl:
            # Download the exact probed manifest. Re-extracting the Tencent page
            # can issue a different short-lived token and select a dead CDN.
            downloaded_info = ydl.extract_info(candidate["url"], download=True)
            output_path = ydl.prepare_filename(downloaded_info)
        merged_path = os.path.splitext(output_path)[0] + ".mp4"
        return merged_path if os.path.exists(merged_path) else output_path

    def _capture_browser_context(self, url):
        driver = None
        try:
            self._set_status("正在后台获取腾讯播放会话...")
            driver = self.create_background_driver()
            driver.get(url)
            time.sleep(2)
            user_agent = driver.execute_script(
                "return navigator.userAgent;"
            )
            headers = {
                "User-Agent": (
                    user_agent or self.REQUEST_HEADERS["User-Agent"]
                ),
                "Referer": url,
            }
            cookie_header = cookies_to_header(driver.get_cookies())
            if cookie_header:
                headers["Cookie"] = cookie_header
            return headers
        finally:
            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    pass

    @staticmethod
    def _target_vid(url):
        match = re.search(
            r"(?:/|\bvid=)([A-Za-z0-9]{11})(?:\.html|[&#?]|$)",
            url,
        )
        return match.group(1) if match else None

    @staticmethod
    def _extract_media_from_player_body(body, target_vid):
        """Extract target media from Tencent proxyhttp/getvinfo JSON."""
        if not body:
            return None
        text = body.strip()
        if text.startswith("QZOutputJson="):
            text = text[len("QZOutputJson="):].rstrip(";")
        try:
            payload = json.loads(text)
            vinfo = payload.get("vinfo", payload)
            if isinstance(vinfo, str):
                vinfo = json.loads(vinfo)
            videos = vinfo.get("vl", {}).get("vi", [])
        except (AttributeError, TypeError, ValueError):
            return None

        for video in videos:
            video_id = str(video.get("vid") or "")
            if target_vid and video_id != target_vid:
                continue
            title = video.get("ti") or "tencent_video"
            bases = video.get("ul", {}).get("ui", [])
            for item in bases:
                base_url = item.get("url") or ""
                hls = item.get("hls") or {}
                hls_path = (
                    hls.get("pt") if isinstance(hls, dict) else ""
                )
                if hls_path:
                    return {
                        "url": urljoin(base_url, hls_path),
                        "title": title,
                        "video_id": video_id,
                    }
                if ".m3u8" in base_url.lower():
                    return {
                        "url": base_url,
                        "title": title,
                        "video_id": video_id,
                    }

            filename = video.get("fn")
            vkey = video.get("fvkey")
            if filename and vkey and bases and bases[0].get("url"):
                return {
                    "url": (
                        f"{bases[0]['url']}{filename}?vkey={vkey}"
                    ),
                    "title": title,
                    "video_id": video_id,
                }
        return None

    @staticmethod
    def _performance_message(entry):
        try:
            return json.loads(entry["message"])["message"]
        except (KeyError, TypeError, ValueError):
            return None

    @staticmethod
    def _extract_player_identity(body):
        """Read the target identity from Tencent's encrypted vinfo_proxy."""
        try:
            payload = json.loads(body)
            data = payload.get("data", payload)
            play_info = data.get("playInfo") or {}
            video_info = data.get("videoInfo") or {}
            video_id = str(
                play_info.get("vid") or video_info.get("vid") or ""
            )
        except (AttributeError, TypeError, ValueError):
            return None
        if not video_id:
            return None
        return {
            "video_id": video_id,
            # vinfo_proxy text fields may still be encrypted/obfuscated.
            # Use the rendered page title after the target VID is verified.
            "title": "tencent_video",
        }

    def _with_browser_context(self, driver, media, page_url):
        user_agent = driver.execute_script("return navigator.userAgent;")
        page_title = re.sub(
            r"[\s_-]*腾讯视频.*$",
            "",
            driver.title,
        ).strip()
        media.update(
            {
                "cookies": driver.get_cookies(),
                "user_agent": (
                    user_agent or self.REQUEST_HEADERS["User-Agent"]
                ),
                "referer": page_url,
                "title": (
                    media.get("title")
                    if media.get("title") != "tencent_video"
                    else page_title or "tencent_video"
                ),
            }
        )
        return media

    def _capture_browser_media(self, url, timeout_seconds=60):
        target_vid = self._target_vid(url)
        if not target_vid:
            raise RuntimeError("无法从腾讯地址识别视频 VID")

        driver = None
        player_requests = {}
        target_player = None
        media_candidates = []
        try:
            self._set_status("正在后台捕获腾讯播放器地址...")
            driver = self.create_background_driver(
                performance_logging=True
            )
            driver.execute_cdp_cmd("Network.enable", {})
            driver.get(url)

            attempts = max(1, int(timeout_seconds * 2))
            for _ in range(attempts):
                self._raise_if_cancelled()
                try:
                    driver.execute_script(
                        "document.querySelectorAll('video').forEach("
                        "v => {v.muted = true; "
                        "v.play().catch(() => {});});"
                    )
                except Exception:
                    pass
                time.sleep(0.5)

                for entry in driver.get_log("performance"):
                    message = self._performance_message(entry)
                    if not message:
                        continue
                    method = message.get("method")
                    params = message.get("params") or {}
                    request_id = params.get("requestId")

                    if method == "Network.responseReceived":
                        response_url = (
                            params.get("response", {}).get("url")
                            or ""
                        )
                        if ".m3u8" in response_url.lower():
                            media_candidates.append(response_url)
                            media_candidates = media_candidates[-20:]
                        if any(
                            marker in response_url.lower()
                            for marker in (
                                "proxyhttp",
                                "getvinfo",
                                "getinfo",
                                "vinfo_proxy",
                            )
                        ):
                            player_requests[request_id] = response_url
                        continue

                    if (
                        method != "Network.loadingFinished"
                        or request_id not in player_requests
                    ):
                        continue
                    try:
                        body_data = driver.execute_cdp_cmd(
                            "Network.getResponseBody",
                            {"requestId": request_id},
                        )
                        response_body = body_data.get("body", "")
                        if body_data.get("base64Encoded"):
                            response_body = base64.b64decode(
                                response_body
                            ).decode("utf-8", "replace")
                    except Exception as error:
                        self._log(
                            f"读取腾讯播放器响应失败: {error}",
                            "warning",
                        )
                        continue

                    media = self._extract_media_from_player_body(
                        response_body,
                        target_vid,
                    )
                    if media:
                        return self._with_browser_context(
                            driver,
                            media,
                            url,
                        )

                    identity = self._extract_player_identity(
                        response_body
                    )
                    if (
                        not identity
                        or identity["video_id"] != target_vid
                    ):
                        continue
                    target_player = identity
                    self._log(
                        "已确认腾讯目标视频，正在等待正片媒体地址..."
                    )

                try:
                    playback = driver.execute_script(
                        "const videos = Array.from("
                        "document.querySelectorAll('video'));"
                        "return {"
                        "main_started: videos.some(v => "
                        "Number.isFinite(v.duration) "
                        "&& v.duration >= 60 "
                        "&& v.currentTime > 0),"
                        "media_urls: performance.getEntriesByType("
                        "'resource').map(e => e.name).filter("
                        "u => u.toLowerCase().includes('.m3u8'))"
                        "};"
                    )
                except Exception:
                    playback = None

                if isinstance(playback, dict):
                    for media_url in playback.get("media_urls") or []:
                        if media_url not in media_candidates:
                            media_candidates.append(media_url)
                    media_candidates = media_candidates[-20:]
                    main_video_started = playback.get("main_started")
                else:
                    main_video_started = bool(playback)

                if main_video_started and media_candidates:
                    return self._with_browser_context(
                        driver,
                        {
                            "url": media_candidates[-1],
                            "title": (
                                target_player.get("title")
                                if target_player
                                else "tencent_video"
                            ),
                            "video_id": target_vid,
                        },
                        url,
                    )

            raise RuntimeError(
                "未捕获到目标视频播放器响应，请确认页面可以播放"
            )
        finally:
            if driver is not None:
                try:
                    driver.quit()
                except Exception:
                    pass

    def _download_captured_media(
        self,
        captured,
        output_dir,
        config,
    ):
        media_url = captured["url"]
        title = sanitize_filename(
            captured.get("title") or "tencent_video"
        )
        output_path = os.path.join(output_dir, f"{title}.mp4")
        headers = {
            "User-Agent": (
                captured.get("user_agent")
                or self.REQUEST_HEADERS["User-Agent"]
            ),
            "Referer": captured.get("referer") or "https://v.qq.com/",
        }
        cookie_header = cookies_to_header(captured.get("cookies") or [])
        if cookie_header:
            headers["Cookie"] = cookie_header

        self._set_status("已捕获目标视频，正在下载...")
        if ".m3u8" in media_url.lower():
            from yt_dlp import YoutubeDL

            options = {
                "outtmpl": output_path,
                "format": "best",
                "http_headers": headers,
                "nocheckcertificate": True,
                "noplaylist": True,
            }
            options.update(self.get_yt_dlp_runtime_options(config))
            ffmpeg = get_ffmpeg_path(config)
            if ffmpeg:
                options["ffmpeg_location"] = ffmpeg
                options["merge_output_format"] = "mp4"
            with YoutubeDL(options) as ydl:
                info = ydl.extract_info(media_url, download=True)
                prepared = ydl.prepare_filename(info)
            if os.path.exists(output_path):
                return output_path
            return prepared

        response = requests.get(
            media_url,
            headers=headers,
            stream=True,
            timeout=(10, 60),
        )
        response.raise_for_status()
        self.download_response(response, output_path)
        return output_path

    def _download_with_yt_dlp(self, url, output_dir, config):
        from yt_dlp import YoutubeDL

        options = {
            "outtmpl": os.path.join(output_dir, "%(title)s.%(ext)s"),
            "format": "bv+ba/b",
            "nocheckcertificate": True,
        }
        options.update(self.get_yt_dlp_runtime_options(config))
        ffmpeg = get_ffmpeg_path(config)
        if ffmpeg:
            options["ffmpeg_location"] = ffmpeg
            options["merge_output_format"] = "mp4"
        with YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)
            output_path = ydl.prepare_filename(info)
        merged_path = os.path.splitext(output_path)[0] + ".mp4"
        return merged_path if os.path.exists(merged_path) else output_path

    def download(self, url, output_dir, **kwargs):
        ensure_dir(output_dir)
        config = kwargs.get("config")
        headers = dict(self.REQUEST_HEADERS)
        try:
            self._set_status("正在解析腾讯视频格式...")
            info = self._extract_with_yt_dlp(
                url,
                headers,
                config,
            )
        except Exception as error:
            self._raise_if_cancelled()
            self._log(
                f"腾讯直接解析失败，正在获取浏览器会话: {error}",
                "warning",
            )
            try:
                headers = self._capture_browser_context(url)
                info = self._extract_with_yt_dlp(
                    url,
                    headers,
                    config,
                )
            except Exception as browser_error:
                self._raise_if_cancelled()
                return DownloadResult(
                    False,
                    f"腾讯视频解析失败：{browser_error}",
                )

        candidates = self._ordered_candidates(
            info.get("formats") or [],
            headers,
        )
        if not candidates:
            return DownloadResult(False, "腾讯视频未找到可用视频轨")

        if (getattr(self, "_fastest_probe_speed", float("inf")) < 16 * 1024
                and ".m3u8" in candidates[0]["url"].lower()
                and find_n_m3u8dl(config)):
            browser_output = None
            try:
                browser_output = self._download_browser_route(
                    url, info, candidates[0], headers, output_dir, config,
                )
                self._validate_output(browser_output, config)
                return DownloadResult(True, "下载完成", browser_output)
            except Exception as error:
                self._raise_if_cancelled()
                if browser_output and os.path.isfile(browser_output):
                    os.remove(browser_output)
                self._log(f"浏览器线路不可用（{type(error).__name__}），继续尝试原线路", "warning")

        failures = []
        for candidate in candidates:
            self._raise_if_cancelled()
            format_id = candidate.get("format_id") or "unknown"
            height = candidate.get("height") or "?"
            self._set_status(
                f"正在下载腾讯线路 {format_id}（{height}P）..."
            )
            output_path = None
            try:
                output_path = self._download_candidate(
                    url,
                    info,
                    candidate,
                    headers,
                    output_dir,
                    config,
                )
                self._validate_output(output_path, config)
                self._log(
                    f"腾讯线路 {format_id} 音视频轨校验通过"
                )
                return DownloadResult(True, "下载完成", output_path)
            except Exception as error:
                self._raise_if_cancelled()
                failures.append(f"{format_id}: {error}")
                self._log(
                    f"腾讯线路 {format_id} 失败，切换下一条: {error}",
                    "warning",
                )
                if output_path and os.path.isfile(output_path):
                    try:
                        os.remove(output_path)
                    except OSError:
                        pass

        return DownloadResult(
            False,
            "腾讯视频所有线路均失败：" + "；".join(failures),
        )
