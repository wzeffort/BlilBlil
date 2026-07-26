import os
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

from core.downloader import BaseDownloader, DownloadResult
from core.utils import get_ffmpeg_path
from platforms.bilibili import Bilibili
from platforms.douyin import Douyin


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


class BilibiliDownloaderTests(unittest.TestCase):
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
        self.assertEqual(1, len(callbacks))
        callbacks[0]()
        self.assertEqual(2, len(callbacks))
        result = callbacks[1]
        self.assertIsInstance(result, DownloadResult)
        self.assertFalse(result.success)
        self.assertIn("network exploded", result.message)


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
