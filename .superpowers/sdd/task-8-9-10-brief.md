# Task 8+9+10: YouTube, CCTV, Generic M3U8 platforms

**Goal:** Create platform downloaders for YouTube, CCTV, and Generic M3U8.

Read code from plan at `D:\python\mv\BlilBlil\docs\superpowers\plans\2026-07-25-blilblil-implementation.md`:

- **YouTube**: Search "class YouTube(BaseDownloader)" — copy class + imports
- **CCTV**: Search "class CCTV(BaseDownloader)" — copy class + imports  
- **M3U8Generic**: Search "class M3U8Generic(BaseDownloader)" — copy class + imports

IMPORTANT: `M3U8Generic` must import `merge_ts` from `core.utils`, NOT define it locally.

Create:
- `platforms/youtube.py`
- `platforms/cctv.py`
- `platforms/m3u8_generic.py`

Test:
```powershell
cd D:\python\mv\BlilBlil
C:\Users\Lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -c "from platforms.youtube import YouTube; from platforms.cctv import CCTV; from platforms.m3u8_generic import M3U8Generic; from platforms import discover_platforms; plats = discover_platforms(); print(f'{len(plats)} platforms: {[p.name for p in plats]}')"
```

Expected: `8 platforms: ['B站', '抖音', '腾讯视频', '爱奇艺', '优酷', 'YouTube', 'CCTV', 'M3U8']`

Report to `task-8-9-10-report.md`.
