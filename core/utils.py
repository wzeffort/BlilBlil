import os
import re
import subprocess
from typing import Optional


def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', '_', name)


def get_ffmpeg_path(config) -> str:
    path = config["ffmpeg_path"]
    if path and os.path.exists(path):
        return path
    for candidate in ["./assets/ffmpeg/ffmpeg.exe", "ffmpeg"]:
        if os.path.exists(candidate) or candidate == "ffmpeg":
            return candidate
    return "ffmpeg"


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
