# BlilBlil Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a unified multi-platform video downloader and VIP player with Tkinter GUI.

**Architecture:** Modular plugin design — each platform is a `BaseDownloader` subclass auto-discovered from `platforms/`. Main window generates tabs dynamically. VIP parser as separate side panel.

**Tech Stack:** Python 3.10+, tkinter/ttk, requests, beautifulsoup4, yt-dlp, sv-ttk, ffmpeg

## Global Constraints

- Bilingual support (zh/en) — all UI strings via translation dict
- Download directory: default `./downloads/` + manual browse
- All hardcoded paths removed; config persisted to `config.json`
- SMTP credentials from original `config.py` explicitly excluded
- ffmpeg bundled in `assets/ffmpeg/`
- Each platform must handle network errors with 3 retries

---

### Task 1: Project scaffold + core infrastructure

**Files:**
- Create: `main.py`
- Create: `core/__init__.py`
- Create: `core/downloader.py`
- Create: `core/config.py`
- Create: `core/utils.py`
- Create: `platforms/__init__.py`
- Create: `tools/__init__.py`
- Create: `requirements.txt`
- Create: `assets/ffmpeg/.gitkeep`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p core platforms tools assets/ffmpeg downloads
```

- [ ] **Step 2: Write core/downloader.py — BaseDownloader abstract class**

```python
import abc
from dataclasses import dataclass, field
from typing import Optional
import tkinter.ttk as ttk


@dataclass
class DownloadResult:
    success: bool
    message: str
    file_path: Optional[str] = None


class BaseDownloader(abc.ABC):
    name: str = ""
    icon: str = ""
    description: str = ""

    @abc.abstractmethod
    def create_tab(self, parent: ttk.Frame) -> ttk.Frame:
        pass

    def validate_url(self, url: str) -> bool:
        return bool(url and url.startswith("http"))

    @abc.abstractmethod
    def download(self, url: str, output_dir: str, **kwargs) -> DownloadResult:
        pass
```

- [ ] **Step 3: Write core/config.py**

```python
import json
import os

DEFAULT_CONFIG = {
    "download_dir": "./downloads",
    "ffmpeg_path": "",
    "language": "zh",
    "max_threads": 7
}


class Config:
    def __init__(self, path: str = "config.json"):
        self.path = path
        self.data = dict(DEFAULT_CONFIG)
        self.load()

    def load(self):
        if os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as f:
                self.data.update(json.load(f))

    def save(self):
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def __getitem__(self, key):
        return self.data[key]

    def __setitem__(self, key, value):
        self.data[key] = value
        self.save()
```

- [ ] **Step 4: Write core/utils.py**

```python
import os
import re
import subprocess
from typing import Optional


def sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', '_', name)


def get_ffmpeg_path(config) -> str:
    path = config["ffmpeg_path"]
    if path and os.path.exists(path):
        return path
    for candidate in ["./assets/ffmpeg/ffmpeg.exe", "ffmpeg"]:
        if os.path.exists(candidate) or candidate == "ffmpeg":
            return candidate
    return "ffmpeg"


def merge_audio_video(audio: str, video: str, output: str, ffmpeg: str) -> bool:
    cmd = [ffmpeg, "-i", audio, "-i", video, "-acodec", "copy", "-vcodec", "copy", output]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode == 0:
        os.remove(audio)
        os.remove(video)
        return True
    return False


def merge_ts(filelist: str, output: str, ffmpeg: str) -> bool:
    cmd = [ffmpeg, "-f", "concat", "-i", filelist, "-c", "copy", output]
    result = subprocess.run(cmd, capture_output=True)
    return result.returncode == 0


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)
```

- [ ] **Step 5: Write platforms/__init__.py**

```python
import importlib
import pkgutil
from core.downloader import BaseDownloader

_platforms: list[type[BaseDownloader]] = []


