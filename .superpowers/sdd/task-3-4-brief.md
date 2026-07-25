# Task 3+4: Bilibili + Douyin platforms

**Goal:** Create platform/ downloaders for Bilibili and Douyin.

Depends on: Task 1 (BaseDownloader, utils).

Read the complete code from `D:\python\mv\BlilBlil\docs\superpowers\plans\2026-07-25-blilblil-implementation.md`:
- **Task 3: Bilibili platform** → Search "class Bilibili(BaseDownloader)" — copy the entire Bilibili class
- **Task 4: Douyin platform** → Search "class Douyin(BaseDownloader)" — copy the entire Douyin class

Create:
- `D:\python\mv\BlilBlil\platforms\bilibili.py`
- `D:\python\mv\BlilBlil\platforms\douyin.py`

Test:
```powershell
cd D:\python\mv\BlilBlil
python -c "from platforms.bilibili import Bilibili; print(f'{Bilibili.icon} {Bilibili.name} OK')"
python -c "from platforms.douyin import Douyin; print(f'{Douyin.icon} {Douyin.name} OK')"
python -c "from platforms import discover_platforms; plats = discover_platforms(); print(f'{len(plats)} platforms: {[p.name for p in plats]}')"
```

Report to `D:\python\mv\BlilBlil\.superpowers\sdd\task-3-4-report.md`.
