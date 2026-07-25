# Task 2: Main window GUI + VIP parser

**Goal:** Create the main Tkinter application window and the VIP video parser panel.

**Depends on:** Task 1 (core/downloader.py, core/config.py, platforms/discover_platforms)

## Files to Create

### 1. `tools/vip_parser.py`

VIP parser panel class `VIPParserPanel(ttk.Frame)` with bilingual support.

### 2. `main.py`

Main application entry point with `BlilBlilApp` class.

## Implementation Details

Read the complete code for both files from the plan at `D:\python\mv\BlilBlil\docs\superpowers\plans\2026-07-25-blilblil-implementation.md`:

- **vip_parser.py**: Look for the section "Step 1: Write tools/vip_parser.py — VIP player panel" in **Task 2**. Copy the entire VIPParserPanel class code exactly.
- **main.py**: Look for "Step 2: Write main.py — main window with platform tabs" in **Task 2**. Copy the entire BlilBlilApp class code exactly. Also include the "Step 3" log color tags addition.

## Interface Contract

- `BlilBlilApp` must have `get_config()` method returning Config instance
- Platform instances get `instance.app = self` set in _build_main_area
- `VIPParserPanel.__init__(self, parent, lang="zh")` - parent is a ttk.Frame

## Test

After creating both files:
```powershell
python -c "from tools.vip_parser import VIPParserPanel; print('vip OK')"
python -c "import main; print('import OK')"
```

## Report

Write to `D:\python\mv\BlilBlil\.superpowers\sdd\task-2-report.md`:
- Files created
- Test results
- Any issues
