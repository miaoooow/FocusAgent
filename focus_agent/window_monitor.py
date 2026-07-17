"""Minimal Win32 foreground-window and input-activity reader."""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ForegroundSnapshot:
    hwnd: int
    pid: int
    process_name: str
    window_title: str
    input_idle_seconds: float
    browser_domain: str = ""

    @property
    def local_label(self) -> str:
        process = Path(self.process_name).stem if self.process_name else "未知应用"
        title = " ".join(self.window_title.split())[:60]
        if self.browser_domain:
            return f"{process} · {self.browser_domain}"
        return f"{process} · {title}" if title else process


if os.name == "nt":
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    SW_RESTORE = 9

    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]

    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetLastInputInfo.argtypes = [ctypes.POINTER(LASTINPUTINFO)]
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD),
    ]


def _window_title(hwnd: int) -> str:
    if os.name != "nt" or not hwnd:
        return ""
    length = user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(max(1, length + 1))
    user32.GetWindowTextW(hwnd, buffer, len(buffer))
    return buffer.value


def _process_path(pid: int) -> str:
    if os.name != "nt" or not pid:
        return ""
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        size = wintypes.DWORD(32768)
        buffer = ctypes.create_unicode_buffer(size.value)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return buffer.value
        return ""
    finally:
        kernel32.CloseHandle(handle)


def input_idle_seconds() -> float:
    if os.name != "nt":
        return 9999.0
    info = LASTINPUTINFO(cbSize=ctypes.sizeof(LASTINPUTINFO))
    if not user32.GetLastInputInfo(ctypes.byref(info)):
        return 9999.0
    # Both values are DWORD milliseconds and wrap together after ~49.7 days.
    elapsed_ms = (kernel32.GetTickCount() - info.dwTime) & 0xFFFFFFFF
    return elapsed_ms / 1000.0


def get_foreground_snapshot() -> ForegroundSnapshot:
    if os.name != "nt":
        raise RuntimeError("前台窗口监测仅支持Windows。")
    hwnd = int(user32.GetForegroundWindow() or 0)
    pid_value = wintypes.DWORD(0)
    if hwnd:
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid_value))
    path = _process_path(pid_value.value)
    return ForegroundSnapshot(
        hwnd=hwnd,
        pid=int(pid_value.value),
        process_name=Path(path).name if path else "",
        window_title=_window_title(hwnd),
        input_idle_seconds=input_idle_seconds(),
    )


def activate_window(hwnd: int) -> bool:
    if os.name != "nt" or not hwnd:
        return False
    user32.ShowWindow(hwnd, SW_RESTORE)
    return bool(user32.SetForegroundWindow(hwnd))
