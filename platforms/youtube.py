import os
import tkinter as tk
from tkinter import ttk, messagebox
from core.downloader import BaseDownloader, DownloadResult
from core.utils import ensure_dir


class YouTube(BaseDownloader):
    name = "YouTube"
    icon = "▶"
    description = "YouTube video downloader (yt-dlp)"

    def create_tab(self, parent):
        frame = ttk.Frame(parent, padding=10)
        ttk.Label(frame, text="YouTube", font=("", 16, "bold")).pack(anchor="w")
        ttk.Label(frame, text=f"{self.icon} {self.description}").pack(anchor="w", pady=(0, 10))
        ttk.Label(frame, text="Video URL:").pack(anchor="w")
        self.url_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.url_var, width=60).pack(fill="x", pady=5)
        ttk.Label(frame, text="Format ID (optional, leave blank for best):").pack(anchor="w")
        self.fmt_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.fmt_var, width=20).pack(anchor="w", pady=5)
        ttk.Button(frame, text="List Formats", command=self._list_formats).pack(side="left", padx=(0, 5))
        ttk.Button(frame, text="Download", command=self._on_download).pack(side="left")
        return frame

    def _list_formats(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showerror("Error", "Please enter a URL first")
            return
        try:
            from yt_dlp import YoutubeDL
            with YoutubeDL({"listformats": True}) as ydl:
                ydl.download([url])
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _on_download(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showerror("Error", "Please enter a YouTube URL")
            return
        output_dir = os.path.join(os.getcwd(), "downloads", "youtube")
        result = self.download(url, output_dir, format_id=self.fmt_var.get())
        if result.success:
            messagebox.showinfo("Success", f"Downloaded: {result.file_path}")
        else:
            messagebox.showerror("Error", result.message)

    def download(self, url, output_dir, **kwargs):
        try:
            from yt_dlp import YoutubeDL
            ensure_dir(output_dir)
            fmt = kwargs.get("format_id", "").strip()
            opts = {
                "outtmpl": os.path.join(output_dir, "%(title)s.%(ext)s"),
                "nocheckcertificate": True,
            }
            if fmt:
                opts["format"] = fmt
            else:
                opts["format"] = "bv+ba/b"

            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = info.get("title", "youtube_video")
                ext = info.get("ext", "mp4")
                path = os.path.join(output_dir, f"{title}.{ext}")
                return DownloadResult(True, "Download complete", path)
        except ImportError:
            return DownloadResult(False, "yt-dlp not installed. Run: pip install yt-dlp")
        except Exception as e:
            return DownloadResult(False, str(e))
