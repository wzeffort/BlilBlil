import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import types
import unittest
from unittest.mock import patch

from core.downloader import BaseDownloader, DownloadCancelled, DownloadResult
from core.media_compat import prepare_windows_video
from core.utils import get_ffmpeg_path


class MediaCompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ffmpeg = get_ffmpeg_path()
        if not ffmpeg:
            raise unittest.SkipTest("FFmpeg unavailable")
        cls.ffmpeg = str(Path(ffmpeg).resolve())
        cls.config = {"ffmpeg_path": cls.ffmpeg}
        cls.fixtures = tempfile.TemporaryDirectory()
        cls.av1 = Path(cls.fixtures.name) / "av1.mkv"
        cls.h264 = Path(cls.fixtures.name) / "h264.mp4"
        cls.audio = Path(cls.fixtures.name) / "audio.mp4"
        base = [cls.ffmpeg, "-v", "error", "-f", "lavfi", "-i", "color=size=32x32:rate=2",
                "-f", "lavfi", "-i", "sine=frequency=440", "-t", "1"]
        subprocess.run(base + ["-c:v", "libaom-av1", "-cpu-used", "8", "-threads", "1",
                               "-c:a", "libopus", str(cls.av1)], check=True, capture_output=True)
        subprocess.run(base + ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                               str(cls.h264)], check=True, capture_output=True)
        subprocess.run([cls.ffmpeg, "-v", "error", "-i", str(cls.h264), "-vn", "-c:a", "copy",
                        str(cls.audio)], check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        cls.fixtures.cleanup()

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)

    def convert(self, source, cancel_check=lambda: None):
        return Path(prepare_windows_video(str(source), self.config, lambda message: None, cancel_check))

    def probe(self, source):
        result = subprocess.run([str(Path(self.ffmpeg).with_name("ffprobe.exe")), "-v", "error",
                                 "-show_streams", "-of", "json", str(source)],
                                check=True, capture_output=True)
        return json.loads(result.stdout)["streams"]

    def test_compatible_file_is_not_reencoded(self):
        source = Path(shutil.copy2(self.h264, self.root / "existing.mp4"))
        before = source.read_bytes()
        self.assertEqual(source, self.convert(source))
        self.assertEqual(before, source.read_bytes())
        self.assertFalse((self.root / "_originals").exists())

    def test_av1_and_opus_convert_to_h264_aac_without_overwriting_another_mp4(self):
        source = Path(shutil.copy2(self.av1, self.root / "video.mkv"))
        existing = self.root / "video.mp4"
        existing.write_bytes(b"unrelated existing file")
        output = self.convert(source)
        self.assertEqual(self.root / "video (2).mp4", output)
        self.assertEqual(b"unrelated existing file", existing.read_bytes())
        streams = self.probe(output)
        self.assertEqual(["h264", "aac"], [s["codec_name"] for s in streams])
        self.assertEqual("yuv420p", streams[0]["pix_fmt"])
        self.assertFalse(source.exists())
        self.assertFalse((self.root / "_originals").exists())
        self.assertEqual({existing, output}, set(self.root.iterdir()))

    def test_same_mp4_path_is_replaced_only_after_conversion(self):
        source = Path(shutil.copy2(self.av1, self.root / "video.mp4"))
        self.assertEqual(source, self.convert(source))
        self.assertEqual(["h264", "aac"], [s["codec_name"] for s in self.probe(source)])
        self.assertEqual([source], list(self.root.iterdir()))

    def test_compatible_video_is_copied_when_only_audio_needs_conversion(self):
        source = self.root / "h264-opus.mkv"
        subprocess.run([self.ffmpeg, "-v", "error", "-i", str(self.h264), "-c:v", "copy",
                        "-c:a", "libopus", str(source)], check=True, capture_output=True)

        def video_packets(path):
            result = subprocess.run([
                str(Path(self.ffmpeg).with_name("ffprobe.exe")), "-v", "error", "-select_streams", "v:0",
                "-show_packets", "-show_data_hash", "sha256", "-of", "json", str(path),
            ], check=True, capture_output=True)
            return [packet["data_hash"] for packet in json.loads(result.stdout)["packets"]]

        before = video_packets(source)
        output = self.convert(source)
        self.assertEqual(before, video_packets(output), "compatible video must not be reencoded")
        self.assertEqual(["h264", "aac"], [s["codec_name"] for s in self.probe(output)])
        self.assertEqual([output], list(self.root.iterdir()))

    def test_publish_failure_preserves_source_and_cleans_temporary(self):
        source = Path(shutil.copy2(self.av1, self.root / "video.mp4"))
        before = source.read_bytes()
        with patch("core.media_compat.os.replace", side_effect=OSError("file locked")):
            with self.assertRaises(OSError):
                self.convert(source)
        self.assertEqual(before, source.read_bytes())
        self.assertEqual([source], list(self.root.iterdir()))

    def test_audio_only_file_is_rejected_and_preserved(self):
        source = Path(shutil.copy2(self.audio, self.root / "audio.mp4"))
        before = source.read_bytes()
        with self.assertRaisesRegex(ValueError, "没有视频画面"):
            self.convert(source)
        self.assertEqual(before, source.read_bytes())

    def test_cancel_during_conversion_preserves_source_and_removes_partial_output(self):
        source = Path(shutil.copy2(self.av1, self.root / "cancel.mkv"))
        before = source.read_bytes()
        calls = []

        def cancel():
            calls.append(True)
            if len(calls) >= 2:
                raise DownloadCancelled("stop")

        with self.assertRaises(DownloadCancelled):
            self.convert(source, cancel)
        self.assertEqual(before, source.read_bytes())
        self.assertEqual([source], list(self.root.iterdir()))

    def test_gui_completion_returns_only_the_converted_file(self):
        source = Path(shutil.copy2(self.av1, self.root / "download.mkv"))

        class Downloader(BaseDownloader):
            def create_tab(self, parent):
                return None

            def download(self, *args, **kwargs):
                return DownloadResult(True, "downloaded", str(source))

        results = []
        downloader = Downloader()
        downloader.app = types.SimpleNamespace(
            root=types.SimpleNamespace(after=lambda delay, callback: callback()),
            _on_download_done=lambda owner, result: results.append(result),
        )
        downloader._download_thread("https://example.com/video", str(self.root), config=self.config)
        self.assertEqual(1, len(results))
        self.assertTrue(results[0].success, results[0].message)
        self.assertEqual(str(self.root / "download.mp4"), results[0].file_path)
        self.assertEqual(["h264", "aac"], [s["codec_name"] for s in self.probe(results[0].file_path)])
