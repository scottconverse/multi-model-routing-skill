"""Timeline utilities for building daily program schedules.

All functions here operate on stdlib `datetime.date` objects so the rest of
the project (and its tests) can stay dependency-free.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta


def parse_date(value: str) -> date:
    """Parse an ISO date string (YYYY-MM-DD) into a date object.

    Raises ValueError if `value` is not a valid ISO date string.
    """
    return datetime.strptime(value, "%Y-%m-%d").date()


def expand_range(start_date: date, end_date: date) -> list[date]:
    """Return the list of calendar dates from start_date to end_date,
    inclusive of both endpoints.

    Raises ValueError if end_date is before start_date.
    """
    if end_date < start_date:
        raise ValueError(f"end_date {end_date} is before start_date {start_date}")
    days = (end_date - start_date).days
    return [start_date + timedelta(days=n) for n in range(days)]


def business_days(start_date: date, end_date: date) -> list[date]:
    """Return the subset of expand_range(start_date, end_date) that fall on
    a weekday (Monday through Friday)."""
    return [d for d in expand_range(start_date, end_date) if d.weekday() < 5]


def week_of(day: date) -> list[date]:
    """Return the 7 dates (Monday through Sunday) of the ISO week that
    contains `day`."""
    monday = day - timedelta(days=day.weekday())
    return expand_range(monday, monday + timedelta(days=6))