def discover_platforms():
    global _platforms
    if _platforms:
        return _platforms
    package = importlib.import_module("platforms")
    for importer, modname, ispkg in pkgutil.iter_modules(package.__path__):
        if modname.startswith("_"):
            continue
        module = importlib.import_module(f"platforms.{modname}")
        for attr in dir(module):
            cls = getattr(module, attr)
            if isinstance(cls, type) and issubclass(cls, BaseDownloader) and cls is not BaseDownloader:
                _platforms.append(cls)
    return _platforms
```

- [ ] **Step 6: Write requirements.txt**

```
requests>=2.28
beautifulsoup4>=4.11
yt-dlp>=2023
sv-ttk>=2.5
```

- [ ] **Step 7: Create __init__ files and assets placeholder**

```bash
echo "" > core/__init__.py
echo "" > tools/__init__.py
echo "" > assets/ffmpeg/.gitkeep
```

- [ ] **Step 8: Commit**

```bash
git add core/ platforms/__init__.py tools/ requirements.txt assets/ main.py
git commit -m "feat: add core infrastructure and project scaffold"
```

---

### Task 2: Main window GUI

**Files:**
- Create: `main.py` (full implementation)
- Create: `tools/vip_parser.py`

- [ ] **Step 1: Write tools/vip_parser.py — VIP player panel**

```python
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
```

- [ ] **Step 2: Write main.py — main window with platform tabs**

```python
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
```

- [ ] **Step 3: Add color tags to log_text in _build_bottom_bar**

```python
self.log_text.tag_config("info", foreground="black")
self.log_text.tag_config("success", foreground="green")
self.log_text.tag_config("error", foreground="red")
```

Add this right after `self.log_text = tk.Text(...)`.

- [ ] **Step 4: Commit**

```bash
git add main.py tools/vip_parser.py
git commit -m "feat: add main window GUI and VIP player panel"
```

---

### Task 3: Bilibili platform

**Files:**
- Create: `platforms/bilibili.py`

- [ ] **Step 1: Write the tab UI and download logic**

```python
import json
import os
import tkinter as tk
from tkinter import ttk, messagebox
import requests
from bs4 import BeautifulSoup
from core.downloader import BaseDownloader, DownloadResult
from core.utils import sanitize_filename, get_ffmpeg_path, merge_audio_video, ensure_dir


class Bilibili(BaseDownloader):
    name = "B站"
    icon = "🎬"
    description = "Bilibili video downloader"

    def create_tab(self, parent):
        frame = ttk.Frame(parent, padding=10)
        ttk.Label(frame, text="Bilibili", font=("", 16, "bold")).pack(anchor="w")
        ttk.Label(frame, text=f"{self.icon} {self.description}").pack(anchor="w", pady=(0, 10))

        ttk.Label(frame, text="Video URL:").pack(anchor="w")
        self.url_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.url_var, width=60).pack(fill="x", pady=5)

        self.download_btn = ttk.Button(frame, text="Download", command=self._on_download)
        self.download_btn.pack(pady=10)

        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(frame, textvariable=self.status_var).pack(anchor="w")
        return frame

    def _on_download(self):
        url = self.url_var.get().strip()
        if not self.validate_url(url):
            messagebox.showerror("Error", "Invalid URL")
            return
        output_dir = self._get_output_dir()
        result = self.download(url, output_dir)
        if result.success:
            messagebox.showinfo("Success", f"Downloaded: {result.file_path}")
        else:
            messagebox.showerror("Error", result.message)

    def _get_output_dir(self):
        # Accessed via app reference — simplified
        return os.path.join(os.getcwd(), "downloads")

    def download(self, url, output_dir, **kwargs):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.bilibili.com"
        }
        try:
            res = requests.get(url, headers=headers, timeout=15)
            res.encoding = "utf-8"
            soup = BeautifulSoup(res.text, "html.parser")

            playinfo = None
            for script in soup.find_all("script"):
                if "window.__playinfo__" in script.text:
                    json_str = script.text.split("=", 1)[1].strip().rsplit(";", 1)[0]
                    playinfo = json.loads(json_str)
                    break

            if not playinfo:
                return DownloadResult(False, "No playinfo found")

            audio_url = playinfo["data"]["dash"]["audio"][0]["base_url"]
            video_url = playinfo["data"]["dash"]["video"][0]["base_url"]

            title_tag = soup.find("h1", class_="video-title")
            title = sanitize_filename(title_tag.text if title_tag else "bilibili_video")

            ensure_dir(output_dir)
            audio_path = os.path.join(output_dir, "audio.m4s")
            video_path = os.path.join(output_dir, "video.m4s")
            output_path = os.path.join(output_dir, f"{title}.mp4")

            for path, src_url in [(audio_path, audio_url), (video_path, video_url)]:
                r = requests.get(src_url, headers=headers, stream=True, timeout=30)
                with open(path, "wb") as f:
                    for chunk in r.iter_content(1024):
                        if chunk:
                            f.write(chunk)

            ffmpeg = get_ffmpeg_path(kwargs.get("config"))
            if merge_audio_video(audio_path, video_path, output_path, ffmpeg):
                return DownloadResult(True, "Download complete", output_path)
            return DownloadResult(False, "FFmpeg merge failed")
        except Exception as e:
            return DownloadResult(False, str(e))
