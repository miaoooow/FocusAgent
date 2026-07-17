import json
import unittest

from focus_agent.contracts import parse_session_response
from focus_agent.runtime import FocusSessionEngine, SessionState
from focus_agent.window_monitor import ForegroundSnapshot


def make_config(mode="whitelist", duration=1, max_alerts=2):
    target = {"kind": "process", "value": "Code.exe", "match": "exact"}
    payload = {
        "schema_version": 1,
        "duration_minutes": duration,
        "mode": mode,
        "allowed_targets": [target] if mode == "whitelist" else [],
        "blocked_targets": [target] if mode == "blacklist" else [],
        "grace_seconds": 5,
        "check_interval_seconds": 2,
        "popup_cooldown_seconds": 30,
        "max_alerts": max_alerts,
        "roast_intensity": "mild",
        "needs_clarification": False,
        "clarification_question": "",
    }
    if mode == "blackout":
        payload["allowed_targets"] = []
        payload["blocked_targets"] = []
    return parse_session_response(json.dumps(payload))


def snapshot(process="chrome.exe", pid=22, idle=0.1):
    return ForegroundSnapshot(
        hwnd=10,
        pid=pid,
        process_name=process,
        window_title="Example",
        input_idle_seconds=idle,
    )


class RuntimeTests(unittest.TestCase):
    def test_grace_cooldown_and_max_alerts(self):
        engine = FocusSessionEngine(make_config(duration=2), own_pid=99, now=0)
        self.assertIsNone(engine.tick(snapshot(), now=0).alert)
        self.assertIsNone(engine.tick(snapshot(), now=4).alert)
        self.assertIsNotNone(engine.tick(snapshot(), now=5).alert)
        self.assertIsNone(engine.tick(snapshot(), now=20).alert)
        self.assertIsNotNone(engine.tick(snapshot(), now=35).alert)
        self.assertIsNone(engine.tick(snapshot(), now=70).alert)
        self.assertEqual(engine.alert_count, 2)

    def test_compliant_window_resets_violation(self):
        engine = FocusSessionEngine(make_config(), own_pid=99, now=0)
        engine.tick(snapshot(), now=0)
        update = engine.tick(snapshot(process="Code.exe"), now=4)
        self.assertFalse(update.violating)
        self.assertIsNone(engine.tick(snapshot(), now=7).alert)

    def test_pause_does_not_consume_session_time(self):
        engine = FocusSessionEngine(make_config(), own_pid=99, now=0)
        engine.pause(now=10)
        self.assertEqual(engine.remaining_seconds(now=30), 50)
        engine.resume(now=30)
        self.assertEqual(engine.remaining_seconds(now=40), 40)

    def test_completion_is_reported_once(self):
        engine = FocusSessionEngine(make_config(), own_pid=99, now=0)
        first = engine.tick(snapshot(process="Code.exe"), now=60)
        second = engine.tick(snapshot(process="Code.exe"), now=61)
        self.assertEqual(first.state, SessionState.COMPLETED)
        self.assertTrue(first.just_completed)
        self.assertFalse(second.just_completed)

    def test_blackout_uses_recent_input_not_window_name(self):
        engine = FocusSessionEngine(make_config(mode="blackout"), own_pid=99, now=0)
        self.assertTrue(engine.tick(snapshot(idle=0.2), now=0).violating)
        self.assertFalse(engine.tick(snapshot(idle=10), now=1).violating)


if __name__ == "__main__":
    unittest.main()

