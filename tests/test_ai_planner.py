import json
import unittest

from focus_agent.ai_planner import parse_ai_planning_result
from focus_agent.ollama_client import OllamaStatus
from focus_agent.services import SessionParserService


def ai_payload(**changes) -> str:
    payload = {
        "duration_minutes": 50,
        "mode": "whitelist",
        "scene_ids": ["coding"],
        "explicit_targets": [],
        "reason": "需要编写代码、管理项目文件并运行测试",
    }
    payload.update(changes)
    return json.dumps(payload, ensure_ascii=False)


class OnlineAIClient:
    def __init__(self, response: str):
        self.response = response
        self.calls = 0
        self.kwargs = {}

    def status(self):
        return OllamaStatus(True, ("qwen3.5:9b",))

    def chat(self, **kwargs):
        self.calls += 1
        self.kwargs = kwargs
        return self.response


class OfflineAIClient:
    def __init__(self):
        self.calls = 0

    def status(self):
        return OllamaStatus(False, error="offline")

    def chat(self, **kwargs):
        self.calls += 1
        raise AssertionError("offline planner must not call chat")


class AIPlannerContractTests(unittest.TestCase):
    valid_ids = {"coding", "writing", "presentation"}

    def test_valid_scene_plan_is_parsed(self):
        result = parse_ai_planning_result(
            ai_payload(),
            goal="50分钟完成Python接口并测试",
            valid_scene_ids=self.valid_ids,
        )
        self.assertEqual(result.scene_ids, ("coding",))
        self.assertEqual(result.duration_minutes, 50)

    def test_unknown_scene_or_ungrounded_software_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_ai_planning_result(
                ai_payload(scene_ids=["gaming"]),
                goal="完成课程作业",
                valid_scene_ids=self.valid_ids,
            )
        with self.assertRaises(ValueError):
            parse_ai_planning_result(
                ai_payload(
                    explicit_targets=[
                        {"kind": "process", "value": "WeChat.exe", "match": "exact"}
                    ]
                ),
                goal="完成Python接口",
                valid_scene_ids=self.valid_ids,
            )

    def test_explicit_named_software_is_allowed_but_not_invented(self):
        result = parse_ai_planning_result(
            ai_payload(
                explicit_targets=[
                    {"kind": "process", "value": "PyCharm64.exe", "match": "exact"}
                ]
            ),
            goal="用PyCharm完成Python接口",
            valid_scene_ids=self.valid_ids,
        )
        self.assertEqual(result.explicit_targets[0].value, "PyCharm64.exe")

    def test_blacklist_ignores_invalid_scene_hint_and_normalizes_bilibili(self):
        result = parse_ai_planning_result(
            ai_payload(
                mode="blacklist",
                scene_ids=[0],
                explicit_targets=[
                    {"kind": "window_title", "value": "bilibili.com", "match": "contains"}
                ],
            ),
            goal="25分钟修改简历，禁止刷B站",
            valid_scene_ids=self.valid_ids,
        )
        self.assertEqual(result.scene_ids, ())
        self.assertEqual(result.explicit_targets[0].value, "哔哩哔哩")


class AIPlannerServiceTests(unittest.TestCase):
    def test_general_ai_planning_calls_ollama_and_merges_curated_targets(self):
        client = OnlineAIClient(ai_payload())
        plan = SessionParserService(client).plan_goal("50分钟完成Python接口并测试")
        values = {item.value.casefold() for item in plan.config.allowed_targets}
        self.assertTrue(plan.ai_used)
        self.assertEqual(client.calls, 1)
        self.assertIn("code.exe", values)
        self.assertIn("explorer.exe", values)
        self.assertEqual(client.kwargs["timeout_seconds"], 60.0)
        self.assertIn("本机AI", plan.source)

    def test_offline_or_invalid_ai_falls_back_without_blocking_core(self):
        offline = OfflineAIClient()
        fallback = SessionParserService(offline).plan_goal("完成高数作业第三章")
        self.assertFalse(fallback.ai_used)
        self.assertTrue(fallback.fallback_reason)
        self.assertIn("AI回退", fallback.source)
        self.assertEqual(offline.calls, 0)

        local_blacklist = SessionParserService(offline).plan_goal("25分钟禁止刷B站")
        self.assertEqual(local_blacklist.config.mode, "blacklist")
        self.assertEqual(local_blacklist.config.blocked_targets[0].value, "哔哩哔哩")

        invalid = OnlineAIClient("not-json")
        recovered = SessionParserService(invalid).plan_goal("完成Python编程任务")
        self.assertFalse(recovered.ai_used)
        self.assertIn("code.exe", {item.value.casefold() for item in recovered.config.allowed_targets})

    def test_ai_switch_off_never_touches_ollama(self):
        client = OfflineAIClient()
        plan = SessionParserService(client).plan_goal("完成周报", use_ai=False)
        self.assertFalse(plan.ai_used)
        self.assertEqual(client.calls, 0)
        self.assertEqual(plan.source, "本地场景库 · 即时规划")


if __name__ == "__main__":
    unittest.main()
