import os
import shutil
import subprocess
import time
from typing import Callable, Optional


EXECUTABLE_NAME = "N_m3u8DL-RE.exe"
MEDIA_EXTENSIONS = (".mp4", ".mkv", ".ts", ".m4v", ".webm")


def find_n_m3u8dl(config=None) -> Optional[str]:
    configured = ""
    if config:
        try:
            configured = str(config["n_m3u8dl_path"] or "").strip()
        except (KeyError, TypeError):
            pass
    if configured and os.path.isfile(configured):
        return configured

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates = (
        os.path.join(
            project_root,
            "tools",
            "N_m3u8DL-RE",
            EXECUTABLE_NAME,
        ),
        os.path.join(project_root, "tools", EXECUTABLE_NAME),
    )
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
    return shutil.which(EXECUTABLE_NAME)


def _thread_count(config):
    try:
        configured = int(config["max_threads"])
    except (KeyError, TypeError, ValueError):
        configured = 4
    return max(1, min(16, configured))


def build_n_m3u8dl_command(
    executable,
    media_url,
    headers,
    output_dir,
    save_name,
    config,
    ffmpeg_path=None,
):
    output_dir = os.path.abspath(output_dir)
    command = [
        executable,
        media_url,
        "--save-dir",
        output_dir,
        "--save-name",
        save_name,
        "--thread-count",
        str(_thread_count(config)),
        "--download-retry-count",
        "2",
        "--http-request-timeout",
        "15",
        "--auto-select",
        "--append-url-params",
        "--no-log",
    ]
    for name in ("User-Agent", "Referer", "Cookie"):
        value = (headers or {}).get(name)
        if value:
            command.extend(("-H", f"{name}: {value}"))
    if ffmpeg_path:
        ffmpeg_path = os.path.abspath(ffmpeg_path)
        command.extend(
            (
                "--ffmpeg-binary-path",
                ffmpeg_path,
                "-M",
                "format=mp4",
            )
        )
    return command


def _output_signatures(output_dir, save_name):
    signatures = {}
    if not os.path.isdir(output_dir):
        return signatures
    prefix = f"{save_name}.".lower()
    for filename in os.listdir(output_dir):
        if not filename.lower().startswith(prefix):
            continue
        path = os.path.join(output_dir, filename)
        if not os.path.isfile(path):
            continue
        try:
            signatures[path] = (os.path.getsize(path), os.path.getmtime(path))
        except OSError:
            continue
    return signatures


def run_n_m3u8dl(
    command,
    output_dir,
    save_name,
    cancel_check: Callable[[], None],
):
    os.makedirs(output_dir, exist_ok=True)
    before = _output_signatures(output_dir, save_name)
    process = subprocess.Popen(
        command,
        cwd=output_dir,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        shell=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    try:
        while process.poll() is None:
            cancel_check()
            time.sleep(0.1)
        return_code = process.returncode
    except BaseException:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        raise

    if return_code:
        raise RuntimeError(
            f"N_m3u8DL-RE 下载失败（退出码 {return_code}）"
        )

    after = _output_signatures(output_dir, save_name)
    produced = [
        path
        for path, signature in after.items()
        if before.get(path) != signature
        and os.path.splitext(path)[1].lower() in MEDIA_EXTENSIONS
        and signature[0] > 0
    ]
    if not produced:
        raise RuntimeError("N_m3u8DL-RE 未生成有效媒体文件")
    extension_order = {
        extension: index
        for index, extension in enumerate(MEDIA_EXTENSIONS)
    }
    produced.sort(
        key=lambda path: (
            extension_order.get(os.path.splitext(path)[1].lower(), 99),
            -os.path.getmtime(path),
        )
    )
    return produced[0]
