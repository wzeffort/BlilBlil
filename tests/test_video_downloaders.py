import os
import json
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import Mock, patch

from core.downloader import BaseDownloader, DownloadResult
from core.utils import get_ffmpeg_path
from platforms.bilibili import Bilibili
from platforms.douyin import Douyin
from platforms.iqiyi import IQiyi
from platforms.tencent import Tencent


class _FakeYoutubeDL:
    last_options = None
    info = None
    download_flags = []
    extracted_urls = []

    def __init__(self, options):
        type(self).last_options = options

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def extract_info(self, url, download):
        self.extracted_url = url
        type(self).download_flags.append(download)
        type(self).extracted_urls.append(url)
        return dict(type(self).info)

    def prepare_filename(self, info):
        return info["_prepared_filename"]


class _FlakyYoutubeDL(_FakeYoutubeDL):
    attempts = 0

    def extract_info(self, url, download):
        type(self).attempts += 1
        if type(self).attempts == 1:
            raise RuntimeError(
                "ERROR: [BiliBili] Failed to extract play info"
            )
        return super().extract_info(url, download)


class _FatalYoutubeDL(_FakeYoutubeDL):
    attempts = 0

    def extract_info(self, url, download):
        type(self).attempts += 1
        raise RuntimeError("No space left on device")


class _ConcurrentYoutubeDL(_FakeYoutubeDL):
    def __init__(self, options):
        if options.get("concurrent_fragment_downloads") != 7:
            raise RuntimeError("configured fragment concurrency was ignored")
        super().__init__(options)


class BilibiliDownloaderTests(unittest.TestCase):
    def test_retries_with_a_new_session_after_play_info_extraction_fails(self):
        with tempfile.TemporaryDirectory() as output_dir:
            expected_path = os.path.join(output_dir, "video.mp4")
            _FlakyYoutubeDL.attempts = 0
            _FlakyYoutubeDL.info = {
                "title": "video",
                "ext": "mp4",
                "_prepared_filename": expected_path,
            }
            fake_module = types.SimpleNamespace(YoutubeDL=_FlakyYoutubeDL)

            with (
                patch.dict(sys.modules, {"yt_dlp": fake_module}),
                patch(
                    "platforms.bilibili.get_ffmpeg_path",
                    return_value="ffmpeg.exe",
                ),
                patch("time.sleep"),
            ):
                result = Bilibili().download(
                    "https://www.bilibili.com/video/BV1sbgv6iEDY",
                    output_dir,
                )

            self.assertTrue(result.success, result.message)
            self.assertEqual(expected_path, result.file_path)
            self.assertEqual(2, _FlakyYoutubeDL.attempts)

    def test_does_not_retry_non_extractor_download_errors(self):
        with tempfile.TemporaryDirectory() as output_dir:
            _FatalYoutubeDL.attempts = 0
            fake_module = types.SimpleNamespace(YoutubeDL=_FatalYoutubeDL)

            with (
                patch.dict(sys.modules, {"yt_dlp": fake_module}),
                patch(
                    "platforms.bilibili.get_ffmpeg_path",
                    return_value="ffmpeg.exe",
                ),
                patch("time.sleep"),
            ):
                result = Bilibili().download(
                    "https://www.bilibili.com/video/BV1sbgv6iEDY",
                    output_dir,
                )

            self.assertFalse(result.success)
            self.assertIn("No space left on device", result.message)
            self.assertEqual(1, _FatalYoutubeDL.attempts)

    def test_missing_ffmpeg_fails_before_downloading_split_streams(self):
        """Without FFmpeg, do not leave unusable audio/video fragments behind."""
        with tempfile.TemporaryDirectory() as output_dir:
            _FakeYoutubeDL.info = {
                "title": "display title",
                "ext": "mp4",
                "_prepared_filename": os.path.join(output_dir, "unused.mp4"),
            }
            _FakeYoutubeDL.last_options = None
            fake_module = types.SimpleNamespace(YoutubeDL=_FakeYoutubeDL)

            with (
                patch.dict(sys.modules, {"yt_dlp": fake_module}),
                patch("platforms.bilibili.get_ffmpeg_path", return_value=None),
            ):
                result = Bilibili().download(
                    "https://www.bilibili.com/video/BV1example",
                    output_dir,
                )

            self.assertFalse(result.success)
            self.assertIn("FFmpeg", result.message)
            self.assertIsNone(_FakeYoutubeDL.last_options)

    def test_configured_download_directory_is_used(self):
        downloader = Bilibili()
        downloader.app = types.SimpleNamespace(
            get_config=lambda: {"download_dir": os.path.join("D:\\", "Videos")}
        )

        self.assertEqual(
            os.path.join("D:\\", "Videos", "bilibili"),
            downloader._get_output_dir(),
        )


