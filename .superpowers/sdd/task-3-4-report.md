# Task 3+4 Report

## Status: DONE

- Created `platforms/bilibili.py` — Bilibili(BaseDownloader)
- Created `platforms/douyin.py` — Douyin(BaseDownloader)

## Verification

```
> from platforms.bilibili import Bilibili; print(f'{Bilibili.icon} {Bilibili.name} OK')
🎬 B站 OK

> from platforms.douyin import Douyin; print(f'{Douyin.icon} {Douyin.name} OK')
🎵 抖音 OK

> from platforms import discover_platforms; plats = discover_platforms(); print(f'{len(plats)} platforms: {[p.name for p in plats]}')
2 platforms: ['B站', '抖音']
```
