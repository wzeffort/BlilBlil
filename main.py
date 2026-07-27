import tkinter as tk
from tkinter import ttk, filedialog
from core.config import Config
from platforms import discover_platforms
from tools.vip_parser import VIPParserPanel

PRIMARY = "#1a1a2e"
ACCENT = "#e94560"
SURFACE = "#f8f9fa"
BORDER = "#dee2e6"
TEXT_PRIMARY = "#212529"
TEXT_SECONDARY = "#6c757d"

LANG = {
    "title": "BlilBlil — 多平台视频下载器",
    "subtitle": "一站式视频下载与 VIP 播放工具",
    "download_dir": "下载目录",
    "browse": "浏览",
    "progress": "进度",
    "log": "日志",
    "download_btn": "下载",
    "url_label": "视频地址",
    "max_threads": "线程数",
    "platforms": "下载",
    "vip_player": "VIP 播放",
}


class BlilBlilApp:
    def __init__(self):
        self.config = Config()
        self.root = tk.Tk()
        self.root.title(LANG["title"])
        self.root.geometry("1100x680")
        self.root.minsize(900, 550)

        try:
            import sv_ttk
            sv_ttk.set_theme("light")
        except ImportError:
            pass

        self._build_top_bar()
        self._build_bottom_bar()
        self._build_main_area()

    def get_config(self):
        return self.config

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
            brand, text=LANG["subtitle"],
            font=("Segoe UI", 10),
            foreground=TEXT_SECONDARY
        )
        subtitle_label.pack(side="left", padx=(8, 0), pady=(4, 0))

        ttk.Separator(brand, orient="vertical").pack(side="left", fill="y", padx=16, pady=2)

        ttk.Label(
            brand, text=LANG["download_dir"],
            font=("Segoe UI", 9)
        ).pack(side="left")

        self.dir_var = tk.StringVar(value=self.config["download_dir"])
        dir_entry = ttk.Entry(
            brand, textvariable=self.dir_var, width=30,
            font=("Segoe UI", 9)
        )
        dir_entry.pack(side="left", padx=6)

        browse_btn = ttk.Button(
            brand, text=LANG["browse"],
            command=self._browse_dir, width=6
        )
        browse_btn.pack(side="left", padx=(0, 16))

        ttk.Label(
            brand, text=LANG["max_threads"],
            font=("Segoe UI", 9)
        ).pack(side="left")

        self.thread_var = tk.StringVar(value=str(self.config["max_threads"]))
        self.thread_var.trace_add("write", lambda *_: self._save_threads())
        thread_spin = ttk.Spinbox(
            brand, from_=1, to=32,
            textvariable=self.thread_var, width=4,
            font=("Segoe UI", 9)
        )
        thread_spin.pack(side="left")

        ttk.Separator(self.root, orient="horizontal").pack(fill="x", padx=16, pady=(10, 0))

    def _save_threads(self):
        try:
            self.config["max_threads"] = int(self.thread_var.get())
        except ValueError:
            pass

    def _browse_dir(self):
        path = filedialog.askdirectory()
        if path:
            self.dir_var.set(path)
            self.config["download_dir"] = path

    def _build_main_area(self):
        paned = ttk.PanedWindow(self.root, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=16, pady=8)

        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=3)

        section_label = ttk.Label(
            left_frame, text=LANG["platforms"],
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
            right_frame, text=LANG["vip_player"],
            font=("Segoe UI", 11, "bold")
        )
        vip_header.pack(anchor="w", pady=(0, 4))

        vip_container = ttk.Frame(right_frame, relief="solid", borderwidth=1)
        vip_container.pack(fill="both", expand=True)

        self.vip_panel = VIPParserPanel(vip_container)
        self.vip_panel.pack(fill="both", expand=True, padx=8, pady=8)

    def _build_bottom_bar(self):
        bottom = ttk.Frame(self.root)
        bottom.pack(side="bottom", fill="x", padx=16, pady=(0, 8))

        progress_row = ttk.Frame(bottom)
        progress_row.pack(fill="x", pady=(0, 6))
        ttk.Label(
            progress_row,
            text="下载进度",
            font=("Segoe UI", 9),
        ).pack(side="left", padx=(0, 8))
        self.progress = ttk.Progressbar(progress_row, mode="determinate")
        self.progress.pack(side="left", fill="x", expand=True)

        log_frame = ttk.LabelFrame(bottom, text=LANG["log"], padding=(4, 2))
        log_frame.pack(fill="both", expand=True)

        self.log_text = tk.Text(
            log_frame, height=5, state="disabled",
            wrap="word", font=("Consolas", 9),
            bg="#fafafa", relief="flat", borderwidth=0
        )
        self.log_text.tag_config("info", foreground=TEXT_SECONDARY)
        self.log_text.tag_config("success", foreground="#2d8a4e")
        self.log_text.tag_config("error", foreground=ACCENT)
        self.log_text.tag_config("warning", foreground="#b26a00")

        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.log_text.pack(fill="both", expand=True)

    def _on_download_done(self, result):
        self.progress.stop()
        self.progress["mode"] = "determinate"
        self.progress["value"] = 100 if result.success else 0
        if result.cancelled:
            self.log("下载已停止", "info")
            return
        if result.success:
            import tkinter.messagebox as mb
            mb.showinfo("成功", f"下载完成:\n{result.file_path}")
        else:
            import tkinter.messagebox as mb
            mb.showerror("错误", result.message)

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
