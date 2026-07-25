# BlilBlil — Multi-Platform Video Downloader & VIP Player

## Overview

A desktop GUI application (Tkinter) that consolidates all existing video scraping/downloading scripts into one unified project. Two core functions: **download** (multi-platform) and **play** (VIP video parsing).

## Project Structure

```
BlilBlil/
├── main.py                   # Entry point + main window
├── core/
│   ├── __init__.py
│   ├── downloader.py          # BaseDownloader abstract class
│   ├── config.py              # Config management (path, ffmpeg, language)
│   └── utils.py               # Shared utilities (ffmpeg helper, path sanitize, etc.)
├── platforms/
│   ├── __init__.py            # Auto-register all platform modules
│   ├── bilibili.py            # Bilibili
│   ├── douyin.py              # Douyin (TikTok China)
│   ├── tencent.py             # Tencent Video
│   ├── iqiyi.py               # iQiyi
│   ├── youku.py               # Youku
│   ├── youtube.py             # YouTube (yt-dlp)
│   ├── cctv.py                # CCTV
│   └── m3u8_generic.py        # Generic M3U8 downloader
├── tools/
│   ├── __init__.py
│   └── vip_parser.py          # VIP video parser (search → parse → play in browser)
├── assets/
│   └── ffmpeg/                # Bundled ffmpeg (Windows)
├── requirements.txt
├── config.json                # User config (auto-generated)
└── README.md
```

## Architecture

### BaseDownloader Interface

```python
class BaseDownloader:
    name: str                  # Display name, e.g. "B站"
    icon: str                  # Unicode icon, e.g. "🎬"
    description: str           # Short description

    def create_tab(self, parent) -> ttk.Frame:
        """Build the platform's GUI tab page"""

    def validate_url(self, url: str) -> bool:
        """Check if URL matches this platform"""

    def download(self, url: str, output_dir: str, **kwargs) -> DownloadResult:
        """Execute download, return result (success/fail + message)"""
```

### Platform Auto-Discovery

`platforms/__init__.py` scans all `.py` files in the directory, imports them, and collects all subclasses of `BaseDownloader`. The main window reads this list to generate Tabs dynamically.

### GUI Layout (Main Window)

```
┌──────────────────────────────────────────────────┐
│  BlilBlil — Multi-Platform Video Downloader      │
├──────────────────────────────────────────────────┤
│  Download Dir: [./downloads]  [Browse...] [⚙]   │
├──────┬──────────────┬────────────────────────────┤
│      │              │  🔓 VIP Player              │
│  Tab │  Panel       │  ──────────                 │
│  Bar  │  (URL input  │  Search: [______] [Search] │
│      │   + Download) │  Type: ○Drama ○Movie ○Show │
│      │              │  Route: ○#1 ○#2 ○#3        │
│      │              │                            │
│      │              │  Results: [dropdown] [▶]   │
├──────┴──────────────┴────────────────────────────┤
│  [████████░░░░] 45%  12.3 MB/s                   │
│  📋 2026-07-25 12:30 B站 download complete       │
└──────────────────────────────────────────────────┘
```

- **Top bar**: global download directory selector + settings
- **Center-left**: platform tabs (ttk.Notebook), each tab contains URL input + download button + platform-specific options
- **Center-right**: VIP player panel (fixed, not a tab) — search Tencent Video, select episode/movie, open parsed URL in browser
- **Bottom**: progress bar + scrollable log area with colored output

## Download Strategy by Platform

| Platform | Method | Key Libraries |
|----------|--------|---------------|
| Bilibili | Parse `window.__playinfo__` → download m4s (audio+video) → ffmpeg merge | requests, bs4 |
| Douyin | Extract direct video URL → download mp4 | requests |
| Tencent | POST API → parse m3u8 → multi-thread ts segments → ffmpeg concat | requests, bs4 |
| iQiyi | DASH API → m3u8 → multi-thread ts → ffmpeg concat | requests, bs4, tqdm |
| Youku | Mtop API → cdn_url → ts download → ffmpeg concat | requests, bs4 |
| YouTube | yt-dlp library with progress hook | yt-dlp |
| CCTV | hls_url → ffmpeg direct stream copy | requests, subprocess |
| Generic M3U8 | Parse m3u8 playlist → multi-thread ts → ffmpeg concat | requests, tqdm |

## Config (core/config.py)

Saved as JSON (`config.json`):

```json
{
  "download_dir": "./downloads",
  "ffmpeg_path": "./assets/ffmpeg/ffmpeg.exe",
  "language": "zh",
  "max_threads": 7
}
```

- First run: auto-detect ffmpeg, fallback to system PATH
- Language: "zh" or "en" (UI labels switch dynamically)
- Config persisted on every change

## Error Handling

- `DownloadError` exception with code + message
- Network retry: 3 attempts with exponential backoff
- All errors displayed in log area (red text)
- ffmpeg missing: clear error with install instructions

## Dependencies

```
requests>=2.28
beautifulsoup4>=4.11
yt-dlp>=2023
sv-ttk>=2.5
Pillow>=9.0
```

## Packaging

- PyInstaller build: single `.exe` with bundled ffmpeg
- Cross-platform: supports Windows (primary), Linux/macOS (via source)

## VIP Parser (tools/vip_parser.py)

The VIP parser wraps the existing `VIP视频解析(1).py` logic:
- Search Tencent Video for dramas, movies, or TV shows
- Select from search results (dropdown)
- Choose a parsing route (3 third-party services)
- Open the parsed video URL in the system browser
- **Note:** Currently only supports Tencent Video search. Architecture allows adding more sources in the future.

It does NOT download — it plays via browser. Packaged as a standalone panel in the main window.

## Non-Goals

- Camera photo capture and email — excluded (config.py with SMTP credentials NOT included)
- Image resizing tool — excluded
- test.py (algorithm practice) — excluded
