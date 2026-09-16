import json
import os
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from core.utils import get_ffmpeg_path
from platforms.douyin import Douyin


class DouyinMediaValidationTests(unittest.TestCase):
    def test_repeated_audio_response_is_never_selected_as_video(self):
        audio = "https://v26-web.douyinvod.com/x/media-audio-und-mp4a/"
        video = "https://v26-web.douyinvod.com/x/media-video-hvc1/"

        def entry(url):
            return {"message": json.dumps({"message": {
                "method": "Network.responseReceived",
                "params": {"response": {"url": url, "mimeType": "video/mp4"}},
            }})}

        self.assertEqual((None, audio), Douyin._network_media_urls([
            entry(audio), entry(audio),
        ]))
        self.assertEqual((video, audio), Douyin._network_media_urls([
            entry(audio), entry(audio), entry(video),
        ]))

    def test_actual_audio_only_mp4_is_rejected_and_video_is_accepted(self):
        ffmpeg = get_ffmpeg_path()
        if not ffmpeg:
            self.skipTest("FFmpeg unavailable")
        config = {"ffmpeg_path": ffmpeg}
        with tempfile.TemporaryDirectory() as directory:
            audio = os.path.join(directory, "audio.mp4")
            video = os.path.join(directory, "video.mp4")
            subprocess.run([
                ffmpeg, "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440",
                "-t", "1", "-c:a", "aac", audio,
            ], check=True, capture_output=True)
            subprocess.run([
                ffmpeg, "-v", "error", "-f", "lavfi", "-i", "color=size=16x16:rate=1",
                "-i", audio, "-t", "1", "-c:v", "mpeg4", "-c:a", "copy", video,
            ], check=True, capture_output=True)
            with self.assertRaisesRegex(ValueError, "视频轨道"):
                Douyin._require_video(audio, config)
            Douyin._require_video(video, config)

    def test_rejected_download_does_not_overwrite_existing_file_or_report_success(self):
        downloader = Douyin()
        driver = Mock()
        driver.execute_script.return_value = [{}]
        driver.get_cookies.return_value = []
        response = Mock()
        response.headers = {"content-type": "video/mp4"}
        response.iter_content.return_value = [b"a" * 60000]
        with tempfile.TemporaryDirectory() as directory:
            target = os.path.join(directory, "target.mp4")
            with open(target, "wb") as file:
                file.write(b"existing video")
            with (
                patch.object(downloader, "create_background_driver", return_value=driver),
                patch.object(downloader, "_find_target_video", return_value=("target", "https://cdn.example/file")),
                patch.object(downloader, "_require_video", side_effect=ValueError("没有视频轨道")),
                patch("platforms.douyin.requests.get", return_value=response),
                patch("platforms.douyin.time.sleep"),
                patch("platforms.douyin.time.monotonic", side_effect=[0, 13]),
            ):
                result = downloader.download("https://www.douyin.com/video/7685734331888782627", directory)
            self.assertFalse(result.success)
            self.assertIn("视频轨道", result.message)
            with open(target, "rb") as file:
                self.assertEqual(b"existing video", file.read())
            driver.quit.assert_called_once()
