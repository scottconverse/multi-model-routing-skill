"""Tests for meridian.report."""

import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from meridian.report import busiest_day, daily_counts, format_report


class TestDailyCounts(unittest.TestCase):
    def test_daily_counts_counts_events_per_day(self):
        events = [
            (date(2025, 2, 3), "morning show"),
            (date(2025, 2, 3), "call-in segment"),
            (date(2025, 2, 4), "news brief"),
        ]
        counts = daily_counts(events, date(2025, 2, 3), date(2025, 2, 5))
        self.assertEqual(counts[date(2025, 2, 3)], 2)
        self.assertEqual(counts[date(2025, 2, 4)], 1)

    def test_daily_counts_ignores_events_outside_range(self):
        events = [
            (date(2025, 2, 3), "morning show"),
            (date(2025, 1, 1), "out of range"),
        ]
        counts = daily_counts(events, date(2025, 2, 3), date(2025, 2, 5))
        self.assertEqual(sum(counts.values()), 1)


class TestFormatReport(unittest.TestCase):
    def test_format_report_contains_title_and_total(self):
        events = [(date(2025, 2, 3), "morning show")]
        text = format_report(
            events, date(2025, 2, 3), date(2025, 2, 5), title="Test Report"
        )
        self.assertIn("Test Report", text)
        self.assertIn("2025-02-03: 1 event(s)", text)
        self.assertIn("Total: 1 event(s)", text)


class TestBusiestDay(unittest.TestCase):
    def test_busiest_day_returns_max_with_tie_break(self):
        events = [
            (date(2025, 2, 3), "a"),
            (date(2025, 2, 3), "b"),
            (date(2025, 2, 4), "c"),
        ]
        result = busiest_day(events, date(2025, 2, 3), date(2025, 2, 5))
        self.assertEqual(result, (date(2025, 2, 3), 2))


if __name__ == "__main__":
    unittest.main()