```

- [ ] **Step 2: Commit**

```bash
git add platforms/bilibili.py
git commit -m "feat: add Bilibili platform downloader"
```

---

### Task 4: Douyin platform

**Files:**
- Create: `platforms/douyin.py`

- [ ] **Step 1: Write douyin platform**

```python
import os
import random
import tkinter as tk
from tkinter import ttk, messagebox
import requests
from core.downloader import BaseDownloader, DownloadResult
from core.utils import ensure_dir


class Douyin(BaseDownloader):
    name = "抖音"
    icon = "🎵"
    description = "Douyin (TikTok China) video downloader"

    def create_tab(self, parent):
        frame = ttk.Frame(parent, padding=10)
        ttk.Label(frame, text="Douyin", font=("", 16, "bold")).pack(anchor="w")
        ttk.Label(frame, text=f"{self.icon} {self.description}").pack(anchor="w", pady=(0, 10))
        ttk.Label(frame, text="Video URL:").pack(anchor="w")
        self.url_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.url_var, width=60).pack(fill="x", pady=5)
        ttk.Button(frame, text="Download", command=self._on_download).pack(pady=10)
        return frame

    def _on_download(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showerror("Error", "Please paste a video URL")
            return
        output_dir = os.path.join(os.getcwd(), "downloads", "douyin")
        result = self.download(url, output_dir)
        if result.success:
            messagebox.showinfo("Success", f"Downloaded: {result.file_path}")
        else:
            messagebox.showerror("Error", result.message)

    def download(self, url, output_dir, **kwargs):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.douyin.com/"
        }
        try:
            ensure_dir(output_dir)
            r = requests.get(url, headers=headers, stream=True, timeout=30)
            if r.status_code != 200:
                return DownloadResult(False, f"HTTP {r.status_code}")
            name = f"douyin_{random.randint(10000, 99999)}.mp4"
            path = os.path.join(output_dir, name)
            with open(path, "wb") as f:
                for chunk in r.iter_content(1024):
                    if chunk:
                        f.write(chunk)
            return DownloadResult(True, "Download complete", path)
        except Exception as e:
            return DownloadResult(False, str(e))
```

- [ ] **Step 2: Commit**

```bash
git add platforms/douyin.py
git commit -m "feat: add Douyin platform downloader"
```

---

### Task 5: Tencent Video platform

**Files:**
- Create: `platforms/tencent.py`

- [ ] **Step 1: Write tencent platform**

```python
import json
import os
import re
import tkinter as tk
from tkinter import ttk, messagebox
import requests
from bs4 import BeautifulSoup
from core.downloader import BaseDownloader, DownloadResult
from core.utils import sanitize_filename, get_ffmpeg_path, ensure_dir, merge_ts


