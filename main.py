import tkinter as tk
from tkinter import ttk, filedialog
from core.config import Config
from platforms import discover_platforms
from tools.vip_parser import VIPParserPanel

LANG = {
    "zh": {
        "title": "BlilBlil — 多平台视频下载器",
        "download_dir": "下载目录:",
        "browse": "浏览...",
        "settings": "⚙",
        "progress": "进度",
        "log": "日志",
        "download_btn": "下载",
        "url_label": "视频地址:",
    },
    "en": {
        "title": "BlilBlil — Multi-Platform Video Downloader",
        "download_dir": "Download Dir:",
        "browse": "Browse...",
        "settings": "⚙",
        "progress": "Progress",
        "log": "Log",
        "download_btn": "Download",
        "url_label": "Video URL:",
    }
}


class BlilBlilApp:
    def __init__(self):
        self.config = Config()
        self.lang = self.config["language"]
        self.txt = LANG.get(self.lang, LANG["zh"])
        self.root = tk.Tk()
        self.root.title(self._tr("title"))
        self.root.geometry("1000x650")

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
        top.pack(fill="x", padx=10, pady=5)

        ttk.Label(top, text=self._tr("download_dir")).pack(side="left")
        self.dir_var = tk.StringVar(value=self.config["download_dir"])
        dir_entry = ttk.Entry(top, textvariable=self.dir_var, width=40)
        dir_entry.pack(side="left", padx=5)
        ttk.Button(top, text=self._tr("browse"), command=self._browse_dir).pack(side="left", padx=2)
        ttk.Button(top, text=self._tr("settings"), command=self._open_settings).pack(side="right")

    def _browse_dir(self):
        path = filedialog.askdirectory()
        if path:
            self.dir_var.set(path)
            self.config["download_dir"] = path

    def _open_settings(self):
        win = tk.Toplevel(self.root)
        win.title("Settings")
        win.geometry("400x200")
        ttk.Label(win, text="FFmpeg Path:").pack(anchor="w", padx=10, pady=5)
        ffmpeg_var = tk.StringVar(value=self.config["ffmpeg_path"])
        entry = ttk.Entry(win, textvariable=ffmpeg_var, width=50)
        entry.pack(padx=10, pady=5)
        ttk.Label(win, text="Max Threads:").pack(anchor="w", padx=10, pady=5)
        thread_var = tk.StringVar(value=str(self.config["max_threads"]))
        ttk.Entry(win, textvariable=thread_var, width=10).pack(anchor="w", padx=10)

        def save():
            self.config["ffmpeg_path"] = ffmpeg_var.get()
            self.config["max_threads"] = int(thread_var.get())
            win.destroy()

        ttk.Button(win, text="Save", command=save).pack(pady=10)

    def _build_main_area(self):
        paned = ttk.PanedWindow(self.root, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=10, pady=5)

        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=3)

        self.notebook = ttk.Notebook(left_frame)
        self.notebook.pack(fill="both", expand=True)

        platforms = discover_platforms()
        for cls in platforms:
            instance = cls()
            instance.app = self
            tab = instance.create_tab(self.notebook)
            self.notebook.add(tab, text=f"{instance.icon} {instance.name}")

        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=2)
        self.vip_panel = VIPParserPanel(right_frame, lang=self.lang)
        self.vip_panel.pack(fill="both", expand=True, padx=(10, 0))

    def _build_bottom_bar(self):
        bottom = ttk.Frame(self.root)
        bottom.pack(fill="x", padx=10, pady=5)

        self.progress = ttk.Progressbar(bottom, mode="determinate")
        self.progress.pack(fill="x")

        self.log_text = tk.Text(bottom, height=6, state="disabled", wrap="word")
        self.log_text.tag_config("info", foreground="black")
        self.log_text.tag_config("success", foreground="green")
        self.log_text.tag_config("error", foreground="red")
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
