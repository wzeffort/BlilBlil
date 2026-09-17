# BlilBlil — Multi-Platform Video Downloader

[中文](#中文) | [English](#english)

---

## 中文
<img width="1102" height="712" alt="image" src="https://github.com/user-attachments/assets/0ad75291-8187-4337-b47a-7c6a8e10ccf3" />

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

```bash
pip install -r requirements.txt
python main.py
```

下载工具需单独准备（不随源码提交）：

- 将 FFmpeg 和 FFprobe 分别放到 `ffmpeg/ffmpeg.exe`、`ffmpeg/ffprobe.exe`，或在 `config.json` 中设置 `ffmpeg_path`；FFprobe 必须与 FFmpeg 在同一目录。
- 腾讯 / 爱奇艺高速下载使用 [N_m3u8DL-RE](https://github.com/nilaoda/N_m3u8DL-RE/releases)。将 Windows x64 程序放到 `tools/N_m3u8DL-RE/N_m3u8DL-RE.exe`，或设置 `n_m3u8dl_path`。本地使用版本见该目录的 `VERSION.txt`。

Windows 用户也可以创建独立环境后双击 `启动.bat`：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

启动脚本将日志、临时文件和浏览器驱动缓存保存在项目目录。更新代码后，请先等正在执行的任务完成，再关闭旧窗口并重新启动。

### 并行下载与播放兼容性

- 可以在不同平台标签中分别发起下载，底部任务表独立展示各平台进度和状态。切换标签、停止或完成一个任务，不会暂停其他平台的任务。每个平台同时运行一个任务；“每任务线程”控制该任务的分片并发数。并行任务共享本机带宽和处理器资源。
- 下载完成后先检查视频轨道。已兼容的 MP4 / H.264 / AAC 直接保留，不重新压缩；其他编码按需处理为 Windows 自带播放器通用兼容格式。只需处理音频时保留视频编码，仅需改封装时直接复制音视频。
- 转换结果通过音视频格式和时长检查、成功落盘后，清理转换前文件，不再生成 `_originals`；失败或取消时保留原件。缺失的视频画面不能靠转码补出，只有音频的文件不会报告视频下载成功。
- YouTube 合并后清理分轨、分片，不额外保存封面、字幕或信息文件；兼容处理完成后只保留一个成品。过程中出现临时文件是正常的，请等任务完成后再播放。

回归测试：`python -m unittest discover -s tests`。音视频集成测试需要 FFmpeg / FFprobe；界面测试需要可用的桌面环境。本地慢速 HTTP 测试覆盖双任务同时传输，以及单项完成、取消或失败时另一项继续运行，不依赖视频网站的实时线路。

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

Place FFmpeg and FFprobe together in `ffmpeg/`, or configure `ffmpeg_path` with FFprobe alongside it. On Windows, create `.venv`, install the requirements there, then use `启动.bat` to launch with project-local logs and caches.

Downloads from different platform tabs run independently, with separate status and progress rows. Completed downloads are checked for video and prepared as MP4/H.264/AAC when needed; already compatible files are not reencoded. Successful conversion removes the superseded source, while failure or cancellation preserves it. YouTube removes intermediate streams after merging and keeps only the final playable file on success.

### Package

```bash
pip install pyinstaller
pyinstaller --onefile --add-data "assets/ffmpeg;assets/ffmpeg" main.py
```

## License

Apache 2.0