class Tencent(BaseDownloader):
    name = "腾讯视频"
    icon = "📺"
    description = "Tencent Video downloader"

    def create_tab(self, parent):
        frame = ttk.Frame(parent, padding=10)
        ttk.Label(frame, text="Tencent Video", font=("", 16, "bold")).pack(anchor="w")
        ttk.Label(frame, text=f"{self.icon} {self.description}").pack(anchor="w", pady=(0, 10))
        ttk.Label(frame, text="Video URL:").pack(anchor="w")
        self.url_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.url_var, width=60).pack(fill="x", pady=5)
        ttk.Label(frame, text="Cookie:").pack(anchor="w")
        self.cookie_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.cookie_var, width=60).pack(fill="x", pady=5)
        ttk.Label(frame, text="Data params (JSON):").pack(anchor="w")
        self.data_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.data_var, width=60).pack(fill="x", pady=5)
        ttk.Button(frame, text="Download", command=self._on_download).pack(pady=10)
        return frame

    def _on_download(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showerror("Error", "Please enter proxyhttp URL")
            return
        output_dir = os.path.join(os.getcwd(), "downloads", "tencent")
        result = self.download(url, output_dir,
                               cookie=self.cookie_var.get(),
                               data=self.data_var.get())
        if result.success:
            messagebox.showinfo("Success", f"Downloaded: {result.file_path}")
        else:
            messagebox.showerror("Error", result.message)

    def download(self, url, output_dir, **kwargs):
        headers = {
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; Redmi K30 Pro) AppleWebKit/537.36",
            "cookie": kwargs.get("cookie", "")
        }
        data_str = kwargs.get("data", "{}")
        try:
            data = json.loads(data_str) if data_str else {}
        except json.JSONDecodeError:
            return DownloadResult(False, "Invalid JSON in data params")

        try:
            res = requests.get(url, headers=headers, params=data, timeout=15)
            soup = BeautifulSoup(res.content, "html.parser")
            info = json.loads(soup.text)
            vinfo = json.loads(info["vinfo"])
            m3u8 = vinfo["vl"]["vi"][0]["ul"]["m3u8"]
            s = re.sub(r"#.*", "", m3u8)
            links = s.split()
            if not links:
                return DownloadResult(False, "No ts segments found")

            ensure_dir(output_dir)
            filelist = os.path.join(output_dir, "filelist.txt")
            with open(filelist, "w") as f:
                for link in links:
                    name = link.split("?")[0].split("/")[-1]
                    f.write(f"file '{name}'\n")

            for i, link in enumerate(links):
                name = link.split("?")[0].split("/")[-1]
                r = requests.get(link, headers=headers, stream=True, timeout=30)
                with open(os.path.join(output_dir, name), "wb") as f:
                    f.write(r.content)

            output_path = os.path.join(output_dir, "output.mp4")
            ffmpeg = get_ffmpeg_path(kwargs.get("config"))
            if merge_ts(filelist, output_path, ffmpeg):
                for f in os.listdir(output_dir):
                    if f.endswith(".ts"):
                        os.remove(os.path.join(output_dir, f))
                os.remove(filelist)
                return DownloadResult(True, "Download complete", output_path)
            return DownloadResult(False, "FFmpeg merge failed")
        except Exception as e:
            return DownloadResult(False, str(e))


- [ ] **Step 2: Commit**

```bash
git add platforms/tencent.py
git commit -m "feat: add Tencent Video platform downloader"
```

---

### Task 6: iQiyi platform

**Files:**
- Create: `platforms/iqiyi.py`

- [ ] **Step 1: Write iqiyi platform**

