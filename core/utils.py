import os
import re
import shutil
import subprocess
import math
from typing import Optional


def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', '_', name)


def image_subsample_factor(width: int, max_width: int) -> int:
    if width <= 0 or max_width <= 0:
        return 1
    return max(1, math.ceil(width / max_width))


def get_ffmpeg_path(config=None) -> Optional[str]:
    if config:
        try:
            path = config["ffmpeg_path"]
        except (KeyError, TypeError):
            path = ""
        if path and os.path.isfile(path):
            return path
    for candidate in [
        os.path.join(".", "ffmpeg", "ffmpeg.exe"),
        "./assets/ffmpeg/ffmpeg.exe",
        "D:/FFmpeg/bin/ffmpeg.exe",
    ]:
        if os.path.isfile(candidate):
            return candidate
    return shutil.which("ffmpeg")


def merge_audio_video(audio: str, video: str, output: str, ffmpeg: str) -> bool:
    cmd = [ffmpeg, "-i", audio, "-i", video, "-acodec", "copy", "-vcodec", "copy", output]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode == 0:
        os.remove(audio)
        os.remove(video)
        return True
    return False


def merge_ts(filelist: str, output: str, ffmpeg: str) -> bool:
    cmd = [ffmpeg, "-f", "concat", "-i", filelist, "-c", "copy", output]
    result = subprocess.run(cmd, capture_output=True)
    return result.returncode == 0


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)
