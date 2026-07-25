import tkinter as tk
from tkinter import ttk, filedialog
from core.config import Config
from platforms import discover_platforms
from tools.vip_parser import VIPParserPanel

# deliberate palette — dark slate, warm accent, clean whitespace
PRIMARY = "#1a1a2e"
ACCENT = "#e94560"
SURFACE = "#f8f9fa"
BORDER = "#dee2e6"
TEXT_PRIMARY = "#212529"
TEXT_SECONDARY = "#6c757d"

LANG = {
    "zh": {
        "title": "BlilBlil — 多平台视频下载器",
        "subtitle": "一站式视频下载与 VIP 播放工具",
        "download_dir": "下载目录",
        "browse": "浏览",
        "settings": "设置",
        "save": "保存",
        "cancel": "取消",
        "progress": "进度",
        "log": "日志",
        "download_btn": "下载",
        "url_label": "视频地址",
        "ffmpeg_path": "FFmpeg 路径",
        "max_threads": "最大线程数",
        "language": "语言",
        "platforms": "下载",
        "vip_player": "VIP 播放",
    },
    "en": {
        "title": "BlilBlil — Multi-Platform Video Downloader",
        "subtitle": "All-in-one video downloader & VIP player",
        "download_dir": "Download Dir",
        "browse": "Browse",
        "settings": "Settings",
        "save": "Save",
        "cancel": "Cancel",
        "progress": "Progress",
        "log": "Log",
        "download_btn": "Download",
        "url_label": "Video URL",
        "ffmpeg_path": "FFmpeg Path",
        "max_threads": "Max Threads",
        "language": "Language",
        "platforms": "Download",
        "vip_player": "VIP Player",
    }
}


