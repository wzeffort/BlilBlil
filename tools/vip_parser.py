import webbrowser
import tkinter as tk
from tkinter import ttk
from tkinter.messagebox import showwarning
import requests
from bs4 import BeautifulSoup

LANG = {
    "zh": {
        "title": "VIP 播放",
        "search_label": "搜索",
        "search_btn": "搜索",
        "type_label": "类型",
        "types": {"电视剧": "1", "电影": "2", "综艺": "3"},
        "route_label": "线路",
        "routes": [("线路一", "https://www.1717yun.com/jx/ty.php"),
                   ("线路二", "https://jx.jsonplayer.com/player/"),
                   ("线路三", "https://yparse.jn1.cc/index.php")],
        "result_label": "结果",
        "play_btn": "播放",
        "mode_label": "方式",
        "modes": {"搜索": "search", "链接": "link"},
        "not_found": "未找到结果",
        "note": "当前仅支持腾讯视频搜索",
        "tab_search": "搜索",
        "tab_link": "链接",
    },
    "en": {
        "title": "VIP Player",
        "search_label": "Search",
        "search_btn": "Search",
        "type_label": "Type",
        "types": {"Drama": "1", "Movie": "2", "Show": "3"},
        "route_label": "Route",
        "routes": [("Route 1", "https://www.1717yun.com/jx/ty.php"),
                   ("Route 2", "https://jx.jsonplayer.com/player/"),
                   ("Route 3", "https://yparse.jn1.cc/index.php")],
        "result_label": "Result",
        "play_btn": "Play",
        "mode_label": "Mode",
        "modes": {"Search": "search", "Link": "link"},
        "not_found": "No results found",
        "note": "Currently only supports Tencent Video search",
        "tab_search": "Search",
        "tab_link": "Link",
    }
}

PRIMARY = "#1a1a2e"
ACCENT = "#e94560"
TEXT_SECONDARY = "#6c757d"


