import webbrowser
import tkinter as tk
from tkinter import ttk
from tkinter.messagebox import showwarning
import requests
from bs4 import BeautifulSoup

LANG = {
    "zh": {
        "title": "🔓 VIP 播放",
        "search_label": "搜索:",
        "search_btn": "搜索",
        "type_label": "类型:",
        "types": {"电视剧": "1", "电影": "2", "综艺": "3"},
        "route_label": "线路:",
        "routes": [("线路一", "https://www.1717yun.com/jx/ty.php"),
                   ("线路二", "https://jx.jsonplayer.com/player/"),
                   ("线路三", "https://yparse.jn1.cc/index.php")],
        "result_label": "结果:",
        "play_btn": "▶ 播放",
        "mode_label": "方式:",
        "modes": {"搜索": "search", "链接": "link"},
        "not_found": "未找到结果",
        "note": "当前仅支持腾讯视频搜索"
    },
    "en": {
        "title": "🔓 VIP Player",
        "search_label": "Search:",
        "search_btn": "Search",
        "type_label": "Type:",
        "types": {"Drama": "1", "Movie": "2", "Show": "3"},
        "route_label": "Route:",
        "routes": [("Route 1", "https://www.1717yun.com/jx/ty.php"),
                   ("Route 2", "https://jx.jsonplayer.com/player/"),
                   ("Route 3", "https://yparse.jn1.cc/index.php")],
        "result_label": "Result:",
        "play_btn": "▶ Play",
        "mode_label": "Mode:",
        "modes": {"Search": "search", "Link": "link"},
        "not_found": "No results found",
        "note": "Currently only supports Tencent Video search"
    }
}


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
        ttk.Label(self, text=self._tr("title"), font=("", 14, "bold")).pack(anchor="w", pady=(0, 10))

        frame = ttk.Frame(self)
        frame.pack(fill="x", pady=2)

        ttk.Label(frame, text=self._tr("mode_label")).grid(row=0, column=0, sticky="w")
        self.mode_var = tk.StringVar(value="search")
        for i, (k, v) in enumerate(self._tr("modes").items() if isinstance(self._tr("modes"), dict) else self.txt["modes"].items(), start=1):
            ttk.Radiobutton(frame, text=k, variable=self.mode_var, value=v).grid(row=0, column=i, sticky="w")

        ttk.Label(frame, text=self._tr("search_label")).grid(row=1, column=0, sticky="w")
        self.query_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.query_var).grid(row=1, column=1, padx=5)
        ttk.Button(frame, text=self._tr("search_btn"), command=self._do_search).grid(row=1, column=2, padx=5)

        ttk.Label(frame, text=self._tr("type_label")).grid(row=2, column=0, sticky="w")
        self.type_var = tk.StringVar(value="1")
        types = self._tr("types")
        for i, (k, v) in enumerate(types.items(), start=1):
            ttk.Radiobutton(frame, text=k, variable=self.type_var, value=v).grid(row=2, column=i, sticky="w")

        ttk.Label(frame, text=self._tr("route_label")).grid(row=3, column=0, sticky="w")
        self.route_var = tk.StringVar()
        routes = self._tr("routes")
        for i, (k, v) in enumerate(routes, start=1):
            rb = ttk.Radiobutton(frame, text=k, variable=self.route_var, value=v)
            rb.grid(row=3, column=i, sticky="w")
            if i == 1:
                rb.invoke()

        ttk.Label(frame, text=self._tr("result_label")).grid(row=4, column=0, sticky="w")
        self.result_combo = ttk.Combobox(frame, state="readonly", width=40)
        self.result_combo.grid(row=4, column=1, padx=5)
        ttk.Button(frame, text=self._tr("play_btn"), command=self._play).grid(row=4, column=2, padx=5)

        ttk.Label(self, text=self._tr("note"), foreground="gray").pack(anchor="w", pady=(5, 0))

    def _do_search(self):
        query = self.query_var.get().strip()
        if not query:
            return
        search_type = self.type_var.get()
        route = self.route_var.get()
        results = self._search_video(query, search_type, route)
        self.result_combo["values"] = list(results.keys())
        if results:
            self.mapping = results
            self.result_combo.set(list(results.keys())[0])
        else:
            showwarning("", self._tr("not_found"))

    def _search_video(self, query, search_type, route):
        # Wraps original VIP视频解析(1).py search logic for Tencent Video
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
