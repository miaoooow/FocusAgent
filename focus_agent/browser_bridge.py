"""Ephemeral active-tab domain bridge for Chrome/Edge extensions."""

from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass, replace

from .window_monitor import ForegroundSnapshot


BROWSER_PROCESSES = {"chrome.exe", "msedge.exe", "firefox.exe"}
DOMAIN_PATTERN = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ActiveBrowserTab:
    process_name: str
    domain: str
    title: str
    reported_at: float


class BrowserBridge:
    """Keep only the latest active domain in memory; never persist browsing data."""

    FRESH_SECONDS = 6.0

    def __init__(self):
        self._lock = threading.Lock()
        self._tabs: dict[str, ActiveBrowserTab] = {}

    @staticmethod
    def _domain(value: object) -> str:
        domain = str(value or "").strip().casefold().rstrip(".")
        if domain.startswith("www."):
            domain = domain[4:]
        if not DOMAIN_PATTERN.fullmatch(domain):
            raise ValueError("浏览器桥接提交了无效域名")
        return domain

    def report(self, payload: dict) -> dict:
        process = str(payload.get("process_name", "")).strip().casefold()
        if process not in BROWSER_PROCESSES:
            raise ValueError("浏览器桥接来源不受支持")
        tab = ActiveBrowserTab(
            process_name=process,
            domain=self._domain(payload.get("domain")),
            title=" ".join(str(payload.get("title", "")).split())[:120],
            reported_at=time.monotonic(),
        )
        with self._lock:
            self._tabs[process] = tab
        return self.status()

    def enrich(self, snapshot: ForegroundSnapshot, now: float | None = None) -> ForegroundSnapshot:
        process = str(snapshot.process_name or "").casefold()
        if process not in BROWSER_PROCESSES:
            return snapshot
        current = time.monotonic() if now is None else now
        with self._lock:
            tab = self._tabs.get(process)
        if tab is None or current - tab.reported_at > self.FRESH_SECONDS:
            return snapshot
        return replace(
            snapshot,
            browser_domain=tab.domain,
            window_title=tab.title or snapshot.window_title,
        )

    def status(self, now: float | None = None) -> dict:
        current = time.monotonic() if now is None else now
        with self._lock:
            tabs = list(self._tabs.values())
        fresh = [tab for tab in tabs if current - tab.reported_at <= self.FRESH_SECONDS]
        latest = max(fresh, key=lambda tab: tab.reported_at, default=None)
        return {
            "connected": latest is not None,
            "browser": latest.process_name.removesuffix(".exe") if latest else "",
            "current_domain": latest.domain if latest else "",
            "age_seconds": round(max(0.0, current - latest.reported_at), 1) if latest else None,
            "privacy": "只在内存保留当前域名，不保存完整网址或浏览历史",
        }
