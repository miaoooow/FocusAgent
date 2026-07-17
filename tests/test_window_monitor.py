import os
import unittest

from focus_agent.window_monitor import get_foreground_snapshot


@unittest.skipUnless(os.name == "nt", "Win32-only monitor")
class WindowMonitorTests(unittest.TestCase):
    def test_foreground_snapshot_is_readable(self):
        snapshot = get_foreground_snapshot()
        self.assertIsInstance(snapshot.hwnd, int)
        self.assertIsInstance(snapshot.pid, int)
        self.assertGreaterEqual(snapshot.input_idle_seconds, 0)


if __name__ == "__main__":
    unittest.main()
