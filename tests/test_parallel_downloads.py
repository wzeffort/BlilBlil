"""Exercise real streaming, merging and GUI worker lifecycles without remote sites."""
import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import patch

import requests

from core.downloader import DownloadResult
from core.utils import get_ffmpeg_path
from main import BlilBlilApp
from platforms.iqiyi import IQiyi
from platforms.tencent import Tencent
from platforms.youtube import YouTube


class ParallelDownloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        ffmpeg = get_ffmpeg_path()
        if not ffmpeg:
            raise unittest.SkipTest("FFmpeg unavailable")
        cls.ffmpeg = str(Path(ffmpeg).resolve())
        cls.fixtures = tempfile.TemporaryDirectory()
        cls.fixture = Path(cls.fixtures.name) / "sample.mp4"
        subprocess.run([
            cls.ffmpeg, "-v", "error", "-f", "lavfi", "-i", "testsrc2=size=160x90:rate=15",
            "-f", "lavfi", "-i", "sine=frequency=440", "-t", "2",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(cls.fixture),
        ], check=True, capture_output=True)
        cls.payload = cls.fixture.read_bytes()

    @classmethod
    def tearDownClass(cls):
        cls.fixtures.cleanup()

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root_dir = Path(self.directory.name)
        payload = self.payload
        self.files = {"/slow.mp4": payload, "/fast.mp4": payload}
        files = self.files

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                data = files.get(self.path)
                if data is None:
                    self.send_error(500)
                    return
                self.send_response(200)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                try:
                    for start in range(0, len(data), 512):
                        self.wfile.write(data[start:start + 512])
                        self.wfile.flush()
                        if self.path in ("/slow.mp4", "/fast.mp4"):
                            time.sleep(0.02 if self.path == "/slow.mp4" else 0.012)
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    pass

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def exercise_parallel(self, scenario):
        app = BlilBlilApp()
        app.root.geometry("1100x680+2000+2000")
        first = next(d for d in app.downloaders if isinstance(d, IQiyi))
        second = next(d for d in app.downloaders if isinstance(d, Tencent))
        completed, progress, snapshots = {}, {}, []
        errors = []
        second_started = cancelled = False
        original_notify = app._on_download_done

        def notify(owner, result):
            completed[owner] = result
            # Retain the real completion handler without opening Explorer or error dialogs.
            original_notify(owner, DownloadResult(True, result.message, cancelled=result.cancelled))

        app._on_download_done = notify
        for downloader in (first, second):
            original_progress = downloader._report_progress

            def record(percent, owner=downloader, original=original_progress):
                progress[owner] = percent
                original(percent)

            downloader._report_progress = record

            def stream(owner, url, output_dir, **kwargs):
                path = Path(output_dir) / f"{owner.name}.mp4"
                owner._set_status("下载中")
                with requests.get(url, stream=True, timeout=5) as response:
                    response.raise_for_status()
                    owner.download_response(response, str(path), chunk_size=512)
                return DownloadResult(True, "downloaded", str(path))

            downloader.download = types.MethodType(stream, downloader)

        def poll():
            nonlocal second_started, cancelled
            try:
                if progress.get(first, 0) >= 10 and not second_started:
                    second_started = True
                    second.start_download(self.url + ("/error" if scenario == "error" else "/fast.mp4"), str(self.root_dir))
                    app.notebook.select(app.downloaders.index(second))
                if second_started:
                    snapshots.append((progress.get(first, 0), progress.get(second, 0), first in completed, second in completed))
                if scenario == "cancel" and progress.get(second, 0) >= 20 and not cancelled:
                    cancelled = True
                    first.stop_download()
                if len(completed) == 2:
                    app.root.quit()
                    return
                app.root.after(20, poll)
            except BaseException as error:
                errors.append(error)
                app.root.quit()

        app.root.after(0, lambda: first.start_download(self.url + "/slow.mp4", str(self.root_dir)))
        app.root.after(20, poll)
        timeout_id = app.root.after(12000, app.root.quit)
        try:
            app.root.mainloop()
            self.assertFalse(errors, errors)
            self.assertEqual(2, len(completed), "both workers must finish")
            if scenario == "cancel":
                self.assertTrue(completed[first].cancelled)
                self.assertTrue(completed[second].success, completed[second].message)
                remaining = [b for a, b, a_done, b_done in snapshots if a_done]
                self.assertGreater(max(remaining), min(remaining))
            else:
                self.assertTrue(completed[first].success, completed[first].message)
                self.assertEqual(scenario != "error", completed[second].success)
                remaining = [a for a, b, a_done, b_done in snapshots if b_done]
                self.assertGreater(max(remaining), min(remaining))
            if scenario != "error":
                overlap = [(a, b) for a, b, a_done, b_done in snapshots if not a_done and not b_done and b > 0]
                self.assertGreater(len(overlap), 1)
                self.assertGreater(overlap[-1][0], overlap[0][0])
                self.assertGreater(overlap[-1][1], overlap[0][1])
            for owner, result in completed.items():
                expected = "完成" if result.success else "已停止" if result.cancelled else "失败"
                self.assertEqual(expected, app.tasks.set(str(id(owner)), "status"))
                if result.success:
                    self.assertEqual(self.payload, Path(result.file_path).read_bytes())
        finally:
            app.root.after_cancel(timeout_id)
            app.root.destroy()

    def test_completion_and_switching_tabs_do_not_pause_other_download(self):
        self.exercise_parallel("complete")

    def test_cancelling_one_download_does_not_cancel_other(self):
        self.exercise_parallel("cancel")

    def test_failed_download_does_not_interrupt_other(self):
        self.exercise_parallel("error")

    def test_youtube_real_merge_and_conversion_leave_only_final_mp4(self):
        from yt_dlp import YoutubeDL

        video = self.root_dir / "video.webm"
        audio = self.root_dir / "audio.webm"
        for target, args in ((video, ["-an", "-c:v", "libvpx-vp9"]),
                             (audio, ["-vn", "-c:a", "libopus"])):
            subprocess.run([self.ffmpeg, "-v", "error", "-i", str(self.fixture), *args, str(target)],
                           check=True, capture_output=True)
        self.files.update({"/video.webm": video.read_bytes(), "/audio.webm": audio.read_bytes()})
        output_dir = self.root_dir / "youtube"
        info = {"id": "local", "title": "Local video", "extractor": "test", "webpage_url": self.url,
                "formats": [
                    {"format_id": "v", "url": self.url + "/video.webm", "ext": "webm",
                     "vcodec": "vp9", "acodec": "none", "height": 90},
                    {"format_id": "a", "url": self.url + "/audio.webm", "ext": "webm",
                     "vcodec": "none", "acodec": "opus", "abr": 64},
                ]}
        results = []
        downloader = YouTube()
        downloader.app = types.SimpleNamespace(
            root=types.SimpleNamespace(after=lambda delay, callback: callback()),
            _on_download_done=lambda owner, result: results.append(result),
        )

        def local_extract(ydl, *args, **kwargs):
            return ydl.process_ie_result(copy.deepcopy(info), download=True)

        # Only replace remote metadata extraction; actual HTTP, yt-dlp, FFmpeg and cleanup run.
        with patch.object(YoutubeDL, "extract_info", autospec=True, side_effect=local_extract):
            downloader._download_thread(self.url, str(output_dir), config={"ffmpeg_path": self.ffmpeg})
        self.assertTrue(results[0].success, results[0].message)
        final = Path(results[0].file_path)
        self.assertEqual(".mp4", final.suffix)
        self.assertEqual([final], list(output_dir.iterdir()))
        subprocess.run([self.ffmpeg, "-v", "error", "-i", str(final), "-map", "0:v:0",
                        "-map", "0:a:0", "-f", "null", "-"], check=True, capture_output=True)


if __name__ == "__main__":
    unittest.main()
