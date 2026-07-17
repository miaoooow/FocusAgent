"""Curated and learnable related-software suggestions for whitelist sessions."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .contracts import TargetRule
from .matcher import APP_PROCESS_ALIASES
from .paths import resource_root, user_data_root
from .window_monitor import ForegroundSnapshot


@dataclass(frozen=True)
class RelatedSuggestion:
    suggestion_id: str
    source_process: str
    process_name: str
    label: str
    reason: str
    confidence: float
    soft_grace_seconds: int

    @property
    def rule(self) -> TargetRule:
        return TargetRule("process", self.process_name, "exact")

    def to_dict(self) -> dict:
        return {
            "id": self.suggestion_id,
            "source_process": self.source_process,
            "process_name": self.process_name,
            "label": self.label,
            "reason": self.reason,
            "confidence": self.confidence,
            "soft_grace_seconds": self.soft_grace_seconds,
            "rule": {"kind": "process", "value": self.process_name, "match": "exact"},
        }


class SoftwareRelationStore:
    def __init__(self, database_path: Path | None = None, learned_path: Path | None = None):
        self.database_path = database_path or resource_root() / "data" / "software_relations.json"
        self.learned_path = learned_path or user_data_root() / "learned_relations.json"
        payload = json.loads(self.database_path.read_text(encoding="utf-8"))
        if payload.get("schema_version") != 1 or not isinstance(payload.get("applications"), dict):
            raise ValueError("关联软件数据库格式不合法")
        self.applications: dict[str, list[dict]] = {
            str(key).casefold(): list(value) for key, value in payload["applications"].items()
        }
        self.learned: set[tuple[str, str]] = self._load_learned()

    def _load_learned(self) -> set[tuple[str, str]]:
        try:
            payload = json.loads(self.learned_path.read_text(encoding="utf-8"))
            return {
                (str(item["source"]).casefold(), str(item["process"]).casefold())
                for item in payload.get("relations", [])
            }
        except (OSError, ValueError, KeyError, TypeError):
            return set()

    def remember(self, suggestion: RelatedSuggestion) -> None:
        self.learned.add((suggestion.source_process.casefold(), suggestion.process_name.casefold()))
        self.learned_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": 1,
            "relations": [
                {"source": source, "process": process}
                for source, process in sorted(self.learned)
            ],
        }
        temporary = self.learned_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temporary.replace(self.learned_path)

    def stats(self) -> dict[str, int]:
        return {
            "application_count": len(self.applications),
            "relation_count": sum(len(items) for items in self.applications.values()),
            "learned_count": len(self.learned),
        }

    @staticmethod
    def _allowed_processes(rules: tuple[TargetRule, ...]) -> set[str]:
        processes: set[str] = set()
        for rule in rules:
            if rule.kind == "process":
                processes.add(Path(rule.value).name.casefold())
            elif rule.kind == "app":
                processes.update(name.casefold() for name in APP_PROCESS_ALIASES.get(rule.value.casefold(), set()))
        return processes

    def suggest(
        self, allowed_rules: tuple[TargetRule, ...], snapshot: ForegroundSnapshot
    ) -> RelatedSuggestion | None:
        current = Path(snapshot.process_name).name.casefold()
        if not current:
            return None
        title = snapshot.window_title.casefold()
        for source in self._allowed_processes(allowed_rules):
            for entry in self.applications.get(source, []):
                if str(entry.get("process", "")).casefold() != current:
                    continue
                keywords = [str(item).casefold() for item in entry.get("title_keywords", [])]
                if keywords and not any(keyword in title for keyword in keywords):
                    continue
                return RelatedSuggestion(
                    suggestion_id=f"{source}>{current}",
                    source_process=source,
                    process_name=current,
                    label=str(entry.get("label") or Path(current).stem),
                    reason=str(entry.get("reason") or "可能与当前任务相关"),
                    confidence=max(0.0, min(1.0, float(entry.get("confidence", 0.8)))),
                    soft_grace_seconds=max(30, min(300, int(entry.get("soft_grace_seconds", 60)))),
                )
        return None

    def is_remembered(self, suggestion: RelatedSuggestion) -> bool:
        return (suggestion.source_process.casefold(), suggestion.process_name.casefold()) in self.learned
