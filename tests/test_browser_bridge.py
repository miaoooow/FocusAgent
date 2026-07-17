import time
import unittest

from focus_agent.browser_bridge import BrowserBridge
from focus_agent.window_monitor import ForegroundSnapshot


class BrowserBridgeTests(unittest.TestCase):
    def setUp(self):
        self.bridge = BrowserBridge()
        self.browser = ForegroundSnapshot(1, 2, "msedge.exe", "旧标题", 0.1)

    def test_fresh_active_domain_enriches_only_the_matching_browser(self):
        status = self.bridge.report(
            {"process_name": "msedge.exe", "domain": "www.bilibili.com", "title": "视频"}
        )
        self.assertTrue(status["connected"])
        enriched = self.bridge.enrich(self.browser)
        self.assertEqual(enriched.browser_domain, "bilibili.com")
        chrome = ForegroundSnapshot(1, 3, "chrome.exe", "别的浏览器", 0.1)
        self.assertEqual(self.bridge.enrich(chrome).browser_domain, "")

    def test_stale_domain_is_not_reused_for_a_later_page(self):
        self.bridge.report(
            {"process_name": "msedge.exe", "domain": "example.com", "title": "Example"}
        )
        stale = self.bridge.enrich(self.browser, now=time.monotonic() + 10)
        self.assertEqual(stale.browser_domain, "")
        self.assertFalse(self.bridge.status(now=time.monotonic() + 10)["connected"])

    def test_invalid_or_non_browser_reports_are_rejected(self):
        with self.assertRaises(ValueError):
            self.bridge.report({"process_name": "code.exe", "domain": "example.com"})
        with self.assertRaises(ValueError):
            self.bridge.report({"process_name": "msedge.exe", "domain": "not a domain"})


if __name__ == "__main__":
    unittest.main()
