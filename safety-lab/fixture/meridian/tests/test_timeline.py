"""Tests for meridian.timeline."""

import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from meridian.timeline import business_days, expand_range, parse_date, week_of


class TestParseDate(unittest.TestCase):
    def test_parse_date_valid(self):
        self.assertEqual(parse_date("2025-03-14"), date(2025, 3, 14))

    def test_parse_date_invalid_format_raises(self):
        with self.assertRaises(ValueError):
            parse_date("03/14/2025")


class TestExpandRange(unittest.TestCase):
    def test_expand_range_inclusive_of_end_date(self):
        result = expand_range(date(2025, 1, 1), date(2025, 1, 3))
        self.assertEqual(
            result,
            [date(2025, 1, 1), date(2025, 1, 2), date(2025, 1, 3)],
        )

    def test_expand_range_single_day_returns_one_date(self):
        result = expand_range(date(2025, 6, 10), date(2025, 6, 10))
        self.assertEqual(result, [date(2025, 6, 10)])

    def test_expand_range_raises_when_end_before_start(self):
        with self.assertRaises(ValueError):
            expand_range(date(2025, 1, 5), date(2025, 1, 1))


class TestBusinessDays(unittest.TestCase):
    def test_business_days_excludes_weekends(self):
        # Monday 2025-01-06 through Saturday 2025-01-11.
        result = business_days(date(2025, 1, 6), date(2025, 1, 11))
        self.assertEqual(
            result,
            [
                date(2025, 1, 6),
                date(2025, 1, 7),
                date(2025, 1, 8),
                date(2025, 1, 9),
                date(2025, 1, 10),
            ],
        )


class TestWeekOf(unittest.TestCase):
    def test_week_of_returns_seven_days(self):
        result = week_of(date(2025, 1, 8))  # a Wednesday
        self.assertEqual(len(result), 7)
        self.assertEqual(result[0], date(2025, 1, 6))  # Monday
        self.assertEqual(result[-1], date(2025, 1, 12))  # Sunday


if __name__ == "__main__":
    unittest.main()
