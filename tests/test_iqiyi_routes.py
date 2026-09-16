import unittest
import os
import tempfile
from unittest.mock import Mock, patch


MANIFEST = """#EXTM3U
#EXT-X-TARGETDURATION:10
#EXTINF:10,
https://data.video.iqiyi.com/videos/vts/video.ts?start=0&end=100&contentlength=100&sd=1
#EXTINF:10,
https://data.video.iqiyi.com/videos/vts/video.ts?start=100&end=200&contentlength=100&sd=1
#EXT-X-ENDLIST
"""
CDN = "https://cdn.example/videos/vts/video.ts?qd_tvid=123&qd_sc=session&start=0&end=100&contentlength=100&sd=1"


class IQiyiRouteTests(unittest.TestCase):
    def test_accepts_player_metadata_without_replacing_cdn_session(self):
        from core.iqiyi_routes import resolve_browser_manifest
        manifest = MANIFEST.replace('&sd=1', '&sd=1&qd_tvid=123&qd_idx=player&qd_sc=manifest')
        result = resolve_browser_manifest(manifest, [CDN], '123')
        self.assertIsNotNone(result)
        self.assertIn('qd_sc=session', result)
        self.assertNotIn('qd_sc=manifest', result)
        self.assertIsNone(resolve_browser_manifest(manifest.replace('qd_tvid=123', 'qd_tvid=999'), [CDN], '123'))

    def test_requires_independent_signed_session_for_each_resource(self):
        from core.iqiyi_routes import resolve_browser_manifest, missing_resource_seek
        manifest = MANIFEST.replace('video.ts?start=100', 'second.ts?start=100')
        second = CDN.replace('video.ts', 'second.ts').replace('start=0', 'start=100').replace('end=100', 'end=200').replace('session', 'second-session')
        self.assertIsNone(resolve_browser_manifest(manifest, [CDN], '123'))
        self.assertEqual('/videos/vts/second.ts', missing_resource_seek(manifest, [CDN], '123')[0])
        result = resolve_browser_manifest(manifest, [CDN, second], '123')
        self.assertIn('qd_sc=second-session', result)
        self.assertEqual(2, result.count('#EXTINF:'))
        self.assertIsNone(missing_resource_seek(manifest, [CDN, second], '123'))

    def test_timestamp_hint_is_not_part_of_byte_range_identity(self):
        from core.iqiyi_routes import resolve_browser_manifest
        self.assertIsNotNone(resolve_browser_manifest(MANIFEST, [CDN.replace('sd=1', 'sd=0')], '123'))

    def test_cdn_aligned_range_requires_exact_signed_scheduler_evidence(self):
        from core.iqiyi_routes import resolve_browser_manifest
        aligned = CDN.replace('end=100', 'end=1024').replace('contentlength=100', 'contentlength=1024')
        schedule = CDN.replace('cdn.example', 'data.video.iqiyi.com')
        self.assertIsNone(resolve_browser_manifest(MANIFEST, [aligned], '123'))
        self.assertIsNone(resolve_browser_manifest(MANIFEST, [aligned, schedule.replace('session', 'other')], '123'))
        self.assertIsNotNone(resolve_browser_manifest(MANIFEST, [aligned, schedule], '123'))

    def test_browser_waits_for_matching_quality_before_closing(self):
        from platforms.iqiyi import IQiyi
        downloader = IQiyi()
        driver = Mock()
        driver.title = '测试-爱奇艺'
        driver.get_cookies.return_value = []
        playlist = 'https://meta.example/video.m3u8?qd_tvid=123'
        batches = [
            ['https://example.com/playervideoinfo?id=123', playlist,
             CDN.replace('video.ts', 'other.ts')],
            [CDN],
        ]
        response = Mock()
        response.text = MANIFEST
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(downloader, 'create_background_driver', return_value=driver),
            patch.object(downloader, '_performance_urls', side_effect=batches),
            patch('platforms.iqiyi.time.sleep'),
            patch('platforms.iqiyi.requests.get', return_value=response),
            patch.object(downloader, '_download_hls', return_value='video.mp4') as download,
        ):
            result = downloader._download_video_page('https://www.iqiyi.com/v_test.html', directory)
        self.assertTrue(result.success, result.message)
        self.assertEqual(2, driver.get_log.call_count)
        self.assertEqual(MANIFEST, download.call_args.kwargs['manifest'])
        driver.quit.assert_called_once()

    def test_hls_dispatches_complete_resolved_playlist_to_native_downloader(self):
        from platforms.iqiyi import IQiyi
        downloader = IQiyi()
        response = Mock()
        response.text = MANIFEST
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        with tempfile.TemporaryDirectory() as output_dir:
            expected = os.path.join(output_dir, "video.mp4")
            def run(command, *_args):
                with open(command[1], encoding="utf-8") as file:
                    playlist = file.read()
                self.assertNotIn("data.video.iqiyi.com", playlist)
                self.assertEqual(2, playlist.count("#EXTINF:"))
                return expected
            with (
                patch("platforms.iqiyi.requests.get", return_value=response),
                patch("platforms.iqiyi.find_n_m3u8dl", return_value="downloader.exe", create=True),
                patch("platforms.iqiyi.run_n_m3u8dl", side_effect=run, create=True),
                patch.object(downloader, "_validate_hls_output", create=True),
            ):
                result = downloader._download_hls("https://meta.example/video.m3u8", [CDN], "123", {}, expected, {})
            self.assertEqual(expected, result)

    def test_uses_matching_cdn_session_and_preserves_every_fragment_range(self):
        from core.iqiyi_routes import resolve_browser_manifest
        result = resolve_browser_manifest(MANIFEST, [CDN], "123")
        from urllib.parse import urlsplit, parse_qs
        urls = [line for line in result.splitlines() if line and not line.startswith("#")]
        self.assertEqual(2, len(urls))
        self.assertEqual(["cdn.example", "cdn.example"], [urlsplit(u).hostname for u in urls])
        self.assertEqual(["0", "100"], [parse_qs(urlsplit(u).query)["start"][0] for u in urls])
        self.assertEqual(["100", "200"], [parse_qs(urlsplit(u).query)["end"][0] for u in urls])
        self.assertEqual(["session", "session"], [parse_qs(urlsplit(u).query)["qd_sc"][0] for u in urls])

    def test_rejects_ad_other_resource_range_and_unsigned_schedule(self):
        from core.iqiyi_routes import resolve_browser_manifest
        for url in (CDN.replace("123", "999"), CDN.replace("video.ts", "other.ts"),
                    CDN.replace("start=0", "start=5"),
                    CDN.replace("qd_sc=session&", "")):
            with self.subTest(url=url):
                self.assertIsNone(resolve_browser_manifest(MANIFEST, [url], "123"))

    def test_rejects_incompatible_playlists(self):
        from core.iqiyi_routes import resolve_browser_manifest
        for manifest in (MANIFEST.replace("#EXT-X-ENDLIST", ""),
                         MANIFEST.replace("#EXTM3U", '#EXTM3U\n#EXT-X-KEY:METHOD=AES-128,URI="key"'),
                         MANIFEST.replace("video.ts?start=100", "other.ts?start=100")):
            with self.subTest(manifest=manifest):
                self.assertIsNone(resolve_browser_manifest(manifest, [CDN], "123"))