```python
import json
import os
import re
import tkinter as tk
from tkinter import ttk, messagebox
import requests
from bs4 import BeautifulSoup
from core.downloader import BaseDownloader, DownloadResult
from core.utils import get_ffmpeg_path, ensure_dir


class IQiyi(BaseDownloader):
    name = "爱奇艺"
    icon = "🎥"
    description = "iQiyi video downloader"

    def create_tab(self, parent):
        frame = ttk.Frame(parent, padding=10)
        ttk.Label(frame, text="iQiyi", font=("", 16, "bold")).pack(anchor="w")
        ttk.Label(frame, text=f"{self.icon} {self.description}").pack(anchor="w", pady=(0, 10))
        ttk.Label(frame, text="DASH API URL:").pack(anchor="w")
        self.url_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.url_var, width=60).pack(fill="x", pady=5)
        ttk.Label(frame, text="Webpage URL (for title):").pack(anchor="w")
        self.page_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.page_var, width=60).pack(fill="x", pady=5)
        ttk.Button(frame, text="Download", command=self._on_download).pack(pady=10)
        return frame

    def _on_download(self):
        dash_url = self.url_var.get().strip()
        page_url = self.page_var.get().strip()
        if not dash_url:
            messagebox.showerror("Error", "Please enter DASH API URL")
            return
        output_dir = os.path.join(os.getcwd(), "downloads", "iqiyi")
        result = self.download(dash_url, output_dir, page_url=page_url)
        if result.success:
            messagebox.showinfo("Success", f"Downloaded: {result.file_path}")
        else:
            messagebox.showerror("Error", result.message)

    def download(self, url, output_dir, **kwargs):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://www.iqiyi.com/"
        }
        try:
            res = requests.get(url, headers=headers, timeout=15)
            data = json.loads(res.text)
            m3u8 = None
            for video in data["data"]["program"]["video"]:
                if "m3u8" in video:
                    m3u8 = video["m3u8"]
                    break
            if not m3u8:
                return DownloadResult(False, "No m3u8 found")
            s = re.sub(r"#.*", "", m3u8)
            links = [l.split("\n")[0] for l in s.split() if l.strip()]
            if not links:
                return DownloadResult(False, "No ts segments")

            title = "iqiyi_video"
            page_url = kwargs.get("page_url", "")
            if page_url:
                try:
                    pr = requests.get(page_url, headers=headers, timeout=10)
                    ps = BeautifulSoup(pr.content, "html.parser")
                    meta = ps.find("meta", attrs={"name": "irTitle"})
                    if meta:
                        title = re.sub(r'[\\/:*?"<>|]', "_", meta.get("content", "iqiyi_video"))
                except Exception:
                    pass

            ensure_dir(output_dir)
            filelist = os.path.join(output_dir, "filelist.txt")
            with open(filelist, "w") as f:
                for link in links:
                    name = link.split("=")[2].replace("&", "_") + ".ts" if "=" in link else f"seg_{links.index(link)}.ts"
                    f.write(f"file '{name}'\n")

            for link in links:
                name = link.split("=")[2].replace("&", "_") + ".ts" if "=" in link else f"seg_{links.index(link)}.ts"
                r = requests.get(link, headers=headers, stream=True, timeout=30)
                with open(os.path.join(output_dir, name), "wb") as f:
                    f.write(r.content)

            output_path = os.path.join(output_dir, f"{title}.mp4")
            ffmpeg = get_ffmpeg_path(kwargs.get("config"))
            if merge_ts(filelist, output_path, ffmpeg):
                for f in os.listdir(output_dir):
                    if f.endswith(".ts"):
                        os.remove(os.path.join(output_dir, f))
                os.remove(filelist)
                return DownloadResult(True, "Download complete", output_path)
            return DownloadResult(False, "FFmpeg merge failed")
        except Exception as e:
            return DownloadResult(False, str(e))
```

- [ ] **Step 2: Commit**

```bash
git add platforms/iqiyi.py
git commit -m "feat: add iQiyi platform downloader"
```

---

### Task 7: Youku platform

**Files:**
- Create: `platforms/youku.py`

- [ ] **Step 1: Write youku platform**

