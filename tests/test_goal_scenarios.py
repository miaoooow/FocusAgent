import unittest
from pathlib import Path

from focus_agent.contracts import TargetRule
from focus_agent.goal_scenarios import GoalScenarioStore
from focus_agent.recommendations import recommend_targets


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RUNTIME_ROOT = PROJECT_ROOT / ".runtime"


class GoalScenarioTests(unittest.TestCase):
    memory_path = RUNTIME_ROOT / "test_goal_scenario_memory.json"

    def setUp(self):
        RUNTIME_ROOT.mkdir(exist_ok=True)
        self.memory_path.unlink(missing_ok=True)
        self.memory_path.with_suffix(".tmp").unlink(missing_ok=True)
        self.store = GoalScenarioStore(
            PROJECT_ROOT / "data" / "goal_scenarios.json",
            self.memory_path,
        )

    def tearDown(self):
        self.memory_path.unlink(missing_ok=True)
        self.memory_path.with_suffix(".tmp").unlink(missing_ok=True)

    def values(self, goal: str) -> set[str]:
        return {item.value.casefold() for item in recommend_targets(goal, self.store)}

    def test_typical_goals_map_to_practical_local_tools(self):
        cases = (
            ("50分钟完成Python爬虫项目", {"code.exe", "windowsterminal.exe", "explorer.exe"}),
            ("40分钟完成课程实验报告", {"winword.exe", "wps.exe", "explorer.exe"}),
            ("30分钟制作答辩PPT", {"powerpnt.exe", "wpp.exe", "explorer.exe"}),
            ("25分钟整理Excel数据透视表", {"excel.exe", "et.exe", "explorer.exe"}),
            ("45分钟整理Obsidian课程笔记", {"obsidian.exe", "onenote.exe", "explorer.exe"}),
            ("60分钟剪辑课程视频", {"adobe premiere pro.exe", "jianyingpro.exe", "explorer.exe"}),
            ("30分钟参加腾讯会议", {"wemeetapp.exe", "zoom.exe", "ms-teams.exe"}),
        )
        for goal, expected in cases:
            with self.subTest(goal=goal):
                self.assertTrue(expected.issubset(self.values(goal)))

    def test_user_confirmed_similar_goal_is_reused_locally(self):
        confirmed = (
            TargetRule("process", "PyCharm64.exe", "exact"),
            TargetRule("process", "explorer.exe", "exact"),
        )
        self.store.learn("45分钟完成Python课程作业", confirmed)
        reloaded = GoalScenarioStore(
            PROJECT_ROOT / "data" / "goal_scenarios.json",
            self.memory_path,
        )
        values = {
            item.value.casefold()
            for item in recommend_targets("继续完成Python课程作业", reloaded)
        }
        self.assertIn("pycharm64.exe", values)

    def test_database_is_local_and_explainable(self):
        matches = self.store.match("制作毕业答辩PPT")
        self.assertEqual(matches[0].scenario_id, "presentation")
        self.assertGreaterEqual(self.store.stats()["scenarios"], 12)


if __name__ == "__main__":
    unittest.main()
