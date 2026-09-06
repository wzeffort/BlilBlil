import unittest
import os
import tempfile
from unittest.mock import Mock, patch

from platforms.youku import Youku


class YoukuDownloadTests(unittest.TestCase):
    def test_normalizes_duplicated_tracking_link(self):
        clean = "https://v.youku.com/v_show/id_XNjU1NTM0OTc0OA==.html"
        pasted = (clean + "?spm=tracking&s=show&scg_id=123") * 2
        self.assertEqual(clean, Youku._normalize_url(pasted))

    def test_rejects_ambiguous_different_videos(self):
        with self.assertRaises(ValueError):
            Youku._normalize_url("https://v.youku.com/v_show/id_XXX=.html https://v.youku.com/v_show/id_YYY=.html")

    def test_download_uses_supported_extractor_and_requires_all_fragments(self):
        downloader = Youku()
        clean = "https://v.youku.com/v_show/id_XNjU1NTM0OTc0OA==.html"
        with tempfile.TemporaryDirectory() as output_dir:
            expected = os.path.join(output_dir, "video.mp4")
            ydl = Mock()
            ydl.__enter__ = Mock(return_value=ydl)
            ydl.__exit__ = Mock(return_value=False)
            ydl.prepare_filename.return_value = expected
            ydl.extract_info.return_value = {"title": "video", "ext": "mp4"}
            with (
                patch("yt_dlp.YoutubeDL", return_value=ydl) as factory,
                patch.object(downloader, "_validate_output", create=True),
            ):
                result = downloader.download(clean + "?tracking=1" + clean, output_dir)
            self.assertTrue(result.success, result.message)
            self.assertEqual(expected, result.file_path)
            ydl.extract_info.assert_called_once_with(clean, download=True)
            self.assertFalse(factory.call_args.args[0]["skip_unavailable_fragments"])
