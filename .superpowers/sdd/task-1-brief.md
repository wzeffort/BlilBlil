# Task 1: Project scaffold + core infrastructure

**Goal:** Create the project directory structure and core infrastructure files.

## Files to Create

- `D:\python\mv\BlilBlil\core\__init__.py`
- `D:\python\mv\BlilBlil\core\downloader.py`
- `D:\python\mv\BlilBlil\core\config.py`
- `D:\python\mv\BlilBlil\core\utils.py`
- `D:\python\mv\BlilBlil\platforms\__init__.py`
- `D:\python\mv\BlilBlil\tools\__init__.py`
- `D:\python\mv\BlilBlil\assets\ffmpeg\.gitkeep`
- `D:\python\mv\BlilBlil\requirements.txt`

## 1. core/downloader.py

```python
import abc
from dataclasses import dataclass
from typing import Optional


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
    def create_tab(self, parent) -> object:
        pass

    def validate_url(self, url: str) -> bool:
        return bool(url and url.startswith("http"))

    @abc.abstractmethod
    def download(self, url: str, output_dir: str, **kwargs) -> DownloadResult:
        pass
```

## 2. core/config.py

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

## 3. core/utils.py

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

## 4. platforms/__init__.py

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

## 5. requirements.txt

```
requests>=2.28
beautifulsoup4>=4.11
yt-dlp>=2023
sv-ttk>=2.5
```

## 6. __init__ files

Create empty `core/__init__.py`, `tools/__init__.py`, and `assets/ffmpeg/.gitkeep`.

## Global Constraints

- Bilingual support (zh/en)
- All hardcoded paths removed
- SMTP credentials excluded
- No imports from non-standard libraries beyond what's in requirements.txt

## Report File

Write your report to `D:\python\mv\BlilBlil\.superpowers\sdd\task-1-report.md` containing:
- List of files created
- Any issues encountered
- Test results (run basic Python import checks)
