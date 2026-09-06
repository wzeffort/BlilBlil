import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from platforms.youtube import YouTube


class YouTubeDownloadTests(unittest.TestCase):
    def test_merge_uses_project_ffmpeg_and_actual_filename(self):
        with tempfile.TemporaryDirectory() as directory:
            output = os.path.join(directory, 'sanitized-title.mkv')
            with open(output, 'wb') as stream:
                stream.write(b'video')
            ydl = MagicMock()
            ydl.extract_info.return_value = {'title': 'title:unsafe', 'ext': 'mkv'}
            ydl.prepare_filename.return_value = output
            with patch('platforms.youtube.get_ffmpeg_path', return_value='tools/ffmpeg.exe'), patch('yt_dlp.YoutubeDL') as factory:
                factory.return_value.__enter__.return_value = ydl
                result = YouTube().download('https://youtube.com/shorts/2EjWPYeaDxI', directory)
            self.assertTrue(result.success)
            self.assertEqual(result.file_path, output)
            opts = factory.call_args.args[0]
            self.assertEqual(opts['ffmpeg_location'], os.path.abspath('tools/ffmpeg.exe'))
            self.assertEqual(opts['format'], 'bv+ba/b')
            self.assertTrue(opts['noplaylist'])

    def test_missing_ffmpeg_fails_before_downloading(self):
        with patch('platforms.youtube.get_ffmpeg_path', return_value=None), patch('yt_dlp.YoutubeDL') as factory:
            result = YouTube().download('https://youtube.com/shorts/2EjWPYeaDxI', '.')
        self.assertFalse(result.success)
        self.assertIn('FFmpeg', result.message)
        factory.assert_not_called()
