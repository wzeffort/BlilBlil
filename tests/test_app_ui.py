import tkinter as tk
import unittest

import platforms
from main import BlilBlilApp
from platforms.cctv import CCTV
from platforms.iqiyi import IQiyi
from platforms.tencent import Tencent
from platforms.youtube import YouTube
from platforms.youku import Youku
from platforms.bilibili import Bilibili


class AppLayoutTests(unittest.TestCase):
    def setUp(self):
        platforms._platforms.clear()
        self.app = BlilBlilApp()
        self.app.root.geometry("1100x680+2000+2000")
        self.app.root.update()

    def tearDown(self):
        self.app.root.destroy()
        platforms._platforms.clear()

    def test_task_progress_is_visible_at_normal_window_size(self):
        root_height = self.app.root.winfo_height()
        progress_bottom = (
            self.app.tasks.winfo_rooty()
            - self.app.root.winfo_rooty()
            + self.app.tasks.winfo_height()
        )

        self.assertTrue(self.app.tasks.winfo_ismapped())
        self.assertLessEqual(progress_bottom, root_height)

    def test_each_platform_has_its_own_progress_and_status(self):
        iqiyi, tencent = IQiyi(), Tencent()
        self.app.update_download_task(iqiyi, active=True, status="下载中", progress="25.0%")
        self.app.update_download_task(tencent, active=True, status="准备下载...", progress="—")
        self.app.update_download_task(tencent, active=False, status="完成", progress="100.0%")
        self.assertEqual("25.0%", self.app.tasks.set(str(id(iqiyi)), "progress"))
        self.assertEqual("下载中", self.app.tasks.set(str(id(iqiyi)), "status"))
        self.assertIn("active", self.app.tasks.item(str(id(iqiyi)), "tags"))

    def test_m3u8_download_tab_is_not_present(self):
        tab_titles = [
            self.app.notebook.tab(tab_id, "text")
            for tab_id in self.app.notebook.tabs()
        ]

        self.assertFalse(any("M3U8" in title for title in tab_titles))


class PlatformStatusTests(unittest.TestCase):
    def test_non_bilibili_and_non_douyin_tabs_expose_execution_status(self):
        root = tk.Tk()
        root.geometry("900x550+2000+2000")
        try:
            for downloader_class in (CCTV, IQiyi, Tencent, Youku, YouTube):
                downloader = downloader_class()
                tab = downloader.create_tab(root)
                status_var = getattr(downloader, "status_var", None)
                self.assertIsNotNone(status_var, downloader_class.__name__)
                self.assertEqual(
                    "就绪",
                    status_var.get(),
                    downloader_class.__name__,
                )
                tab.destroy()
        finally:
            root.destroy()

    def test_updated_download_tabs_have_download_and_stop_controls(self):
        root = tk.Tk()
        root.geometry("900x550+2000+2000")
        try:
            for downloader_class in (
                Bilibili,
                CCTV,
                IQiyi,
                Tencent,
                Youku,
                YouTube,
            ):
                downloader = downloader_class()
                tab = downloader.create_tab(root)
                buttons = []
                pending = [tab]
                while pending:
                    widget = pending.pop()
                    pending.extend(widget.winfo_children())
                    if widget.winfo_class() == "TButton":
                        buttons.append(widget.cget("text"))
                self.assertIn("下载", buttons, downloader_class.__name__)
                self.assertIn("停止下载", buttons, downloader_class.__name__)
                tab.destroy()
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
