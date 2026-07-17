"""Pure-rule focus session state machine; no model calls are allowed here."""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .contracts import SessionConfig
from .matcher import matching_rules
from .window_monitor import ForegroundSnapshot


class SessionState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    STOPPED = "stopped"


@dataclass(frozen=True)
class AlertEvent:
    target_label: str
    elapsed_seconds: int
    remaining_seconds: int
    alert_number: int


@dataclass(frozen=True)
class RuntimeUpdate:
    state: SessionState
    remaining_seconds: int
    violating: bool
    violation_elapsed_seconds: int
    target_label: str
    alert: AlertEvent | None = None
    just_completed: bool = False


class FocusSessionEngine:
    def __init__(self, config: SessionConfig, own_pid: int, now: float | None = None):
        self.config = config
        self.own_pid = own_pid
        self.state = SessionState.RUNNING
        self.started_at = time.monotonic() if now is None else now
        self.pause_started_at: float | None = None
        self.violation_started_at: float | None = None
        self.last_alert_at: float | None = None
        self.alert_count = 0
        self._completion_reported = False

    def remaining_seconds(self, now: float | None = None) -> int:
        current = time.monotonic() if now is None else now
        if self.state == SessionState.PAUSED and self.pause_started_at is not None:
            current = self.pause_started_at
        elapsed = max(0.0, current - self.started_at)
        return max(0, int(round(self.config.duration_minutes * 60 - elapsed)))

    def pause(self, now: float | None = None) -> None:
        if self.state != SessionState.RUNNING:
            return
        self.pause_started_at = time.monotonic() if now is None else now
        self.violation_started_at = None
        self.state = SessionState.PAUSED

    def resume(self, now: float | None = None) -> None:
        if self.state != SessionState.PAUSED or self.pause_started_at is None:
            return
        current = time.monotonic() if now is None else now
        self.started_at += max(0.0, current - self.pause_started_at)
        self.pause_started_at = None
        self.violation_started_at = None
        self.state = SessionState.RUNNING

    def stop(self) -> None:
        if self.state not in {SessionState.COMPLETED, SessionState.STOPPED}:
            self.state = SessionState.STOPPED
        self.violation_started_at = None

    def _violation_status(
        self, snapshot: ForegroundSnapshot
    ) -> tuple[bool, str]:
        if snapshot.pid == self.own_pid:
            return False, "专注监督器"

        if self.config.mode == "blackout":
            active_window = max(2.5, self.config.check_interval_seconds * 1.5)
            return snapshot.input_idle_seconds <= active_window, "电脑操作"

        if self.config.mode == "whitelist":
            matched = matching_rules(self.config.allowed_targets, snapshot)
            process_label = Path(snapshot.process_name).stem if snapshot.process_name else "未知应用"
            return (not bool(matched)), process_label

        matched = matching_rules(self.config.blocked_targets, snapshot)
        label = matched[0].value if matched else snapshot.local_label
        return bool(matched), label

    def tick(
        self, snapshot: ForegroundSnapshot, now: float | None = None
    ) -> RuntimeUpdate:
        current = time.monotonic() if now is None else now
        remaining = self.remaining_seconds(current)

        if self.state == SessionState.RUNNING and remaining <= 0:
            self.state = SessionState.COMPLETED
            just_completed = not self._completion_reported
            self._completion_reported = True
            return RuntimeUpdate(
                self.state, 0, False, 0, "会话完成", just_completed=just_completed
            )

        if self.state != SessionState.RUNNING:
            return RuntimeUpdate(self.state, remaining, False, 0, self.state.value)

        violating, label = self._violation_status(snapshot)
        if not violating:
            self.violation_started_at = None
            return RuntimeUpdate(self.state, remaining, False, 0, label)

        if self.violation_started_at is None:
            self.violation_started_at = current
        violation_elapsed = max(0, int(current - self.violation_started_at))
        alert: AlertEvent | None = None

        grace_met = current - self.violation_started_at >= self.config.grace_seconds
        cooldown_met = (
            self.last_alert_at is None
            or current - self.last_alert_at >= self.config.popup_cooldown_seconds
        )
        if grace_met and cooldown_met and self.alert_count < self.config.max_alerts:
            self.alert_count += 1
            self.last_alert_at = current
            self.violation_started_at = current
            alert = AlertEvent(
                target_label=label,
                elapsed_seconds=max(self.config.grace_seconds, violation_elapsed),
                remaining_seconds=remaining,
                alert_number=self.alert_count,
            )

        return RuntimeUpdate(
            self.state,
            remaining,
            True,
            violation_elapsed,
            label,
            alert=alert,
        )
