import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PublicEditionTests(unittest.TestCase):
    def test_browser_extension_contains_only_runtime_files(self):
        folder = ROOT / "browser_extension_standalone"
        self.assertEqual(
            {item.name for item in folder.iterdir() if item.is_file()},
            {"manifest.json", "background.js", "popup.html", "popup.css", "popup.js"},
        )
        manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["manifest_version"], 3)
        self.assertEqual(manifest["version"], "3.1.0")
        self.assertEqual(
            set(manifest["permissions"]),
            {"storage", "tabs", "alarms", "notifications"},
        )
        self.assertNotIn("host_permissions", manifest)

    def test_web_edition_contains_only_runtime_files(self):
        folder = ROOT / "web_standalone"
        self.assertEqual(
            {item.name for item in folder.iterdir() if item.is_file()},
            {"index.html", "styles.css", "app.js", "manifest.webmanifest", "sw.js"},
        )
        manifest = json.loads((folder / "manifest.webmanifest").read_text(encoding="utf-8"))
        self.assertEqual(manifest["display"], "standalone")
        self.assertEqual(manifest["start_url"], "./")
        self.assertIn("只判断你是否离开当前页面", (folder / "index.html").read_text(encoding="utf-8"))

    def test_readme_explains_three_editions_and_attribution(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for phrase in ("Windows 安装版", "浏览器扩展版", "网页版", "项目文件结构"):
            self.assertIn(phrase, readme)
        self.assertIn("YouTube 博主 **mocha.**", readme)
        self.assertIn("声音花园", readme)
        self.assertNotIn(r"D:\Agent", readme)
        self.assertNotIn("设计说明书.docx", readme)

    def test_pages_workflow_deploys_only_web_edition(self):
        workflow = (ROOT / ".github" / "workflows" / "pages.yml").read_text(encoding="utf-8")
        self.assertIn("path: web_standalone", workflow)
        self.assertNotIn("path: .", workflow)


if __name__ == "__main__":
    unittest.main()
