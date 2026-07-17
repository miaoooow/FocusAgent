"""Database-backed goal classification and user-confirmed local learning."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

from .contracts import TargetRule
from .paths import resource_root, user_data_root


@dataclass(frozen=True)
class ScenarioMatch:
    scenario_id: str
    name: str
    description: str
    score: int
    targets: tuple[TargetRule, ...]


def _rule(payload: dict) -> TargetRule:
    kind = str(payload.get("kind", ""))
    value = str(payload.get("value", "")).strip()
    match = str(payload.get("match", ""))
    if kind not in {"app", "process", "domain", "window_title"}:
        raise ValueError("场景数据库包含未知目标类型")
    if not value or len(value) > 100:
        raise ValueError("场景数据库包含无效目标")
    if match not in {"exact", "domain_suffix", "contains"}:
        raise ValueError("场景数据库包含无效匹配方式")
    return TargetRule(kind, value, match)


def _compact(text: str) -> str:
    return re.sub(r"[\s，。！？、,.!?;；:：()（）【】\[\]\"'“”‘’]+", "", text.casefold())


def goal_fingerprint(text: str) -> str:
    compact = _compact(text)
    compact = re.sub(r"\d+(?:\.\d+)?(?:分钟|小时|min|h)", "", compact)
    for prefix in (
        "我要", "我想", "今天", "现在", "接下来", "帮我", "完成", "做完",
        "搞定", "继续", "开始", "专注", "分钟内", "小时内",
    ):
        compact = compact.replace(prefix, "")
    return compact[:96] or "空目标"


class GoalScenarioStore:
    """Match curated scenes first, then reuse user-confirmed similar goals."""

    def __init__(
        self,
        database_path: Path | None = None,
        learned_path: Path | None = None,
    ):
        self.database_path = database_path or resource_root() / "data" / "goal_scenarios.json"
        self.learned_path = learned_path or user_data_root() / "goal_scenario_memory.json"
        payload = json.loads(self.database_path.read_text(encoding="utf-8"))
        if payload.get("schema_version") != 1 or not isinstance(payload.get("scenarios"), list):
            raise ValueError("目标场景数据库格式不合法")
        self.scenarios = tuple(payload["scenarios"])
        self.learned = self._load_learned()

    def _load_learned(self) -> list[dict]:
        try:
            payload = json.loads(self.learned_path.read_text(encoding="utf-8"))
            if payload.get("schema_version") != 1:
                return []
            return list(payload.get("mappings", []))[:60]
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return []

    @staticmethod
    def _score(goal: str, scenario: dict) -> int:
        text = goal.casefold()
        compact = _compact(goal)
        if any(_compact(word) in compact for word in scenario.get("negative_keywords", [])):
            return 0
        strong_hits = sum(
            1 for word in scenario.get("strong_keywords", [])
            if str(word).casefold() in text or _compact(str(word)) in compact
        )
        weak_hits = sum(
            1 for word in scenario.get("weak_keywords", [])
            if str(word).casefold() in text or _compact(str(word)) in compact
        )
        if not strong_hits and weak_hits < 2:
            return 0
        return strong_hits * 8 + weak_hits * 3 + int(scenario.get("priority", 0)) // 20

    def match(self, goal: str) -> tuple[ScenarioMatch, ...]:
        candidates: list[tuple[dict, int]] = []
        for scenario in self.scenarios:
            score = self._score(goal, scenario)
            if score:
                candidates.append((scenario, score))
        candidates.sort(key=lambda item: (-item[1], -int(item[0].get("priority", 0))))

        # Output formats are alternatives. If "PPT" is present, do not also
        # recommend the complete Word stack merely because the user says 汇报.
        chosen_groups: set[str] = set()
        matches: list[ScenarioMatch] = []
        for scenario, score in candidates:
            group = str(scenario.get("exclusive_group", ""))
            if group and group in chosen_groups:
                continue
            if group:
                chosen_groups.add(group)
            matches.append(
                ScenarioMatch(
                    scenario_id=str(scenario["id"]),
                    name=str(scenario["name"]),
                    description=str(scenario["description"]),
                    score=score,
                    targets=tuple(_rule(item) for item in scenario.get("targets", [])),
                )
            )
            if len(matches) >= 3:
                break
        return tuple(matches)

    def catalog(self) -> tuple[dict, ...]:
        """Return the compact, non-sensitive catalog supplied to the model."""
        return tuple(
            {
                "id": str(item["id"]),
                "name": str(item["name"]),
                "description": str(item["description"]),
            }
            for item in self.scenarios
        )

    def targets_for_ids(self, scenario_ids: tuple[str, ...]) -> tuple[TargetRule, ...]:
        by_id = {str(item["id"]): item for item in self.scenarios}
        targets: list[TargetRule] = []
        for scenario_id in scenario_ids:
            scenario = by_id.get(str(scenario_id))
            if scenario:
                targets.extend(_rule(item) for item in scenario.get("targets", []))
        return tuple(targets)

    def learned_targets(self, goal: str) -> tuple[TargetRule, ...]:
        fingerprint = goal_fingerprint(goal)
        best: tuple[float, dict] | None = None
        for item in self.learned:
            saved = str(item.get("fingerprint", ""))
            if not saved:
                continue
            ratio = SequenceMatcher(None, fingerprint, saved).ratio()
            if ratio < 0.82:
                continue
            if best is None or ratio > best[0]:
                best = (ratio, item)
        if best is None:
            return ()
        try:
            return tuple(_rule(item) for item in best[1].get("targets", []))[:10]
        except ValueError:
            return ()

    def learn(self, goal: str, targets: tuple[TargetRule, ...]) -> None:
        if not goal.strip() or not targets:
            return
        fingerprint = goal_fingerprint(goal)
        mapping = {
            "fingerprint": fingerprint,
            "goal": " ".join(goal.split())[:160],
            "targets": [
                {"kind": item.kind, "value": item.value, "match": item.match}
                for item in targets[:10]
            ],
        }
        retained = [
            item for item in self.learned
            if str(item.get("fingerprint", "")) != fingerprint
        ]
        self.learned = [mapping, *retained][:60]
        self.learned_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.learned_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(
                {"schema_version": 1, "mappings": self.learned},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        temporary.replace(self.learned_path)

    def stats(self) -> dict:
        return {
            "scenarios": len(self.scenarios),
            "learned_goals": len(self.learned),
            "database_path": str(self.database_path),
        }