class CoreDownloaderTests(unittest.TestCase):
    def test_background_browser_factory_always_requests_headless_mode(self):
        class BrowserDownloader(BaseDownloader):
            def create_tab(self, parent):
                return None

            def download(self, url, output_dir, **kwargs):
                return DownloadResult(True, "ok")

        expected_driver = object()
        downloader = BrowserDownloader()
        create_driver = getattr(
            downloader, "create_background_driver", lambda: None
        )

        with patch(
            "core.browser._make_driver", return_value=expected_driver
        ) as make_driver:
            driver = create_driver()

        self.assertIs(expected_driver, driver)
        make_driver.assert_called_once_with(headless=True)

    def test_project_root_ffmpeg_executable_is_detected(self):
        expected = os.path.join(".", "ffmpeg", "ffmpeg.exe")

        def is_file(path):
            return os.path.normcase(os.path.normpath(path)) == os.path.normcase(
                os.path.normpath(expected)
            )

        with (
            patch("core.utils.os.path.isfile", side_effect=is_file),
            patch("shutil.which", return_value=None),
        ):
            self.assertEqual(expected, get_ffmpeg_path())

    def test_missing_ffmpeg_returns_none_instead_of_invalid_command(self):
        with (
            patch("core.utils.os.path.isfile", return_value=False),
            patch("shutil.which", return_value=None),
        ):
            self.assertIsNone(get_ffmpeg_path())

    def test_unhandled_download_error_is_reported_to_the_app(self):
        class BrokenDownloader(BaseDownloader):
            def create_tab(self, parent):
                return None

            def download(self, url, output_dir, **kwargs):
                raise RuntimeError("network exploded")

        callbacks = []
        root = types.SimpleNamespace(
            after=lambda delay, callback: callbacks.append(callback)
        )
        downloader = BrokenDownloader()
        downloader.app = types.SimpleNamespace(
            root=root,
            _on_download_done=lambda result: callbacks.append(result),
        )

        downloader._download_thread("https://example.com/video", "unused")
        for callback in list(callbacks):
            callback()
        results = [
            item for item in callbacks
            if isinstance(item, DownloadResult)
        ]
        self.assertEqual(1, len(results))
        result = results[0]
        self.assertIsInstance(result, DownloadResult)
        self.assertFalse(result.success)
        self.assertIn("network exploded", result.message)

    def test_yt_dlp_progress_is_forwarded_to_gui_progress(self):
        class ProgressDownloader(BaseDownloader):
            def create_tab(self, parent):
                return None

            def download(self, url, output_dir, **kwargs):
                return DownloadResult(True, "ok")

        callbacks = []
        progress = {"mode": "indeterminate", "value": 0}
        downloader = ProgressDownloader()
        downloader.app = types.SimpleNamespace(
            root=types.SimpleNamespace(
                after=lambda delay, callback: callbacks.append(callback)
            ),
            progress=progress,
            log=Mock(),
        )
        progress_hook = getattr(
            downloader,
            "_yt_dlp_progress_hook",
            lambda data: None,
        )

        progress_hook(
            {
                "status": "downloading",
                "downloaded_bytes": 50,
                "total_bytes": 100,
                "speed": 1024,
                "eta": 5,
            }
        )
        for callback in callbacks:
            callback()

        self.assertEqual("determinate", progress["mode"])
        self.assertEqual(50, progress["value"])
        downloader.app.log.assert_called()


class ConfigTests(unittest.TestCase):
    def test_older_config_receives_n_m3u8dl_default(self):
        from core.config import Config

        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = os.path.join(temp_dir, "config.json")
            with open(config_path, "w", encoding="utf-8") as config_file:
                json.dump(
                    {
                        "download_dir": "D:/Videos",
                        "max_threads": 6,
                    },
                    config_file,
                )

            config = Config(config_path)

        self.assertEqual("", config["n_m3u8dl_path"])
        self.assertEqual("D:/Videos", config["download_dir"])
        self.assertEqual(6, config["max_threads"])


class NM3U8DLAdapterTests(unittest.TestCase):
    def test_executable_lookup_accepts_app_config(self):
        from core.config import Config
        from core.n_m3u8dl import find_n_m3u8dl

        with tempfile.TemporaryDirectory() as temp_dir:
            executable = os.path.join(temp_dir, "N_m3u8DL-RE.exe")
            with open(executable, "wb") as file:
                file.write(b"test fixture")
            config = Config(os.path.join(temp_dir, "config.json"))
            config["n_m3u8dl_path"] = executable
            self.assertEqual(executable, find_n_m3u8dl(config))

    def test_command_uses_threads_from_app_config(self):
        from core.config import Config
        from core.n_m3u8dl import build_n_m3u8dl_command

        with tempfile.TemporaryDirectory() as temp_dir:
            config = Config(os.path.join(temp_dir, "config.json"))
            config["max_threads"] = 6
            command = build_n_m3u8dl_command(
                "N_m3u8DL-RE.exe", "https://cdn.example/video.m3u8",
                {}, temp_dir, "video", config,
            )
            self.assertEqual("6", command[command.index("--thread-count") + 1])

    def test_configured_executable_has_priority(self):
        from core.n_m3u8dl import find_n_m3u8dl

        configured = os.path.join("D:\\", "Tools", "N_m3u8DL-RE.exe")
        with (
            patch("core.n_m3u8dl.os.path.isfile", return_value=True),
            patch("core.n_m3u8dl.shutil.which") as which,
        ):
            result = find_n_m3u8dl({"n_m3u8dl_path": configured})

        self.assertEqual(configured, result)
        which.assert_not_called()

    def test_command_clamps_threads_and_passes_media_context(self):
        from core.n_m3u8dl import build_n_m3u8dl_command

        command = build_n_m3u8dl_command(
            "N_m3u8DL-RE.exe",
            "https://cdn.example/video.m3u8?token=signed",
            {
                "User-Agent": "Browser UA",
                "Referer": "https://v.qq.com/",
                "Cookie": "video_guid=session",
            },
            os.path.join("downloads", "tencent"),
            "目标视频 [shd-0]",
            {"max_threads": 99},
            os.path.join("ffmpeg", "ffmpeg.exe"),
        )

        self.assertEqual("N_m3u8DL-RE.exe", command[0])
        self.assertEqual(
            "https://cdn.example/video.m3u8?token=signed",
            command[1],
        )
        thread_index = command.index("--thread-count")
        self.assertEqual("16", command[thread_index + 1])
        output_index = command.index("--save-dir")
        self.assertEqual(
            os.path.abspath(os.path.join("downloads", "tencent")),
            command[output_index + 1],
        )
        self.assertIn("User-Agent: Browser UA", command)
        self.assertIn("Referer: https://v.qq.com/", command)
        self.assertIn("Cookie: video_guid=session", command)
        self.assertIn("--append-url-params", command)
        ffmpeg_index = command.index("--ffmpeg-binary-path")
        self.assertEqual(
            os.path.abspath(os.path.join("ffmpeg", "ffmpeg.exe")),
            command[ffmpeg_index + 1],
        )
        self.assertNotIn("shell=True", command)

    def test_runner_returns_new_media_file(self):
        from core.n_m3u8dl import run_n_m3u8dl

        with tempfile.TemporaryDirectory() as output_dir:
            expected = os.path.join(output_dir, "目标视频.mp4")

            class CompletedProcess:
                returncode = 0

                def poll(self):
                    return 0

            def start_process(*_args, **_kwargs):
                with open(expected, "wb") as output:
                    output.write(b"video")
                return CompletedProcess()

            with patch(
                "core.n_m3u8dl.subprocess.Popen",
                side_effect=start_process,
            ):
                result = run_n_m3u8dl(
                    ["N_m3u8DL-RE.exe", "signed-url"],
                    output_dir,
                    "目标视频",
                    lambda: None,
                )

        self.assertEqual(expected, result)

    def test_runner_terminates_child_when_cancelled(self):
        from core.downloader import DownloadCancelled
        from core.n_m3u8dl import run_n_m3u8dl

        process = Mock()
        process.poll.return_value = None
        process.wait.return_value = 0

        def cancel():
            raise DownloadCancelled("下载已停止")

        with (
            tempfile.TemporaryDirectory() as output_dir,
            patch("core.n_m3u8dl.subprocess.Popen", return_value=process),
        ):
            with self.assertRaises(DownloadCancelled):
                run_n_m3u8dl(
                    ["N_m3u8DL-RE.exe", "signed-url"],
                    output_dir,
                    "目标视频",
                    cancel,
                )

        process.terminate.assert_called_once_with()
        process.wait.assert_called_once()


