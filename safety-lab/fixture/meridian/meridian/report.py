"""Program report generation, built on top of meridian.timeline.

Aggregates a list of (date, event_name) tuples into per-day counts and
formats them into a plain-text report.
"""

from __future__ import annotations

from collections import Counter
from datetime import date

from .timeline import expand_range


def daily_counts(
    events: list[tuple[date, str]], start_date: date, end_date: date
) -> dict[date, int]:
    """Count events per day across expand_range(start_date, end_date),
    including days that have zero events. Events outside the range are
    ignored."""
    days = expand_range(start_date, end_date)
    valid_days = set(days)
    counts = Counter()
    for day, _name in events:
        if day in valid_days:
            counts[day] += 1
    return {d: counts.get(d, 0) for d in days}


def format_report(
    events: list[tuple[date, str]],
    start_date: date,
    end_date: date,
    title: str = "Program Schedule",
) -> str:
    """Format a plain-text report: a header followed by one line per day
    with that day's event count, and a trailing total."""
    counts = daily_counts(events, start_date, end_date)
    lines = [title, "=" * len(title)]
    total = 0
    for day, count in counts.items():
        lines.append(f"{day.isoformat()}: {count} event(s)")
        total += count
    lines.append("-" * 20)
    lines.append(f"Total: {total} event(s) over {len(counts)} day(s)")
    return "\n".join(lines)


def busiest_day(
    events: list[tuple[date, str]], start_date: date, end_date: date
) -> tuple[date, int] | None:
    """Return the (date, count) pair for the day with the most events in
    the range. Ties are broken by the earliest date. Returns None if the
    range contains no days."""
    counts = daily_counts(events, start_date, end_date)
    if not counts:
        return None
    return max(counts.items(), key=lambda kv: (kv[1], -kv[0].toordinal()))
