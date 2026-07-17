import unittest

from focus_agent.recommendations import (
    fallback_config_for_goal,
    group_targets_by_scene,
    infer_duration_minutes,
    recommend_targets,
)


class RecommendationTests(unittest.TestCase):
    def test_coding_goal_recommends_editor_and_terminal(self):
        targets = recommend_targets("完成 Python 编程任务并跑通测试")
        values = {item.value.casefold() for item in targets}
        self.assertIn("code.exe", values)
        self.assertIn("windowsterminal.exe", values)

    def test_math_homework_does_not_invent_course_platforms(self):
        targets = recommend_targets("完成今天的高数作业第三章")
        values = {item.value for item in targets}
        self.assertIn("高数", values)
        self.assertIn("AcroRd32.exe", values)
        self.assertNotIn("学习通", values)
        self.assertNotIn("雨课堂", values)
        self.assertNotIn("WINWORD.EXE", values)

    def test_presentation_does_not_expand_into_writing_stack(self):
        targets = recommend_targets("完成汇报PPT初稿")
        values = {item.value.casefold() for item in targets}
        self.assertIn("powerpnt.exe", values)
        self.assertNotIn("winword.exe", values)
        self.assertNotIn("语雀", values)

    def test_course_platform_is_only_added_when_named(self):
        targets = recommend_targets("在学习通完成英语作业")
        values = {item.value for item in targets}
        self.assertIn("学习通", values)

    def test_coding_docs_are_only_added_when_requested(self):
        basic = {item.value for item in recommend_targets("完成Python编程任务")}
        research = {item.value for item in recommend_targets("完成Python任务并查官方文档")}
        self.assertNotIn("官方文档", basic)
        self.assertIn("官方文档", research)

    def test_unknown_goal_still_has_editable_recommendations(self):
        self.assertTrue(recommend_targets("整理明天要用的材料"))

    def test_explicit_app_name_is_kept_in_recommendations(self):
        targets = recommend_targets("用 MATLAB 完成第三章计算题")
        self.assertEqual(targets[0].value, "MATLAB")

    def test_targets_are_grouped_into_explainable_scenes(self):
        targets = recommend_targets("完成 Python 编程任务并跑通测试")
        scenes = group_targets_by_scene("完成 Python 编程任务并跑通测试", targets)
        names = [scene.name for scene in scenes]
        self.assertEqual(names, ["主任务", "运行与验证", "协作与素材"])
        self.assertEqual(scenes[0].targets[0].value, "Code.exe")

    def test_duration_is_inferred_from_minutes_and_hours(self):
        self.assertEqual(infer_duration_minutes("专注 25 分钟"), 25)
        self.assertEqual(infer_duration_minutes("做 1.5 小时"), 90)

    def test_blackout_goal_needs_no_targets_or_clarification(self):
        config = fallback_config_for_goal("接下来30分钟完全不碰电脑")
        self.assertEqual(config.mode, "blackout")
        self.assertEqual(config.duration_minutes, 30)
        self.assertFalse(config.allowed_targets)
        self.assertFalse(config.needs_clarification)

    def test_explicit_distraction_goal_builds_a_local_blacklist(self):
        config = fallback_config_for_goal("25分钟修改简历，禁止刷B站和微博")
        self.assertEqual(config.mode, "blacklist")
        self.assertEqual(
            {item.value for item in config.blocked_targets},
            {"哔哩哔哩", "微博"},
        )
        self.assertFalse(config.allowed_targets)


if __name__ == "__main__":
    unittest.main()