class TencentDownloaderTests(unittest.TestCase):
    def test_candidates_exclude_audio_only_formats(self):
        formats = [
            {
                "format_id": "audio-only",
                "url": "https://audio.example/stream.m3u8",
                "vcodec": "none",
                "acodec": "aac",
                "height": None,
            },
            {
                "format_id": "shd-0",
                "url": "https://video.example/stream.m3u8",
                "vcodec": "h264",
                "acodec": "aac",
                "height": 720,
            },
        ]

        candidates = Tencent._format_candidates(formats)

        self.assertEqual(
            ["shd-0"],
            [item["format_id"] for item in candidates],
        )

    def test_candidates_keep_tencent_formats_with_unknown_vcodec(self):
        formats = [
            {
                "format_id": "shd-0",
                "url": "https://video.example/stream.m3u8",
                "vcodec": None,
                "acodec": None,
                "height": 720,
            },
        ]

        candidates = Tencent._format_candidates(formats)

        self.assertEqual(["shd-0"], [item["format_id"] for item in candidates])

    def test_probe_timeout_moves_candidate_behind_a_fast_line(self):
        formats = [
            {
                "format_id": "slow",
                "url": "https://slow.example/stream.m3u8",
                "vcodec": "h264",
                "acodec": "aac",
                "height": 720,
            },
            {
                "format_id": "fast",
                "url": "https://fast.example/stream.m3u8",
                "vcodec": "h264",
                "acodec": "aac",
                "height": 720,
            },
        ]
        downloader = Tencent()

        with patch.object(
            downloader,
            "_probe_format",
            side_effect=[0.0, 2048.0],
        ):
            ordered = downloader._ordered_candidates(formats, {})

        self.assertEqual(
            ["fast", "slow"],
            [item["format_id"] for item in ordered],
        )

    def test_probe_stops_after_absolute_sampling_deadline(self):
        class TricklingResponse:
            def __init__(self):
                self.chunks_yielded = 0

            def raise_for_status(self):
                pass

            def iter_content(self, _chunk_size):
                for _ in range(100):
                    self.chunks_yielded += 1
                    yield b"x" * 4096

            def close(self):
                pass

        response = TricklingResponse()
        downloader = Tencent()

        with (
            patch("platforms.tencent.requests.get", return_value=response),
            patch(
                "platforms.tencent.time.monotonic",
                side_effect=[0.0, 0.5, 2.1, 2.2],
            ),
        ):
            downloader._probe_format(
                {"url": "https://slow.example/video.mp4"},
                {},
            )

        self.assertEqual(2, response.chunks_yielded)

    def test_probe_timeout_closes_pending_http_response(self):
        class BlockingResponse:
            def __init__(self):
                self.closed = False
                self.released = threading.Event()

            def raise_for_status(self):
                pass

            def iter_content(self, _chunk_size):
                self.released.wait(0.2)
                if not self.closed:
                    yield b"x" * 4096

            def close(self):
                self.closed = True
                self.released.set()

        response = BlockingResponse()
        downloader = Tencent()
        downloader.PROBE_DEADLINE = 0.01

        with patch(
            "platforms.tencent.requests.get",
            return_value=response,
        ):
            downloader._ordered_candidates(
                [{"format_id": "slow", "url": "https://slow/video.mp4"}],
                {},
            )

        self.assertTrue(response.closed)

    def test_output_validation_rejects_an_audio_only_file(self):
        downloader = Tencent()
        with patch.object(
            downloader,
            "_media_tracks",
            return_value={"audio"},
        ):
            with self.assertRaisesRegex(RuntimeError, "缺少视频轨"):
                downloader._validate_output("audio-only.mp4", {})

    def test_output_validation_accepts_video_and_audio_tracks(self):
        downloader = Tencent()
        with patch.object(
            downloader,
            "_media_tracks",
            return_value={"video", "audio"},
        ):
            downloader._validate_output("complete.mp4", {})

    def test_download_retries_after_an_audio_only_candidate(self):
        with tempfile.TemporaryDirectory() as output_dir:
            first_path = os.path.join(output_dir, "first.mp4")
            second_path = os.path.join(output_dir, "second.mp4")
            formats = [
                {
                    "format_id": "first-line",
                    "url": "https://first.example/video.m3u8",
                    "vcodec": "h264",
                    "acodec": "aac",
                },
                {
                    "format_id": "second-line",
                    "url": "https://second.example/video.m3u8",
                    "vcodec": "h264",
                    "acodec": "aac",
                },
            ]
            downloader = Tencent()

            with (
                patch.object(
                    downloader,
                    "_extract_with_yt_dlp",
                    return_value={"title": "目标视频", "formats": formats},
                ),
                patch.object(
                    downloader,
                    "_ordered_candidates",
                    return_value=formats,
                ),
                patch.object(
                    downloader,
                    "_download_candidate",
                    side_effect=[first_path, second_path],
                ) as download_candidate,
                patch.object(
                    downloader,
                    "_validate_output",
                    side_effect=[
                        RuntimeError("下载结果缺少视频轨"),
                        None,
                    ],
                ),
            ):
                result = downloader.download(
                    "https://v.qq.com/x/page/n00467d0py3.html",
                    output_dir,
                    config={"max_threads": 7, "ffmpeg_path": ""},
                )

            self.assertTrue(result.success, result.message)
            self.assertEqual(second_path, result.file_path)
            self.assertEqual(2, download_candidate.call_count)

    def test_candidate_download_caps_tencent_fragment_concurrency(self):
        with tempfile.TemporaryDirectory() as output_dir:
            expected_path = os.path.join(output_dir, "目标视频.mp4")
            _FakeYoutubeDL.info = {
                "title": "目标视频",
                "ext": "mp4",
                "_prepared_filename": expected_path,
            }
            _FakeYoutubeDL.download_flags = []
            _FakeYoutubeDL.extracted_urls = []
            fake_module = types.SimpleNamespace(YoutubeDL=_FakeYoutubeDL)
            downloader = Tencent()

            with (
                patch.dict(sys.modules, {"yt_dlp": fake_module}),
                patch(
                    "platforms.tencent.find_n_m3u8dl",
                    return_value=None,
                ),
                patch(
                    "platforms.tencent.get_ffmpeg_path",
                    return_value=None,
                ),
            ):
                path = downloader._download_candidate(
                    "https://v.qq.com/x/page/n00467d0py3.html",
                    {"title": "目标视频"},
                    {
                        "format_id": "shd-0",
                        "url": "https://fast.example/video.m3u8",
                        "vcodec": "h264",
                        "acodec": "aac",
                    },
                    {},
                    output_dir,
                    {"max_threads": 7, "ffmpeg_path": ""},
                )

            self.assertEqual(expected_path, path)
            self.assertEqual(
                2,
                _FakeYoutubeDL.last_options[
                    "concurrent_fragment_downloads"
                ],
            )
            self.assertEqual(
                "bestvideo+bestaudio/best",
                _FakeYoutubeDL.last_options["format"],
            )
            self.assertEqual(
                ["https://fast.example/video.m3u8"],
                _FakeYoutubeDL.extracted_urls,
            )
            self.assertIn(
                "[shd-0]",
                _FakeYoutubeDL.last_options["outtmpl"],
            )
            self.assertEqual([True], _FakeYoutubeDL.download_flags)

    def test_m3u8_candidate_prefers_n_m3u8dl_backend(self):
        with tempfile.TemporaryDirectory() as output_dir:
            expected_path = os.path.join(
                output_dir,
                "目标视频 [shd-0].mp4",
            )
            downloader = Tencent()
            candidate = {
                "format_id": "shd-0",
                "url": "https://fast.example/video.m3u8?token=signed",
                "http_headers": {"Origin": "https://v.qq.com"},
            }

            with (
                patch(
                    "platforms.tencent.find_n_m3u8dl",
                    return_value="N_m3u8DL-RE.exe",
                ),
                patch(
                    "platforms.tencent.build_n_m3u8dl_command",
                    return_value=["external-command"],
                ) as build_command,
                patch(
                    "platforms.tencent.run_n_m3u8dl",
                    return_value=expected_path,
                ) as run_external,
            ):
                result = downloader._download_candidate(
                    "https://v.qq.com/x/page/n00467d0py3.html",
                    {"title": "目标视频"},
                    candidate,
                    {"User-Agent": "Browser UA"},
                    output_dir,
                    {"max_threads": 4, "ffmpeg_path": ""},
                )

            self.assertEqual(expected_path, result)
            build_command.assert_called_once()
            run_external.assert_called_once()

    def test_failed_n_m3u8dl_backend_falls_back_to_yt_dlp(self):
        with tempfile.TemporaryDirectory() as output_dir:
            expected_path = os.path.join(output_dir, "目标视频.mp4")
            _FakeYoutubeDL.info = {
                "title": "目标视频",
                "ext": "mp4",
                "_prepared_filename": expected_path,
            }
            _FakeYoutubeDL.download_flags = []
            _FakeYoutubeDL.extracted_urls = []
            fake_module = types.SimpleNamespace(YoutubeDL=_FakeYoutubeDL)
            downloader = Tencent()

            with (
                patch.dict(sys.modules, {"yt_dlp": fake_module}),
                patch(
                    "platforms.tencent.find_n_m3u8dl",
                    return_value="N_m3u8DL-RE.exe",
                ),
                patch(
                    "platforms.tencent.build_n_m3u8dl_command",
                    return_value=["external-command"],
                ),
                patch(
                    "platforms.tencent.run_n_m3u8dl",
                    side_effect=RuntimeError("external failed"),
                ),
                patch("platforms.tencent.get_ffmpeg_path", return_value=None),
            ):
                result = downloader._download_candidate(
                    "https://v.qq.com/x/page/n00467d0py3.html",
                    {"title": "目标视频"},
                    {
                        "format_id": "shd-0",
                        "url": "https://fast.example/video.m3u8",
                    },
                    {},
                    output_dir,
                    {"max_threads": 4, "ffmpeg_path": ""},
                )

            self.assertEqual(expected_path, result)
            self.assertEqual(
                ["https://fast.example/video.m3u8"],
                _FakeYoutubeDL.extracted_urls,
            )

    def test_direct_mp4_candidate_skips_n_m3u8dl_backend(self):
        with tempfile.TemporaryDirectory() as output_dir:
            expected_path = os.path.join(output_dir, "目标视频.mp4")
            _FakeYoutubeDL.info = {
                "title": "目标视频",
                "ext": "mp4",
                "_prepared_filename": expected_path,
            }
            _FakeYoutubeDL.download_flags = []
            fake_module = types.SimpleNamespace(YoutubeDL=_FakeYoutubeDL)
            downloader = Tencent()

            with (
                patch.dict(sys.modules, {"yt_dlp": fake_module}),
                patch("platforms.tencent.find_n_m3u8dl") as find_external,
                patch("platforms.tencent.get_ffmpeg_path", return_value=None),
            ):
                result = downloader._download_candidate(
                    "https://v.qq.com/x/page/n00467d0py3.html",
                    {"title": "目标视频"},
                    {
                        "format_id": "shd-0",
                        "url": "https://fast.example/video.mp4?token=signed",
                    },
                    {},
                    output_dir,
                    {"max_threads": 4, "ffmpeg_path": ""},
                )

            self.assertEqual(expected_path, result)
            find_external.assert_not_called()

    def test_extraction_retry_uses_browser_session_headers(self):
        with tempfile.TemporaryDirectory() as output_dir:
            output_path = os.path.join(output_dir, "目标视频.mp4")
            candidate = {
                "format_id": "shd-0",
                "url": "https://video.example/stream.m3u8",
                "vcodec": "h264",
                "acodec": "aac",
            }
            browser_headers = {
                "User-Agent": "Browser UA",
                "Referer": "https://v.qq.com/x/page/n00467d0py3.html",
                "Cookie": "video_guid=browser",
            }
            downloader = Tencent()

            with (
                patch.object(
                    downloader,
                    "_extract_with_yt_dlp",
                    side_effect=[
                        RuntimeError("direct extraction failed"),
                        {"title": "目标视频", "formats": [candidate]},
                    ],
                ) as extract,
                patch.object(
                    downloader,
                    "_capture_browser_context",
                    return_value=browser_headers,
                ),
                patch.object(
                    downloader,
                    "_ordered_candidates",
                    return_value=[candidate],
                ),
                patch.object(
                    downloader,
                    "_download_candidate",
                    return_value=output_path,
                ),
                patch.object(downloader, "_validate_output"),
            ):
                result = downloader.download(
                    "https://v.qq.com/x/page/n00467d0py3.html",
                    output_dir,
                    config={"max_threads": 7, "ffmpeg_path": ""},
                )

            self.assertTrue(result.success, result.message)
            self.assertEqual(browser_headers, extract.call_args_list[1].args[1])

    @unittest.skip("旧浏览器媒体猜测流程已移除")
    def test_player_body_extracts_hls_for_target_video(self):
        player_data = {
            "vl": {
                "vi": [
                    {
                        "vid": "k41005qmjig",
                        "ti": "腾讯目标视频",
                        "ul": {
                            "ui": [
                                {
                                    "url": "https://cdn.example/path/",
                                    "hls": {"pt": "target.m3u8?token=ok"},
                                }
                            ]
                        },
                    }
                ]
            }
        }
        body = json.dumps({"vinfo": json.dumps(player_data)})

        media = Tencent._extract_media_from_player_body(
            body,
            "k41005qmjig",
        )

        self.assertEqual(
            "https://cdn.example/path/target.m3u8?token=ok",
            media["url"],
        )
        self.assertEqual("腾讯目标视频", media["title"])

    @unittest.skip("旧浏览器媒体猜测流程已移除")
    def test_player_body_rejects_a_different_video(self):
        player_data = {
            "vl": {
                "vi": [
                    {
                        "vid": "advertising",
                        "ul": {
                            "ui": [
                                {
                                    "url": "https://ad.example/",
                                    "hls": {"pt": "advertising.m3u8"},
                                }
                            ]
                        },
                    }
                ]
            }
        }
        body = json.dumps({"vinfo": json.dumps(player_data)})

        self.assertIsNone(
            Tencent._extract_media_from_player_body(
                body,
                "k41005qmjig",
            )
        )

    @unittest.skip("旧浏览器媒体猜测流程已移除")
    def test_background_browser_captures_target_player_response(self):
        player_data = {
            "vl": {
                "vi": [
                    {
                        "vid": "k41005qmjig",
                        "ti": "浏览器捕获视频",
                        "ul": {
                            "ui": [
                                {
                                    "url": "https://cdn.example/video/",
                                    "hls": {"pt": "index.m3u8"},
                                }
                            ]
                        },
                    }
                ]
            }
        }
        response_body = json.dumps(
            {"vinfo": json.dumps(player_data)}
        )

        def event(method, params):
            return {
                "message": json.dumps(
                    {
                        "message": {
                            "method": method,
                            "params": params,
                        }
                    }
                )
            }

        class FakeDriver:
            title = "浏览器捕获视频 - 腾讯视频"

            def __init__(self):
                self.closed = False
                self.visited_url = None
                self.logs_read = False

            def get(self, url):
                self.visited_url = url

            def get_log(self, _log_type):
                if self.logs_read:
                    return []
                self.logs_read = True
                return [
                    event(
                        "Network.responseReceived",
                        {
                            "requestId": "target-request",
                            "response": {
                                "url": "https://vd6.l.qq.com/proxyhttp",
                                "mimeType": "application/json",
                            },
                        },
                    ),
                    event(
                        "Network.loadingFinished",
                        {"requestId": "target-request"},
                    ),
                ]

            def execute_cdp_cmd(self, command, _params):
                if command == "Network.getResponseBody":
                    return {"body": response_body}
                return {}

            def execute_script(self, script):
                if "navigator.userAgent" in script:
                    return "Captured Browser UA"
                return None

            def get_cookies(self):
                return [{"name": "video_guid", "value": "browser"}]

            def quit(self):
                self.closed = True

        driver = FakeDriver()
        downloader = Tencent()
        with (
            patch.object(
                downloader,
                "create_background_driver",
                return_value=driver,
            ),
            patch("platforms.tencent.time.sleep"),
        ):
            captured = downloader._capture_browser_media(
                "https://v.qq.com/x/page/k41005qmjig.html",
                timeout_seconds=2,
            )

        self.assertEqual(
            "https://cdn.example/video/index.m3u8",
            captured["url"],
        )
        self.assertEqual("Captured Browser UA", captured["user_agent"])
        self.assertEqual("browser", captured["cookies"][0]["value"])
        self.assertTrue(driver.closed)

    @unittest.skip("旧浏览器媒体猜测流程已移除")
    def test_background_browser_waits_for_a_slow_player_response(self):
        player_data = {
            "vl": {
                "vi": [
                    {
                        "vid": "n00467d0py3",
                        "ti": "延迟出现的视频",
                        "ul": {
                            "ui": [
                                {
                                    "url": "https://cdn.example/video/",
                                    "hls": {"pt": "slow.m3u8"},
                                }
                            ]
                        },
                    }
                ]
            }
        }
        response_body = json.dumps(
            {"vinfo": json.dumps(player_data)}
        )

        def event(method, params):
            return {
                "message": json.dumps(
                    {
                        "message": {
                            "method": method,
                            "params": params,
                        }
                    }
                )
            }

        class DelayedDriver:
            title = "延迟出现的视频 - 腾讯视频"

            def __init__(self):
                self.logs_read = 0
                self.closed = False

            def get(self, _url):
                pass

            def get_log(self, _log_type):
                self.logs_read += 1
                if self.logs_read != 41:
                    return []
                return [
                    event(
                        "Network.responseReceived",
                        {
                            "requestId": "slow-request",
                            "response": {
                                "url": "https://vd6.l.qq.com/proxyhttp"
                            },
                        },
                    ),
                    event(
                        "Network.loadingFinished",
                        {"requestId": "slow-request"},
                    ),
                ]

            def execute_cdp_cmd(self, command, _params):
                if command == "Network.getResponseBody":
                    return {"body": response_body}
                return {}

            def execute_script(self, script):
                if "navigator.userAgent" in script:
                    return "Delayed Browser UA"
                return None

            def get_cookies(self):
                return []

            def quit(self):
                self.closed = True

        driver = DelayedDriver()
        downloader = Tencent()
        with (
            patch.object(
                downloader,
                "create_background_driver",
                return_value=driver,
            ),
            patch("platforms.tencent.time.sleep"),
        ):
            captured = downloader._capture_browser_media(
                "https://v.qq.com/x/cover/mzc0020016apvkq/"
                "n00467d0py3.html"
            )

        self.assertEqual(
            "https://cdn.example/video/slow.m3u8",
            captured["url"],
        )
        self.assertEqual(41, driver.logs_read)
        self.assertTrue(driver.closed)

    @unittest.skip("旧浏览器媒体猜测流程已移除")
    def test_background_browser_uses_media_after_target_vinfo_proxy(self):
        target_body = json.dumps(
            {
                "ret": 0,
                "data": {
                    "playInfo": {"vid": "n00467d0py3"},
                    "videoInfo": {
                        "vid": "n00467d0py3",
                        "title": "encrypted-player-title",
                    },
                    "proxyhttp": {"vinfo": "encrypted-player-data"},
                },
            }
        )

        def event(method, params):
            return {
                "message": json.dumps(
                    {
                        "message": {
                            "method": method,
                            "params": params,
                        }
                    }
                )
            }

        class VinfoProxyDriver:
            title = "新版播放器目标视频 - 腾讯视频"

            def __init__(self):
                self.logs_read = 0
                self.closed = False

            def get(self, _url):
                pass

            def get_log(self, _log_type):
                self.logs_read += 1
                if self.logs_read == 1:
                    return [
                        event(
                            "Network.responseReceived",
                            {
                                "requestId": "vinfo-request",
                                "response": {
                                    "url": (
                                        "https://vd6.l.qq.com/"
                                        "vinfo_proxy"
                                    )
                                },
                            },
                        ),
                        event(
                            "Network.loadingFinished",
                            {"requestId": "vinfo-request"},
                        ),
                        event(
                            "Network.responseReceived",
                            {
                                "requestId": "advertisement-manifest",
                                "response": {
                                    "url": (
                                        "https://video.example/ad/"
                                        "advertisement.m3u8"
                                    )
                                },
                            },
                        ),
                    ]
                if self.logs_read == 2:
                    return [
                        event(
                            "Network.responseReceived",
                            {
                                "requestId": "manifest-request",
                                "response": {
                                    "url": (
                                        "https://video.example/target/"
                                        "index.m3u8?token=browser"
                                    )
                                },
                            },
                        )
                    ]
                return []

            def execute_cdp_cmd(self, command, _params):
                if command == "Network.getResponseBody":
                    return {"body": target_body}
                return {}

            def execute_script(self, script):
                if "navigator.userAgent" in script:
                    return "Vinfo Proxy Browser UA"
                if "Number.isFinite" in script:
                    return self.logs_read >= 2
                return None

            def get_cookies(self):
                return [{"name": "guid", "value": "target"}]

            def quit(self):
                self.closed = True

        driver = VinfoProxyDriver()
        downloader = Tencent()
        with (
            patch.object(
                downloader,
                "create_background_driver",
                return_value=driver,
            ),
            patch("platforms.tencent.time.sleep"),
        ):
            captured = downloader._capture_browser_media(
                "https://v.qq.com/x/cover/mzc0020016apvkq/"
                "n00467d0py3.html",
                timeout_seconds=1,
            )

        self.assertEqual(
            "https://video.example/target/index.m3u8?token=browser",
            captured["url"],
        )
        self.assertEqual("新版播放器目标视频", captured["title"])
        self.assertEqual("n00467d0py3", captured["video_id"])
        self.assertTrue(driver.closed)

    @unittest.skip("旧浏览器媒体猜测流程已移除")
    def test_background_browser_uses_playing_video_without_vinfo_event(self):
        advertisement_url = (
            "https://video.example/ad/advertisement.m3u8"
        )
        target_url = (
            "https://video.example/target/index.m3u8?token=browser"
        )

        def event(url):
            return {
                "message": json.dumps(
                    {
                        "message": {
                            "method": "Network.responseReceived",
                            "params": {
                                "requestId": url,
                                "response": {"url": url},
                            },
                        }
                    }
                )
            }

        class PlaybackDriver:
            title = "页面正片标题_腾讯视频"

            def __init__(self):
                self.logs_read = 0
                self.closed = False

            def get(self, _url):
                pass

            def get_log(self, _log_type):
                self.logs_read += 1
                if self.logs_read == 1:
                    return [event(advertisement_url)]
                if self.logs_read == 2:
                    return [event(target_url)]
                return []

            def execute_cdp_cmd(self, _command, _params):
                return {}

            def execute_script(self, script):
                if "navigator.userAgent" in script:
                    return "Playback Browser UA"
                if "performance.getEntriesByType" in script:
                    urls = [advertisement_url]
                    if self.logs_read >= 2:
                        urls.append(target_url)
                    return {
                        "main_started": self.logs_read >= 2,
                        "media_urls": urls,
                    }
                return None

            def get_cookies(self):
                return []

            def quit(self):
                self.closed = True

        driver = PlaybackDriver()
        downloader = Tencent()
        with (
            patch.object(
                downloader,
                "create_background_driver",
                return_value=driver,
            ),
            patch("platforms.tencent.time.sleep"),
        ):
            captured = downloader._capture_browser_media(
                "https://v.qq.com/x/cover/mzc0020016apvkq/"
                "n00467d0py3.html",
                timeout_seconds=1,
            )

        self.assertEqual(target_url, captured["url"])
        self.assertEqual("页面正片标题", captured["title"])
        self.assertEqual("n00467d0py3", captured["video_id"])
        self.assertTrue(driver.closed)

    @unittest.skip("旧 browser-first 下载流程已移除")
    def test_download_uses_browser_media_before_page_extractor(self):
        with tempfile.TemporaryDirectory() as output_dir:
            expected_path = os.path.join(
                output_dir,
                "浏览器目标视频.mp4",
            )
            captured_url = (
                "https://cdn.example/video/target.m3u8?token=ok"
            )
            _FakeYoutubeDL.info = {
                "title": "浏览器目标视频",
                "ext": "mp4",
                "_prepared_filename": expected_path,
            }
            _FakeYoutubeDL.download_flags = []
            _FakeYoutubeDL.extracted_urls = []
            fake_module = types.SimpleNamespace(YoutubeDL=_FakeYoutubeDL)
            downloader = Tencent()

            with (
                patch.dict(sys.modules, {"yt_dlp": fake_module}),
                patch.object(
                    downloader,
                    "_capture_browser_media",
                    return_value={
                        "url": captured_url,
                        "title": "浏览器目标视频",
                        "cookies": [
                            {"name": "video_guid", "value": "browser"}
                        ],
                        "user_agent": "Captured Browser UA",
                        "referer": (
                            "https://v.qq.com/x/page/k41005qmjig.html"
                        ),
                    },
                ) as capture,
            ):
                result = downloader.download(
                    "https://v.qq.com/x/page/k41005qmjig.html",
                    output_dir,
                    config={"max_threads": 7, "ffmpeg_path": ""},
                )

            self.assertTrue(result.success, result.message)
            self.assertEqual(expected_path, result.file_path)
            self.assertEqual([True], _FakeYoutubeDL.download_flags)
            self.assertEqual([captured_url], _FakeYoutubeDL.extracted_urls)
            self.assertEqual(
                "video_guid=browser",
                _FakeYoutubeDL.last_options["http_headers"]["Cookie"],
            )
            self.assertEqual(
                "Captured Browser UA",
                _FakeYoutubeDL.last_options["http_headers"]["User-Agent"],
            )
            capture.assert_called_once()

    @unittest.skip("旧 browser-first 下载流程已移除")
    def test_yt_dlp_download_is_used_when_browser_capture_is_unavailable(self):
        with tempfile.TemporaryDirectory() as output_dir:
            expected_path = os.path.join(output_dir, "tencent.mp4")
            _FakeYoutubeDL.info = {
                "title": "腾讯回退",
                "ext": "mp4",
                "formats": [],
                "_prepared_filename": expected_path,
            }
            _FakeYoutubeDL.download_flags = []
            fake_module = types.SimpleNamespace(YoutubeDL=_FakeYoutubeDL)

            downloader = Tencent()
            with (
                patch.dict(sys.modules, {"yt_dlp": fake_module}),
                patch.object(
                    downloader,
                    "_capture_browser_media",
                    side_effect=RuntimeError("capture unavailable"),
                ),
            ):
                result = downloader.download(
                    "https://v.qq.com/x/page/example.html",
                    output_dir,
                    config={"max_threads": 3, "ffmpeg_path": ""},
                )

            self.assertTrue(result.success, result.message)
            self.assertEqual(expected_path, result.file_path)
            self.assertEqual([True], _FakeYoutubeDL.download_flags)

    @unittest.skip("旧 browser-first 下载流程已移除")
    def test_video_page_falls_back_to_vqq_extractor_when_capture_fails(self):
        with tempfile.TemporaryDirectory() as output_dir:
            expected_path = os.path.join(output_dir, "tencent.mp4")
            _FakeYoutubeDL.info = {
                "title": "腾讯测试视频",
                "ext": "mp4",
                "_prepared_filename": expected_path,
            }
            _FakeYoutubeDL.last_options = None
            fake_module = types.SimpleNamespace(YoutubeDL=_FakeYoutubeDL)
            downloader = Tencent()

            with (
                patch.dict(sys.modules, {"yt_dlp": fake_module}),
                patch.object(
                    downloader,
                    "_capture_browser_media",
                    side_effect=RuntimeError("capture unavailable"),
                ),
            ):
                result = downloader.download(
                    "https://v.qq.com/x/cover/example/video.html",
                    output_dir,
                )

            self.assertTrue(result.success, result.message)
            self.assertEqual(expected_path, result.file_path)

    @unittest.skip("腾讯并发策略已改为固定上限 2")
    def test_configured_threads_control_fragment_concurrency(self):
        with tempfile.TemporaryDirectory() as output_dir:
            expected_path = os.path.join(output_dir, "tencent.mp4")
            _ConcurrentYoutubeDL.info = {
                "title": "腾讯并发测试",
                "ext": "mp4",
                "_prepared_filename": expected_path,
            }
            fake_module = types.SimpleNamespace(
                YoutubeDL=_ConcurrentYoutubeDL
            )
            downloader = Tencent()

            with (
                patch.dict(sys.modules, {"yt_dlp": fake_module}),
                patch.object(
                    downloader,
                    "_capture_browser_media",
                    side_effect=RuntimeError("capture unavailable"),
                ),
            ):
                result = downloader.download(
                    "https://v.qq.com/x/cover/example/video.html",
                    output_dir,
                    config={"max_threads": 7, "ffmpeg_path": ""},
                )

            self.assertTrue(result.success, result.message)
            self.assertEqual(expected_path, result.file_path)