```python
import json
import os
import re
import tkinter as tk
from tkinter import ttk, messagebox
import requests
from bs4 import BeautifulSoup
from core.downloader import BaseDownloader, DownloadResult
from core.utils import get_ffmpeg_path, ensure_dir


class Youku(BaseDownloader):
    name = "优酷"
    icon = "🎞"
    description = "Youku video downloader"

    def create_tab(self, parent):
        frame = ttk.Frame(parent, padding=10)
        ttk.Label(frame, text="Youku", font=("", 16, "bold")).pack(anchor="w")
        ttk.Label(frame, text=f"{self.icon} {self.description}").pack(anchor="w", pady=(0, 10))
        ttk.Label(frame, text="Mtop API URL:").pack(anchor="w")
        self.url_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.url_var, width=60).pack(fill="x", pady=5)
        ttk.Label(frame, text="Cookie:").pack(anchor="w")
        self.cookie_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.cookie_var, width=60).pack(fill="x", pady=5)
        ttk.Button(frame, text="Download", command=self._on_download).pack(pady=10)
        return frame

    def _on_download(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showerror("Error", "Please enter Mtop API URL")
            return
        output_dir = os.path.join(os.getcwd(), "downloads", "youku")
        result = self.download(url, output_dir, cookie=self.cookie_var.get())
        if result.success:
            messagebox.showinfo("Success", f"Downloaded: {result.file_path}")
        else:
            messagebox.showerror("Error", result.message)

    def download(self, url, output_dir, **kwargs):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": "https://v.youku.com/",
            "Cookie": kwargs.get("cookie", "")
        }
        try:
            res = requests.get(url, headers=headers, timeout=15)
            text = res.text
            if text.startswith("mtopjsonp"):
                text = text[12:-1]
            data = json.loads(text)
            title = data["data"]["data"]["video"]["title"].replace(" ", "_")
            title = re.sub(r'[\\/:*?"<>|]', "_", title)

            cdn_urls = [seg["cdn_url"] for seg in data["data"]["data"]["stream"][1]["segs"]]

            ensure_dir(output_dir)
            filelist = os.path.join(output_dir, "filelist.txt")
            with open(filelist, "w") as f:
                for cdn in cdn_urls:
                    name = cdn.split("=")[-2].replace("&", "_") + ".ts" if "=" in cdn else f"seg_{cdn_urls.index(cdn)}.ts"
                    f.write(f"file '{name}'\n")

            for cdn in cdn_urls:
                name = cdn.split("=")[-2].replace("&", "_") + ".ts" if "=" in cdn else f"seg_{cdn_urls.index(cdn)}.ts"
                r = requests.get(cdn, headers=headers, stream=True, timeout=30)
                with open(os.path.join(output_dir, name), "wb") as f:
                    f.write(r.content)

            output_path = os.path.join(output_dir, f"{title}.mp4")
            ffmpeg = get_ffmpeg_path(kwargs.get("config"))
            if merge_ts(filelist, output_path, ffmpeg):
                for f in os.listdir(output_dir):
                    if f.endswith(".ts"):
                        os.remove(os.path.join(output_dir, f))
                os.remove(filelist)
                return DownloadResult(True, "Download complete", output_path)
            return DownloadResult(False, "FFmpeg merge failed")
        except Exception as e:
            return DownloadResult(False, str(e))
```

- [ ] **Step 2: Commit**

```bash
git add platforms/youku.py
git commit -m "feat: add Youku platform downloader"
```

---

### Task 8: YouTube platform

**Files:**
- Create: `platforms/youtube.py`

- [ ] **Step 1: Write youtube platform**

```python
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
```

- [ ] **Step 2: Commit**

```bash
git add platforms/youtube.py
git commit -m "feat: add YouTube platform downloader"
```

---

### Task 9: CCTV platform

**Files:**
- Create: `platforms/cctv.py`

- [ ] **Step 1: Write cctv platform**

