"""Visible but bounded penalties for a single focus session.

The system never removes historic growth, levels, or already-earned currency.
Penalties only reduce rewards that are still available in the current round.
"""

from __future__ import annotations

import math


PENALTY_STEPS = (8, 14, 18, 20)


def penalty_snapshot(alert_count: int, duration_minutes: int) -> dict:
    alerts = max(0, int(alert_count))
    duration = max(1, int(duration_minutes))
    points = sum(PENALTY_STEPS[min(index, len(PENALTY_STEPS) - 1)] for index in range(alerts))
    points = min(80, points)
    focus_score = max(20, 100 - points)
    potential_coins = max(1, duration // 5) + 3
    coins_lost = min(max(0, potential_coins - 1), alerts * 2)
    xp_lost = min(20, math.ceil(points / 2))
    if focus_score >= 92:
        grade = "S"
    elif focus_score >= 78:
        grade = "A"
    elif focus_score >= 60:
        grade = "B"
    elif focus_score >= 40:
        grade = "C"
    else:
        grade = "D"
    next_step = PENALTY_STEPS[min(alerts, len(PENALTY_STEPS) - 1)]
    return {
        "alert_count": alerts,
        "penalty_points": points,
        "focus_score": focus_score,
        "grade": grade,
        "potential_coins": potential_coins,
        "coins_lost": coins_lost,
        "xp_lost": xp_lost,
        "next_penalty_points": next_step,
    }