class IQiyiDownloaderTests(unittest.TestCase):
    def test_media_selection_rejects_ad_and_uses_target_tvid(self):
        entries = [
            (
                "https://pcw-data.video.iqiyi.com/videos/other/ad.f4v"
                "?qd_tvid=advertisement"
            ),
            (
                "https://pcw-data.video.iqiyi.com/videos/v1/target.f4v"
                "?qd_tvid=5017450200&qd_index=1"
            ),
        ]
        select_media = getattr(
            IQiyi,
            "_select_target_media_url",
            lambda urls, target_tvid: None,
        )

        self.assertEqual(
            entries[1],
            select_media(entries, "5017450200"),
        )

    def test_media_selection_accepts_target_m3u8(self):
        entries = [
            (
                "https://meta-cdn.video.iqiyi.com/ad.m3u8"
                "?qd_tvid=advertisement"
            ),
            (
                "https://meta-cdn.video.iqiyi.com/target.m3u8"
                "?qd_tvid=3515592099674800&qd_index=vod"
            ),
        ]

        self.assertEqual(
            entries[1],
            IQiyi._select_target_media_url(
                entries,
                "3515592099674800",
            ),
        )

    def test_video_page_captures_target_media_in_background(self):
        target_url = (
            "https://pcw-data.video.iqiyi.com/videos/v1/target.f4v"
            "?qd_tvid=5017450200&qd_index=1"
        )

        def performance_entry(url):
            return {
                "message": json.dumps(
                    {
                        "message": {
                            "method": "Network.responseReceived",
                            "params": {"response": {"url": url}},
                        }
                    }
                )
            }

        class FakeDriver:
            title = "爱奇艺目标视频"

            def __init__(self):
                self.closed = False
                self.visited_url = None

            def get(self, url):
                self.visited_url = url

            def get_log(self, log_type):
                return [
                    performance_entry(
                        "https://mesh.if.iqiyi.com/player/pcw/video/"
                        "playervideoinfo?id=5017450200"
                    ),
                    performance_entry(
                        "https://pcw-data.video.iqiyi.com/videos/other/ad.f4v"
                        "?qd_tvid=advertisement"
                    ),
                    performance_entry(target_url),
                ]

            def get_cookies(self):
                return [{"name": "QC005", "value": "device-cookie"}]

            def quit(self):
                self.closed = True

        resolver_response = Mock()
        resolver_response.raise_for_status.return_value = None
        resolver_response.headers = {"Content-Type": "application/json"}
        resolver_response.json.return_value = {
            "d": [{"URL": "https://cdn.iqiyi.example/target.f4v"}]
        }
        resolver_response.iter_content.return_value = [b"resolver-json"]

        media_response = Mock()
        media_response.raise_for_status.return_value = None
        media_response.headers = {"Content-Type": "video/x-flv"}
        media_response.iter_content.return_value = [b"target-video-bytes"]
        driver = FakeDriver()

        with (
            tempfile.TemporaryDirectory() as output_dir,
            patch.object(
                IQiyi,
                "create_background_driver",
                return_value=driver,
            ),
            patch(
                "platforms.iqiyi.requests.get",
                side_effect=[resolver_response, media_response],
            ),
            patch("time.sleep"),
        ):
            result = IQiyi().download(
                "https://www.iqiyi.com/v_target.html",
                output_dir,
            )

            self.assertTrue(result.success, result.message)
            with open(result.file_path, "rb") as downloaded_file:
                self.assertEqual(
                    b"target-video-bytes",
                    downloaded_file.read(),
                )

        self.assertTrue(driver.closed)


