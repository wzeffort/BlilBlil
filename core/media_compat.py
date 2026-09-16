"""Validate video downloads and prepare MP4 files for Windows playback."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

from core.utils import get_ffmpeg_path


def _probe(path, ffprobe):
    result = subprocess.run(
        [str(ffprobe), "-v", "error", "-show_streams", "-show_format",
         "-of", "json", str(path)],
        capture_output=True, timeout=30,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode:
        raise ValueError("下载文件无法读取，未通过视频完整性检查。")
    data = json.loads(result.stdout)
    video = next((s for s in data["streams"] if s["codec_type"] == "video"), None)
    audio = next((s for s in data["streams"] if s["codec_type"] == "audio"), None)
    if not video or not video.get("width") or not video.get("height"):
        raise ValueError("下载文件没有视频画面，不能报告下载成功。")
    return data, video, audio


def _unused_path(path):
    candidate = path
    index = 2
    while candidate.exists():
        candidate = path.with_name(f"{path.stem} ({index}){path.suffix}")
        index += 1
    return candidate


def prepare_windows_video(path, config, status, cancel_check):
    """Publish a verified playable file, then remove the superseded source."""
    source = Path(path).resolve()
    ffmpeg = get_ffmpeg_path(config)
    if not ffmpeg:
        raise ValueError("未找到 FFmpeg，无法完成视频兼容处理。")
    ffmpeg = Path(ffmpeg).resolve()
    ffprobe = ffmpeg.with_name("ffprobe.exe" if os.name == "nt" else "ffprobe")
    if not ffprobe.is_file():
        raise ValueError("缺少 FFprobe，请将它放在 FFmpeg 同一目录后重试。")
    cancel_check()
    status("正在检查视频画面和播放格式...")
    before, video, audio = _probe(source, ffprobe)
    video_compatible = video["codec_name"] == "h264" and video.get("pix_fmt") == "yuv420p"
    audio_compatible = audio is None or (
        audio["codec_name"] == "aac" and audio.get("profile") == "LC"
        and audio.get("channels", 2) <= 2
    )
    mp4_container = "mp4" in before.get("format", {}).get("format_name", "").split(",")
    if video_compatible and audio_compatible and mp4_container and source.suffix.lower() == ".mp4":
        status("已是自带播放器兼容格式，直接保留，不转换。")
        return str(source)

    target = source.with_suffix(".mp4")
    if target != source:
        target = _unused_path(target)
    if video_compatible and audio_compatible:
        status("音视频编码已兼容，仅调整为 MP4 封装，不重新压缩。")
    else:
        changes = []
        if not video_compatible:
            changes.append(f"视频 {video['codec_name']} → H.264")
        if not audio_compatible:
            changes.append(f"音频 {audio['codec_name']} → AAC")
        status("检测到不兼容编码，正在处理：" + "；".join(changes) + "。兼容的轨道直接保留。")
    descriptor, temporary_name = tempfile.mkstemp(prefix=".compat-", suffix=".mp4", dir=source.parent)
    os.close(descriptor)
    temporary = Path(temporary_name)
    command = [str(ffmpeg), "-hide_banner", "-v", "error", "-nostdin", "-y",
               "-threads", "4", "-i", str(source), "-map", "0:v:0", "-map", "0:a:0?"]
    if video_compatible:
        command += ["-c:v", "copy"]
    else:
        command += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                    "-pix_fmt", "yuv420p", "-vf", "pad=ceil(iw/2)*2:ceil(ih/2)*2", "-threads", "4"]
    if audio_compatible:
        command += ["-c:a", "copy"]
    else:
        command += ["-c:a", "aac", "-profile:a", "aac_low", "-ac", "2", "-b:a", "192k"]
    command += ["-movflags", "+faststart", str(temporary)]
    try:
        with tempfile.TemporaryFile(dir=source.parent) as error_log:
            process = subprocess.Popen(
                command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                stderr=error_log, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            try:
                while process.poll() is None:
                    cancel_check()
                    time.sleep(0.1)
                cancel_check()
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
            if process.returncode:
                error_log.seek(0)
                detail = error_log.read().decode("utf-8", errors="replace")[-1200:]
                raise ValueError("视频兼容处理失败，原文件已保留。" + detail)
        after, converted_video, converted_audio = _probe(temporary, ffprobe)
        if converted_video["codec_name"] != "h264" or converted_video.get("pix_fmt") != "yuv420p":
            raise ValueError("转换结果的视频格式检查失败，原文件已保留。")
        if audio and (not converted_audio or converted_audio["codec_name"] != "aac"):
            raise ValueError("转换结果缺少兼容音轨，原文件已保留。")
        old_duration = float(before.get("format", {}).get("duration") or 0)
        new_duration = float(after.get("format", {}).get("duration") or 0)
        if old_duration and abs(old_duration - new_duration) > 1:
            raise ValueError("转换前后时长不一致，原文件已保留。")
        cancel_check()
        os.replace(temporary, target)
        if source != target:
            try:
                source.unlink()
            except OSError as error:
                status(f"兼容视频已生成，但转换前文件未能清理：{source}（{error}）")
                return str(target)
        status("兼容处理完成，转换前文件已清理。")
        return str(target)
    finally:
        temporary.unlink(missing_ok=True)
