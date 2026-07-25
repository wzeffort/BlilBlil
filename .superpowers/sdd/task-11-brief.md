# Task 11: Final integration & README

**Goal:** Create README.md and verify the full project works.

## Steps

### 1. Verify config wiring

Check that `main.py` has `get_config()` method and `instance.app = self` in `_build_main_area`. The implementer in Task 2 should have added these. If not, add them.

### 2. Create README.md

Write bilingual README at `D:\python\mv\BlilBlil\README.md`:

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

### 3. Final verification

```powershell
cd D:\python\mv\BlilBlil
C:\Users\Lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -c "from platforms import discover_platforms; plats = discover_platforms(); print(f'Discovered {len(plats)} platforms:'); [print(f'  {p.icon} {p.name}') for p in plats]"
```

Expected:
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

Report to `task-11-report.md`.
