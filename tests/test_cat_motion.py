import struct
import unittest
from pathlib import Path

from focus_agent.controller import NativeAlert


ROOT = Path(__file__).resolve().parent.parent
STORY_SKIN_ROOT = ROOT / "assets" / "cat-story-skins"


def png_header(path: Path) -> tuple[int, int, int]:
    data = path.read_bytes()[:29]
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise AssertionError(f"not a PNG: {path}")
    width, height = struct.unpack(">II", data[16:24])
    color_type = data[25]
    return width, height, color_type


class CatMotionAssetTests(unittest.TestCase):
    def test_storybook_skins_have_matching_young_and_adult_forms(self):
        for skin in ("orange", "tuxedo", "ragdoll"):
            for age in ("young", "adult"):
                width, height, color_type = png_header(
                    STORY_SKIN_ROOT / f"{skin}-{age}-v2.png"
                )
                self.assertEqual((width, height, color_type), (560, 340, 6))
        provenance = (STORY_SKIN_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("original AI-generated project assets", provenance)

    def test_only_current_storybook_assets_are_kept(self):
        png_names = sorted(path.name for path in STORY_SKIN_ROOT.glob("*.png"))
        self.assertEqual(
            png_names,
            [
                "orange-adult-v2.png",
                "orange-young-v2.png",
                "ragdoll-adult-v2.png",
                "ragdoll-young-v2.png",
                "tuxedo-adult-v2.png",
                "tuxedo-young-v2.png",
            ],
        )

    def test_alert_count_selects_a_repeat_visitor_mood(self):
        alert = NativeAlert("回来看看", "测试页面", 9, 1200, 3)
        self.assertEqual(alert.alert_count, 3)


if __name__ == "__main__":
    unittest.main()
