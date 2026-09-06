import re
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox
from urllib.parse import urlencode, urlsplit

ROUTES = (
    ("虾米解析", "https://jx.xmflv.cc/"),
    ("备用线路", "https://jx.jsonplayer.com/player/"),
)


def parser_target(value, route_index):
    value = value.strip()
    parsed = urlsplit(value)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("请先粘贴完整的视频播放页链接；片名可用官网搜索。")
    if route_index not in range(len(ROUTES)):
        raise ValueError("请选择解析线路")
    return ROUTES[route_index][1] + "?" + urlencode({"url": value})


def playback_target(value):
    value = value.strip()
    if not value:
        raise ValueError("请粘贴视频链接或输入片名")
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", value):
        parsed = urlsplit(value)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ValueError("请使用完整的 http 或 https 视频播放页链接")
        return value
    return "https://v.qq.com/x/search/?" + urlencode({"q": value})


class VIPParserPanel(ttk.Frame):
    """Compact parser launcher with explicit, dated verification limits."""

    def __init__(self, parent):
        super().__init__(parent)
        ttk.Label(self, text="视频链接或片名", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0, 6))
        self.query_var = tk.StringVar()
        entry = ttk.Entry(self, textvariable=self.query_var, width=28)
        entry.pack(fill="x", pady=(0, 8))
        entry.bind("<Return>", lambda event: self._play())
        self.route_combo = ttk.Combobox(self, values=[route[0] for route in ROUTES], state="readonly")
        self.route_combo.current(0)
        self.route_combo.pack(fill="x", pady=(0, 8))
        ttk.Button(self, text="解析播放", command=self._play).pack(fill="x")
        ttk.Button(self, text="官网打开 / 搜索", command=self._open).pack(fill="x", pady=(6, 0))
        ttk.Label(self, text="粘贴视频链接，选择线路后解析播放。\n输入片名可点击“官网打开 / 搜索”。\n第三方线路能否播放以实际结果为准。", foreground="#6c757d", wraplength=260, justify="left").pack(anchor="w", pady=(12, 0))

    def _play(self):
        try:
            target = parser_target(self.query_var.get(), self.route_combo.current())
        except ValueError as error:
            messagebox.showwarning("提示", str(error), parent=self)
            return
        self._launch(target)

    def _open(self):
        try:
            target = playback_target(self.query_var.get())
        except ValueError as error:
            messagebox.showwarning("提示", str(error), parent=self)
            return
        self._launch(target)

    def _launch(self, target):
        try:
            if not webbrowser.open(target):
                messagebox.showwarning("提示", "无法打开浏览器，请检查默认浏览器设置。", parent=self)
        except Exception:
            messagebox.showwarning("提示", "无法打开浏览器，请检查默认浏览器设置。", parent=self)
