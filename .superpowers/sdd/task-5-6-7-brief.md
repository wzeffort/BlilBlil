# Task 5+6+7: Tencent Video, iQiyi, Youku platforms

**Goal:** Create platform downloaders for Tencent Video, iQiyi, and Youku.

Read the complete code from the plan file at `D:\python\mv\BlilBlil\docs\superpowers\plans\2026-07-25-blilblil-implementation.md`:

- **Tencent**: Search "class Tencent(BaseDownloader)" in the plan, copy the class and its imports
- **iQiyi**: Search "class IQiyi(BaseDownloader)" in the plan, copy the class and its imports  
- **Youku**: Search "class Youku(BaseDownloader)" in the plan, copy the class and its imports

IMPORTANT: These classes use `merge_ts` which is imported from `core.utils`. Do NOT define `merge_ts` locally — import it:
```python
from core.utils import ..., merge_ts
```

Create:
- `platforms/tencent.py`
- `platforms/iqiyi.py`  
- `platforms/youku.py`

Test:
```powershell
cd D:\python\mv\BlilBlil
C:\Users\Lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe -c "from platforms.tencent import Tencent; from platforms.iqiyi import IQiyi; from platforms.youku import Youku; print('all OK')"
```

Report to `task-5-6-7-report.md`.
