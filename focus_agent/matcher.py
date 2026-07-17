"""Deterministic matching between validated target rules and Win32 metadata."""

from __future__ import annotations

from pathlib import Path

from .contracts import SessionConfig, TargetRule
from .window_monitor import ForegroundSnapshot


APP_PROCESS_ALIASES = {
    "vs code": {"code.exe"},
    "visual studio code": {"code.exe"},
    "vscode": {"code.exe"},
    "记事本": {"notepad.exe"},
    "notepad": {"notepad.exe"},
    "word": {"winword.exe"},
    "microsoft word": {"winword.exe"},
    "excel": {"excel.exe"},
    "powerpoint": {"powerpnt.exe"},
    "edge": {"msedge.exe"},
    "chrome": {"chrome.exe"},
    "firefox": {"firefox.exe"},
}

BROWSER_PROCESSES = {"chrome.exe", "msedge.exe", "firefox.exe"}


def _normalized(value: str) -> str:
    return " ".join(value.casefold().split())


def rule_matches(rule: TargetRule, snapshot: ForegroundSnapshot) -> bool:
    value = _normalized(rule.value)
    process = _normalized(Path(snapshot.process_name).name)
    process_stem = _normalized(Path(snapshot.process_name).stem)
    title = _normalized(snapshot.window_title)
    domain = _normalized(snapshot.browser_domain).removeprefix("www.").rstrip(".")

    if rule.kind == "process":
        return process == value
    if rule.kind == "window_title":
        return value in title
    if rule.kind == "domain":
        expected = value.removeprefix("www.").rstrip(".")
        if not domain:
            return False
        if rule.match == "exact":
            return domain == expected
        return domain == expected or domain.endswith(f".{expected}")
    if rule.kind == "app":
        aliases = APP_PROCESS_ALIASES.get(value, set())
        return (
            process in aliases
            or process == value
            or process_stem == value.removesuffix(".exe")
            or value in title
        )
    return False


def matching_rules(
    rules: tuple[TargetRule, ...], snapshot: ForegroundSnapshot
) -> tuple[TargetRule, ...]:
    return tuple(rule for rule in rules if rule_matches(rule, snapshot))


def browser_domain_is_unknown(config: SessionConfig, snapshot: ForegroundSnapshot) -> bool:
    """Return true when a domain whitelist cannot currently be verified.

    Uncertainty is not evidence of distraction. The controller uses this signal
    to fail open without awarding a violation while the local bridge reconnects.
    """
    process = _normalized(Path(snapshot.process_name).name)
    return (
        config.mode == "whitelist"
        and process in BROWSER_PROCESSES
        and not _normalized(snapshot.browser_domain)
        and any(rule.kind == "domain" for rule in config.allowed_targets)
    )


def unsupported_rules(config: SessionConfig) -> tuple[TargetRule, ...]:
    # Domain rules are supported when the local browser bridge is connected.
    # The controller performs that live capability check before session start.
    return ()


def describe_config(config: SessionConfig) -> str:
    labels = [item.value for item in config.allowed_targets + config.blocked_targets]
    target_text = "、".join(labels) if labels else "全部电脑操作"
    descriptions = {
        "whitelist": f"只允许：{target_text}",
        "blacklist": f"禁止：{target_text}",
        "blackout": "完全离开电脑",
    }
    return descriptions[config.mode]
