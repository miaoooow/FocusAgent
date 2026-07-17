"""Strict local validation for model outputs.

Prompts improve compliance; these validators are the actual trust boundary.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any


MODES = {"whitelist", "blacklist", "blackout"}
TARGET_KINDS = {"app", "process", "domain", "window_title"}
MATCH_MODES = {"exact", "domain_suffix", "contains"}
INTENSITIES = {"mild", "spicy"}

SESSION_FIELDS = {
    "schema_version", "duration_minutes", "mode", "allowed_targets",
    "blocked_targets", "grace_seconds", "check_interval_seconds",
    "popup_cooldown_seconds", "max_alerts", "roast_intensity",
    "needs_clarification", "clarification_question",
}

ROAST_FORBIDDEN_TERMS = {
    "废物", "没救了", "蠢", "懒货", "小猪", "你怎么这么",
    "果然坚持不了", "没用", "失败者",
}


@dataclass(frozen=True)
class TargetRule:
    kind: str
    value: str
    match: str


@dataclass(frozen=True)
class SessionConfig:
    schema_version: int
    duration_minutes: int
    mode: str
    allowed_targets: tuple[TargetRule, ...]
    blocked_targets: tuple[TargetRule, ...]
    grace_seconds: int
    check_interval_seconds: int
    popup_cooldown_seconds: int
    max_alerts: int
    roast_intensity: str
    needs_clarification: bool
    clarification_question: str


def session_config_to_dict(config: SessionConfig) -> dict[str, Any]:
    return {
        "schema_version": config.schema_version,
        "duration_minutes": config.duration_minutes,
        "mode": config.mode,
        "allowed_targets": [
            {"kind": item.kind, "value": item.value, "match": item.match}
            for item in config.allowed_targets
        ],
        "blocked_targets": [
            {"kind": item.kind, "value": item.value, "match": item.match}
            for item in config.blocked_targets
        ],
        "grace_seconds": config.grace_seconds,
        "check_interval_seconds": config.check_interval_seconds,
        "popup_cooldown_seconds": config.popup_cooldown_seconds,
        "max_alerts": config.max_alerts,
        "roast_intensity": config.roast_intensity,
        "needs_clarification": config.needs_clarification,
        "clarification_question": config.clarification_question,
    }


def _bounded_int(payload: dict, field: str, low: int, high: int) -> int:
    value = payload.get(field)
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError(f"{field}必须是{low}至{high}的整数")
    return value


def _parse_targets(value: object, field: str) -> tuple[TargetRule, ...]:
    if not isinstance(value, list):
        raise ValueError(f"{field}必须是数组")
    parsed: list[TargetRule] = []
    for item in value:
        if not isinstance(item, dict) or set(item) != {"kind", "value", "match"}:
            raise ValueError(f"{field}中的目标结构不合法")
        kind, target, match = item["kind"], item["value"], item["match"]
        if kind not in TARGET_KINDS or match not in MATCH_MODES:
            raise ValueError(f"{field}中的kind或match不合法")
        if not isinstance(target, str) or not target.strip() or len(target) > 100:
            raise ValueError(f"{field}中的value不合法")
        if re.search(r"[\x00-\x1f\x7f]", target):
            raise ValueError(f"{field}中的value含控制字符")
        if kind in {"app", "process"} and match != "exact":
            raise ValueError(f"{kind}目标只能使用exact匹配")
        if kind == "domain" and match not in {"exact", "domain_suffix"}:
            raise ValueError("domain目标只能使用exact或domain_suffix匹配")
        if kind == "domain" and (
            "://" in target or "/" in target or " " in target or "." not in target
        ):
            raise ValueError("domain目标只能包含规范域名")
        if kind == "window_title" and match != "contains":
            raise ValueError("window_title目标只能使用contains匹配")
        parsed.append(TargetRule(kind=kind, value=target.strip(), match=match))
    return tuple(parsed)


def parse_session_response(raw_text: str) -> SessionConfig:
    """Reject malformed or semantically unsafe model configuration."""
    try:
        payload = json.loads(raw_text.strip())
    except json.JSONDecodeError as exc:
        raise ValueError("模型没有返回合法JSON") from exc
    if not isinstance(payload, dict) or set(payload) != SESSION_FIELDS:
        raise ValueError("会话配置字段不完整或包含未知字段")
    if payload.get("schema_version") != 1:
        raise ValueError("不支持的schema_version")

    mode = payload.get("mode")
    intensity = payload.get("roast_intensity")
    if mode not in MODES or intensity not in INTENSITIES:
        raise ValueError("mode或roast_intensity不合法")

    allowed = _parse_targets(payload.get("allowed_targets"), "allowed_targets")
    blocked = _parse_targets(payload.get("blocked_targets"), "blocked_targets")
    needs_clarification = payload.get("needs_clarification")
    question = payload.get("clarification_question")
    if not isinstance(needs_clarification, bool) or not isinstance(question, str):
        raise ValueError("澄清字段类型不合法")
    if len(question.strip()) > 120 or re.search(r"[\x00-\x1f\x7f]", question):
        raise ValueError("澄清问题过长或含控制字符")
    if needs_clarification != bool(question.strip()):
        raise ValueError("澄清状态与澄清问题不一致")
    if mode == "blackout" and (allowed or blocked):
        raise ValueError("blackout模式不应包含目标")
    if mode == "whitelist" and blocked:
        raise ValueError("whitelist模式不应包含禁止目标")
    if mode == "blacklist" and allowed:
        raise ValueError("blacklist模式不应包含允许目标")
    if mode == "whitelist" and not allowed and not needs_clarification:
        raise ValueError("whitelist模式缺少允许目标")
    if mode == "blacklist" and not blocked and not needs_clarification:
        raise ValueError("blacklist模式缺少禁止目标")

    return SessionConfig(
        schema_version=1,
        duration_minutes=_bounded_int(payload, "duration_minutes", 1, 480),
        mode=mode,
        allowed_targets=allowed,
        blocked_targets=blocked,
        grace_seconds=_bounded_int(payload, "grace_seconds", 5, 120),
        check_interval_seconds=_bounded_int(payload, "check_interval_seconds", 1, 10),
        popup_cooldown_seconds=_bounded_int(payload, "popup_cooldown_seconds", 30, 600),
        max_alerts=_bounded_int(payload, "max_alerts", 1, 20),
        roast_intensity=intensity,
        needs_clarification=needs_clarification,
        clarification_question=question.strip(),
    )


def sanitize_roast_response(raw_text: str) -> str | None:
    """Accept one safe 6-13 character line, otherwise request a local fallback."""
    line = raw_text.strip().strip('"“”\'‘’')
    if "\n" in line or "\r" in line:
        return None
    visible_length = len(re.sub(r"\s+", "", line))
    if not 6 <= visible_length <= 13:
        return None
    if any(term in line for term in ROAST_FORBIDDEN_TERMS):
        return None
    if "http" in line.lower() or "www." in line.lower():
        return None
    return line


def sanitize_summary_response(raw_text: str) -> str | None:
    """Accept one safe 4-20 character session-summary line."""
    line = raw_text.strip().strip('"“”\'‘’')
    if "\n" in line or "\r" in line:
        return None
    visible_length = len(re.sub(r"\s+", "", line))
    if not 4 <= visible_length <= 20:
        return None
    if any(term in line for term in ROAST_FORBIDDEN_TERMS):
        return None
    if "http" in line.lower() or "www." in line.lower():
        return None
    return line