```python
import json
import os
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox
import requests
from bs4 import BeautifulSoup
from core.downloader import BaseDownloader, DownloadResult
from core.utils import get_ffmpeg_path, ensure_dir


class CCTV(BaseDownloader):
    name = "CCTV"
    icon = "📡"
    description = "CCTV video downloader"

    def create_tab(self, parent):
        frame = ttk.Frame(parent, padding=10)
        ttk.Label(frame, text="CCTV", font=("", 16, "bold")).pack(anchor="w")
        ttk.Label(frame, text=f"{self.icon} {self.description}").pack(anchor="w", pady=(0, 10))
        ttk.Label(frame, text="Video PID URL:").pack(anchor="w")
        self.url_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.url_var, width=60).pack(fill="x", pady=5)
        ttk.Button(frame, text="Download", command=self._on_download).pack(pady=10)
        return frame

    def _on_download(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showerror("Error", "Please enter getHttpVideoInfo URL")
            return
        output_dir = os.path.join(os.getcwd(), "downloads", "cctv")
        result = self.download(url, output_dir)
        if result.success:
            messagebox.showinfo("Success", f"Downloaded: {result.file_path}")
        else:
            messagebox.showerror("Error", result.message)

    def download(self, url, output_dir, **kwargs):
        try:
            res = requests.get(url, timeout=15)
            data = json.loads(res.text)
            hls_url = data["hls_url"]

            ensure_dir(output_dir)
            output_path = os.path.join(output_dir, "cctv_video.mp4")
            ffmpeg = get_ffmpeg_path(kwargs.get("config"))
            cmd = [ffmpeg, "-i", hls_url, "-c", "copy", output_path]
            result = subprocess.run(cmd, capture_output=True, timeout=300)
            if result.returncode == 0:
                return DownloadResult(True, "Download complete", output_path)
            return DownloadResult(False, result.stderr.decode())
        except Exception as e:
            return DownloadResult(False, str(e))
```

- [ ] **Step 2: Commit**

```bash
git add platforms/cctv.py
git commit -m "feat: add CCTV platform downloader"
```

---

### Task 10: Generic M3U8 platform

**Files:**
- Create: `platforms/m3u8_generic.py`

- [ ] **Step 1: Write generic m3u8 platform**

```python
import os
import tkinter as tk
from tkinter import ttk, messagebox
import requests
from core.downloader import BaseDownloader, DownloadResult
from core.utils import get_ffmpeg_path, ensure_dir, merge_ts


class M3U8Generic(BaseDownloader):
    name = "M3U8"
    icon = "🔗"
    description = "Generic M3U8 video downloader"

    def create_tab(self, parent):
        frame = ttk.Frame(parent, padding=10)
        ttk.Label(frame, text="Generic M3U8", font=("", 16, "bold")).pack(anchor="w")
        ttk.Label(frame, text=f"{self.icon} {self.description}").pack(anchor="w", pady=(0, 10))
        ttk.Label(frame, text="M3U8 URL:").pack(anchor="w")
        self.url_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.url_var, width=60).pack(fill="x", pady=5)
        ttk.Button(frame, text="Download", command=self._on_download).pack(pady=10)
        return frame

    def _on_download(self):
        url = self.url_var.get().strip()
        if not url:
            messagebox.showerror("Error", "Please enter M3U8 URL")
            return
        output_dir = os.path.join(os.getcwd(), "downloads", "m3u8")
        result = self.download(url, output_dir)
        if result.success:
            messagebox.showinfo("Success", f"Downloaded: {result.file_path}")
        else:
            messagebox.showerror("Error", result.message)

    def download(self, url, output_dir, **kwargs):
        try:
            res = requests.get(url, timeout=15)
            lines = res.text.strip().split("\n")
            ts_urls = [line for line in lines if line and not line.startswith("#")]

            if not ts_urls:
                return DownloadResult(False, "No ts segments found in m3u8")

            base_url = url.rsplit("/", 1)[0] + "/"
            ensure_dir(output_dir)
            filelist = os.path.join(output_dir, "filelist.txt")

            with open(filelist, "w") as f:
                for ts in ts_urls:
                    ts_url = ts if ts.startswith("http") else base_url + ts
                    name = ts.split("/")[-1].split("?")[0]
                    f.write(f"file '{name}'\n")
                    r = requests.get(ts_url, stream=True, timeout=30)
                    with open(os.path.join(output_dir, name), "wb") as f2:
                        f2.write(r.content)

            output_path = os.path.join(output_dir, "output.mp4")
            ffmpeg = get_ffmpeg_path(kwargs.get("config"))
            if merge_ts(filelist, output_path, ffmpeg):
                for f in os.listdir(output_dir):
                    if f.endswith(".ts"):
                        os.remove(os.path.join(output_dir, f))
                os.remove(filelist)
                return DownloadResult(True, "Download complete", output_path)
            return DownloadResult(False, "FFmpeg merge failed")
        except Exception as e:
            return DownloadResult(False, str(e))


- [ ] **Step 2: Commit**

```bash
git add platforms/m3u8_generic.py
git commit -m "feat: add generic M3U8 downloader"
```

---

### Task 11: Final integration & README

**Files:**
- Modify: `main.py` (wire config to platform download methods)
- Create: `README.md`

- [ ] **Step 1: Update main.py to pass config to download calls**

Edit `main.py` — add `get_config` method and pass it to platform tabs:

Add to `BlilBlilApp`:
```python
def get_config(self):
    return self.config