class DouyinDownloaderTests(unittest.TestCase):
    def test_status_updates_are_scheduled_on_the_tk_main_thread(self):
        callbacks = []
        downloader = Douyin()
        downloader.status_var = Mock()
        downloader.app = types.SimpleNamespace(
            root=types.SimpleNamespace(
                after=lambda delay, callback: callbacks.append(callback)
            )
        )

        downloader._set_status("下载中")

        downloader.status_var.set.assert_not_called()
        self.assertEqual(1, len(callbacks))
        callbacks[0]()
        downloader.status_var.set.assert_called_once_with("下载中")

    def test_short_share_link_is_resolved_before_extracting_aweme_id(self):
        response = Mock()
        response.url = "https://www.douyin.com/video/7666163361146621227"
        response.raise_for_status.return_value = None

        with patch("platforms.douyin.requests.get", return_value=response) as get:
            video_url, aweme_id = Douyin._resolve_video_url(
                "https://v.douyin.com/AbCdEf/"
            )

        self.assertEqual(response.url, video_url)
        self.assertEqual("7666163361146621227", aweme_id)
        get.assert_called_once_with(
            "https://v.douyin.com/AbCdEf/",
            allow_redirects=True,
            headers=Douyin.REQUEST_HEADERS,
            timeout=15,
        )

    def test_state_lookup_selects_requested_video_instead_of_first_ad(self):
        state = {
            "feed": {
                "aweme_list": [
                    {
                        "aweme_id": "advertisement",
                        "desc": "广告",
                        "video": {
                            "play_addr": {
                                "url_list": ["https://cdn.example/ad.mp4"]
                            }
                        },
                    },
                    {
                        "aweme_id": "7666163361146621227",
                        "desc": "用户作品",
                        "video": {
                            "play_addr": {
                                "url_list": ["https://cdn.example/target.mp4"]
                            }
                        },
                    },
                ]
            }
        }

        title, video_url = Douyin._find_target_video(
            state, "7666163361146621227"
        )

        self.assertEqual("用户作品", title)
        self.assertEqual("https://cdn.example/target.mp4", video_url)

    def test_state_lookup_rejects_page_ad_when_target_is_absent(self):
        state = {
            "aweme_detail": {
                "aweme_id": "advertisement",
                "video": {
                    "play_addr": {"url_list": ["https://cdn.example/ad.mp4"]}
                },
            }
        }

        self.assertEqual(
            (None, None),
            Douyin._find_target_video(state, "7666163361146621227"),
        )

    def test_dom_lookup_selects_video_url_tagged_with_requested_id(self):
        candidates = [
            {
                "src": "https://cdn.example/ad.mp4?__vid=advertisement",
                "ancestor_href": "",
            },
            {
                "src": (
                    "https://v26-web.douyinvod.com/target.mp4"
                    "?mime_type=video_mp4&__vid=7666163361146621227"
                ),
                "ancestor_href": "",
            },
        ]

        self.assertEqual(
            candidates[1]["src"],
            Douyin._select_target_dom_video(
                candidates, "7666163361146621227"
            ),
        )

    def test_dom_lookup_selects_video_linked_to_requested_work(self):
        candidate = {
            "src": "https://v26-web.douyinvod.com/target.mp4",
            "ancestor_href": (
                "https://www.douyin.com/video/7666163361146621227"
            ),
        }

        self.assertEqual(
            candidate["src"],
            Douyin._select_target_dom_video(
                [candidate], "7666163361146621227"
            ),
        )

    def test_network_capture_selects_separate_video_and_audio_streams(self):
        def entry(url, mime_type):
            return {
                "message": json.dumps(
                    {
                        "message": {
                            "method": "Network.responseReceived",
                            "params": {
                                "response": {
                                    "url": url,
                                    "mimeType": mime_type,
                                }
                            },
                        }
                    }
                )
            }

        video = "https://v26-web.douyinvod.com/x/media-video-hvc1/"
        audio = "https://v26-web.douyinvod.com/x/media-audio-und-mp4a/"
        entries = [
            entry("https://example.com/ad.mp4", "video/mp4"),
            entry(audio, "audio/mp4"),
            entry(video, "video/mp4"),
        ]

        self.assertEqual(
            (video, audio),
            Douyin._network_media_urls(entries),
        )

    def test_dom_lookup_rejects_untagged_page_ad(self):
        candidates = [
            {
                "src": "https://cdn.example/ad.mp4",
                "ancestor_href": "",
            }
        ]

        self.assertIsNone(
            Douyin._select_target_dom_video(
                candidates, "7666163361146621227"
            )
        )


if __name__ == "__main__":
    unittest.main()
