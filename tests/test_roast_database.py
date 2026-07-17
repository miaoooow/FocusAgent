import json
import unittest
from pathlib import Path

from focus_agent.contracts import sanitize_roast_response
from focus_agent.roast_database import RoastDatabase


ROOT = Path(__file__).resolve().parent.parent


class RoastDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.database_path = ROOT / ".runtime" / "test_roasts.sqlite3"
        self.database_path.parent.mkdir(exist_ok=True)
        self._remove_database_files()
        self.database = RoastDatabase(self.database_path)

    def tearDown(self):
        self._remove_database_files()

    def _remove_database_files(self):
        for path in (
            self.database_path,
            Path(f"{self.database_path}-wal"),
            Path(f"{self.database_path}-shm"),
        ):
            path.unlink(missing_ok=True)

    def test_seed_library_has_64_safe_humorous_lines(self):
        payload = json.loads((ROOT / "data" / "roast_lines.json").read_text(encoding="utf-8"))
        lines = [
            line
            for category in payload["categories"].values()
            for intensity in category["lines"].values()
            for line in intensity
        ]
        self.assertEqual(len(lines), 64)
        self.assertTrue(all(sanitize_roast_response(line) for line in lines))

    def test_current_page_is_classified_before_copy_is_selected(self):
        self.assertEqual(self.database.classify_target("Bilibili 视频页面"), "video")
        self.assertEqual(self.database.classify_target("淘宝购物车"), "shopping")
        self.assertEqual(self.database.classify_target("微信聊天"), "chat")
        video_lines = {self.database.pick("YouTube", "mild") for _ in range(4)}
        seed = json.loads((ROOT / "data" / "roast_lines.json").read_text(encoding="utf-8"))
        self.assertEqual(video_lines, set(seed["categories"]["video"]["lines"]["mild"]))

    def test_model_copy_can_be_learned_without_replacing_curated_copy(self):
        before = self.database.stats()
        self.database.add_generated("视频很忙，目标很凉", "Bilibili", "mild")
        after = self.database.stats()
        self.assertEqual(after["line_count"], before["line_count"] + 1)
        self.assertEqual(after["generated_count"], 1)
        self.database.pick("Bilibili", "mild")
        self.assertGreater(self.database.stats()["used_count"], 0)


if __name__ == "__main__":
    unittest.main()