```

Update `_build_main_area` platform tab creation to inject app reference:
```python
instance = cls()
instance.app = self  # for accessing config later
tab = instance.create_tab(self.notebook)
```

Platform download methods access config via `self.app.get_config()`.

- [ ] **Step 2: Write bilingual README.md**

```markdown
# BlilBlil — Multi-Platform Video Downloader & VIP Player

[中文](#中文) | [English](#english)

---

## 中文

BlilBlil 是一个多平台视频下载工具，支持主流视频网站的视频下载和 VIP 视频解析播放。

### 支持的平台

- 🎬 **B站** — 解析 playinfo，下载 m4s 音视频并合并
- 🎵 **抖音** — 直接下载 mp4
- 📺 **腾讯视频** — M3U8 分段下载
- 🎥 **爱奇艺** — DASH API → M3U8 下载
- 🎞 **优酷** — Mtop API 下载
- ▶ **YouTube** — yt-dlp 下载
- 📡 **CCTV** — HLS 流直接下载
- 🔗 **通用 M3U8** — 任意 M3U8 链接下载

### VIP 播放

内置 VIP 视频解析器，支持搜索腾讯视频并调用第三方解析通道播放。

### 安装

```bash
pip install -r requirements.txt
python main.py
```

### 打包

```bash
pip install pyinstaller
pyinstaller --onefile --add-data "assets/ffmpeg;assets/ffmpeg" main.py
```

---

## English

BlilBlil is a multi-platform video downloader supporting mainstream video sites.

### Supported Platforms

- 🎬 **Bilibili** — parse playinfo, download m4s audio/video and merge
- 🎵 **Douyin** — direct mp4 download
- 📺 **Tencent Video** — M3U8 segment download
- 🎥 **iQiyi** — DASH API → M3U8 download
- 🎞 **Youku** — Mtop API download
- ▶ **YouTube** — yt-dlp download
- 📡 **CCTV** — HLS stream download
- 🔗 **Generic M3U8** — any M3U8 URL

### VIP Player

Built-in VIP video parser supporting Tencent Video search with third-party parsing routes.

### Install

```bash
pip install -r requirements.txt
python main.py
```

### Package

```bash
pip install pyinstaller
pyinstaller --onefile --add-data "assets/ffmpeg;assets/ffmpeg" main.py
```

## License

Apache 2.0
```

- [ ] **Step 3: Run final verification test**

```bash
python -c "from platforms import discover_platforms; plats = discover_platforms(); print(f'Discovered {len(plats)} platforms:'); [print(f'  {p.icon} {p.name}') for p in plats]"
```

Expected output:
```
Discovered 8 platforms:
  🎬 B站
  🎵 抖音
  📺 腾讯视频
  🎥 爱奇艺
  🎞 优酷
  ▶ YouTube
  📡 CCTV
  🔗 M3U8
```

- [ ] **Step 4: Commit**

```bash
git add README.md main.py
git commit -m "docs: add README and wire config to platforms"
```
