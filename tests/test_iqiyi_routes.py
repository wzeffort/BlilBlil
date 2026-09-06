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
