# BlilBlil — Multi-Platform Video Downloader

[中文](#中文) | [English](#english)

---

## 中文

BlilBlil 是一个多平台视频下载工具，支持主流视频网站的非 VIP 普通视频下载。复制播放页链接即可。

### 支持的平台

- 🎬 **B站** — 解析 playinfo，下载 m4s 音视频并合并
- 🎵 **抖音** — 直接下载 mp4
- 📺 **腾讯视频** — M3U8 分段下载
- 🎥 **爱奇艺** — DASH API → M3U8 下载
- 🎞 **优酷** — yt-dlp 解析下载
- ▶ **YouTube** — yt-dlp 下载

### VIP 视频免费播放

粘贴视频链接，选择线路后点击“解析播放”。默认使用虾米解析，也可切换备用线路。输入片名可使用“官网打开 / 搜索”。第三方线路能否播放以实际结果为准。

### 安装

Windows 用户双击根目录的 **start.bat** 即可启动。脚本自动查找项目虚拟环境、已登记的 Conda 环境（优先 `mv`）及系统 Python，检查依赖后启动窗口，无需手动激活环境。首次使用仍需安装下列依赖。

运行 `start.bat --check` 可仅检查环境；启动日志保存在 `%LOCALAPPDATA%\BlilBlil\logs`。脚本不会自动安装依赖或修改系统环境。

```bash
pip install -r requirements.txt
python main.py
```

下载工具需单独准备（不随源码提交）：

- 将 FFmpeg 放到 `ffmpeg/ffmpeg.exe`，或在 `config.json` 中设置 `ffmpeg_path`。
- 腾讯 / 爱奇艺高速下载使用 [N_m3u8DL-RE](https://github.com/nilaoda/N_m3u8DL-RE/releases)。将 Windows x64 程序放到 `tools/N_m3u8DL-RE/N_m3u8DL-RE.exe`，或设置 `n_m3u8dl_path`。本地使用版本见该目录的 `VERSION.txt`。

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
- 🎞 **Youku** — yt-dlp download
- ▶ **YouTube** — yt-dlp download

### Video playback

Paste a video URL and choose a route to play. XMFLV is the default, with an alternative route available. Use the official-site button to open the original page or search Tencent Video by title. Playback availability depends on the provider. Downloads support non-VIP videos only.

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
