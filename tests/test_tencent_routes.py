import json
import os
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from platforms.tencent import Tencent


MANIFEST = """#EXTM3U
#EXT-X-TARGETDURATION:12
#EXTINF:12,
00_video.ts?index=0&brs=0&bre=99&token=first
#EXTINF:12,
01_video.ts?index=1&brs=100&bre=199&token=second
#EXT-X-ENDLIST
"""
SOURCE = "https://old.example/old-session/video.m3u8"
OBSERVED = "https://new.example/browser-session/00_video.ts?index=0&brs=0&bre=99&token=first"


class TencentRouteTests(unittest.TestCase):
    def test_track_validation_handles_utf8_ffmpeg_output_on_windows(self):
        from core.utils import get_ffmpeg_path

        ffmpeg = get_ffmpeg_path()
        if not ffmpeg:
            self.skipTest("FFmpeg unavailable")
        with tempfile.TemporaryDirectory() as temp_dir:
            media = os.path.join(temp_dir, "中文视频.mp4")
            subprocess.run([
                ffmpeg, "-v", "error", "-f", "lavfi", "-i", "color=size=16x16:rate=1",
                "-f", "lavfi", "-i", "sine=frequency=440", "-t", "1",
                "-c:v", "mpeg4", "-c:a", "aac", "-metadata", "title=中文视频", media,
            ], check=True, capture_output=True, timeout=15)
            self.assertEqual({"audio", "video"}, Tencent()._media_tracks(media, {}))

    def test_rebases_complete_playlist_only_after_exact_segment_match(self):
        from core.tencent_routes import rebase_manifest

        result = rebase_manifest(MANIFEST, SOURCE, OBSERVED)
        self.assertIn(OBSERVED, result)
        self.assertIn(
            "https://new.example/browser-session/01_video.ts?index=1&brs=100&bre=199&token=second",
            result,
        )
        self.assertEqual(2, result.count("#EXTINF:"))
        self.assertIn("#EXT-X-ENDLIST", result)

    def test_rejects_ads_other_signatures_and_incompatible_playlists(self):
        from core.tencent_routes import rebase_manifest

        for observed in (OBSERVED.replace("video.ts", "ad.ts"),
                         OBSERVED.replace("token=first", "token=other"),
                         OBSERVED.replace("brs=0", "brs=1")):
            with self.subTest(observed=observed):
                self.assertIsNone(rebase_manifest(MANIFEST, SOURCE, observed))
        for manifest in (MANIFEST.replace("#EXT-X-ENDLIST", ""),
                         MANIFEST.replace("#EXTM3U", '#EXTM3U\n#EXT-X-KEY:METHOD=AES-128,URI="key"'),
                         MANIFEST.replace("01_video.ts", "https://other.example/01_video.ts")):
            with self.subTest(manifest=manifest):
                self.assertIsNone(rebase_manifest(manifest, SOURCE, OBSERVED))

    def test_capture_ignores_ad_and_returns_matching_route_and_closes_driver(self):
        downloader = Tencent()
        driver = Mock()
        events = []
        for url in (OBSERVED.replace("video.ts", "ad.ts"), OBSERVED):
            events.append({"message": json.dumps({"message": {
                "method": "Network.responseReceived",
                "params": {"response": {"url": url, "status": 200}},
            }})})
        driver.get_log.return_value = events
        with patch.object(downloader, "create_background_driver", return_value=driver):
            manifest = downloader._capture_browser_route("https://v.qq.com/x/page/z0022yjl3ep.html", MANIFEST, SOURCE)
        self.assertIn("browser-session/01_video.ts", manifest)
        driver.quit.assert_called_once()

    def test_low_speed_uses_browser_route_before_old_download(self):
        downloader = Tencent()
        formats = [{"url": SOURCE, "format_id": "hd"}]
        def ordered(*args):
            downloader._fastest_probe_speed = 800
            return formats
        with tempfile.TemporaryDirectory() as output_dir:
            expected = os.path.join(output_dir, "browser.mp4")
            with (
                patch.object(downloader, "_extract_with_yt_dlp", return_value={"title": "video", "formats": formats}),
                patch.object(downloader, "_ordered_candidates", side_effect=ordered),
                patch.object(downloader, "_download_browser_route", return_value=expected),
                patch.object(downloader, "_download_candidate", side_effect=AssertionError("must not use slow route")),
                patch.object(downloader, "_validate_output") as validate,
                patch("platforms.tencent.find_n_m3u8dl", return_value="downloader.exe"),
            ):
                result = downloader.download("https://v.qq.com/x/page/z0022yjl3ep.html", output_dir)
            self.assertTrue(result.success)
            self.assertEqual(expected, result.file_path)
            validate.assert_called_once_with(expected, None)

    def test_capture_cancellation_closes_browser(self):
        from core.downloader import DownloadCancelled

        downloader = Tencent()
        driver = Mock()
        downloader.stop_download()
        with patch.object(downloader, "create_background_driver", return_value=driver):
            with self.assertRaises(DownloadCancelled):
                downloader._capture_browser_route("https://v.qq.com/", MANIFEST, SOURCE)
        driver.quit.assert_called_once()

    def test_capture_deadline_closes_browser_without_guessing_media(self):
        downloader = Tencent()
        driver = Mock()
        with (
            patch.object(downloader, "create_background_driver", return_value=driver),
            patch("platforms.tencent.time.monotonic", side_effect=[0, 2]),
        ):
            with self.assertRaises(RuntimeError):
                downloader._capture_browser_route("https://v.qq.com/", MANIFEST, SOURCE, timeout_seconds=1)
        driver.quit.assert_called_once()
