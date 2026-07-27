import os
import json
import sys
import tempfile
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

    def __init__(self, options):
        type(self).last_options = options

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def extract_info(self, url, download):
        self.extracted_url = url
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


class TencentDownloaderTests(unittest.TestCase):
    def test_video_page_uses_vqq_extractor_before_legacy_page_parsing(self):
        with tempfile.TemporaryDirectory() as output_dir:
            expected_path = os.path.join(output_dir, "tencent.mp4")
            _FakeYoutubeDL.info = {
                "title": "腾讯测试视频",
                "ext": "mp4",
                "_prepared_filename": expected_path,
            }
            _FakeYoutubeDL.last_options = None
            fake_module = types.SimpleNamespace(YoutubeDL=_FakeYoutubeDL)

            with (
                patch.dict(sys.modules, {"yt_dlp": fake_module}),
                patch(
                    "platforms.tencent.requests.Session",
                    side_effect=AssertionError("不应先读取旧版页面状态"),
                ),
            ):
                result = Tencent().download(
                    "https://v.qq.com/x/cover/example/video.html",
                    output_dir,
                )

            self.assertTrue(result.success, result.message)
            self.assertEqual(expected_path, result.file_path)

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

            with (
                patch.dict(sys.modules, {"yt_dlp": fake_module}),
                patch(
                    "platforms.tencent.requests.Session",
                    side_effect=AssertionError("并发配置未传给 yt-dlp"),
                ),
            ):
                result = Tencent().download(
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
