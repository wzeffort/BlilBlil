import os
import tkinter as tk
from tkinter import ttk, messagebox
from core.downloader import BaseDownloader, DownloadResult
from core.utils import ensure_dir, get_ffmpeg_path
from core.instruction_panel import InstructionPanel


class YouTube(BaseDownloader):
    name = "YouTube"
    icon = "▶"
    description = "YouTube video downloader (yt-dlp)"

    def create_tab(self, parent):
        frame = ttk.Frame(parent, padding=10)
        ttk.Label(frame, text="YouTube", font=("", 16, "bold")).pack(anchor="w")
        ttk.Label(frame, text=f"{self.icon} {self.description}").pack(anchor="w", pady=(0, 10))
        ttk.Label(frame, text="仅支持非 VIP 普通视频；复制播放页链接到下方：").pack(anchor="w")
        self.url_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.url_var, width=60).pack(fill="x", pady=5)
        ttk.Label(frame, text="支持普通视频和 Shorts，自动选择最佳画质并合并音视频。", foreground="#6c757d").pack(anchor="w", pady=(0, 6))
        button_row = ttk.Frame(frame)
        button_row.pack(anchor="w", pady=5)
        self.create_download_controls(
            button_row, self._on_download
        ).pack(side="left")
        self.create_status_label(frame)
        InstructionPanel(
            frame,
            steps=[
                "打开 YouTube 视频或 Shorts，右键点击画面。",
                "选择“Copy video URL”（复制视频链接），也可复制地址栏链接。",
                "粘贴到上方后点击下载，自动选择画质并合并音视频。",
            ],
            image_name="YouTube下载说明.png",
            max_image_width=200,
        ).pack(fill="both", expand=True, pady=(8, 0))
        return frame

    def _on_download(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showerror("错误", "请输入视频地址")
            return
        output_dir = self.get_output_dir("youtube")
        self.start_download(url, output_dir)

    def download(self, url, output_dir, **kwargs):
        try:
            from yt_dlp import YoutubeDL
            ffmpeg = get_ffmpeg_path(kwargs.get("config"))
            if not ffmpeg:
                return DownloadResult(False, "未找到 FFmpeg，请检查项目中的 ffmpeg/ffmpeg.exe 或配置路径。")
            self._set_status("正在解析 YouTube 视频...")
            ensure_dir(output_dir)
            opts = {
                "outtmpl": os.path.join(output_dir, "%(title)s.%(ext)s"),
                "nocheckcertificate": True,
                "ffmpeg_location": os.path.abspath(ffmpeg),
                "format": "bv+ba/b",
                "noplaylist": True,
            }
            opts.update(
                self.get_yt_dlp_runtime_options(kwargs.get("config"))
            )
            with YoutubeDL(opts) as ydl:
                self._set_status("正在下载...")
                info = ydl.extract_info(url, download=True)
                self._raise_if_cancelled()
                path = ydl.prepare_filename(info)
                if not os.path.isfile(path) or os.path.getsize(path) == 0:
                    return DownloadResult(False, "下载未生成有效文件，请查看下载日志。")
                return DownloadResult(True, "下载完成", path)
        except ImportError:
            return DownloadResult(False, "yt-dlp not installed. Run: pip install yt-dlp")
        except Exception as e:
            self._raise_if_cancelled()
            return DownloadResult(False, str(e))