class VIPParserPanel(ttk.Frame):
    def __init__(self, parent, lang="zh"):
        super().__init__(parent)
        self.lang = lang
        self.txt = LANG.get(lang, LANG["zh"])
        self.mapping = {}
        self._build_ui()

    def _tr(self, key):
        return self.txt.get(key, key)

    def _build_ui(self):
        header_frame = ttk.Frame(self)
        header_frame.pack(fill="x", pady=(0, 8))

        mode_frame = ttk.Frame(header_frame)
        mode_frame.pack(side="left")
        self.mode_var = tk.StringVar(value="search")
        for k, v in self._tr("modes").items():
            rb = ttk.Radiobutton(
                mode_frame, text=k, variable=self.mode_var,
                value=v, command=self._toggle_mode
            )
            rb.pack(side="left", padx=(0, 8))

        sep = ttk.Separator(self, orient="horizontal")
        sep.pack(fill="x", pady=(0, 8))

        self.search_frame = ttk.Frame(self)
        self._build_search_ui()
        self.search_frame.pack(fill="x")

        self.link_frame = ttk.Frame(self)
        self._build_link_ui()

    def _toggle_mode(self):
        if self.mode_var.get() == "search":
            self.link_frame.pack_forget()
            self.search_frame.pack(fill="x")
        else:
            self.search_frame.pack_forget()
            self.link_frame.pack(fill="x")

    def _build_search_ui(self):
        row = 0

        ttk.Label(self.search_frame, text=self._tr("search_label"),
                  font=("Segoe UI", 9, "bold")).grid(row=row, column=0, sticky="w", pady=(0, 4))
        row += 1

        query_frame = ttk.Frame(self.search_frame)
        query_frame.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(0, 6))
        self.query_var = tk.StringVar()
        ttk.Entry(query_frame, textvariable=self.query_var, width=24,
                  font=("Segoe UI", 9)).pack(side="left", fill="x", expand=True)
        ttk.Button(query_frame, text=self._tr("search_btn"),
                   command=self._do_search, width=8).pack(side="left", padx=(6, 0))
        row += 1

        ttk.Separator(self.search_frame, orient="horizontal").grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=4)
        row += 1

        ttk.Label(self.search_frame, text=self._tr("type_label"),
                  font=("Segoe UI", 9, "bold")).grid(row=row, column=0, sticky="w", pady=(0, 4))
        row += 1

        type_frame = ttk.Frame(self.search_frame)
        type_frame.grid(row=row, column=0, columnspan=3, sticky="w", pady=(0, 6))
        self.type_var = tk.StringVar(value="1")
        for k, v in self._tr("types").items():
            ttk.Radiobutton(type_frame, text=k, variable=self.type_var,
                            value=v).pack(side="left", padx=(0, 12))
        row += 1

        ttk.Label(self.search_frame, text=self._tr("route_label"),
                  font=("Segoe UI", 9, "bold")).grid(row=row, column=0, sticky="w", pady=(0, 4))
        row += 1

        route_frame = ttk.Frame(self.search_frame)
        route_frame.grid(row=row, column=0, columnspan=3, sticky="w", pady=(0, 8))
        first = True
        for k, v in self._tr("routes"):
            rb = ttk.Radiobutton(route_frame, text=k, variable=self.route_var, value=v)
            rb.pack(side="left", padx=(0, 8))
            if first:
                self.route_var = tk.StringVar(value=v)
                rb = ttk.Radiobutton(route_frame, text=k, variable=self.route_var, value=v)
                rb.pack(side="left", padx=(0, 8))
                rb.invoke()
                first = False
        row += 1

        ttk.Separator(self.search_frame, orient="horizontal").grid(
            row=row, column=0, columnspan=3, sticky="ew", pady=4)
        row += 1

        ttk.Label(self.search_frame, text=self._tr("result_label"),
                  font=("Segoe UI", 9, "bold")).grid(row=row, column=0, sticky="w", pady=(0, 4))
        row += 1

        result_frame = ttk.Frame(self.search_frame)
        result_frame.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(0, 4))
        self.result_combo = ttk.Combobox(result_frame, state="readonly", width=22,
                                          font=("Segoe UI", 9))
        self.result_combo.pack(side="left", fill="x", expand=True)
        ttk.Button(result_frame, text=self._tr("play_btn"),
                   command=self._play, width=8).pack(side="left", padx=(6, 0))

        note_frame = ttk.Frame(self.search_frame)
        note_frame.grid(row=row + 1, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Label(note_frame, text=self._tr("note"),
                  foreground=TEXT_SECONDARY, font=("Segoe UI", 8)).pack(anchor="w")

    def _build_link_ui(self):
        ttk.Label(self.link_frame, text=self._tr("route_label"),
                  font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 4))
        routes = self._tr("routes")
        first = True
        route_var = tk.StringVar()
        for k, v in routes:
            rb = ttk.Radiobutton(self.link_frame, text=k, variable=route_var, value=v)
            rb.pack(anchor="w", pady=1)
            if first:
                route_var.set(v)
                first = False

        ttk.Separator(self.link_frame, orient="horizontal").pack(fill="x", pady=8)

        ttk.Label(self.link_frame, text="URL",
                  font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 4))
        link_frame = ttk.Frame(self.link_frame)
        link_frame.pack(fill="x")
        self.link_var = tk.StringVar()
        ttk.Entry(link_frame, textvariable=self.link_var, width=24,
                  font=("Segoe UI", 9)).pack(side="left", fill="x", expand=True)

        def play_link():
            url = self.link_var.get().strip()
            route = route_var.get()
            if url and route:
                webbrowser.open(f"{route}?url={url}")

        ttk.Button(link_frame, text=self._tr("play_btn"),
                   command=play_link, width=8).pack(side="left", padx=(6, 0))

    def _do_search(self):
        query = self.query_var.get().strip()
        if not query:
            return
        results = self._search_video(query, self.type_var.get(), self.route_var.get())
        self.result_combo["values"] = list(results.keys())
        if results:
            self.mapping = results
            self.result_combo.set(list(results.keys())[0])
        else:
            showwarning("", self._tr("not_found"))

    def _search_video(self, query, search_type, route):
        txt_list = {}
        headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "referer": "https://v.qq.com/"
        }
        url = f"https://v.qq.com/x/search/?q={query}"
        try:
            html = requests.get(url, headers=headers, verify=False, timeout=15).content.decode("utf-8")
        except Exception:
            return txt_list
        parser = BeautifulSoup(html, "html.parser")

        if search_type == "1":
            root_div = parser.find("div", attrs={"class": "result_episode_list"})
            if root_div:
                link = root_div.find("a")
                if link:
                    detail = link.get("dt-params", "")
                    name = detail.split("&")[0].split("=")[-1] if "=" in detail else query
                    play_url = link.get("href", "")
                    full_url = f"{route}?url={play_url}"
                    txt_list[name] = full_url
        elif search_type == "2":
            root_div = parser.find("div", attrs={"class": "result_btn_line"})
            if root_div:
                link = root_div.find("a")
                if link:
                    detail = link.get("dt-params", "")
                    name = detail.split("&")[0].split("=")[-1] if "=" in detail else query
                    play_url = link.get("href", "")
                    full_url = f"{route}?url={play_url}"
                    txt_list[name] = full_url
        else:
            root_div = parser.find("div", attrs={"class": "result_link_list"})
            if root_div:
                for link in root_div.find_all("a", attrs={"dt-eid": "poster"}):
                    title = link.get("title", "")
                    play_url = link.get("href", "")
                    full_url = f"{route}?url={play_url}"
                    if title:
                        txt_list[title] = full_url
        return txt_list

    def _play(self):
        selected = self.result_combo.get()
        if selected and selected in self.mapping:
            webbrowser.open(self.mapping[selected])
