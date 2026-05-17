"""Utilities for formatting domain values in user-facing texts."""

from datetime import date, time


def format_date(value: date) -> str:
    """Format date in 24-hour format."""
    return value.strftime("%d.%m.%Y")

def format_time(value: time) -> str:
    """Format time in 24-hour format."""
    return value.strftime("%H:%M")

def format_reward(minutes: int, color_scheme: str = "🟢⚪🔴") -> str:
    """Format minute reward with a status icon and always-signed value."""
    if len(color_scheme) != 3:
        raise ValueError("color_scheme must contain exactly three symbols.")

    positive, zero, negative = color_scheme
    if minutes == 0:
        icon = zero
    elif minutes > 0:
        icon = positive
    else:
        icon = negative

    return f"{icon} {minutes:+d}"
