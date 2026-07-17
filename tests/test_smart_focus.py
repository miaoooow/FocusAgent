import os
import unittest
from dataclasses import replace
from pathlib import Path

from focus_agent.contracts import TargetRule
from focus_agent.controller import FocusController
from focus_agent.penalties import penalty_snapshot
from focus_agent.profile_store import FocusProfileStore
from focus_agent.recommendations import fallback_config_for_goal
from focus_agent.software_relations import SoftwareRelationStore
from focus_agent.window_monitor import ForegroundSnapshot


PROJECT_ROOT = Path(__file__).resolve().parent.parent
RUNTIME_ROOT = PROJECT_ROOT / ".runtime"


class RuntimeFileMixin:
    runtime_files: tuple[Path, ...] = ()

    def setUp(self):
        RUNTIME_ROOT.mkdir(exist_ok=True)
        self._cleanup_runtime_files()

    def tearDown(self):
        self._cleanup_runtime_files()

    def _cleanup_runtime_files(self):
        for path in self.runtime_files:
            path.unlink(missing_ok=True)
            path.with_suffix(".tmp").unlink(missing_ok=True)


class SmartRelationTests(RuntimeFileMixin, unittest.TestCase):
    learned_path = RUNTIME_ROOT / "test_learned_relations.json"
    runtime_files = (learned_path,)

    def _store(self) -> SoftwareRelationStore:
        return SoftwareRelationStore(
            database_path=PROJECT_ROOT / "data" / "software_relations.json",
            learned_path=self.learned_path,
        )

    def test_vscode_file_explorer_is_suggested_with_soft_grace(self):
        store = self._store()
        config = fallback_config_for_goal("完成Python编程任务")
        snapshot = ForegroundSnapshot(1, 123, "explorer.exe", "我的项目", 0)
        suggestion = store.suggest(config.allowed_targets, snapshot)
        self.assertIsNotNone(suggestion)
        self.assertEqual(suggestion.label, "文件资源管理器")
        self.assertGreaterEqual(suggestion.soft_grace_seconds, 60)

    def test_browser_relation_requires_a_relevant_title(self):
        store = self._store()
        config = fallback_config_for_goal("完成Python编程任务")
        unrelated = ForegroundSnapshot(1, 123, "chrome.exe", "视频网站", 0)
        related = ForegroundSnapshot(1, 123, "chrome.exe", "Python Documentation", 0)
        self.assertIsNone(store.suggest(config.allowed_targets, unrelated))
        self.assertIsNotNone(store.suggest(config.allowed_targets, related))

    def test_confirmed_relation_is_persisted_locally(self):
        store = self._store()
        config = fallback_config_for_goal("完成Python编程任务")
        snapshot = ForegroundSnapshot(1, 123, "explorer.exe", "项目文件", 0)
        suggestion = store.suggest(config.allowed_targets, snapshot)
        store.remember(suggestion)
        reloaded = self._store()
        self.assertTrue(reloaded.is_remembered(suggestion))

    def test_native_suggestion_waits_before_asking(self):
        controller = object.__new__(FocusController)
        controller.relations = self._store()
        controller.dynamic_allowed = set()
        controller.dismissed_suggestions = set()
        controller.suggestions = {}
        controller.notified_suggestions = set()
        controller.soft_until = {}
        config = replace(
            fallback_config_for_goal("完成Python编程任务"),
            allowed_targets=(TargetRule("process", "Code.exe", "exact"),),
        )
        snapshot = ForegroundSnapshot(1, 123, "explorer.exe", "项目文件", 0)
        effective, _, first = controller._related_snapshot(config, snapshot, now=100)
        self.assertEqual(effective.pid, os.getpid())
        self.assertIsNone(first)
        _, _, later = controller._related_snapshot(config, snapshot, now=104.1)
        self.assertIsNotNone(later)


class ProfileStoreTests(RuntimeFileMixin, unittest.TestCase):
    profile_path = RUNTIME_ROOT / "test_focus_profile.json"
    runtime_files = (profile_path,)

    def test_new_cat_is_named_luna_by_default(self):
        snapshot = FocusProfileStore(self.profile_path).snapshot()
        self.assertEqual(snapshot["cat_name"], "Luna")
        self.assertEqual(snapshot["pet"]["name"], "Luna")

    def test_rewards_badges_and_abort_penalty_persist(self):
        store = FocusProfileStore(self.profile_path)
        reward = store.record_completion(25, 0, "写完作业")
        self.assertEqual(reward["xp"], 70)
        self.assertEqual(reward["coins"], 8)
        store.record_aborted(3, "提前结束")
        snapshot = FocusProfileStore(self.profile_path).snapshot()
        self.assertEqual(snapshot["completed_sessions"], 1)
        self.assertEqual(snapshot["clean_sessions"], 1)
        self.assertEqual(snapshot["aborted_sessions"], 1)
        self.assertTrue(snapshot["badges"][0]["unlocked"])
        self.assertEqual(len(snapshot["weekly_minutes"]), 7)

    def test_owner_can_name_the_cat_and_the_name_persists(self):
        store = FocusProfileStore(self.profile_path)
        snapshot = store.rename_cat("饭团")
        self.assertEqual(snapshot["pet"]["name"], "饭团")
        self.assertEqual(FocusProfileStore(self.profile_path).snapshot()["cat_name"], "饭团")
        with self.assertRaises(ValueError):
            store.rename_cat("   ")
        with self.assertRaises(ValueError):
            store.rename_cat("这是一只名字实在太长太长的小猫")

    def test_owner_can_choose_a_cat_skin_without_losing_its_name(self):
        store = FocusProfileStore(self.profile_path)
        store.rename_cat("饭团")
        snapshot = store.set_cat_skin("ragdoll")
        self.assertEqual(snapshot["pet"]["skin"], "ragdoll")
        self.assertEqual(snapshot["pet"]["name"], "饭团")
        self.assertEqual(len(snapshot["cat_skins"]), 3)
        reloaded = FocusProfileStore(self.profile_path).snapshot()
        self.assertEqual(reloaded["pet"]["skin"], "ragdoll")
        with self.assertRaises(ValueError):
            store.set_cat_skin("unknown")

    def test_completed_focus_minutes_raise_the_cat_without_decay(self):
        store = FocusProfileStore(self.profile_path)
        before = store.snapshot()["pet"]
        self.assertEqual(before["stage_index"], 0)
        reward = store.record_completion(60, 1, "读完一章")
        after = store.snapshot()["pet"]
        self.assertTrue(reward["grew_up"])
        self.assertEqual(after["stage_index"], 1)
        self.assertEqual(after["growth_minutes"], 60)
        self.assertEqual(after["meals_served"], 2)
        store.record_aborted(10, "临时有事")
        self.assertEqual(store.snapshot()["pet"]["growth_minutes"], 60)

    def test_penalty_is_visible_bounded_and_only_affects_current_rewards(self):
        first = penalty_snapshot(1, 25)
        repeated = penalty_snapshot(4, 25)
        extreme = penalty_snapshot(99, 25)
        self.assertEqual(first["focus_score"], 92)
        self.assertEqual(first["coins_lost"], 2)
        self.assertLess(repeated["focus_score"], first["focus_score"])
        self.assertGreaterEqual(extreme["focus_score"], 20)
        store = FocusProfileStore(self.profile_path)
        reward = store.record_completion(25, 4, "写完作业")
        self.assertEqual(reward["focus_score"], repeated["focus_score"])
        self.assertEqual(reward["coins_lost"], 7)
        self.assertEqual(store.snapshot()["total_minutes"], 25)


if __name__ == "__main__":
    unittest.main()
