import unittest
from unittest.mock import patch

from core.browser import _make_driver


class BackgroundBrowserTests(unittest.TestCase):
    def test_background_browser_starts_headless_and_muted(self):
        with patch("core.browser.webdriver.Chrome") as chrome:
            _make_driver(performance_logging=True)
        arguments = chrome.call_args.kwargs["options"].arguments
        self.assertIn("--headless=new", arguments)
        self.assertIn("--mute-audio", arguments)