class BlilBlilApp:
    def __init__(self):
        self.config = Config()
        self.lang = self.config["language"]
        self.txt = LANG.get(self.lang, LANG["zh"])
        self.root = tk.Tk()
        self.root.title(self._tr("title"))
        self.root.geometry("1100x680")
        self.root.minsize(900, 550)

        try:
            import sv_ttk
            sv_ttk.set_theme("light")
        except ImportError:
            pass

        self._build_top_bar()
        self._build_main_area()
        self._build_bottom_bar()

    def get_config(self):
        return self.config

    def _tr(self, key):
        return self.txt.get(key, key)

    def _build_top_bar(self):
        top = ttk.Frame(self.root)
        top.pack(fill="x", padx=16, pady=(12, 0))

        brand = ttk.Frame(top)
        brand.pack(fill="x")

        title_label = ttk.Label(
            brand, text="BlilBlil",
            font=("Segoe UI", 18, "bold"),
            foreground=ACCENT
        )
        title_label.pack(side="left")

        subtitle_label = ttk.Label(
            brand, text=self._tr("subtitle"),
            font=("Segoe UI", 10),
            foreground=TEXT_SECONDARY
        )
        subtitle_label.pack(side="left", padx=(8, 0), pady=(4, 0))

        ttk.Separator(brand, orient="vertical").pack(side="left", fill="y", padx=16, pady=2)

        ttk.Label(
            brand, text=self._tr("download_dir"),
            font=("Segoe UI", 9)
        ).pack(side="left")

        self.dir_var = tk.StringVar(value=self.config["download_dir"])
        dir_entry = ttk.Entry(
            brand, textvariable=self.dir_var, width=36,
            font=("Segoe UI", 9)
        )
        dir_entry.pack(side="left", padx=6)

        browse_btn = ttk.Button(
            brand, text=self._tr("browse"),
            command=self._browse_dir, width=8
        )
        browse_btn.pack(side="left", padx=(0, 8))

        settings_btn = ttk.Button(
            brand, text=self._tr("settings"),
            command=self._open_settings, width=8
        )
        settings_btn.pack(side="right")

        ttk.Separator(self.root, orient="horizontal").pack(fill="x", padx=16, pady=(10, 0))

    def _browse_dir(self):
        path = filedialog.askdirectory()
        if path:
            self.dir_var.set(path)
            self.config["download_dir"] = path

    def _open_settings(self):
        win = tk.Toplevel(self.root)
        win.title(self._tr("settings"))
        win.geometry("460x240")
        win.resizable(False, False)
        win.transient(self.root)
        win.grab_set()

        pad = {"padx": 20, "pady": (16, 4)}

        ttk.Label(win, text=self._tr("ffmpeg_path"), font=("Segoe UI", 9, "bold")).pack(anchor="w", **pad)
        ffmpeg_var = tk.StringVar(value=self.config["ffmpeg_path"])
        ffmpeg_entry = ttk.Entry(win, textvariable=ffmpeg_var, width=54, font=("Segoe UI", 9))
        ffmpeg_entry.pack(padx=20, pady=(0, 8), fill="x")

        ttk.Label(win, text=self._tr("max_threads"), font=("Segoe UI", 9, "bold")).pack(anchor="w", **pad)
        thread_frame = ttk.Frame(win)
        thread_frame.pack(fill="x", padx=20, pady=(0, 4))
        thread_var = tk.StringVar(value=str(self.config["max_threads"]))
        thread_spin = ttk.Spinbox(
            thread_frame, from_=1, to=32,
            textvariable=thread_var, width=8,
            font=("Segoe UI", 9)
        )
        thread_spin.pack(side="left")

        btn_frame = ttk.Frame(win)
        btn_frame.pack(fill="x", padx=20, pady=(12, 16))

        def save():
            self.config["ffmpeg_path"] = ffmpeg_var.get()
            try:
                self.config["max_threads"] = int(thread_var.get())
            except ValueError:
                pass
            win.destroy()

        ttk.Button(btn_frame, text=self._tr("save"), command=save, width=10).pack(side="right", padx=(6, 0))
        ttk.Button(btn_frame, text=self._tr("cancel"), command=win.destroy, width=10).pack(side="right")

    def _build_main_area(self):
        paned = ttk.PanedWindow(self.root, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=16, pady=8)

        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=3)

        section_label = ttk.Label(
            left_frame, text=self._tr("platforms"),
            font=("Segoe UI", 11, "bold")
        )
        section_label.pack(anchor="w", pady=(0, 4))

        self.notebook = ttk.Notebook(left_frame)
        self.notebook.pack(fill="both", expand=True)

        platforms = discover_platforms()
        for cls in platforms:
            instance = cls()
            instance.app = self
            tab = instance.create_tab(self.notebook)
            self.notebook.add(tab, text=f"  {instance.icon} {instance.name}  ")

        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=2)

        vip_header = ttk.Label(
            right_frame, text=self._tr("vip_player"),
            font=("Segoe UI", 11, "bold")
        )
        vip_header.pack(anchor="w", pady=(0, 4))

        vip_container = ttk.Frame(right_frame, relief="solid", borderwidth=1)
        vip_container.pack(fill="both", expand=True)

        self.vip_panel = VIPParserPanel(vip_container, lang=self.lang)
        self.vip_panel.pack(fill="both", expand=True, padx=8, pady=8)

    def _build_bottom_bar(self):
        bottom = ttk.Frame(self.root)
        bottom.pack(fill="x", padx=16, pady=(0, 8))

        self.progress = ttk.Progressbar(bottom, mode="determinate")
        self.progress.pack(fill="x", pady=(0, 4))

        log_frame = ttk.LabelFrame(bottom, text=self._tr("log"), padding=(4, 2))
        log_frame.pack(fill="both", expand=True)

        self.log_text = tk.Text(
            log_frame, height=5, state="disabled",
            wrap="word", font=("Consolas", 9),
            bg="#fafafa", relief="flat", borderwidth=0
        )
        self.log_text.tag_config("info", foreground=TEXT_SECONDARY)
        self.log_text.tag_config("success", foreground="#2d8a4e")
        self.log_text.tag_config("error", foreground=ACCENT)

        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.log_text.pack(fill="both", expand=True)

    def log(self, message: str, tag: str = "info"):
        self.log_text.config(state="normal")
        self.log_text.insert("end", message + "\n", tag)
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = BlilBlilApp()
    app.run()
