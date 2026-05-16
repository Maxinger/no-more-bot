"""Utilities for formatting domain values in user-facing texts."""

from datetime import date, time


def format_date(value: date) -> str:
    """Format date in 24-hour format."""
    return value.strftime("%d.%m.%Y")

def format_time(value: time) -> str:
    """Format time in 24-hour format."""
    return value.strftime("%H:%M")

def format_reward(minutes: int) -> str:
    """Format minute reward total (+ earlier than goal, - later) with status emoji."""
    if minutes == 0:
        return "⚪ 0"
    if minutes > 0:
        return f"🟢 +{minutes}"
    return f"🔴 {minutes}"
